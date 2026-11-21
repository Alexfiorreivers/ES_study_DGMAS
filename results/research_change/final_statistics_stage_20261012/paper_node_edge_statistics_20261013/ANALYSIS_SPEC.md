> Historical full-snapshot documentation. Some referenced inputs/outputs are now held in the separate editorial store after the rights review. This report does not establish public availability of those records.

# Node and edge paper-analysis specification

English companion. Version exploratory-node-edge-paper-1.0, 2026-10-13. Fixed before grouped results were computed at this stage. Overall distributions and sample agreement were already known; no retrospective claim of experiment preregistration is made.

**Historical-status note:** the union paragraph below describes this node/edge analysis stage. Terminal-union auditing and statistics were subsequently completed on 2026-10-15. The latest finalization status and final handoff take precedence; this document is not a request to reopen adjudication.

## Data and record identity

Retain the frozen 60 questions, 680 observations, 7,098 node scopes, and 2,444 edge scopes. Use the latest formal adjudications for the original 769 node and 559 edge records. Estimate the remainder with the established audit weights for 24 node strata and eight edge strata; do not resample. Convert the 633 node forms into analysis records and validate all M2 fields without rewriting formal judgment files or changing the identities of unsampled candidates.

Condition identity includes dataset, model, condition, prompt_ref, topology, and observation_version. Compare DeepSeek 1.0.4 M with 1.0.4 B0/B1/A1/A2; report 1.0.1c-r2 M separately. The Qwen panel contains chain and star_bidirectional, each with 40 questions and replicate_index=1. Keep them separate, rather than averaging them as two repetitions. Only chain can serve as a descriptive reference for DeepSeek's older chain protocol.

## Primary and sensitivity views

The primary view is the exact originally human-adjudicated component plus stratified Horvitz–Thompson expansion of the remainder: `T_hat = sum(known y) + sum(sample N_h/n_h*y)`. The sample represents the remaining population and must not be added a second time.

The candidate sensitivity baseline combines original formal human judgments with original candidates for the remainder. A further view replaces sampled candidates with their human judgments. The edge candidate view includes rule proxies reconstructed after review, which must be disclosed. The revised view replaces reviewed edges only; it does not presume that all unaudited edges have received updated endpoint adjudications.

Overall scope distributions describe only the frozen panel and use the full scope count as denominator. Grouped tables retain true scope counts and weighted represented quantities; the total weight for a group need not equal its true scope count.

## Metrics

Node: CSR is complete equivalent expression; ESS is complete equivalence with an exact canonical-source-set match; VSSR is valid substitution; AA is complete equivalence with fully_supported evidence. Five mutually exclusive support outcomes follow M2 ordering: ClaimDropped (including partial/absent/uninterpretable), SourceMissing, FullSupport, PartialSupport, and NotSupport. Here ClaimDropped is a cross-sectional lack of full equivalence, not automatic evidence that information was lost along an edge. Report disposition separately; decided is not a substitute for CSR.

Verify that absent with review_status=decided means observed semantic absence, not a missing judgment file. It contributes to CSR and related denominators and has numerator zero. Engineering failures, missing judgments, and needs_review are not treated this way. If new missing judgments or needs_review items occur, report them separately and stop estimates that depend on unconfirmed denominators. Unaudited candidates are neither missing observations nor established human-correct judgments.

Edge: under M2 definitions, ClaimRetention applies where claim_event is not not_applicable; ExactSourceRetention uses retained/rewritten/split/merged events as denominator; ValidSubstitution uses valid or invalid substitution. Report claim/source/support event distributions and applicability rates separately. source_events may have multiple selections and need not sum to 100%. Edge not_applicable is not an error.

## Aggregation and comparisons

The primary node comparison is a process description of all_message_nodes: normalize each observation by its actual node×truth scope count; for DeepSeek, average r1/r2 within question and condition, then calculate the question-macro mean. Supplementary tables stratify by communication_hop. This is neither terminal-union CSR/ESS nor a replacement for terminal primary outcomes. Absence at one node does not imply absence at other nodes for the same question.

Normalize HT question contributions by known complete scope denominators. Zero sampled contribution does not establish a zero true result for that question. Individual-question or small-stratum estimates may fall outside [0,1]; do not clip or interpret them as question-level probabilities. Complete question values from candidate views provide sensitivity references.

Show four 2Wiki strata and six MuSiQue strata separately. Within datasets, weight strata by frozen question-count proportions, equivalent to equal question-macro weighting. Do not pool datasets into one model effect. Main descriptive contrasts are M−B0, M−B1, and 2Wiki M−A1/M−A2. B0/B1 have no edges and are NA. Edge condition contrasts are M−A1/M−A2 only: use event frequencies over all edge scopes per question and separately report conditional event rates with their own applicable denominators. Rates with different condition-specific denominators are not the same outcome.

## Intervals and scope

Use seed 20261013 and 5,000 stratified question-level percentile-bootstrap draws. Within dataset×question-stratum, sample questions with replacement and preserve each question's conditions, repetitions, and scopes. Label main-table intervals “95% descriptive between-question bootstrap intervals with fixed audit weights.” They are not complete two-stage sampling-design confidence intervals: the human audit is not resimulated, unsampled annotation error is not covered, and intervals do not support confirmatory tests. MuSiQue 4hop/2 contains one question and therefore supplies no between-question variation within that stratum; explicitly flag this.

Provide condition contrasts and descriptive intervals for HT and candidate views. Add conservative identification bounds by assigning all individually unaudited scopes metric values of zero or one. Do not turn high agreement into a 99% correctness probability for each record. Do not report confirmatory p-values, Holm results, repair comparisons, or full-population engineering success rates.

## Union boundary

At this stage no new semantic union judgments are created; only requirements are inventoried and discussed against the paper design. Preserve original terminal selection. Sums, averages, OR operations over message-node labels, or unions of all historical sources do not constitute formal union judgments.

## Outputs

Paper statistical report; union-necessity assessment; scope analysis ledger; observation/question-level base tables; condition/stratum/event tables; paired differences and intervals; candidate agreement and worst-case bounds; verification records; input/output SHA-256 manifests; and rerunnable scripts. Display counts and percentages to two decimal places while retaining full floating-point precision in base tables.
