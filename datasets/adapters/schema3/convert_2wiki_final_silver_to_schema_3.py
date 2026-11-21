#!/usr/bin/env python3
"""Convert every root-level 2Wiki final-silver JSONL file to Data Truth Schema 3.0.

The converter never edits source files. It validates every converted record in
memory first, then writes same-named JSONL files to the configured output
directory. Use --dry-run to perform all conversion and validation without any
filesystem writes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable

try:
    import jsonschema
except ImportError as exc:  # pragma: no cover - environment check
    raise SystemExit("Missing dependency: install jsonschema with: python -m pip install jsonschema") from exc


CONVERTER_VERSION = "2wiki-schema3-converter-1.0.0"
VALIDATOR_VERSION = "data-truth-relational-v3.0-converter-1.0.0"
DEFAULT_INPUT_DIR = Path(__file__).resolve().parent / "legacy_inputs/2wiki"
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_DIR / "3.0"
DEFAULT_SCHEMA = Path(__file__).resolve().parents[2] / "schema/data_truth_schema.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ConversionError(ValueError):
    """A record cannot be migrated without guessing or losing an invariant."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ConversionError(message)


def as_dict(value: Any, field: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{field} must be an object")
    return value


def nonempty(value: Any, field: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"{field} must be a non-empty string")
    return value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def portable_source_locator(value: Any) -> str:
    source = nonempty(value, "dataset_manifest.source_file")
    basename = PureWindowsPath(source.replace("/", "\\")).name
    require(bool(basename), "cannot derive source filename")
    return f"datasets/2wiki/{basename}"


def normalize_warnings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, dict):
        return [f"legacy:{key}={item}" for key, item in value.items() if item not in (None, "", [], {})]
    return [f"legacy:{value}"]


def context_id_from(document: dict[str, Any]) -> str:
    if isinstance(document.get("context_id"), str) and document["context_id"]:
        return document["context_id"]
    index = document.get("context_index")
    require(isinstance(index, int) and index >= 0, "document.context_index must be a non-negative integer")
    return f"ctx_{index}"


def map_relation(old_relation: Any, source_count: int) -> str:
    require(source_count >= 1, "accepted link must contain at least one source")
    if old_relation == "supports":
        return "supports"
    if source_count == 1:
        return "entails"
    return "joint_entailment"


def map_edge_type(value: Any) -> str:
    if value in {"supports", "requires", "comparison", "inference"}:
        return str(value)
    return "inference"


def transform_graph(old: dict[str, Any], claim_ids: set[str]) -> dict[str, Any]:
    edges: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    targetless_comparison_roots: set[str] = set()
    for edge_index, edge_value in enumerate(old.get("edges", [])):
        edge = as_dict(edge_value, f"reasoning_graph.edges[{edge_index}]")
        target = edge.get("to_claim_id", edge.get("target_node_id"))
        source_nodes = (
            [edge.get("from_claim_id")]
            if "from_claim_id" in edge
            else edge.get("source_node_ids", [])
        )
        require(isinstance(source_nodes, list) and source_nodes, f"graph edge {edge_index} has no source nodes")
        edge_type = map_edge_type(edge.get("edge_type", edge.get("relation")))
        if target is None:
            require(edge_type == "comparison", f"non-comparison graph edge {edge_index} has no target")
            require(all(isinstance(source, str) and source for source in source_nodes), f"graph edge {edge_index} has invalid source")
            targetless_comparison_roots.update(source_nodes)
            continue
        require(isinstance(target, str) and target, f"graph edge {edge_index} has invalid target")
        for source in source_nodes:
            require(isinstance(source, str) and source, f"graph edge {edge_index} has invalid source")
            key = (source, target, edge_type)
            if key not in seen:
                seen.add(key)
                edges.append({"from_claim_id": source, "to_claim_id": target, "edge_type": edge_type})

    outgoing = {edge["from_claim_id"] for edge in edges}
    old_roots = old.get("root_claim_ids")
    if isinstance(old_roots, list) and old_roots:
        roots = list(old_roots)
    elif targetless_comparison_roots:
        roots = sorted(targetless_comparison_roots)
    else:
        roots = sorted(claim_ids - outgoing)
    require(bool(roots), "reasoning graph has no root claim")
    hop_count = old.get("hop_count", old.get("reasoning_hop_count"))
    require(isinstance(hop_count, int) and hop_count >= 1, "reasoning graph has invalid hop count")
    graph_type = old.get("graph_type")
    return {
        "graph_type": nonempty(graph_type, "reasoning_graph.graph_type"),
        "hop_count": hop_count,
        "root_claim_ids": roots,
        "edges": edges,
    }


