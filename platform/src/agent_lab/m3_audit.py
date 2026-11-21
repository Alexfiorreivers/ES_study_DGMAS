"""Machine-checkable acceptance audit for M3-A condition runs."""

from __future__ import annotations

import json
import re
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from agent_lab.domain.contracts_v0_1 import ProviderMessage, RunManifest, RuntimeMessageNode
from agent_lab.evaluation_trace import canonical_messages_sha256, validate_evaluation_trace
from agent_lab.m3_prompts import canonical_hash


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def audit_m3_run(run_dir: str | Path) -> dict[str, Any]:
    run_dir = Path(run_dir).resolve()
    failures: list[str] = []
    manifest = RunManifest.model_validate(_json(run_dir / "manifest.json"))
    if manifest.status.value != "completed" or not all((manifest.condition_id, manifest.model_id,
                                                         manifest.dataset_id, manifest.replicate_id)):
        failures.append("M3_IDENTITY_OR_STATUS_INVALID")
    snapshot = _json(run_dir / "prompt_snapshot.json")
    templates = snapshot.get("templates", {})
    hashes = {name: sha256(text.encode("utf-8")).hexdigest() for name, text in templates.items()}
    if hashes != snapshot.get("component_hashes") or hashes != manifest.prompts[0].component_hashes:
        failures.append("PROMPT_COMPONENT_HASH_MISMATCH")
    expected_set = canonical_hash({"prompt_ref": snapshot.get("prompt_ref"), "components": hashes})
    if expected_set != snapshot.get("prompt_set_hash") or expected_set != manifest.prompts[0].prompt_set_hash:
        failures.append("PROMPT_SET_HASH_MISMATCH")
    contract = _json(run_dir / "condition_contract.json")
    material = {key: value for key, value in contract.items() if key not in {"contract_sha256", "status"}}
    if contract.get("status") != "passed" or canonical_hash(material) != contract.get("contract_sha256"):
        failures.append("CONDITION_CONTRACT_HASH_MISMATCH")
    nodes = [RuntimeMessageNode.model_validate(item) for item in _jsonl(run_dir / "message_nodes.jsonl")]
    deps_raw = _jsonl(run_dir / "dependency_records.jsonl")
    from agent_lab.domain.contracts_v0_1 import DependencyRecord
    dependencies = [DependencyRecord.model_validate(item) for item in deps_raw]
    try:
        validate_evaluation_trace(nodes, dependencies)
    except Exception as error:
        failures.append(f"TRACE_INVALID:{type(error).__name__}")
    recon = _jsonl(run_dir / "request_reconstruction.jsonl")
    recon_by_node = {item["node_id"]: item for item in recon}
    if set(recon_by_node) != {node.node_id for node in nodes}:
        failures.append("REQUEST_RECONSTRUCTION_COVERAGE_MISMATCH")
    for node in nodes:
        item = recon_by_node.get(node.node_id)
        if item is None:
            continue
        messages = tuple(ProviderMessage.model_validate(value) for value in item["messages"])
        if (canonical_messages_sha256(messages) != node.visible_input_sha256 or
                item.get("messages_sha256") != node.visible_input_sha256 or
                item.get("prompt_set_hash") != expected_set):
            failures.append(f"REQUEST_RECONSTRUCTION_MISMATCH:{node.node_id}")
    projections = _jsonl(run_dir / "parent_projections.jsonl")
    node_by_id = {node.node_id: node for node in nodes}
    for projection in projections:
        claims = projection["projected_view"]["claims"]
        if canonical_hash(projection["projected_view"]) != projection["projected_view_sha256"]:
            failures.append("PROJECTION_VIEW_HASH_MISMATCH")
        if manifest.condition_id == "A1":
            if projection["projection_ref"] != "hide-source-refs@1.0.0" or any(c["source_refs"] for c in claims):
                failures.append("A1_SOURCE_REFS_VISIBLE")
            if projection["changed_fields"] != ["claims[].source_refs"]:
                failures.append("A1_CHANGED_FIELDS_INVALID")
            parent = node_by_id[projection["parent_node_id"]]
            expected_claims = []
            for claim in parent.payload.claims:
                value = claim.model_dump(mode="json")
                value["source_refs"] = []
                expected_claims.append(value)
            if claims != expected_claims:
                failures.append("A1_CHANGED_FIELD_OUTSIDE_SOURCE_REFS")
        elif projection["before_sha256"] != projection["after_sha256"] or projection["changed_fields"]:
            failures.append("NON_A1_PROJECTION_CHANGED")
    qcount = len(manifest.selected_sample_ids)
    node_counts = Counter(node.question_id for node in nodes)
    dep_counts = Counter(item["question_id"] for item in deps_raw)
    if manifest.condition_id == "B0" and (set(node_counts.values()) != {1} or dependencies):
        failures.append("B0_EXECUTION_SHAPE_INVALID")
    if manifest.condition_id == "B0":
        assignments = {item["question_id"]: item for item in _json(run_dir / "assignments.json")}
        for node in nodes:
            expected_refs = {canonical_hash(ref) for refs in assignments[node.question_id]["assignments"].values()
                             for ref in refs}
            actual_refs = {canonical_hash(ref.model_dump(mode="json")) for ref in node.visible_document_refs}
            if actual_refs != expected_refs:
                failures.append(f"B0_ASSIGNED_DOCUMENT_UNION_MISMATCH:{node.question_id}")
    if manifest.condition_id == "B1" and (set(node_counts.values()) != {3} or dependencies):
        failures.append("B1_EXECUTION_SHAPE_INVALID")
    if manifest.condition_id in {"M", "A1", "A2"} and (set(node_counts.values()) != {5} or set(dep_counts.values()) != {2}):
        failures.append("MULTI_AGENT_EXECUTION_SHAPE_INVALID")
    if manifest.condition_id == "A2":
        diff = _json(run_dir / "a2_prompt_diff.json")
        if diff.get("added_lines") != [] or not diff.get("removed_lines"):
            failures.append("A2_DIFF_INVALID")
    observations = _jsonl(run_dir / "terminal_observations.jsonl")
    terminal_ids = {item["terminal_node_id"] for item in observations}
    if manifest.condition_id in {"M", "A1", "A2"}:
        allowed = {node.node_id for node in nodes if node.round == 1}
        if not terminal_ids <= allowed:
            failures.append("TERMINAL_UNION_INCLUDED_NONTERMINAL_NODE")
    forbidden_key_patterns = re.compile(
        r'"(?:answer|answer_aliases|truth_view|evaluation_truth_view|canonical_source_sets|authorization|api_key)"\s*:',
        re.IGNORECASE,
    )
    credential_patterns = (re.compile(r"sk-[A-Za-z0-9]{20,}"),
                           re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}"))
    leak_files = []
    credential_files = []
    sidecar_mentions = []
    agent_visible = ("trace.jsonl", "message_nodes.jsonl", "dependency_records.jsonl",
                     "request_reconstruction.jsonl", "input_snapshots.json")
    for name in agent_visible:
        text = (run_dir / name).read_text(encoding="utf-8", errors="ignore")
        if forbidden_key_patterns.search(text):
            leak_files.append(name)
        if any(pattern.search(text) for pattern in credential_patterns):
            credential_files.append(name)
        if "sidecar" in text.casefold():
            sidecar_mentions.append(name)
    if leak_files:
        failures.append("TRUTHVIEW_OR_ANSWER_LEAK")
    if credential_files:
        failures.append("CREDENTIAL_LEAK")
    if sidecar_mentions:
        failures.append("SIDECAR_LEAK")
    trace = _jsonl(run_dir / "trace.jsonl")
    responses = [event for event in trace if event["event_type"] == "MODEL_RESPONSE_RECEIVED"]
    usage = Counter()
    for event in responses:
        for key, value in (event.get("event_data", {}).get("usage") or {}).items():
            if isinstance(value, int):
                usage[key] += value
    result = {
        "status": "passed" if not failures else "failed", "run_dir": str(run_dir),
        "run_id": manifest.run_id, "condition_id": manifest.condition_id,
        "model_id": manifest.model_id, "dataset_id": manifest.dataset_id,
        "replicate_id": manifest.replicate_id, "questions": qcount,
        "logical_model_requests": manifest.logical_model_requests,
        "total_model_attempts": manifest.total_model_attempts,
        "usage": dict(usage), "message_nodes": len(nodes), "dependency_records": len(dependencies),
        "terminal_occurrences": len(observations),
        "edge_metrics_applicability": "not_applicable" if manifest.condition_id in {"B0", "B1"} else "applicable",
        "prompt_set_hash": expected_set, "projection_records": len(projections),
        "leak_scan": {"truth_or_answer_files": leak_files, "credential_files": credential_files,
                      "sidecar_files": sidecar_mentions}, "failures": failures,
    }
    return result
