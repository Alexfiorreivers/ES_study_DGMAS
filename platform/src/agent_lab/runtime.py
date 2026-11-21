"""Serial, trace-first experiment runner with a Schema 3.0 Gate A."""

from __future__ import annotations

import importlib.metadata
import json
import platform
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml

from agent_lab.adapters.datasets import DataTruthV3Adapter
from agent_lab.adapters.datasets.data_truth_v3 import file_sha256
from agent_lab.domain.contracts_v0_1 import (
    AgentStateSnapshot, AggregatedClaim, AggregatedResult, AtomicClaim, ExperimentConfig,
    DependencyKind, DependencyRecord, FreeTextPayload, FreeTextRecord, InputArtifactRef,
    MessageEnvelope, MessageFormat,
    MessageStatus, ModelRequest, PlatformInputBundle, PromptSnapshot,
    ProviderSnapshot, ReferenceOrigin, RunManifest, RunStatus, RunSummary,
    RuntimeMessageNode, RuntimeNodeKind, Stage, StructuredPayload, TraceEvent, TraceEventType,
)
from agent_lab.evaluation_trace import (
    canonical_messages_sha256,
    communication_visible_input,
    initial_messages,
    validate_reconstructability,
)
from agent_lab.eligibility import evaluate_selected
from agent_lab.prompts import PROMPT_ID, PROMPT_VERSION, content_hash
from agent_lab.providers import LineageReplayMockProvider, ProviderError, create_provider
from agent_lab.topology import directed_edges


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def stable_id(prefix: str, *parts: object) -> str:
    material = "\x1f".join(str(part) for part in parts)
    return f"{prefix}_{sha256(material.encode()).hexdigest()[:20]}"


def load_config(path: str | Path) -> ExperimentConfig:
    path = Path(path).resolve()
    def merge(left, right):
        result = dict(left)
        for key, value in right.items():
            can_merge = (key in result and isinstance(result[key], dict) and isinstance(value, dict)
                         and not ("kind" in result[key] and "kind" in value
                                  and result[key]["kind"] != value["kind"]))
            result[key] = merge(result[key], value) if can_merge else value
        return result
    def read(current: Path, seen: set[Path]):
        if current in seen:
            raise ValueError("CONFIG_EXTENDS_CYCLE")
        raw_value = yaml.safe_load(current.read_text(encoding="utf-8"))
        parent = raw_value.pop("extends", None)
        if parent is None:
            return raw_value
        base_path = (current.parent / parent).resolve()
        return merge(read(base_path, seen | {current}), raw_value)
    raw = read(path, set())
    return ExperimentConfig.model_validate(raw)


def prepare_experiment(config: ExperimentConfig):
    """Complete Gate A and Gate B before any provider/run artifact exists."""
    adapter = DataTruthV3Adapter(
        config.dataset.path,
        config.dataset.schema_path,
        config.dataset.expected_sha256,
        config.dataset.repair_manifest_path,
        config.dataset.expected_repair_manifest_sha256,
    )
    gate_a_report = adapter.validate_all()
    bundles = adapter.load_selected(config.dataset.sample_ids)
    gate_b_report, assignments = evaluate_selected(bundles, config)
    return adapter, gate_a_report, bundles, gate_b_report, assignments


