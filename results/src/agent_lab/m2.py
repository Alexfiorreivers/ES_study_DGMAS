"""M2 evaluator admission, judgment workflow, metrics, and mechanical audit."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, TypeVar

from pydantic import BaseModel

from agent_lab.acceptance import audit_single_run
from agent_lab.domain.contracts_v0_1 import (
    DependencyRecord,
    EvaluationTruthView,
    RunManifest,
    RunState,
    RuntimeMessageNode,
)
from agent_lab.m2_contracts import (
    ANNOTATION_RULE_VERSION,
    EVALUATOR_PROMPT_VERSION,
    METRICS_SPEC_VERSION,
    ArtifactHash,
    CalibrationItem,
    ClaimPresence,
    ConditionIdentity,
    EdgeJudgment,
    EvaluationManifest,
    JudgmentAuditEvent,
    JudgmentOrigin,
    MetricValue,
    NodeJudgment,
    ReviewStatus,
    SemanticDisposition,
    SourceChangeStatus,
    SourceMarkerStatus,
    SupportFine,
)
from agent_lab.truth_view import TruthViewLoader


FIELD_EVALUATOR_PROMPT = """You are an evaluator, not a generator and not a ground-truth editor.
Return independent candidate fields for: (1) truth/runtime claim alignment, (2) source-marker
parsing, (3) evidence support, (4) content truth, (5) qualification change, and (6) parent-child
edge events. Never replace those fields with a total score. Treat official_gold only as locator
provenance. A candidate is never final until human review/adjudication. Use needs_review only for
the frozen ambiguity reasons; explicit absence, empty source_refs, wrong source, contradiction,
and engineering failure are not automatically review cases.
"""

T = TypeVar("T", bound=BaseModel)


class M2Error(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _hash_file(path: Path) -> str:
    return _hash_bytes(path.read_bytes())


def _canonical_hash(value: Any) -> str:
    return _hash_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[Any]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: Iterable[Any]) -> None:
    lines = [json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for value in values]
    path.write_text(("\n".join(lines) + ("\n" if lines else "")), encoding="utf-8")


def _load_models(path: Path, model: type[T]) -> list[T]:
    return [model.model_validate(value) for value in _read_jsonl(path)]


def _blind_alias(run_id: str) -> str:
    return "condition_" + sha256(("m2-blind:" + run_id).encode()).hexdigest()[:12]


def _truth_hash(views: tuple[EvaluationTruthView, ...]) -> str:
    payload = [view.model_dump(mode="json") for view in views]
    return _canonical_hash(payload)


def admit_run(run_dir: str | Path) -> tuple[RunManifest, RunState, tuple[EvaluationTruthView, ...], dict[str, Any]]:
    """Apply the completed-run and completed-question admission gate without mutation."""

    root = Path(run_dir).resolve()
    audit = audit_single_run(root)
    failures: list[str] = []
    if audit["structural_audit_status"] != "passed":
        failures.append("STRUCTURAL_AUDIT_FAILED")
    if audit["run_outcome"] != "completed":
        failures.append("RUN_NOT_COMPLETED")
    if not audit["pilot_completed"]:
        failures.append("PILOT_NOT_COMPLETED")
    if audit["questions"]["completed"] != audit["questions"]["total"] or audit["questions"]["failed"]:
        failures.append("INCOMPLETE_QUESTION_SET")
    if audit["truth_views_loaded"] != audit["questions"]["total"]:
        failures.append("TRUTH_VIEW_INCOMPLETE")
    manifest = RunManifest.model_validate(_read_json(root / "manifest.json"))
    state = RunState.model_validate(_read_json(root / "run_state.json"))
    if manifest.config_sha256 != state.config_sha256:
        failures.append("CONFIG_IDENTITY_MISMATCH")
    if not manifest.prompts or len(manifest.prompts) != 1:
        failures.append("PROMPT_IDENTITY_AMBIGUOUS")
    else:
        prompt = manifest.prompts[0]
        if (prompt.prompt_id, prompt.version, prompt.content_hash) != (
            state.prompt_id, state.prompt_version, state.prompt_hash
        ):
            failures.append("PROMPT_IDENTITY_MISMATCH")
    data_artifacts = [
        item for item in manifest.input_artifacts
        if item.dataset_name and item.schema_version == "3.0" and item.sha256 == state.input_artifact_sha256
    ]
    schema_artifacts = [item for item in manifest.input_artifacts if not item.dataset_name and item.schema_version == "3.0"]
    if len(data_artifacts) != 1 or data_artifacts[0].sha256 != state.input_artifact_sha256:
        failures.append("DATA_IDENTITY_MISMATCH")
    if len(schema_artifacts) != 1 or schema_artifacts[0].sha256 != state.schema_artifact_sha256:
        failures.append("SCHEMA_IDENTITY_MISMATCH")
    if tuple(state.questions) != manifest.selected_sample_ids:
        failures.append("QUESTION_IDENTITY_MISMATCH")
    if failures:
        raise M2Error("evaluation admission rejected: " + ",".join(sorted(set(failures))))
    views = TruthViewLoader.load_for_run(root)
    if tuple(view.sample_id for view in views) != manifest.selected_sample_ids:
        raise M2Error("evaluation admission rejected: TRUTH_VIEW_ORDER_MISMATCH")
    return manifest, state, views, audit


def prepare_evaluation(run_dir: str | Path, output_dir: str | Path) -> Path:
    """Create a blind offline package and empty, replayable M2 output set."""

    run_root = Path(run_dir).resolve()
    # Keep a subst/junction spelling intact on Windows.  Resolving it can pass a
    # mojibake native cwd back to Python when the workspace contains CJK text.
    out = Path(output_dir).absolute()
    if out.exists() and any(out.iterdir()):
        raise M2Error(f"evaluation directory is not empty: {out}")
    out.mkdir(parents=True, exist_ok=True)
    manifest, state, views, _ = admit_run(run_root)
    nodes = _load_models(run_root / "message_nodes.jsonl", RuntimeMessageNode)
    dependencies = _load_models(run_root / "dependency_records.jsonl", DependencyRecord)
    alias = _blind_alias(manifest.run_id)
    provider = manifest.providers[0]
    data_artifact = next(
        item for item in manifest.input_artifacts
        if item.dataset_name and item.schema_version == "3.0" and item.sha256 == state.input_artifact_sha256
    )
    schema_artifact = next(item for item in manifest.input_artifacts if not item.dataset_name and item.schema_version == "3.0")
    prompt = manifest.prompts[0]
    eval_id = "eval_" + sha256((manifest.run_id + EVALUATOR_PROMPT_VERSION).encode()).hexdigest()[:20]
    blind_items = []
    view_by_id = {view.sample_id: view for view in views}
    nodes_by_question: dict[str, list[RuntimeMessageNode]] = defaultdict(list)
    deps_by_question: dict[str, list[DependencyRecord]] = defaultdict(list)
    for node in nodes:
        nodes_by_question[node.question_id].append(node)
    for dep in dependencies:
        deps_by_question[dep.question_id].append(dep)
    for question_id in manifest.selected_sample_ids:
        blind_items.append({
            "schema_version": "1.0.0",
            "evaluation_id": eval_id,
            "blind_condition_alias": alias,
            "question_id": question_id,
            "truth_view": view_by_id[question_id].model_dump(mode="json"),
            "runtime_nodes": [node.model_dump(mode="json") for node in nodes_by_question[question_id]],
            "dependencies": [dep.model_dump(mode="json") for dep in deps_by_question[question_id]],
        })
    _write_jsonl(out / "blind_evaluation_package.jsonl", blind_items)
    _write_jsonl(out / "node_judgments.jsonl", [])
    _write_jsonl(out / "edge_judgments.jsonl", [])
    _write_jsonl(out / "judgment_audit.jsonl", [])
    prompt_path = out / "evaluator_prompt.txt"
    prompt_path.write_text(FIELD_EVALUATOR_PROMPT, encoding="utf-8")
    condition = ConditionIdentity(
        condition_alias=alias,
        condition_id=manifest.experiment_id,
        model_id=provider.model,
        dataset_id=f"{data_artifact.dataset_name}:{data_artifact.release}:{data_artifact.split}",
        replicate_id=manifest.replicate_id,
    )
    evaluation_manifest = EvaluationManifest(
        evaluation_id=eval_id,
        run_id=manifest.run_id,
        admission_status="admitted",
        completed_question_ids=manifest.selected_sample_ids,
        condition=condition,
        evaluator_prompt_sha256=_hash_file(prompt_path),
        run_manifest_sha256=_hash_file(run_root / "manifest.json"),
        data_sha256=data_artifact.sha256,
        schema_sha256=schema_artifact.sha256,
        truth_artifact_sha256=_truth_hash(views),
        repair_manifest_sha256=manifest.repair_manifest_sha256,
        generator_prompt_id=prompt.prompt_id,
        generator_prompt_version=prompt.version,
        generator_prompt_sha256=prompt.content_hash,
        input_artifacts=(
            ArtifactHash(path=str(run_root / "manifest.json"), sha256=_hash_file(run_root / "manifest.json")),
            ArtifactHash(path=str(run_root / "message_nodes.jsonl"), sha256=_hash_file(run_root / "message_nodes.jsonl")),
            ArtifactHash(path=str(run_root / "dependency_records.jsonl"), sha256=_hash_file(run_root / "dependency_records.jsonl")),
            ArtifactHash(path=data_artifact.path, sha256=data_artifact.sha256),
            ArtifactHash(path=schema_artifact.path, sha256=schema_artifact.sha256),
        ),
        semantic_status="awaiting_judgments",
        created_at=_now(),
    )
    _write_json(out / "evaluation_manifest.json", evaluation_manifest.model_dump(mode="json"))
    _write_empty_metrics(out, evaluation_manifest)
    _refresh_manifest_outputs(out, "awaiting_judgments")
    return out


def _write_empty_metrics(out: Path, manifest: EvaluationManifest) -> None:
    common = {
        "metric_status": "missing",
        "not_applicable_reason": "no_final_semantic_judgments_imported",
        "numerator": "",
        "effective_denominator": 0,
        "raw_truth_claim_denominator": 0,
        "needs_review_count": 0,
        "missing_count": 0,
        "not_applicable_count": 0,
        "value": "",
    }
    _write_csv(out / "claim_metrics.csv", ["evaluation_id", "run_id", "question_id", "node_id", "truth_claim_id", *common], [])
    _write_csv(out / "question_metrics.csv", ["evaluation_id", "run_id", "question_id", "node_id", "hop", "metric", *common], [])
    _write_csv(out / "edge_metrics.csv", ["evaluation_id", "run_id", "question_id", "dependency_id", "metric", *common], [])
    summary = {
        "evaluation_id": manifest.evaluation_id,
        "condition_alias": manifest.condition.condition_alias,
        "dataset": manifest.condition.dataset_id,
        "model": manifest.condition.model_id,
        "replicate": manifest.condition.replicate_id,
        "question_count": len(manifest.completed_question_ids),
        "semantic_status": "awaiting_judgments",
        **common,
    }
    _write_csv(out / "condition_summary.csv", list(summary), [summary])
    (out / "report.md").write_text(
        "# M2 evaluation replay\n\n"
        f"- Evaluation: `{manifest.evaluation_id}`\n"
        f"- Run: `{manifest.run_id}`\n"
        "- Admission: passed\n"
        "- Semantic status: awaiting judgments\n\n"
        "No human or validated candidate judgments were supplied. Semantic metrics are missing, not zero.\n",
        encoding="utf-8",
    )


def _refresh_manifest_outputs(out: Path, semantic_status: str) -> EvaluationManifest:
    manifest_path = out / "evaluation_manifest.json"
    manifest = EvaluationManifest.model_validate(_read_json(manifest_path))
    names = (
        "blind_evaluation_package.jsonl", "evaluator_prompt.txt", "node_judgments.jsonl",
        "edge_judgments.jsonl", "judgment_audit.jsonl", "claim_metrics.csv",
        "question_metrics.csv", "edge_metrics.csv", "condition_summary.csv", "report.md",
    )
    artifacts = tuple(
        ArtifactHash(path=str((out / name).absolute()), sha256=_hash_file(out / name))
        for name in names if (out / name).is_file()
    )
    updated = manifest.model_copy(update={"output_artifacts": artifacts, "semantic_status": semantic_status})
    _write_json(manifest_path, updated.model_dump(mode="json"))
    return updated


def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _edge_group_key(value: EdgeJudgment | dict[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    """Return the revision identity for one truth-claim group on a dependency."""

    if isinstance(value, EdgeJudgment):
        question_id = value.question_id
        dependency_id = value.dependency_id
        truth_claim_ids = value.truth_claim_ids
    else:
        question_id = str(value["question_id"])
        dependency_id = str(value["dependency_id"])
        truth_claim_ids = tuple(str(item) for item in value["truth_claim_ids"])
    return question_id, dependency_id, tuple(sorted(truth_claim_ids))


def _edge_atomic_scopes(value: EdgeJudgment | dict[str, Any]) -> set[tuple[str, str, str]]:
    question_id, dependency_id, truth_claim_ids = _edge_group_key(value)
    return {(question_id, dependency_id, truth_claim_id) for truth_claim_id in truth_claim_ids}


def _validate_final_edge_scope_coverage(values: Iterable[EdgeJudgment | dict[str, Any]]) -> None:
    """Reject overlapping final truth-claim coverage on the same dependency."""

    owner_by_scope: dict[tuple[str, str, str], str] = {}
    for value in values:
        is_final = value.is_final if isinstance(value, EdgeJudgment) else bool(value.get("is_final"))
        if not is_final:
            continue
        judgment_id = value.judgment_id if isinstance(value, EdgeJudgment) else str(value["judgment_id"])
        for scope in _edge_atomic_scopes(value):
            previous = owner_by_scope.get(scope)
            if previous is not None:
                raise M2Error(
                    "overlapping final edge truth-claim scope "
                    f"{scope} in judgments {previous} and {judgment_id}"
                )
            owner_by_scope[scope] = judgment_id


def import_judgments(evaluation_dir: str | Path, source: str | Path, kind: str) -> dict[str, int]:
    """Import strict node/edge rows and append an immutable audit event per row."""

    out = Path(evaluation_dir).absolute()
    # Keep subst-drive paths intact on Windows. Resolving them can return a
    # mojibake native path when the workspace contains CJK characters.
    source_path = Path(source).absolute()
    if kind not in {"node", "edge"}:
        raise M2Error("kind must be node or edge")
    model: type[NodeJudgment] | type[EdgeJudgment] = NodeJudgment if kind == "node" else EdgeJudgment
    rows = [model.model_validate(value) for value in _read_jsonl(source_path)]
    manifest = EvaluationManifest.model_validate(_read_json(out / "evaluation_manifest.json"))
    if any(row.run_id != manifest.run_id for row in rows):
        raise M2Error("judgment run_id does not match evaluation manifest")
    target = out / f"{kind}_judgments.jsonl"
    existing = _read_jsonl(target)
    existing_ids = {row["judgment_id"] for row in existing}
    if existing_ids & {row.judgment_id for row in rows}:
        raise M2Error("judgment_id already exists; revisions require a new adjudicated row")
    combined = [*existing, *(row.model_dump(mode="json") for row in rows)]
    if kind == "edge":
        _validate_final_edge_scope_coverage(combined)
    _write_jsonl(target, combined)
    source_hash = _hash_file(source_path)
    events = _read_jsonl(out / "judgment_audit.jsonl")
    for row in rows:
        action = "candidate_imported" if row.origin in {
            JudgmentOrigin.AUTOMATIC_CANDIDATE, JudgmentOrigin.DEEPSEEK_CANDIDATE
        } else "manual_imported"
        event = JudgmentAuditEvent(
            event_id=f"audit_{len(events)+1:06d}",
            judgment_id=row.judgment_id,
            action=action,
            actor_id=row.annotator_id or row.origin.value,
            source_hashes=(source_hash,),
            after_sha256=_canonical_hash(row.model_dump(mode="json")),
            created_at=_now(),
        )
        events.append(event.model_dump(mode="json"))
    _write_jsonl(out / "judgment_audit.jsonl", events)
    return {"imported": len(rows), "final": sum(row.is_final for row in rows), "candidates": sum(not row.is_final for row in rows)}


def adjudicate_judgments(evaluation_dir: str | Path, source: str | Path, kind: str) -> dict[str, int]:
    """Append final adjudications/revisions while retaining candidates and prior finals."""

    out = Path(evaluation_dir).absolute()
    # Keep subst-drive paths intact on Windows; see import_judgments above.
    source_path = Path(source).absolute()
    if kind not in {"node", "edge"}:
        raise M2Error("kind must be node or edge")
    model: type[NodeJudgment] | type[EdgeJudgment] = NodeJudgment if kind == "node" else EdgeJudgment
    rows = [model.model_validate(value) for value in _read_jsonl(source_path)]
    if any(row.origin is not JudgmentOrigin.ADJUDICATED or not row.is_final for row in rows):
        raise M2Error("adjudication input requires origin=adjudicated and is_final=true")
    manifest = EvaluationManifest.model_validate(_read_json(out / "evaluation_manifest.json"))
    if any(row.run_id != manifest.run_id for row in rows):
        raise M2Error("adjudication run_id does not match evaluation manifest")
    target = out / f"{kind}_judgments.jsonl"
    existing = _read_jsonl(target)
    existing_ids = {row["judgment_id"] for row in existing}
    if existing_ids & {row.judgment_id for row in rows}:
        raise M2Error("adjudication must use a new judgment_id")
    if kind == "edge":
        _validate_final_edge_scope_coverage(rows)
        existing_finals = [value for value in existing if value.get("is_final")]
        for row in rows:
            overlaps = [
                value for value in existing_finals
                if _edge_atomic_scopes(value) & _edge_atomic_scopes(row)
            ]
            if any(_edge_group_key(value) != _edge_group_key(row) for value in overlaps):
                raise M2Error(
                    "edge adjudication overlaps an existing final truth-claim group without matching its exact scope; "
                    "migrate/supersede the existing groups before regrouping"
                )
    key_fields = ("question_id", "node_id", "truth_claim_id")
    def key(value: dict[str, Any]) -> tuple[Any, ...]:
        if kind == "edge":
            return _edge_group_key(value)
        return tuple(value[name] for name in key_fields)
    latest_by_key = {key(value): value for value in existing if value.get("is_final")}
    events = _read_jsonl(out / "judgment_audit.jsonl")
    source_hash = _hash_file(source_path)
    for row in rows:
        dumped = row.model_dump(mode="json")
        before = latest_by_key.get(key(dumped))
        action = "revised" if before is not None else "adjudicated"
        event = JudgmentAuditEvent(
            event_id=f"audit_{len(events)+1:06d}", judgment_id=row.judgment_id,
            action=action, actor_id=row.annotator_id or "adjudicator",
            source_hashes=(source_hash,),
            before_sha256=None if before is None else _canonical_hash(before),
            after_sha256=_canonical_hash(dumped), created_at=_now(),
        )
        events.append(event.model_dump(mode="json"))
        if before is not None:
                before["is_final"] = False
                before["rationale"] = ((before.get("rationale") or "") + " | superseded_by:" + row.judgment_id).strip(" |")
        existing.append(dumped)
        latest_by_key[key(dumped)] = dumped
    if kind == "edge":
        _validate_final_edge_scope_coverage(existing)
    _write_jsonl(target, existing)
    _write_jsonl(out / "judgment_audit.jsonl", events)
    return {"adjudicated": len(rows), "revisions": sum(event["action"] == "revised" for event in events[-len(rows):])}


def create_calibration_package(evaluation_dirs: Iterable[str | Path], output: str | Path, size: int = 24) -> Path:
    if not 20 <= size <= 30:
        raise M2Error("calibration size must be within 20..30")
    candidates: list[dict[str, Any]] = []
    for raw_dir in evaluation_dirs:
        root = Path(raw_dir).absolute()
        manifest = EvaluationManifest.model_validate(_read_json(root / "evaluation_manifest.json"))
        for item in _read_jsonl(root / "blind_evaluation_package.jsonl"):
            nodes = item["runtime_nodes"]
            truth = item["truth_view"]
            for node in nodes:
                claims = node["payload"].get("claims", [])
                stratum = ":".join([
                    manifest.condition.dataset_id.split(":", 1)[0],
                    node["node_kind"],
                    "empty" if not claims else ("multi_source" if any(len(c.get("source_refs", [])) > 1 for c in claims) else "single_source"),
                ])
                candidates.append({
                    "manifest": manifest,
                    "question_id": item["question_id"],
                    "node_id": node["node_id"],
                    "stratum": stratum,
                    "truth_claim_count": len(truth["truth_claims"]),
                })
    if len(candidates) < size:
        raise M2Error(f"only {len(candidates)} calibration trajectories are available")
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        buckets[candidate["stratum"]].append(candidate)
    chosen: list[dict[str, Any]] = []
    ordered_strata = sorted(buckets)
    while len(chosen) < size:
        made_progress = False
        for stratum in ordered_strata:
            if buckets[stratum] and len(chosen) < size:
                chosen.append(buckets[stratum].pop(0))
                made_progress = True
        if not made_progress:
            break
    items = [CalibrationItem(
        calibration_id=f"cal_{index:03d}",
        blind_condition_alias=item["manifest"].condition.condition_alias,
        run_id=item["manifest"].run_id,
        question_id=item["question_id"],
        node_ids=(item["node_id"],),
        stratum=item["stratum"],
    ).model_dump(mode="json") for index, item in enumerate(chosen, 1)]
    target = Path(output).absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(target, items)
    status_path = target.with_suffix(".status.md")
    strata = Counter(item["stratum"] for item in items)
    status_path.write_text(
        "# M2 calibration status\n\n"
        f"- Prepared trajectories: {len(items)}\n"
        f"- Strata represented: {len(strata)}\n"
        "- First annotation: pending\n"
        "- Blind repeat annotation after 7–14 days: pending\n"
        "- Field-wise intra-annotator agreement: pending\n"
        "- Full 600-question semantic audit: not completed; current truth remains silver\n\n"
        "Prepared strata:\n" + "".join(f"- `{name}`: {count}\n" for name, count in sorted(strata.items())),
        encoding="utf-8",
    )
    return target


def calibration_agreement(first: str | Path, repeat: str | Path, output: str | Path) -> Path:
    first_rows = {row["judgment_id"]: row for row in _read_jsonl(Path(first).resolve())}
    repeat_rows = {row["judgment_id"]: row for row in _read_jsonl(Path(repeat).resolve())}
    common = sorted(set(first_rows) & set(repeat_rows))
    fields = [
        "claim_presence", "semantic_equivalence", "source_marker_status", "exact_set_survived",
        "source_change_status", "support_fine", "content_truth", "qualification_change", "review_status",
    ]
    report: dict[str, Any] = {"schema_version": "1.0.0", "matched_judgments": len(common), "agreement": {}}
    for field in fields:
        matches = sum(first_rows[key].get(field) == repeat_rows[key].get(field) for key in common)
        report["agreement"][field] = {
            "matches": matches,
            "denominator": len(common),
            "rate": None if not common else matches / len(common),
        }
    target = Path(output).absolute()
    _write_json(target, report)
    return target


def _metric(numerator: int, denominator: int, raw: int, review: int, missing: int = 0, na: int = 0) -> MetricValue:
    if denominator == 0:
        return MetricValue(
            status="not_applicable", effective_denominator=0, raw_truth_claim_denominator=raw,
            needs_review_count=review, missing_count=missing, not_applicable_count=na,
            not_applicable_reason="zero_effective_denominator",
        )
    return MetricValue(
        status="computed", numerator=numerator, effective_denominator=denominator,
        raw_truth_claim_denominator=raw, needs_review_count=review, missing_count=missing,
        not_applicable_count=na, value=numerator / denominator,
    )


def _metric_row(base: dict[str, Any], name: str, metric: MetricValue) -> dict[str, Any]:
    return {**base, "metric": name, **metric.model_dump(mode="json")}


def compute_metrics(evaluation_dir: str | Path, *, scope_mode: str = "strict_hop_union") -> Path:
    """Compute per-question first, then condition macro means, from final judgments only."""

    if scope_mode not in {"strict_hop_union", "calibration_node_scopes"}:
        raise M2Error("scope_mode must be strict_hop_union or calibration_node_scopes")
    out = Path(evaluation_dir).absolute()
    manifest = EvaluationManifest.model_validate(_read_json(out / "evaluation_manifest.json"))
    all_nodes = _load_models(out / "node_judgments.jsonl", NodeJudgment)
    all_edges = _load_models(out / "edge_judgments.jsonl", EdgeJudgment)
    nodes = [row for row in all_nodes if row.is_final]
    edges = [row for row in all_edges if row.is_final]
    _validate_final_edge_scope_coverage(edges)
    if not nodes:
        _write_empty_metrics(out, manifest)
        _refresh_manifest_outputs(out, "awaiting_judgments")
        return out
    duplicate_keys = Counter((row.question_id, row.node_id, row.truth_claim_id) for row in nodes)
    duplicates = [key for key, count in duplicate_keys.items() if count > 1]
    if duplicates:
        raise M2Error(f"multiple final node judgments for the same scope: {duplicates[0]}")
    blind_items = _read_jsonl(out / "blind_evaluation_package.jsonl")
    expected_node_scopes: set[tuple[str, str, str]] = set()
    expected_edge_scopes: set[tuple[str, str, str]] = set()
    for item in blind_items:
        question_id = str(item["question_id"])
        truth_claim_ids = [str(claim["claim_id"]) for claim in item["truth_view"]["truth_claims"]]
        for node in item["runtime_nodes"]:
            expected_node_scopes.update(
                (question_id, str(node["node_id"]), truth_claim_id)
                for truth_claim_id in truth_claim_ids
            )
        for dependency in item["dependencies"]:
            expected_edge_scopes.update(
                (question_id, str(dependency["dependency_id"]), truth_claim_id)
                for truth_claim_id in truth_claim_ids
            )
    final_node_scopes = {(row.question_id, row.node_id, row.truth_claim_id) for row in nodes}
    final_edge_scopes = set().union(*(_edge_atomic_scopes(row) for row in edges)) if edges else set()
    unexpected_node_scopes = final_node_scopes - expected_node_scopes
    unexpected_edge_scopes = final_edge_scopes - expected_edge_scopes
    if unexpected_node_scopes:
        raise M2Error(f"final node judgment is outside the evaluation package: {sorted(unexpected_node_scopes)[0]}")
    if unexpected_edge_scopes:
        raise M2Error(f"final edge judgment is outside the evaluation package: {sorted(unexpected_edge_scopes)[0]}")
    missing_node_scope_count = len(expected_node_scopes - final_node_scopes)
    missing_edge_scope_count = len(expected_edge_scopes - final_edge_scopes)
    scopes_by_question_hop: dict[tuple[str, int], set[str]] = defaultdict(set)
    for row in nodes:
        scopes_by_question_hop[(row.question_id, row.communication_hop)].add(row.node_id)
    ambiguous_scope = next((key for key, scope_ids in scopes_by_question_hop.items() if len(scope_ids) > 1), None)
    if ambiguous_scope is not None and scope_mode == "strict_hop_union":
        raise M2Error(
            f"multiple metric scopes for question/hop {ambiguous_scope}; import one explicit hop_union judgment scope"
        )
    question_rows: list[dict[str, Any]] = []
    claim_rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, int], list[NodeJudgment]] = defaultdict(list)
    for row in nodes:
        grouped[(row.question_id, row.node_id, row.communication_hop)].append(row)
        applicable_source = row.claim_presence is ClaimPresence.PRESENT_EQUIVALENT and row.source_marker_status is SourceMarkerStatus.IDENTIFIABLE
        precision = recall = f1 = extra = None
        if applicable_source:
            canonical, runtime = set(row.canonical_source_ids), set(row.runtime_source_ids)
            intersection = len(canonical & runtime)
            precision = intersection / len(runtime) if runtime else 0
            recall = intersection / len(canonical)
            f1 = 0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
            extra = len(runtime - canonical) / len(runtime) if runtime else None
        claim_rows.append({
            "evaluation_id": manifest.evaluation_id, "run_id": manifest.run_id,
            "question_id": row.question_id, "node_id": row.node_id, "hop": row.communication_hop,
            "truth_claim_id": row.truth_claim_id, "disposition": row.disposition.value,
            "review_status": row.review_status.value, "claim_presence": row.claim_presence.value,
            "exact_set_survived": row.exact_set_survived, "source_change_status": row.source_change_status.value,
            "support_fine": row.support_fine.value, "content_truth": row.content_truth.value,
            "source_precision": precision, "source_recall": recall, "source_f1": f1,
            "extra_source_rate": extra,
            "source_metric_status": "computed" if applicable_source else "not_applicable",
            "not_applicable_reason": "" if applicable_source else "claim_not_equivalent_or_source_unidentifiable",
        })
    metric_names = [
        "ReviewRate", "CSR", "ESS", "VSSR", "FullSupportRate", "PartialSupportRate",
        "NotSupportRate", "SourceMissingRate", "ClaimDroppedRate", "CanonicalSourcePrecision",
        "CanonicalSourceRecall", "CanonicalSourceF1", "ExtraSourceRate",
    ]
    for (question_id, node_id, hop), rows in sorted(grouped.items()):
        raw = len(rows)
        review = sum(row.review_status is ReviewStatus.NEEDS_REVIEW for row in rows)
        decided = [row for row in rows if row.review_status is ReviewStatus.DECIDED]
        denominator = len(decided)
        base = {"evaluation_id": manifest.evaluation_id, "run_id": manifest.run_id,
                "question_id": question_id, "node_id": node_id, "hop": hop}
        question_rows.append(_metric_row(base, "ReviewRate", _metric(review, raw, raw, review)))
        question_rows.append(_metric_row(base, "CSR", _metric(sum(r.claim_presence is ClaimPresence.PRESENT_EQUIVALENT for r in decided), denominator, raw, review)))
        question_rows.append(_metric_row(base, "ESS", _metric(sum(r.exact_set_survived is True for r in decided), denominator, raw, review)))
        question_rows.append(_metric_row(base, "VSSR", _metric(sum(r.source_change_status is SourceChangeStatus.SUBSTITUTED_VALID for r in decided), denominator, raw, review)))
        categories = Counter()
        for row in decided:
            if row.claim_presence is not ClaimPresence.PRESENT_EQUIVALENT:
                categories["ClaimDroppedRate"] += 1
            elif row.source_marker_status in {SourceMarkerStatus.ABSENT, SourceMarkerStatus.UNIDENTIFIABLE}:
                categories["SourceMissingRate"] += 1
            elif row.support_fine is SupportFine.FULLY_SUPPORTED:
                categories["FullSupportRate"] += 1
            elif row.support_fine is SupportFine.PARTIALLY_SUPPORTED:
                categories["PartialSupportRate"] += 1
            elif row.support_fine in {SupportFine.CONTRADICTED, SupportFine.INSUFFICIENT}:
                categories["NotSupportRate"] += 1
            else:
                raise M2Error(f"support partition failed for {row.judgment_id}")
        if sum(categories.values()) != denominator:
            raise M2Error(f"support outcome partition does not equal effective denominator for {question_id}/{node_id}")
        for name in ["FullSupportRate", "PartialSupportRate", "NotSupportRate", "SourceMissingRate", "ClaimDroppedRate"]:
            question_rows.append(_metric_row(base, name, _metric(categories[name], denominator, raw, review)))
        applicable = [row for row in claim_rows if row["question_id"] == question_id and row["node_id"] == node_id and row["source_metric_status"] == "computed"]
        for name, field in [("CanonicalSourcePrecision", "source_precision"), ("CanonicalSourceRecall", "source_recall"), ("CanonicalSourceF1", "source_f1"), ("ExtraSourceRate", "extra_source_rate")]:
            values = [float(row[field]) for row in applicable if row[field] is not None]
            not_applicable = raw - review - len(values)
            metric = MetricValue(
                status="computed", numerator=sum(values), effective_denominator=len(values),
                raw_truth_claim_denominator=raw, needs_review_count=review, missing_count=0,
                not_applicable_count=not_applicable, value=sum(values)/len(values),
            ) if values else MetricValue(
                status="not_applicable", effective_denominator=0, raw_truth_claim_denominator=raw,
                needs_review_count=review, missing_count=0, not_applicable_count=not_applicable,
                not_applicable_reason="no_equivalent_claim_with_identifiable_source",
            )
            question_rows.append(_metric_row(base, name, metric))
    edge_rows: list[dict[str, Any]] = []
    for edge in edges:
        scope_count = len(edge.truth_claim_ids)
        base = {"evaluation_id": manifest.evaluation_id, "run_id": manifest.run_id,
                "question_id": edge.question_id, "dependency_id": edge.dependency_id,
                "claim_event": edge.claim_event, "source_events": "|".join(edge.source_events),
                "support_event": edge.support_event}
        if edge.review_status is ReviewStatus.NEEDS_REVIEW:
            for name in ("EdgeClaimRetention", "EdgeExactSourceRetention", "EdgeValidSubstitution"):
                edge_rows.append(_metric_row(base, name, MetricValue(
                    status="not_applicable", effective_denominator=0,
                    raw_truth_claim_denominator=scope_count, needs_review_count=scope_count,
                    missing_count=0, not_applicable_count=0,
                    not_applicable_reason="edge_needs_review",
                )))
            continue
        claim_applicable = edge.claim_event != "not_applicable"
        edge_rows.append(_metric_row(base, "EdgeClaimRetention", _metric(
            scope_count if edge.claim_event == "claim_retained_equivalent" else 0,
            scope_count if claim_applicable else 0,
            scope_count, 0, na=0 if claim_applicable else scope_count)))
        exact_applicable = edge.claim_event in {"claim_retained_equivalent", "claim_rewritten_non_equivalent", "claim_split", "claim_merged"}
        edge_rows.append(_metric_row(base, "EdgeExactSourceRetention", _metric(
            scope_count if "source_set_retained_exact" in edge.source_events else 0,
            scope_count if exact_applicable else 0,
            scope_count, 0, na=0 if exact_applicable else scope_count)))
        changed = any(event in edge.source_events for event in ("source_substituted_valid", "source_substituted_invalid"))
        edge_rows.append(_metric_row(base, "EdgeValidSubstitution", _metric(
            scope_count if "source_substituted_valid" in edge.source_events else 0,
            scope_count if changed else 0,
            scope_count, 0, na=0 if changed else scope_count)))
    q_fields = ["evaluation_id", "run_id", "question_id", "node_id", "hop", "metric", *MetricValue.model_fields]
    _write_csv(out / "question_metrics.csv", q_fields, question_rows)
    first_loss: dict[tuple[str, str], int | str] = {}
    by_claim: dict[tuple[str, str], list[NodeJudgment]] = defaultdict(list)
    for row in nodes:
        by_claim[(row.question_id, row.truth_claim_id)].append(row)
    for key, rows in by_claim.items():
        ordered = sorted(rows, key=lambda row: row.communication_hop)
        loss = next((row.communication_hop for row in ordered if row.claim_presence is not ClaimPresence.PRESENT_EQUIVALENT), None)
        first_loss[key] = loss if loss is not None else f">{max(row.communication_hop for row in ordered)}"
    for row in claim_rows:
        row["first_loss_hop"] = first_loss[(row["question_id"], row["truth_claim_id"])]
    claim_fields = list(claim_rows[0])
    _write_csv(out / "claim_metrics.csv", claim_fields, claim_rows)
    e_fields = ["evaluation_id", "run_id", "question_id", "dependency_id", "claim_event", "source_events", "support_event", "metric", *MetricValue.model_fields]
    _write_csv(out / "edge_metrics.csv", e_fields, edge_rows)
    summaries = []
    for name in metric_names:
      for hop in sorted({int(row["hop"]) for row in question_rows if row["metric"] == name}):
        rows = [row for row in question_rows if row["metric"] == name and int(row["hop"]) == hop]
        computed_rows = [row for row in rows if row["status"] == "computed"]
        if scope_mode == "calibration_node_scopes":
            values_by_question: dict[str, list[float]] = defaultdict(list)
            for row in computed_rows:
                values_by_question[str(row["question_id"])].append(float(row["value"]))
            values = [sum(items) / len(items) for items in values_by_question.values()]
            aggregation = "question_macro_mean_of_message_scope_means"
        else:
            values = [float(row["value"]) for row in computed_rows]
            aggregation = "question_macro_mean"
        summaries.append({
            "evaluation_id": manifest.evaluation_id,
            "condition_alias": manifest.condition.condition_alias,
            "dataset": manifest.condition.dataset_id,
            "model": manifest.condition.model_id,
            "replicate": manifest.condition.replicate_id,
            "metric": name,
            "hop": hop,
            "aggregation": aggregation,
            "value": None if not values else sum(values) / len(values),
            "effective_question_count": len(values),
            "question_count": len({row["question_id"] for row in rows}),
            "raw_truth_claim_denominator": sum(int(row["raw_truth_claim_denominator"]) for row in rows),
            "effective_denominator": sum(int(row["effective_denominator"]) for row in rows),
            "needs_review_count": sum(int(row["needs_review_count"]) for row in rows),
            "missing_count": sum(int(row["missing_count"]) for row in rows),
            "not_applicable_count": sum(int(row["not_applicable_count"]) for row in rows),
            "metrics_spec_version": METRICS_SPEC_VERSION,
            "annotation_rule_version": ANNOTATION_RULE_VERSION,
        })
    _write_csv(out / "condition_summary.csv", list(summaries[0]), summaries)
    (out / "report.md").write_text(
        "# M2 single-run evaluation\n\n"
        f"- Evaluation: `{manifest.evaluation_id}`\n- Run: `{manifest.run_id}`\n"
        f"- Final node judgments: {len(nodes)}\n- Final edge judgments: {len(edges)}\n"
        f"- Final/expected node truth scopes: {len(final_node_scopes)}/{len(expected_node_scopes)}\n"
        f"- Missing node truth scopes: {missing_node_scope_count}\n"
        f"- Final/expected edge truth scopes: {len(final_edge_scopes)}/{len(expected_edge_scopes)}\n"
        f"- Missing edge truth scopes: {missing_edge_scope_count}\n"
        f"- First-loss-hop records: {len(first_loss)}\n"
        f"- Scope mode: {scope_mode}\n"
        f"- Aggregation: {'message-node scope mean within question/hop, then question macro mean' if scope_mode == 'calibration_node_scopes' else 'explicit question/hop scope, then question macro mean'}\n"
        "- needs_review is excluded from effective denominators and retained in all denominator columns.\n",
        encoding="utf-8",
    )
    semantic_status = "complete" if missing_node_scope_count == 0 and missing_edge_scope_count == 0 else "partially_judged"
    _refresh_manifest_outputs(out, semantic_status)
    return out


def audit_truth_artifacts(
    dataset_path: str | Path,
    schema_path: str | Path,
    expected_dataset_sha256: str,
    expected_schema_sha256: str,
    output: str | Path,
    repair_manifest_path: str | Path | None = None,
    expected_repair_manifest_sha256: str | None = None,
) -> Path:
    """Full mechanical claim-source audit. Mechanical errors are fatal, never review items."""

    dataset = Path(dataset_path).resolve()
    schema = Path(schema_path).resolve()
    failures: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()
    actual_data_hash, actual_schema_hash = _hash_file(dataset), _hash_file(schema)
    if actual_data_hash != expected_dataset_sha256:
        failures.append({"code": "DATA_HASH_MISMATCH"})
    if actual_schema_hash != expected_schema_sha256:
        failures.append({"code": "SCHEMA_HASH_MISMATCH"})
    repair_hash = None
    if (repair_manifest_path is None) != (expected_repair_manifest_sha256 is None):
        failures.append({"code": "REPAIR_MANIFEST_IDENTITY_INCOMPLETE"})
    elif repair_manifest_path is not None:
        repair_hash = _hash_file(Path(repair_manifest_path).resolve())
        if repair_hash != expected_repair_manifest_sha256:
            failures.append({"code": "REPAIR_MANIFEST_HASH_MISMATCH"})
    schema_value = _read_json(schema)
    try:
        import jsonschema
        validator = jsonschema.Draft202012Validator(schema_value)
    except Exception as exc:
        raise M2Error(f"cannot compile truth schema: {exc}") from exc
    sample_ids: set[str] = set()
    for line_number, line in enumerate(dataset.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        counters["records"] += 1
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            failures.append({"code": "JSON_INVALID", "line": line_number})
            continue
        errors = list(validator.iter_errors(record))
        if errors:
            failures.append({"code": "SCHEMA_INVALID", "line": line_number, "count": len(errors)})
            continue
        sample_id = record["sample"]["sample_id"]
        if sample_id in sample_ids:
            failures.append({"code": "SAMPLE_ID_DUPLICATE", "sample_id": sample_id})
        sample_ids.add(sample_id)
        claims = {item["claim_id"]: item for item in record["claims"]}
        sources = {item["source_id"]: item for item in record["sources"]}
        documents = {item["context_id"]: item for item in record["documents"]}
        counters["claims"] += len(record["claims"])
        counters["sources"] += len(record["sources"])
        counters["links"] += len(record["claim_source_links"])
        if len(claims) != len(record["claims"]):
            failures.append({"code": "CLAIM_ID_DUPLICATE", "sample_id": sample_id})
        if len(sources) != len(record["sources"]):
            failures.append({"code": "SOURCE_ID_DUPLICATE", "sample_id": sample_id})
        if len(documents) != len(record["documents"]):
            failures.append({"code": "CONTEXT_ID_DUPLICATE", "sample_id": sample_id})
        accepted_by_claim: Counter[str] = Counter()
        link_pairs: set[tuple[str, tuple[str, ...]]] = set()
        for link in record["claim_source_links"]:
            claim_id, source_ids = link["claim_id"], tuple(link["source_ids"])
            if not claim_id or not source_ids:
                failures.append({"code": "EMPTY_CLAIM_OR_SOURCE_SET", "sample_id": sample_id})
            if claim_id not in claims:
                failures.append({"code": "LINK_CLAIM_MISSING", "sample_id": sample_id, "claim_id": claim_id})
            if len(source_ids) != len(set(source_ids)):
                failures.append({"code": "DUPLICATE_SOURCE_IN_SET", "sample_id": sample_id, "claim_id": claim_id})
            pair = (claim_id, source_ids)
            if pair in link_pairs:
                failures.append({"code": "CLAIM_SOURCE_LINK_DUPLICATE", "sample_id": sample_id, "claim_id": claim_id})
            link_pairs.add(pair)
            for source_id in source_ids:
                if source_id not in sources:
                    failures.append({"code": "LINK_SOURCE_MISSING", "sample_id": sample_id, "source_id": source_id})
            if link["validation_status"] == "accepted":
                accepted_by_claim[claim_id] += 1
        for claim_id in claims:
            if accepted_by_claim[claim_id] != 1:
                failures.append({"code": "CANONICAL_SET_NOT_UNIQUE", "sample_id": sample_id, "claim_id": claim_id, "count": accepted_by_claim[claim_id]})
        for source_id, source in sources.items():
            context_id = source["context_id"]
            if context_id not in documents:
                failures.append({"code": "SOURCE_CONTEXT_MISSING", "sample_id": sample_id, "source_id": source_id})
                continue
            document = documents[context_id]
            if not document["is_supporting_context"]:
                failures.append({"code": "SOURCE_CONTEXT_NOT_SUPPORTING", "sample_id": sample_id, "source_id": source_id})
            if source["granularity"] in {"sentence", "sentence_set"}:
                sent_id = source.get("sent_id")
                sentence_by_id = {sentence["sent_id"]: sentence for sentence in document["sentences"]}
                if sent_id not in sentence_by_id:
                    failures.append({"code": "SOURCE_SENTENCE_OUT_OF_RANGE", "sample_id": sample_id, "source_id": source_id})
                elif source["text"].strip() != sentence_by_id[sent_id]["text"].strip():
                    failures.append({"code": "SOURCE_SENTENCE_TEXT_MISMATCH", "sample_id": sample_id, "source_id": source_id})
            if source["granularity"] == "paragraph":
                paragraph_idx = source.get("paragraph_idx")
                document_paragraph_idx = document.get("raw_locator", {}).get("paragraph_idx")
                if paragraph_idx is None or document_paragraph_idx is None or paragraph_idx != document_paragraph_idx:
                    failures.append({"code": "SOURCE_PARAGRAPH_OUT_OF_RANGE", "sample_id": sample_id, "source_id": source_id})
                elif source["text"].strip() != document["text"].strip():
                    failures.append({"code": "SOURCE_PARAGRAPH_TEXT_MISMATCH", "sample_id": sample_id, "source_id": source_id})
            char_start, char_end = source.get("char_start"), source.get("char_end")
            if (char_start is None) != (char_end is None):
                failures.append({"code": "SOURCE_CHAR_RANGE_INCOMPLETE", "sample_id": sample_id, "source_id": source_id})
            elif char_start is not None and (char_start < 0 or char_end <= char_start or char_end > len(document["text"])):
                failures.append({"code": "SOURCE_CHAR_RANGE_OUT_OF_RANGE", "sample_id": sample_id, "source_id": source_id})
            raw_context_index = source.get("raw_locator", {}).get("context_index")
            doc_context_index = document.get("raw_locator", {}).get("context_index")
            if raw_context_index is not None and doc_context_index is not None and raw_context_index != doc_context_index:
                failures.append({"code": "CONTEXT_INDEX_MISMATCH", "sample_id": sample_id, "source_id": source_id})
        graph = record["reasoning_graph"]
        for claim_id in graph["root_claim_ids"]:
            if claim_id not in claims:
                failures.append({"code": "GRAPH_ROOT_MISSING", "sample_id": sample_id, "claim_id": claim_id})
        edge_keys: set[tuple[str, str, str]] = set()
        for edge in graph["edges"]:
            key = (edge["from_claim_id"], edge["to_claim_id"], edge["edge_type"])
            if key in edge_keys:
                failures.append({"code": "GRAPH_EDGE_DUPLICATE", "sample_id": sample_id})
            edge_keys.add(key)
            if edge["from_claim_id"] not in claims or edge["to_claim_id"] not in claims:
                failures.append({"code": "GRAPH_CLAIM_MISSING", "sample_id": sample_id})
    status = "passed" if not failures else "failed"
    report = {
        "schema_version": "1.0.0",
        "status": status,
        "dataset_path": str(dataset),
        "dataset_sha256": actual_data_hash,
        "schema_path": str(schema),
        "schema_sha256": actual_schema_hash,
        "repair_manifest_sha256": repair_hash,
        "counts": dict(counters),
        "failure_count": len(failures),
        "failure_codes": dict(Counter(item["code"] for item in failures)),
        "failures": failures[:200],
        "needs_review_count": 0,
        "note": "mechanical errors are fatal and are never converted to needs_review",
    }
    target = Path(output).absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_json(target, report)
    if failures:
        raise M2Error(f"mechanical truth audit failed with {len(failures)} error(s); report: {target}")
    return target


def verify_evaluation_replay(evaluation_dir: str | Path) -> dict[str, Any]:
    out = Path(evaluation_dir).absolute()
    manifest = EvaluationManifest.model_validate(_read_json(out / "evaluation_manifest.json"))
    expected = {"evaluation_manifest.json", "node_judgments.jsonl", "edge_judgments.jsonl",
                "claim_metrics.csv", "question_metrics.csv", "edge_metrics.csv",
                "condition_summary.csv", "report.md"}
    missing = sorted(name for name in expected if not (out / name).is_file())
    hash_failures = []
    for artifact in manifest.output_artifacts:
        path = Path(artifact.path)
        if not path.is_file():
            hash_failures.append(f"OUTPUT_MISSING:{path.name}")
        elif _hash_file(path) != artifact.sha256:
            hash_failures.append(f"OUTPUT_HASH_MISMATCH:{path.name}")
    return {
        "status": "passed" if not missing and not hash_failures else "failed",
        "evaluation_id": manifest.evaluation_id,
        "run_id": manifest.run_id,
        "semantic_status": manifest.semantic_status,
        "missing_artifacts": missing,
        "hash_failures": hash_failures,
        "artifact_hashes": {name: _hash_file(out / name) for name in sorted(expected) if (out / name).is_file()},
    }
