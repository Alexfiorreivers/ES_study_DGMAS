"""Platform runtime contract v0.1 for Data Truth Schema 3.0.

The platform keeps dataset truth, runtime communication, and future evaluation
outputs separate. Models are immutable and reject unknown fields so a trace can
never silently change meaning when a schema evolves.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


PLATFORM_SCHEMA_VERSION = "0.1"
DATA_TRUTH_SCHEMA_VERSION = "3.0"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)


class Stage(StrEnum):
    INITIAL_READ = "initial_read"
    COMMUNICATION = "communication"
    AGGREGATION = "aggregation"


class MessageFormat(StrEnum):
    FREE_TEXT = "free_text"
    STRUCTURED = "structured"


class MessageStatus(StrEnum):
    CONTENT = "content"
    NO_NEW_INFORMATION = "no_new_information"


class SourceGranularity(StrEnum):
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    SENTENCE_SET = "sentence_set"


class ReferenceOrigin(StrEnum):
    LOCAL_DOCUMENT = "local_document"
    INHERITED_MESSAGE = "inherited_message"
    GENERATED_UNVERIFIED = "generated_unverified"


class ParseStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REPAIRED = "repaired"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class QuestionRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TraceEventType(StrEnum):
    RUN_STARTED = "RUN_STARTED"
    RUN_FINISHED = "RUN_FINISHED"
    RUN_FAILED = "RUN_FAILED"
    QUESTION_STARTED = "QUESTION_STARTED"
    QUESTION_FINISHED = "QUESTION_FINISHED"
    QUESTION_FAILED = "QUESTION_FAILED"
    INPUT_VALIDATION_FAILED = "INPUT_VALIDATION_FAILED"
    DOCUMENT_ASSIGNMENT_FROZEN = "DOCUMENT_ASSIGNMENT_FROZEN"
    INITIAL_READ_STARTED = "INITIAL_READ_STARTED"
    INITIAL_READ_FINISHED = "INITIAL_READ_FINISHED"
    ROUND_STARTED = "ROUND_STARTED"
    ROUND_FINISHED = "ROUND_FINISHED"
    MODEL_ATTEMPT_STARTED = "MODEL_ATTEMPT_STARTED"
    MODEL_ATTEMPT_FAILED = "MODEL_ATTEMPT_FAILED"
    MODEL_ATTEMPT_BUDGET_EXHAUSTED = "MODEL_ATTEMPT_BUDGET_EXHAUSTED"
    MODEL_RESPONSE_RECEIVED = "MODEL_RESPONSE_RECEIVED"
    QUESTION_CHECKPOINTED = "QUESTION_CHECKPOINTED"
    RUN_RESUMED = "RUN_RESUMED"
    MESSAGE_NODE_CREATED = "MESSAGE_NODE_CREATED"
    DEPENDENCY_RECORDED = "DEPENDENCY_RECORDED"
    MESSAGE_PARSED = "MESSAGE_PARSED"
    MESSAGE_PARSE_FAILED = "MESSAGE_PARSE_FAILED"
    MESSAGE_DELIVERED = "MESSAGE_DELIVERED"
    AGENT_STATE_SNAPSHOTTED = "AGENT_STATE_SNAPSHOTTED"
    AGGREGATION_COMPLETED = "AGGREGATION_COMPLETED"


class ContextRef(ContractModel):
    """Stable per-sample document locator; it is not a global document ID."""

    sample_id: str = Field(min_length=1)
    context_index: int = Field(ge=0)

    @property
    def key(self) -> str:
        return f"{self.sample_id}:context:{self.context_index}"


class DocumentSentence(ContractModel):
    sentence_index: int = Field(ge=0)
    text: str


class Question(ContractModel):
    """Agent-visible question. The gold answer is intentionally absent."""

    schema_version: Literal["0.1"] = PLATFORM_SCHEMA_VERSION
    question_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    dataset_ref: str = Field(min_length=1)
    question_type: str | None = None
    reasoning_hop_count: int | None = Field(default=None, ge=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class Document(ContractModel):
    schema_version: Literal["0.1"] = PLATFORM_SCHEMA_VERSION
    sample_id: str = Field(min_length=1)
    context_index: int = Field(ge=0)
    truth_context_id: str | None = Field(default=None, min_length=1)
    title: str | None
    text: str
    sentences: tuple[DocumentSentence, ...] = ()
    is_supporting_context: bool
    raw_locator: dict[str, JsonValue] = Field(default_factory=dict)

    @property
    def context_ref(self) -> ContextRef:
        return ContextRef(sample_id=self.sample_id, context_index=self.context_index)

    @model_validator(mode="after")
    def unique_native_sentence_indexes(self) -> "Document":
        indexes = [sentence.sentence_index for sentence in self.sentences]
        if len(indexes) != len(set(indexes)):
            raise ValueError("Document sentence_index values must be unique")
        return self


class EvidenceRef(ContractModel):
    """A declared locator, not an automatic semantic-entailment verdict."""

    evidence_id: str = Field(min_length=1)
    context_ref: ContextRef
    granularity: SourceGranularity
    sentence_ids: tuple[int, ...] = ()
    paragraph_idx: int | None = Field(default=None, ge=0)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    truth_source_id: str | None = None
    locator_origin: Literal["official_gold", "derived"] | None = None
    reference_origin: ReferenceOrigin
    link_relation: Literal["entails", "joint_entailment", "supports"] | None = None
    link_validation_status: Literal["accepted"] | None = None
    structural_confidence: float | None = Field(default=None, ge=0, le=1)
    requires_human_audit: bool = True
    raw_locator: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_locator(self) -> "EvidenceRef":
        if self.granularity in {SourceGranularity.SENTENCE, SourceGranularity.SENTENCE_SET}:
            if not self.sentence_ids:
                raise ValueError("sentence evidence requires sentence_ids")
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError("char_start and char_end must be set together")
        if self.char_start is not None and self.char_end <= self.char_start:
            raise ValueError("char_end must be greater than char_start")
        return self


class AtomicClaim(ContractModel):
    claim_id: str = Field(min_length=1)
    claim_text: str = Field(min_length=1)
    source_refs: tuple[EvidenceRef, ...] = ()
    confidence: float | None = Field(default=None, ge=0, le=1)
    qualification: str | None = None
    parent_claim_ids: tuple[str, ...] = ()
    communication_hop: int = Field(default=0, ge=0)
    truth_claim_id: str | None = None
    truth_annotation_status: Literal[
        "candidate", "silver", "gold_audit", "rejected"
    ] | None = None
    derivation_operator: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_references(self) -> "AtomicClaim":
        if len(self.parent_claim_ids) != len(set(self.parent_claim_ids)):
            raise ValueError("parent_claim_ids must be unique")
        evidence_ids = [ref.evidence_id for ref in self.source_refs]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("source_refs must have unique evidence_id values")
        return self


class StructuredPayload(ContractModel):
    payload_type: Literal["structured"] = "structured"
    message_status: MessageStatus
    claims: tuple[AtomicClaim, ...] = ()
    summary: str | None = None

    @model_validator(mode="after")
    def status_matches_claims(self) -> "StructuredPayload":
        if self.message_status is MessageStatus.CONTENT and not self.claims:
            raise ValueError("content structured payload requires at least one claim")
        if self.message_status is MessageStatus.NO_NEW_INFORMATION and self.claims:
            raise ValueError("no_new_information structured payload must have no claims")
        return self


class ContractValidationIssue(ContractModel):
    category: Literal["schema_validation", "status_claims_inconsistent"]
    field_path: str = Field(min_length=1)
    error_type: str = Field(min_length=1)


class ProviderContractDiagnostic(ContractModel):
    """Evaluator/operator-only failure structure; never a model response or Agent payload."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    error_category: Literal["structured_payload_contract"] = "structured_payload_contract"
    request_id: str
    question_id: str
    stage: Stage
    round: int = Field(ge=0)
    attempt: int = Field(ge=1)
    response_text_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    error_count: int = Field(ge=1)
    issues: tuple[ContractValidationIssue, ...]


