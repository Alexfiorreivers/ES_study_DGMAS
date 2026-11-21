"""Privileged post-run loader for Data Truth Schema 3.0 evaluation views.

This module is intentionally disconnected from providers and the runtime.  It
loads truth only after a completed run and binds every view to the exact unified
JSONL artifact recorded by that run's manifest.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable, Mapping

from pydantic import ValidationError

from agent_lab.adapters.datasets import DataTruthV3Adapter, GateAValidationError
from agent_lab.adapters.datasets.data_truth_v3 import file_sha256
from agent_lab.domain.contracts_v0_1 import (
    CanonicalSourceSet,
    ContextRef,
    EvaluationTruthView,
    InputArtifactRef,
    RunManifest,
    RunStatus,
    SourceGranularity,
    TruthClaim,
    TruthDocument,
    TruthDocumentSentence,
    TruthReasoningGraph,
    TruthSourceLocator,
)


class TruthViewErrorCode(StrEnum):
    RUN_NOT_COMPLETED = "RUN_NOT_COMPLETED"
    RUN_MANIFEST_INVALID = "RUN_MANIFEST_INVALID"
    TRUTH_ARTIFACT_NOT_FOUND = "TRUTH_ARTIFACT_NOT_FOUND"
    TRUTH_ARTIFACT_SHA256_MISMATCH = "TRUTH_ARTIFACT_SHA256_MISMATCH"
    TRUTH_SCHEMA_MISMATCH = "TRUTH_SCHEMA_MISMATCH"
    SAMPLE_NOT_SELECTED = "SAMPLE_NOT_SELECTED"
    SAMPLE_MISSING = "SAMPLE_MISSING"
    SAMPLE_DUPLICATE = "SAMPLE_DUPLICATE"
    DATASET_IDENTITY_MISMATCH = "DATASET_IDENTITY_MISMATCH"
    TRUTH_RELATION_INVALID = "TRUTH_RELATION_INVALID"


class TruthViewLoadError(ValueError):
    """Stable evaluator-loader failure that never embeds a raw truth record."""

    def __init__(self, code: TruthViewErrorCode | str, detail: str):
        self.code = TruthViewErrorCode(code)
        self.detail = detail
        super().__init__(f"{self.code.value}: {detail}")


def _fail(code: TruthViewErrorCode, detail: str) -> None:
    raise TruthViewLoadError(code, detail)


def _resolve_artifact_path(run_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else run_dir / path


def _single_artifact(
    manifest: RunManifest, predicate, description: str
) -> InputArtifactRef:
    matches = tuple(artifact for artifact in manifest.input_artifacts if predicate(artifact))
    if len(matches) != 1:
        _fail(
            TruthViewErrorCode.RUN_MANIFEST_INVALID,
            f"manifest must contain exactly one {description}; found {len(matches)}",
        )
    return matches[0]


def _gate_a_error(error: GateAValidationError) -> TruthViewLoadError:
    if error.code == "DUPLICATE_SAMPLE_ID":
        code = TruthViewErrorCode.SAMPLE_DUPLICATE
    elif error.code in {"JSON_SCHEMA", "JSON_DECODE_ERROR", "SCHEMA_VERSION_UNSUPPORTED"}:
        code = TruthViewErrorCode.TRUTH_SCHEMA_MISMATCH
    elif error.code in {"FILE_MANIFEST_MISMATCH", "MANIFEST_SAMPLE_MISMATCH"}:
        code = TruthViewErrorCode.DATASET_IDENTITY_MISMATCH
    else:
        code = TruthViewErrorCode.TRUTH_RELATION_INVALID
    locator = f" ({error.sample_id})" if error.sample_id else ""
    return TruthViewLoadError(code, f"Data Truth validation failed with {error.code}{locator}")


def _load_manifest(run_dir: Path) -> RunManifest:
    path = run_dir / "manifest.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        manifest = RunManifest.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        _fail(TruthViewErrorCode.RUN_MANIFEST_INVALID, f"invalid run manifest ({type(error).__name__})")
    if len(manifest.selected_sample_ids) != len(set(manifest.selected_sample_ids)):
        _fail(TruthViewErrorCode.RUN_MANIFEST_INVALID, "selected_sample_ids must be unique")
    if manifest.status is not RunStatus.COMPLETED or manifest.finished_at is None:
        _fail(TruthViewErrorCode.RUN_NOT_COMPLETED, "truth is available only after a completed run")
    return manifest


def _truth_view(record: Mapping[str, Any], artifact_sha256: str) -> EvaluationTruthView:
    sample = record["sample"]
    sample_id = str(sample["sample_id"])
    context_indexes = {
        document["context_id"]: int(document["raw_locator"]["context_index"])
        for document in record["documents"]
    }
    sources: dict[str, TruthSourceLocator] = {}
    for source in record["sources"]:
        sources[source["source_id"]] = TruthSourceLocator(
            source_id=source["source_id"],
            context_id=source["context_id"],
            context_ref=ContextRef(
                sample_id=sample_id,
                context_index=context_indexes[source["context_id"]],
            ),
            title=source.get("title"),
            granularity=SourceGranularity(source["granularity"]),
            paragraph_idx=source.get("paragraph_idx"),
            sent_id=source.get("sent_id"),
            char_start=source.get("char_start"),
            char_end=source.get("char_end"),
            text=source["text"],
            source_origin=source["source_origin"],
            locator_status=source["locator_status"],
            raw_locator=source.get("raw_locator", {}),
        )
    source_sets = tuple(
        CanonicalSourceSet(
            claim_id=link["claim_id"],
            source_ids=tuple(link["source_ids"]),
            source_locators=tuple(sources[source_id] for source_id in link["source_ids"]),
            relation=link["relation"],
            validation_status=link["validation_status"],
            needs_review=link["needs_review"],
            reviewer=link.get("reviewer"),
            review_timestamp=link.get("review_timestamp"),
        )
        for link in record["claim_source_links"]
    )
    return EvaluationTruthView(
        sample_id=sample_id,
        answer=sample["answer"],
        answer_aliases=tuple(sample.get("answer_aliases", ())),
        truth_claims=tuple(
            TruthClaim(
                claim_id=claim["claim_id"],
                claim_text=claim["claim_text"],
                claim_kind=claim["claim_kind"],
                structured_form=claim.get("structured_form"),
                annotation_status=claim["annotation_status"],
            )
            for claim in record["claims"]
        ),
        canonical_source_sets=source_sets,
        reasoning_graph=TruthReasoningGraph.model_validate(record["reasoning_graph"]),
        complete_document_catalog=tuple(
            TruthDocument(
                context_id=document["context_id"],
                title=document.get("title"),
                text=document["text"],
                sentences=tuple(
                    TruthDocumentSentence(
                        sent_id=sentence["sent_id"],
                        text=sentence["text"],
                        raw_locator=sentence.get("raw_locator", {}),
                    )
                    for sentence in document["sentences"]
                ),
                is_supporting_context=document["is_supporting_context"],
                raw_locator=document.get("raw_locator", {}),
            )
            for document in record["documents"]
        ),
        optional_minimal_source_sets=None,
        truth_artifact_sha256=artifact_sha256,
    )


class TruthViewLoader:
    """Load immutable evaluator truth for an already-completed run."""

    @classmethod
    def load_for_run(
        cls,
        run_dir: str | Path,
        truth_data_path: str | Path | None = None,
        schema_path: str | Path | None = None,
        *,
        sample_ids: Iterable[str] | None = None,
    ) -> tuple[EvaluationTruthView, ...]:
        run_dir = Path(run_dir)
        manifest = _load_manifest(run_dir)
        dataset_artifact = _single_artifact(
            manifest,
            lambda item: item.schema_version == "3.0" and item.dataset_name is not None,
            "Data Truth dataset artifact",
        )
        schema_artifact = _single_artifact(
            manifest,
            lambda item: item.schema_version == "3.0" and item.dataset_name is None,
            "Data Truth schema artifact",
        )
        selected = tuple(manifest.selected_sample_ids)
        requested = selected if sample_ids is None else tuple(sample_ids)
        if len(requested) != len(set(requested)):
            _fail(TruthViewErrorCode.SAMPLE_DUPLICATE, "requested sample IDs must be unique")
        unselected = set(requested) - set(selected)
        if unselected:
            _fail(
                TruthViewErrorCode.SAMPLE_NOT_SELECTED,
                f"sample is not selected by this run: {sorted(unselected)[0]}",
            )

        data_path = (
            Path(truth_data_path)
            if truth_data_path is not None
            else _resolve_artifact_path(run_dir, dataset_artifact.path)
        )
        actual_schema_path = (
            Path(schema_path)
            if schema_path is not None
            else _resolve_artifact_path(run_dir, schema_artifact.path)
        )
        if not data_path.is_file():
            _fail(TruthViewErrorCode.TRUTH_ARTIFACT_NOT_FOUND, "frozen truth dataset artifact was not found")
        if not actual_schema_path.is_file():
            _fail(TruthViewErrorCode.TRUTH_ARTIFACT_NOT_FOUND, "frozen truth schema artifact was not found")

        actual_hash = file_sha256(data_path)
        if actual_hash != dataset_artifact.sha256:
            _fail(
                TruthViewErrorCode.TRUTH_ARTIFACT_SHA256_MISMATCH,
                "truth dataset content does not match the run manifest",
            )
        if file_sha256(actual_schema_path) != schema_artifact.sha256:
            _fail(
                TruthViewErrorCode.TRUTH_SCHEMA_MISMATCH,
                "truth schema content does not match the run manifest",
            )

        # Inventory IDs after immutable-content checks but before relational
        # validation so missing/duplicate selection failures retain their own
        # stable evaluator error category, including for an empty artifact.
        records: dict[str, Mapping[str, Any]] = {}
        try:
            with data_path.open(encoding="utf-8") as stream:
                for line in stream:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    sample_id = str(record["sample"]["sample_id"])
                    if sample_id in records:
                        _fail(TruthViewErrorCode.SAMPLE_DUPLICATE, f"duplicate sample ID: {sample_id}")
                    records[sample_id] = record
        except TruthViewLoadError:
            raise
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            _fail(TruthViewErrorCode.TRUTH_SCHEMA_MISMATCH, f"truth record decoding failed ({type(error).__name__})")
        missing = [sample_id for sample_id in requested if sample_id not in records]
        if missing:
            _fail(TruthViewErrorCode.SAMPLE_MISSING, f"selected sample is absent: {missing[0]}")

        try:
            adapter = DataTruthV3Adapter(data_path, actual_schema_path, actual_hash)
            report = adapter.validate_all()
        except GateAValidationError as error:
            raise _gate_a_error(error) from None
        expected_identity = (
            dataset_artifact.dataset_name,
            dataset_artifact.release,
            dataset_artifact.split,
        )
        actual_identity = (report.dataset_name, report.dataset_release, report.split)
        if actual_identity != expected_identity:
            _fail(
                TruthViewErrorCode.DATASET_IDENTITY_MISMATCH,
                "truth dataset identity does not match the run manifest",
            )
        try:
            return tuple(_truth_view(records[sample_id], actual_hash) for sample_id in requested)
        except (ValidationError, KeyError, TypeError, ValueError) as error:
            _fail(
                TruthViewErrorCode.TRUTH_RELATION_INVALID,
                f"validated truth could not be mapped ({type(error).__name__})",
            )

    @classmethod
    def load_sample_for_run(
        cls,
        run_dir: str | Path,
        sample_id: str,
        truth_data_path: str | Path | None = None,
        schema_path: str | Path | None = None,
    ) -> EvaluationTruthView:
        return cls.load_for_run(
            run_dir,
            truth_data_path=truth_data_path,
            schema_path=schema_path,
            sample_ids=(sample_id,),
        )[0]