def transform_record(old: dict[str, Any], validated_at: str) -> dict[str, Any]:
    manifest = as_dict(old.get("dataset_manifest"), "dataset_manifest")
    sample = as_dict(old.get("sample"), "sample")
    screening = as_dict(old.get("semantic_screening"), "semantic_screening")
    require(manifest.get("dataset_name") == "2WikiMultiHopQA", "not a 2WikiMultiHopQA record")

    documents: list[dict[str, Any]] = []
    context_by_index: dict[int, str] = {}
    for doc_index, doc_value in enumerate(old.get("documents", [])):
        doc = as_dict(doc_value, f"documents[{doc_index}]")
        source_index = doc.get("context_index", doc_index)
        require(isinstance(source_index, int) and source_index >= 0, f"documents[{doc_index}] invalid context_index")
        require(source_index not in context_by_index, f"duplicate context_index {source_index}")
        context_id = context_id_from(doc)
        context_by_index[source_index] = context_id
        sentences: list[dict[str, Any]] = []
        for sentence_index, sent_value in enumerate(doc.get("sentences", [])):
            sent = as_dict(sent_value, f"documents[{doc_index}].sentences[{sentence_index}]")
            sent_id = sent.get("sent_id", sent.get("sentence_index"))
            require(isinstance(sent_id, int) and sent_id >= 0, "invalid sentence id")
            raw_locator = sent.get("raw_locator")
            if not isinstance(raw_locator, dict):
                raw_locator = {"context_index": source_index, "sentence_index": sent_id}
            sentences.append({
                "sent_id": sent_id,
                "text": nonempty(sent.get("text"), "sentence.text"),
                "raw_locator": raw_locator,
            })
        documents.append({
            "context_id": context_id,
            "title": doc.get("title") or None,
            "text": nonempty(doc.get("text"), "document.text"),
            "sentences": sentences,
            "is_supporting_context": bool(doc.get("is_supporting_context")),
            "raw_locator": doc.get("raw_locator") if isinstance(doc.get("raw_locator"), dict) else {},
        })
    require(bool(documents), "documents must not be empty")

    sources: list[dict[str, Any]] = []
    for source_index, source_value in enumerate(old.get("sources", [])):
        source = as_dict(source_value, f"sources[{source_index}]")
        old_context_index = source.get("context_index")
        require(old_context_index in context_by_index, f"source references missing context_index {old_context_index}")
        sources.append({
            "source_id": nonempty(source.get("source_id"), "source.source_id"),
            "context_id": context_by_index[old_context_index],
            "title": source.get("title") or None,
            "paragraph_idx": None,
            "sent_id": source.get("sent_id"),
            "char_start": None,
            "char_end": None,
            "text": nonempty(source.get("text"), "source.text"),
            "granularity": "sentence",
            "source_origin": "official_gold",
            "locator_status": "valid",
            "raw_locator": source.get("raw_locator") if isinstance(source.get("raw_locator"), dict) else {},
        })

    links: list[dict[str, Any]] = []
    link_by_claim: dict[str, dict[str, Any]] = {}
    incomplete_review_metadata = False
    for link_index, link_value in enumerate(old.get("claim_source_links", [])):
        link = as_dict(link_value, f"claim_source_links[{link_index}]")
        claim_id = nonempty(link.get("claim_id"), "link.claim_id")
        source_ids = link.get("source_ids")
        require(isinstance(source_ids, list) and source_ids, "link.source_ids must be non-empty")
        require(claim_id not in link_by_claim, f"claim {claim_id} has multiple accepted links")
        old_relation = link.get("relation")
        reason = link.get("entailment_notes") or link.get("automatic_match_reason")
        reviewer = link.get("reviewer")
        review_timestamp = link.get("review_timestamp")
        review_pair_valid = (
            isinstance(reviewer, str) and bool(reviewer.strip())
            and isinstance(review_timestamp, str) and bool(review_timestamp.strip())
        )
        if (reviewer is None) != (review_timestamp is None) or (reviewer is not None and not review_pair_valid):
            incomplete_review_metadata = True
        migrated = {
            "claim_id": claim_id,
            "source_ids": list(dict.fromkeys(source_ids)),
            "relation": map_relation(old_relation, len(set(source_ids))),
            "validation_status": "accepted",
            "entailment_notes": str(reason) if reason not in (None, "") else None,
            "needs_review": bool(link.get("needs_review")),
            "reviewer": reviewer if review_pair_valid else None,
            "review_timestamp": review_timestamp if review_pair_valid else None,
        }
        links.append(migrated)
        link_by_claim[claim_id] = migrated

    claims: list[dict[str, Any]] = []
    for claim_index, claim_value in enumerate(old.get("claims", [])):
        claim = as_dict(claim_value, f"claims[{claim_index}]")
        claim_id = nonempty(claim.get("claim_id"), "claim.claim_id")
        require(claim_id in link_by_claim, f"claim {claim_id} has no accepted link")
        source_count = len(link_by_claim[claim_id]["source_ids"])
        annotation_status = claim.get("annotation_status", "silver")
        require(annotation_status in {"silver", "gold_audit"}, f"invalid annotation_status {annotation_status}")
        structured = claim.get("structured_form")
        require(structured is None or isinstance(structured, dict), "structured_form must be object or null")
        claims.append({
            "claim_id": claim_id,
            "claim_text": nonempty(claim.get("claim_text"), "claim.claim_text"),
            "claim_kind": "direct" if source_count == 1 else "derived",
            "structured_form": structured,
            "annotation_status": annotation_status,
        })

    claim_status = {claim["claim_id"]: claim["annotation_status"] for claim in claims}
    for link in links:
        if claim_status[link["claim_id"]] == "gold_audit":
            require(not link["needs_review"], "gold_audit link cannot need review")
            require(link["reviewer"] is not None and link["review_timestamp"] is not None, "gold_audit requires reviewer and timestamp")

    warnings = normalize_warnings(as_dict(old.get("validation"), "validation").get("warnings"))
    if any(link["needs_review"] for link in links):
        warnings.append("SILVER_NEEDS_REVIEW")
    if incomplete_review_metadata:
        warnings.append("SILVER_INCOMPLETE_REVIEW_METADATA_DROPPED")
    linked_source_ids = {source_id for link in links for source_id in link["source_ids"]}
    if linked_source_ids != {source["source_id"] for source in sources}:
        warnings.append("UNREFERENCED_OFFICIAL_SOURCE")
    old_graph = as_dict(old.get("reasoning_graph"), "reasoning_graph")
    if any(edge.get("relation") == "comparison" and edge.get("target_node_id") is None for edge in old_graph.get("edges", [])):
        warnings.append("TARGETLESS_COMPARISON_REPRESENTED_BY_ROOTS")
    release = manifest.get("dataset_release", manifest.get("release"))
    dataset_split = manifest.get("split")
    result = {
        "schema_version": "3.0",
        "dataset_manifest": {
            "dataset_name": "2WikiMultiHopQA",
            "dataset_release": nonempty(release, "dataset_manifest.release"),
            "split": nonempty(dataset_split, "dataset_manifest.split"),
            "source_file": portable_source_locator(manifest.get("source_file")),
            "file_sha256": nonempty(manifest.get("file_sha256"), "dataset_manifest.file_sha256").lower(),
            "adapter_version": f"{nonempty(manifest.get('adapter_version'), 'adapter_version')}|{CONVERTER_VERSION}",
            "schema_version": "3.0",
        },
        "semantic_screening": {
            "screening_method": nonempty(screening.get("screening_method", screening.get("method")), "screening.method"),
            "screening_model": screening.get("screening_model", screening.get("model")) or None,
            "screening_prompt_version": screening.get("screening_prompt_version", screening.get("prompt_version")) or None,
            "screened_at": screening.get("screened_at") or None,
            "requires_human_audit": bool(screening.get("requires_human_audit")),
        },
        "sample": {
            "dataset": "2WikiMultiHopQA",
            "dataset_release": nonempty(sample.get("dataset_release", sample.get("release")), "sample.release"),
            "split": nonempty(sample.get("split"), "sample.split"),
            "sample_id": nonempty(sample.get("sample_id"), "sample.sample_id"),
            "question": nonempty(sample.get("question"), "sample.question"),
            "answer": sample.get("answer"),
            "answer_aliases": sample.get("answer_aliases", []),
            "question_type": nonempty(sample.get("question_type"), "sample.question_type"),
            "answerability": 1,
            "normalization_status": "normalized",
            "exclusion_reason": None,
        },
        "documents": documents,
        "claims": claims,
        "sources": sources,
        "claim_source_links": links,
        "reasoning_graph": transform_graph(old_graph, {c["claim_id"] for c in claims}),
        "validation": {
            "status": "qualified",
            "errors": [],
            "warnings": sorted(set(warnings)),
            "validator_version": VALIDATOR_VERSION,
            "validated_at": validated_at,
        },
    }
    require(SHA256_RE.fullmatch(result["dataset_manifest"]["file_sha256"]) is not None, "invalid source SHA-256")
    return result


