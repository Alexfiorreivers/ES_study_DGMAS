"""Evaluation-ready runtime DAG validation and deterministic input replay."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from hashlib import sha256
from typing import Iterable

from agent_lab.domain.contracts_v0_1 import (
    AssignmentSnapshot,
    AtomicClaim,
    DependencyKind,
    DependencyRecord,
    MessageStatus,
    PlatformInputBundle,
    ProviderMessage,
    RuntimeMessageNode,
    RuntimeNodeKind,
    StructuredPayload,
)
from agent_lab.prompts import (
    PROMPT_VERSION, communication_user_content, initial_user_content, system_prompt_for_version,
)


class EvaluationTraceValidationError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> None:
    raise EvaluationTraceValidationError(code, detail)


def canonical_messages_sha256(messages: Iterable[ProviderMessage]) -> str:
    material = json.dumps(
        [message.model_dump(mode="json") for message in messages],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(material.encode("utf-8")).hexdigest()


def _payload_claims(node: RuntimeMessageNode) -> tuple[AtomicClaim, ...]:
    return node.payload.claims if isinstance(node.payload, StructuredPayload) else ()


def _dependency_sort_key(record: DependencyRecord, nodes: dict[str, RuntimeMessageNode]):
    parent = nodes[record.parent_node_id]
    return (
        0 if record.dependency_kind is DependencyKind.SELF_INITIAL else 1,
        parent.round,
        parent.sender_id,
        parent.receiver_id,
        parent.node_id,
    )


def initial_messages(bundle: PlatformInputBundle, visible_document_refs,
                     prompt_version: str = PROMPT_VERSION) -> tuple[ProviderMessage, ...]:
    wanted = {(ref.sample_id, ref.context_index) for ref in visible_document_refs}
    documents = tuple(
        document for document in bundle.documents
        if (document.sample_id, document.context_index) in wanted
    )
    rendered_documents = []
    for document in documents:
        context_ref = {"sample_id": document.sample_id, "context_index": document.context_index}
        citation = {
            "evidence_id": f"evidence-{document.context_index}-0",
            "context_ref": context_ref,
            "granularity": "sentence" if document.sentences else "paragraph",
            "reference_origin": "local_document",
        }
        if document.sentences:
            first_index = document.sentences[0].sentence_index
            citation["evidence_id"] = f"evidence-{document.context_index}-{first_index}"
            citation["sentence_ids"] = [first_index]
            body = "\n".join(
                f"[sentence_index={sentence.sentence_index}] {sentence.text}"
                for sentence in document.sentences
            )
        else:
            citation["paragraph_idx"] = 0
            body = f"[paragraph_idx=0] {document.text}"
        rendered_documents.append(
            f"[context_ref={json.dumps(context_ref, ensure_ascii=False, separators=(',', ':'))}; "
            f"title={document.title}]\n"
            f"Citation template: {json.dumps(citation, ensure_ascii=False, separators=(',', ':'))}\n"
            f"{body}"
        )
    rendered = "\n\n".join(rendered_documents)
    return (
        ProviderMessage(role="system", content=system_prompt_for_version(prompt_version)),
        ProviderMessage(role="user", content=initial_user_content(bundle.question.text, rendered,
                                                                   prompt_version)),
    )


def communication_visible_input(
    bundle: PlatformInputBundle,
    child_node_id: str,
    nodes: Iterable[RuntimeMessageNode],
    dependencies: Iterable[DependencyRecord],
    prompt_version: str = PROMPT_VERSION,
) -> tuple[tuple[ProviderMessage, ...], tuple[AtomicClaim, ...], tuple[str, ...]]:
    node_by_id = {node.node_id: node for node in nodes}
    child_dependencies = [record for record in dependencies if record.child_node_id == child_node_id]
    child_dependencies.sort(key=lambda record: _dependency_sort_key(record, node_by_id))
    parent_views: list[dict] = []
    visible_claims: list[AtomicClaim] = []
    parent_ids: list[str] = []
    for record in child_dependencies:
        parent = node_by_id[record.parent_node_id]
        claims_by_id = {claim.claim_id: claim for claim in _payload_claims(parent)}
        claims = tuple(claims_by_id[claim_id] for claim_id in record.visible_claim_ids)
        visible_claims.extend(claims)
        parent_ids.append(parent.node_id)
        parent_views.append({
            "parent_node_id": parent.node_id,
            "node_kind": parent.node_kind.value,
            "sender_id": parent.sender_id,
            "receiver_id": parent.receiver_id,
            "round": parent.round,
            "message_status": parent.payload.message_status.value,
            "claims": [claim.model_dump(mode="json") for claim in claims],
            "text": getattr(parent.payload, "text", None),
        })
    messages = (
        ProviderMessage(role="system", content=system_prompt_for_version(prompt_version)),
        ProviderMessage(role="user", content=communication_user_content(bundle.question.text, parent_views,
                                                                          prompt_version)),
    )
    return messages, tuple(visible_claims), tuple(parent_ids)


def reconstruct_request_messages(
    node: RuntimeMessageNode,
    nodes: Iterable[RuntimeMessageNode],
    dependencies: Iterable[DependencyRecord],
    bundle: PlatformInputBundle,
    assignment: AssignmentSnapshot,
    prompt_version: str = PROMPT_VERSION,
) -> tuple[ProviderMessage, ...]:
    if node.node_kind is RuntimeNodeKind.INITIAL_OUTPUT:
        expected = tuple(assignment.assignments[node.sender_id])
        if tuple(node.visible_document_refs) != expected:
            _fail("VISIBLE_DOCUMENT_MISMATCH", f"{node.node_id} document refs differ from its frozen assignment")
        return initial_messages(bundle, node.visible_document_refs, prompt_version)
    messages, _, _ = communication_visible_input(bundle, node.node_id, nodes, dependencies,
                                                  prompt_version)
    return messages


def validate_evaluation_trace(
    nodes: Iterable[RuntimeMessageNode], dependencies: Iterable[DependencyRecord]
) -> None:
    nodes = tuple(nodes)
    dependencies = tuple(dependencies)
    node_ids = [node.node_id for node in nodes]
    if len(node_ids) != len(set(node_ids)):
        _fail("DUPLICATE_NODE_ID", "RuntimeMessageNode IDs must be unique")
    request_ids = [node.request_id for node in nodes]
    response_ids = [node.response_id for node in nodes]
    if len(request_ids) != len(set(request_ids)) or len(response_ids) != len(set(response_ids)):
        _fail("MODEL_NODE_CARDINALITY", "request_id and response_id must map one-to-one onto nodes")
    dep_ids = [record.dependency_id for record in dependencies]
    if len(dep_ids) != len(set(dep_ids)):
        _fail("DUPLICATE_DEPENDENCY_ID", "DependencyRecord IDs must be unique")
    node_by_id = {node.node_id: node for node in nodes}
    incoming: dict[str, list[DependencyRecord]] = defaultdict(list)
    graph: dict[str, set[str]] = {node_id: set() for node_id in node_by_id}
    indegree = {node_id: 0 for node_id in node_by_id}
    seen_pairs: set[tuple[str, str]] = set()
    for record in dependencies:
        parent = node_by_id.get(record.parent_node_id)
        child = node_by_id.get(record.child_node_id)
        if parent is None or child is None:
            _fail("DEPENDENCY_FOREIGN_KEY", f"{record.dependency_id} references a missing node")
        pending = [child.node_id]
        reachable: set[str] = set()
        while pending:
            current = pending.pop()
            if current in reachable:
                continue
            reachable.add(current)
            pending.extend(graph[current])
        if parent.node_id in reachable:
            _fail("DEPENDENCY_CYCLE", f"{record.dependency_id} closes a directed cycle")
        if record.run_id != parent.run_id or record.run_id != child.run_id:
            _fail("DEPENDENCY_CROSS_RUN", f"{record.dependency_id} crosses run boundaries")
        if record.question_id != parent.question_id or record.question_id != child.question_id:
            _fail("DEPENDENCY_CROSS_QUESTION", f"{record.dependency_id} crosses question boundaries")
        if record.parent_round != parent.round or record.child_round != child.round:
            _fail("DEPENDENCY_ROUND_MISMATCH", f"{record.dependency_id} round metadata is inconsistent")
        if parent.round >= child.round:
            _fail("DEPENDENCY_NON_CAUSAL", f"{record.dependency_id} is same-round or future-round")
        if child.node_kind is not RuntimeNodeKind.COMMUNICATION_OUTPUT:
            _fail("INITIAL_NODE_HAS_PARENT", f"initial node {child.node_id} cannot have dependencies")
        parent_claim_ids = {claim.claim_id for claim in _payload_claims(parent)}
        missing_claims = set(record.visible_claim_ids) - parent_claim_ids
        if missing_claims:
            _fail("VISIBLE_CLAIM_FOREIGN_KEY", f"{record.dependency_id} contains claims absent from parent: {sorted(missing_claims)}")
        if record.dependency_kind is DependencyKind.SELF_INITIAL:
            if parent.node_kind is not RuntimeNodeKind.INITIAL_OUTPUT or parent.sender_id != child.sender_id:
                _fail("SELF_INITIAL_INVALID", f"{record.dependency_id} is not the sender's initial node")
        else:
            if parent.node_kind is not RuntimeNodeKind.COMMUNICATION_OUTPUT:
                _fail("RECEIVED_MESSAGE_INVALID", f"{record.dependency_id} parent is not a communication node")
            if parent.receiver_id != child.sender_id or parent.round != child.round - 1:
                _fail("FROZEN_MAILBOX_VIOLATION", f"{record.dependency_id} was not delivered in the preceding round")
        pair = (parent.node_id, child.node_id)
        if pair in seen_pairs:
            _fail("DUPLICATE_DEPENDENCY_EDGE", f"duplicate dependency edge {pair}")
        seen_pairs.add(pair)
        incoming[child.node_id].append(record)
        graph[parent.node_id].add(child.node_id)
        indegree[child.node_id] += 1
    for node in nodes:
        records = incoming.get(node.node_id, [])
        if node.node_kind is RuntimeNodeKind.INITIAL_OUTPUT and records:
            _fail("INITIAL_NODE_HAS_PARENT", f"initial node {node.node_id} has incoming dependencies")
        if node.node_kind is RuntimeNodeKind.COMMUNICATION_OUTPUT:
            self_initial = [record for record in records if record.dependency_kind is DependencyKind.SELF_INITIAL]
            if len(self_initial) != 1:
                _fail("SELF_INITIAL_MISSING", f"communication node {node.node_id} requires exactly one self_initial dependency")
    queue = deque(sorted(node_id for node_id, value in indegree.items() if value == 0))
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for child in sorted(graph[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if visited != len(nodes):
        _fail("DEPENDENCY_CYCLE", "dependency graph contains a directed cycle")


def validate_reconstructability(
    nodes: Iterable[RuntimeMessageNode],
    dependencies: Iterable[DependencyRecord],
    bundles: Iterable[PlatformInputBundle],
    assignments: Iterable[AssignmentSnapshot],
    prompt_version: str = PROMPT_VERSION,
) -> None:
    nodes = tuple(nodes)
    dependencies = tuple(dependencies)
    validate_evaluation_trace(nodes, dependencies)
    bundle_by_id = {bundle.question.question_id: bundle for bundle in bundles}
    assignment_by_id = {assignment.question_id: assignment for assignment in assignments}
    for node in nodes:
        bundle = bundle_by_id.get(node.question_id)
        assignment = assignment_by_id.get(node.question_id)
        if bundle is None or assignment is None:
            _fail("REPLAY_INPUT_MISSING", f"missing persisted input or assignment for {node.question_id}")
        messages = reconstruct_request_messages(node, nodes, dependencies, bundle, assignment,
                                                prompt_version)
        actual_hash = canonical_messages_sha256(messages)
        if actual_hash != node.visible_input_sha256:
            _fail("VISIBLE_INPUT_HASH_MISMATCH", f"reconstructed input differs for {node.node_id}")
