"""Provider-neutral M1-F retry, checkpoint, resume, and single-run planning."""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import time
from collections import Counter
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from agent_lab.adapters.datasets.data_truth_v3 import file_sha256
from agent_lab.domain.contracts_v0_1 import (
    AgentStateSnapshot, AggregatedClaim, AggregatedResult, AssignmentSnapshot,
    AtomicClaim, DependencyKind, DependencyRecord, ExperimentConfig, FreeTextPayload,
    FreeTextRecord, InputArtifactRef, MessageEnvelope, MessageFormat, ModelRequest,
    PlatformInputBundle, PromptSnapshot, ProviderMessage, ProviderSnapshot, QuestionCheckpoint,
    QuestionRunStatus, QuestionStateEntry, RunManifest, RunState, RunStatus, RunSummary,
    RuntimeMessageNode, RuntimeNodeKind, Stage, StructuredPayload, TraceEventType,
)
from agent_lab.evaluation_trace import (
    canonical_messages_sha256, communication_visible_input, initial_messages,
    validate_reconstructability,
)
from agent_lab.prompts import PROMPT_ID, PROMPT_VERSION, content_hash
from agent_lab.providers import ModelProvider, ProviderError, ProviderErrorCode, create_provider
from agent_lab.topology import directed_edges


class ReliabilityErrorCode(StrEnum):
    CONFIG = "EXECUTION_CONFIG_ERROR"
    BUDGET_EXHAUSTED = "MODEL_ATTEMPT_BUDGET_EXHAUSTED"
    RESUME_MISMATCH = "RESUME_IDENTITY_MISMATCH"
    CHECKPOINT_INVALID = "QUESTION_CHECKPOINT_INVALID"


class ReliabilityError(RuntimeError):
    def __init__(self, code: ReliabilityErrorCode, detail: str):
        self.code, self.detail = code, detail
        super().__init__(f"{code.value}: {detail}")


def expected_logical_model_calls(config: ExperimentConfig) -> int:
    if config.m3_condition is not None:
        from agent_lab.m3_execution import expected_calls_per_question
        return len(config.dataset.sample_ids) * expected_calls_per_question(config)
    per_question = 3 + len(directed_edges(config.topology.kind, config.topology.center_agent_id)) * \
        config.protocol.communication_rounds
    return len(config.dataset.sample_ids) * per_question


def plan_experiment(config: ExperimentConfig) -> dict[str, Any]:
    if config.execution is None:
        raise ReliabilityError(ReliabilityErrorCode.CONFIG, "plan-run requires execution configuration")
    logical = expected_logical_model_calls(config)
    per_question = logical // len(config.dataset.sample_ids)
    result = {
        "selected_questions": list(config.dataset.sample_ids),
        "selected_question_count": len(config.dataset.sample_ids),
        "dataset_adapter": config.dataset.adapter,
        "topology": config.topology.kind,
        "communication_rounds": config.protocol.communication_rounds,
        "expected_calls_per_question": per_question,
        "expected_logical_model_calls": logical,
        "maximum_allowed_attempts": config.execution.max_total_model_attempts,
        "model": getattr(config.provider, "model", None) or getattr(config.provider, "version"),
        "thinking": None if config.generation.thinking is None else config.generation.thinking.type,
        "max_output_tokens": config.generation.max_output_tokens,
        "within_budget": logical <= config.execution.max_total_model_attempts,
    }
    if config.m3_condition is not None:
        result["run_identity"] = config.m3_condition.model_dump(mode="json")
        result["real_provider_execution_authorized"] = False
    return result


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if hasattr(value, "model_dump_json"):
        material = value.model_dump_json(indent=2)
    else:
        material = json.dumps(value, ensure_ascii=False, indent=2)
    temporary.write_text(material, encoding="utf-8")
    _replace_with_retries(temporary, path)


def _atomic_jsonl(path: Path, values) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        for value in values:
            if hasattr(value, "model_dump_json"):
                stream.write(value.model_dump_json() + "\n")
            else:
                stream.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
    _replace_with_retries(temporary, path)


def _replace_with_retries(temporary: Path, path: Path, *, attempts: int = 5,
                          initial_delay_seconds: float = 0.1) -> None:
    """Bound transient Windows file-lock failures without changing experiment requests."""
    for attempt in range(attempts):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt + 1 >= attempts:
                raise
            time.sleep(initial_delay_seconds * (2 ** attempt))


def _canonical_hash(value: Any) -> str:
    material = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(material.encode("utf-8")).hexdigest()


def _config_hash(config_path: Path, config: ExperimentConfig) -> str:
    return file_sha256(config_path) if config.m3_condition is None else \
        _canonical_hash(config.model_dump(mode="json"))


def _identity(config_path: Path, config: ExperimentConfig, adapter, bundles, code_hash: str) -> tuple[str, dict]:
    if config.m3_condition is not None:
        from agent_lab.m3_prompts import resolve_prompt_set
        prompt = resolve_prompt_set(config)
        prompt_identity = {"ref": prompt.prompt_ref, "version": prompt.registry_version,
                           "hash": prompt.prompt_set_hash, "registry_sha256": prompt.registry_sha256}
    else:
        prompt_identity = {"id": PROMPT_ID, "version": PROMPT_VERSION, "hash": content_hash()}
    value = {
        "config_sha256": _config_hash(config_path, config),
        "code_tree_sha256": code_hash,
        "dataset_sha256": adapter.data_sha256,
        "schema_sha256": file_sha256(Path(config.dataset.schema_path)),
        "repair_manifest_sha256": adapter.repair_manifest_sha256,
        "selected_sample_ids": [bundle.question.question_id for bundle in bundles],
        "prompt": prompt_identity,
        "m3_condition": None if config.m3_condition is None else config.m3_condition.model_dump(mode="json"),
        "provider": config.provider.model_dump(mode="json"),
        "generation": config.generation.model_dump(mode="json"),
        "topology": config.topology.model_dump(mode="json"),
        "protocol": config.protocol.model_dump(mode="json"),
        "policy": config.document_assignment.model_dump(mode="json"),
        "execution": config.execution.model_dump(mode="json"),
    }
    return _canonical_hash(value), value


def _checkpoint_name(question_id: str) -> str:
    return "question_" + sha256(question_id.encode("utf-8")).hexdigest()[:20] + ".json"


