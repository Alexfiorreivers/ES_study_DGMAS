> Historical full-snapshot documentation. Some referenced inputs/outputs are now held in the separate editorial store after the rights review. This report does not establish public availability of those records.

# Terminal-union analysis specification

English companion to the Chinese source. Written on 2026-10-15 before computing this round of statistics. Human adjudications and sample discrepancies were already known; this is not a claim of preregistration.

The scope is DeepSeek 1.0.4, chain, original_protocol: 60 questions, 520 observations, and 1,366 terminal truth scopes. r1/r2 are repetitions of the same question. Conditions are M/B0/B1/A1/A2 for 2Wiki and M/B0/B1 for MuSiQue. The frozen terminal-union-primary-1.0 boundary and M2 metrics are retained: CSR means complete semantic equivalence; ESS requires equivalence and exact equality of source sets; VSSR denotes valid source substitution; AA requires equivalence and sufficient support. All use all truth scopes as denominator.

The exact component consists of 74 directly reused human-evidence records and 136 complex items reviewed exhaustively, totaling 210. The simple-proxy population contains 1,156 items; 120 were sampled across 12 strata. The other 1,036 receive no individual human labels. The primary estimator combines the exact component with stratified Horvitz–Thompson expansion:

`T_hat = T_exact + sum_h (N_h/n_h) sum_sample y`.

Report the simple population, actual audited sample, and estimated unsampled component separately. The unsampled estimate is `sum_h (N_h/n_h - 1) sum_sample y`; do not count the sample twice.

Three sensitivity views are reported alongside it: exact component plus all simple candidates; exact component plus human sample results plus unsampled candidates; and the candidate-assisted difference estimator, exact component plus all simple candidates plus `sum_sample w(human-candidate)`. The 136 complex items have no complete earlier union candidates, so their human judgments anchor all views. There is no complete original-candidate baseline.

For primary condition comparisons, normalize each observation by its actual number of truth scopes, average the two repetitions within question and condition, and then take an equally weighted question-macro mean. Do not pool datasets into a single model effect. M−B0, M−B1, and 2Wiki M−A1/M−A2 are descriptive paired differences. Preserve question-type strata. HT small-domain and individual-question contributions can exceed [0,1]; do not clip them or interpret them as individual probabilities. Sensitivity estimators can also exceed these bounds.

Two uncertainty components are distinct and cannot substitute for each other or be called a combined complete confidence interval:

1. Audit-sampling standard errors within the frozen finite population assume stratified simple random sampling without replacement: `sum_h N_h^2 (1-n_h/N_h) s_h^2/n_h`. For question-macro means and paired differences, first assign fixed coefficients to scopes and then apply the same formula. The difference estimator uses human−candidate residuals instead of y. Report estimate ±1.96 SE as an approximate 95% audit-design interval without clipping. Fixed SHA-ranking sampling relies on a seeded pseudorandom working assumption. Zero sample variance does not establish zero error among unaudited items; normal approximations are limited in small strata.
2. Retain the node/edge stratified question bootstrap with fixed audit weights: 5,000 draws, seed 20261015. Resample entire questions, retaining all conditions and both repetitions. Label the result a “95% descriptive between-question bootstrap interval.” It does not capture complete audit-sampling uncertainty; a one-question stratum supplies no within-stratum between-question variation.

Report field-level and metric-level sample agreement, weighted agreement, discrepancy lists, and worst-case bounds for unaudited items. Do not convert agreement into individual correctness probabilities. Preserve audit metadata, candidate provenance identities, and frozen denominators. Report no confirmatory p-values; do not claim three repetitions, exhaustive human review, the full experimental panel, cross-model generalization, or a formal failure-worst analysis.

New mechanical source diagnostics flag citation-identity discrepancies in frozen reused judgments or candidates only. They do not silently revise existing node adjudications. If discrepancies exist in the exact reuse stratum, disclose them in the text and provide a separate sensitivity range.
