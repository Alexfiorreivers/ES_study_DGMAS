"""Frozen deterministic document-assignment policies."""

from __future__ import annotations

from hashlib import sha256

from agent_lab.domain.contracts_v0_1 import AssignmentSnapshot, ContextRef, PlatformInputBundle


class AmbiguousGoldPartition(ValueError):
    pass


def _ordered(values: set[int], seed: int, sample_id: str) -> list[int]:
    return sorted(values, key=lambda index: sha256(f"{seed}:{sample_id}:{index}".encode()).hexdigest())


def _claim_contexts(claim) -> set[int]:
    return {ref.context_ref.context_index for ref in claim.source_refs}


def _graph_partition(bundle: PlatformInputBundle, supporting: set[int]):
    graph = bundle.truth_reasoning_graph
    roots = list(graph.get("root_claim_ids", []))
    if len(roots) != 2:
        raise AmbiguousGoldPartition("gold branch partition is not uniquely defined")
    claim_by_truth = {claim.truth_claim_id: claim for claim in bundle.seed_claims}
    if set(roots) - set(claim_by_truth):
        raise AmbiguousGoldPartition("gold branch root references an unknown claim")

    def ancestors(node: str) -> set[str]:
        result = {node}
        changed = True
        while changed:
            changed = False
            for edge in graph.get("edges", []):
                if edge["to_claim_id"] in result:
                    before = len(result)
                    result.add(edge["from_claim_id"])
                    changed |= len(result) != before
        return result

    branch_nodes = [ancestors(node) for node in roots]
    if branch_nodes[0] & branch_nodes[1] or set().union(*branch_nodes) != set(claim_by_truth):
        raise AmbiguousGoldPartition("gold branch claims are overlapping or incomplete")
    contexts = [
        {index for node in nodes for index in _claim_contexts(claim_by_truth[node])}
        for nodes in branch_nodes
    ]
    left, right = contexts
    if not left or not right or left & right or left | right != supporting:
        raise AmbiguousGoldPartition("gold branch contexts are overlapping or incomplete")
    return left, right, tuple(tuple(sorted(nodes)) for nodes in branch_nodes)


def _structured_qid_partition(bundle: PlatformInputBundle, supporting: set[int]):
    if bundle.question.question_type != "bridge_comparison" or len(bundle.seed_claims) != 4:
        raise AmbiguousGoldPartition("structured QID fallback requires a four-claim bridge_comparison")
    claim_by_truth = {claim.truth_claim_id: claim for claim in bundle.seed_claims}
    if None in claim_by_truth or len(claim_by_truth) != 4:
        raise AmbiguousGoldPartition("structured QID fallback requires four unique truth claim IDs")

    forms = {}
    for claim_id, claim in claim_by_truth.items():
        form = claim.metadata.get("structured_form")
        if not isinstance(form, dict) or not form.get("subject_qid") or not form.get("object_qid"):
            raise AmbiguousGoldPartition("structured QID fallback requires nonempty subject_qid and object_qid")
        forms[claim_id] = form
    candidates = sorted(
        (source, target)
        for source, source_form in forms.items()
        for target, target_form in forms.items()
        if source != target and source_form["object_qid"] == target_form["subject_qid"]
    )
    flattened = [claim_id for edge in candidates for claim_id in edge]
    if len(candidates) != 2 or len(flattened) != 4 or set(flattened) != set(claim_by_truth):
        raise AmbiguousGoldPartition("structured QID chains do not uniquely partition all four claims")

    graph_edges = {
        (str(edge["from_claim_id"]), str(edge["to_claim_id"]))
        for edge in bundle.truth_reasoning_graph.get("edges", [])
        if edge.get("edge_type") == "inference"
    }
    all_recorded_edges = {
        (str(edge["from_claim_id"]), str(edge["to_claim_id"]))
        for edge in bundle.truth_reasoning_graph.get("edges", [])
    }
    inferred = set(candidates)
    if all_recorded_edges != graph_edges or not graph_edges <= inferred:
        raise AmbiguousGoldPartition("recorded reasoning edges contradict structured QID chains")

    branches = tuple(tuple(edge) for edge in candidates)
    contexts = [
        {index for claim_id in branch for index in _claim_contexts(claim_by_truth[claim_id])}
        for branch in branches
    ]
    left, right = contexts
    if not left or not right or left & right or left | right != supporting:
        raise AmbiguousGoldPartition("structured QID branch contexts are overlapping or incomplete")
    missing = tuple(edge for edge in branches if edge not in graph_edges)
    return left, right, branches, missing


def assign_documents(bundle: PlatformInputBundle, policy: str, rule_version: str, seed: int) -> AssignmentSnapshot:
    all_indexes = {d.context_index for d in bundle.documents}
    claim_contexts = [_claim_contexts(claim) for claim in bundle.seed_claims]
    supporting = set().union(*claim_contexts)
    partition_basis = "two_claims"
    branch_claim_ids = tuple((claim.truth_claim_id,) for claim in bundle.seed_claims)
    inferred_missing_edges: tuple[tuple[str, str], ...] = ()
    if len(claim_contexts) == 2:
        left, right = claim_contexts
    else:
        try:
            left, right, branch_claim_ids = _graph_partition(bundle, supporting)
            partition_basis = "truth_graph"
        except AmbiguousGoldPartition:
            if policy != "gold_partition_minimal_v2":
                raise
            left, right, branch_claim_ids, inferred_missing_edges = _structured_qid_partition(bundle, supporting)
            partition_basis = "structured_qid_chain_fallback"
    distractors = _ordered(all_indexes - supporting, seed, bundle.question.question_id)
    assignments: dict[str, list[int]] = {"agent_1": sorted(left), "agent_2": [], "agent_3": sorted(right)}
    if policy in {"gold_partition_minimal_v1", "gold_partition_minimal_v2"}:
        if not distractors:
            raise AmbiguousGoldPartition("minimal policy requires one distractor")
        assignments["agent_2"] = [distractors[0]]
        unused = set(distractors[1:])
    elif policy == "full_context_partition_v1":
        targets = {"agent_1": 3, "agent_2": 4, "agent_3": 3}
        for index in distractors:
            eligible = [a for a in assignments if len(assignments[a]) < targets[a]]
            target = min(eligible, key=lambda a: (len(assignments[a]) / targets[a], a))
            assignments[target].append(index)
        unused = set()
        if set().union(*(set(v) for v in assignments.values())) != all_indexes:
            raise RuntimeError("full-context policy failed to allocate every context")
    else:
        raise ValueError(f"unknown assignment policy: {policy}")
    return AssignmentSnapshot(question_id=bundle.question.question_id, policy=policy, rule_version=rule_version,
        seed=seed, assignments={a: tuple(ContextRef(sample_id=bundle.question.question_id, context_index=i)
        for i in sorted(indexes)) for a, indexes in assignments.items()},
        unused_context_refs=tuple(ContextRef(sample_id=bundle.question.question_id, context_index=i) for i in sorted(unused)),
        partition_basis=partition_basis, branch_claim_ids=branch_claim_ids,
        inferred_missing_edges=inferred_missing_edges)