def _m3_identity_segment(label: str, value: str) -> str:
    return f"{label}-{sha256(value.encode('utf-8')).hexdigest()[:12]}"


def _m3_run_dir(run_root: Path, condition, run_id: str) -> Path:
    return (run_root / f"condition-{condition.condition_id}" /
            _m3_identity_segment("model", condition.model_id) /
            _m3_identity_segment("dataset", condition.dataset_id) /
            _m3_identity_segment("replicate", condition.replicate_id) / run_id)


class AttemptExecutor:
    def __init__(self, provider: ModelProvider, config: ExperimentConfig, trace, state: RunState,
                 persist_state: Callable[[RunState], None], sleeper: Callable[[float], None]):
        self.provider, self.config, self.trace = provider, config, trace
        self.state, self.persist_state, self.sleeper = state, persist_state, sleeper

    def _update_counts(self, question_id: str, *, retry: bool = False) -> None:
        questions = dict(self.state.questions)
        entry = questions[question_id]
        questions[question_id] = entry.model_copy(update={"attempt_count": entry.attempt_count + 1})
        self.state = self.state.model_copy(update={
            "questions": questions,
            "total_model_attempts": self.state.total_model_attempts + 1,
            "retry_count": self.state.retry_count + int(retry),
            "updated_at": _utcnow(),
        })
        self.persist_state(self.state)

    def complete(self, request: ModelRequest):
        execution = self.config.execution
        assert execution is not None
        body_hash = self.provider.request_body_sha256(request)
        for attempt_number in range(1, execution.max_attempts_per_request + 1):
            if self.state.total_model_attempts >= execution.max_total_model_attempts:
                self.trace.emit(TraceEventType.MODEL_ATTEMPT_BUDGET_EXHAUSTED,
                    question_id=request.question_id, stage=request.stage, round=request.round,
                    agent_id=request.agent_id, attempt=attempt_number,
                    event_data={"request_id": request.request_id, "request_body_sha256": body_hash,
                                "total_model_attempts": self.state.total_model_attempts})
                raise ReliabilityError(ReliabilityErrorCode.BUDGET_EXHAUSTED,
                                       "maximum total model attempts reached")
            self._update_counts(request.question_id, retry=attempt_number > 1)
            started_at = _utcnow(); started = perf_counter()
            self.trace.emit(TraceEventType.MODEL_ATTEMPT_STARTED,
                question_id=request.question_id, stage=request.stage, round=request.round,
                agent_id=request.agent_id, attempt=attempt_number,
                event_data={"request": request.model_dump(mode="json"),
                            "logical_request_id": request.request_id,
                            "provider_kind": self.config.provider.kind,
                            "request_model": request.model,
                            "request_body_sha256": body_hash,
                            "started_at": started_at.isoformat(),
                            "total_model_attempts": self.state.total_model_attempts})
            try:
                response = self.provider.complete(request)
            except ProviderError as error:
                latency_ms = (perf_counter() - started) * 1000
                retryable = error.code.value in execution.retry.retryable_error_codes
                will_retry = retryable and attempt_number < execution.max_attempts_per_request and \
                    self.state.total_model_attempts < execution.max_total_model_attempts
                backoff = 0.0
                if will_retry:
                    backoff = execution.retry.initial_backoff_seconds * (2 ** (attempt_number - 1))
                    if execution.retry.honor_retry_after and error.retry_after_seconds is not None:
                        backoff = error.retry_after_seconds
                    backoff = min(backoff, execution.retry.max_backoff_seconds)
                self.trace.emit(TraceEventType.MODEL_ATTEMPT_FAILED,
                    question_id=request.question_id, stage=request.stage, round=request.round,
                    agent_id=request.agent_id, attempt=attempt_number,
                    event_data={"logical_request_id": request.request_id,
                                "request_body_sha256": body_hash,
                                "ended_at": _utcnow().isoformat(), "latency_ms": latency_ms,
                                "provider_error_code": error.code.value,
                                "http_status": error.status_code, "retryable": retryable,
                                "will_retry": will_retry, "backoff_seconds": backoff,
                                "contract_diagnostic": None if error.contract_diagnostic is None else
                                    error.contract_diagnostic.model_copy(update={"attempt": attempt_number})
                                    .model_dump(mode="json"),
                                "total_model_attempts": self.state.total_model_attempts})
                if not will_retry:
                    raise
                self.sleeper(backoff)
                if self.provider.request_body_sha256(request) != body_hash:
                    raise ReliabilityError(ReliabilityErrorCode.CONFIG, "retry changed request body")
                continue
            self.trace.emit(TraceEventType.MODEL_RESPONSE_RECEIVED,
                question_id=request.question_id, stage=request.stage, round=request.round,
                agent_id=request.agent_id, attempt=attempt_number,
                event_data={**response.model_dump(mode="json"),
                            "logical_request_id": request.request_id,
                            "request_body_sha256": body_hash,
                            "attempt_number": attempt_number,
                            "total_model_attempts": self.state.total_model_attempts})
            return response
        raise AssertionError("attempt loop exhausted")


def _utcnow() -> datetime:
    from agent_lab.runtime import utcnow
    return utcnow()


