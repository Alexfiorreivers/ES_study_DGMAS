#!/usr/bin/env python3
"""Deterministic 2WikiMultiHopQA dev -> unified data-truth candidate adapter with documents.

Python 3.11 standard library only.

Normative sources:
  - historical://dataset-preparation/2wiki/rules.md
  - historical://dataset-preparation/2wiki/relation_process_rules.md

This adapter performs structural preprocessing only. It does not decide whether a
source semantically supports a claim; that decision belongs to the GPT screening
stage and later human audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ADAPTER_VERSION = "2.0.0"
SCHEMA_VERSION = "2.0"
RULE_VERSION = "1.0.0"
DATASET_NAME = "2WikiMultiHopQA"
RELEASE = "20210407"
SPLIT = "dev"
QUESTION_TYPES = ("compositional", "comparison", "inference", "bridge_comparison")


class AdapterError(Exception):
    """A record-level, rule-addressable adapter failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class AliasIndex:
    """Exact alias lookup. Ambiguous aliases intentionally do not resolve."""

    alias_to_qids: Mapping[str, tuple[str, ...]]

    def resolve(self, value: str) -> str | None:
        qids = self.alias_to_qids.get(normalize_text(value), ())
        return qids[0] if len(qids) == 1 else None


def normalize_text(value: Any) -> str:
    """Rules §QID/link confidence: NFKC, case-fold, trim, collapse whitespace."""

    text = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    return " ".join(text.split())


def possessive(subject: str) -> str:
    """relation_process_rules: return the complete English possessive string."""

    return subject + ("'" if subject.casefold().endswith("s") else "'s")


def indefinite_article(word: str) -> str:
    """Adapter-only approximation; GPT must check pseudo-vowel pronunciations."""

    stripped = word.lstrip()
    return "an" if stripped and stripped[0].casefold() in "aeiou" else "a"


def lcs_length(left: str, right: str) -> int:
    """Memory-efficient longest-common-subsequence length."""

    if len(left) < len(right):
        left, right = right, left
    row = [0] * (len(right) + 1)
    for char_left in left:
        diagonal = 0
        for index, char_right in enumerate(right, start=1):
            previous = row[index]
            if char_left == char_right:
                row[index] = diagonal + 1
            elif row[index - 1] > row[index]:
                row[index] = row[index - 1]
            diagonal = previous
    return row[-1]


