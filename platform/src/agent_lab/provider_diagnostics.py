"""Bounded, structural diagnostics for rejected Provider payloads.

Never persist ValidationError messages, inputs, contexts, or response text here.
"""

from __future__ import annotations

from hashlib import sha256

from pydantic import ValidationError

from agent_lab.domain.contracts_v0_1 import (
    ContractValidationIssue, ModelRequest, ProviderContractDiagnostic,
)


# Only names from the frozen StructuredPayload/AtomicClaim/EvidenceRef/ContextRef
# contract are allowed in persisted paths. Arbitrary model-supplied keys are masked.
_FIELD_NAMES = frozenset({
    "payload_type", "message_status", "claims", "summary",
    "claim_id", "claim_text", "source_refs", "confidence", "qualification",
    "parent_claim_ids", "communication_hop", "truth_claim_id",
    "truth_annotation_status", "derivation_operator", "metadata",
    "evidence_id", "context_ref", "granularity", "sentence_ids",
    "paragraph_idx", "char_start", "char_end", "truth_source_id",
    "locator_origin", "reference_origin", "link_relation",
    "link_validation_status", "structural_confidence", "requires_human_audit",
    "raw_locator", "sample_id", "context_index",
})

# Pydantic type identifiers are selected by code, never copied from its message.
_ERROR_TYPES = frozenset({
    "missing", "extra_forbidden", "string_type", "string_too_short",
    "tuple_type", "list_type", "model_type", "dict_type", "int_type",
    "int_parsing", "int_from_float", "greater_than_equal", "greater_than",
    "less_than_equal", "less_than", "float_type", "float_parsing",
    "literal_error", "enum", "bool_type", "value_error", "assertion_error",
    "none_required", "json_type", "finite_number",
})


def _safe_path(location: tuple[object, ...]) -> str:
    path = "$"
    for segment in location:
        if isinstance(segment, int) and not isinstance(segment, bool) and segment >= 0:
            path += f"[{segment}]"
        elif isinstance(segment, str) and segment in _FIELD_NAMES:
            path += f".{segment}"
        else:
            path += ".<unknown_field>"
    return path


def build_contract_diagnostic(error: ValidationError, request: ModelRequest,
                              response_text: str) -> ProviderContractDiagnostic:
    # include_input=False is defense in depth; only loc/type are ever used.
    details = error.errors(include_input=False, include_context=False, include_url=False)
    issues = []
    for item in details[:32]:
        location = tuple(item.get("loc", ()))
        raw_type = item.get("type")
        issues.append(ContractValidationIssue(
            category="status_claims_inconsistent" if not location else "schema_validation",
            field_path=_safe_path(location),
            error_type=raw_type if raw_type in _ERROR_TYPES else "other_validation_error",
        ))
    return ProviderContractDiagnostic(
        request_id=request.request_id, question_id=request.question_id,
        stage=request.stage, round=request.round, attempt=1,
        response_text_sha256=sha256(response_text.encode("utf-8")).hexdigest(),
        error_count=len(details), issues=tuple(issues),
    )
