"""M3-A condition semantics layered on the accepted M1 reliable runner."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from agent_lab.domain.contracts_v0_1 import (
    AgentStateSnapshot, AggregatedClaim, AggregatedResult, AssignmentSnapshot, AtomicClaim,
    DependencyKind, DependencyRecord, ExperimentConfig, MessageFormat, ModelRequest,
    QuestionCheckpoint, QuestionRunStatus, RuntimeMessageNode, RuntimeNodeKind, Stage,
    StructuredPayload, TraceEventType,
)
from agent_lab.evaluation_trace import canonical_messages_sha256
from agent_lab.m3_prompts import ResolvedPromptSet, canonical_hash, render_communication, render_initial
from agent_lab.topology import directed_edges


DATASET_HASHES = {
    "2wiki-audit-gold-400": "d6e2e051da9e02ed0c0929f25872964d4a3ff13a2c1ba8f517cd8e2d10421340",
    "musique-final-gold-167": "c6f3f1b3eeb4e954d14f900747e1aaeb176512b8ba70d0ab3ab94d2cfdd2d4b5",
}
# Publication-only English inputs are allowed for offline development examples.
# Historical/formal runs retain the original frozen identity checks above.
ENGLISH_LOCALIZED_DATASET_HASHES = {
    "2wiki-audit-gold-400": "7092d80012861b6a333ad78c54fc32fc3b5fa1ed96e5f71fd4bb5c7241dc2c84",
    "musique-final-gold-167": "c9b641e9483c8677bfa2c3f8d79543c32ddb920d72fb4ccaec1de2793ec8a067",
}
PROMPT_REFS = {
    "M": frozenset({"m3-M@1.0.0", "m3-M@1.0.1", "m3-M@1.0.1c", "m3-M@1.0.1c-r2", "m3-M@1.0.2", "m3-M@1.0.3", "m3-M@1.0.4"}),
    "B0": frozenset({"m3-B0@1.0.0", "m3-B0@1.0.3", "m3-B0@1.0.4"}),
    "B1": frozenset({"m3-B1@1.0.0", "m3-B1@1.0.3", "m3-B1@1.0.4"}),
    "A1": frozenset({"m3-A1@1.0.0", "m3-A1@1.0.3", "m3-A1@1.0.4"}),
    "A2": frozenset({"m3-A2@1.0.0", "m3-A2@1.0.3", "m3-A2@1.0.4"}),
}


def expected_calls_per_question(config: ExperimentConfig) -> int:
    condition = config.m3_condition
    if condition is None:
        raise ValueError("m3_condition is required")
    if condition.condition_id == "B0":
        return 1
    if condition.condition_id == "B1":
        return 3
    return 3 + len(directed_edges(config.topology.kind, config.topology.center_agent_id))


def validate_condition_contract(config: ExperimentConfig, prompt: ResolvedPromptSet) -> dict[str, Any]:
    condition = config.m3_condition
    if condition is None:
        raise ValueError("M3_CONDITION_MISSING")
    failures: list[str] = []
    prefix, _, declared_hash = condition.dataset_id.partition("@sha256:")
    expected_hash = DATASET_HASHES.get(prefix)
    if "@english-localized:sha256:" in condition.dataset_id:
        prefix, _, declared_hash = condition.dataset_id.partition("@english-localized:sha256:")
        expected_hash = ENGLISH_LOCALIZED_DATASET_HASHES.get(prefix)
        if condition.run_intent != "development" or config.provider.kind != "lineage_replay_mock":
            failures.append("ENGLISH_LOCALIZED_INPUT_REQUIRES_DEVELOPMENT_MOCK")
    if expected_hash is None or declared_hash != expected_hash or config.dataset.expected_sha256 != expected_hash:
        failures.append("DATASET_IDENTITY_MISMATCH")
    if condition.prompt_ref not in PROMPT_REFS[condition.condition_id]:
        failures.append("PROMPT_REF_NOT_FROZEN_FOR_CONDITION")
    if prompt.condition_id != condition.condition_id:
        failures.append("PROMPT_CONDITION_MISMATCH")
    if condition.condition_id in {"A1", "A2"} and prefix != "2wiki-audit-gold-400":
        failures.append("ABLATION_DATASET_FORBIDDEN")
    if prefix == "2wiki-audit-gold-400":
        if config.document_assignment.policy != "gold_partition_minimal_v2" or config.document_assignment.rule_version != "2.0.0":
            failures.append("2WIKI_ASSIGNMENT_POLICY_CHANGED")
    if prefix == "musique-final-gold-167":
        if (config.document_assignment.policy != "gold_decomposition_step_partition_musique_v2" or
                config.document_assignment.rule_version != "2.0.0" or
                config.document_assignment.include_distractors is not False):
            failures.append("MUSIQUE_GOLD_ONLY_POLICY_CHANGED")
    expected_model = getattr(config.provider, "model", None)
    if expected_model is None:
        expected_model = f"lineage-replay-mock@{getattr(config.provider, 'version', '')}"
    if condition.model_id != expected_model:
        failures.append("MODEL_ID_MISMATCH")
    expected_projection = "hide-source-refs@1.0.0" if condition.condition_id == "A1" else "identity@1.0.0"
    if condition.parent_projection_ref != expected_projection:
        failures.append("PROJECTION_NOT_FROZEN_FOR_CONDITION")
    if failures:
        raise ValueError("M3_UNIQUE_DIFFERENCE_VIOLATION: " + ",".join(failures))
    allowed = {
        "M": [], "B0": ["execution_mode", "initial_task", "terminal_node_set"],
        "B1": ["communication_rounds", "terminal_node_set"],
        "A1": ["parent_projection"], "A2": ["source_maintenance_prompt_lines"],
    }[condition.condition_id]
    material = {
        "condition_id": condition.condition_id, "allowed_differences_from_M": allowed,
        "model_id": condition.model_id, "dataset_id": condition.dataset_id,
        "replicate_id": condition.replicate_id, "prompt_ref": condition.prompt_ref,
        "prompt_set_hash": prompt.prompt_set_hash, "assignment_policy": config.document_assignment.policy,
        "assignment_version": config.document_assignment.rule_version,
        "terminal_union_ref": condition.terminal_union_ref,
        "parent_projection_ref": condition.parent_projection_ref,
        "communication_rounds": config.protocol.communication_rounds,
        "expected_calls_per_question": expected_calls_per_question(config),
    }
    return {**material, "contract_sha256": canonical_hash(material), "status": "passed"}


def validate_condition_matrix(configs: list[ExperimentConfig]) -> dict[str, Any]:
    """Reject any cross-condition change outside the preregistered dimensions."""
    groups: dict[tuple[str, str], list[ExperimentConfig]] = {}
    for config in configs:
        if config.m3_condition is None:
            raise ValueError("M3_CONDITION_MISSING")
        groups.setdefault((config.m3_condition.model_id, config.m3_condition.dataset_id), []).append(config)
    results = []
    for (model_id, dataset_id), values in groups.items():
        by_condition = {config.m3_condition.condition_id: config for config in values}
        required = {"M", "B0", "B1"} | ({"A1", "A2"} if dataset_id.startswith("2wiki-") else set())
        if set(by_condition) != required:
            raise ValueError(f"M3_MATRIX_INCOMPLETE:{dataset_id}")
        baseline = by_condition["M"]
        def invariant(config: ExperimentConfig) -> dict[str, Any]:
            return {
                "dataset": config.dataset.model_dump(mode="json"), "gates": config.gates.model_dump(mode="json"),
                "document_assignment": config.document_assignment.model_dump(mode="json"),
                "agents": [item.model_dump(mode="json") for item in config.agents],
                "topology": config.topology.model_dump(mode="json"),
                "provider": config.provider.model_dump(mode="json"),
                "generation": config.generation.model_dump(mode="json"),
                "aggregation": config.aggregation.model_dump(mode="json"),
                "random_seed": config.randomness.seed, "runs_dir": config.output.runs_dir,
                "protocol_common": {"profile": config.protocol.profile,
                    "initial_read_round": config.protocol.initial_read_round,
                    "frozen_mailbox": config.protocol.frozen_mailbox,
                    "raw_documents_after_initial_read": config.protocol.raw_documents_after_initial_read,
                    "message_format": config.protocol.message_format.value},
                "registry": config.m3_condition.prompt_registry.model_dump(mode="json"),
                "terminal_union_ref": config.m3_condition.terminal_union_ref,
                "replicate_id": config.m3_condition.replicate_id,
            }
        expected = invariant(baseline)
        for condition_id, config in by_condition.items():
            if invariant(config) != expected:
                raise ValueError(f"M3_UNPLANNED_MATRIX_DIFFERENCE:{dataset_id}:{condition_id}")
        result = {"model_id": model_id, "dataset_id": dataset_id,
                  "conditions": sorted(by_condition), "invariant_sha256": canonical_hash(expected),
                  "status": "passed"}
        results.append(result)
    return {"status": "passed", "groups": results,
            "matrix_sha256": canonical_hash(results)}


def _render_documents(bundle, refs) -> str:
    wanted = {(ref.sample_id, ref.context_index) for ref in refs}
    blocks = []
    for document in sorted(bundle.documents, key=lambda item: item.context_index):
        if (document.sample_id, document.context_index) not in wanted:
            continue
        context_ref = {"sample_id": document.sample_id, "context_index": document.context_index}
        if document.sentences:
            first = document.sentences[0].sentence_index
            citation = {"evidence_id": f"evidence-{document.context_index}-{first}",
                        "context_ref": context_ref, "granularity": "sentence",
                        "sentence_ids": [first], "reference_origin": "local_document"}
            body = "\n".join(f"[sentence_index={s.sentence_index}] {s.text}" for s in document.sentences)
        else:
            citation = {"evidence_id": f"evidence-{document.context_index}-0",
                        "context_ref": context_ref, "granularity": "paragraph", "paragraph_idx": 0,
                        "reference_origin": "local_document"}
            body = f"[paragraph_idx=0] {document.text}"
        blocks.append(f"[context_ref={json.dumps(context_ref, ensure_ascii=False, separators=(',', ':'))}; title={document.title}]\n"
                      f"Citation template: {json.dumps(citation, ensure_ascii=False, separators=(',', ':'))}\n{body}")
    return "\n\n".join(blocks)


def _project_claim(claim: AtomicClaim, hide_sources: bool) -> AtomicClaim:
    return claim.model_copy(update={"source_refs": ()}) if hide_sources else claim


def _terminal_union(run_id: str, qid: str, nodes: list[RuntimeMessageNode], condition_id: str,
                    aggregator_version: str, now) -> tuple[AggregatedResult, tuple[dict[str, Any], ...]]:
    if condition_id in {"M", "A1", "A2"}:
        terminal = [node for node in nodes if node.node_kind is RuntimeNodeKind.COMMUNICATION_OUTPUT and node.round == 1]
    else:
        terminal = list(nodes)
    occurrences: list[dict[str, Any]] = []
    grouped: dict[str, list[tuple[RuntimeMessageNode, AtomicClaim]]] = {}
    for node in terminal:
        assert isinstance(node.payload, StructuredPayload)
        for claim in node.payload.claims:
            source_material = sorted((ref.model_dump(mode="json") for ref in claim.source_refs),
                                     key=lambda value: canonical_hash(value))
            signature_material = {"normalized_claim_text": " ".join(claim.claim_text.casefold().split()),
                                  "source_refs": source_material, "qualification": claim.qualification,
                                  "message_status": node.payload.message_status.value}
            signature = canonical_hash(signature_material)
            grouped.setdefault(signature, []).append((node, claim))
            occurrences.append({"question_id": qid, "terminal_node_id": node.node_id,
                                "agent_id": node.sender_id, "round": node.round,
                                "claim_id": claim.claim_id, "occurrence_signature": signature,
                                "claim": claim.model_dump(mode="json")})
    claims = []
    for signature, items in sorted(grouped.items()):
        first = items[0][1]
        claims.append(AggregatedClaim(normalized_text=" ".join(first.claim_text.casefold().split()),
            claim_text=first.claim_text, source_refs=first.source_refs,
            contributing_claim_ids=tuple(sorted({claim.claim_id for _, claim in items})),
            contributing_agent_ids=tuple(sorted({node.sender_id for node, _ in items}))))
    result = AggregatedResult(run_id=run_id, question_id=qid, message_format=MessageFormat.STRUCTURED,
                              claims=tuple(claims), aggregator_version=aggregator_version, created_at=now())
    return result, tuple(occurrences)


def build_question_artifacts(bundle, assignment: AssignmentSnapshot, config: ExperimentConfig,
                             provider, request_model: str, run_id: str, trace, attempts,
                             prompt: ResolvedPromptSet) -> QuestionCheckpoint:
    from agent_lab.runtime import (_available_claims, _canonical_payload, _claims_from_node,
                                   _message_from_node, stable_id)
    from agent_lab.reliability import _utcnow
    condition = config.m3_condition
    assert condition is not None
    qid = bundle.question.question_id
    nodes: list[RuntimeMessageNode] = []
    dependencies: list[DependencyRecord] = []
    messages = []
    machine_claims: dict[str, tuple[AtomicClaim, ...]] = {}
    reconstructions: list[dict[str, Any]] = []
    projections: list[dict[str, Any]] = []
    initial_nodes: dict[str, RuntimeMessageNode] = {}
    trace.emit(TraceEventType.QUESTION_STARTED, question_id=qid)
    trace.emit(TraceEventType.DOCUMENT_ASSIGNMENT_FROZEN, question_id=qid,
               event_data=assignment.model_dump(mode="json"))
    initial_specs = list(config.agents)
    if condition.condition_id == "B0":
        initial_specs = [type("CentralSpec", (), {"agent_id": "centralized_reader"})()]
    for spec in initial_specs:
        if condition.condition_id == "B0":
            unique = {ref.key: ref for refs in assignment.assignments.values() for ref in refs}
            visible_refs = tuple(sorted(unique.values(), key=lambda ref: ref.key))
        else:
            visible_refs = tuple(assignment.assignments[spec.agent_id])
        indexes = {ref.context_index for ref in visible_refs}
        local = _available_claims(bundle, indexes)
        request_messages = render_initial(prompt, bundle.question.text, _render_documents(bundle, visible_refs))
        request_id = stable_id("req", run_id, qid, spec.agent_id, 0)
        request = ModelRequest(request_id=request_id, provider_ref=provider.provider_ref, model=request_model,
            messages=request_messages, output_format=MessageFormat.STRUCTURED, output_schema_version="0.1",
            prompt_id=prompt.registry_id, prompt_version=prompt.registry_version,
            prompt_content_hash=prompt.prompt_set_hash, run_id=run_id, question_id=qid,
            agent_id=spec.agent_id, stage=Stage.INITIAL_READ, round=0, receiver_id=spec.agent_id,
            replicate_id=condition.replicate_id,
            request_context={"local_documents": [d.model_dump(mode="json") for d in bundle.documents
                                                  if d.context_index in indexes],
                             "local_claims": [c.model_dump(mode="json") for c in local],
                             "visible_document_refs": [ref.model_dump(mode="json") for ref in visible_refs],
                             "condition_id": condition.condition_id})
        response = attempts.complete(request)
        node_id = stable_id("node", request_id)
        payload, canonical_claims = _canonical_payload(response, MessageFormat.STRUCTURED, node_id, 0)
        node = RuntimeMessageNode(node_id=node_id, node_kind=RuntimeNodeKind.INITIAL_OUTPUT,
            run_id=run_id, question_id=qid, sender_id=spec.agent_id, receiver_id=spec.agent_id,
            stage=Stage.INITIAL_READ, round=0, communication_hop=0, visible_document_refs=visible_refs,
            payload=payload, request_id=request_id, response_id=response.response_id,
            prompt_ref=prompt.prompt_ref, model_ref=provider.provider_ref,
            visible_input_sha256=canonical_messages_sha256(request_messages), created_at=_utcnow())
        nodes.append(node); initial_nodes[spec.agent_id] = node; machine_claims[node_id] = canonical_claims
        reconstructions.append({"request_id": request_id, "node_id": node_id, "condition_id": condition.condition_id,
            "prompt_ref": prompt.prompt_ref, "prompt_set_hash": prompt.prompt_set_hash,
            "messages": [m.model_dump(mode="json") for m in request_messages],
            "messages_sha256": canonical_messages_sha256(request_messages),
            "visible_document_refs": [ref.model_dump(mode="json") for ref in visible_refs],
            "parent_projection_ref": condition.parent_projection_ref})
        trace.emit(TraceEventType.MESSAGE_NODE_CREATED, question_id=qid, stage=Stage.INITIAL_READ, round=0,
                   agent_id=spec.agent_id, event_data={"node_id": node_id, "request_id": request_id})
    if condition.condition_id not in {"B0", "B1"}:
        for sender, receiver in directed_edges(config.topology.kind, config.topology.center_agent_id):
            request_id = stable_id("req", run_id, qid, 1, sender, receiver)
            node_id = stable_id("node", request_id)
            parent_nodes = (initial_nodes[sender],)
            deps = tuple(DependencyRecord(dependency_id=stable_id("dep", parent.node_id, node_id, "self_initial"),
                run_id=run_id, question_id=qid, parent_node_id=parent.node_id, child_node_id=node_id,
                dependency_kind=DependencyKind.SELF_INITIAL, parent_round=0, child_round=1,
                visible_claim_ids=tuple(claim.claim_id for claim in parent.payload.claims)) for parent in parent_nodes)
            hide = condition.condition_id == "A1"
            parent_views = []
            visible_claims = []
            for parent in parent_nodes:
                before = [claim.model_dump(mode="json") for claim in parent.payload.claims]
                projected = [_project_claim(claim, hide) for claim in parent.payload.claims]
                after = [claim.model_dump(mode="json") for claim in projected]
                parent_view = {"parent_node_id": parent.node_id, "node_kind": parent.node_kind.value,
                    "sender_id": parent.sender_id, "receiver_id": parent.receiver_id, "round": parent.round,
                    "message_status": parent.payload.message_status.value, "claims": after, "text": None}
                parent_views.append(parent_view); visible_claims.extend(projected)
                projections.append({"question_id": qid, "child_node_id": node_id,
                    "parent_node_id": parent.node_id, "projection_ref": condition.parent_projection_ref,
                    "before_sha256": canonical_hash(before), "after_sha256": canonical_hash(after),
                    "projected_view_sha256": canonical_hash(parent_view),
                    "changed_fields": ["claims[].source_refs"] if hide else [], "projected_view": parent_view})
            request_messages = render_communication(prompt, bundle.question.text, parent_views)
            request = ModelRequest(request_id=request_id, provider_ref=provider.provider_ref, model=request_model,
                messages=request_messages, output_format=MessageFormat.STRUCTURED, output_schema_version="0.1",
                prompt_id=prompt.registry_id, prompt_version=prompt.registry_version,
                prompt_content_hash=prompt.prompt_set_hash, run_id=run_id, question_id=qid, agent_id=sender,
                stage=Stage.COMMUNICATION, round=1, receiver_id=receiver,
                replicate_id=condition.replicate_id,
                request_context={"incoming_claims": [claim.model_dump(mode="json") for claim in visible_claims],
                                 "visible_parent_node_ids": [parent.node_id for parent in parent_nodes],
                                 "raw_documents_supplied": False, "condition_id": condition.condition_id})
            response = attempts.complete(request)
            payload, canonical_claims = _canonical_payload(response, MessageFormat.STRUCTURED, node_id, 1)
            node = RuntimeMessageNode(node_id=node_id, node_kind=RuntimeNodeKind.COMMUNICATION_OUTPUT,
                run_id=run_id, question_id=qid, sender_id=sender, receiver_id=receiver,
                stage=Stage.COMMUNICATION, round=1, communication_hop=1, visible_document_refs=(), payload=payload,
                request_id=request_id, response_id=response.response_id, prompt_ref=prompt.prompt_ref,
                model_ref=provider.provider_ref, visible_input_sha256=canonical_messages_sha256(request_messages),
                created_at=_utcnow())
            nodes.append(node); dependencies.extend(deps); machine_claims[node_id] = canonical_claims
            messages.append(_message_from_node(node, parent_nodes, canonical_claims))
            reconstructions.append({"request_id": request_id, "node_id": node_id,
                "condition_id": condition.condition_id, "prompt_ref": prompt.prompt_ref,
                "prompt_set_hash": prompt.prompt_set_hash,
                "messages": [m.model_dump(mode="json") for m in request_messages],
                "messages_sha256": canonical_messages_sha256(request_messages), "visible_document_refs": [],
                "parent_projection_ref": condition.parent_projection_ref,
                "parent_view_hashes": [canonical_hash(view) for view in parent_views]})
            trace.emit(TraceEventType.MESSAGE_NODE_CREATED, question_id=qid, stage=Stage.COMMUNICATION,
                       round=1, agent_id=sender, event_data={"node_id": node_id, "request_id": request_id})
    result, observations = _terminal_union(run_id, qid, nodes, condition.condition_id,
                                           config.aggregation.version, _utcnow)
    states = []
    terminal_ids = {obs["terminal_node_id"] for obs in observations}
    for agent_id in sorted({node.sender_id for node in nodes}):
        owned = [node for node in nodes if node.sender_id == agent_id]
        terminal_claims = tuple(claim for node in owned if node.node_id in terminal_ids
                                for claim in _claims_from_node(node, machine_claims))
        initial_claims = tuple(claim for node in owned if node.node_kind is RuntimeNodeKind.INITIAL_OUTPUT
                               for claim in _claims_from_node(node, machine_claims))
        states.append(AgentStateSnapshot(run_id=run_id, question_id=qid, agent_id=agent_id,
            round=config.protocol.communication_rounds, message_format=MessageFormat.STRUCTURED,
            private_initial_claims=initial_claims, current_structured_claims=terminal_claims,
            created_at=_utcnow()))
    trace.emit(TraceEventType.AGGREGATION_COMPLETED, question_id=qid, stage=Stage.AGGREGATION,
               event_data={"candidate_claim_count": len(result.claims), "terminal_nodes": len(terminal_ids),
                           "final_answer_generated": False})
    trace.emit(TraceEventType.QUESTION_FINISHED, question_id=qid)
    return QuestionCheckpoint(run_id=run_id, question_id=qid, status=QuestionRunStatus.COMPLETED,
        attempt_count=attempts.state.questions[qid].attempt_count, assignment=assignment,
        nodes=tuple(nodes), dependencies=tuple(dependencies), messages=tuple(messages),
        agent_states=tuple(states), aggregated_result=result,
        request_reconstructions=tuple(reconstructions), parent_projections=tuple(projections),
        terminal_observations=observations, created_at=_utcnow())