def normalized_lcs(left: str, right: str) -> float:
    """Rules §link: LCS divided by the shorter normalized string length."""

    a, b = normalize_text(left), normalize_text(right)
    denominator = min(len(a), len(b))
    if denominator == 0:
        return 0.0
    return round(lcs_length(a, b) / denominator, 6)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _schema_type_matches(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return True


def _resolve_local_ref(root: Mapping[str, Any], reference: str) -> Mapping[str, Any]:
    if not reference.startswith("#/"):
        raise ValueError(f"Only local JSON Schema references are supported: {reference}")
    node: Any = root
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        node = node[part]
    if not isinstance(node, dict):
        raise ValueError(f"Schema reference is not an object: {reference}")
    return node


def validate_json_schema(
    value: Any,
    schema: Mapping[str, Any],
    root_schema: Mapping[str, Any] | None = None,
    path: str = "$",
) -> list[str]:
    """Validate the JSON-Schema keywords used by data_truth_schema.json.

    This is deliberately a small, auditable standard-library validator, not a
    general replacement for the jsonschema package.
    """

    root = root_schema or schema
    if "$ref" in schema:
        return validate_json_schema(value, _resolve_local_ref(root, schema["$ref"]), root, path)
    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None:
        expected_types = [expected] if isinstance(expected, str) else expected
        if not any(_schema_type_matches(value, item) for item in expected_types):
            return [f"{path}: expected type {expected!r}, got {type(value).__name__}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: value does not equal const {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {value!r} is outside enum")
    if isinstance(value, str):
        if len(value) < int(schema.get("minLength", 0)):
            errors.append(f"{path}: string is shorter than minLength")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{path}: string does not match pattern {schema['pattern']!r}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: number is below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: number is above maximum")
    if isinstance(value, list):
        if len(value) < int(schema.get("minItems", 0)):
            errors.append(f"{path}: array is shorter than minItems")
        if schema.get("uniqueItems"):
            canonical = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
            if len(canonical) != len(set(canonical)):
                errors.append(f"{path}: array items are not unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(validate_json_schema(item, item_schema, root, f"{path}[{index}]"))
    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        for key, child in value.items():
            if key in properties:
                errors.extend(validate_json_schema(child, properties[key], root, f"{path}.{key}"))
            else:
                additional = schema.get("additionalProperties", True)
                if additional is False:
                    errors.append(f"{path}: unexpected property {key!r}")
                elif isinstance(additional, dict):
                    errors.extend(validate_json_schema(child, additional, root, f"{path}.{key}"))
    return errors


def load_aliases(path: Path) -> AliasIndex:
    """Load 2Wiki JSONL aliases; use only explicit aliases/demonyms, never fuzzy."""

    buckets: dict[str, set[str]] = defaultdict(set)
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid alias JSONL at line {line_number}: {exc}") from exc
            qid = row.get("Q_id")
            if not isinstance(qid, str) or not qid.startswith("Q"):
                continue
            for alias in row.get("aliases", []) + row.get("demonyms", []):
                if isinstance(alias, str) and alias.strip():
                    buckets[normalize_text(alias)].add(qid)
    return AliasIndex({key: tuple(sorted(values)) for key, values in buckets.items()})


def load_relation_templates(path: Path) -> dict[str, dict[str, Any]]:
    payload = read_json(path)
    relations = payload.get("relations") if isinstance(payload, dict) else None
    if not isinstance(relations, dict) or len(relations) != 34:
        raise ValueError("relation_templates.json must contain exactly 34 relations")
    return relations


def render_claim(triple: Sequence[Any], relations: Mapping[str, Mapping[str, Any]]) -> str:
    """Rules §claims: convert one source triple to one initial claim_text."""

    if len(triple) != 3 or not all(isinstance(value, str) and value.strip() for value in triple):
        raise AdapterError("invalid_evidence_triple", f"Invalid evidence triple: {triple!r}")
    subject, predicate, object_ = (value.strip() for value in triple)
    definition = relations.get(predicate)
    if definition is None:
        raise AdapterError("unknown_relation", f"No relation template for {predicate!r}")
    template = definition.get("template")
    if not isinstance(template, str):
        raise AdapterError("claim_generation_failed", f"Invalid template for {predicate!r}")
    try:
        claim = template.format(
            subject=subject,
            object=object_,
            subject_possessive=possessive(subject),
            indefinite_article=indefinite_article(object_),
        )
    except (KeyError, ValueError) as exc:
        raise AdapterError("claim_generation_failed", f"Template failure for {predicate!r}: {exc}") from exc
    if not claim.strip():
        raise AdapterError("claim_generation_failed", f"Empty claim for {predicate!r}")
    return claim


def valid_qid(value: Any) -> str | None:
    return value if isinstance(value, str) and value.startswith("Q") else None


def official_qid_map(record: Mapping[str, Any]) -> dict[str, str]:
    """Rules §QID priority 1: evidences_id aligned with evidence triples."""

    evidences = record.get("evidences", [])
    evidence_ids = record.get("evidences_id", [])
    result: dict[str, str] = {}
    if not isinstance(evidence_ids, list) or len(evidence_ids) != len(evidences):
        return result
    for triple, id_triple in zip(evidences, evidence_ids):
        if not isinstance(triple, list) or not isinstance(id_triple, list) or len(triple) != 3 or len(id_triple) != 3:
            continue
        for entity, qid in ((triple[0], id_triple[0]), (triple[2], id_triple[2])):
            resolved = valid_qid(qid)
            if isinstance(entity, str) and resolved:
                result.setdefault(normalize_text(entity), resolved)
    return result


def has_complete_evidences_id(record: Mapping[str, Any]) -> bool:
    """True for the preferred bridge-comparison subset with fully aligned ID triples."""

    evidences = record.get("evidences", [])
    evidence_ids = record.get("evidences_id", [])
    return (
        isinstance(evidences, list)
        and isinstance(evidence_ids, list)
        and len(evidences) > 0
        and len(evidence_ids) == len(evidences)
        and all(isinstance(row, list) and len(row) == 3 for row in evidence_ids)
    )


def entity_id_title_map(record: Mapping[str, Any]) -> dict[str, str]:
    """Rules §QID priority 2: align entity_ids with supporting-fact titles."""

    raw_ids = record.get("entity_ids")
    supporting = record.get("supporting_facts", [])
    if not isinstance(raw_ids, str) or not isinstance(supporting, list):
        return {}
    qids = raw_ids.split("_") if raw_ids else []
    titles = [row[0] for row in supporting if isinstance(row, list) and len(row) == 2 and isinstance(row[0], str)]
    if len(qids) != len(titles):
        return {}
    result: dict[str, str] = {}
    for title, qid in zip(titles, qids):
        resolved = valid_qid(qid)
        if resolved:
            result.setdefault(normalize_text(title), resolved)
    return result


def resolve_entity_qid(
    entity: str,
    official: Mapping[str, str],
    title_ids: Mapping[str, str],
    aliases: AliasIndex,
) -> tuple[str | None, str]:
    key = normalize_text(entity)
    if key in official:
        return official[key], "evidences_id"
    if key in title_ids:
        return title_ids[key], "entity_ids"
    alias_qid = aliases.resolve(entity)
    if alias_qid:
        return alias_qid, "id_aliases"
    return None, "unresolved"


def parse_context_blocks(record: Mapping[str, Any]) -> list[tuple[str, list[str]]]:
    """Rules §16: validate and retain every native 2Wiki context block."""

    context = record.get("context")
    if not isinstance(context, list) or not context:
        raise AdapterError("invalid_context", "context must be a non-empty array")
    blocks: list[tuple[str, list[str]]] = []
    for context_index, block in enumerate(context):
        if (
            not isinstance(block, list)
            or len(block) != 2
            or not isinstance(block[0], str)
            or not isinstance(block[1], list)
            or any(not isinstance(sentence, str) for sentence in block[1])
        ):
            raise AdapterError(
                "invalid_context",
                f"Malformed context block at index {context_index}: {block!r}",
            )
        blocks.append((block[0], list(block[1])))
    return blocks


def locate_supporting_sources(
    record: Mapping[str, Any],
    context_blocks: Sequence[tuple[str, Sequence[str]]],
) -> list[tuple[int, str, int, str]]:
    """Rules §6/§16: resolve every official locator to one unique context."""

    supporting = record.get("supporting_facts")
    if not isinstance(supporting, list):
        raise AdapterError("invalid_locator", "supporting_facts must be an array")
    located: list[tuple[int, str, int, str]] = []
    for locator in supporting:
        if not isinstance(locator, list) or len(locator) != 2:
            raise AdapterError("invalid_locator", f"Malformed supporting fact: {locator!r}")
        title, sent_id = locator
        if not isinstance(title, str) or not isinstance(sent_id, int) or isinstance(sent_id, bool):
            raise AdapterError("invalid_locator", f"Malformed locator values: {locator!r}")
        title_matches = [
            (context_index, sentences)
            for context_index, (context_title, sentences) in enumerate(context_blocks)
            if context_title == title
        ]
        valid_matches = [
            (context_index, sentences)
            for context_index, sentences in title_matches
            if 0 <= sent_id < len(sentences)
        ]
        if not title_matches or not valid_matches:
            raise AdapterError("invalid_locator", f"Unresolvable locator: {locator!r}")
        if len(valid_matches) != 1:
            raise AdapterError("ambiguous_locator", f"Locator matches multiple contexts: {locator!r}")
        context_index, sentences = valid_matches[0]
        located.append((context_index, title, sent_id, sentences[sent_id]))
    return located


def build_documents(
    context_blocks: Sequence[tuple[str, Sequence[str]]],
    located_sources: Sequence[tuple[int, str, int, str]],
) -> list[dict[str, Any]]:
    """Rules §16: build the complete DocumentCatalog without semantic rewriting."""

    supporting_context_indexes = {row[0] for row in located_sources}
    documents: list[dict[str, Any]] = []
    for context_index, (title, sentences) in enumerate(context_blocks):
        documents.append({
            "context_index": context_index,
            "title": title,
            "text": " ".join(sentences),
            "sentences": [
                {"sentence_index": sentence_index, "text": text}
                for sentence_index, text in enumerate(sentences)
            ],
            "is_supporting_context": context_index in supporting_context_indexes,
            "raw_locator": {"context_index": context_index, "title": title},
        })
    return documents

def infer_parents(evidences: Sequence[Sequence[str]], claim_ids: Sequence[str]) -> list[list[str]]:
    """Rules §reasoning: explicit dependency by exact object -> later subject equality."""

    parents: list[list[str]] = []
    for current_index, triple in enumerate(evidences):
        subject = normalize_text(triple[0])
        matches = [
            claim_ids[prior]
            for prior in range(current_index)
            if normalize_text(evidences[prior][2]) == subject
        ]
        parents.append(matches)
    return parents


def longest_claim_path(parents: Sequence[Sequence[str]], claim_ids: Sequence[str]) -> int:
    depths: dict[str, int] = {}
    for claim_id, parent_ids in zip(claim_ids, parents):
        depths[claim_id] = 1 + max((depths[parent] for parent in parent_ids), default=0)
    return max(depths.values(), default=0)


def build_reasoning_graph(
    sample_id: str,
    question_type: str,
    claim_ids: Sequence[str],
    parents: Sequence[Sequence[str]],
) -> dict[str, Any]:
    edges: list[dict[str, Any]] = []
    for target_id, source_ids in zip(claim_ids, parents):
        if source_ids:
            edges.append({"source_node_ids": list(source_ids), "target_node_id": target_id, "relation": "inference"})
    if question_type in {"comparison", "bridge_comparison"}:
        used_as_parent = {parent for group in parents for parent in group}
        leaves = [claim_id for claim_id in claim_ids if claim_id not in used_as_parent]
        edges.append({"source_node_ids": leaves, "target_node_id": None, "relation": "comparison"})
    return {
        "reasoning_graph_id": f"{sample_id}:reasoning_graph",
        "sample_id": sample_id,
        "node_ids": list(claim_ids),
        "edges": edges,
        "reasoning_hop_count": longest_claim_path(parents, claim_ids),
        "graph_type": question_type,
        "graph_origin": "derived",
    }


def build_candidate(
    record: Mapping[str, Any],
    record_index: int,
    source_file: Path,
    source_hash: str,
    aliases: AliasIndex,
    relations: Mapping[str, Mapping[str, Any]],
    review_threshold: float = 0.9,
) -> dict[str, Any]:
    """Transform one record. Each numbered block corresponds to a rules.md stage."""

    # Rules §hard exclusions: required sample/type fields and array parity.
    original_id = record.get("_id")
    question_type = record.get("type")
    evidences = record.get("evidences")
    supporting = record.get("supporting_facts")
    if not isinstance(original_id, str) or not original_id:
        raise AdapterError("missing_required_field", "Missing _id")
    if not isinstance(record.get("question"), str) or not isinstance(record.get("answer"), str):
        raise AdapterError("missing_required_field", "question/answer must be strings")
    if question_type not in QUESTION_TYPES:
        raise AdapterError("invalid_question_type", f"Unsupported type: {question_type!r}")
    if not isinstance(evidences, list) or not isinstance(supporting, list):
        raise AdapterError("missing_required_field", "evidences/supporting_facts must be arrays")
    if len(supporting) != len(evidences):
        raise AdapterError("sf_evidence_count_mismatch", f"{len(supporting)} != {len(evidences)}")
    if not evidences:
        raise AdapterError("missing_required_field", "evidences must not be empty")

    # Rules §16: validate complete context and resolve every supporting locator.
    context_blocks = parse_context_blocks(record)
    located = locate_supporting_sources(record, context_blocks)
    documents = build_documents(context_blocks, located)
    sample_id = f"{DATASET_NAME}:{RELEASE}:{SPLIT}:{original_id}"
    claim_ids = [f"{sample_id}:claim:{index}" for index in range(len(evidences))]

    # Rules §claims/QID: one claim per triple, direct claim_kind, strict QID priority.
    official = official_qid_map(record)
    title_ids = entity_id_title_map(record)
    claims: list[dict[str, Any]] = []
    qid_warnings: dict[str, str] = {}
    triples: list[list[str]] = []
    for index, raw_triple in enumerate(evidences):
        if not isinstance(raw_triple, list) or len(raw_triple) != 3:
            raise AdapterError("invalid_evidence_triple", f"Evidence {index} is malformed")
        triple = [str(value).strip() if isinstance(value, str) else "" for value in raw_triple]
        claim_text = render_claim(triple, relations)
        subject_qid, subject_origin = resolve_entity_qid(triple[0], official, title_ids, aliases)
        object_qid, object_origin = resolve_entity_qid(triple[2], official, title_ids, aliases)
        if subject_qid is None:
            qid_warnings[f"claim_{index}_subject_qid"] = f"Unresolved QID for {triple[0]!r}"
        if object_qid is None:
            qid_warnings[f"claim_{index}_object_qid"] = f"Unresolved QID for {triple[2]!r}"
        triples.append(triple)
        claims.append({
            "claim_id": claim_ids[index],
            "sample_id": sample_id,
            "claim_text": claim_text,
            "structured_form": {
                "subject": triple[0], "predicate": triple[1], "object": triple[2],
                "subject_qid": subject_qid, "object_qid": object_qid,
            },
            "claim_kind": "direct",
            "parent_claim_ids": [],
            "derivation_operator": "triple_to_claim_text",
            "derivation_rule_version": RULE_VERSION,
            "annotation_status": "candidate",
        })

    parents = infer_parents(triples, claim_ids)
    for claim, parent_ids in zip(claims, parents):
        claim["parent_claim_ids"] = parent_ids

    # Rules §sources/QID: source QID only on exact title/entity equality in its linked claim.
    sources: list[dict[str, Any]] = []
    for index, (context_index, title, sent_id, text) in enumerate(located):
        structured = claims[index]["structured_form"]
        entity_qid = None
        if title == structured["subject"]:
            entity_qid = structured["subject_qid"]
        elif title == structured["object"]:
            entity_qid = structured["object_qid"]
        sources.append({
            "source_id": f"{sample_id}:source:{index}", "sample_id": sample_id,
            "context_index": context_index, "title": title, "entity_qid": entity_qid,
            "paragraph_idx": None, "sent_id": sent_id, "char_start": None, "char_end": None,
            "text": text, "granularity": "sentence", "source_origin": "official_gold",
            "raw_locator": {
                "context_index": context_index, "title": title, "sent_id": sent_id,
            },
            "locator_status": "valid",
        })

    # Rules §official_pairs: natural-index links are candidates, not semantic verdicts.
    links: list[dict[str, Any]] = []
    for index, (claim, source) in enumerate(zip(claims, sources)):
        structured = claim["structured_form"]
        confidence = max(
            normalized_lcs(source["title"], structured["subject"]),
            normalized_lcs(source["title"], structured["object"]),
        )
        links.append({
            "link_id": f"{sample_id}:link:{index}", "claim_id": claim["claim_id"],
            "source_ids": [source["source_id"]], "relation": "direct_entailment",
            "validation_status": "unreviewed", "automatic_match_reason": "official_pairs",
            "confidence": confidence, "needs_review": confidence < review_threshold,
            "reviewer": None, "review_timestamp": None, "rule_version": RULE_VERSION,
        })

    warning_map = dict(qid_warnings)
    for index, link in enumerate(links):
        if link["needs_review"]:
            warning_map[f"link_{index}_low_structural_confidence"] = str(link["confidence"])

    candidate = {
        "schema_version": SCHEMA_VERSION,
        "dataset_manifest": {
            "dataset_name": DATASET_NAME, "release": RELEASE, "split": SPLIT,
            "source_file": str(source_file), "file_sha256": source_hash,
            "adapter_version": ADAPTER_VERSION, "schema_version": SCHEMA_VERSION,
        },
        "semantic_screening": {
            "method": None, "model": None, "reasoning_effort": None,
            "prompt_version": None, "rule_version": RULE_VERSION,
            "screened_at": None, "requires_human_audit": True,
        },
        "sample": {
            "sample_id": sample_id, "original_sample_id": original_id,
            "dataset_name": DATASET_NAME, "release": RELEASE, "split": SPLIT,
            "question": record.get("question"), "answer": record.get("answer"),
            "question_type": question_type, "answerability": 1,
            "raw_locator": {"source_file": str(source_file), "record_index": record_index},
            "normalization_status": "normalized", "exclusion_reason": None,
        },
        "documents": documents,
        "claims": claims, "sources": sources, "claim_source_links": links,
        "reasoning_graph": build_reasoning_graph(sample_id, question_type, claim_ids, parents),
        "validation": {
            "status": None, "errors": {}, "warnings": warning_map,
            "validator_version": ADAPTER_VERSION, "validated_at": None,
        },
    }
    errors = validate_contract(candidate)
    if errors:
        raise AdapterError("schema_contract_failure", "; ".join(errors))
    return candidate


def analyze_inference_graph(
    claim_ids: set[str], edges: Sequence[Mapping[str, Any]]
) -> tuple[bool, int]:
    """Return (is_acyclic, longest claim-node path) for inference edges.

    Rules §reasoning defines ``reasoning_hop_count`` as the number of claim
    nodes on the longest dependency path. Comparison edges are terminal
    operators rather than claim dependencies, so they do not add a hop.
    """

    predecessors: dict[str, set[str]] = {claim_id: set() for claim_id in claim_ids}
    successors: dict[str, set[str]] = {claim_id: set() for claim_id in claim_ids}
    for edge in edges:
        if edge.get("relation") != "inference":
            continue
        target = edge.get("target_node_id")
        source_ids = edge.get("source_node_ids", [])
        if target not in claim_ids or not isinstance(source_ids, list):
            continue
        for source_id in source_ids:
            if source_id in claim_ids:
                predecessors[target].add(source_id)
                successors[source_id].add(target)

    indegree = {claim_id: len(parent_ids) for claim_id, parent_ids in predecessors.items()}
    ready = sorted(claim_id for claim_id, degree in indegree.items() if degree == 0)
    depths = {claim_id: 1 for claim_id in ready}
    processed = 0
    while ready:
        claim_id = ready.pop(0)
        processed += 1
        for child_id in sorted(successors[claim_id]):
            depths[child_id] = max(depths.get(child_id, 1), depths[claim_id] + 1)
            indegree[child_id] -= 1
            if indegree[child_id] == 0:
                ready.append(child_id)
                ready.sort()

    is_acyclic = processed == len(claim_ids)
    return is_acyclic, max(depths.values(), default=0)


def validate_contract(candidate: Mapping[str, Any]) -> list[str]:
    """Standard-library contract validation for required fields/enums/ID references."""

    errors: list[str] = []
    required = {
        "schema_version", "dataset_manifest", "semantic_screening", "sample", "documents",
        "claims", "sources", "claim_source_links", "reasoning_graph", "validation",
    }
    missing = required - set(candidate)
    if missing:
        errors.append(f"missing top-level fields: {sorted(missing)}")
        return errors
    manifest = candidate.get("dataset_manifest", {})
    sample = candidate.get("sample", {})
    sample_id = sample.get("sample_id") if isinstance(sample, dict) else None
    if candidate.get("schema_version") != manifest.get("schema_version"):
        errors.append("top-level and manifest schema_version differ")
    for field in ("dataset_name", "release", "split"):
        if manifest.get(field) != sample.get(field):
            errors.append(f"manifest/sample {field} values differ")
    if sample.get("question_type") not in QUESTION_TYPES:
        errors.append("invalid question_type")
    documents = candidate.get("documents", [])
    claims = candidate.get("claims", [])
    sources = candidate.get("sources", [])
    links = candidate.get("claim_source_links", [])
    document_indexes = [
        row.get("context_index") for row in documents if isinstance(row, dict)
    ]
    if len(document_indexes) != len(documents) or len(set(document_indexes)) != len(documents):
        errors.append("document context_index values are missing or duplicated")
    document_map = {
        row.get("context_index"): row for row in documents if isinstance(row, dict)
    }
    for document in documents:
        context_index = document.get("context_index")
        sentences = document.get("sentences", [])
        if context_index is None or document.get("raw_locator", {}).get("context_index") != context_index:
            errors.append(f"invalid document locator: {context_index!r}")
        if document.get("raw_locator", {}).get("title") != document.get("title"):
            errors.append(f"document title differs from raw_locator: {context_index!r}")
        if [row.get("sentence_index") for row in sentences] != list(range(len(sentences))):
            errors.append(f"non-native sentence indexes: {context_index!r}")
        if document.get("text") != " ".join(row.get("text", "") for row in sentences):
            errors.append(f"document text is not the frozen sentence join: {context_index!r}")
    claim_ids = {row.get("claim_id") for row in claims if isinstance(row, dict)}
    source_ids = {row.get("source_id") for row in sources if isinstance(row, dict)}
    if len(claim_ids) != len(claims) or None in claim_ids:
        errors.append("claim IDs are missing or duplicated")
    if len(source_ids) != len(sources) or None in source_ids:
        errors.append("source IDs are missing or duplicated")
    for claim in claims:
        if claim.get("sample_id") != sample_id or claim.get("claim_kind") != "direct":
            errors.append(f"invalid claim ownership/kind: {claim.get('claim_id')}")
        if not set(claim.get("parent_claim_ids", [])).issubset(claim_ids):
            errors.append(f"invalid parent reference: {claim.get('claim_id')}")
    for source in sources:
        if source.get("sample_id") != sample_id or source.get("locator_status") != "valid":
            errors.append(f"invalid source ownership/locator: {source.get('source_id')}")
        if "document_id" in source:
            errors.append(f"obsolete document_id present: {source.get('source_id')}")
        document = document_map.get(source.get("context_index"))
        if document is None:
            errors.append(f"source has invalid context_index: {source.get('source_id')}")
            continue
        if source.get("title") != document.get("title"):
            errors.append(f"source/document title mismatch: {source.get('source_id')}")
        sent_id = source.get("sent_id")
        sentences = document.get("sentences", [])
        if not isinstance(sent_id, int) or isinstance(sent_id, bool) or not 0 <= sent_id < len(sentences):
            errors.append(f"source sent_id is outside document: {source.get('source_id')}")
        elif source.get("text") != sentences[sent_id].get("text"):
            errors.append(f"source/document sentence mismatch: {source.get('source_id')}")
    for link in links:
        if link.get("claim_id") not in claim_ids:
            errors.append(f"invalid link claim reference: {link.get('link_id')}")
        if not set(link.get("source_ids", [])).issubset(source_ids):
            errors.append(f"invalid link source reference: {link.get('link_id')}")
        if link.get("automatic_match_reason") != "official_pairs":
            errors.append(f"invalid match reason: {link.get('link_id')}")
    graph = candidate.get("reasoning_graph", {})
    if graph.get("sample_id") != sample_id:
        errors.append("reasoning graph sample_id differs from sample")
    if graph.get("graph_type") != sample.get("question_type"):
        errors.append("reasoning graph type differs from question_type")
    if set(graph.get("node_ids", [])) != claim_ids:
        errors.append("reasoning graph node_ids differ from claim IDs")
    graph_edges = graph.get("edges", [])
    for edge in graph_edges:
        if not set(edge.get("source_node_ids", [])).issubset(claim_ids):
            errors.append("reasoning edge has invalid source node")
        target = edge.get("target_node_id")
        if target is not None and target not in claim_ids:
            errors.append("reasoning edge has invalid target node")
        if edge.get("relation") not in {"inference", "comparison"}:
            errors.append("reasoning edge has invalid relation")
        if edge.get("relation") == "inference" and target is None:
            errors.append("inference edge has no target node")
    is_acyclic, recomputed_hops = analyze_inference_graph(claim_ids, graph_edges)
    if not is_acyclic:
        errors.append("reasoning graph contains an inference cycle")
    if graph.get("reasoning_hop_count") != recomputed_hops:
        errors.append(
            "reasoning_hop_count differs from recomputed longest dependency path "
            f"({graph.get('reasoning_hop_count')!r} != {recomputed_hops})"
        )

    validation = candidate.get("validation", {})
    if validation.get("status") == "qualified":
        accepted_claim_ids = {
            link.get("claim_id")
            for link in links
            if link.get("validation_status") == "accepted" and link.get("source_ids")
        }
        for claim_id in sorted(claim_ids - accepted_claim_ids):
            errors.append(f"qualified claim has no accepted source link: {claim_id}")
    return errors


def candidate_sort_key(
    candidate: Mapping[str, Any], seed: int, complete_evidence_ids: bool = False
) -> tuple[Any, ...]:
    """Rules §candidate ordering; stable hash is a deterministic final tie-break."""

    claims = candidate["claims"]
    links = candidate["claim_source_links"]
    predicates = [claim["structured_form"]["predicate"] for claim in claims]
    all_qids = all(
        claim["structured_form"][side] is not None
        for claim in claims for side in ("subject_qid", "object_qid")
    )
    warnings = candidate["validation"]["warnings"]
    average_confidence = sum(link["confidence"] for link in links) / len(links)
    stable = hashlib.sha256(f"{seed}:{candidate['sample']['original_sample_id']}".encode()).hexdigest()
    return (
        0 if all_qids else 1,
        0 if not warnings else 1,
        -average_confidence,
        0 if candidate["sample"]["question_type"] != "bridge_comparison" or complete_evidence_ids else 1,
        1 if "place of death" in predicates else 0,
        stable,
    )


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=False)
        stream.write("\n")
    temporary.replace(path)


def atomic_write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=script_dir / "raw/dev.json")
    parser.add_argument("--aliases", type=Path, default=script_dir / "raw/id_aliases.json")
    parser.add_argument("--output-dir", type=Path, default=script_dir / "2Wiki_pipeline_v2")
    parser.add_argument("--config", type=Path, default=script_dir / "adapter_config_v2.json")
    parser.add_argument("--relation-templates", type=Path, default=script_dir / "relation_templates.json")
    parser.add_argument(
        "--schema", type=Path,
        default=script_dir / "schema2.json",
    )
    parser.add_argument("--limit", type=int, help="Debug: scan at most N records after type filtering")
    parser.add_argument("--sample-id", help="Debug: process only this raw _id")
    parser.add_argument("--question-type", choices=QUESTION_TYPES, help="Debug: process one type")
    parser.add_argument("--skip-hash-check", action="store_true", help="Only for fixtures/debug inputs")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict[str, Any]:
    config = read_json(args.config)
    input_hash = sha256_file(args.input)
    alias_hash = sha256_file(args.aliases)
    expected = config["dataset"]
    if not args.skip_hash_check:
        if input_hash != expected["expected_input_sha256"]:
            raise SystemExit(f"Input SHA-256 mismatch: {input_hash}")
        if alias_hash != expected["expected_aliases_sha256"]:
            raise SystemExit(f"Alias SHA-256 mismatch: {alias_hash}")
    records = read_json(args.input)
    if not isinstance(records, list):
        raise SystemExit("Input dev.json must be a JSON array")
    aliases = load_aliases(args.aliases)
    relations = load_relation_templates(args.relation_templates)
    formal_schema = read_json(args.schema)
    candidates: dict[str, list[dict[str, Any]]] = {kind: [] for kind in QUESTION_TYPES}
    complete_ids_by_sample: dict[str, bool] = {}
    exclusions: list[dict[str, Any]] = []
    scanned = 0
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            exclusions.append({"record_index": index, "sample_id": None, "reason_code": "invalid_record", "reason": "Record is not an object", "original_record": record})
            continue
        if args.sample_id and record.get("_id") != args.sample_id:
            continue
        if args.question_type and record.get("type") != args.question_type:
            continue
        if args.limit is not None and scanned >= args.limit:
            break
        scanned += 1
        try:
            candidate = build_candidate(
                record, index, args.input.resolve(), input_hash, aliases, relations,
                float(config["confidence_review_threshold"]),
            )
        except AdapterError as exc:
            exclusions.append({
                "record_index": index, "sample_id": record.get("_id"),
                "question_type": record.get("type"), "reason_code": exc.code,
                "reason": exc.message, "original_record": record,
            })
        else:
            formal_errors = validate_json_schema(candidate, formal_schema)
            if formal_errors:
                exclusions.append({
                    "record_index": index, "sample_id": record.get("_id"),
                    "question_type": record.get("type"), "reason_code": "formal_schema_failure",
                    "reason": "; ".join(formal_errors), "original_record": record,
                })
            else:
                candidates[candidate["sample"]["question_type"]].append(candidate)
                complete_ids_by_sample[candidate["sample"]["sample_id"]] = has_complete_evidences_id(record)

    seed = int(config["selection_seed"])
    candidate_dir = args.output_dir / "candidate_pool"
    exclusion_dir = args.output_dir / "exclusions"
    manifest_dir = args.output_dir / "manifests"
    counts: dict[str, int] = {}
    for kind, rows in candidates.items():
        rows.sort(key=lambda row: candidate_sort_key(
            row, seed, complete_ids_by_sample.get(row["sample"]["sample_id"], False)
        ))
        atomic_write_jsonl(candidate_dir / f"{kind}.jsonl", rows)
        counts[kind] = len(rows)
    atomic_write_jsonl(exclusion_dir / "excluded_records.jsonl", exclusions)
    exclusion_reasons = dict(sorted(Counter(row["reason_code"] for row in exclusions).items()))
    summary = {
        "adapter_version": ADAPTER_VERSION, "schema_version": SCHEMA_VERSION,
        "input": str(args.input.resolve()), "input_sha256": input_hash,
        "aliases": str(args.aliases.resolve()), "aliases_sha256": alias_hash,
        "records_in_input": len(records), "records_scanned": scanned,
        "candidate_counts": counts, "candidate_total": sum(counts.values()),
        "excluded_total": len(exclusions), "exclusion_reasons": exclusion_reasons,
        "filters": {"sample_id": args.sample_id, "question_type": args.question_type, "limit": args.limit},
        "deterministic_selection_seed": seed, "generated_at": None,
    }
    atomic_write_json(manifest_dir / "adapter_run_manifest.json", summary)
    atomic_write_json(manifest_dir / "summary_statistics.json", {
        "candidate_counts": counts, "exclusion_reasons": exclusion_reasons,
        "candidate_total": sum(counts.values()), "excluded_total": len(exclusions),
    })
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    try:
        summary = run(parse_args(argv))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"adapter error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
