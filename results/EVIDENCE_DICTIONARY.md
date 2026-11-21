> Public-scope update (2026-11-21): full mixed-content evidence referenced below is now in the separate editorial store. Only retained code, synthetic examples, identifiers and aggregate files are public candidates. Historical source paths describe the earlier full snapshot; consult the root DATA_AND_EVIDENCE_INDEX.md.

# English guide to evidence records and historical procedures

This guide describes the English publication rendering of audit and procedure records. Original source-language files remain in the external research archive. Translations do not create new reviewer decisions, infer unaudited labels, or establish a new benchmark evaluation.

## Record identities and fields

| Field or file | Meaning |
| --- | --- |
| `question_id`, `truth_claim_id` | Fixed input question and audited target claim |
| `observation_key`, `run_id`, `replicate_index` | Execution identity and repeated run within a question/condition |
| `scope_id` | Unique node×target, edge×target, or terminal-output-set×target unit |
| `scope_node_ids`, `terminal_node_ids` | Actual output boundaries, including valid empty outputs |
| `node_id::claim_id` | Namespaced terminal occurrence; prevents cross-node claim-ID collisions |
| `canonical_source_ids` | Fixed reference source set attached to the audited target |
| `runtime_source_ids` | Resolvable citations carried by accepted aligned expressions |
| `claim_presence` | `present_equivalent`, `present_partial`, `absent`, or `uninterpretable` |
| `source_marker_status` | Whether citations are identifiable, unidentifiable, absent, or inapplicable |
| `exact_set_survived` | Equality of current and canonical source sets under the contract |
| `source_change_status` | Source identity change, including valid or invalid substitutions |
| `support_fine` | Joint evidential support from the currently cited sources |
| `content_truth` | Separate content-truth assessment; not implied by citation presence |
| `alignment` | Accepted runtime/target correspondences and alignment type |
| `review_status` | Review completion state; distinct from `disposition` |
| `disposition` | Workflow classification; cannot substitute for semantic coverage |
| `origin`, `is_final` | Original annotation identity; not upgraded during analysis or packaging |
| `rationale`, `human_review_reason.md` | English reading translations of recorded reviewer explanations; original decisions remain unchanged |
| `exact_judgment`, `sample_analysis_judgment` | Previously adjudicated evidence and analytical representation of sampled human review |
| `judgment=null` | No individual human judgment; not a negative label |
| `expansion_weight`, `weight`, `sampling_stratum` | Frozen sampling-design information; not a per-item correctness probability |
| `frozen_proposal`, `original_candidate` | Candidate auxiliary information, not human-final evidence |
| `union_reuse_corrected` | One of four explicitly approved terminal-only source corrections |

## Current completion state

All 256 terminal review-form entries (136 complex plus 120 sampled simple scopes) were completed. Seventy-four other scopes reuse existing human evidence. TU-0310 accepts its own candidate rather than the accidentally pasted TU-0258 conclusion. The other five formerly pending items were adjudicated according to the author's instruction; the instruction did not authorize changing every ID in a continuous numeric range. TU-1165, TU-1182, TU-1224 and TU-1296 received terminal-only corrections for resolvable canonical paragraph references. Old node/edge judgments were not rewritten. Historical pending lists are retained only when recorded as direct statistical inputs.

## Historical frozen node/edge processing rules

The reduced panel was selected by fixed quotas and seeded question-ID ordering. It is exploratory, not a representative random sample of the full M3 study. All selected observations are original protocol; no repair or matched supplemental-contract observations are available. The historical panel contains 60 questions, 680 observations, 1,520 same-question/same-text groups, 8,676 claim occurrences, 7,098 node scopes, 960 dependencies and 2,444 edge scopes. The 1,398 terminal-group subset cannot replace all-message-node coverage.

The original procedure assigned whole-question batches to separate sessions. A group could share a semantic-alignment proposal, but every occurrence required its own source, support, qualification and truth checks. Matching text or a resolvable locator did not establish equivalence or support. Partial, ambiguous and many-to-many alignments were allowed. A node-level absence judgment required considering all claims in that node. Candidate identities remained `automatic_candidate` and `is_final=false`. Batch completion required full occurrence coverage, unique scope identities, schema validation and recorded hashes.

Edges were processed only after node coverage was complete. Empty endpoints could yield inapplicable events; structurally unchanged endpoints still required semantic alignment checks. Other dependencies were reviewed per truth claim, not assigned one blanket dependency label. Parent-relative source retention is distinct from canonical identity and current support. Invalid field combinations, unresolved identities, duplicate scopes or hash drift were stop conditions, not reasons to silently remove denominators.

## Historical quality plan and actual execution

The initial plan described six question-level blind-audit questions and 151 groups as a defect-detection check, not evidence of a low error rate. It also explicitly rejected treating all candidates as human-final labels. That plan predates the completed audit. Actual reporting follows the completed non-blind, candidate-assisted human review and stratified node/edge/terminal sampling described in the final reports. Historical aspirations for blind review must not be restated as completed blind or independent double annotation.

The final node audit has 769 exact records (269 `decided`, 490 `semantic_negative`, 10 `missing`) and 633 sampled records from 6,329. The edge audit has 559 exact and 189 sampled records from 1,885. Unreviewed records remain candidates. Questions are the aggregation and resampling unit; repeated runs, claims and edges are not independent questions. Data/model/condition/prompt/topology/observation-version identities remain separate. B0/B1 have no communication edges (NA).

## Reading judgments without changing their meaning

CSR requires complete equivalent expression; ESS adds exact canonical source-set identity; AA adds sufficient current support; VSSR records valid substitution. `ClaimDropped` is a cross-sectional non-equivalent state and does not by itself identify a propagation loss. `SourceMissing`, `FullSupport`, `PartialSupport` and `NotSupport` are the other mutually exclusive support outcomes. Applicable edge metrics each use their own event set. Multiple source events can coexist.

Detailed reviewer explanations are translated completely for reading. English evidence quotations and all identifiers/decisions are preserved; original source-language wording remains in the external archive. Translated wording is not a new reviewer statement. Historical hashes identify original records, while FILES.sha256.json verifies the current English publication bytes.