def _question_artifacts(bundle: PlatformInputBundle, assignment: AssignmentSnapshot, config: ExperimentConfig,
                        provider: ModelProvider, request_model: str, run_id: str, trace,
                        attempts: AttemptExecutor) -> QuestionCheckpoint:
    if config.m3_condition is not None:
        from agent_lab.m3_execution import build_question_artifacts
        from agent_lab.m3_prompts import resolve_prompt_set
        return build_question_artifacts(bundle, assignment, config, provider, request_model, run_id,
                                        trace, attempts, resolve_prompt_set(config))
    from agent_lab.runtime import (
        _available_claims, _canonical_payload, _claims_from_node, _dedupe_claims, _dedupe_refs,
        _message_from_node, stable_id,
    )
    qid = bundle.question.question_id
    nodes: list[RuntimeMessageNode] = []
    dependencies: list[DependencyRecord] = []
    messages: list[MessageEnvelope] = []
    machine_claims: dict[str, tuple[AtomicClaim, ...]] = {}
    initial_nodes: dict[str, RuntimeMessageNode] = {}
    trace.emit(TraceEventType.QUESTION_STARTED, question_id=qid)
    trace.emit(TraceEventType.DOCUMENT_ASSIGNMENT_FROZEN, question_id=qid,
               event_data=assignment.model_dump(mode="json"))
    trace.emit(TraceEventType.INITIAL_READ_STARTED, question_id=qid, stage=Stage.INITIAL_READ, round=0)
    for spec in config.agents:
        indexes = {ref.context_index for ref in assignment.assignments[spec.agent_id]}
        local = _available_claims(bundle, indexes)
        local_documents = tuple(document for document in bundle.documents if document.context_index in indexes)
        visible_refs = tuple(assignment.assignments[spec.agent_id])
        request_messages = initial_messages(bundle, visible_refs)
        request = ModelRequest(
            request_id=stable_id("req", run_id, qid, spec.agent_id, 0), provider_ref=provider.provider_ref,
            model=request_model, messages=request_messages, output_format=config.protocol.message_format,
            output_schema_version="0.1", prompt_id=PROMPT_ID, prompt_version=PROMPT_VERSION,
            prompt_content_hash=content_hash(), run_id=run_id, question_id=qid, agent_id=spec.agent_id,
            stage=Stage.INITIAL_READ, round=0, receiver_id=spec.agent_id,
            replicate_id=config.randomness.replicate_id,
            request_context={"local_documents": [d.model_dump(mode="json") for d in local_documents],
                             "local_claims": [c.model_dump(mode="json") for c in local],
                             "mock_oracle_usage": "accessible-evidence replay only"},
        )
        response = attempts.complete(request)
        node_id = stable_id("node", request.request_id)
        payload, canonical_claims = _canonical_payload(response, config.protocol.message_format, node_id, 0)
        node = RuntimeMessageNode(node_id=node_id, node_kind=RuntimeNodeKind.INITIAL_OUTPUT,
            run_id=run_id, question_id=qid, sender_id=spec.agent_id, receiver_id=spec.agent_id,
            stage=Stage.INITIAL_READ, round=0, communication_hop=0, visible_document_refs=visible_refs,
            payload=payload, request_id=request.request_id, response_id=response.response_id,
            prompt_ref=f"{PROMPT_ID}:{PROMPT_VERSION}", model_ref=provider.provider_ref,
            visible_input_sha256=canonical_messages_sha256(request_messages), created_at=_utcnow())
        nodes.append(node); initial_nodes[spec.agent_id] = node; machine_claims[node.node_id] = canonical_claims
        trace.emit(TraceEventType.MESSAGE_NODE_CREATED, question_id=qid, stage=Stage.INITIAL_READ, round=0,
                   agent_id=spec.agent_id,
                   event_data={"node_id": node.node_id, "request_id": node.request_id,
                               "response_id": node.response_id})
    trace.emit(TraceEventType.INITIAL_READ_FINISHED, question_id=qid, stage=Stage.INITIAL_READ, round=0)
    for round_number in range(1, config.protocol.communication_rounds + 1):
        trace.emit(TraceEventType.ROUND_STARTED, question_id=qid, stage=Stage.COMMUNICATION, round=round_number)
        for sender, receiver in directed_edges(config.topology.kind, config.topology.center_agent_id):
            request_id = stable_id("req", run_id, qid, round_number, sender, receiver)
            node_id = stable_id("node", request_id)
            parent_nodes = (initial_nodes[sender],) + tuple(
                node for node in nodes if node.node_kind is RuntimeNodeKind.COMMUNICATION_OUTPUT
                and node.round == round_number - 1 and node.receiver_id == sender)
            child_dependencies = tuple(DependencyRecord(
                dependency_id=stable_id("dep", parent.node_id, node_id,
                    DependencyKind.SELF_INITIAL.value if parent.node_kind is RuntimeNodeKind.INITIAL_OUTPUT
                    else DependencyKind.RECEIVED_MESSAGE.value), run_id=run_id, question_id=qid,
                parent_node_id=parent.node_id, child_node_id=node_id,
                dependency_kind=DependencyKind.SELF_INITIAL if parent.node_kind is RuntimeNodeKind.INITIAL_OUTPUT
                else DependencyKind.RECEIVED_MESSAGE, parent_round=parent.round, child_round=round_number,
                visible_claim_ids=tuple(claim.claim_id for claim in parent.payload.claims)
                if isinstance(parent.payload, StructuredPayload) else ()) for parent in parent_nodes)
            request_messages, visible_claims, visible_parent_ids = communication_visible_input(
                bundle, node_id, nodes, child_dependencies)
            request = ModelRequest(request_id=request_id, provider_ref=provider.provider_ref, model=request_model,
                messages=request_messages, output_format=config.protocol.message_format,
                output_schema_version="0.1", prompt_id=PROMPT_ID, prompt_version=PROMPT_VERSION,
                prompt_content_hash=content_hash(), run_id=run_id, question_id=qid, agent_id=sender,
                stage=Stage.COMMUNICATION, round=round_number, receiver_id=receiver,
                replicate_id=config.randomness.replicate_id,
                request_context={"incoming_claims": [c.model_dump(mode="json") for c in visible_claims],
                                 "incoming_texts": [p.payload.text for p in parent_nodes
                                                    if isinstance(p.payload, FreeTextPayload)],
                                 "visible_parent_node_ids": list(visible_parent_ids),
                                 "raw_documents_supplied": False})
            response = attempts.complete(request)
            payload, canonical_claims = _canonical_payload(response, config.protocol.message_format,
                                                            node_id, round_number)
            node = RuntimeMessageNode(node_id=node_id, node_kind=RuntimeNodeKind.COMMUNICATION_OUTPUT,
                run_id=run_id, question_id=qid, sender_id=sender, receiver_id=receiver,
                stage=Stage.COMMUNICATION, round=round_number, communication_hop=round_number,
                visible_document_refs=(), payload=payload, request_id=request.request_id,
                response_id=response.response_id, prompt_ref=f"{PROMPT_ID}:{PROMPT_VERSION}",
                model_ref=provider.provider_ref, visible_input_sha256=canonical_messages_sha256(request_messages),
                created_at=_utcnow())
            nodes.append(node); machine_claims[node.node_id] = canonical_claims
            dependencies.extend(child_dependencies)
            message = _message_from_node(node, parent_nodes, canonical_claims); messages.append(message)
            trace.emit(TraceEventType.MESSAGE_NODE_CREATED, question_id=qid, stage=Stage.COMMUNICATION,
                       round=round_number, agent_id=sender, message_id=message.message_id,
                       event_data={"node_id": node.node_id, "request_id": node.request_id,
                                   "response_id": node.response_id})
            for dependency in child_dependencies:
                trace.emit(TraceEventType.DEPENDENCY_RECORDED, question_id=qid, stage=Stage.COMMUNICATION,
                           round=round_number, agent_id=sender, message_id=message.message_id,
                           event_data=dependency.model_dump(mode="json"))
            trace.emit(TraceEventType.MESSAGE_PARSED, question_id=qid, stage=Stage.COMMUNICATION,
                       round=round_number, agent_id=sender, message_id=message.message_id,
                       event_data={"parse_status": response.parse_status.value})
            trace.emit(TraceEventType.MESSAGE_DELIVERED, question_id=qid, stage=Stage.COMMUNICATION,
                       round=round_number, agent_id=receiver, message_id=message.message_id)
        trace.emit(TraceEventType.ROUND_FINISHED, question_id=qid, stage=Stage.COMMUNICATION, round=round_number)
    states = []
    for spec in config.agents:
        received_nodes = tuple(node for node in nodes if node.node_kind is RuntimeNodeKind.COMMUNICATION_OUTPUT
                               and node.receiver_id == spec.agent_id)
        state_claims = _dedupe_claims([
            *_claims_from_node(initial_nodes[spec.agent_id], machine_claims),
            *(claim for node in received_nodes for claim in _claims_from_node(node, machine_claims)),
        ])
        records = () if config.protocol.message_format is MessageFormat.STRUCTURED else tuple(
            FreeTextRecord(text=claim.claim_text, source_refs=claim.source_refs) for claim in state_claims)
        state = AgentStateSnapshot(run_id=run_id, question_id=qid, agent_id=spec.agent_id,
            round=config.protocol.communication_rounds, message_format=config.protocol.message_format,
            private_initial_claims=_claims_from_node(initial_nodes[spec.agent_id], machine_claims),
            received_message_ids=tuple(stable_id("msg", node.node_id) for node in received_nodes),
            current_structured_claims=state_claims if config.protocol.message_format is MessageFormat.STRUCTURED else (),
            current_free_text_records=records, created_at=_utcnow())
        states.append(state)
        trace.emit(TraceEventType.AGENT_STATE_SNAPSHOTTED, question_id=qid, agent_id=spec.agent_id,
                   round=config.protocol.communication_rounds, event_data={"claim_count": len(state_claims)})
    grouped: dict[str, list[tuple[str, AtomicClaim]]] = {}
    for state in states:
        for claim in state.current_structured_claims:
            grouped.setdefault(" ".join(claim.claim_text.casefold().split()), []).append((state.agent_id, claim))
    aggregated = tuple(AggregatedClaim(normalized_text=key, claim_text=items[0][1].claim_text,
        source_refs=_dedupe_refs([ref for _, claim in items for ref in claim.source_refs]),
        contributing_claim_ids=tuple(sorted({claim.claim_id for _, claim in items})),
        contributing_agent_ids=tuple(sorted({agent for agent, _ in items})))
        for key, items in sorted(grouped.items()))
    result = AggregatedResult(run_id=run_id, question_id=qid, message_format=config.protocol.message_format,
        claims=aggregated, aggregator_version=config.aggregation.version, created_at=_utcnow())
    trace.emit(TraceEventType.AGGREGATION_COMPLETED, question_id=qid, stage=Stage.AGGREGATION,
               event_data={"candidate_claim_count": len(aggregated), "final_answer_generated": False})
    trace.emit(TraceEventType.QUESTION_FINISHED, question_id=qid)
    return QuestionCheckpoint(run_id=run_id, question_id=qid, status=QuestionRunStatus.COMPLETED,
        attempt_count=attempts.state.questions[qid].attempt_count, assignment=assignment,
        nodes=tuple(nodes), dependencies=tuple(dependencies), messages=tuple(messages),
        agent_states=tuple(states), aggregated_result=result, created_at=_utcnow())


