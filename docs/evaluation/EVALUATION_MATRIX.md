# Detailed evaluation matrix

## Document identity


This repository matrix consolidates Task D `metrics_spec_v0.2.md` (September 16 discussion version), `annotation_schema_v0.2.md` and the latest statistical handoff. It is not a full translation of the two historical specifications, introduces no annotation rule and changes no frozen judgment. Historical general plans about topologies, repetitions, pending-review exclusions and human-only primary judgments do not override the completed stratified audit estimators. Frozen ledgers and analysis specifications govern the final analysis.

## 1. Objects, identities and denominators

| Object | Definition | Storage and use |
| --- | --- | --- |
| truth claim g | Atomic proposition in the truth data | Stable ID, not an array-position key |
| canonical source set S0 | Unique nonempty canonical ID set from the accepted link for g | Order-independent; duplicates, empty sets and nonunique links are data errors |
| node scope | Truth claim × evaluable message node | Round 0 is a real node; all relevant scopes form the node-coverage denominator |
| dependency edge scope | Truth claim × actual parent–child dependency edge | Visibility is not semantic causation; evaluate each parent separately |
| terminal union scope | Truth claim in an observation's terminal output set | Count each target once; do not union all historical messages |
| Independent unit | Question | Claims, nodes, edges and repetitions are nested |


The final main panel contains 60 questions, 520 runs, 4,898 node scopes, 1,444 edge scopes and 1,366 terminal scopes. Denominators are not interchangeable; edge metrics additionally have their own applicability denominators. M/A1/A2 have five nodes per run, B1 three and B0 one. B0/B1 have no communication edges. Terminal sets comprise the three initial outputs for B1, two final-communication-layer outputs for M, and the centralized output for B0.

## 2. Node semantic matrix

| Field | Values and decision |
| --- | --- |
| claim_presence | present_equivalent: full truth-conditional equivalence; present_partial: partial retention or changed conditions; absent: no acceptable expression; uninterpretable: not reliably interpretable |
| semantic_equivalence | True only for complete equivalence; paraphrase, voice alternation, aliases and lossless splitting are allowed |
| alignment_cardinality | one_to_one, one_to_many, many_to_one, many_to_many, none; validate across records |
| interpretable | yes, no, uncertain, not_applicable; judge before viewing sources |
| source_marker_status | identifiable: all markers uniquely resolve, nonempty; absent: no marker; unidentifiable: at least one unresolved; not_applicable: not fully equivalent |
| observed_source_ids | Explicit uniquely resolved current source IDs; retain original and unresolved markers |
| exact_set_survived | Equivalent, identifiable and current set equals S0 |
| source_change_status | unchanged, substituted_valid, substituted_invalid, dropped, unidentifiable, not_applicable; node reference is S0; edge reference is the parent |
| support_fine | fully_supported, partially_supported, contradicted, insufficient, not_applicable |
| content_truth | true, false, partial, unknown, not_applicable; independently compare with TruthView |
| qualification_change | Time, quantity, scope, modality, polarity, conditions, entity/coreference, comparison target, relation direction |
| review_status | decided or needs_review; latter requires reasons |


A group of expressions jointly covering one truth claim counts once. A merged expression aligned to multiple truth claims requires a separate projection and decision for each. Topic, entity or lexical overlap is insufficient for equivalence. Strengthened, weakened, broadened or narrowed truth conditions can retain lineage without full survival. Marker presence, source identity, sufficient support and factual truth are independent judgments.

## 3. Support and identity decisions

| Decision | Meaning |
| --- | --- |
| fully_supported | Current explicit sources jointly support the whole proposition and its qualifications |
| partially_supported | Supports substantive parts but leaves unsupported components; record spans |
| contradicted | Sources contradict core content or a key qualification |
| insufficient | Cannot establish the proposition without explicit contradiction |
| not_applicable | Claim is not fully equivalent or sources are not evaluable |
| substituted_valid | Changed set with full support; ESS must be false |
| substituted_invalid | Changed set with insufficient, partial or contradictory support |
| unchanged | Exact set equality does not itself establish full support |


Fully supported claims have no unsupported spans; partial support requires at least one. Missing/unidentifiable sources are not evidence-entailment judgments. A false claim with full support signals a truth/source conflict for adjudication under the frozen rules; the support label cannot overwrite truth.

## 4. Metric matrix

Let C denote full equivalence, I identifiable sources, E exact equality to S0, and F full support.