def _tree_hash(root: Path) -> str:
    digest = sha256()
    for path in sorted((root / "src").rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


class TraceWriter:
    def __init__(self, path: Path, run_id: str, *, append: bool = False):
        self.path, self.run_id, self.count = path, run_id, 0
        path.parent.mkdir(parents=True, exist_ok=True)
        if append and path.exists():
            events = [TraceEvent.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines()
                      if line.strip()]
            ids = [event.event_id for event in events]
            if len(ids) != len(set(ids)) or any(event.run_id != run_id for event in events):
                raise ValueError("existing trace is not safe to resume")
            expected = [f"evt_{index:06d}" for index in range(1, len(events) + 1)]
            if ids != expected:
                raise ValueError("existing trace event sequence is not contiguous")
            self.count = len(events)
        else:
            path.write_text("", encoding="utf-8")

    def emit(self, event_type: TraceEventType, **fields: Any) -> None:
        self.count += 1
        event = TraceEvent(event_id=f"evt_{self.count:06d}", event_type=event_type,
            timestamp=utcnow(), run_id=self.run_id, **fields)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(event.model_dump_json() + "\n")


def _available_claims(bundle: PlatformInputBundle, context_indexes: set[int]) -> tuple[AtomicClaim, ...]:
    return tuple(claim for claim in bundle.seed_claims
        if claim.source_refs and all(ref.context_ref.context_index in context_indexes for ref in claim.source_refs))


def _inherited(claim: AtomicClaim, message_id: str, hop: int) -> AtomicClaim:
    refs = tuple(ref.model_copy(update={"reference_origin": ReferenceOrigin.INHERITED_MESSAGE}) for ref in claim.source_refs)
    return claim.model_copy(update={"claim_id": stable_id("claim", message_id, claim.claim_id),
        "source_refs": refs, "parent_claim_ids": (claim.claim_id,), "communication_hop": hop})


def _payload(claims: tuple[AtomicClaim, ...], fmt: MessageFormat):
    status = MessageStatus.CONTENT if claims else MessageStatus.NO_NEW_INFORMATION
    if fmt is MessageFormat.STRUCTURED:
        return StructuredPayload(message_status=status, claims=claims)
    return FreeTextPayload(message_status=status, text="\n".join(c.claim_text for c in claims),
        declared_source_refs=tuple(ref for claim in claims for ref in claim.source_refs))


def _canonical_payload(response, fmt: MessageFormat, node_id: str, round_number: int):
    if fmt is MessageFormat.STRUCTURED:
        parsed = StructuredPayload.model_validate(response.raw_response)
        claims = parsed.claims
        if round_number > 0:
            claims = tuple(_inherited(claim, node_id, round_number) for claim in claims)
        claims = _dedupe_claims(list(claims))
        return _payload(claims, fmt), claims
    raw = response.raw_response if isinstance(response.raw_response, dict) else {}
    claims = tuple(AtomicClaim.model_validate(value) for value in raw.get("claims", []))
    if round_number > 0:
        claims = tuple(_inherited(claim, node_id, round_number) for claim in claims)
    claims = _dedupe_claims(list(claims))
    text = response.raw_text
    status = MessageStatus.CONTENT if text.strip() else MessageStatus.NO_NEW_INFORMATION
    return FreeTextPayload(
        message_status=status,
        text=text,
        declared_source_refs=tuple(ref for claim in claims for ref in claim.source_refs),
    ), claims


def _dedupe_claims(claims: list[AtomicClaim]) -> tuple[AtomicClaim, ...]:
    seen: set[tuple[str, tuple[str, ...]]] = set(); result = []
    for claim in claims:
        key = (" ".join(claim.claim_text.casefold().split()), tuple(sorted(r.evidence_id for r in claim.source_refs)))
        if key not in seen:
            seen.add(key); result.append(claim)
    return tuple(result)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(value, "model_dump_json"):
        path.write_text(value.model_dump_json(indent=2), encoding="utf-8")
    else:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, values) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for value in values:
            stream.write(value.model_dump_json() + "\n")


def _claims_from_node(node: RuntimeMessageNode, machine_claims: dict[str, tuple[AtomicClaim, ...]]):
    if isinstance(node.payload, StructuredPayload):
        return node.payload.claims
    return machine_claims.get(node.node_id, ())