def _load_checkpoints(run_dir: Path, state: RunState) -> list[QuestionCheckpoint]:
    checkpoints = []
    for question_id in state.selected_sample_ids:
        entry = state.questions[question_id]
        if entry.status is not QuestionRunStatus.COMPLETED:
            continue
        if entry.checkpoint_path is None:
            raise ReliabilityError(ReliabilityErrorCode.CHECKPOINT_INVALID, "completed question lacks checkpoint")
        path = run_dir / entry.checkpoint_path
        if not path.is_file():
            raise ReliabilityError(ReliabilityErrorCode.CHECKPOINT_INVALID, "question checkpoint is missing")
        checkpoint = QuestionCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))
        if checkpoint.question_id != question_id or checkpoint.run_id != state.run_id:
            raise ReliabilityError(ReliabilityErrorCode.CHECKPOINT_INVALID, "question checkpoint identity mismatch")
        checkpoints.append(checkpoint)
    return checkpoints


def _rebuild_roots(run_dir: Path, state: RunState, bundles, assignments) -> None:
    checkpoints = _load_checkpoints(run_dir, state)
    nodes = tuple(node for checkpoint in checkpoints for node in checkpoint.nodes)
    dependencies = tuple(dep for checkpoint in checkpoints for dep in checkpoint.dependencies)
    messages = tuple(message for checkpoint in checkpoints for message in checkpoint.messages)
    states = tuple(item for checkpoint in checkpoints for item in checkpoint.agent_states)
    results = tuple(checkpoint.aggregated_result for checkpoint in checkpoints if checkpoint.aggregated_result)
    reconstructions = tuple(item for checkpoint in checkpoints for item in checkpoint.request_reconstructions)
    projections = tuple(item for checkpoint in checkpoints for item in checkpoint.parent_projections)
    terminal_observations = tuple(item for checkpoint in checkpoints for item in checkpoint.terminal_observations)
    if (run_dir / "prompt_snapshot.json").is_file():
        from agent_lab.evaluation_trace import validate_evaluation_trace
        validate_evaluation_trace(nodes, dependencies)
        snapshot = json.loads((run_dir / "prompt_snapshot.json").read_text(encoding="utf-8"))
        by_node = {item["node_id"]: item for item in reconstructions}
        if set(by_node) != {node.node_id for node in nodes}:
            raise ReliabilityError(ReliabilityErrorCode.CHECKPOINT_INVALID,
                                   "request reconstruction does not cover all M3 nodes")
        for node in nodes:
            record = by_node[node.node_id]
            if (record["messages_sha256"] != node.visible_input_sha256 or
                    record["prompt_set_hash"] != snapshot["prompt_set_hash"] or
                    canonical_messages_sha256(tuple(ProviderMessage.model_validate(item)
                                                    for item in record["messages"])) != node.visible_input_sha256):
                raise ReliabilityError(ReliabilityErrorCode.CHECKPOINT_INVALID,
                                       f"M3 request reconstruction mismatch for {node.node_id}")
    else:
        validate_reconstructability(nodes, dependencies, bundles, assignments)
    _atomic_jsonl(run_dir / "message_nodes.jsonl", nodes)
    _atomic_jsonl(run_dir / "dependency_records.jsonl", dependencies)
    _atomic_json(run_dir / "messages.json", [value.model_dump(mode="json") for value in messages])
    _atomic_json(run_dir / "agent_states.json", [value.model_dump(mode="json") for value in states])
    _atomic_json(run_dir / "aggregated_results.json", [value.model_dump(mode="json") for value in results])
    if reconstructions or (run_dir / "prompt_snapshot.json").is_file():
        _atomic_jsonl(run_dir / "request_reconstruction.jsonl", reconstructions)
        _atomic_jsonl(run_dir / "parent_projections.jsonl", projections)
        _atomic_jsonl(run_dir / "terminal_observations.jsonl", terminal_observations)


