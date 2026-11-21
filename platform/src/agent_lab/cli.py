"""Small YAML-first command line."""

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

from agent_lab.acceptance import audit_run, audit_single_run
from agent_lab.adapters.datasets import DataTruthV3Adapter
from agent_lab.eligibility import GateBValidationError
from agent_lab.domain.contracts_v0_1 import MessageFormat, ModelRequest, ProviderMessage, Stage
from agent_lab.prompts import PROMPT_ID, PROMPT_VERSION, SYSTEM_PROMPT, content_hash
from agent_lab.providers import ProviderError, create_provider
from agent_lab.runtime import load_config, prepare_experiment, run_experiment
from agent_lab.reliability import plan_experiment, resume_reliable_experiment
from agent_lab.m2 import (
    adjudicate_judgments,
    audit_truth_artifacts,
    calibration_agreement,
    compute_metrics,
    create_calibration_package,
    import_judgments,
    prepare_evaluation,
    verify_evaluation_replay,
)
from agent_lab.m3_audit import audit_m3_run
from agent_lab.m3_execution import validate_condition_matrix
from agent_lab.m3_statistics import aggregate_m3


def _synthetic_request(provider, config, *, suffix: str = "provider-check") -> ModelRequest:
    request_model = getattr(config.provider, "model", None) or getattr(config.provider, "version")
    messages = (
        ProviderMessage(role="system", content=SYSTEM_PROMPT),
        ProviderMessage(
            role="user",
            content=(
                "Provider capability check only. Return this JSON object exactly: "
                '{"payload_type":"structured","message_status":"no_new_information",'
                '"claims":[],"summary":null}'
            ),
        ),
    )
    material = "\n".join(message.content for message in messages) + suffix
    return ModelRequest(
        request_id="provider_check_" + sha256(material.encode("utf-8")).hexdigest()[:20],
        provider_ref=provider.provider_ref,
        model=request_model,
        messages=messages,
        output_format=MessageFormat.STRUCTURED,
        output_schema_version="0.1",
        prompt_id=PROMPT_ID,
        prompt_version=PROMPT_VERSION,
        prompt_content_hash=content_hash(),
        run_id="provider-check-not-an-experiment",
        question_id="synthetic-provider-check",
        agent_id="agent_1",
        stage=Stage.INITIAL_READ,
        round=0,
        receiver_id="agent_1",
        replicate_id="provider-check",
        request_context={},
    )


def _provider_check(config, *, live: bool) -> dict:
    provider_kind = config.provider.kind
    request_model = getattr(config.provider, "model", None) or getattr(config.provider, "version")
    empty = {
        "success": True,
        "failure_code": None,
        "provider_kind": provider_kind,
        "request_model": request_model,
        "response_model": None,
        "latency_ms": None,
        "usage": None,
        "finish_reason": None,
        "parse_status": None,
        "provider_request_id": None,
        "health_status": None,
        "served_model_present": None,
    }
    try:
        provider = create_provider(config.provider, config.generation)
        if not live:
            return empty
        health = provider.healthcheck() if hasattr(provider, "healthcheck") else {}
        request = _synthetic_request(provider, config)
        response = provider.complete(request)
        return {
            **empty,
            **health,
            "response_model": response.response_model,
            "latency_ms": response.latency_ms,
            "usage": response.usage.model_dump(mode="json"),
            "finish_reason": response.finish_reason,
            "parse_status": response.parse_status.value,
            "provider_request_id": response.provider_request_id,
        }
    except ProviderError as error:
        return {**empty, "success": False, "failure_code": error.code.value}


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return round(ordered[index], 3)


