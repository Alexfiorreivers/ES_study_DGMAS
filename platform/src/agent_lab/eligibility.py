"""Gate B experiment eligibility and frozen policy registry.

Gate B consumes only Gate-A-validated ``PlatformInputBundle`` objects.  It
never repairs truth data and never calls a provider.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from agent_lab.assignment import AmbiguousGoldPartition, assign_documents
from agent_lab.domain.contracts_v0_1 import (
    AssignmentSnapshot,
    ContextRef,
    ExperimentConfig,
    GateBReport,
    GateBResult,
    PlatformInputBundle,
)


MUSIQUE_POLICY = "gold_hop_partition_musique_v1"
MUSIQUE_POLICY_VERSION = "1.0.0"
MUSIQUE_V2_POLICY = "gold_decomposition_step_partition_musique_v2"
MUSIQUE_V2_POLICY_VERSION = "2.0.0"
MUSIQUE_DIFFICULTY_BASIS = "inference_edge_count"
MUSIQUE_V2_DIFFICULTY_BASIS = "decomposition_step_count"
AGENTS = ("agent_1", "agent_2", "agent_3")

IMPLEMENTED_POLICY_REGISTRY: dict[str, dict[str, dict[str, str]]] = {
    "2WikiMultiHopQA": {
        question_type: {
            "gold_partition_minimal_v1": "1.0.0",
            "gold_partition_minimal_v2": "2.0.0",
            "full_context_partition_v1": "1.0.0",
        }
        for question_type in ("compositional", "comparison", "inference", "bridge_comparison")
    },
    "MuSiQue": {
        question_type: {
            MUSIQUE_POLICY: MUSIQUE_POLICY_VERSION,
            MUSIQUE_V2_POLICY: MUSIQUE_V2_POLICY_VERSION,
        }
        for question_type in ("2hop", "3hop", "4hop")
    },
}

FROZEN_MUSIQUE_MAPPINGS = {
    "2hop": {"agent_1": (1,), "agent_2": (), "agent_3": (2,)},
    "3hop": {"agent_1": (1,), "agent_2": (2,), "agent_3": (3,)},
    "4hop": {"agent_1": (1, 2), "agent_2": (3,), "agent_3": (4,)},
}


class GateBValidationError(ValueError):
    """One or more selected samples failed experiment eligibility."""

    def __init__(self, report: GateBReport):
        self.report = report
        first = next(result for result in report.results if not result.eligible)
        self.code = first.failure_code
        self.detail = first.failure_detail
        self.sample_id = first.sample_id
        super().__init__(f"Gate B {self.code} for {self.sample_id}: {self.detail}")


def _empty_assignments() -> dict[str, tuple[ContextRef, ...]]:
    return {agent: () for agent in AGENTS}


def _failure(
    bundle: PlatformInputBundle,
    policy: str,
    version: str,
    code: str,
    detail: str,
    *,
    basis: str = "not_computed",
    value: int | str | None = None,
    **metadata,
) -> GateBResult:
    return GateBResult(
        sample_id=bundle.question.question_id,
        dataset_name=bundle.truth_provenance.dataset_name,
        eligible=False,
        policy=policy,
        policy_version=version,
        difficulty_basis=basis,
        difficulty_value=value,
        assignments=_empty_assignments(),
        failure_code=code,
        failure_detail=detail,
        **metadata,
    )


def _resolve_policy(bundle: PlatformInputBundle, config: ExperimentConfig) -> GateBResult | None:
    dataset = bundle.truth_provenance.dataset_name
    question_type = bundle.question.question_type or ""
    policy = config.document_assignment.policy
    version = config.document_assignment.rule_version
    implemented_dataset = IMPLEMENTED_POLICY_REGISTRY.get(dataset)
    if implemented_dataset is None:
        return _failure(bundle, policy, version, "POLICY_NOT_REGISTERED", f"dataset {dataset!r} has no implemented policy registry")
    if question_type not in implemented_dataset:
        return _failure(bundle, policy, version, "QUESTION_TYPE_UNSUPPORTED", f"question_type {question_type!r} is unsupported for {dataset}")
    configured = config.gates.gate_b.policy_registry
    configured_version = configured.get(dataset, {}).get(question_type, {}).get(policy)
    implemented_version = implemented_dataset[question_type].get(policy)
    if implemented_version is None or configured_version != version or implemented_version != version:
        return _failure(
            bundle,
            policy,
            version,
            "POLICY_NOT_REGISTERED",
            f"exact dataset/question_type/policy/version registration not found: {dataset}/{question_type}/{policy}/{version}",
        )
    return None


def _all_inference_paths(bundle: PlatformInputBundle) -> tuple[tuple[str, ...], ...]:
    graph = bundle.truth_reasoning_graph
    roots = tuple(str(value) for value in graph.get("root_claim_ids", []))
    if len(roots) != 1:
        return ()
    final_claim = roots[0]
    claim_ids = {claim.truth_claim_id for claim in bundle.seed_claims if claim.truth_claim_id}
    outgoing: dict[str, list[str]] = {claim_id: [] for claim_id in claim_ids}
    incoming_count: Counter[str] = Counter()
    for edge in graph.get("edges", []):
        if edge.get("edge_type") != "inference":
            continue
        source, target = str(edge["from_claim_id"]), str(edge["to_claim_id"])
        if source in outgoing and target in outgoing:
            outgoing[source].append(target)
            incoming_count[target] += 1
    for targets in outgoing.values():
        targets.sort()
    starts = sorted(node for node in claim_ids if incoming_count[node] == 0)
    paths: list[tuple[str, ...]] = []

    def walk(node: str, path: tuple[str, ...]) -> None:
        if node == final_claim:
            paths.append(path)
            return
        for target in outgoing[node]:
            walk(target, (*path, target))

    for start in starts:
        walk(start, (start,))
    return tuple(paths)


def _musique_v1_result(bundle: PlatformInputBundle, config: ExperimentConfig) -> GateBResult:
    policy = config.document_assignment.policy
    version = config.document_assignment.rule_version
    question_type = bundle.question.question_type or ""
    expected_hops = int(question_type.removesuffix("hop"))
    paths = _all_inference_paths(bundle)
    if not paths:
        return _failure(
            bundle, policy, version, "HOP_EVIDENCE_NOT_UNIQUE",
            "no directed inference path reaches the unique final claim",
            basis=MUSIQUE_DIFFICULTY_BASIS,
        )
    max_edges = max(len(path) - 1 for path in paths)
    longest = tuple(path for path in paths if len(path) - 1 == max_edges)

    # Stable failure priority: hop mismatch precedes path ambiguity, followed by
    # evidence, coverage, overlap, and final assignment validation.
    if max_edges != expected_hops:
        return _failure(
            bundle, policy, version, "HOP_COUNT_MISMATCH",
            f"question_type requires {expected_hops} inference edges; graph longest path has {max_edges}",
            basis=MUSIQUE_DIFFICULTY_BASIS, value=max_edges,
        )
    if len(longest) != 1:
        return _failure(
            bundle, policy, version, "GOLD_PATH_NOT_UNIQUE",
            f"found {len(longest)} longest inference paths with {max_edges} edges",
            basis=MUSIQUE_DIFFICULTY_BASIS, value=max_edges,
        )

    path = longest[0]
    claim_by_truth = {claim.truth_claim_id: claim for claim in bundle.seed_claims}
    valid_contexts = {document.context_index for document in bundle.documents}
    units: list[tuple[int, ...]] = []
    for hop_index, claim_id in enumerate(path[:-1], 1):
        claim = claim_by_truth.get(claim_id)
        contexts = () if claim is None else tuple(sorted({ref.context_ref.context_index for ref in claim.source_refs}))
        refs_valid = claim is not None and claim.source_refs and all(
            ref.context_ref.sample_id == bundle.question.question_id and ref.context_ref.context_index in valid_contexts
            for ref in claim.source_refs
        )
        if not contexts or not refs_valid:
            return _failure(
                bundle, policy, version, "HOP_EVIDENCE_NOT_UNIQUE",
                f"hop {hop_index} claim {claim_id} has empty or invalid evidence contexts",
                basis=MUSIQUE_DIFFICULTY_BASIS, value=max_edges,
            )
        units.append(contexts)

    covered = set().union(*(set(unit) for unit in units))
    final_claim = claim_by_truth.get(path[-1])
    final_contexts = set() if final_claim is None else {ref.context_ref.context_index for ref in final_claim.source_refs}
    gold_contexts = {document.context_index for document in bundle.documents if document.is_supporting_context}
    if not final_contexts <= covered:
        return _failure(
            bundle, policy, version, "GOLD_CONTEXT_UNCOVERED",
            f"final claim introduces contexts not present in hop units: {sorted(final_contexts - covered)}",
            basis=MUSIQUE_DIFFICULTY_BASIS, value=max_edges,
        )
    if covered != gold_contexts:
        return _failure(
            bundle, policy, version, "GOLD_CONTEXT_UNCOVERED",
            f"hop units cover {sorted(covered)} but official gold contexts are {sorted(gold_contexts)}",
            basis=MUSIQUE_DIFFICULTY_BASIS, value=max_edges,
        )

    configured_mappings = config.document_assignment.mappings or {}
    normalized_mapping = {
        agent: tuple(hops) for agent, hops in configured_mappings.get(question_type, {}).items()
    }
    if normalized_mapping != FROZEN_MUSIQUE_MAPPINGS[question_type]:
        return _failure(
            bundle, policy, version, "AGENT_ASSIGNMENT_INVALID",
            f"YAML mapping {normalized_mapping} does not equal frozen mapping {FROZEN_MUSIQUE_MAPPINGS[question_type]}",
            basis=MUSIQUE_DIFFICULTY_BASIS, value=max_edges,
        )

    agent_contexts: dict[str, set[int]] = {agent: set() for agent in AGENTS}
    for agent, hop_numbers in normalized_mapping.items():
        for hop_number in hop_numbers:
            if hop_number < 1 or hop_number > len(units):
                return _failure(
                    bundle, policy, version, "AGENT_ASSIGNMENT_INVALID",
                    f"{agent} references invalid hop {hop_number}",
                    basis=MUSIQUE_DIFFICULTY_BASIS, value=max_edges,
                )
            agent_contexts[agent].update(units[hop_number - 1])
    context_occurrences = Counter(index for unit in units for index in unit)
    repeated_contexts = sorted(index for index, count in context_occurrences.items() if count != 1)
    if repeated_contexts:
        return _failure(
            bundle, policy, version, "GOLD_CONTEXT_OVERLAP",
            f"gold contexts occur in more than one hop evidence unit: {repeated_contexts}",
            basis=MUSIQUE_DIFFICULTY_BASIS, value=max_edges,
        )
    for left_index, left in enumerate(AGENTS):
        for right in AGENTS[left_index + 1:]:
            overlap = agent_contexts[left] & agent_contexts[right]
            if overlap:
                return _failure(
                    bundle, policy, version, "GOLD_CONTEXT_OVERLAP",
                    f"{left} and {right} share gold contexts {sorted(overlap)}",
                    basis=MUSIQUE_DIFFICULTY_BASIS, value=max_edges,
                )
    assigned_union = set().union(*agent_contexts.values())
    if set(agent_contexts) != set(AGENTS) or assigned_union != gold_contexts:
        return _failure(
            bundle, policy, version, "AGENT_ASSIGNMENT_INVALID",
            "final three-Agent assignment does not exactly cover official gold contexts",
            basis=MUSIQUE_DIFFICULTY_BASIS, value=max_edges,
        )

    assignments = {
        agent: tuple(ContextRef(sample_id=bundle.question.question_id, context_index=index) for index in sorted(contexts))
        for agent, contexts in agent_contexts.items()
    }
    return GateBResult(
        sample_id=bundle.question.question_id,
        dataset_name=bundle.truth_provenance.dataset_name,
        eligible=True,
        policy=policy,
        policy_version=version,
        difficulty_basis=MUSIQUE_DIFFICULTY_BASIS,
        difficulty_value=max_edges,
        assignments=assignments,
        inference_path_claim_ids=path,
        hop_evidence_units=tuple(
            tuple(ContextRef(sample_id=bundle.question.question_id, context_index=index) for index in unit)
            for unit in units
        ),
    )


def _musique_v2_result(bundle: PlatformInputBundle, config: ExperimentConfig) -> GateBResult:
    policy = config.document_assignment.policy
    version = config.document_assignment.rule_version
    question_type = bundle.question.question_type or ""
    step_count = int(question_type.removesuffix("hop"))
    sample_id = bundle.question.question_id
    question_template = str(bundle.question.metadata.get("question_template") or "")
    graph_hop = bundle.question.reasoning_hop_count
    edge_counts = dict(Counter(str(edge["edge_type"]) for edge in bundle.truth_reasoning_graph.get("edges", [])))
    base_metadata = {
        "dataset_hop_label": step_count,
        "decomposition_step_count": step_count,
        "dependency_graph_hop_count": graph_hop,
        "question_template": question_template or None,
        "edge_type_counts": edge_counts,
        "agent_step_positions": FROZEN_MUSIQUE_MAPPINGS[question_type],
    }

    def fail(code: str, detail: str, **extra) -> GateBResult:
        return _failure(
            bundle, policy, version, code, detail,
            basis=MUSIQUE_V2_DIFFICULTY_BASIS, value=step_count,
            **{**base_metadata, **extra},
        )

    claim_by_truth = {claim.truth_claim_id: claim for claim in bundle.seed_claims if claim.truth_claim_id}
    expected_claim_ids = tuple(f"{sample_id}:claim:{index}" for index in range(step_count))
    if any(claim_id not in claim_by_truth for claim_id in expected_claim_ids):
        return fail("STEP_SOURCE_GROUP_MISSING", "one or more stable decomposition-step claims are missing")
    if set(claim_by_truth) != set(expected_claim_ids):
        return fail("STEP_SOURCE_GROUP_AMBIGUOUS", "claims do not map one-to-one onto decomposition steps")

    valid_contexts = {document.context_index for document in bundle.documents}
    step_units: list[tuple[ContextRef, ...]] = []
    step_source_ids: list[tuple[str, ...]] = []
    source_to_step: dict[str, int] = {}
    for step_position, claim_id in enumerate(expected_claim_ids, 1):
        claim = claim_by_truth[claim_id]
        if not claim.source_refs:
            return fail("STEP_SOURCE_GROUP_MISSING", f"step {step_position} has no accepted source refs",
                        step_claim_ids=expected_claim_ids[:step_position - 1])
        source_ids: list[str] = []
        contexts: set[int] = set()
        for ref in claim.source_refs:
            source_id = ref.truth_source_id or ref.evidence_id
            positions = ref.raw_locator.get("decomposition_step_positions")
            if not isinstance(positions, list) or step_position not in positions:
                return fail("STEP_SOURCE_GROUP_AMBIGUOUS",
                            f"source {source_id} does not uniquely identify step {step_position}")
            if positions != [step_position]:
                return fail("SOURCE_ASSIGNED_MORE_THAN_ONCE",
                            f"source {source_id} declares multiple decomposition steps: {positions}")
            previous = source_to_step.get(source_id)
            if previous is not None and previous != step_position:
                return fail("SOURCE_ASSIGNED_MORE_THAN_ONCE",
                            f"source {source_id} is assigned to steps {previous} and {step_position}")
            if ref.context_ref.sample_id != sample_id or ref.context_ref.context_index not in valid_contexts:
                return fail("STEP_SOURCE_GROUP_AMBIGUOUS", f"source {source_id} has an invalid context ref")
            source_to_step[source_id] = step_position
            source_ids.append(source_id)
            contexts.add(ref.context_ref.context_index)
        if len(source_ids) != len(set(source_ids)) or not contexts:
            return fail("STEP_SOURCE_GROUP_AMBIGUOUS", f"step {step_position} source group is empty or duplicated")
        step_source_ids.append(tuple(source_ids))
        step_units.append(tuple(ContextRef(sample_id=sample_id, context_index=index) for index in sorted(contexts)))

    occurrences = Counter(ref.context_index for unit in step_units for ref in unit)
    repeated_contexts = sorted(index for index, count in occurrences.items() if count != 1)
    if repeated_contexts:
        return fail("SOURCE_ASSIGNED_MORE_THAN_ONCE",
                    f"gold contexts occur in multiple step source groups: {repeated_contexts}",
                    step_claim_ids=expected_claim_ids, step_evidence_units=tuple(step_units),
                    step_source_ids=tuple(step_source_ids))
    covered = set(occurrences)
    gold_contexts = {document.context_index for document in bundle.documents if document.is_supporting_context}
    if covered != gold_contexts:
        return fail("ASSIGNMENT_COVERAGE_MISMATCH",
                    f"step groups cover {sorted(covered)} but official gold contexts are {sorted(gold_contexts)}",
                    step_claim_ids=expected_claim_ids, step_evidence_units=tuple(step_units),
                    step_source_ids=tuple(step_source_ids))

    configured = config.document_assignment.mappings or {}
    normalized_mapping = {agent: tuple(steps) for agent, steps in configured.get(question_type, {}).items()}
    if normalized_mapping != FROZEN_MUSIQUE_MAPPINGS[question_type]:
        return fail("AGENT_ASSIGNMENT_INVALID", "YAML step mapping does not equal the frozen v2 mapping")
    assignments = {
        agent: tuple(
            ref
            for step_position in normalized_mapping[agent]
            for ref in step_units[step_position - 1]
        )
        for agent in AGENTS
    }
    assigned = [ref.context_index for refs in assignments.values() for ref in refs]
    if len(assigned) != len(set(assigned)) or set(assigned) != gold_contexts:
        return fail("ASSIGNMENT_COVERAGE_MISMATCH", "final Agent assignments are overlapping or incomplete")
    return GateBResult(
        sample_id=sample_id,
        dataset_name=bundle.truth_provenance.dataset_name,
        eligible=True,
        policy=policy,
        policy_version=version,
        difficulty_basis=MUSIQUE_V2_DIFFICULTY_BASIS,
        difficulty_value=step_count,
        assignments=assignments,
        step_claim_ids=expected_claim_ids,
        step_evidence_units=tuple(step_units),
        step_source_ids=tuple(step_source_ids),
        **base_metadata,
    )


def evaluate_bundle(bundle: PlatformInputBundle, config: ExperimentConfig) -> GateBResult:
    resolution_failure = _resolve_policy(bundle, config)
    if resolution_failure is not None:
        return resolution_failure
    if bundle.truth_provenance.dataset_name == "MuSiQue":
        if config.document_assignment.policy == MUSIQUE_V2_POLICY:
            return _musique_v2_result(bundle, config)
        return _musique_v1_result(bundle, config)
    try:
        snapshot = assign_documents(
            bundle,
            config.document_assignment.policy,
            config.document_assignment.rule_version,
            config.document_assignment.seed,
        )
    except (AmbiguousGoldPartition, ValueError, RuntimeError) as error:
        return _failure(
            bundle,
            config.document_assignment.policy,
            config.document_assignment.rule_version,
            "AGENT_ASSIGNMENT_INVALID",
            str(error),
            basis="question_type",
            value=bundle.question.question_type,
        )
    return GateBResult(
        sample_id=bundle.question.question_id,
        dataset_name=bundle.truth_provenance.dataset_name,
        eligible=True,
        policy=snapshot.policy,
        policy_version=snapshot.rule_version,
        difficulty_basis="question_type",
        difficulty_value=bundle.question.question_type,
        assignments=snapshot.assignments,
        unused_context_refs=snapshot.unused_context_refs,
        partition_basis=snapshot.partition_basis,
        branch_claim_ids=snapshot.branch_claim_ids,
        inferred_missing_edges=snapshot.inferred_missing_edges,
    )


def evaluate_selected(
    bundles: Iterable[PlatformInputBundle], config: ExperimentConfig
) -> tuple[GateBReport, dict[str, AssignmentSnapshot]]:
    results = tuple(evaluate_bundle(bundle, config) for bundle in bundles)
    eligible = sum(result.eligible for result in results)
    report = GateBReport(
        status="pass" if eligible == len(results) else "fail",
        selected_samples=len(results),
        eligible_samples=eligible,
        ineligible_samples=len(results) - eligible,
        results=results,
    )
    if report.status == "fail":
        raise GateBValidationError(report)
    snapshots = {
        result.sample_id: AssignmentSnapshot(
            question_id=result.sample_id,
            policy=result.policy,
            rule_version=result.policy_version,
            seed=config.document_assignment.seed,
            difficulty_basis=result.difficulty_basis,
            difficulty_value=result.difficulty_value,
            dataset_hop_label=result.dataset_hop_label,
            decomposition_step_count=result.decomposition_step_count,
            dependency_graph_hop_count=result.dependency_graph_hop_count,
            question_template=result.question_template,
            step_claim_ids=result.step_claim_ids,
            step_evidence_units=result.step_evidence_units,
            step_source_ids=result.step_source_ids,
            edge_type_counts=result.edge_type_counts,
            agent_step_positions=result.agent_step_positions,
            partition_basis=result.partition_basis,
            branch_claim_ids=result.branch_claim_ids,
            inferred_missing_edges=result.inferred_missing_edges,
            assignments=result.assignments,
            unused_context_refs=result.unused_context_refs,
        )
        for result in results
    }
    return report, snapshots
