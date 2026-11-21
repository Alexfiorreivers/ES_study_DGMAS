"""M3-B repeated-run aggregation and paired uncertainty analysis.

The input is a deliberately narrow tidy table.  Every semantic metric row keeps
its status separate from its value so missing, failed, and not-applicable cells
can never be silently coerced to zero.
"""

from __future__ import annotations

import csv
import json
import math
import random
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any, Iterable

import yaml


STATUSES = {"ok", "missing", "failed", "not_applicable"}
IDENTITY_COLUMNS = (
    "run_id", "dataset_id", "provider_id", "model_id", "model_version",
    "condition_id", "question_id", "question_stratum", "replicate_index",
    "replicate_id", "prompt_set_hash", "assignment_policy",
    "assignment_version", "evaluation_spec_version", "metric", "metric_status",
)
COUNT_COLUMNS = ("numerator", "effective_denominator", "raw_denominator")
COST_COLUMNS = (
    "calls", "attempts", "retries", "input_tokens", "output_tokens",
    "total_tokens", "cost", "latency_seconds", "runtime_seconds",
)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _canonical_hash(value: Any) -> str:
    material = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(material.encode("utf-8")).hexdigest()


def _number(value: str, *, column: str, required: bool = False) -> float | None:
    if value is None or value.strip() == "":
        if required:
            raise ValueError(f"M3B_NUMERIC_VALUE_REQUIRED:{column}")
        return None
    try:
        result = float(value)
    except ValueError as error:
        raise ValueError(f"M3B_INVALID_NUMBER:{column}:{value}") from error
    if not math.isfinite(result):
        raise ValueError(f"M3B_NONFINITE_NUMBER:{column}")
    return result


def _load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(set(IDENTITY_COLUMNS) - set(reader.fieldnames or ()))
        if missing:
            raise ValueError("M3B_MISSING_COLUMNS:" + ",".join(missing))
        rows = []
        for source in reader:
            if source["metric_status"] not in STATUSES:
                raise ValueError(f"M3B_INVALID_STATUS:{source['metric_status']}")
            row: dict[str, Any] = {name: (source.get(name) or "").strip() for name in IDENTITY_COLUMNS}
            if any(not row[name] for name in IDENTITY_COLUMNS if name != "metric_status"):
                raise ValueError("M3B_EMPTY_IDENTITY_FIELD")
            try:
                row["replicate_index"] = int(row["replicate_index"])
            except ValueError as error:
                raise ValueError("M3B_INVALID_REPLICATE_INDEX") from error
            row["value"] = _number(source.get("value", ""), column="value",
                                   required=row["metric_status"] == "ok")
            if row["metric_status"] != "ok" and row["value"] is not None:
                raise ValueError("M3B_NON_OK_VALUE_FORBIDDEN")
            for name in COUNT_COLUMNS + COST_COLUMNS:
                row[name] = _number(source.get(name, ""), column=name) or 0.0
            rows.append(row)
    return rows


def _validate(rows: list[dict[str, Any]], config: dict[str, Any]) -> None:
    if not rows:
        raise ValueError("M3B_EMPTY_INPUT")
    expected_unit = config["analysis_unit"]
    for name in ("dataset_id", "provider_id", "model_id", "model_version", "evaluation_spec_version"):
        observed = {row[name] for row in rows}
        if observed != {str(expected_unit[name])}:
            raise ValueError(f"M3B_ANALYSIS_UNIT_MISMATCH:{name}:{sorted(observed)}")
    expected_replicates = {int(item) for item in config["replicate_indices"]}
    if not expected_replicates:
        raise ValueError("M3B_NO_REPLICATES")
    duplicate_key = (
        "dataset_id", "provider_id", "model_id", "model_version", "condition_id",
        "question_id", "replicate_index", "metric", "evaluation_spec_version",
    )
    seen: set[tuple[Any, ...]] = set()
    for row in rows:
        key = tuple(row[name] for name in duplicate_key)
        if key in seen:
            raise ValueError("M3B_DUPLICATE_KEY:" + "|".join(map(str, key)))
        seen.add(key)
    by_cell: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_cell[(row["condition_id"], row["metric"])].append(row)
    for key, values in by_cell.items():
        for identity in ("prompt_set_hash", "assignment_policy", "assignment_version"):
            observed = {row[identity] for row in values}
            if len(observed) != 1:
                raise ValueError(f"M3B_VERSION_DRIFT:{key[0]}:{key[1]}:{identity}")
    replicate_groups: dict[tuple[str, str, str], set[int]] = defaultdict(set)
    strata: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        replicate_groups[(row["condition_id"], row["question_id"], row["metric"])].add(row["replicate_index"])
        strata[row["question_id"]].add(row["question_stratum"])
    for key, observed in replicate_groups.items():
        if observed != expected_replicates:
            raise ValueError(f"M3B_REPLICATE_SET_MISMATCH:{'|'.join(key)}:{sorted(observed)}")
    if any(len(values) != 1 for values in strata.values()):
        raise ValueError("M3B_QUESTION_STRATUM_DRIFT")
    conditions = {row["condition_id"] for row in rows}
    for comparison in config["comparisons"]:
        if comparison["left"] not in conditions or comparison["right"] not in conditions:
            raise ValueError(f"M3B_COMPARISON_CONDITION_MISSING:{comparison['left']}:{comparison['right']}")