class FreeTextPayload(ContractModel):
    payload_type: Literal["free_text"] = "free_text"
    message_status: MessageStatus
    text: str
    declared_source_refs: tuple[EvidenceRef, ...] = ()

    @model_validator(mode="after")
    def status_matches_text(self) -> "FreeTextPayload":
        if self.message_status is MessageStatus.CONTENT and not self.text.strip():
            raise ValueError("content free-text payload requires non-empty text")
        if self.message_status is MessageStatus.NO_NEW_INFORMATION and self.text.strip():
            raise ValueError("no_new_information free-text payload must be empty")
        return self


MessagePayload = Annotated[
    StructuredPayload | FreeTextPayload,
    Field(discriminator="payload_type"),
]


class RuntimeNodeKind(StrEnum):
    INITIAL_OUTPUT = "initial_output"
    COMMUNICATION_OUTPUT = "communication_output"


class DependencyKind(StrEnum):
    SELF_INITIAL = "self_initial"
    RECEIVED_MESSAGE = "received_message"


class RuntimeMessageNode(ContractModel):
    """Canonical post-parse model output used by the runtime communication DAG."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    node_id: str = Field(min_length=1)
    node_kind: RuntimeNodeKind
    run_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    sender_id: str = Field(min_length=1)
    receiver_id: str = Field(min_length=1)
    stage: Stage
    round: int = Field(ge=0)
    communication_hop: int = Field(ge=0)
    visible_document_refs: tuple[ContextRef, ...] = ()
    payload: MessagePayload
    request_id: str = Field(min_length=1)
    response_id: str = Field(min_length=1)
    prompt_ref: str = Field(min_length=1)
    model_ref: str = Field(min_length=1)
    visible_input_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    created_at: datetime

    @model_validator(mode="after")
    def enforce_node_protocol(self) -> "RuntimeMessageNode":
        if self.created_at.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        if self.node_kind is RuntimeNodeKind.INITIAL_OUTPUT:
            if self.stage is not Stage.INITIAL_READ or self.round != 0 or self.communication_hop != 0:
                raise ValueError("initial_output requires initial_read round=0 and communication_hop=0")
            if self.receiver_id != self.sender_id:
                raise ValueError("initial_output receiver_id must equal sender_id")
        else:
            if self.stage is not Stage.COMMUNICATION or self.round < 1 or self.communication_hop != self.round:
                raise ValueError("communication_output requires communication round>=1 and matching hop")
            if self.visible_document_refs:
                raise ValueError("communication_output cannot expose raw documents")
        if len(self.visible_document_refs) != len({ref.key for ref in self.visible_document_refs}):
            raise ValueError("visible_document_refs must be unique")
        return self


class DependencyRecord(ContractModel):
    """Input visibility edge; it deliberately contains no semantic judgment."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    dependency_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    parent_node_id: str = Field(min_length=1)
    child_node_id: str = Field(min_length=1)
    dependency_kind: DependencyKind
    parent_round: int = Field(ge=0)
    child_round: int = Field(ge=1)
    visible_claim_ids: tuple[str, ...] = ()
    available_to_child: Literal[True] = True

    @model_validator(mode="after")
    def enforce_dependency_protocol(self) -> "DependencyRecord":
        if self.parent_node_id == self.child_node_id:
            raise ValueError("dependency self-loop is forbidden")
        if self.parent_round >= self.child_round:
            raise ValueError("dependency parent_round must be less than child_round")
        if len(self.visible_claim_ids) != len(set(self.visible_claim_ids)):
            raise ValueError("visible_claim_ids must be unique")
        if self.dependency_kind is DependencyKind.SELF_INITIAL and self.parent_round != 0:
            raise ValueError("self_initial dependency must originate at round 0")
        return self