def _provider_snapshot(config: ExperimentConfig, provider: ModelProvider, request_model: str) -> ProviderSnapshot:
    return ProviderSnapshot(provider_ref=provider.provider_ref, provider_kind=config.provider.kind,
        model=request_model, model_revision=getattr(config.provider, "model_revision", None),
        model_repository=getattr(config.provider, "model_repository", None),
        deployment_manifest_sha256=getattr(config.provider, "deployment_manifest_sha256", None),
        deployment=(getattr(config.provider, "deployment", None).model_dump(mode="json")
                    if getattr(config.provider, "deployment", None) is not None else {}),
        api_style=getattr(provider, "api_style", None),
        base_url=getattr(provider, "base_url", None), request_model=getattr(provider, "request_model", request_model),
        response_model=getattr(provider, "response_model", None), generation=config.generation.model_dump(mode="json"),
        accessed_at=getattr(provider, "accessed_at", None))


def _manifest(config_path: Path, config: ExperimentConfig, adapter, bundles, provider, request_model,
              run_id: str, run_dir: Path, state: RunState, status: RunStatus, started_at: datetime) -> RunManifest:
    from agent_lab.runtime import _tree_hash
    artifacts = [InputArtifactRef(path=str(Path(config.dataset.path).resolve()), sha256=adapter.data_sha256,
        schema_version="3.0", dataset_name=bundles[0].truth_provenance.dataset_name,
        release=bundles[0].truth_provenance.release, split=bundles[0].truth_provenance.split),
        InputArtifactRef(path=str(Path(config.dataset.schema_path).resolve()),
            sha256=file_sha256(Path(config.dataset.schema_path)), schema_version="3.0")]
    if adapter.repair_manifest_path is not None:
        artifacts.append(InputArtifactRef(path=str(adapter.repair_manifest_path.resolve()),
            sha256=adapter.repair_manifest_sha256, schema_version="repair-manifest-1.0.0",
            dataset_name=bundles[0].truth_provenance.dataset_name,
            release=bundles[0].truth_provenance.release, split=bundles[0].truth_provenance.split))
    deps = {name: importlib.metadata.version(name) for name in ("pydantic", "jsonschema", "PyYAML", "httpx")}
    checkpoints = _load_checkpoints(run_dir, state)
    node_count = sum(len(checkpoint.nodes) for checkpoint in checkpoints)
    dependency_count = sum(len(checkpoint.dependencies) for checkpoint in checkpoints)
    m3 = config.m3_condition
    if m3 is not None:
        from agent_lab.m3_prompts import resolve_prompt_set
        prompt = resolve_prompt_set(config)
        prompt_snapshots = (PromptSnapshot(prompt_id=prompt.registry_id, version=prompt.registry_version,
            content_hash=prompt.prompt_set_hash, snapshot_path=str(run_dir / "prompt_snapshot.json"),
            component_hashes=prompt.component_hashes, prompt_set_hash=prompt.prompt_set_hash),)
    else:
        prompt = None
        prompt_snapshots = (PromptSnapshot(prompt_id=PROMPT_ID, version=PROMPT_VERSION,
                                           content_hash=content_hash()),)
    return RunManifest(run_id=run_id, status=status, experiment_id=config.experiment_id,
        condition_id=None if m3 is None else m3.condition_id,
        model_id=None if m3 is None else m3.model_id,
        dataset_id=None if m3 is None else m3.dataset_id,
        config_version=config.config_version, config_sha256=_config_hash(config_path, config),
        code_tree_sha256=_tree_hash(Path(__file__).resolve().parents[2]), input_artifacts=tuple(artifacts),
        selected_sample_ids=tuple(bundle.question.question_id for bundle in bundles),
        trace_path=str(run_dir / "trace.jsonl"), input_snapshot_path=str(run_dir / "input_snapshots.json"),
        assignment_snapshot_path=str(run_dir / "assignments.json"), gate_b_report_path=str(run_dir / "gate_b_report.json"),
        repair_manifest_path=None if adapter.repair_manifest_path is None else str(adapter.repair_manifest_path.resolve()),
        repair_manifest_sha256=adapter.repair_manifest_sha256, repair_rule_version=adapter.repair_rule_version,
        messages_path=str(run_dir / "messages.json"), message_nodes_path=str(run_dir / "message_nodes.jsonl"),
        message_node_count=node_count, dependency_records_path=str(run_dir / "dependency_records.jsonl"),
        dependency_record_count=dependency_count, agent_states_path=str(run_dir / "agent_states.json"),
        aggregated_result_path=str(run_dir / "aggregated_results.json"), summary_path=str(run_dir / "summary.json"),
        python_version=platform.python_version(), dependencies=deps, random_seed=config.randomness.seed,
        replicate_id=config.randomness.replicate_id, topology_kind=config.topology.kind,
        communication_rounds=config.protocol.communication_rounds, message_format=config.protocol.message_format,
        protocol_profile=config.protocol.profile, document_assignment_policy=config.document_assignment.policy,
        providers=(_provider_snapshot(config, provider, request_model),),
        prompts=prompt_snapshots,
        prompt_registry_sha256=None if prompt is None else prompt.registry_sha256,
        condition_contract_path=None if m3 is None else str(run_dir / "condition_contract.json"),
        request_reconstruction_path=None if m3 is None else str(run_dir / "request_reconstruction.jsonl"),
        parent_projection_path=None if m3 is None else str(run_dir / "parent_projections.jsonl"),
        run_state_path=str(run_dir / "run_state.json"), question_checkpoint_dir=str(run_dir / "question_checkpoints"),
        logical_model_requests=state.logical_model_requests, total_model_attempts=state.total_model_attempts,
        retry_count=state.retry_count, started_at=started_at,
        finished_at=None if status is RunStatus.RUNNING else _utcnow(),
        notes=("Silver data are for engineering validation only.",
               "No final QA answer or formal metrics were produced."))