def _status_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    result = {status: 0 for status in STATUSES}
    for row in rows:
        result[row["metric_status"]] += 1
    return result


def _safe_mean(values: Iterable[float]) -> float | None:
    material = list(values)
    return fmean(material) if material else None


def _round(value: float | None) -> str:
    return "" if value is None else format(value, ".12g")


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _round(row.get(name)) if isinstance(row.get(name), float) else row.get(name, "")
                             for name in fieldnames})


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _question_differences(
    rows: list[dict[str, Any]], left: str, right: str, metric: str,
    *, failure_worst: bool, worst_value: float,
) -> tuple[dict[str, list[float]], dict[str, str], dict[str, int]]:
    indexed = {(row["condition_id"], row["question_id"], row["replicate_index"]): row
               for row in rows if row["metric"] == metric and row["condition_id"] in {left, right}}
    questions = sorted({key[1] for key in indexed})
    result: dict[str, list[float]] = {}
    strata: dict[str, str] = {}
    exclusions = defaultdict(int)
    for question in questions:
        deltas = []
        indices = sorted({key[2] for key in indexed if key[1] == question})
        for replicate in indices:
            lrow = indexed.get((left, question, replicate))
            rrow = indexed.get((right, question, replicate))
            if lrow is None or rrow is None:
                exclusions["unpaired"] += 1
                continue
            values = []
            for item in (lrow, rrow):
                if item["metric_status"] == "ok":
                    values.append(item["value"])
                elif failure_worst and item["metric_status"] == "failed":
                    values.append(worst_value)
                else:
                    exclusions[item["metric_status"]] += 1
                    break
            if len(values) == 2:
                deltas.append(values[0] - values[1])
                strata[question] = lrow["question_stratum"]
        if deltas:
            result[question] = deltas
    return result, strata, dict(exclusions)


def _bootstrap(
    differences: dict[str, list[float]], strata: dict[str, str], *, seed: int,
    iterations: int, ci_level: float,
) -> tuple[float, float, float, list[float]]:
    if not differences:
        raise ValueError("M3B_NO_PAIRED_QUESTIONS")
    question_means = {qid: fmean(values) for qid, values in differences.items()}
    point = fmean(question_means.values())
    by_stratum: dict[str, list[str]] = defaultdict(list)
    for qid in sorted(question_means):
        by_stratum[strata[qid]].append(qid)
    rng = random.Random(seed)
    draws = []
    for _ in range(iterations):
        sampled = []
        for stratum in sorted(by_stratum):
            qids = by_stratum[stratum]
            sampled.extend(question_means[qids[rng.randrange(len(qids))]] for _ in range(len(qids)))
        draws.append(fmean(sampled))
    alpha = (1.0 - ci_level) / 2.0
    return point, _percentile(draws, alpha), _percentile(draws, 1.0 - alpha), draws


def _holm(rows: list[dict[str, Any]]) -> None:
    indexed = sorted(((index, row) for index, row in enumerate(rows) if row["p_value"] is not None),
                     key=lambda item: item[1]["p_value"])
    running = 0.0
    count = len(indexed)
    for rank, (index, row) in enumerate(indexed):
        adjusted = min(1.0, (count - rank) * row["p_value"])
        running = max(running, adjusted)
        rows[index]["p_value_holm"] = running