def _provider_stability_check(config, *, request_count: int) -> dict:
    provider = create_provider(config.provider, config.generation)
    health = provider.healthcheck() if hasattr(provider, "healthcheck") else {}
    latencies: list[float] = []
    errors: Counter[str] = Counter()
    usage: Counter[str] = Counter()
    response_models: Counter[str] = Counter()
    finish_reasons: Counter[str] = Counter()
    for index in range(request_count):
        try:
            response = provider.complete(_synthetic_request(provider, config, suffix=f"stability-{index}"))
        except ProviderError as error:
            errors[error.code.value] += 1
            continue
        latencies.append(response.latency_ms)
        usage.update(response.usage.model_dump(mode="json"))
        response_models[response.response_model] += 1
        finish_reasons[response.finish_reason] += 1
    successes = len(latencies)
    return {
        "passed": successes == request_count,
        "requested": request_count,
        "successes": successes,
        "failures": request_count - successes,
        "error_codes": dict(errors),
        "latency_ms": {
            "min": round(min(latencies), 3) if latencies else None,
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "p99": _percentile(latencies, 0.99),
            "max": round(max(latencies), 3) if latencies else None,
        },
        "usage": dict(usage),
        "response_models": dict(response_models),
        "finish_reasons": dict(finish_reasons),
        **health,
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="agent-lab")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "run", "resume", "plan-run"):
        command = commands.add_parser(name); command.add_argument("--config", required=True)
    provider_check = commands.add_parser("provider-check")
    provider_check.add_argument("--config", required=True)
    provider_check.add_argument("--live", action="store_true")
    stability = commands.add_parser("provider-stability-check")
    stability.add_argument("--config", required=True)
    stability.add_argument("--requests", type=int, default=100)
    stability.add_argument("--output", required=True)
    accept = commands.add_parser("accept")
    accept.add_argument("--config", required=True)
    accept.add_argument("--work-dir", required=True)
    audit = commands.add_parser("audit-run")
    audit.add_argument("--run-dir", required=True)
    m3_audit = commands.add_parser("m3-audit-run")
    m3_audit.add_argument("--run-dir", required=True)
    m3_matrix = commands.add_parser("m3-validate-matrix")
    m3_matrix.add_argument("--config", action="append", required=True)
    m3_aggregate = commands.add_parser("m3-aggregate")
    m3_aggregate.add_argument("--config", required=True)
    m2_prepare = commands.add_parser("m2-prepare")
    m2_prepare.add_argument("--run-dir", required=True)
    m2_prepare.add_argument("--output-dir", required=True)
    m2_import = commands.add_parser("m2-import")
    m2_import.add_argument("--evaluation-dir", required=True)
    m2_import.add_argument("--source", required=True)
    m2_import.add_argument("--kind", choices=("node", "edge"), required=True)
    m2_adjudicate = commands.add_parser("m2-adjudicate")
    m2_adjudicate.add_argument("--evaluation-dir", required=True)
    m2_adjudicate.add_argument("--source", required=True)
    m2_adjudicate.add_argument("--kind", choices=("node", "edge"), required=True)
    m2_compute = commands.add_parser("m2-compute")
    m2_compute.add_argument("--evaluation-dir", required=True)
    m2_replay = commands.add_parser("m2-verify-replay")
    m2_replay.add_argument("--evaluation-dir", required=True)
    m2_calibration = commands.add_parser("m2-calibration")
    m2_calibration.add_argument("--evaluation-dir", action="append", required=True)
    m2_calibration.add_argument("--output", required=True)
    m2_calibration.add_argument("--size", type=int, default=24)
    m2_agreement = commands.add_parser("m2-calibration-agreement")
    m2_agreement.add_argument("--first", required=True)
    m2_agreement.add_argument("--repeat", required=True)
    m2_agreement.add_argument("--output", required=True)
    m2_truth = commands.add_parser("m2-audit-truth")
    m2_truth.add_argument("--dataset", required=True)
    m2_truth.add_argument("--schema", required=True)
    m2_truth.add_argument("--expected-dataset-sha256", required=True)
    m2_truth.add_argument("--expected-schema-sha256", required=True)
    m2_truth.add_argument("--repair-manifest")
    m2_truth.add_argument("--expected-repair-manifest-sha256")
    m2_truth.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "audit-run":
        report = audit_single_run(args.run_dir)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if report["status"] != "passed":
            raise SystemExit(2)
        return
    if args.command == "m3-audit-run":
        report = audit_m3_run(args.run_dir)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if report["status"] != "passed":
            raise SystemExit(2)
        return
    if args.command == "m3-validate-matrix":
        print(json.dumps(validate_condition_matrix([load_config(path) for path in args.config]),
                         ensure_ascii=False, indent=2))
        return
    if args.command == "m3-aggregate":
        print(aggregate_m3(args.config))
        return
    if args.command == "m2-prepare":
        print(prepare_evaluation(args.run_dir, args.output_dir))
        return
    if args.command == "m2-import":
        print(json.dumps(import_judgments(args.evaluation_dir, args.source, args.kind), ensure_ascii=False))
        return
    if args.command == "m2-adjudicate":
        print(json.dumps(adjudicate_judgments(args.evaluation_dir, args.source, args.kind), ensure_ascii=False))
        return
    if args.command == "m2-compute":
        print(compute_metrics(args.evaluation_dir))
        return
    if args.command == "m2-verify-replay":
        report = verify_evaluation_replay(args.evaluation_dir)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if report["status"] != "passed":
            raise SystemExit(2)
        return
    if args.command == "m2-calibration":
        print(create_calibration_package(args.evaluation_dir, args.output, args.size))
        return
    if args.command == "m2-calibration-agreement":
        print(calibration_agreement(args.first, args.repeat, args.output))
        return
    if args.command == "m2-audit-truth":
        print(audit_truth_artifacts(
            args.dataset, args.schema, args.expected_dataset_sha256, args.expected_schema_sha256,
            args.output, args.repair_manifest, args.expected_repair_manifest_sha256,
        ))
        return
    config = load_config(args.config)
    if args.command == "provider-check":
        result = _provider_check(config, live=args.live)
        print(json.dumps(result, ensure_ascii=False))
        if not result["success"]:
            raise SystemExit(2)
    elif args.command == "provider-stability-check":
        if args.requests < 1:
            raise SystemExit("--requests must be positive")
        result = _provider_stability_check(config, request_count=args.requests)
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(output)
        if not result["passed"]:
            raise SystemExit(2)
    elif args.command == "validate":
        try:
            _, gate_a, bundles, gate_b, _ = prepare_experiment(config)
        except GateBValidationError as error:
            # Gate A necessarily succeeded if execution reached this exception.
            adapter = DataTruthV3Adapter(
                config.dataset.path,
                config.dataset.schema_path,
                config.dataset.expected_sha256,
                config.dataset.repair_manifest_path,
                config.dataset.expected_repair_manifest_sha256,
            )
            gate_a = adapter.validate_all()
            print(json.dumps({"gate_a": gate_a.as_dict(), "selected_records": len(config.dataset.sample_ids),
                "gate_b": error.report.model_dump(mode="json")}, ensure_ascii=False))
            raise SystemExit(2) from None
        print(json.dumps({"gate_a": gate_a.as_dict(), "selected_records": len(bundles),
            "gate_b": gate_b.model_dump(mode="json")}, ensure_ascii=False))
    elif args.command == "run":
        print(run_experiment(args.config))
    elif args.command == "resume":
        print(resume_reliable_experiment(args.config))
    elif args.command == "plan-run":
        print(json.dumps(plan_experiment(config), ensure_ascii=False, indent=2))
    else:
        if config.execution is not None:
            raise SystemExit("accept performs paid double replay and is forbidden for execution configs; use audit-run")
        work_dir = Path(args.work_dir).resolve()
        first = run_experiment(args.config, runs_dir_override=work_dir / "replay_a")
        second = run_experiment(args.config, runs_dir_override=work_dir / "replay_b")
        report = audit_run(first, second)
        output = work_dir / "acceptance_metrics.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(output)


if __name__ == "__main__":
    main()