def ensure_unique(values: Iterable[str], label: str) -> None:
    values_list = list(values)
    duplicates = [value for value, count in Counter(values_list).items() if count > 1]
    require(not duplicates, f"duplicate {label}: {duplicates[:3]}")


def validate_relations(record: dict[str, Any]) -> None:
    manifest, sample = record["dataset_manifest"], record["sample"]
    require(manifest["dataset_name"] == sample["dataset"], "manifest/sample dataset mismatch")
    require(manifest["dataset_release"] == sample["dataset_release"], "manifest/sample release mismatch")
    require(manifest["split"] == sample["split"], "manifest/sample split mismatch")
    documents = {item["context_id"]: item for item in record["documents"]}
    claims = {item["claim_id"]: item for item in record["claims"]}
    sources = {item["source_id"]: item for item in record["sources"]}
    ensure_unique((item["context_id"] for item in record["documents"]), "context_id")
    ensure_unique((item["claim_id"] for item in record["claims"]), "claim_id")
    ensure_unique((item["source_id"] for item in record["sources"]), "source_id")
    for document in documents.values():
        ensure_unique((item["sent_id"] for item in document["sentences"]), f"sent_id in {document['context_id']}")
        require(bool(document["sentences"]), f"2Wiki document {document['context_id']} has no sentences")
    links_by_claim: dict[str, list[dict[str, Any]]] = {key: [] for key in claims}
    referenced_sources: set[str] = set()
    for link in record["claim_source_links"]:
        require(link["claim_id"] in claims, "link references missing claim")
        links_by_claim[link["claim_id"]].append(link)
        require(all(source_id in sources for source_id in link["source_ids"]), "link references missing source")
        referenced_sources.update(link["source_ids"])
    for claim_id, claim in claims.items():
        require(len(links_by_claim[claim_id]) == 1, f"claim {claim_id} must have exactly one link")
        count = len(links_by_claim[claim_id][0]["source_ids"])
        require((count == 1 and claim["claim_kind"] == "direct") or (count >= 2 and claim["claim_kind"] == "derived"), f"claim_kind mismatch for {claim_id}")
    source_contexts: set[str] = set()
    for source in sources.values():
        require(source["context_id"] in documents, "source references missing document")
        document = documents[source["context_id"]]
        require(source["title"] == document["title"], "source/document title mismatch")
        matches = [sent for sent in document["sentences"] if sent["sent_id"] == source["sent_id"]]
        require(len(matches) == 1 and matches[0]["text"] == source["text"], "source sentence locator mismatch")
        source_contexts.add(source["context_id"])
    supporting = {key for key, value in documents.items() if value["is_supporting_context"]}
    require(supporting == source_contexts, "supporting-context/source-catalog set mismatch")
    graph = record["reasoning_graph"]
    graph_ids = set(graph["root_claim_ids"])
    adjacency = {claim_id: [] for claim_id in claims}
    indegree = {claim_id: 0 for claim_id in claims}
    edge_keys: set[tuple[str, str, str]] = set()
    for edge in graph["edges"]:
        require(edge["from_claim_id"] in claims and edge["to_claim_id"] in claims, "graph references missing claim")
        require(edge["from_claim_id"] != edge["to_claim_id"], "graph self-loop")
        key = (edge["from_claim_id"], edge["to_claim_id"], edge["edge_type"])
        require(key not in edge_keys, "duplicate graph edge")
        edge_keys.add(key)
        adjacency[edge["from_claim_id"]].append((edge["to_claim_id"], edge["edge_type"]))
        indegree[edge["to_claim_id"]] += 1
        graph_ids.update((edge["from_claim_id"], edge["to_claim_id"]))
    require(graph_ids == set(claims), "reasoning graph does not cover every claim")
    sinks = {claim_id for claim_id, children in adjacency.items() if not children}
    require(set(graph["root_claim_ids"]) == sinks, "root_claim_ids must equal graph sinks")
    queue = deque(claim_id for claim_id, degree in indegree.items() if degree == 0)
    depth = {claim_id: 1 for claim_id in claims}
    processed = 0
    while queue:
        node = queue.popleft()
        processed += 1
        for child, edge_type in adjacency[node]:
            increment = 0 if edge_type == "comparison" else 1
            depth[child] = max(depth[child], depth[node] + increment)
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    require(processed == len(claims), "reasoning graph contains a cycle")
    require(graph["hop_count"] == max(depth.values()), "reasoning graph hop_count mismatch")