def aggregate_m3(config_path: str | Path) -> Path:
    """Validate a frozen M3-B analysis config and write deterministic outputs."""
    config_path = Path(config_path).resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    input_path = Path(config["input_csv"]).resolve()
    output_dir = Path(config["output_dir"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = _load_rows(input_path)
    _validate(rows, config)
    rows.sort(key=lambda row: tuple(str(row[name]) for name in (
        "condition_id", "metric", "question_stratum", "question_id", "replicate_index")))

    qgroups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        qgroups[(row["condition_id"], row["metric"], row["question_stratum"], row["question_id"])].append(row)
    question_rows = []
    for key, values in sorted(qgroups.items()):
        counts = _status_counts(values)
        valid = [row["value"] for row in values if row["metric_status"] == "ok"]
        question_rows.append({
            "condition_id": key[0], "metric": key[1], "question_stratum": key[2], "question_id": key[3],
            "replicates_expected": len(config["replicate_indices"]), "replicates_valid": len(valid),
            **{f"{status}_count": counts[status] for status in sorted(STATUSES)},
            "value_mean": _safe_mean(valid), "value_sd": pstdev(valid) if len(valid) > 1 else (0.0 if valid else None),
            "value_min": min(valid) if valid else None, "value_max": max(valid) if valid else None,
            **{name: sum(row[name] for row in values) for name in COUNT_COLUMNS},
            "source_run_ids": ";".join(sorted({row["run_id"] for row in values})),
        })

    rgroups: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rgroups[(row["condition_id"], row["metric"], row["replicate_index"])].append(row)
    replicate_rows = []
    for key, values in sorted(rgroups.items()):
        counts = _status_counts(values)
        valid = [row["value"] for row in values if row["metric_status"] == "ok"]
        replicate_rows.append({
            "condition_id": key[0], "metric": key[1], "replicate_index": key[2],
            "question_count": len(values), "valid_count": len(valid),
            **{f"{status}_count": counts[status] for status in sorted(STATUSES)},
            "value_macro_mean": _safe_mean(valid),
            **{name: sum(row[name] for row in values) for name in COST_COLUMNS},
            "source_run_ids": ";".join(sorted({row["run_id"] for row in values})),
        })

    cgroups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in question_rows:
        cgroups[(row["condition_id"], row["metric"])].append(row)
    condition_rows = []
    for key, values in sorted(cgroups.items()):
        valid = [row["value_mean"] for row in values if row["value_mean"] is not None]
        condition_rows.append({
            "condition_id": key[0], "metric": key[1], "question_count": len(values),
            "valid_question_count": len(valid), "value_macro_mean": _safe_mean(valid),
            "value_question_sd": pstdev(valid) if len(valid) > 1 else (0.0 if valid else None),
            **{f"{status}_count": sum(int(row[f"{status}_count"]) for row in values)
               for status in sorted(STATUSES)},
            "source_run_ids": ";".join(sorted({run for row in values
                                                for run in row["source_run_ids"].split(";") if run})),
        })

    metrics = sorted({row["metric"] for row in rows})
    bootstrap = config["bootstrap"]
    paired_rows: list[dict[str, Any]] = []
    draw_rows: list[dict[str, Any]] = []
    modes = (("complete_case", False), ("failure_worst", True))
    for comparison_index, comparison in enumerate(config["comparisons"]):
        for metric_index, metric in enumerate(metrics):
            worst = float(config["failure_worst"]["metrics"].get(metric, config["failure_worst"]["default"]))
            for mode_index, (mode, use_worst) in enumerate(modes):
                differences, strata, exclusions = _question_differences(
                    rows, comparison["left"], comparison["right"], metric,
                    failure_worst=use_worst, worst_value=worst,
                )
                seed = int(bootstrap["seed"]) + comparison_index * 100003 + metric_index * 1009 + mode_index
                if differences:
                    point, ci_low, ci_high, draws = _bootstrap(
                        differences, strata, seed=seed, iterations=int(bootstrap["iterations"]),
                        ci_level=float(bootstrap["ci_level"]),
                    )
                    p_value = min(1.0, 2.0 * min(
                        sum(draw <= 0 for draw in draws) / len(draws),
                        sum(draw >= 0 for draw in draws) / len(draws),
                    ))
                else:
                    point = ci_low = ci_high = p_value = None
                    draws = []
                paired_rows.append({
                    "comparison": f"{comparison['left']}-{comparison['right']}", "left": comparison["left"],
                    "right": comparison["right"], "metric": metric, "analysis": mode,
                    "question_count": len(differences), "paired_replicate_count": sum(map(len, differences.values())),
                    "estimate": point, "ci_low": ci_low, "ci_high": ci_high,
                    "ci_level": float(bootstrap["ci_level"]), "bootstrap_iterations": len(draws),
                    "bootstrap_seed": seed, "p_value": p_value,
                    "exclusions": json.dumps(exclusions, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                })
                for index, draw in enumerate(draws):
                    draw_rows.append({"comparison": f"{comparison['left']}-{comparison['right']}",
                                      "metric": metric, "analysis": mode, "draw_index": index, "estimate": draw})
    if config.get("multiplicity") == "holm":
        for mode in ("complete_case", "failure_worst"):
            _holm([row for row in paired_rows if row["analysis"] == mode])
    else:
        for row in paired_rows:
            row["p_value_holm"] = row["p_value"]
    for row in paired_rows:
        row.setdefault("p_value_holm", None)

    status_by_execution: dict[tuple[str, str, int], str] = {}
    for row in rows:
        key = (row["condition_id"], row["question_id"], row["replicate_index"])
        previous = status_by_execution.get(key)
        status = "failed" if row["metric_status"] == "failed" else "completed"
        status_by_execution[key] = "failed" if previous == "failed" or status == "failed" else "completed"
    engineering_rows = []
    by_condition: dict[str, list[str]] = defaultdict(list)
    for (condition, _, _), status in status_by_execution.items():
        by_condition[condition].append(status)
    for condition, statuses in sorted(by_condition.items()):
        failures = statuses.count("failed")
        engineering_rows.append({"condition_id": condition, "executions": len(statuses),
                                 "engineering_failures": failures,
                                 "engineering_failure_rate": failures / len(statuses)})

    question_fields = ["condition_id", "metric", "question_stratum", "question_id", "replicates_expected",
                       "replicates_valid", "failed_count", "missing_count", "not_applicable_count", "ok_count",
                       "value_mean", "value_sd", "value_min", "value_max", *COUNT_COLUMNS, "source_run_ids"]
    replicate_fields = ["condition_id", "metric", "replicate_index", "question_count", "valid_count",
                        "failed_count", "missing_count", "not_applicable_count", "ok_count", "value_macro_mean",
                        *COST_COLUMNS, "source_run_ids"]
    condition_fields = ["condition_id", "metric", "question_count", "valid_question_count", "value_macro_mean",
                        "value_question_sd", "failed_count", "missing_count", "not_applicable_count", "ok_count",
                        "source_run_ids"]
    paired_fields = ["comparison", "left", "right", "metric", "analysis", "question_count",
                     "paired_replicate_count", "estimate", "ci_low", "ci_high", "ci_level",
                     "bootstrap_iterations", "bootstrap_seed", "p_value", "p_value_holm", "exclusions"]
    _write_csv(output_dir / "question_level.csv", question_fields, question_rows)
    _write_csv(output_dir / "replicate_level.csv", replicate_fields, replicate_rows)
    _write_csv(output_dir / "condition_level.csv", condition_fields, condition_rows)
    _write_csv(output_dir / "paired_statistics.csv", paired_fields, paired_rows)
    _write_csv(output_dir / "bootstrap_draws.csv", ["comparison", "metric", "analysis", "draw_index", "estimate"], draw_rows)
    _write_csv(output_dir / "engineering_failures.csv",
               ["condition_id", "executions", "engineering_failures", "engineering_failure_rate"], engineering_rows)

    output_names = ("question_level.csv", "replicate_level.csv", "condition_level.csv", "paired_statistics.csv",
                    "bootstrap_draws.csv", "engineering_failures.csv")
    manifest = {
        "schema_version": "1.0.0", "statistics_version": config["statistics_version"],
        "analysis_unit": config["analysis_unit"], "input_csv": str(input_path),
        "input_sha256": _sha256(input_path), "config_sha256": _sha256(config_path),
        "replicate_indices": sorted(int(item) for item in config["replicate_indices"]),
        "bootstrap": config["bootstrap"], "failure_worst": config["failure_worst"],
        "multiplicity": config.get("multiplicity", "none"),
        "source_run_ids": sorted({row["run_id"] for row in rows}),
        "outputs": [{"path": name, "sha256": _sha256(output_dir / name)} for name in output_names],
    }
    manifest["analysis_sha256"] = _canonical_hash(manifest)
    (output_dir / "analysis_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = [
        "# M3-B repeated-run analysis", "",
        f"- Statistics version: `{config['statistics_version']}`",
        f"- Input SHA-256: `{manifest['input_sha256']}`",
        f"- Replicates: `{', '.join(map(str, manifest['replicate_indices']))}`",
        f"- Bootstrap: `{bootstrap['iterations']}` stratified question-cluster draws; seed `{bootstrap['seed']}`",
        f"- Multiplicity: `{manifest['multiplicity']}`", "",
        "Both paired complete-case and failure=worst sensitivity analyses are reported. Missing and "
        "not-applicable cells are never converted to zero; engineering failures are reported separately.",
    ]
    (output_dir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return output_dir