def _finalize(run_dir: Path, config_path: Path, config: ExperimentConfig, adapter, bundles, assignments,
              provider, request_model, trace, state: RunState, started_at: datetime) -> RunState:
    _rebuild_roots(run_dir, state, bundles, assignments)
    completed = sum(entry.status is QuestionRunStatus.COMPLETED for entry in state.questions.values())
    failed = sum(entry.status is QuestionRunStatus.FAILED for entry in state.questions.values())
    status = RunStatus.COMPLETED if completed == len(state.selected_sample_ids) else RunStatus.FAILED
    state = state.model_copy(update={"status": status, "updated_at": _utcnow(), "finished_at": _utcnow()})
    _atomic_json(run_dir / "run_state.json", state)
    checkpoints = _load_checkpoints(run_dir, state)
    nodes = sum(len(checkpoint.nodes) for checkpoint in checkpoints)
    dependencies = sum(len(checkpoint.dependencies) for checkpoint in checkpoints)
    messages = sum(len(checkpoint.messages) for checkpoint in checkpoints)
    summary = RunSummary(run_id=state.run_id, status=status, questions_total=len(state.selected_sample_ids),
        questions_completed=completed, questions_failed=failed, model_calls=state.total_model_attempts,
        messages_delivered=messages, message_nodes=nodes, dependency_records=dependencies,
        trace_events=trace.count + 1, logical_model_requests=state.logical_model_requests,
        total_model_attempts=state.total_model_attempts, retry_count=state.retry_count)
    _atomic_json(run_dir / "summary.json", summary)
    manifest = _manifest(config_path, config, adapter, bundles, provider, request_model,
                         state.run_id, run_dir, state, status, started_at)
    _atomic_json(run_dir / "manifest.json", manifest)
    trace.emit(TraceEventType.RUN_FINISHED if status is RunStatus.COMPLETED else TraceEventType.RUN_FAILED,
               event_data={"completed": completed, "failed": failed,
                           "pending": len(state.selected_sample_ids) - completed - failed,
                           "total_model_attempts": state.total_model_attempts})
    return state