class MessageEnvelope(ContractModel):
    schema_version: Literal["0.1"] = PLATFORM_SCHEMA_VERSION
    message_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    stage: Stage
    round: int = Field(ge=0)
    communication_hop: int = Field(ge=0)
    sender_id: str = Field(min_length=1)
    receiver_id: str = Field(min_length=1)
    message_format: MessageFormat
    payload: MessagePayload
    parent_message_ids: tuple[str, ...] = ()
    created_at: datetime
    prompt_ref: str = Field(min_length=1)
    model_ref: str = Field(min_length=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def enforce_protocol(self) -> "MessageEnvelope":
        if self.created_at.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        if self.stage is Stage.INITIAL_READ and (self.round != 0 or self.communication_hop != 0):
            raise ValueError("initial_read requires round=0 and communication_hop=0")
        if self.stage is Stage.COMMUNICATION and self.round < 1:
            raise ValueError("communication requires round>=1")
        if MessageFormat(self.payload.payload_type) is not self.message_format:
            raise ValueError("message_format must match payload_type")
        if len(self.parent_message_ids) != len(set(self.parent_message_ids)):
            raise ValueError("parent_message_ids must be unique")
        return self


class AgentSpec(ContractModel):
    agent_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    prompt_profile: str = Field(min_length=1)


class DatasetConfig(ContractModel):
    adapter: Literal["data_truth_v3"]
    path: str = Field(min_length=1)
    schema_path: str = Field(min_length=1)
    expected_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    sample_ids: tuple[str, ...] = Field(min_length=1)
    repair_manifest_path: str | None = None
    expected_repair_manifest_sha256: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def repair_manifest_fields_are_paired(self) -> "DatasetConfig":
        if (self.repair_manifest_path is None) != (self.expected_repair_manifest_sha256 is None):
            raise ValueError("repair_manifest_path and expected_repair_manifest_sha256 must be supplied together")
        return self


class GateAConfig(ContractModel):
    kind: Literal["schema_and_relational_v3"]
    require_normalized: Literal[True] = True
    require_qualified: Literal[True] = True


class GateBConfig(ContractModel):
    kind: Literal["experiment_eligibility"]
    policy_registry: dict[str, dict[str, dict[str, str]]]

    @model_validator(mode="after")
    def nonempty_registry(self) -> "GateBConfig":
        if not self.policy_registry:
            raise ValueError("Gate B policy_registry must not be empty")
        for dataset, question_types in self.policy_registry.items():
            if not dataset or not question_types:
                raise ValueError("Gate B registry requires dataset and question-type entries")
            for question_type, policies in question_types.items():
                if not question_type or not policies or any(not name or not version for name, version in policies.items()):
                    raise ValueError("Gate B registry policy names and versions must be non-empty")
        return self


class GatesConfig(ContractModel):
    gate_a: GateAConfig
    gate_b: GateBConfig


class EligibilityConstraintsConfig(ContractModel):
    require_unique_longest_inference_path: Literal[True] = True
    require_question_type_hop_match: Literal[True] = True
    require_nonempty_unique_hop_evidence: Literal[True] = True
    require_disjoint_agent_contexts: Literal[True] = True
    require_all_gold_contexts_covered: Literal[True] = True
    final_claim_may_introduce_new_context: Literal[False] = False
    ambiguity_behavior: Literal["fail"] = "fail"


class EmptyAssignmentConfig(ContractModel):
    allowed_agents_by_question_type: dict[str, tuple[str, ...]]
    round_0_message_status: Literal["no_new_information"]
    round_0_claims: tuple[()] = ()


class DocumentAssignmentConfig(ContractModel):
    policy: Literal[
        "gold_partition_minimal_v1",
        "gold_partition_minimal_v2",
        "full_context_partition_v1",
        "gold_hop_partition_musique_v1",
        "gold_decomposition_step_partition_musique_v2",
    ]
    rule_version: str = Field(min_length=1)
    seed: int
    hop_count_basis: Literal["longest_inference_path_edge_count"] | None = None
    difficulty_basis: Literal["decomposition_step_count"] | None = None
    evidence_unit: Literal["decomposition_step"] | None = None
    graph_semantics: Literal["raw_hash_reference_dag"] | None = None
    eligibility_constraints: EligibilityConstraintsConfig | None = None
    include_distractors: bool | None = None
    record_unused_context_refs: bool | None = None
    empty_assignment: EmptyAssignmentConfig | None = None
    mappings: dict[str, dict[str, tuple[int, ...]]] | None = None

    @model_validator(mode="after")
    def musique_fields_are_explicit(self) -> "DocumentAssignmentConfig":
        if self.policy == "gold_hop_partition_musique_v1":
            required = (
                self.hop_count_basis,
                self.eligibility_constraints,
                self.include_distractors,
                self.record_unused_context_refs,
                self.empty_assignment,
                self.mappings,
            )
            if any(value is None for value in required):
                raise ValueError("MuSiQue policy requires all frozen eligibility and mapping fields")
            if self.include_distractors or self.record_unused_context_refs:
                raise ValueError("MuSiQue gold-only v1 forbids distractors and unused_context_refs")
        if self.policy == "gold_decomposition_step_partition_musique_v2":
            required = (
                self.difficulty_basis,
                self.evidence_unit,
                self.graph_semantics,
                self.include_distractors,
                self.record_unused_context_refs,
                self.empty_assignment,
                self.mappings,
            )
            if any(value is None for value in required):
                raise ValueError("MuSiQue v2 requires decomposition-step semantics and all frozen mapping fields")
            if self.include_distractors or self.record_unused_context_refs:
                raise ValueError("MuSiQue gold-only v2 forbids distractors and unused_context_refs")
            if self.hop_count_basis is not None or self.eligibility_constraints is not None:
                raise ValueError("MuSiQue v2 must not inherit v1 longest-path constraints")
        return self


class TopologyConfig(ContractModel):
    kind: Literal["chain", "star_bidirectional"]
    center_agent_id: str = "agent_2"


class ProtocolConfig(ContractModel):
    profile: Literal["legacy_engineering", "evaluation_ready_v1"] = "legacy_engineering"
    initial_read_round: Literal[0] = 0
    communication_rounds: Literal[0, 1, 2] = 2
    frozen_mailbox: Literal[True] = True
    raw_documents_after_initial_read: Literal[False] = False
    message_format: MessageFormat


class LineageReplayMockProviderConfig(ContractModel):
    kind: Literal["lineage_replay_mock"]
    version: str = Field(min_length=1)


class DeepSeekProviderConfig(ContractModel):
    kind: Literal["deepseek_openai_compatible"]
    api_style: Literal["chat_completions"]
    base_url: str = Field(min_length=1)
    model: str = Field(min_length=1)
    api_key_env: str = Field(min_length=1, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    timeout_seconds: float = Field(gt=0)
    stream: Literal[False] = False
    fallback_to_mock: Literal[False] = False
    preserve_raw_response: Literal[True] = True

    @model_validator(mode="after")
    def validate_base_url(self) -> "DeepSeekProviderConfig":
        value = self.base_url.rstrip("/")
        if not value.startswith("https://"):
            raise ValueError("DeepSeek base_url must use HTTPS")
        if value.endswith("/chat/completions"):
            raise ValueError("base_url must not include /chat/completions")
        return self


class VllmDeploymentConfig(ContractModel):
    dtype: Literal["bfloat16"] = "bfloat16"
    quantization: None = None
    max_model_len: Literal[8192] = 8192
    tensor_parallel_size: Literal[1] = 1
    gpu_memory_utilization: Literal[0.9] = 0.9


class VllmProviderConfig(ContractModel):
    kind: Literal["vllm_openai_compatible"]
    api_style: Literal["chat_completions"]
    base_url: Literal["http://127.0.0.1:8000/v1"]
    model: Literal["qwen3-8b-m1"]
    model_repository: Literal["Qwen/Qwen3-8B"]
    model_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    deployment_manifest_path: str = Field(min_length=1)
    deployment_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    timeout_seconds: float = Field(gt=0)
    healthcheck: Literal[True] = True
    stream: Literal[False] = False
    fallback_to_mock: Literal[False] = False
    preserve_raw_response: Literal[True] = True
    deployment: VllmDeploymentConfig


ProviderConfig = Annotated[
    LineageReplayMockProviderConfig | DeepSeekProviderConfig | VllmProviderConfig,
    Field(discriminator="kind"),
]


class GenerationConfig(ContractModel):
    thinking: "ThinkingConfig | None" = None
    response_format: Literal["json_object"] = "json_object"
    temperature: float = Field(default=0.0, ge=0, le=2)
    max_output_tokens: int = Field(default=1024, ge=1)
    prompt_requires_json_instruction: Literal[True] = True


class ThinkingConfig(ContractModel):
    type: Literal["enabled", "disabled"]


RetryableProviderErrorCode = Literal[
    "PROVIDER_CONNECTION_ERROR",
    "PROVIDER_TIMEOUT",
    "PROVIDER_RATE_LIMITED",
    "PROVIDER_SERVER_ERROR",
]


class RetryConfig(ContractModel):
    initial_backoff_seconds: float = Field(ge=0)
    max_backoff_seconds: float = Field(ge=0)
    honor_retry_after: bool = True
    retryable_error_codes: tuple[RetryableProviderErrorCode, ...]

    @model_validator(mode="after")
    def backoff_is_bounded(self) -> "RetryConfig":
        if self.initial_backoff_seconds > self.max_backoff_seconds:
            raise ValueError("initial_backoff_seconds must not exceed max_backoff_seconds")
        if len(self.retryable_error_codes) != len(set(self.retryable_error_codes)):
            raise ValueError("retryable_error_codes must be unique")
        return self


class ExecutionConfig(ContractModel):
    checkpoint_granularity: Literal["question"]
    resume_policy: Literal["skip_completed"]
    max_attempts_per_request: int = Field(ge=1)
    max_total_model_attempts: int = Field(ge=1)
    retry: RetryConfig
    continue_after_question_failure: Literal[True] = True
    persist_after_each_question: Literal[True] = True


class AggregationConfig(ContractModel):
    kind: Literal["union"]
    version: str = Field(min_length=1)


class RandomnessConfig(ContractModel):
    seed: int
    replicate_id: str = Field(min_length=1)


class OutputConfig(ContractModel):
    runs_dir: str = Field(min_length=1)


class PromptRegistryConfig(ContractModel):
    path: str = Field(min_length=1)
    expected_sha256: str = Field(pattern="^[0-9a-f]{64}$")


class M3ConditionConfig(ContractModel):
    condition_id: Literal["M", "B0", "B1", "A1", "A2"]
    model_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    replicate_id: str = Field(min_length=1)
    prompt_ref: str = Field(min_length=1)
    prompt_registry: PromptRegistryConfig
    terminal_union_ref: Literal["terminal-offline-union@1.0.0"] = "terminal-offline-union@1.0.0"
    parent_projection_ref: Literal["identity@1.0.0", "hide-source-refs@1.0.0"]
    run_intent: Literal["development", "e_ready_pilot", "formal_batch"] = "development"


class ExperimentConfig(ContractModel):
    schema_version: Literal["0.1"] = PLATFORM_SCHEMA_VERSION
    config_version: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    dataset: DatasetConfig
    gates: GatesConfig
    document_assignment: DocumentAssignmentConfig
    agents: tuple[AgentSpec, ...] = Field(min_length=3, max_length=3)
    topology: TopologyConfig
    protocol: ProtocolConfig
    provider: ProviderConfig
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    execution: ExecutionConfig | None = None
    aggregation: AggregationConfig
    randomness: RandomnessConfig
    output: OutputConfig
    m3_condition: M3ConditionConfig | None = None

    @model_validator(mode="after")
    def exactly_three_unique_agents(self) -> "ExperimentConfig":
        ids = [agent.agent_id for agent in self.agents]
        if len(ids) != len(set(ids)):
            raise ValueError("agent_id values must be unique")
        if set(ids) != {"agent_1", "agent_2", "agent_3"}:
            raise ValueError("M0 requires agent_1, agent_2, and agent_3")
        if self.topology.kind == "star_bidirectional" and self.topology.center_agent_id not in ids:
            raise ValueError("star center must reference an existing agent")
        if self.document_assignment.policy == "gold_decomposition_step_partition_musique_v2":
            accepted_gold_167 = self.dataset.expected_sha256 == \
                "c6f3f1b3eeb4e954d14f900747e1aaeb176512b8ba70d0ab3ab94d2cfdd2d4b5"
            # Permit the English publication derivative only in mock development.
            localized_mock = (
                self.dataset.expected_sha256 == "c9b641e9483c8677bfa2c3f8d79543c32ddb920d72fb4ccaec1de2793ec8a067"
                and self.provider.kind == "lineage_replay_mock"
                and self.m3_condition is not None
                and self.m3_condition.run_intent == "development"
                and "@english-localized:sha256:" in self.m3_condition.dataset_id
            )
            accepted_gold_167 = accepted_gold_167 or localized_mock
            if self.dataset.repair_manifest_path is None and not accepted_gold_167:
                raise ValueError("MuSiQue v2 requires a frozen repair manifest or the accepted 167-item gold core")
            if self.protocol.message_format is not MessageFormat.STRUCTURED:
                raise ValueError("MuSiQue v2 formal profile is structured-only")
        if self.protocol.profile == "evaluation_ready_v1" and self.protocol.message_format is not MessageFormat.STRUCTURED:
            raise ValueError("evaluation_ready_v1 is structured-only")
        if isinstance(self.provider, DeepSeekProviderConfig):
            if self.protocol.profile != "evaluation_ready_v1":
                raise ValueError("DeepSeek formal runs require evaluation_ready_v1")
            if self.protocol.message_format is not MessageFormat.STRUCTURED:
                raise ValueError("DeepSeek provider is structured-only")
            if self.generation.thinking is None:
                raise ValueError("DeepSeek provider requires explicit generation.thinking")
        if isinstance(self.provider, VllmProviderConfig):
            if self.protocol.profile != "evaluation_ready_v1":
                raise ValueError("vLLM formal runs require evaluation_ready_v1")
            if self.protocol.message_format is not MessageFormat.STRUCTURED:
                raise ValueError("vLLM provider is structured-only")
            if self.generation.thinking is None or self.generation.thinking.type != "disabled":
                raise ValueError("vLLM Qwen3 provider requires generation.thinking.type=disabled")
        if self.m3_condition is not None:
            condition = self.m3_condition
            if condition.replicate_id != self.randomness.replicate_id:
                raise ValueError("M3 replicate_id must match randomness.replicate_id")
            if self.protocol.profile != "evaluation_ready_v1" or self.protocol.message_format is not MessageFormat.STRUCTURED:
                raise ValueError("M3 conditions require evaluation_ready_v1 structured protocol")
            expected_rounds = 0 if condition.condition_id in {"B0", "B1"} else 1
            if self.protocol.communication_rounds != expected_rounds:
                raise ValueError(f"M3 condition {condition.condition_id} requires communication_rounds={expected_rounds}")
            expected_projection = "hide-source-refs@1.0.0" if condition.condition_id == "A1" else "identity@1.0.0"
            if condition.parent_projection_ref != expected_projection:
                raise ValueError(f"M3 condition {condition.condition_id} requires projection {expected_projection}")
            is_2wiki = condition.dataset_id.startswith("2wiki-audit-gold-400@")
            is_musique = condition.dataset_id.startswith("musique-final-gold-167@")
            if not (is_2wiki or is_musique):
                raise ValueError("M3 dataset_id must identify the frozen 2Wiki-400 or MuSiQue-167 release")
            if condition.condition_id in {"A1", "A2"} and not is_2wiki:
                raise ValueError("A1 and A2 are permitted only for 2Wiki")
        return self


class ProviderMessage(ContractModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class ModelRequest(ContractModel):
    schema_version: Literal["0.1"] = PLATFORM_SCHEMA_VERSION
    request_id: str = Field(min_length=1)
    provider_ref: str = Field(min_length=1)
    model: str = Field(min_length=1)
    messages: tuple[ProviderMessage, ...] = Field(min_length=1)
    output_format: MessageFormat
    output_schema_version: str | None = None
    prompt_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    prompt_content_hash: str = Field(pattern="^[0-9a-f]{64}$")
    run_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    stage: Stage
    round: int = Field(ge=0)
    receiver_id: str
    replicate_id: str = Field(min_length=1)
    request_context: dict[str, JsonValue] = Field(default_factory=dict)

    def cache_material(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        for key in ("request_id", "run_id", "question_id", "agent_id", "stage", "round", "receiver_id"):
            data.pop(key, None)
        return data


class TokenUsage(ContractModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class ModelResponse(ContractModel):
    schema_version: Literal["0.1"] = PLATFORM_SCHEMA_VERSION
    response_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    provider_ref: str = Field(min_length=1)
    model: str = Field(min_length=1)
    raw_response: JsonValue
    provider_raw_response: JsonValue | None = None
    raw_text: str
    request_model: str | None = None
    response_model: str | None = None
    provider_metadata: dict[str, JsonValue] = Field(default_factory=dict)
    finish_reason: str | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)
    latency_ms: float = Field(ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    provider_request_id: str | None = None
    cache_hit: bool = False
    parse_status: ParseStatus = ParseStatus.NOT_APPLICABLE
    parse_warnings: tuple[str, ...] = ()
    parse_error: str | None = None
    received_at: datetime

    @model_validator(mode="after")
    def response_time_and_parse(self) -> "ModelResponse":
        if self.received_at.utcoffset() is None:
            raise ValueError("received_at must include a timezone")
        if self.parse_status is ParseStatus.FAILED and not self.parse_error:
            raise ValueError("failed parsing requires parse_error")
        return self


class TraceEvent(ContractModel):
    schema_version: Literal["0.1"] = PLATFORM_SCHEMA_VERSION
    event_id: str = Field(min_length=1)
    event_type: TraceEventType
    timestamp: datetime
    run_id: str = Field(min_length=1)
    question_id: str | None = None
    stage: Stage | None = None
    round: int | None = Field(default=None, ge=0)
    agent_id: str | None = None
    message_id: str | None = None
    attempt: int | None = Field(default=None, ge=1)
    event_data: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def timezone_required(self) -> "TraceEvent":
        if self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return self


class DatasetTruthProvenance(ContractModel):
    schema_version: Literal["3.0"] = DATA_TRUTH_SCHEMA_VERSION
    dataset_name: str = Field(min_length=1)
    release: str = Field(min_length=1)
    split: str = Field(min_length=1)
    source_file: str = Field(min_length=1)
    file_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    adapter_version: str = Field(min_length=1)
    sample_raw_locator: dict[str, JsonValue] = Field(default_factory=dict)
    semantic_screening_method: str | None = None
    semantic_screening_model: str | None = None
    semantic_screening_prompt_version: str | None = None
    validation_status: str | None = None
    requires_human_audit: bool = True


class TruthClaim(ContractModel):
    """Evaluator-only claim copied verbatim from frozen Data Truth 3.0."""

    claim_id: str = Field(min_length=1)
    claim_text: str = Field(min_length=1)
    claim_kind: Literal["direct", "derived"]
    structured_form: dict[str, JsonValue] | None = None
    annotation_status: Literal["silver", "gold_audit"]


class TruthDocumentSentence(ContractModel):
    sent_id: int = Field(ge=0)
    text: str
    raw_locator: dict[str, JsonValue] = Field(default_factory=dict)


class TruthDocument(ContractModel):
    """Complete evaluator catalog entry, including distractors."""

    context_id: str = Field(min_length=1)
    title: str | None = None
    text: str
    sentences: tuple[TruthDocumentSentence, ...] = ()
    is_supporting_context: bool
    raw_locator: dict[str, JsonValue] = Field(default_factory=dict)


class TruthSourceLocator(ContractModel):
    source_id: str = Field(min_length=1)
    context_id: str = Field(min_length=1)
    context_ref: ContextRef
    title: str | None = None
    granularity: SourceGranularity
    paragraph_idx: int | None = Field(default=None, ge=0)
    sent_id: int | None = Field(default=None, ge=0)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    text: str
    source_origin: str = Field(min_length=1)
    locator_status: str = Field(min_length=1)
    raw_locator: dict[str, JsonValue] = Field(default_factory=dict)


class CanonicalSourceSet(ContractModel):
    """One accepted frozen claim-source link; canonical does not imply gold audit."""

    claim_id: str = Field(min_length=1)
    source_ids: tuple[str, ...] = Field(min_length=1)
    source_locators: tuple[TruthSourceLocator, ...] = Field(min_length=1)
    relation: Literal["entails", "joint_entailment", "supports"]
    validation_status: Literal["accepted"]
    needs_review: bool
    reviewer: str | None = None
    review_timestamp: str | None = None

    @model_validator(mode="after")
    def source_ids_match_locators(self) -> "CanonicalSourceSet":
        if self.source_ids != tuple(locator.source_id for locator in self.source_locators):
            raise ValueError("source_ids must match source_locators in order")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("canonical source IDs must be unique")
        return self


class TruthReasoningEdge(ContractModel):
    from_claim_id: str = Field(min_length=1)
    to_claim_id: str = Field(min_length=1)
    edge_type: str = Field(min_length=1)


class TruthReasoningGraph(ContractModel):
    graph_type: str = Field(min_length=1)
    hop_count: int = Field(ge=1)
    root_claim_ids: tuple[str, ...] = Field(min_length=1)
    edges: tuple[TruthReasoningEdge, ...] = ()


class EvaluationTruthView(ContractModel):
    """Privileged, post-run evaluator view. Never an Agent/runtime input."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    sample_id: str = Field(min_length=1)
    answer: str
    answer_aliases: tuple[str, ...] = ()
    truth_claims: tuple[TruthClaim, ...] = Field(min_length=1)
    canonical_source_sets: tuple[CanonicalSourceSet, ...] = Field(min_length=1)
    reasoning_graph: TruthReasoningGraph
    complete_document_catalog: tuple[TruthDocument, ...] = Field(min_length=1)
    optional_minimal_source_sets: None = None
    truth_artifact_sha256: str = Field(pattern="^[0-9a-f]{64}$")


class PlatformInputBundle(ContractModel):
    schema_version: Literal["0.1"] = PLATFORM_SCHEMA_VERSION
    question: Question
    documents: tuple[Document, ...] = Field(min_length=1)
    seed_claims: tuple[AtomicClaim, ...] = Field(min_length=1)
    truth_reasoning_graph: dict[str, JsonValue]
    truth_provenance: DatasetTruthProvenance


class AssignmentSnapshot(ContractModel):
    schema_version: Literal["0.1"] = PLATFORM_SCHEMA_VERSION
    question_id: str = Field(min_length=1)
    policy: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    seed: int
    difficulty_basis: str | None = None
    difficulty_value: int | str | None = None
    dataset_hop_label: int | None = Field(default=None, ge=1)
    decomposition_step_count: int | None = Field(default=None, ge=1)
    dependency_graph_hop_count: int | None = Field(default=None, ge=1)
    question_template: str | None = None
    step_claim_ids: tuple[str, ...] = ()
    step_evidence_units: tuple[tuple[ContextRef, ...], ...] = ()
    step_source_ids: tuple[tuple[str, ...], ...] = ()
    edge_type_counts: dict[str, int] = Field(default_factory=dict)
    agent_step_positions: dict[str, tuple[int, ...]] = Field(default_factory=dict)
    partition_basis: str | None = None
    branch_claim_ids: tuple[tuple[str, ...], ...] = ()
    inferred_missing_edges: tuple[tuple[str, str], ...] = ()
    assignments: dict[str, tuple[ContextRef, ...]]
    unused_context_refs: tuple[ContextRef, ...] = ()


class GateBResult(ContractModel):
    sample_id: str = Field(min_length=1)
    dataset_name: str = Field(min_length=1)
    eligible: bool
    policy: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    difficulty_basis: str = Field(min_length=1)
    difficulty_value: int | str | None = None
    dataset_hop_label: int | None = Field(default=None, ge=1)
    decomposition_step_count: int | None = Field(default=None, ge=1)
    dependency_graph_hop_count: int | None = Field(default=None, ge=1)
    question_template: str | None = None
    step_claim_ids: tuple[str, ...] = ()
    step_evidence_units: tuple[tuple[ContextRef, ...], ...] = ()
    step_source_ids: tuple[tuple[str, ...], ...] = ()
    edge_type_counts: dict[str, int] = Field(default_factory=dict)
    agent_step_positions: dict[str, tuple[int, ...]] = Field(default_factory=dict)
    partition_basis: str | None = None
    branch_claim_ids: tuple[tuple[str, ...], ...] = ()
    inferred_missing_edges: tuple[tuple[str, str], ...] = ()
    assignments: dict[str, tuple[ContextRef, ...]]
    unused_context_refs: tuple[ContextRef, ...] = ()
    inference_path_claim_ids: tuple[str, ...] = ()
    hop_evidence_units: tuple[tuple[ContextRef, ...], ...] = ()
    failure_code: Literal[
        "POLICY_NOT_REGISTERED",
        "QUESTION_TYPE_UNSUPPORTED",
        "HOP_COUNT_MISMATCH",
        "GOLD_PATH_NOT_UNIQUE",
        "HOP_EVIDENCE_NOT_UNIQUE",
        "GOLD_CONTEXT_OVERLAP",
        "GOLD_CONTEXT_UNCOVERED",
        "AGENT_ASSIGNMENT_INVALID",
        "STEP_SOURCE_GROUP_MISSING",
        "STEP_SOURCE_GROUP_AMBIGUOUS",
        "SOURCE_ASSIGNED_MORE_THAN_ONCE",
        "ASSIGNMENT_COVERAGE_MISMATCH",
    ] | None = None
    failure_detail: str | None = None

    @model_validator(mode="after")
    def status_is_consistent(self) -> "GateBResult":
        if self.eligible and (self.failure_code is not None or self.failure_detail is not None):
            raise ValueError("eligible Gate B result cannot contain failure fields")
        if not self.eligible and (self.failure_code is None or not self.failure_detail):
            raise ValueError("ineligible Gate B result requires failure_code and failure_detail")
        return self


class GateBReport(ContractModel):
    gate: Literal["gate_b"] = "gate_b"
    kind: Literal["experiment_eligibility"] = "experiment_eligibility"
    status: Literal["pass", "fail"]
    selected_samples: int = Field(ge=1)
    eligible_samples: int = Field(ge=0)
    ineligible_samples: int = Field(ge=0)
    results: tuple[GateBResult, ...]

    @model_validator(mode="after")
    def counts_are_consistent(self) -> "GateBReport":
        if self.selected_samples != len(self.results):
            raise ValueError("Gate B selected_samples must equal result count")
        if self.eligible_samples + self.ineligible_samples != self.selected_samples:
            raise ValueError("Gate B eligible/ineligible counts must sum to selected_samples")
        if self.eligible_samples != sum(result.eligible for result in self.results):
            raise ValueError("Gate B eligible count mismatch")
        if (self.status == "pass") != (self.ineligible_samples == 0):
            raise ValueError("Gate B report status/count mismatch")
        return self


class FreeTextRecord(ContractModel):
    text: str = Field(min_length=1)
    source_refs: tuple[EvidenceRef, ...] = ()
    contributing_message_ids: tuple[str, ...] = ()


class AgentStateSnapshot(ContractModel):
    schema_version: Literal["0.1"] = PLATFORM_SCHEMA_VERSION
    run_id: str
    question_id: str
    agent_id: str
    round: int = Field(ge=0)
    message_format: MessageFormat
    private_initial_claims: tuple[AtomicClaim, ...] = ()
    received_message_ids: tuple[str, ...] = ()
    current_structured_claims: tuple[AtomicClaim, ...] = ()
    current_free_text_records: tuple[FreeTextRecord, ...] = ()
    created_at: datetime

    @model_validator(mode="after")
    def timezone_required(self) -> "AgentStateSnapshot":
        if self.created_at.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        return self


class AggregatedClaim(ContractModel):
    normalized_text: str
    claim_text: str
    source_refs: tuple[EvidenceRef, ...]
    contributing_claim_ids: tuple[str, ...]
    contributing_agent_ids: tuple[str, ...]


class AggregatedResult(ContractModel):
    schema_version: Literal["0.1"] = PLATFORM_SCHEMA_VERSION
    run_id: str
    question_id: str
    message_format: MessageFormat
    claims: tuple[AggregatedClaim, ...] = ()
    free_text_records: dict[str, tuple[FreeTextRecord, ...]] = Field(default_factory=dict)
    aggregator_kind: Literal["union"] = "union"
    aggregator_version: str
    created_at: datetime

    @model_validator(mode="after")
    def timezone_required(self) -> "AggregatedResult":
        if self.created_at.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        return self


class InputArtifactRef(ContractModel):
    path: str
    sha256: str = Field(pattern="^[0-9a-f]{64}$")
    schema_version: str
    dataset_name: str | None = None
    release: str | None = None
    split: str | None = None


class PromptSnapshot(ContractModel):
    prompt_id: str
    version: str
    content_hash: str = Field(pattern="^[0-9a-f]{64}$")
    snapshot_path: str | None = None
    component_hashes: dict[str, str] = Field(default_factory=dict)
    prompt_set_hash: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")


class ProviderSnapshot(ContractModel):
    provider_ref: str
    provider_kind: str
    model: str
    model_revision: str | None = None
    model_repository: str | None = None
    deployment_manifest_sha256: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")
    deployment: dict[str, JsonValue] = Field(default_factory=dict)
    api_style: str | None = None
    base_url: str | None = None
    request_model: str | None = None
    response_model: str | None = None
    generation: dict[str, JsonValue] = Field(default_factory=dict)
    accessed_at: datetime | None = None

    @model_validator(mode="after")
    def timezone_required(self) -> "ProviderSnapshot":
        if self.accessed_at is not None and self.accessed_at.utcoffset() is None:
            raise ValueError("accessed_at must include a timezone")
        return self


class RunManifest(ContractModel):
    schema_version: Literal["0.1"] = PLATFORM_SCHEMA_VERSION
    run_id: str
    status: RunStatus
    experiment_id: str
    condition_id: str | None = None
    model_id: str | None = None
    dataset_id: str | None = None
    config_version: str
    config_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    code_tree_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    input_artifacts: tuple[InputArtifactRef, ...]
    selected_sample_ids: tuple[str, ...]
    trace_path: str
    input_snapshot_path: str
    assignment_snapshot_path: str
    gate_b_report_path: str
    repair_manifest_path: str | None = None
    repair_manifest_sha256: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")
    repair_rule_version: str | None = None
    messages_path: str
    message_nodes_path: str
    message_nodes_schema_version: Literal["1.0.0"] = "1.0.0"
    message_node_count: int = Field(ge=0)
    dependency_records_path: str
    dependency_records_schema_version: Literal["1.0.0"] = "1.0.0"
    dependency_record_count: int = Field(ge=0)
    agent_states_path: str
    aggregated_result_path: str
    summary_path: str
    git_commit: None = None
    git_dirty: None = None
    python_version: str
    dependencies: dict[str, str]
    random_seed: int
    replicate_id: str
    topology_kind: str
    communication_rounds: int
    message_format: MessageFormat
    protocol_profile: Literal["legacy_engineering", "evaluation_ready_v1"]
    document_assignment_policy: str
    providers: tuple[ProviderSnapshot, ...]
    prompts: tuple[PromptSnapshot, ...]
    prompt_registry_sha256: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")
    condition_contract_path: str | None = None
    request_reconstruction_path: str | None = None
    parent_projection_path: str | None = None
    run_state_path: str | None = None
    question_checkpoint_dir: str | None = None
    logical_model_requests: int = Field(default=0, ge=0)
    total_model_attempts: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    started_at: datetime
    finished_at: datetime | None = None
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def timezone_required(self) -> "RunManifest":
        if self.started_at.utcoffset() is None:
            raise ValueError("started_at must include a timezone")
        if self.finished_at is not None and self.finished_at.utcoffset() is None:
            raise ValueError("finished_at must include a timezone")
        return self


class RunSummary(ContractModel):
    schema_version: Literal["0.1"] = PLATFORM_SCHEMA_VERSION
    run_id: str
    status: RunStatus
    questions_total: int = Field(ge=0)
    questions_completed: int = Field(ge=0)
    questions_failed: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    messages_delivered: int = Field(ge=0)
    message_nodes: int = Field(ge=0)
    dependency_records: int = Field(ge=0)
    trace_events: int = Field(ge=0)
    logical_model_requests: int = Field(default=0, ge=0)
    total_model_attempts: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    formal_metrics_computed: Literal[False] = False


class QuestionStateEntry(ContractModel):
    status: QuestionRunStatus = QuestionRunStatus.PENDING
    attempt_count: int = Field(default=0, ge=0)
    checkpoint_path: str | None = None
    failure_code: str | None = None
    failure_detail: str | None = None


class RunState(ContractModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    run_id: str
    status: RunStatus
    config_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    code_tree_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    input_artifact_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    schema_artifact_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    repair_manifest_sha256: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")
    identity_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    prompt_id: str
    prompt_version: str
    prompt_hash: str = Field(pattern="^[0-9a-f]{64}$")
    provider_snapshot: dict[str, JsonValue]
    generation_snapshot: dict[str, JsonValue]
    selected_sample_ids: tuple[str, ...]
    questions: dict[str, QuestionStateEntry]
    logical_model_requests: int = Field(default=0, ge=0)
    total_model_attempts: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    started_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None

    @model_validator(mode="after")
    def timestamps_are_timezone_aware(self) -> "RunState":
        for value in (self.started_at, self.updated_at, self.finished_at):
            if value is not None and value.utcoffset() is None:
                raise ValueError("run-state timestamps must include timezone")
        if tuple(self.questions) != self.selected_sample_ids:
            raise ValueError("run-state questions must preserve selected_sample_ids order")
        return self


class QuestionCheckpoint(ContractModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    run_id: str
    question_id: str
    status: QuestionRunStatus
    attempt_count: int = Field(ge=0)
    assignment: AssignmentSnapshot | None = None
    nodes: tuple[RuntimeMessageNode, ...] = ()
    dependencies: tuple[DependencyRecord, ...] = ()
    messages: tuple[MessageEnvelope, ...] = ()
    agent_states: tuple[AgentStateSnapshot, ...] = ()
    aggregated_result: AggregatedResult | None = None
    request_reconstructions: tuple[dict[str, JsonValue], ...] = ()
    parent_projections: tuple[dict[str, JsonValue], ...] = ()
    terminal_observations: tuple[dict[str, JsonValue], ...] = ()
    failure_code: str | None = None
    failure_detail: str | None = None
    created_at: datetime

    @model_validator(mode="after")
    def terminal_shape(self) -> "QuestionCheckpoint":
        if self.created_at.utcoffset() is None:
            raise ValueError("checkpoint created_at must include timezone")
        artifacts = bool(self.nodes or self.dependencies or self.messages or self.agent_states or
                         self.aggregated_result or self.request_reconstructions or
                         self.parent_projections or self.terminal_observations)
        if self.status is QuestionRunStatus.COMPLETED:
            if self.assignment is None or self.aggregated_result is None or not self.nodes:
                raise ValueError("completed checkpoint requires canonical question artifacts")
            if self.failure_code is not None or self.failure_detail is not None:
                raise ValueError("completed checkpoint cannot contain failure")
        elif self.status is QuestionRunStatus.FAILED:
            if artifacts or self.assignment is not None:
                raise ValueError("failed checkpoint cannot contain partial canonical artifacts")
            if not self.failure_code or not self.failure_detail:
                raise ValueError("failed checkpoint requires sanitized failure")
        else:
            raise ValueError("question checkpoint must be terminal")
        return self
