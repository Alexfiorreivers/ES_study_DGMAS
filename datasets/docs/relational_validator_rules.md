> Historical full-snapshot documentation. Some referenced inputs/outputs are now held in the separate editorial store after the rights review. This report does not establish public availability of those records.

# Data Truth Schema 3.0: relational validation rules

Relational-validation contract localized from the accepted specification. Rule identifiers and normative distinctions are retained. This document specifies the contract; the packaged converter validators implement the original mechanical checks and do not replace semantic audit.

## 1. Purpose and gates

JSON Schema checks object shape, field types, enumerations and local conditions. Cross-array foreign keys, uniqueness, graph structure and cross-field consistency also require relational validation. Apply the same core contract before Task B freezes final silver/gold-audit files and independently at platform Gate 0. Records failing the contract cannot be marked `validation.status=qualified` or admitted as formal inputs. Maintain a versioned shared implementation and conformance examples; do not maintain divergent meanings across the two gates.

Relational validation is distinct from the experiment policy gate. The order is manifest identity, Schema3 shape, relational constraints, experimental-policy applicability, then runtime. Passing data validation does not imply compatibility with every topology or allocation policy.

## 2. Input scope

Only final silver or gold-audit records for `2WikiMultiHopQA` or `MuSiQue` are accepted: `normalization_status=normalized`, `answerability=1`, `validation.status=qualified`, and `validation.errors=[]`. Candidate pools, exclusions, semantic-screening intermediates, sidecars, edit histories, runtime messages and evaluation results are outside Schema3 input scope.

## 3. Manifest and file rules

- **M01:** Compute SHA-256 on the actual configured JSON/JSONL input and compare with the frozen configuration hash. `dataset_manifest.file_sha256` identifies the frozen source data; `source_file` is a portable locator hint, not a replacement for identity. Embedded manifests in one file must agree on dataset name/release/split, source file/hash, adapter version and schema version.
- **M02:** Manifest dataset name, release and split must equal the corresponding sample fields. Top-level and manifest schema versions must both be `3.0`.
- **M03:** `sample.sample_id` must be unique within an input. For combined inputs, additionally check global `(dataset, dataset_release, split, sample_id)` uniqueness.

## 4. Keys and references

- **R01:** Context IDs, claim IDs and source IDs must each be unique per sample. Sentence IDs must be unique within their document; global sentence-ID uniqueness is not required.
- **R02:** Every source refers to exactly one existing document. Its title must equal that document's title, including paired nulls.
- **R03:** Each link references an existing claim and existing, nonduplicated source IDs. Official gold sources may remain unreferenced after semantic screening: retaining an unreferenced source is allowed and produces `UNREFERENCED_OFFICIAL_SOURCE`, not rejection or deletion. Such sources still require official origin, valid locator and all localization checks.
- **R04:** Graph roots and both edge endpoints reference existing claims. Self-loops and identical duplicate edges are forbidden.

## 5. Claim–source sets

- **C01:** Every claim has exactly one accepted link. Because all Schema3 links are `accepted`, this equals exactly one link per claim. No missing claim link or link to an absent claim is allowed.
- **C02:** `claim_kind` follows the number of distinct sources in that link: one is `direct`, two or more is `derived`. This expresses source cardinality only; it does not replace relation semantics or runtime message enums.
- **C03:** `joint_entailment` requires at least two sources. `entails` should use one source; multiple sources require an error and either joint entailment or claim decomposition. `supports` is allowed without asserting strict entailment but still follows C02.
- **C04:** Each claim is an independently truth-evaluable atomic proposition. Multiple independently evaluable facts should be split in Task B and assigned their own unique source sets. Automatic heuristics may warn, but semantic or human audit is required for this quality rule.

## 6. Document/source localization

- **D01:** The contexts flagged `is_supporting_context=true` equal the contexts of the complete source catalog. Contexts referenced by accepted links are a subset; none can be flagged false. Official supporting documents/sources may remain unreferenced by final links. The document catalog can retain every context. The flag concerns the truth layer, not agent visibility; `AgentSpec` and allocation policy control visibility.
- **D02 (2Wiki):** Every document has nonempty sentences. Sources use sentence granularity; paragraph and character indices are null. Each source's sentence ID matches exactly one sentence, with identical text and document title. Dataset-native `raw_locator` is provenance; arbitrary extensions are not interpreted by the platform.
- **D03 (MuSiQue paragraph):** `paragraph_idx` is nonnegative and matches the native paragraph position; `sent_id=null`; source text/title equal document text/title. Document sentences may be empty.
- **D04 (MuSiQue sentence):** The paragraph index is nonnegative and native-position aligned. The sentence ID matches exactly one document sentence; text/title match exactly. Human-highlighted sentences retain their original paragraph-local IDs, even when only highlighted sentences are retained. `raw_locator` preserves paragraph/sentence position and annotation provenance without requiring platform interpretation of extension keys.
- **D05:** Sources have `source_origin=official_gold` and `locator_status=valid`. Official locator provenance alone does not prove human-audited semantic support. Character offsets are null in both current profiles; enabling character localization requires a schema/profile upgrade.