| Metric | Numerator | Denominator and interpretation |
| --- | --- | --- |
| CSR | C | All truth scopes at that level; not string matching |
| ESS | C ∧ I ∧ E | All scopes at that level; adding, removing or validly substituting a source fails exact equality |
| AA | C ∧ I ∧ F | All scopes at that level; not final-answer accuracy |
| VSSR | C ∧ I ∧ ¬E ∧ F | All scopes at that level; do not merge with ESS |
| FullSupportRate | C ∧ I ∧ F | One of five exclusive support outcomes |
| PartialSupportRate | C ∧ I ∧ partially_supported | Same |
| NotSupportRate | C ∧ I ∧ (contradicted or insufficient) | Same |
| SourceMissingRate | C ∧ (absent or unidentifiable source) | Same |
| ClaimDroppedRate | ¬C | Includes partial, absent and uninterpretable, not absent alone |
| ReviewRate (historical specification) | needs_review count | All original claims; historical exclusion is not the final audit estimator |
| SourcePrecision/Recall/F1 (extension) | Set overlap with S0 | Empty current sets scored 0 in the original spec; nonretained/unidentifiable cases NA with applicability counts |
| ExtraSourceRate (extension) | Current sources outside S0 | Current set size; empty/unidentifiable NA |


Derive the five outcomes in order: claim dropped, source missing, then full/partial/not supported. Counts must reconcile with the relevant judgment domain. Store numerators, denominators and unresolved counts; never replace NA with zero. Historical HT audit estimates use weighted numerators without assigning individual human labels to unknown records. Current candidate-replacement summaries retain candidate indicators for unreviewed records.

## 5. Edge events and applicability

| Family | Labels | Decision boundary |
| --- | --- | --- |
| Claim | claim_retained_equivalent, claim_rewritten_non_equivalent, claim_dropped, claim_added, claim_split, claim_merged | Compare the two texts directly, not just their truth-relative labels |
| Source | source_set_retained_exact, source_added_redundant, source_dropped_partial, source_dropped_all, source_substituted_valid, source_substituted_invalid, source_marker_became_unidentifiable | Jointly assess parent–child identity changes and support |
| Support | support_maintained, support_improved, support_degraded | Separate from identity retention |
| Qualification | qualification_strengthened, qualification_weakened, scope_broadened, scope_narrowed, polarity_changed, modality_changed, entity_or_coreference_shifted | Additional events, not substitutes for base semantics |
| Added origin | private_document, other_parent_message, unidentified, not_applicable | Origin relative to the current dependency edge |


When neither side has a valid alignment, retain an edge record marked not applicable with empty event arrays. Valid alignment includes equivalent and partial expressions. Read texts to determine whether partial→partial is equivalent; partial→equivalent is a non-equivalent parent–child rewrite. Split/merge may coexist with one base event. Claim retention conditions on traceable parent claims; exact source retention additionally requires identifiable parent sources; valid substitution conditions on its source-change applicability set. Use the frozen tables' `applicable_denominator_estimate` in plots and reports.

## 6. Audit, sampling and statistical boundaries


The historical human sequence evaluates semantics before showing sources, resolves markers, compares canonical sets, judges current support, independently checks truth, and then judges edge events; unresolved cases receive needs_review. Automatic systems produce candidates only. The final study combines author review, reused decisions, complete complex-case review and stratified simple-case sampling. Terminal audit: 74 reused + 136 complex = 210 exact records; 120 sampled from 1,156 simple cases. There are 330 records with review evidence and 1,036 unsampled unknowns, not 1,366 individually human-reviewed records. Historical node/edge audit frames differ from the main 520-run terminal frame.


HT equals exact counts plus Σh(Nh/nh) × sampled positives. Sampled cases are already included in the expansion and must not be added twice. Do not extrapolate positive rates from risk-directed review. Preserve question-level repetition/condition pairing before aggregation. Coarse-stratum weights can produce small-domain estimates above 100%; retain and explain them without clipping. Between-question bootstrap intervals hold audit weights fixed; audit-design intervals describe sampling error. They do not jointly cover all uncertainty. Zero-width intervals do not prove error-free data. Do not invent completed Holm, confirmatory p-value or equivalence tests.

## 7. Validation and versions


Preserve stable trajectory/run/question/claim/node/edge/annotation IDs, rule versions, input hashes, judgment origins and reasons. JSON ID arrays are unique and sorted; timestamps include time zones; annotators may be pseudonymous; credentials are excluded. Validate manifest counts, cross-record alignments, source sets, node–edge references and label constraints. Preserve the true identities of automatic_candidate, human_primary, human_adjudicated and analysis-materialized records; do not manufacture uniform final status. Changes to labels, denominators, aggregation or alignment need a new version with impact documentation. This matrix does not reopen adjudication or recompute statistics.

## Current release view

Current numerical displays use candidate_sample_corrected (node) and sample_replaced (terminal) semantics. Reviewed records supply human judgments, others retain candidates. HT and difference expansion remain supplementary historical views. [Current release](../../results/current_release/README.md) documents author revisions separately; no new record-level labels or intervals are inferred.