def run_reliable_experiment(config_path: Path, config: ExperimentConfig, *, runs_dir_override=None,
                            provider: ModelProvider | None = None, sleeper: Callable[[float], None] = time.sleep,
                            interrupt_after_questions: int | None = None) -> Path:
    from agent_lab.runtime import TraceWriter, _tree_hash, prepare_experiment, stable_id
    plan = plan_experiment(config)
    if not plan["within_budget"]:
        raise ReliabilityError(ReliabilityErrorCode.CONFIG, "expected logical calls exceed attempt budget")
    if (config.m3_condition is not None and config.provider.kind != "lineage_replay_mock" and
            (os.environ.get("AGENT_LAB_M3_BLIND_RELABEL_STATUS") != "passed" or
             os.environ.get("AGENT_LAB_M3_PAID_EXECUTION_AUTHORIZED") != "YES")):
        raise ReliabilityError(
            ReliabilityErrorCode.CONFIG,
            "real M3 provider execution is blocked until blind relabel passes and paid execution is explicitly authorized",
        )
    adapter, _, bundles, gate_b, frozen = prepare_experiment(config)
    prompt = condition_contract = None
    if config.m3_condition is not None:
        if runs_dir_override is not None:
            raise ReliabilityError(ReliabilityErrorCode.CONFIG, "M3 run directories cannot be manually overridden")
        from agent_lab.m3_execution import validate_condition_contract
        from agent_lab.m3_prompts import a2_prompt_diff, resolve_prompt_set
        prompt = resolve_prompt_set(config)
        condition_contract = validate_condition_contract(config, prompt)
    provider = provider or create_provider(config.provider, config.generation)
    request_model = getattr(config.provider, "model", None) or getattr(config.provider, "version")
    if config.m3_condition is None:
        run_id = stable_id("run", config.experiment_id, config.randomness.replicate_id)
    else:
        m3_identity = config.m3_condition
        run_id = stable_id("run", m3_identity.condition_id, m3_identity.model_id, m3_identity.dataset_id,
                           m3_identity.replicate_id)
    run_root = Path(runs_dir_override).resolve() if runs_dir_override else Path(config.output.runs_dir).resolve()
    run_dir = run_root / run_id if config.m3_condition is None else _m3_run_dir(run_root, m3_identity, run_id)
    if run_dir.exists():
        raise FileExistsError(f"run directory already exists: {run_dir}; use resume")
    run_dir.mkdir(parents=True)
    started = _utcnow(); code_hash = _tree_hash(Path(__file__).resolve().parents[2])
    identity_hash, identity = _identity(config_path, config, adapter, bundles, code_hash)
    questions = {bundle.question.question_id: QuestionStateEntry() for bundle in bundles}
    prompt_id = PROMPT_ID if prompt is None else prompt.registry_id
    prompt_version = PROMPT_VERSION if prompt is None else prompt.registry_version
    prompt_hash = content_hash() if prompt is None else prompt.prompt_set_hash
    state = RunState(run_id=run_id, status=RunStatus.RUNNING, config_sha256=identity["config_sha256"],
        code_tree_sha256=code_hash, input_artifact_sha256=adapter.data_sha256,
        schema_artifact_sha256=identity["schema_sha256"], repair_manifest_sha256=adapter.repair_manifest_sha256,
        identity_sha256=identity_hash, prompt_id=prompt_id, prompt_version=prompt_version,
        prompt_hash=prompt_hash, provider_snapshot=config.provider.model_dump(mode="json"),
        generation_snapshot=config.generation.model_dump(mode="json"),
        selected_sample_ids=tuple(questions), questions=questions, started_at=started, updated_at=started)
    _atomic_json(run_dir / "input_snapshots.json", [bundle.model_dump(mode="json") for bundle in bundles])
    _atomic_json(run_dir / "assignments.json", [frozen[q].model_dump(mode="json") for q in questions])
    _atomic_json(run_dir / "gate_b_report.json", gate_b)
    _atomic_json(run_dir / "run_state.json", state)
    if prompt is not None:
        _atomic_json(run_dir / "prompt_snapshot.json", prompt.snapshot())
        _atomic_json(run_dir / "condition_contract.json", condition_contract)
        if config.m3_condition.condition_id == "A2":
            _atomic_json(run_dir / "a2_prompt_diff.json", a2_prompt_diff(
                config.m3_condition.prompt_registry.path,
                config.m3_condition.prompt_registry.expected_sha256))
    _atomic_json(run_dir / "manifest.json", _manifest(config_path, config, adapter, bundles, provider,
                                                       request_model, run_id, run_dir, state, RunStatus.RUNNING, started))
    trace = TraceWriter(run_dir / "trace.jsonl", run_id)
    trace.emit(TraceEventType.RUN_STARTED, event_data={"experiment_id": config.experiment_id})
    attempts = AttemptExecutor(provider, config, trace, state,
        lambda value: _atomic_json(run_dir / "run_state.json", value), sleeper)
    completed_this_process = 0
    for bundle in bundles:
        qid = bundle.question.question_id
        questions = dict(attempts.state.questions)
        questions[qid] = questions[qid].model_copy(update={"status": QuestionRunStatus.RUNNING})
        attempts.state = attempts.state.model_copy(update={"questions": questions, "updated_at": _utcnow()})
        _atomic_json(run_dir / "run_state.json", attempts.state)
        before = attempts.state.questions[qid].attempt_count
        try:
            checkpoint = _question_artifacts(bundle, frozen[qid], config, provider, request_model,
                                             run_id, trace, attempts)
        except Exception as error:
            code = error.code.value if isinstance(error, (ProviderError, ReliabilityError)) else type(error).__name__
            detail = error.detail if isinstance(error, (ProviderError, ReliabilityError)) else str(error)
            checkpoint = QuestionCheckpoint(run_id=run_id, question_id=qid, status=QuestionRunStatus.FAILED,
                attempt_count=attempts.state.questions[qid].attempt_count, failure_code=code,
                failure_detail=detail, created_at=_utcnow())
            trace.emit(TraceEventType.QUESTION_FAILED, question_id=qid,
                       event_data={"failure_code": code, "failure_detail": detail})
        checkpoint_path = Path("question_checkpoints") / _checkpoint_name(qid)
        _atomic_json(run_dir / checkpoint_path, checkpoint)
        questions = dict(attempts.state.questions)
        questions[qid] = QuestionStateEntry(status=checkpoint.status,
            attempt_count=attempts.state.questions[qid].attempt_count,
            checkpoint_path=str(checkpoint_path), failure_code=checkpoint.failure_code,
            failure_detail=checkpoint.failure_detail)
        attempts.state = attempts.state.model_copy(update={"questions": questions,
            "updated_at": _utcnow()})
        # Logical calls are the number of distinct started request IDs, recomputed safely from trace at finalize.
        _atomic_json(run_dir / "run_state.json", attempts.state)
        trace.emit(TraceEventType.QUESTION_CHECKPOINTED, question_id=qid,
                   event_data={"status": checkpoint.status.value, "checkpoint_path": str(checkpoint_path),
                               "attempt_count": checkpoint.attempt_count})
        _rebuild_roots(run_dir, attempts.state, bundles, tuple(frozen[q] for q in questions))
        completed_this_process += 1
        if interrupt_after_questions is not None and completed_this_process >= interrupt_after_questions:
            raise KeyboardInterrupt("simulated interruption after committed question")
        if checkpoint.failure_code in {ProviderErrorCode.CONFIG.value, ProviderErrorCode.CREDENTIAL_MISSING.value,
                                       ProviderErrorCode.AUTHENTICATION.value}:
            break
    started_request_ids = {json.loads(line)["event_data"].get("logical_request_id")
                           for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
                           if json.loads(line)["event_type"] == TraceEventType.MODEL_ATTEMPT_STARTED.value}
    started_request_ids.discard(None)
    attempts.state = attempts.state.model_copy(update={"logical_model_requests": len(started_request_ids)})
    _finalize(run_dir, config_path, config, adapter, bundles, tuple(frozen[q] for q in questions), provider,
              request_model, trace, attempts.state, started)
    return run_dir