## 7. Silver and gold audit

- **A01:** For silver claims, reviewer and review timestamp are either both null or both present (including automatic semantic screening such as `gpt:<model>`). Incomplete legacy pairs are normalized to paired nulls during migration. Automatic reviewer metadata does not promote silver to human gold. A final silver link still marked `needs_review=true` produces at least a warning, with admission decided by experiment configuration.
- **A02:** Gold-audit claims preserve official source provenance. Their unique links have `needs_review=false`, a nonempty reviewer and a timezone-aware RFC3339 review timestamp. Human decisions are represented by content and these status fields; edit histories remain outside Schema3. Mixed silver/gold claims within one sample are allowed; checks are claim-specific.

## 8. Reasoning graphs

- **G01:** The directed graph must be acyclic. Roots denote final reasoning exits, or comparison participants without a separate conclusion claim, and must be nonempty. Root IDs equal all graph sinks. Every nonroot must reach a root.
- **G02:** Every claim appears as a root or edge endpoint. Isolated uncovered claims are forbidden; a single-claim sample has that claim as its sole root and no edges.
- **G03:** `hop_count` is longest dependency depth in the claim graph, not source count. Nodes without incoming edges start at depth 1. Inference/requires/supports edges add one; comparison edges add zero. Recompute maximum depth and match the declaration. Pure 2Wiki comparison is usually depth 1, while other types follow actual dependencies (currently often 2), never a universal hard-coded value. MuSiQue's official 2/3/4-hop question type is a different dimension: claim-graph depth can differ, including depth 2 for 3-hop and depth 1 or 2 for 4-hop items.
- **G04:** A legacy hyperedge with a target becomes one binary edge from each source to that target. All incoming edges to one target jointly form its dependency parent set, not alternative paths. A targetless 2Wiki comparison must not invent a target, bidirectional edges or a claim: omit that edge, retain participants as roots, and preserve graph type/depth. If a legacy target has semantically alternative hyperedge groups, Schema3 cannot preserve those groups and migration must explicitly fail; current frozen datasets do not use that shape.

## 9. Time and status

- **T01:** Nonnull screening/review/validation timestamps require RFC3339 with `Z` or an explicit timezone offset. Naive local timestamps are invalid.
- **T02:** Any relational failure prevents qualified status. Final `errors` are empty. Accepted nonblocking issues go into stable, countable warnings. `validator_version` names the actually executed validator, never a future version or placeholder.

## 10. Suggested diagnostic codes

| Error | Meaning |
|---|---|
| MANIFEST_HASH_MISMATCH | Input hash differs from frozen identity |
| MANIFEST_SAMPLE_MISMATCH | Dataset/release/split inconsistency |
| DUPLICATE_ID | Duplicate context/claim/source/local-sentence key |
| BROKEN_FOREIGN_KEY | Missing referenced object |
| CLAIM_LINK_CARDINALITY | Missing or multiple accepted links per claim |
| CLAIM_KIND_SOURCE_COUNT | Direct/derived does not match source count |
| RELATION_SOURCE_COUNT | Relation/source count mismatch |
| LOCATOR_MISMATCH | Source does not match document paragraph/sentence |
| SUPPORTING_CONTEXT_MISMATCH | Supporting flags and source-context set differ |
| GOLD_AUDIT_METADATA | Missing reviewer/timezone timestamp or unresolved review flag |
| GRAPH_CYCLE | Directed cycle |
| GRAPH_COVERAGE | Uncovered claim or no route to a root |
| HOP_COUNT_MISMATCH | Declared and computed graph depth differ |
| TIMESTAMP_INVALID | Invalid or timezone-free timestamp |

Suggested nonblocking warnings: `UNREFERENCED_OFFICIAL_SOURCE` (retained official source outside accepted links), `SILVER_NEEDS_REVIEW` (silver still requires review), `SILVER_INCOMPLETE_REVIEW_METADATA_DROPPED` (incomplete legacy pair normalized to nulls), and `TARGETLESS_COMPARISON_REPRESENTED_BY_ROOTS` (comparison represented by roots and graph type).

## 11. Minimum Gate 0 output

Report file path/logical locator, actual and expected SHA-256, schema ID and validator version, total/passed/failed/warning counts, failed sample IDs with error codes and JSON paths, and final pass/fail. Failure prevents experiment startup: runtime must not guess, repair or skip invalid records. Experimental allocation applicability remains a separate policy-gate decision.
