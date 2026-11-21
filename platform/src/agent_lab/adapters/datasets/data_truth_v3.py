"""Strict Data Truth Schema 3.0 intake and Gate A validation.

Gate A validates immutable file identity, the official JSON Schema, file-level
identity invariants, and record-level relational invariants.  It never repairs
records and deliberately does not decide experiment-policy eligibility.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from jsonschema import Draft202012Validator

from agent_lab.domain.contracts_v0_1 import (
    AtomicClaim,
    ContextRef,
    DatasetTruthProvenance,
    Document,
    DocumentSentence,
    EvidenceRef,
    PlatformInputBundle,
    Question,
    ReferenceOrigin,
    SourceGranularity,
)


GATE_A_VALIDATOR_VERSION = "agent-lab-gate-a-v1.1.0"
MUSIQUE_REPAIR_RULE_VERSION = "musique-reasoning-graph-repair-1.0.0"
MUSIQUE_TEMPLATE_EDGES = {
    "2hop": ((0, 1),),
    "3hop1": ((0, 1), (1, 2)),
    "3hop2": ((0, 2), (1, 2)),
    "4hop1": ((0, 1), (1, 2), (2, 3)),
    "4hop2": ((0, 2), (1, 2), (2, 3)),
    "4hop3": ((0, 1), (1, 3), (2, 3)),
}
MUSIQUE_TEMPLATE_PATTERN = re.compile(r":(2hop|3hop1|3hop2|4hop1|4hop2|4hop3)__")


@dataclass(frozen=True)
class DatasetProfile:
    dataset_name: str
    question_types: frozenset[str]
    document_sentences_may_be_empty: bool
    source_granularities: frozenset[str]


DATASET_PROFILES = {
    "2WikiMultiHopQA": DatasetProfile(
        dataset_name="2WikiMultiHopQA",
        question_types=frozenset({"compositional", "comparison", "inference", "bridge_comparison"}),
        document_sentences_may_be_empty=False,
        source_granularities=frozenset({"sentence"}),
    ),
    "MuSiQue": DatasetProfile(
        dataset_name="MuSiQue",
        question_types=frozenset({"2hop", "3hop", "4hop"}),
        document_sentences_may_be_empty=True,
        source_granularities=frozenset({"paragraph", "sentence"}),
    ),
}


class GateAValidationError(ValueError):
    """A stable, machine-identifiable Data Truth contract failure."""

    def __init__(self, code: str, detail: str, *, path: str = "$", sample_id: str | None = None):
        self.code = code
        self.detail = detail
        self.path = path
        self.sample_id = sample_id
        prefix = f"{code} at {path}"
        if sample_id:
            prefix += f" for {sample_id}"
        super().__init__(f"{prefix}: {detail}")


# Historical import name retained only as an exception alias, not as a v2 input path.
RelationalValidationError = GateAValidationError


@dataclass(frozen=True)
class GateAReport:
    input_path: str
    actual_sha256: str
    expected_sha256: str
    schema_id: str
    schema_sha256: str
    validator_version: str
    total_records: int
    passed_records: int
    failed_records: int
    warning_count: int
    dataset_name: str
    dataset_release: str
    split: str
    repair_manifest_path: str | None = None
    repair_manifest_sha256: str | None = None
    repair_rule_version: str | None = None

    @property
    def status(self) -> str:
        return "pass" if self.failed_records == 0 else "fail"

    def as_dict(self) -> dict[str, Any]:
        return {**self.__dict__, "status": self.status}


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fail(code: str, detail: str, *, path: str = "$", sample_id: str | None = None) -> None:
    raise GateAValidationError(code, detail, path=path, sample_id=sample_id)


def _unique(
    items: Sequence[Mapping[str, Any]], key: str, label: str, sample_id: str
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(items):
        value = str(item[key])
        if value in result:
            _fail("DUPLICATE_ID", f"duplicate {label}: {value}", path=f"$.{label}[{index}].{key}", sample_id=sample_id)
        result[value] = item
    return result


def _context_index(document: Mapping[str, Any], sample_id: str, index: int) -> int:
    value = document.get("raw_locator", {}).get("context_index")
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        _fail(
            "LOCATOR_MISMATCH",
            "document.raw_locator.context_index must be a non-negative integer",
            path=f"$.documents[{index}].raw_locator.context_index",
            sample_id=sample_id,
        )
    return value


def _timestamp_is_rfc3339(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.utcoffset() is not None


def _validate_timestamp(value: Any, path: str, sample_id: str) -> None:
    if value is not None and (not isinstance(value, str) or not _timestamp_is_rfc3339(value)):
        _fail("TIMESTAMP_INVALID", "timestamp must be RFC 3339 with timezone", path=path, sample_id=sample_id)


def _compute_graph_depth(
    claim_ids: set[str], edges: Sequence[Mapping[str, Any]], sample_id: str
) -> tuple[int, dict[str, set[str]]]:
    incoming: dict[str, list[tuple[str, str]]] = {claim_id: [] for claim_id in claim_ids}
    outgoing: dict[str, set[str]] = {claim_id: set() for claim_id in claim_ids}
    seen_edges: set[tuple[str, str, str]] = set()
    for index, edge in enumerate(edges):
        source, target, edge_type = edge["from_claim_id"], edge["to_claim_id"], edge["edge_type"]
        if source not in claim_ids or target not in claim_ids:
            _fail("BROKEN_FOREIGN_KEY", "reasoning edge references missing claim", path=f"$.reasoning_graph.edges[{index}]", sample_id=sample_id)
        if source == target:
            _fail("GRAPH_CYCLE", "reasoning graph contains a self-loop", path=f"$.reasoning_graph.edges[{index}]", sample_id=sample_id)
        signature = (source, target, edge_type)
        if signature in seen_edges:
            _fail("DUPLICATE_ID", "duplicate reasoning edge", path=f"$.reasoning_graph.edges[{index}]", sample_id=sample_id)
        seen_edges.add(signature)
        incoming[target].append((source, edge_type))
        outgoing[source].add(target)

    visiting: set[str] = set()
    depths: dict[str, int] = {}

    def depth(node: str) -> int:
        if node in visiting:
            _fail("GRAPH_CYCLE", "reasoning graph contains a directed cycle", path="$.reasoning_graph.edges", sample_id=sample_id)
        if node in depths:
            return depths[node]
        visiting.add(node)
        if not incoming[node]:
            value = 1
        else:
            value = max(depth(parent) + (0 if edge_type == "comparison" else 1) for parent, edge_type in incoming[node])
        visiting.remove(node)
        depths[node] = value
        return value

    computed = max(depth(node) for node in claim_ids)
    return computed, {node: {parent for parent, _ in parents} for node, parents in incoming.items()}


def musique_question_template(sample_id: str) -> str | None:
    match = MUSIQUE_TEMPLATE_PATTERN.search(sample_id)
    return None if match is None else match.group(1)


def _validate_repaired_musique_shape(
    record: Mapping[str, Any],
    claims: Mapping[str, Mapping[str, Any]],
    links_by_claim: Mapping[str, list[Mapping[str, Any]]],
    computed_hops: int,
    sinks: set[str],
) -> None:
    sample = record["sample"]
    sample_id = str(sample["sample_id"])
    step_count = int(str(sample["question_type"])[0])
    expected_claim_ids = tuple(f"{sample_id}:claim:{index}" for index in range(step_count))
    actual_claim_ids = tuple(claim["claim_id"] for claim in record["claims"])
    if actual_claim_ids != expected_claim_ids or set(claims) != set(expected_claim_ids):
        code = "MUSIQUE_EXTRA_FINAL_CLAIM" if len(actual_claim_ids) > step_count else "MUSIQUE_STEP_CLAIM_MISMATCH"
        _fail(code, f"expected consecutive step claims {expected_claim_ids}, got {actual_claim_ids}",
              path="$.claims", sample_id=sample_id)
    for index, claim_id in enumerate(expected_claim_ids):
        links = links_by_claim.get(claim_id, [])
        if len(links) != 1 or links[0].get("validation_status") != "accepted" or not links[0].get("source_ids"):
            _fail("MUSIQUE_STEP_CLAIM_MISMATCH", f"step {index + 1} must have one accepted non-empty source link",
                  path="$.claim_source_links", sample_id=sample_id)

    terminal = expected_claim_ids[-1]
    roots = tuple(record["reasoning_graph"]["root_claim_ids"])
    if roots != (terminal,) or sinks != {terminal}:
        _fail("MUSIQUE_ROOT_MISMATCH", f"root and recomputed sink must both be terminal claim {terminal}",
              path="$.reasoning_graph.root_claim_ids", sample_id=sample_id)

    template = musique_question_template(sample_id)
    if template is None or int(template[0]) != step_count:
        _fail("MUSIQUE_REFERENCE_GRAPH_MISMATCH", "sample_id does not encode a supported MuSiQue template",
              path="$.sample.sample_id", sample_id=sample_id)
    expected_edges = {
        (expected_claim_ids[source], expected_claim_ids[target])
        for source, target in MUSIQUE_TEMPLATE_EDGES[template]
    }
    edges = record["reasoning_graph"]["edges"]
    actual_edges = {(edge["from_claim_id"], edge["to_claim_id"]) for edge in edges}
    if len(actual_edges) != len(edges) or actual_edges != expected_edges:
        _fail("MUSIQUE_REFERENCE_GRAPH_MISMATCH",
              f"template {template} requires endpoints {sorted(expected_edges)}, got {sorted(actual_edges)}",
              path="$.reasoning_graph.edges", sample_id=sample_id)

    terminal_edges = [edge for edge in edges if edge["to_claim_id"] == terminal]
    comparison_edges = [edge for edge in edges if edge["edge_type"] == "comparison"]
    if comparison_edges and (
        any(edge["to_claim_id"] != terminal for edge in comparison_edges)
        or any(edge["edge_type"] != "comparison" for edge in terminal_edges)
    ):
        _fail("MUSIQUE_COMPARISON_EDGE_INVALID",
              "comparison edges are allowed only as the complete set of edges entering the terminal claim",
              path="$.reasoning_graph.edges", sample_id=sample_id)
    if computed_hops != record["reasoning_graph"]["hop_count"]:
        _fail("MUSIQUE_HOP_RECOMPUTE_MISMATCH",
              f"declared {record['reasoning_graph']['hop_count']}, recomputed {computed_hops}",
              path="$.reasoning_graph.hop_count", sample_id=sample_id)


def validate_relations(record: Mapping[str, Any], *, require_qualified: bool = True) -> tuple[str, ...]:
    """Validate one schema-valid record and return non-blocking warnings."""

    manifest, sample = record["dataset_manifest"], record["sample"]
    sample_id = str(sample["sample_id"])
    dataset = str(manifest["dataset_name"])
    profile = DATASET_PROFILES.get(dataset)
    if profile is None:
        _fail("DATASET_PROFILE_UNSUPPORTED", f"no Gate A profile for {dataset}", path="$.dataset_manifest.dataset_name", sample_id=sample_id)
    identity_pairs = (
        ("dataset_name", "dataset"),
        ("dataset_release", "dataset_release"),
        ("split", "split"),
    )
    for manifest_field, sample_field in identity_pairs:
        if manifest[manifest_field] != sample[sample_field]:
            _fail("MANIFEST_SAMPLE_MISMATCH", f"{manifest_field}/{sample_field} mismatch", path=f"$.sample.{sample_field}", sample_id=sample_id)
    if record["schema_version"] != "3.0" or manifest["schema_version"] != "3.0":
        _fail("MANIFEST_SAMPLE_MISMATCH", "top-level and manifest schema_version must both be 3.0", path="$.schema_version", sample_id=sample_id)
    if sample["question_type"] not in profile.question_types:
        _fail("DATASET_PROFILE_MISMATCH", "question_type is invalid for dataset profile", path="$.sample.question_type", sample_id=sample_id)
    if sample["normalization_status"] != "normalized" or sample["answerability"] != 1 or sample["exclusion_reason"] is not None:
        _fail("AUDIT_STATUS_INVALID", "sample is not a normalized answerable final record", path="$.sample", sample_id=sample_id)
    if require_qualified and (record["validation"]["status"] != "qualified" or record["validation"]["errors"]):
        _fail("AUDIT_STATUS_INVALID", "Gate A accepts qualified records with no validation errors only", path="$.validation", sample_id=sample_id)
    _validate_timestamp(record["validation"]["validated_at"], "$.validation.validated_at", sample_id)
    _validate_timestamp(record["semantic_screening"].get("screened_at"), "$.semantic_screening.screened_at", sample_id)

    documents = _unique(record["documents"], "context_id", "documents", sample_id)
    context_indexes: dict[int, str] = {}
    for index, document in enumerate(record["documents"]):
        native_index = _context_index(document, sample_id, index)
        if native_index in context_indexes:
            _fail("DUPLICATE_ID", f"duplicate document context index: {native_index}", path=f"$.documents[{index}].raw_locator.context_index", sample_id=sample_id)
        context_indexes[native_index] = document["context_id"]
        sentence_ids = [sentence["sent_id"] for sentence in document["sentences"]]
        if len(sentence_ids) != len(set(sentence_ids)):
            _fail("DUPLICATE_ID", "duplicate sentence sent_id within document", path=f"$.documents[{index}].sentences", sample_id=sample_id)
        if not profile.document_sentences_may_be_empty and not sentence_ids:
            _fail("LOCATOR_MISMATCH", "2Wiki documents require non-empty sentences", path=f"$.documents[{index}].sentences", sample_id=sample_id)

    claims = _unique(record["claims"], "claim_id", "claims", sample_id)
    sources = _unique(record["sources"], "source_id", "sources", sample_id)
    source_contexts: set[str] = set()
    for index, source in enumerate(record["sources"]):
        context_id = source["context_id"]
        document = documents.get(context_id)
        if document is None:
            _fail("BROKEN_FOREIGN_KEY", "source references missing document", path=f"$.sources[{index}].context_id", sample_id=sample_id)
        source_contexts.add(context_id)
        if source["title"] != document["title"]:
            _fail("LOCATOR_MISMATCH", "source title does not match document", path=f"$.sources[{index}].title", sample_id=sample_id)
        if source["granularity"] not in profile.source_granularities:
            _fail("DATASET_PROFILE_MISMATCH", "source granularity is invalid for dataset profile", path=f"$.sources[{index}].granularity", sample_id=sample_id)
        sentence_map = {sentence["sent_id"]: sentence["text"] for sentence in document["sentences"]}
        if dataset == "2WikiMultiHopQA":
            valid = (
                source["granularity"] == "sentence"
                and source["paragraph_idx"] is None
                and source["sent_id"] in sentence_map
                and sentence_map.get(source["sent_id"]) == source["text"]
                and source["char_start"] is None
                and source["char_end"] is None
            )
        else:
            document_paragraph = document.get("raw_locator", {}).get("paragraph_idx")
            common = (
                isinstance(source["paragraph_idx"], int)
                and not isinstance(source["paragraph_idx"], bool)
                and source["paragraph_idx"] == document_paragraph
                and source["char_start"] is None
                and source["char_end"] is None
            )
            if source["granularity"] == "paragraph":
                valid = common and source["sent_id"] is None and source["text"] == document["text"]
            else:
                valid = common and source["sent_id"] in sentence_map and sentence_map.get(source["sent_id"]) == source["text"]
        if not valid:
            _fail("LOCATOR_MISMATCH", "source does not resolve exactly under its dataset profile", path=f"$.sources[{index}]", sample_id=sample_id)

    supporting_contexts = {document["context_id"] for document in record["documents"] if document["is_supporting_context"]}
    if supporting_contexts != source_contexts:
        _fail("SUPPORTING_CONTEXT_MISMATCH", "supporting documents must equal all official source contexts", path="$.documents", sample_id=sample_id)

    links_by_claim: dict[str, list[Mapping[str, Any]]] = {claim_id: [] for claim_id in claims}
    referenced_sources: set[str] = set()
    for index, link in enumerate(record["claim_source_links"]):
        claim_id = link["claim_id"]
        if claim_id not in claims:
            _fail("BROKEN_FOREIGN_KEY", "link references missing claim", path=f"$.claim_source_links[{index}].claim_id", sample_id=sample_id)
        missing = [source_id for source_id in link["source_ids"] if source_id not in sources]
        if missing:
            _fail("BROKEN_FOREIGN_KEY", f"link references missing sources: {missing}", path=f"$.claim_source_links[{index}].source_ids", sample_id=sample_id)
        links_by_claim[claim_id].append(link)
        referenced_sources.update(link["source_ids"])
        source_count = len(set(link["source_ids"]))
        if (link["relation"] == "joint_entailment" and source_count < 2) or (link["relation"] == "entails" and source_count != 1):
            _fail("RELATION_SOURCE_COUNT", "relation is inconsistent with accepted source count", path=f"$.claim_source_links[{index}].relation", sample_id=sample_id)

    for index, claim in enumerate(record["claims"]):
        claim_id = claim["claim_id"]
        claim_links = links_by_claim[claim_id]
        if len(claim_links) != 1:
            _fail("CLAIM_LINK_CARDINALITY", "each claim must have exactly one accepted link", path=f"$.claims[{index}].claim_id", sample_id=sample_id)
        link = claim_links[0]
        expected_kind = "direct" if len(set(link["source_ids"])) == 1 else "derived"
        if claim["claim_kind"] != expected_kind:
            _fail("CLAIM_KIND_SOURCE_COUNT", f"{claim['claim_kind']} must be {expected_kind}", path=f"$.claims[{index}].claim_kind", sample_id=sample_id)
        reviewer, reviewed_at = link["reviewer"], link["review_timestamp"]
        if claim["annotation_status"] == "silver":
            if (reviewer is None) != (reviewed_at is None):
                _fail("SILVER_REVIEW_METADATA", "silver reviewer and timestamp must both be null or both non-null", path=f"$.claim_source_links[{index}]", sample_id=sample_id)
            _validate_timestamp(reviewed_at, f"$.claim_source_links[{index}].review_timestamp", sample_id)
        elif claim["annotation_status"] == "gold_audit":
            if link["needs_review"] or not reviewer or not reviewed_at:
                _fail("GOLD_AUDIT_METADATA", "gold_audit requires completed reviewer metadata", path=f"$.claim_source_links[{index}]", sample_id=sample_id)
            _validate_timestamp(reviewed_at, f"$.claim_source_links[{index}].review_timestamp", sample_id)
        else:
            _fail("AUDIT_STATUS_INVALID", "claim must be silver or gold_audit", path=f"$.claims[{index}].annotation_status", sample_id=sample_id)

    graph = record["reasoning_graph"]
    claim_ids = set(claims)
    roots = set(graph["root_claim_ids"])
    if not roots <= claim_ids:
        _fail("BROKEN_FOREIGN_KEY", "root_claim_ids reference missing claims", path="$.reasoning_graph.root_claim_ids", sample_id=sample_id)
    computed_hops, parent_claims = _compute_graph_depth(claim_ids, graph["edges"], sample_id)
    edge_nodes = {edge[key] for edge in graph["edges"] for key in ("from_claim_id", "to_claim_id")}
    outgoing = {claim_id: set() for claim_id in claim_ids}
    for edge in graph["edges"]:
        outgoing[edge["from_claim_id"]].add(edge["to_claim_id"])
    sinks = {claim_id for claim_id, targets in outgoing.items() if not targets}
    is_repaired_musique = dataset == "MuSiQue" and MUSIQUE_REPAIR_RULE_VERSION in str(manifest["adapter_version"])
    if is_repaired_musique:
        _validate_repaired_musique_shape(record, claims, links_by_claim, computed_hops, sinks)
    if len(claim_ids) > 1 and claim_ids - roots - edge_nodes:
        _fail("GRAPH_COVERAGE", "claims are isolated from the reasoning graph", path="$.reasoning_graph", sample_id=sample_id)
    if roots != sinks:
        _fail("GRAPH_PARENT_MISMATCH", "root claims must equal graph sinks", path="$.reasoning_graph.root_claim_ids", sample_id=sample_id)
    reachable: set[str] = set(roots)
    changed = True
    while changed:
        changed = False
        for child, parents in parent_claims.items():
            if child in reachable:
                before = len(reachable)
                reachable.update(parents)
                changed = changed or len(reachable) != before
    if reachable != claim_ids:
        _fail("GRAPH_COVERAGE", "every claim must reach a root claim", path="$.reasoning_graph.edges", sample_id=sample_id)
    if computed_hops != graph["hop_count"]:
        _fail("HOP_COUNT_MISMATCH", f"declared {graph['hop_count']}, recomputed {computed_hops}", path="$.reasoning_graph.hop_count", sample_id=sample_id)

    warnings = list(record["validation"].get("warnings", []))
    if referenced_sources != set(sources) and "UNREFERENCED_OFFICIAL_SOURCE" not in warnings:
        warnings.append("UNREFERENCED_OFFICIAL_SOURCE")
    return tuple(warnings)


class DataTruthV3Adapter:
    """The sole runtime dataset adapter. Schema 2.x is rejected by construction."""

    def __init__(
        self,
        data_path: str | Path,
        schema_path: str | Path,
        expected_sha256: str,
        repair_manifest_path: str | Path | None = None,
        expected_repair_manifest_sha256: str | None = None,
    ):
        self.data_path, self.schema_path = Path(data_path), Path(schema_path)
        self.expected_sha256 = expected_sha256.lower()
        actual = file_sha256(self.data_path)
        if actual != self.expected_sha256:
            _fail("INPUT_SHA256_MISMATCH", f"expected {self.expected_sha256}, got {actual}", path=str(self.data_path))
        self.data_sha256 = actual
        self.repair_manifest_path: Path | None = None
        self.repair_manifest_sha256: str | None = None
        self.repair_rule_version: str | None = None
        if (repair_manifest_path is None) != (expected_repair_manifest_sha256 is None):
            _fail("REPAIR_MANIFEST_INVALID", "repair manifest path and expected SHA-256 must be supplied together")
        if repair_manifest_path is not None and expected_repair_manifest_sha256 is not None:
            self.repair_manifest_path = Path(repair_manifest_path)
            self.repair_manifest_sha256 = file_sha256(self.repair_manifest_path)
            if self.repair_manifest_sha256 != expected_repair_manifest_sha256.lower():
                _fail("REPAIR_MANIFEST_INVALID", "repair manifest SHA-256 mismatch", path=str(self.repair_manifest_path))
            repair_manifest = json.loads(self.repair_manifest_path.read_text(encoding="utf-8"))
            self.repair_rule_version = str(repair_manifest.get("repair_rule_version", ""))
            valid_manifest = (
                repair_manifest.get("status") == "complete"
                and repair_manifest.get("manifest_version") == "1.0.0"
                and self.repair_rule_version == MUSIQUE_REPAIR_RULE_VERSION
                and repair_manifest.get("output", {}).get("sha256") == self.data_sha256
                and repair_manifest.get("output", {}).get("record_count") == 200
            )
            if not valid_manifest:
                _fail("REPAIR_MANIFEST_INVALID", "repair manifest is incomplete or does not bind the input artifact",
                      path=str(self.repair_manifest_path))
        self.schema_sha256 = file_sha256(self.schema_path)
        self.schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        self.schema_id = str(self.schema.get("$id", ""))
        if "v3.0" not in self.schema_id or self.schema.get("properties", {}).get("schema_version", {}).get("const") != "3.0":
            _fail("SCHEMA_VERSION_UNSUPPORTED", "schema_path must point to the formal Data Truth Schema 3.0", path=str(self.schema_path))
        self.validator = Draft202012Validator(self.schema)
        self._cached: tuple[list[Mapping[str, Any]], GateAReport] | None = None

    def _load_and_validate_all(self) -> tuple[list[Mapping[str, Any]], GateAReport]:
        if self._cached is not None:
            return self._cached
        records: list[Mapping[str, Any]] = []
        sample_ids: set[str] = set()
        manifest_identity: tuple[Any, ...] | None = None
        warning_count = 0
        with self.data_path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as error:
                    _fail("JSON_DECODE_ERROR", str(error), path=f"line {line_number}")
                errors = sorted(self.validator.iter_errors(record), key=lambda error: [str(part) for part in error.absolute_path])
                if errors:
                    error = errors[0]
                    json_path = "$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path)
                    sample_id = str(record.get("sample", {}).get("sample_id", "")) or None
                    _fail("JSON_SCHEMA", error.message, path=f"line {line_number}:{json_path}", sample_id=sample_id)
                sample_id = str(record["sample"]["sample_id"])
                if sample_id in sample_ids:
                    _fail("DUPLICATE_SAMPLE_ID", "sample_id is duplicated within input file", path=f"line {line_number}:$.sample.sample_id", sample_id=sample_id)
                sample_ids.add(sample_id)
                manifest = record["dataset_manifest"]
                identity = tuple(manifest[key] for key in (
                    "dataset_name", "dataset_release", "split", "source_file", "file_sha256", "adapter_version", "schema_version"
                ))
                if manifest_identity is None:
                    manifest_identity = identity
                elif identity != manifest_identity:
                    _fail("FILE_MANIFEST_MISMATCH", "embedded manifests differ within one input file", path=f"line {line_number}:$.dataset_manifest", sample_id=sample_id)
                warning_count += len(validate_relations(record))
                records.append(record)
        if not records or manifest_identity is None:
            _fail("EMPTY_INPUT", "input file contains no records", path=str(self.data_path))
        report = GateAReport(
            input_path=str(self.data_path.resolve()),
            actual_sha256=self.data_sha256,
            expected_sha256=self.expected_sha256,
            schema_id=self.schema_id,
            schema_sha256=self.schema_sha256,
            validator_version=GATE_A_VALIDATOR_VERSION,
            total_records=len(records),
            passed_records=len(records),
            failed_records=0,
            warning_count=warning_count,
            dataset_name=str(manifest_identity[0]),
            dataset_release=str(manifest_identity[1]),
            split=str(manifest_identity[2]),
            repair_manifest_path=None if self.repair_manifest_path is None else str(self.repair_manifest_path.resolve()),
            repair_manifest_sha256=self.repair_manifest_sha256,
            repair_rule_version=self.repair_rule_version,
        )
        self._cached = (records, report)
        return self._cached

    def validate_all(self) -> GateAReport:
        return self._load_and_validate_all()[1]

    def load_selected(self, sample_ids: Iterable[str]) -> tuple[PlatformInputBundle, ...]:
        wanted = set(sample_ids)
        records, _ = self._load_and_validate_all()
        found = {record["sample"]["sample_id"]: record for record in records if record["sample"]["sample_id"] in wanted}
        missing = wanted - set(found)
        if missing:
            raise KeyError(f"sample ids not found: {sorted(missing)}")
        return tuple(self.map_record(found[sample_id]) for sample_id in sorted(found))

    def load_all(self) -> tuple[PlatformInputBundle, ...]:
        records, _ = self._load_and_validate_all()
        return tuple(self.map_record(record) for record in records)

    @staticmethod
    def map_record(record: Mapping[str, Any]) -> PlatformInputBundle:
        sample, manifest = record["sample"], record["dataset_manifest"]
        sample_id = str(sample["sample_id"])
        context_indexes = {document["context_id"]: int(document["raw_locator"]["context_index"]) for document in record["documents"]}
        documents = tuple(
            Document(
                sample_id=sample_id,
                context_index=context_indexes[document["context_id"]],
                truth_context_id=document["context_id"],
                title=document.get("title"),
                text=document["text"],
                sentences=tuple(DocumentSentence(sentence_index=sentence["sent_id"], text=sentence["text"]) for sentence in document["sentences"]),
                is_supporting_context=document["is_supporting_context"],
                raw_locator=document.get("raw_locator", {}),
            )
            for document in record["documents"]
        )
        sources = {source["source_id"]: source for source in record["sources"]}
        links = {link["claim_id"]: link for link in record["claim_source_links"]}
        parents: dict[str, list[str]] = {claim["claim_id"]: [] for claim in record["claims"]}
        for edge in record["reasoning_graph"]["edges"]:
            parents[edge["to_claim_id"]].append(edge["from_claim_id"])
        claims = []
        for claim in record["claims"]:
            link = links[claim["claim_id"]]
            refs = []
            for source_id in link["source_ids"]:
                source = sources[source_id]
                refs.append(EvidenceRef(
                    evidence_id=source_id,
                    truth_source_id=source_id,
                    context_ref=ContextRef(sample_id=sample_id, context_index=context_indexes[source["context_id"]]),
                    granularity=SourceGranularity(source["granularity"]),
                    sentence_ids=() if source["sent_id"] is None else (source["sent_id"],),
                    paragraph_idx=source["paragraph_idx"],
                    char_start=source["char_start"],
                    char_end=source["char_end"],
                    locator_origin=source["source_origin"],
                    reference_origin=ReferenceOrigin.LOCAL_DOCUMENT,
                    link_relation=link["relation"],
                    link_validation_status=link["validation_status"],
                    requires_human_audit=record["semantic_screening"]["requires_human_audit"],
                    raw_locator=source.get("raw_locator", {}),
                ))
            claims.append(AtomicClaim(
                claim_id=f"seed:{claim['claim_id']}",
                claim_text=claim["claim_text"],
                source_refs=tuple(refs),
                parent_claim_ids=(),
                communication_hop=0,
                truth_claim_id=claim["claim_id"],
                truth_annotation_status=claim["annotation_status"],
                metadata={
                    "truth_claim_kind": claim["claim_kind"],
                    "truth_parent_claim_ids": sorted(parents[claim["claim_id"]]),
                    "structured_form": claim["structured_form"],
                },
            ))
        question = Question(
            question_id=sample_id,
            text=sample["question"],
            dataset_ref=":".join((manifest["dataset_name"], manifest["dataset_release"], manifest["split"])),
            question_type=sample["question_type"],
            reasoning_hop_count=record["reasoning_graph"]["hop_count"],
            metadata={
                "answerability": sample["answerability"],
                "question_template": musique_question_template(sample_id) if manifest["dataset_name"] == "MuSiQue" else None,
            },
        )
        screening = record["semantic_screening"]
        provenance = DatasetTruthProvenance(
            dataset_name=manifest["dataset_name"],
            release=manifest["dataset_release"],
            split=manifest["split"],
            source_file=manifest["source_file"],
            file_sha256=manifest["file_sha256"].lower(),
            adapter_version=manifest["adapter_version"],
            semantic_screening_method=screening["screening_method"],
            semantic_screening_model=screening["screening_model"],
            semantic_screening_prompt_version=screening["screening_prompt_version"],
            validation_status=record["validation"]["status"],
            requires_human_audit=screening["requires_human_audit"],
        )
        return PlatformInputBundle(
            question=question,
            documents=documents,
            seed_claims=tuple(claims),
            truth_reasoning_graph=dict(record["reasoning_graph"]),
            truth_provenance=provenance,
        )