def resume_reliable_experiment(config_path: str | Path, *, runs_dir_override=None,
                               provider: ModelProvider | None = None,
                               sleeper: Callable[[float], None] = time.sleep) -> Path:
    from agent_lab.runtime import TraceWriter, _tree_hash, load_config, prepare_experiment, stable_id
    config_path = Path(config_path).resolve(); config = load_config(config_path)
    if config.execution is None:
        raise ReliabilityError(ReliabilityErrorCode.CONFIG, "resume requires execution configuration")
    if config.m3_condition is not None and runs_dir_override is not None:
        raise ReliabilityError(ReliabilityErrorCode.CONFIG, "M3 run directories cannot be manually overridden")
    adapter, _, bundles, gate_b, frozen = prepare_experiment(config)
    provider = provider or create_provider(config.provider, config.generation)
    request_model = getattr(config.provider, "model", None) or getattr(config.provider, "version")
    if config.m3_condition is None:
        run_id = stable_id("run", config.experiment_id, config.randomness.replicate_id)
    else:
        m3_identity = config.m3_condition
        run_id = stable_id("run", m3_identity.condition_id, m3_identity.model_id,
                           m3_identity.dataset_id, m3_identity.replicate_id)
    run_root = Path(runs_dir_override).resolve() if runs_dir_override else Path(config.output.runs_dir).resolve()
    run_dir = run_root / run_id if config.m3_condition is None else _m3_run_dir(run_root, m3_identity, run_id)
    state_path = run_dir / "run_state.json"
    if not state_path.is_file():
        raise FileNotFoundError(f"run state not found: {state_path}")
    state = RunState.model_validate_json(state_path.read_text(encoding="utf-8"))
    code_hash = _tree_hash(Path(__file__).resolve().parents[2])
    identity_hash, identity = _identity(config_path, config, adapter, bundles, code_hash)
    if config.m3_condition is None:
        expected_prompt_id, expected_prompt_version, expected_prompt_hash = PROMPT_ID, PROMPT_VERSION, content_hash()
    else:
        from agent_lab.m3_execution import validate_condition_contract
        from agent_lab.m3_prompts import resolve_prompt_set
        prompt = resolve_prompt_set(config)
        validate_condition_contract(config, prompt)
        expected_prompt_id, expected_prompt_version, expected_prompt_hash = \
            prompt.registry_id, prompt.registry_version, prompt.prompt_set_hash
    if (state.run_id != run_id or state.identity_sha256 != identity_hash
            or state.config_sha256 != identity["config_sha256"]
            or state.code_tree_sha256 != code_hash
            or state.input_artifact_sha256 != adapter.data_sha256
            or state.schema_artifact_sha256 != identity["schema_sha256"]
            or state.repair_manifest_sha256 != adapter.repair_manifest_sha256
            or state.selected_sample_ids != tuple(bundle.question.question_id for bundle in bundles)
            or state.prompt_id != expected_prompt_id or state.prompt_version != expected_prompt_version
            or state.prompt_hash != expected_prompt_hash
            or state.provider_snapshot != config.provider.model_dump(mode="json")
            or state.generation_snapshot != config.generation.model_dump(mode="json")):
        raise ReliabilityError(ReliabilityErrorCode.RESUME_MISMATCH, "frozen run identity changed")
    questions = dict(state.questions)
    for qid, entry in tuple(questions.items()):
        if entry.status is QuestionRunStatus.RUNNING:
            questions[qid] = entry.model_copy(update={"status": QuestionRunStatus.PENDING})
    state = state.model_copy(update={"status": RunStatus.RUNNING, "questions": questions,
                                    "updated_at": _utcnow(), "finished_at": None})
    _atomic_json(state_path, state)
    trace = TraceWriter(run_dir / "trace.jsonl", run_id, append=True)
    trace.emit(TraceEventType.RUN_RESUMED,
               event_data={"completed_skipped": sum(e.status is QuestionRunStatus.COMPLETED for e in questions.values()),
                           "total_model_attempts": state.total_model_attempts})
    attempts = AttemptExecutor(provider, config, trace, state, lambda value: _atomic_json(state_path, value), sleeper)
    bundle_by_id = {bundle.question.question_id: bundle for bundle in bundles}
    for qid in state.selected_sample_ids:
        entry = attempts.state.questions[qid]
        if entry.status in {QuestionRunStatus.COMPLETED, QuestionRunStatus.FAILED}:
            continue
        questions = dict(attempts.state.questions)
        questions[qid] = entry.model_copy(update={"status": QuestionRunStatus.RUNNING})
        attempts.state = attempts.state.model_copy(update={"questions": questions, "updated_at": _utcnow()})
        _atomic_json(state_path, attempts.state)
        try:
            checkpoint = _question_artifacts(bundle_by_id[qid], frozen[qid], config, provider,
                                             request_model, run_id, trace, attempts)
        except Exception as error:
            code = error.code.value if isinstance(error, (ProviderError, ReliabilityError)) else type(error).__name__
            detail = error.detail if isinstance(error, (ProviderError, ReliabilityError)) else str(error)
            checkpoint = QuestionCheckpoint(run_id=run_id, question_id=qid, status=QuestionRunStatus.FAILED,
                attempt_count=attempts.state.questions[qid].attempt_count, failure_code=code,
                failure_detail=detail, created_at=_utcnow())
            trace.emit(TraceEventType.QUESTION_FAILED, question_id=qid,
                       event_data={"failure_code": code, "failure_detail": detail})
        checkpoint_path = Path("question_checkpoints") / _checkpoint_name(qid)
        _atomic_json(run_dir / checkpoint_path, checkpoint)
        questions = dict(attempts.state.questions)
        questions[qid] = QuestionStateEntry(status=checkpoint.status,
            attempt_count=attempts.state.questions[qid].attempt_count, checkpoint_path=str(checkpoint_path),
            failure_code=checkpoint.failure_code, failure_detail=checkpoint.failure_detail)
        attempts.state = attempts.state.model_copy(update={"questions": questions, "updated_at": _utcnow()})
        _atomic_json(state_path, attempts.state)
        trace.emit(TraceEventType.QUESTION_CHECKPOINTED, question_id=qid,
                   event_data={"status": checkpoint.status.value, "checkpoint_path": str(checkpoint_path),
                               "attempt_count": checkpoint.attempt_count})
        _rebuild_roots(run_dir, attempts.state, bundles, tuple(frozen[q] for q in questions))
    started_ids = {json.loads(line)["event_data"].get("logical_request_id")
                   for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
                   if json.loads(line)["event_type"] == TraceEventType.MODEL_ATTEMPT_STARTED.value}
    started_ids.discard(None)
    attempts.state = attempts.state.model_copy(update={"logical_model_requests": len(started_ids)})
    manifest = RunManifest.model_validate_json((run_dir / "manifest.json").read_text(encoding="utf-8"))
    _finalize(run_dir, config_path, config, adapter, bundles, tuple(frozen[q] for q in questions), provider,
              request_model, trace, attempts.state, manifest.started_at)
    return run_dir
