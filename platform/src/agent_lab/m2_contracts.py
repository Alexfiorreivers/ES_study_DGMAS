"""Strict, versioned contracts for the M2 evaluator.

These models deliberately live outside the runtime contracts.  Evaluator-only
truth and semantic judgments must never become a Provider or Agent input.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


M2_CONTRACT_VERSION = "1.0.0"
METRICS_SPEC_VERSION = "task-d-v0.2"
ANNOTATION_RULE_VERSION = "m2-annotation-1.0.0"
EVALUATOR_PROMPT_VERSION = "m2-fielded-evaluator-1.0.0"


class M2Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)


class AlignmentType(StrEnum):
    NONE = "none"
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"


class ClaimPresence(StrEnum):
    PRESENT_EQUIVALENT = "present_equivalent"
    PRESENT_PARTIAL = "present_partial"
    ABSENT = "absent"
    UNINTERPRETABLE = "uninterpretable"


class SourceMarkerStatus(StrEnum):
    ABSENT = "absent"
    UNIDENTIFIABLE = "unidentifiable"
    IDENTIFIABLE = "identifiable"
    NOT_APPLICABLE = "not_applicable"


class SourceChangeStatus(StrEnum):
    UNCHANGED = "unchanged"
    SUBSTITUTED_VALID = "substituted_valid"
    SUBSTITUTED_INVALID = "substituted_invalid"
    DROPPED = "dropped"
    UNIDENTIFIABLE = "unidentifiable"
    NOT_APPLICABLE = "not_applicable"


class SupportFine(StrEnum):
    FULLY_SUPPORTED = "fully_supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    CONTRADICTED = "contradicted"
    INSUFFICIENT = "insufficient"
    NOT_APPLICABLE = "not_applicable"


class ContentTruth(StrEnum):
    TRUE = "true"
    FALSE = "false"
    UNDETERMINED = "undetermined"
    NOT_APPLICABLE = "not_applicable"


class ReviewStatus(StrEnum):
    DECIDED = "decided"
    NEEDS_REVIEW = "needs_review"


class ReviewReason(StrEnum):
    ALIGNMENT_AMBIGUITY = "alignment_ambiguity"
    LOCATOR_AMBIGUITY = "locator_ambiguity"
    JOINT_SUPPORT_AMBIGUITY = "joint_support_ambiguity"
    TRUTH_CONDITION_AMBIGUITY = "truth_condition_ambiguity"
    TRUTH_SOURCE_CONFLICT = "truth_source_conflict"
    QUALIFICATION_AMBIGUITY = "qualification_ambiguity"
    ANNOTATOR_OR_CANDIDATE_CONFLICT = "annotator_or_candidate_conflict"
    ANNOTATION_RULE_CONFLICT = "annotation_rule_conflict"


class JudgmentOrigin(StrEnum):
    MANUAL = "manual"
    AUTOMATIC_CANDIDATE = "automatic_candidate"
    DEEPSEEK_CANDIDATE = "deepseek_candidate"
    ADJUDICATED = "adjudicated"


class SemanticDisposition(StrEnum):
    DECIDED = "decided"
    NOT_APPLICABLE = "not_applicable"
    MISSING = "missing"
    SEMANTIC_NEGATIVE = "semantic_negative"
    NEEDS_REVIEW = "needs_review"


class EngineeringExclusion(M2Model):
    """Run/question failures are recorded outside semantic judgments."""

    schema_version: Literal["1.0.0"] = M2_CONTRACT_VERSION
    run_id: str = Field(min_length=1)
    question_id: str | None = None
    exclusion_level: Literal["run", "question"]
    failure_code: str = Field(min_length=1)
    semantic_denominator_included: Literal[False] = False
    converted_to_semantic_label: Literal[False] = False

    @model_validator(mode="after")
    def question_level_has_id(self) -> "EngineeringExclusion":
        if self.exclusion_level == "question" and not self.question_id:
            raise ValueError("question-level engineering exclusion requires question_id")
        if self.exclusion_level == "run" and self.question_id is not None:
            raise ValueError("run-level engineering exclusion cannot name one question")
        return self


class AlignmentJudgment(M2Model):
    alignment_id: str = Field(min_length=1)
    alignment_type: AlignmentType
    truth_claim_ids: tuple[str, ...]
    runtime_claim_ids: tuple[str, ...]

    @model_validator(mode="after")
    def cardinality_matches_type(self) -> "AlignmentJudgment":
        if len(set(self.truth_claim_ids)) != len(self.truth_claim_ids):
            raise ValueError("truth_claim_ids must be unique")
        if len(set(self.runtime_claim_ids)) != len(self.runtime_claim_ids):
            raise ValueError("runtime_claim_ids must be unique")
        counts = (len(self.truth_claim_ids), len(self.runtime_claim_ids))
        expected = {
            AlignmentType.NONE: (0, 0),
            AlignmentType.ONE_TO_ONE: (1, 1),
            AlignmentType.ONE_TO_MANY: (1, 2),
            AlignmentType.MANY_TO_ONE: (2, 1),
            AlignmentType.MANY_TO_MANY: (2, 2),
        }
        minimum = expected[self.alignment_type]
        if self.alignment_type is AlignmentType.NONE:
            if counts != minimum:
                raise ValueError("none alignment must have empty claim lists")
        elif counts[0] < minimum[0] or counts[1] < minimum[1]:
            raise ValueError("alignment cardinality does not match alignment_type")
        return self


class NodeJudgment(M2Model):
    schema_version: Literal["1.0.0"] = M2_CONTRACT_VERSION
    judgment_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    scope_kind: Literal["message_node", "hop_union", "terminal_union"] = "message_node"
    scope_node_ids: tuple[str, ...] = ()
    communication_hop: int = Field(ge=0)
    truth_claim_id: str = Field(min_length=1)
    canonical_source_ids: tuple[str, ...] = Field(min_length=1)
    alignment: AlignmentJudgment
    claim_presence: ClaimPresence
    semantic_equivalence: bool | None
    interpretable: bool
    source_marker_status: SourceMarkerStatus
    runtime_source_ids: tuple[str, ...] = ()
    exact_set_survived: bool | None
    source_change_status: SourceChangeStatus
    support_fine: SupportFine
    unsupported_spans: tuple[str, ...] = ()
    content_truth: ContentTruth
    qualification_change: tuple[str, ...] = ()
    disposition: SemanticDisposition
    review_status: ReviewStatus
    review_reason_codes: tuple[ReviewReason, ...] = ()
    origin: JudgmentOrigin
    is_final: bool
    annotator_id: str | None = None
    candidate_id: str | None = None
    rationale: str | None = None
    created_at: datetime

    @model_validator(mode="after")
    def enforce_semantics(self) -> "NodeJudgment":
        if self.created_at.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        if self.scope_kind == "message_node" and self.scope_node_ids not in {(), (self.node_id,)}:
            raise ValueError("message_node scope can only reference its own node_id")
        if self.scope_kind != "message_node" and not self.scope_node_ids:
            raise ValueError("union scopes require contributing scope_node_ids")
        if self.truth_claim_id not in self.alignment.truth_claim_ids and self.alignment.alignment_type is not AlignmentType.NONE:
            raise ValueError("truth_claim_id must occur in alignment.truth_claim_ids")
        if len(set(self.canonical_source_ids)) != len(self.canonical_source_ids):
            raise ValueError("canonical_source_ids must be unique")
        if len(set(self.runtime_source_ids)) != len(self.runtime_source_ids):
            raise ValueError("runtime_source_ids must be unique")
        if self.origin in {JudgmentOrigin.AUTOMATIC_CANDIDATE, JudgmentOrigin.DEEPSEEK_CANDIDATE} and self.is_final:
            raise ValueError("automatic/DeepSeek candidates cannot be final judgments")
        if self.review_status is ReviewStatus.NEEDS_REVIEW:
            if not self.review_reason_codes or self.disposition is not SemanticDisposition.NEEDS_REVIEW:
                raise ValueError("needs_review requires an allowed reason and needs_review disposition")
        elif self.review_reason_codes or self.disposition is SemanticDisposition.NEEDS_REVIEW:
            raise ValueError("decided rows cannot carry review reasons or needs_review disposition")
        equivalent = self.claim_presence is ClaimPresence.PRESENT_EQUIVALENT
        if equivalent != (self.semantic_equivalence is True):
            raise ValueError("semantic_equivalence=true iff claim_presence=present_equivalent")
        if not equivalent:
            if self.exact_set_survived is not None:
                raise ValueError("non-equivalent claims require exact_set_survived=null")
            if self.source_change_status is not SourceChangeStatus.NOT_APPLICABLE:
                raise ValueError("non-equivalent claims require source_change_status=not_applicable")
            if self.support_fine is not SupportFine.NOT_APPLICABLE:
                raise ValueError("non-equivalent claims require support_fine=not_applicable")
        elif self.source_marker_status is SourceMarkerStatus.IDENTIFIABLE:
            expected_exact = set(self.runtime_source_ids) == set(self.canonical_source_ids)
            if self.exact_set_survived is not expected_exact:
                raise ValueError("exact_set_survived must equal exact canonical/runtime source-set equality")
            if not self.runtime_source_ids:
                raise ValueError("identifiable source markers require runtime_source_ids")
            if expected_exact and self.source_change_status is not SourceChangeStatus.UNCHANGED:
                raise ValueError("exact source-set survival requires unchanged source status")
            if not expected_exact and self.source_change_status not in {
                SourceChangeStatus.SUBSTITUTED_VALID, SourceChangeStatus.SUBSTITUTED_INVALID
            }:
                raise ValueError("changed identifiable source sets require valid/invalid substitution status")
        elif self.source_marker_status is SourceMarkerStatus.ABSENT:
            if self.runtime_source_ids or self.exact_set_survived is not False:
                raise ValueError("absent source requires empty runtime set and exact_set_survived=false")
            if self.source_change_status is not SourceChangeStatus.DROPPED:
                raise ValueError("absent source on retained claim requires source_change_status=dropped")
            if self.support_fine is not SupportFine.NOT_APPLICABLE:
                raise ValueError("absent source requires support_fine=not_applicable")
        elif self.source_marker_status is SourceMarkerStatus.UNIDENTIFIABLE:
            if self.runtime_source_ids or self.exact_set_survived is not False:
                raise ValueError("unidentifiable source requires empty parsed set and exact_set_survived=false")
            if self.source_change_status is not SourceChangeStatus.UNIDENTIFIABLE:
                raise ValueError("unidentifiable marker requires matching source change")
            if self.support_fine is not SupportFine.NOT_APPLICABLE:
                raise ValueError("unidentifiable source requires support_fine=not_applicable")
        if self.source_change_status is SourceChangeStatus.SUBSTITUTED_VALID and self.support_fine is not SupportFine.FULLY_SUPPORTED:
            raise ValueError("valid substitution requires fully_supported")
        if self.source_change_status is SourceChangeStatus.SUBSTITUTED_INVALID and self.support_fine not in {
            SupportFine.PARTIALLY_SUPPORTED, SupportFine.CONTRADICTED, SupportFine.INSUFFICIENT
        }:
            raise ValueError("invalid substitution requires a non-full support judgment")
        return self


class EdgeJudgment(M2Model):
    schema_version: Literal["1.0.0"] = M2_CONTRACT_VERSION
    judgment_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    dependency_id: str = Field(min_length=1)
    parent_node_id: str = Field(min_length=1)
    child_node_id: str = Field(min_length=1)
    truth_claim_ids: tuple[str, ...] = Field(min_length=1)
    parent_runtime_claim_ids: tuple[str, ...] = ()
    child_runtime_claim_ids: tuple[str, ...] = ()
    claim_event: Literal[
        "claim_retained_equivalent", "claim_rewritten_non_equivalent", "claim_dropped",
        "claim_added", "claim_split", "claim_merged", "not_applicable"
    ]
    source_events: tuple[Literal[
        "source_set_retained_exact", "source_added_redundant", "source_dropped_partial",
        "source_dropped_all", "source_substituted_valid", "source_substituted_invalid",
        "source_marker_became_unidentifiable", "not_applicable"
    ], ...] = ()
    support_event: Literal["support_maintained", "support_improved", "support_degraded", "not_applicable"]
    qualification_events: tuple[str, ...] = ()
    disposition: SemanticDisposition
    review_status: ReviewStatus
    review_reason_codes: tuple[ReviewReason, ...] = ()
    origin: JudgmentOrigin
    is_final: bool
    annotator_id: str | None = None
    candidate_id: str | None = None
    rationale: str | None = None
    created_at: datetime

    @model_validator(mode="after")
    def enforce_edge_semantics(self) -> "EdgeJudgment":
        if self.created_at.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        if len(set(self.truth_claim_ids)) != len(self.truth_claim_ids):
            raise ValueError("truth_claim_ids must be unique within an edge judgment")
        if len(set(self.parent_runtime_claim_ids)) != len(self.parent_runtime_claim_ids):
            raise ValueError("parent_runtime_claim_ids must be unique within an edge judgment")
        if len(set(self.child_runtime_claim_ids)) != len(self.child_runtime_claim_ids):
            raise ValueError("child_runtime_claim_ids must be unique within an edge judgment")
        if self.origin in {JudgmentOrigin.AUTOMATIC_CANDIDATE, JudgmentOrigin.DEEPSEEK_CANDIDATE} and self.is_final:
            raise ValueError("candidate edge judgments cannot be final")
        if self.review_status is ReviewStatus.NEEDS_REVIEW:
            if not self.review_reason_codes or self.disposition is not SemanticDisposition.NEEDS_REVIEW:
                raise ValueError("needs_review edge requires reason and matching disposition")
        elif self.review_reason_codes or self.disposition is SemanticDisposition.NEEDS_REVIEW:
            raise ValueError("decided edge cannot carry review metadata")
        if self.claim_event == "not_applicable" and any(event != "not_applicable" for event in self.source_events):
            raise ValueError("not_applicable claim event cannot carry substantive source events")
        if self.claim_event == "not_applicable" and (self.parent_runtime_claim_ids or self.child_runtime_claim_ids):
            raise ValueError("not_applicable truth-claim scope cannot carry runtime claim ids")
        return self


class ArtifactHash(M2Model):
    path: str = Field(min_length=1)
    sha256: str = Field(pattern="^[0-9a-f]{64}$")


class ConditionIdentity(M2Model):
    condition_alias: str = Field(min_length=1)
    condition_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    replicate_id: str = Field(min_length=1)


class EvaluationManifest(M2Model):
    schema_version: Literal["1.0.0"] = M2_CONTRACT_VERSION
    evaluation_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    admission_status: Literal["admitted", "rejected"]
    admission_failures: tuple[str, ...] = ()
    completed_question_ids: tuple[str, ...]
    condition: ConditionIdentity
    metrics_spec_version: str = METRICS_SPEC_VERSION
    annotation_rule_version: str = ANNOTATION_RULE_VERSION
    evaluator_prompt_version: str = EVALUATOR_PROMPT_VERSION
    evaluator_prompt_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    run_manifest_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    data_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    schema_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    truth_artifact_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    repair_manifest_sha256: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")
    generator_prompt_id: str = Field(min_length=1)
    generator_prompt_version: str = Field(min_length=1)
    generator_prompt_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    input_artifacts: tuple[ArtifactHash, ...]
    output_artifacts: tuple[ArtifactHash, ...] = ()
    truth_view_access: Literal["post_run_evaluator_only"] = "post_run_evaluator_only"
    semantic_status: Literal["awaiting_judgments", "partially_judged", "complete"]
    created_at: datetime

    @model_validator(mode="after")
    def admission_is_consistent(self) -> "EvaluationManifest":
        if self.created_at.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        if self.admission_status == "admitted" and self.admission_failures:
            raise ValueError("admitted manifests cannot have admission failures")
        if self.admission_status == "rejected" and not self.admission_failures:
            raise ValueError("rejected manifests require admission failures")
        return self


class JudgmentAuditEvent(M2Model):
    schema_version: Literal["1.0.0"] = M2_CONTRACT_VERSION
    event_id: str = Field(min_length=1)
    judgment_id: str = Field(min_length=1)
    action: Literal["candidate_imported", "manual_imported", "adjudicated", "revised"]
    actor_id: str = Field(min_length=1)
    source_hashes: tuple[str, ...] = Field(min_length=1)
    before_sha256: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")
    after_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    note: str | None = None
    created_at: datetime


class CalibrationItem(M2Model):
    schema_version: Literal["1.0.0"] = M2_CONTRACT_VERSION
    calibration_id: str = Field(min_length=1)
    blind_condition_alias: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    node_ids: tuple[str, ...] = Field(min_length=1)
    stratum: str = Field(min_length=1)
    first_pass_judgment_ids: tuple[str, ...] = ()
    repeat_pass_judgment_ids: tuple[str, ...] = ()


class MetricValue(M2Model):
    status: Literal["computed", "not_applicable", "missing"]
    numerator: float | None = None
    effective_denominator: int = Field(ge=0)
    raw_truth_claim_denominator: int = Field(ge=0)
    needs_review_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    not_applicable_count: int = Field(ge=0)
    value: float | None = None
    not_applicable_reason: str | None = None

    @model_validator(mode="after")
    def metric_status_is_consistent(self) -> "MetricValue":
        if self.status == "computed":
            if self.numerator is None or self.value is None or self.effective_denominator <= 0:
                raise ValueError("computed metric requires numerator, value, and a positive denominator")
            if self.not_applicable_reason is not None:
                raise ValueError("computed metric cannot have not_applicable_reason")
        else:
            if self.numerator is not None or self.value is not None:
                raise ValueError("non-computed metric cannot use numeric zero/value placeholders")
            if not self.not_applicable_reason:
                raise ValueError("non-computed metric requires a reason")
        return self


class FieldedEvaluatorCandidate(M2Model):
    """Offline evaluator output: independent fields, never a single total score."""

    schema_version: Literal["1.0.0"] = M2_CONTRACT_VERSION
    candidate_id: str = Field(min_length=1)
    alignment: dict[str, JsonValue]
    source_parsing: dict[str, JsonValue]
    support: dict[str, JsonValue]
    content_truth: dict[str, JsonValue]
    qualification: dict[str, JsonValue]
    edge_event: dict[str, JsonValue]
    confidence_by_field: dict[str, float]
    rationale_by_field: dict[str, str]

    @model_validator(mode="after")
    def required_fields_are_separate(self) -> "FieldedEvaluatorCandidate":
        required = {"alignment", "source_parsing", "support", "content_truth", "qualification", "edge_event"}
        if set(self.confidence_by_field) != required or set(self.rationale_by_field) != required:
            raise ValueError("confidence and rationale must be supplied for every evaluator field")
        if any(not 0 <= value <= 1 for value in self.confidence_by_field.values()):
            raise ValueError("field confidence must be within [0, 1]")
        return self


class TerminalClaimOccurrence(M2Model):
    """Condition-neutral occurrence retained by the future non-generative union."""

    occurrence_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    runtime_claim_id: str = Field(min_length=1)
    sender_id: str = Field(min_length=1)
    round: int = Field(ge=0)
    claim_text: str = Field(min_length=1)
    source_ids: tuple[str, ...] = ()
    qualification: str | None = None
    message_status: Literal["content", "no_new_information"]
    provenance: dict[str, JsonValue]


class TerminalClaimGroup(M2Model):
    """Only byte-identical semantic/source/status signatures may collapse."""

    group_id: str = Field(min_length=1)
    occurrence_ids: tuple[str, ...] = Field(min_length=1)
    claim_text: str = Field(min_length=1)
    source_ids: tuple[str, ...] = ()
    qualification: str | None = None
    message_status: Literal["content", "no_new_information"]


class TerminalObservationView(M2Model):
    """M3-facing interface only; it does not implement any condition runner."""

    schema_version: Literal["1.0.0"] = M2_CONTRACT_VERSION
    condition_family: Literal["M", "A1", "A2", "B1", "B0"]
    selection_rule: Literal[
        "last_communication_round_all_outputs", "three_round0_outputs", "single_centralized_output"
    ]
    union_mode: Literal["non_generative"] = "non_generative"
    selected_node_ids: tuple[str, ...] = Field(min_length=1)
    occurrences: tuple[TerminalClaimOccurrence, ...] = ()
    groups: tuple[TerminalClaimGroup, ...] = ()

    @model_validator(mode="after")
    def enforce_frozen_terminal_semantics(self) -> "TerminalObservationView":
        expected_rule = {
            "M": "last_communication_round_all_outputs",
            "A1": "last_communication_round_all_outputs",
            "A2": "last_communication_round_all_outputs",
            "B1": "three_round0_outputs",
            "B0": "single_centralized_output",
        }[self.condition_family]
        if self.selection_rule != expected_rule:
            raise ValueError("selection_rule does not match the frozen condition terminal view")
        if self.condition_family == "B1" and len(self.selected_node_ids) != 3:
            raise ValueError("B1 terminal view requires exactly three round-0 nodes")
        if self.condition_family == "B0" and len(self.selected_node_ids) != 1:
            raise ValueError("B0 terminal view requires exactly one centralized node")
        occurrence_by_id = {item.occurrence_id: item for item in self.occurrences}
        if len(occurrence_by_id) != len(self.occurrences):
            raise ValueError("terminal occurrence IDs must be unique")
        grouped_ids: list[str] = []
        for group in self.groups:
            grouped_ids.extend(group.occurrence_ids)
            for occurrence_id in group.occurrence_ids:
                occurrence = occurrence_by_id.get(occurrence_id)
                if occurrence is None:
                    raise ValueError("terminal group references an unknown occurrence")
                signature = (occurrence.claim_text, occurrence.source_ids, occurrence.qualification, occurrence.message_status)
                group_signature = (group.claim_text, group.source_ids, group.qualification, group.message_status)
                if signature != group_signature:
                    raise ValueError("only exact text/source/qualification/status duplicates may collapse")
        if len(grouped_ids) != len(set(grouped_ids)):
            raise ValueError("an occurrence cannot be collapsed into multiple terminal groups")
        if set(grouped_ids) != set(occurrence_by_id):
            raise ValueError("every occurrence must remain represented in a terminal group")
        return self
