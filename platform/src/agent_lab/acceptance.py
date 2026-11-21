"""Executable M0 acceptance metrics derived from persisted artifacts."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from agent_lab.domain.contracts_v0_1 import (
    AgentStateSnapshot, AggregatedResult, AssignmentSnapshot, AtomicClaim,
    DependencyRecord, MessageEnvelope, PlatformInputBundle, RunManifest,
    QuestionCheckpoint, QuestionRunStatus, RunState, RunStatus, RunSummary, RuntimeMessageNode,
    RuntimeNodeKind, TraceEvent,
)
from agent_lab.evaluation_trace import (
    EvaluationTraceValidationError, reconstruct_request_messages,
    validate_reconstructability,
)
from agent_lab.topology import directed_edges
from agent_lab.truth_view import TruthViewLoader


@dataclass(frozen=True)
class Metric:
    name: str
    numerator: int
    denominator: int
    expected: str
    passed: bool

    @property
    def rate(self) -> float:
        return 1.0 if self.denominator == 0 else self.numerator / self.denominator


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[Any]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _claim_list(message: MessageEnvelope) -> tuple[AtomicClaim, ...]:
    return tuple(AtomicClaim.model_validate(value) for value in message.metadata.get("machine_claims", []))


def _source_refs(claims: Iterable[AtomicClaim]):
    for claim in claims:
        yield from claim.source_refs


def _expected_trace_counts(manifest: RunManifest) -> Counter[str]:
    questions = len(manifest.selected_sample_ids)
    rounds = manifest.communication_rounds
    edges = len(directed_edges(manifest.topology_kind))
    calls = questions * (3 + edges * rounds)
    deliveries = questions * edges * rounds
    topology_edges = directed_edges(manifest.topology_kind)
    incoming_counts = Counter(receiver for _, receiver in topology_edges)
    dependencies_per_question = edges
    if rounds > 1:
        dependencies_per_question += (rounds - 1) * sum(
            1 + incoming_counts[sender] for sender, _ in topology_edges
        )
    dependencies = questions * dependencies_per_question
    return Counter({
        "RUN_STARTED": 1, "RUN_FINISHED": 1,
        "QUESTION_STARTED": questions, "QUESTION_FINISHED": questions,
        "DOCUMENT_ASSIGNMENT_FROZEN": questions,
        "INITIAL_READ_STARTED": questions, "INITIAL_READ_FINISHED": questions,
        "ROUND_STARTED": questions * rounds, "ROUND_FINISHED": questions * rounds,
        "MODEL_ATTEMPT_STARTED": calls, "MODEL_RESPONSE_RECEIVED": calls,
        "MESSAGE_NODE_CREATED": calls, "DEPENDENCY_RECORDED": dependencies,
        "MESSAGE_PARSED": deliveries, "MESSAGE_DELIVERED": deliveries,
        "AGENT_STATE_SNAPSHOTTED": questions * 3,
        "AGGREGATION_COMPLETED": questions,
    })


def _canonical(value: Any) -> Any:
    volatile = {"timestamp", "created_at", "received_at", "started_at", "finished_at"}
    if isinstance(value, dict):
        return {key: _canonical(item) for key, item in sorted(value.items())
                if key not in volatile and not key.endswith("_path")}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    return value


def audit_run(run_dir: str | Path, replay_run_dir: str | Path) -> dict[str, Any]:
    run_dir, replay_run_dir = Path(run_dir), Path(replay_run_dir)
    manifest = RunManifest.model_validate(_read_json(run_dir / "manifest.json"))
    summary = RunSummary.model_validate(_read_json(run_dir / "summary.json"))
    traces = [TraceEvent.model_validate(value) for value in _read_jsonl(run_dir / "trace.jsonl")]
    bundles = [PlatformInputBundle.model_validate(value) for value in _read_json(run_dir / "input_snapshots.json")]
    assignments = [AssignmentSnapshot.model_validate(value) for value in _read_json(run_dir / "assignments.json")]
    nodes = [RuntimeMessageNode.model_validate(value) for value in _read_jsonl(run_dir / "message_nodes.jsonl")]
    dependencies = [DependencyRecord.model_validate(value) for value in _read_jsonl(run_dir / "dependency_records.jsonl")]
    messages = [MessageEnvelope.model_validate(value) for value in _read_json(run_dir / "messages.json")]
    states = [AgentStateSnapshot.model_validate(value) for value in _read_json(run_dir / "agent_states.json")]
    results = [AggregatedResult.model_validate(value) for value in _read_json(run_dir / "aggregated_results.json")]

    expected_counts = _expected_trace_counts(manifest)
    observed_counts = Counter(event.event_type.value for event in traces)
    expected_trace_total = sum(expected_counts.values())
    matched_trace_slots = sum(min(observed_counts[name], count) for name, count in expected_counts.items())
    expected_deliveries = expected_counts["MESSAGE_DELIVERED"]
    trace_exact = (observed_counts == expected_counts and summary.trace_events == len(traces)
                   and len({event.event_id for event in traces}) == len(traces)
                   and len(messages) == expected_deliveries
                   and len({message.message_id for message in messages}) == len(messages)
                   and len(nodes) == summary.model_calls == manifest.message_node_count
                   and len(dependencies) == manifest.dependency_record_count)

    graph_valid = True
    try:
        validate_reconstructability(nodes, dependencies, bundles, assignments)
    except EvaluationTraceValidationError:
        graph_valid = False

    message_id_counts = Counter(message.message_id for message in messages)
    message_by_id = {message.message_id: message for message in messages}
    node_by_id = {node.node_id: node for node in nodes}
    compatibility_total = compatibility_ok = 0
    for message in messages:
        compatibility_total += 1
        node = node_by_id.get(str(message.metadata.get("canonical_node_id", "")))
        if (
            node is not None
            and node.node_kind is RuntimeNodeKind.COMMUNICATION_OUTPUT
            and message.run_id == node.run_id
            and message.question_id == node.question_id
            and message.sender_id == node.sender_id
            and message.receiver_id == node.receiver_id
            and message.round == node.round
            and message.payload == node.payload
            and message.metadata.get("response_id") == node.response_id
        ):
            compatibility_ok += 1
    parent_message_total = parent_message_ok = 0
    illegal_same_round_events: set[str] = set()
    for message in messages:
        for parent_id in message.parent_message_ids:
            parent_message_total += 1
            parent = message_by_id.get(parent_id)
            if (parent is not None and message_id_counts[parent_id] == 1 and parent.question_id == message.question_id
                    and parent.receiver_id == message.sender_id and parent.round == message.round - 1):
                parent_message_ok += 1
            else:
                illegal_same_round_events.add(message.message_id)

    claim_by_id: dict[str, AtomicClaim] = {}
    claim_id_counts: Counter[str] = Counter()
    for bundle in bundles:
        for claim in bundle.seed_claims:
            claim_by_id[claim.claim_id] = claim
            claim_id_counts[claim.claim_id] += 1
    for message in messages:
        for claim in _claim_list(message):
            claim_by_id[claim.claim_id] = claim
            claim_id_counts[claim.claim_id] += 1
    parent_claim_total = parent_claim_ok = 0
    for message in messages:
        for claim in _claim_list(message):
            for parent_id in claim.parent_claim_ids:
                parent_claim_total += 1
                if parent_id in claim_by_id and claim_id_counts[parent_id] == 1:
                    parent_claim_ok += 1

    documents = {(document.sample_id, document.context_index): document
                 for bundle in bundles for document in bundle.documents}
    all_claims: list[AtomicClaim] = []
    for bundle in bundles:
        all_claims.extend(bundle.seed_claims)
    for message in messages:
        all_claims.extend(_claim_list(message))
    for state in states:
        all_claims.extend(state.private_initial_claims)
        all_claims.extend(state.current_structured_claims)
    locator_total = locator_ok = 0
    for ref in _source_refs(all_claims):
        locator_total += 1
        document = documents.get((ref.context_ref.sample_id, ref.context_ref.context_index))
        sentence_ids = set(ref.sentence_ids)
        available = set() if document is None else {sentence.sentence_index for sentence in document.sentences}
        if document is not None and (not sentence_ids or sentence_ids <= available):
            locator_ok += 1
    for result in results:
        for claim in result.claims:
            for ref in claim.source_refs:
                locator_total += 1
                document = documents.get((ref.context_ref.sample_id, ref.context_ref.context_index))
                available = set() if document is None else {sentence.sentence_index for sentence in document.sentences}
                if document is not None and (not ref.sentence_ids or set(ref.sentence_ids) <= available):
                    locator_ok += 1

    attempts = {}
    responses = {}
    for event in traces:
        if event.event_type.value == "MODEL_ATTEMPT_STARTED":
            request = event.event_data["request"]
            attempts[request["request_id"]] = request
            if request["stage"] == "communication":
                round_number = int(request["round"])
                if any(int(claim["communication_hop"]) >= round_number
                       for claim in request["request_context"].get("incoming_claims", [])):
                    illegal_same_round_events.add(event.event_id)
                if "local_documents" in request["request_context"]:
                    illegal_same_round_events.add(event.event_id)
        elif event.event_type.value == "MODEL_RESPONSE_RECEIVED":
            response = event.event_data
            responses[response["request_id"]] = response
    bundle_by_id = {bundle.question.question_id: bundle for bundle in bundles}
    assignment_by_id = {assignment.question_id: assignment for assignment in assignments}
    request_replay_total = request_replay_ok = 0
    for node in nodes:
        request_replay_total += 1
        request = attempts.get(node.request_id)
        if request is None:
            continue
        reconstructed = reconstruct_request_messages(
            node, nodes, dependencies, bundle_by_id[node.question_id], assignment_by_id[node.question_id]
        )
        if request["messages"] == [message.model_dump(mode="json") for message in reconstructed]:
            request_replay_ok += 1
    replay_total = replay_ok = source_replay_total = source_replay_ok = 0
    for request_id, request in attempts.items():
        response = responses.get(request_id)
        expected_claims = request["request_context"].get(
            "local_claims" if request["round"] == 0 else "incoming_claims", []
        )
        actual_claims = None if response is None else response["raw_response"].get("claims")
        actual_claims = [] if actual_claims is None else actual_claims
        replay_total += max(len(expected_claims), len(actual_claims))
        replay_ok += sum(expected == actual for expected, actual in zip(expected_claims, actual_claims))
        expected_refs = [ref for claim in expected_claims for ref in claim.get("source_refs", [])]
        actual_refs = [ref for claim in actual_claims for ref in claim.get("source_refs", [])]
        source_replay_total += max(len(expected_refs), len(actual_refs))
        source_replay_ok += sum(expected == actual for expected, actual in zip(expected_refs, actual_refs))

    artifact_names = ("manifest.json", "trace.jsonl", "input_snapshots.json", "assignments.json", "gate_b_report.json",
                      "message_nodes.jsonl", "dependency_records.jsonl",
                      "messages.json", "agent_states.json", "aggregated_results.json", "summary.json")
    replay_equal = 0
    replay_details = {}
    for name in artifact_names:
        left = _read_jsonl(run_dir / name) if name.endswith(".jsonl") else _read_json(run_dir / name)
        right = _read_jsonl(replay_run_dir / name) if name.endswith(".jsonl") else _read_json(replay_run_dir / name)
        equal = _canonical(left) == _canonical(right)
        replay_details[name] = equal
        replay_equal += int(equal)

    metrics = [
        Metric("Trace completeness", matched_trace_slots, expected_trace_total, "100%", trace_exact),
        Metric("Evaluation DAG validity", int(graph_valid), 1, "100%", graph_valid),
        Metric("Prompt reconstructability", request_replay_ok, request_replay_total, "100%",
               request_replay_ok == request_replay_total),
        Metric("Derived-message consistency", compatibility_ok, compatibility_total, "100%",
               compatibility_ok == compatibility_total),
        Metric("Parent-message resolvability", parent_message_ok, parent_message_total, "100%", parent_message_ok == parent_message_total),
        Metric("Parent-claim resolvability", parent_claim_ok, parent_claim_total, "100%", parent_claim_ok == parent_claim_total),
        Metric("Source-locator traceability", locator_ok, locator_total, "100%", locator_ok == locator_total),
        Metric("Mock exact claim replay rate", replay_ok, replay_total, "100%", replay_ok == replay_total),
        Metric("Mock exact source-reference replay rate", source_replay_ok, source_replay_total, "100%", source_replay_ok == source_replay_total),
        Metric("Identical-configuration replay consistency", replay_equal, len(artifact_names), "100%", replay_equal == len(artifact_names)),
        Metric("Illegal same-round message-visibility events", 0, len(illegal_same_round_events), "0", not illegal_same_round_events),
    ]
    return {
        "run_dir": str(run_dir), "replay_run_dir": str(replay_run_dir),
        "status": "passed" if all(metric.passed for metric in metrics) else "failed",
        "metrics": [{**asdict(metric), "rate": metric.rate} for metric in metrics],
        "trace_expected_counts": dict(expected_counts), "trace_observed_counts": dict(observed_counts),
        "replay_artifact_equality": replay_details,
        "illegal_same_round_event_ids": sorted(illegal_same_round_events),
    }


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in _all_keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in _all_keys(item)}
    return set()


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * percentile + 0.999999)))
    return ordered[index]


def audit_single_run(run_dir: str | Path) -> dict[str, Any]:
    """Audit one paid/reliable run without constructing a Provider or calling a model."""
    run_dir = Path(run_dir).resolve()
    manifest = RunManifest.model_validate(_read_json(run_dir / "manifest.json"))
    summary = RunSummary.model_validate(_read_json(run_dir / "summary.json"))
    state = RunState.model_validate(_read_json(run_dir / "run_state.json"))
    traces = [TraceEvent.model_validate(value) for value in _read_jsonl(run_dir / "trace.jsonl")]
    bundles = [PlatformInputBundle.model_validate(value) for value in _read_json(run_dir / "input_snapshots.json")]
    assignments = [AssignmentSnapshot.model_validate(value) for value in _read_json(run_dir / "assignments.json")]
    nodes = [RuntimeMessageNode.model_validate(value) for value in _read_jsonl(run_dir / "message_nodes.jsonl")]
    dependencies = [DependencyRecord.model_validate(value) for value in _read_jsonl(run_dir / "dependency_records.jsonl")]
    messages = [MessageEnvelope.model_validate(value) for value in _read_json(run_dir / "messages.json")]
    states = [AgentStateSnapshot.model_validate(value) for value in _read_json(run_dir / "agent_states.json")]
    results = [AggregatedResult.model_validate(value) for value in _read_json(run_dir / "aggregated_results.json")]
    failures: list[str] = []
    if not (manifest.run_id == summary.run_id == state.run_id):
        failures.append("RUN_ID_MISMATCH")
    if not (manifest.status == summary.status == state.status):
        failures.append("RUN_STATUS_MISMATCH")
    if tuple(manifest.selected_sample_ids) != state.selected_sample_ids:
        failures.append("SELECTED_SAMPLE_MISMATCH")
    if len({event.event_id for event in traces}) != len(traces):
        failures.append("TRACE_EVENT_ID_DUPLICATE")
    expected_event_ids = [f"evt_{index:06d}" for index in range(1, len(traces) + 1)]
    if [event.event_id for event in traces] != expected_event_ids:
        failures.append("TRACE_EVENT_SEQUENCE_INVALID")
    checkpoints = []
    for question_id, entry in state.questions.items():
        if entry.status in {QuestionRunStatus.COMPLETED, QuestionRunStatus.FAILED}:
            if entry.checkpoint_path is None or not (run_dir / entry.checkpoint_path).is_file():
                failures.append(f"CHECKPOINT_MISSING:{question_id}")
                continue
            try:
                checkpoint = QuestionCheckpoint.model_validate(_read_json(run_dir / entry.checkpoint_path))
            except Exception:
                failures.append(f"CHECKPOINT_INVALID:{question_id}")
                continue
            if checkpoint.question_id != question_id or checkpoint.status is not entry.status:
                failures.append(f"CHECKPOINT_IDENTITY_MISMATCH:{question_id}")
            checkpoints.append(checkpoint)
    completed_ids = {qid for qid, entry in state.questions.items()
                     if entry.status is QuestionRunStatus.COMPLETED}
    canonical_ids = {node.question_id for node in nodes} | {dep.question_id for dep in dependencies} | \
        {message.question_id for message in messages} | {item.question_id for item in states} | \
        {result.question_id for result in results}
    if not canonical_ids <= completed_ids:
        failures.append("FAILED_QUESTION_POLLUTED_CANONICAL_ARTIFACTS")
    try:
        validate_reconstructability(nodes, dependencies, bundles, assignments, state.prompt_version)
    except EvaluationTraceValidationError:
        failures.append("EVALUATION_DAG_INVALID")
    if manifest.message_node_count != len(nodes) or summary.message_nodes != len(nodes):
        failures.append("MESSAGE_NODE_COUNT_MISMATCH")
    if manifest.dependency_record_count != len(dependencies) or summary.dependency_records != len(dependencies):
        failures.append("DEPENDENCY_COUNT_MISMATCH")
    if not (manifest.total_model_attempts == summary.total_model_attempts == state.total_model_attempts
            == summary.model_calls):
        failures.append("ATTEMPT_COUNT_MISMATCH")
    if not (manifest.logical_model_requests == summary.logical_model_requests == state.logical_model_requests):
        failures.append("LOGICAL_REQUEST_COUNT_MISMATCH")
    if not (manifest.retry_count == summary.retry_count == state.retry_count):
        failures.append("RETRY_COUNT_MISMATCH")
    starts = [event for event in traces if event.event_type.value == "MODEL_ATTEMPT_STARTED"]
    successes = [event for event in traces if event.event_type.value == "MODEL_RESPONSE_RECEIVED"]
    failed_attempts = [event for event in traces if event.event_type.value == "MODEL_ATTEMPT_FAILED"]
    if len(starts) != state.total_model_attempts or len(successes) + len(failed_attempts) != len(starts):
        failures.append("ATTEMPT_TRACE_INCOMPLETE")
    successful_request_ids = {str(event.event_data.get("logical_request_id")) for event in successes}
    if any(node.request_id not in successful_request_ids for node in nodes):
        failures.append("NODE_WITHOUT_SUCCESSFUL_RESPONSE")
    requests = {}
    for event in starts:
        request = event.event_data.get("request")
        if isinstance(request, dict):
            requests.setdefault(str(request.get("request_id")), request)
    bundle_by_id = {bundle.question.question_id: bundle for bundle in bundles}
    assignment_by_id = {assignment.question_id: assignment for assignment in assignments}
    for node in nodes:
        request = requests.get(node.request_id)
        if request is None:
            failures.append("NODE_REQUEST_MISSING")
            break
        reconstructed = reconstruct_request_messages(
            node, nodes, dependencies, bundle_by_id[node.question_id], assignment_by_id[node.question_id],
            state.prompt_version)
        if request.get("messages") != [message.model_dump(mode="json") for message in reconstructed]:
            failures.append("PROMPT_RECONSTRUCTION_MISMATCH")
            break
    forbidden = {
        "answer", "answer_aliases", "gold_answer", "gold_answers", "truth_view",
        "evaluation_truth_view", "canonical_source_sets", "authorization", "api_key",
    }
    visible_names = ("input_snapshots.json", "assignments.json", "messages.json", "agent_states.json",
                     "aggregated_results.json", "message_nodes.jsonl", "dependency_records.jsonl", "trace.jsonl")
    leaks = []
    for name in visible_names:
        value = _read_jsonl(run_dir / name) if name.endswith(".jsonl") else _read_json(run_dir / name)
        if {key.casefold() for key in _all_keys(value)} & forbidden:
            leaks.append(name)
    if leaks:
        failures.append("AGENT_VISIBLE_FIELD_LEAK")
    credential_pattern = re.compile(r"sk-[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9._-]{16,}", re.IGNORECASE)
    credential_files = []
    for path in run_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".json", ".jsonl", ".txt", ".log"}:
            if credential_pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
                credential_files.append(str(path.relative_to(run_dir)))
    if credential_files:
        failures.append("CREDENTIAL_PATTERN_DETECTED")
    provider = manifest.providers[0] if manifest.providers else None
    if provider is None or not provider.generation or provider.request_model is None:
        failures.append("PROVIDER_SNAPSHOT_INCOMPLETE")
    elif provider.provider_kind == "deepseek_openai_compatible" and provider.generation.get("thinking") is None:
        failures.append("THINKING_SNAPSHOT_MISSING")
    elif provider.provider_kind == "vllm_openai_compatible":
        thinking = provider.generation.get("thinking") or {}
        if thinking.get("type") != "disabled":
            failures.append("THINKING_SNAPSHOT_NOT_DISABLED")
        if not re.fullmatch(r"[0-9a-f]{40}", provider.model_revision or ""):
            failures.append("MODEL_REVISION_SNAPSHOT_INVALID")
        if provider.model_repository != "Qwen/Qwen3-8B":
            failures.append("MODEL_REPOSITORY_SNAPSHOT_INVALID")
        if not re.fullmatch(r"[0-9a-f]{64}", provider.deployment_manifest_sha256 or ""):
            failures.append("DEPLOYMENT_MANIFEST_SNAPSHOT_INVALID")
        if not provider.deployment:
            failures.append("DEPLOYMENT_SNAPSHOT_MISSING")
    truth_views = ()
    if manifest.status is RunStatus.COMPLETED:
        try:
            truth_views = TruthViewLoader.load_for_run(run_dir)
        except Exception:
            failures.append("TRUTH_VIEW_LOAD_FAILED")
    usage = Counter()
    latencies = []
    finish_reasons = Counter()
    parse_success = 0
    response_models = Counter()
    for event in successes:
        data = event.event_data
        token_usage = data.get("usage") or {}
        usage["input_tokens"] += int(token_usage.get("input_tokens") or 0)
        usage["output_tokens"] += int(token_usage.get("output_tokens") or 0)
        usage["total_tokens"] += int(token_usage.get("total_tokens") or 0)
        if data.get("latency_ms") is not None:
            latencies.append(float(data["latency_ms"]))
        finish_reasons[str(data.get("finish_reason"))] += 1
        parse_success += int(data.get("parse_status") == "succeeded")
        response_models[str(data.get("response_model") or data.get("model"))] += 1
    error_codes = Counter(str(event.event_data.get("provider_error_code")) for event in failed_attempts)
    structural_status = "passed" if not failures else "failed"
    completed_count = sum(entry.status is QuestionRunStatus.COMPLETED for entry in state.questions.values())
    failed_count = sum(entry.status is QuestionRunStatus.FAILED for entry in state.questions.values())
    pilot_completed = (structural_status == "passed" and manifest.status is RunStatus.COMPLETED
                       and completed_count == len(state.questions) and failed_count == 0)
    return {
        "run_dir": str(run_dir),
        # `status` remains the historical structural-audit result for CLI callers.
        "status": structural_status,
        "structural_audit_status": structural_status,
        "run_outcome": manifest.status.value,
        "pilot_completed": pilot_completed,
        "failures": failures,
        "questions": {"total": len(state.questions),
                      "completed": completed_count,
                      "failed": failed_count},
        "logical_requests": state.logical_model_requests,
        "total_attempts": state.total_model_attempts,
        "retry_count": state.retry_count,
        "provider_error_codes": dict(error_codes),
        "parse_success_rate": None if not successes else parse_success / len(successes),
        "tokens": dict(usage),
        "latency_ms": {"p50": _percentile(latencies, .50), "p95": _percentile(latencies, .95),
                       "p99": _percentile(latencies, .99)},
        "finish_reasons": dict(finish_reasons),
        "response_models": dict(response_models),
        "artifacts": {"nodes": len(nodes), "dependencies": len(dependencies), "messages": len(messages)},
        "truth_views_loaded": len(truth_views),
        "agent_visible_leak_files": leaks,
        "credential_pattern_files": credential_files,
        "formal_metrics_computed": False,
        "final_answer_generated": False,
    }