def _message_from_node(
    node: RuntimeMessageNode,
    parent_nodes: tuple[RuntimeMessageNode, ...],
    machine_claims: tuple[AtomicClaim, ...],
) -> MessageEnvelope:
    return MessageEnvelope(
        message_id=stable_id("msg", node.node_id),
        run_id=node.run_id,
        question_id=node.question_id,
        stage=node.stage,
        round=node.round,
        communication_hop=node.communication_hop,
        sender_id=node.sender_id,
        receiver_id=node.receiver_id,
        message_format=MessageFormat(node.payload.payload_type),
        payload=node.payload,
        parent_message_ids=tuple(
            stable_id("msg", parent.node_id)
            for parent in parent_nodes
            if parent.node_kind is RuntimeNodeKind.COMMUNICATION_OUTPUT
        ),
        created_at=node.created_at,
        prompt_ref=node.prompt_ref,
        model_ref=node.model_ref,
        metadata={
            "canonical_node_id": node.node_id,
            "machine_claims": [claim.model_dump(mode="json") for claim in machine_claims],
            "raw_documents_supplied": False,
            "response_id": node.response_id,
        },
    )


def run_experiment(config_path: str | Path, *, runs_dir_override: str | Path | None = None) -> Path:
    config_path = Path(config_path).resolve(); config = load_config(config_path)
    if config.execution is not None:
        from agent_lab.reliability import run_reliable_experiment
        return run_reliable_experiment(config_path, config, runs_dir_override=runs_dir_override)
    # Gate A completes for the entire input artifact before a provider is created
    # or any run directory/model-call trace can exist.
    adapter, _, bundles, gate_b_report, frozen_assignments = prepare_experiment(config)
    provider = create_provider(config.provider, config.generation)
    request_model = getattr(config.provider, "model", None) or getattr(config.provider, "version")
    run_id = stable_id("run", config.experiment_id, config.randomness.replicate_id, config_path.read_bytes().hex())
    run_root = Path(runs_dir_override).resolve() if runs_dir_override is not None else Path(config.output.runs_dir).resolve()
    run_dir = run_root / run_id
    if run_dir.exists():
        raise FileExistsError(f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    paths = {name: run_dir / filename for name, filename in {
        "trace": "trace.jsonl", "inputs": "input_snapshots.json", "assignments": "assignments.json",
        "gate_b": "gate_b_report.json",
        "nodes": "message_nodes.jsonl", "dependencies": "dependency_records.jsonl",
        "messages": "messages.json", "states": "agent_states.json",
        "results": "aggregated_results.json", "summary": "summary.json",
        "manifest": "manifest.json"}.items()}
    trace = TraceWriter(paths["trace"], run_id); started = utcnow()
    _write_json(paths["gate_b"], gate_b_report)
    trace.emit(TraceEventType.RUN_STARTED, event_data={"experiment_id": config.experiment_id})
    all_assignments, all_states, all_results, messages = [], [], [], []
    nodes: list[RuntimeMessageNode] = []
    dependencies: list[DependencyRecord] = []
    machine_claims_by_node: dict[str, tuple[AtomicClaim, ...]] = {}
    completed = failed = model_calls = delivered = 0
    for bundle in bundles:
        qid = bundle.question.question_id
        trace.emit(TraceEventType.QUESTION_STARTED, question_id=qid)
        try:
            assignment = frozen_assignments[qid]
            all_assignments.append(assignment)
            trace.emit(TraceEventType.DOCUMENT_ASSIGNMENT_FROZEN, question_id=qid,
                event_data=assignment.model_dump(mode="json"))
            question_nodes: list[RuntimeMessageNode] = []
            initial_nodes: dict[str, RuntimeMessageNode] = {}
            trace.emit(TraceEventType.INITIAL_READ_STARTED, question_id=qid, stage=Stage.INITIAL_READ, round=0)
            for spec in config.agents:
                indexes = {ref.context_index for ref in assignment.assignments[spec.agent_id]}
                local = _available_claims(bundle, indexes)
                local_documents = tuple(d for d in bundle.documents if d.context_index in indexes)
                visible_document_refs = tuple(assignment.assignments[spec.agent_id])
                request_messages = initial_messages(bundle, visible_document_refs)
                request = ModelRequest(request_id=stable_id("req", run_id, qid, spec.agent_id, 0),
                    provider_ref=provider.provider_ref, model=request_model,
                    messages=request_messages,
                    output_format=config.protocol.message_format, output_schema_version="0.1",
                    prompt_id=PROMPT_ID, prompt_version=PROMPT_VERSION, prompt_content_hash=content_hash(),
                    run_id=run_id, question_id=qid, agent_id=spec.agent_id, stage=Stage.INITIAL_READ,
                    round=0, receiver_id=spec.agent_id, replicate_id=config.randomness.replicate_id,
                    request_context={"local_documents": [d.model_dump(mode="json") for d in local_documents],
                                     "local_claims": [c.model_dump(mode="json") for c in local],
                                     "mock_oracle_usage": "accessible-evidence replay only"})
                trace.emit(TraceEventType.MODEL_ATTEMPT_STARTED, question_id=qid, stage=Stage.INITIAL_READ,
                    round=0, agent_id=spec.agent_id, attempt=1, event_data={"request": request.model_dump(mode="json")})
                response = provider.complete(request); model_calls += 1
                trace.emit(TraceEventType.MODEL_RESPONSE_RECEIVED, question_id=qid, stage=Stage.INITIAL_READ,
                    round=0, agent_id=spec.agent_id, event_data=response.model_dump(mode="json"))
                node_id = stable_id("node", request.request_id)
                payload, canonical_claims = _canonical_payload(response, config.protocol.message_format, node_id, 0)
                node = RuntimeMessageNode(
                    node_id=node_id, node_kind=RuntimeNodeKind.INITIAL_OUTPUT,
                    run_id=run_id, question_id=qid, sender_id=spec.agent_id, receiver_id=spec.agent_id,
                    stage=Stage.INITIAL_READ, round=0, communication_hop=0,
                    visible_document_refs=visible_document_refs, payload=payload,
                    request_id=request.request_id, response_id=response.response_id,
                    prompt_ref=f"{PROMPT_ID}:{PROMPT_VERSION}", model_ref=provider.provider_ref,
                    visible_input_sha256=canonical_messages_sha256(request_messages), created_at=utcnow(),
                )
                nodes.append(node); question_nodes.append(node); initial_nodes[spec.agent_id] = node
                machine_claims_by_node[node.node_id] = canonical_claims
                trace.emit(TraceEventType.MESSAGE_NODE_CREATED, question_id=qid, stage=Stage.INITIAL_READ,
                    round=0, agent_id=spec.agent_id,
                    event_data={"node_id": node.node_id, "request_id": node.request_id, "response_id": node.response_id})
            trace.emit(TraceEventType.INITIAL_READ_FINISHED, question_id=qid, stage=Stage.INITIAL_READ, round=0)
            for round_number in range(1, config.protocol.communication_rounds + 1):
                trace.emit(TraceEventType.ROUND_STARTED, question_id=qid, stage=Stage.COMMUNICATION, round=round_number)
                for sender, receiver in directed_edges(config.topology.kind, config.topology.center_agent_id):
                    request_id = stable_id("req", run_id, qid, round_number, sender, receiver)
                    node_id = stable_id("node", request_id)
                    parent_nodes = (initial_nodes[sender],) + tuple(
                        node for node in question_nodes
                        if node.node_kind is RuntimeNodeKind.COMMUNICATION_OUTPUT
                        and node.round == round_number - 1 and node.receiver_id == sender
                    )
                    child_dependencies = tuple(
                        DependencyRecord(
                            dependency_id=stable_id("dep", parent.node_id, node_id,
                                DependencyKind.SELF_INITIAL.value if parent.node_kind is RuntimeNodeKind.INITIAL_OUTPUT
                                else DependencyKind.RECEIVED_MESSAGE.value),
                            run_id=run_id, question_id=qid, parent_node_id=parent.node_id, child_node_id=node_id,
                            dependency_kind=(DependencyKind.SELF_INITIAL if parent.node_kind is RuntimeNodeKind.INITIAL_OUTPUT
                                             else DependencyKind.RECEIVED_MESSAGE),
                            parent_round=parent.round, child_round=round_number,
                            visible_claim_ids=tuple(
                                claim.claim_id for claim in parent.payload.claims
                            ) if isinstance(parent.payload, StructuredPayload) else (),
                        )
                        for parent in parent_nodes
                    )
                    request_messages, visible_claims, visible_parent_ids = communication_visible_input(
                        bundle, node_id, question_nodes, child_dependencies
                    )
                    request = ModelRequest(request_id=request_id,
                        provider_ref=provider.provider_ref, model=request_model,
                        messages=request_messages,
                        output_format=config.protocol.message_format, output_schema_version="0.1",
                        prompt_id=PROMPT_ID, prompt_version=PROMPT_VERSION, prompt_content_hash=content_hash(),
                        run_id=run_id, question_id=qid, agent_id=sender, stage=Stage.COMMUNICATION,
                        round=round_number, receiver_id=receiver, replicate_id=config.randomness.replicate_id,
                        request_context={"incoming_claims": [c.model_dump(mode="json") for c in visible_claims],
                                         "incoming_texts": [parent.payload.text for parent in parent_nodes
                                                            if isinstance(parent.payload, FreeTextPayload)],
                                         "visible_parent_node_ids": list(visible_parent_ids),
                                         "raw_documents_supplied": False})
                    trace.emit(TraceEventType.MODEL_ATTEMPT_STARTED, question_id=qid, stage=Stage.COMMUNICATION,
                        round=round_number, agent_id=sender, attempt=1, event_data={"request": request.model_dump(mode="json")})
                    response = provider.complete(request); model_calls += 1
                    payload, canonical_claims = _canonical_payload(
                        response, config.protocol.message_format, node_id, round_number
                    )
                    node = RuntimeMessageNode(
                        node_id=node_id, node_kind=RuntimeNodeKind.COMMUNICATION_OUTPUT,
                        run_id=run_id, question_id=qid, sender_id=sender, receiver_id=receiver,
                        stage=Stage.COMMUNICATION, round=round_number, communication_hop=round_number,
                        visible_document_refs=(), payload=payload,
                        request_id=request.request_id, response_id=response.response_id,
                        prompt_ref=f"{PROMPT_ID}:{PROMPT_VERSION}", model_ref=provider.provider_ref,
                        visible_input_sha256=canonical_messages_sha256(request_messages), created_at=utcnow(),
                    )
                    nodes.append(node); question_nodes.append(node)
                    machine_claims_by_node[node.node_id] = canonical_claims
                    dependencies.extend(child_dependencies)
                    message = _message_from_node(node, parent_nodes, canonical_claims)
                    messages.append(message); delivered += 1
                    trace.emit(TraceEventType.MODEL_RESPONSE_RECEIVED, question_id=qid, stage=Stage.COMMUNICATION,
                        round=round_number, agent_id=sender, event_data=response.model_dump(mode="json"))
                    trace.emit(TraceEventType.MESSAGE_NODE_CREATED, question_id=qid, stage=Stage.COMMUNICATION,
                        round=round_number, agent_id=sender, message_id=message.message_id,
                        event_data={"node_id": node.node_id, "request_id": node.request_id, "response_id": node.response_id})
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
            question_states = []
            for spec in config.agents:
                received_nodes = tuple(
                    node for node in question_nodes
                    if node.node_kind is RuntimeNodeKind.COMMUNICATION_OUTPUT and node.receiver_id == spec.agent_id
                )
                received = tuple(stable_id("msg", node.node_id) for node in received_nodes)
                state_claims = _dedupe_claims([
                    *_claims_from_node(initial_nodes[spec.agent_id], machine_claims_by_node),
                    *(claim for node in received_nodes for claim in _claims_from_node(node, machine_claims_by_node)),
                ])
                records = () if config.protocol.message_format is MessageFormat.STRUCTURED else tuple(
                    FreeTextRecord(text=c.claim_text, source_refs=c.source_refs) for c in state_claims
                )
                state = AgentStateSnapshot(run_id=run_id, question_id=qid, agent_id=spec.agent_id,
                    round=config.protocol.communication_rounds, message_format=config.protocol.message_format,
                    private_initial_claims=_claims_from_node(initial_nodes[spec.agent_id], machine_claims_by_node),
                    received_message_ids=received,
                    current_structured_claims=state_claims if config.protocol.message_format is MessageFormat.STRUCTURED else (),
                    current_free_text_records=records, created_at=utcnow())
                question_states.append(state); all_states.append(state)
                trace.emit(TraceEventType.AGENT_STATE_SNAPSHOTTED, question_id=qid, agent_id=spec.agent_id,
                    round=config.protocol.communication_rounds, event_data={"claim_count": len(state_claims)})
            grouped: dict[str, list[tuple[str, AtomicClaim]]] = {}
            for state in question_states:
                for claim in state.current_structured_claims:
                    grouped.setdefault(" ".join(claim.claim_text.casefold().split()), []).append((state.agent_id, claim))
            aggregated = tuple(AggregatedClaim(normalized_text=key, claim_text=items[0][1].claim_text,
                source_refs=_dedupe_refs([r for _, c in items for r in c.source_refs]),
                contributing_claim_ids=tuple(sorted({c.claim_id for _, c in items})),
                contributing_agent_ids=tuple(sorted({a for a, _ in items}))) for key, items in sorted(grouped.items()))
            result = AggregatedResult(run_id=run_id, question_id=qid, message_format=config.protocol.message_format,
                claims=aggregated, aggregator_version=config.aggregation.version, created_at=utcnow())
            all_results.append(result); completed += 1
            trace.emit(TraceEventType.AGGREGATION_COMPLETED, question_id=qid, stage=Stage.AGGREGATION,
                event_data={"candidate_claim_count": len(aggregated), "final_answer_generated": False})
            trace.emit(TraceEventType.QUESTION_FINISHED, question_id=qid)
        except Exception as error:
            failed += 1
            error_data = {"error_type": type(error).__name__, "error": str(error)}
            if isinstance(error, ProviderError):
                error_data["provider_error_code"] = error.code.value
                error_data["provider_http_status"] = error.status_code
            trace.emit(TraceEventType.QUESTION_FAILED, question_id=qid, event_data=error_data)
    status = RunStatus.COMPLETED if failed == 0 else RunStatus.FAILED
    trace.emit(TraceEventType.RUN_FINISHED if failed == 0 else TraceEventType.RUN_FAILED,
        event_data={"completed": completed, "failed": failed})
    validate_reconstructability(nodes, dependencies, bundles, all_assignments)
    _write_json(paths["inputs"], [b.model_dump(mode="json") for b in bundles])
    _write_json(paths["assignments"], [a.model_dump(mode="json") for a in all_assignments])
    _write_jsonl(paths["nodes"], nodes)
    _write_jsonl(paths["dependencies"], dependencies)
    _write_json(paths["messages"], [m.model_dump(mode="json") for m in messages])
    _write_json(paths["states"], [s.model_dump(mode="json") for s in all_states])
    _write_json(paths["results"], [r.model_dump(mode="json") for r in all_results])
    summary = RunSummary(run_id=run_id, status=status, questions_total=len(bundles), questions_completed=completed,
        questions_failed=failed, model_calls=model_calls, messages_delivered=delivered,
        message_nodes=len(nodes), dependency_records=len(dependencies), trace_events=trace.count)
    _write_json(paths["summary"], summary)
    root = Path(__file__).resolve().parents[2]
    installed_dependencies = {
        name: importlib.metadata.version(name) for name in ("pydantic", "jsonschema", "PyYAML", "httpx")
    }
    input_artifacts = [
        InputArtifactRef(path=str(Path(config.dataset.path).resolve()), sha256=adapter.data_sha256,
            schema_version="3.0", dataset_name=bundles[0].truth_provenance.dataset_name,
            release=bundles[0].truth_provenance.release, split=bundles[0].truth_provenance.split),
        InputArtifactRef(path=str(Path(config.dataset.schema_path).resolve()),
            sha256=file_sha256(Path(config.dataset.schema_path)), schema_version="3.0"),
    ]
    if adapter.repair_manifest_path is not None and adapter.repair_manifest_sha256 is not None:
        input_artifacts.append(InputArtifactRef(
            path=str(adapter.repair_manifest_path.resolve()),
            sha256=adapter.repair_manifest_sha256,
            schema_version="repair-manifest-1.0.0",
            dataset_name=bundles[0].truth_provenance.dataset_name,
            release=bundles[0].truth_provenance.release,
            split=bundles[0].truth_provenance.split,
        ))
    manifest = RunManifest(run_id=run_id, status=status, experiment_id=config.experiment_id,
        config_version=config.config_version, config_sha256=file_sha256(config_path), code_tree_sha256=_tree_hash(root),
        input_artifacts=tuple(input_artifacts),
        selected_sample_ids=tuple(b.question.question_id for b in bundles),
        trace_path=str(paths["trace"]), input_snapshot_path=str(paths["inputs"]),
        assignment_snapshot_path=str(paths["assignments"]), gate_b_report_path=str(paths["gate_b"]),
        repair_manifest_path=None if adapter.repair_manifest_path is None else str(adapter.repair_manifest_path.resolve()),
        repair_manifest_sha256=adapter.repair_manifest_sha256,
        repair_rule_version=adapter.repair_rule_version,
        messages_path=str(paths["messages"]),
        message_nodes_path=str(paths["nodes"]), message_node_count=len(nodes),
        dependency_records_path=str(paths["dependencies"]), dependency_record_count=len(dependencies),
        agent_states_path=str(paths["states"]),
        aggregated_result_path=str(paths["results"]), summary_path=str(paths["summary"]),
        python_version=platform.python_version(), dependencies=installed_dependencies, random_seed=config.randomness.seed,
        replicate_id=config.randomness.replicate_id, topology_kind=config.topology.kind,
        communication_rounds=config.protocol.communication_rounds, message_format=config.protocol.message_format,
        protocol_profile=config.protocol.profile,
        document_assignment_policy=config.document_assignment.policy,
        providers=(ProviderSnapshot(
            provider_ref=provider.provider_ref,
            provider_kind=config.provider.kind,
            model=request_model,
            model_revision=getattr(config.provider, "model_revision", None),
            model_repository=getattr(config.provider, "model_repository", None),
            deployment_manifest_sha256=getattr(config.provider, "deployment_manifest_sha256", None),
            deployment=(
                config.provider.deployment.model_dump(mode="json")
                if hasattr(config.provider, "deployment") else {}
            ),
            api_style=getattr(provider, "api_style", None),
            base_url=getattr(provider, "base_url", None),
            request_model=getattr(provider, "request_model", request_model),
            response_model=getattr(provider, "response_model", None),
            generation=config.generation.model_dump(mode="json"),
            accessed_at=getattr(provider, "accessed_at", None),
        ),),
        prompts=(PromptSnapshot(prompt_id=PROMPT_ID, version=PROMPT_VERSION, content_hash=content_hash()),),
        started_at=started, finished_at=utcnow(), notes=("Silver data are for engineering validation only.",
            "Git was intentionally not initialized; code_tree_sha256 records local code identity.",
            "No final QA answer or formal metrics were produced."))
    _write_json(paths["manifest"], manifest)
    return run_dir


def _dedupe_refs(refs):
    result, seen = [], set()
    for ref in refs:
        key = (ref.evidence_id, ref.context_ref.key)
        if key not in seen:
            seen.add(key); result.append(ref)
    return tuple(result)