def schema_errors(validator: jsonschema.Draft202012Validator, record: dict[str, Any]) -> list[str]:
    errors = sorted(validator.iter_errors(record), key=lambda item: list(item.absolute_path))
    return [f"{'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}" for error in errors]


def read_jsonl(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ConversionError(f"{path.name}:{line_number}: invalid JSON: {exc}") from exc
            require(isinstance(value, dict), f"{path.name}:{line_number}: record must be an object")
            yield line_number, value


def convert_file(path: Path, validator: jsonschema.Draft202012Validator, validated_at: str) -> list[str]:
    output_lines: list[str] = []
    sample_ids: list[str] = []
    for line_number, old in read_jsonl(path):
        try:
            record = transform_record(old, validated_at)
            errors = schema_errors(validator, record)
            require(not errors, "Schema 3.0 validation failed: " + " | ".join(errors[:10]))
            validate_relations(record)
        except ConversionError as exc:
            raise ConversionError(f"{path.name}:{line_number}: {exc}") from exc
        sample_ids.append(record["sample"]["sample_id"])
        output_lines.append(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
    require(bool(output_lines), f"{path.name}: no records")
    ensure_unique(sample_ids, f"sample_id in {path.name}")
    return output_lines


def write_outputs(outputs: dict[Path, list[str]], output_dir: Path, overwrite: bool) -> None:
    targets = {source: output_dir / source.name for source in outputs}
    existing = [str(target) for target in targets.values() if target.exists()]
    require(overwrite or not existing, "output exists; use --overwrite: " + ", ".join(existing))
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary: list[tuple[Path, Path]] = []
    try:
        for source, lines in outputs.items():
            target = targets[source]
            temp = target.with_name(target.name + ".tmp")
            temp.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
            temporary.append((temp, target))
        for temp, target in temporary:
            temp.replace(target)
    finally:
        for temp, _ in temporary:
            if temp.exists():
                temp.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--dry-run", action="store_true", help="convert and validate without writing files")
    parser.add_argument("--overwrite", action="store_true", help="replace existing same-named outputs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    require(args.input_dir.is_dir(), f"input directory not found: {args.input_dir}")
    require(args.schema.is_file(), f"schema not found: {args.schema}")
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    files = sorted(args.input_dir.glob("*.jsonl"), key=lambda item: item.name.lower())
    require(bool(files), f"no root-level JSONL files found in {args.input_dir}")
    validated_at = utc_now()
    outputs: dict[Path, list[str]] = {}
    for path in files:
        outputs[path] = convert_file(path, validator, validated_at)
        print(f"validated {path.name}: {len(outputs[path])} records")
    if args.dry_run:
        print(f"dry-run complete: {sum(map(len, outputs.values()))} records; no files written")
    else:
        write_outputs(outputs, args.output_dir, args.overwrite)
        print(f"wrote {len(outputs)} files to {args.output_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ConversionError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
