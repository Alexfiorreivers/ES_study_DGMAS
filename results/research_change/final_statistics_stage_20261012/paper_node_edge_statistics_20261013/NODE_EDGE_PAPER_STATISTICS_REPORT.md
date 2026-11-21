> Historical full-snapshot documentation. Some referenced inputs/outputs are now held in the separate editorial store after the rights review. This report does not establish public availability of those records.

# Node and edge statistics for the frozen exploratory substudy

> **Version notice (2026-10-15):** This is a faithful English translation of the historical 2026-10-13 node/edge report. Its statements that terminal union was not yet completed describe that date only. Terminal-union adjudication and statistics were completed on 2026-10-15; consult `../terminal_union_statistics_20261015/TERMINAL_UNION_STATISTICS_REPORT.md` and the integrated report for the final status. No historical results or denominators are replaced here.

Date: 2026-10-13 (Asia/Shanghai). This report completes message-node and dependency-edge statistics for the frozen 60-question, 680-original-protocol-observation panel, including human-audit primary estimates, question/condition/stratum results, paired contrasts, descriptive intervals, candidate usability and sensitivity. **It is neither a terminal-union report nor the full original M3 confirmatory analysis.** The union rationale is in `UNION_DESIGN_ASSESSMENT.md`.

## 1. Study scope and valid denominators

2Wiki has 40 questions, ten in each of four types. MuSiQue has 20 questions with six question-stratum-by-hop cells containing 6, 4, 3, 1, 4 and 2 questions. DeepSeek averages r1/r2 within the same question, condition and protocol before equal-question aggregation; Qwen has r1 only for each topology. All observations use the original protocol, with no repair or matched supplemental observations.

Identity checks separate 520 DeepSeek 1.0.4 primary-comparison observations, 80 older-M observations, 40 Qwen-chain observations and 40 star_bidirectional observations. Older protocols and auxiliary topologies do not enter primary condition comparisons. The 680 observations are not 680 independent questions.


| Analysis cell | Questions | Observations | Node scopes | Edge scopes |
| --- | --- | --- | --- | --- |
| 2wiki DS A1 1.0.4 | 40 | 80 | 1000 | 400 |
| 2wiki DS A2 1.0.4 | 40 | 80 | 1000 | 400 |
| 2wiki DS B0 1.0.4 | 40 | 80 | 200 | NA (no edges) |
| 2wiki DS B1 1.0.4 | 40 | 80 | 600 | NA (no edges) |
| 2wiki DS M 1.0.4 | 40 | 80 | 1000 | 400 |
| musique DS B0 1.0.4 | 20 | 40 | 122 | NA (no edges) |
| musique DS B1 1.0.4 | 20 | 40 | 366 | NA (no edges) |
| musique DS M 1.0.4 | 20 | 40 | 610 | 244 |
| 2wiki DS M 1.0.1c-r2 | 40 | 80 | 1000 | 400 |
| 2wiki Qwen M 1.0.1 | 40 | 40 | 500 | 200 |
| 2wiki Qwen M 1.0.1 star | 40 | 40 | 700 | 400 |

Original formal review covered 769 node and 559 edge records. From the remaining populations, 633 of 6,329 nodes were reviewed across 24 strata, and 189 of 1,885 edges across eight strata. Thus 1,402 nodes and 748 edges have itemwise review; the 5,696 unsampled nodes and 1,696 unsampled edges do not have itemwise human-final status. The 633 node items are human-review forms; this analysis generated M2-validated conversion records retaining `is_final=false`, not replacements for the formal adjudication registry.

Original risk-directed review enters as exact evidence rather than proportionally extrapolated evidence. The remainder uses fixed N_h/n_h weights. The primary population estimate is original formal review plus weighted sample expansion over the remaining population. Sampled items are already represented in the latter and must not be counted again. Review includes author LRR review, evidence checking and sign-off, and cannot collectively be described as independent blind review.

## 2. Metrics and statistical methods

CSR denotes complete semantic equivalence; ESS requires complete equivalence plus exact equality to the canonical source set; VSSR denotes sufficiently supported valid source substitution; AA requires complete equivalence and current sources assessed as fully_supported. All four use the relevant message-node truth-scope denominator; disposition=decided is not a substitute. Five support outcomes are mutually exclusive under M2 and sum to the valid denominator.

`review_status=decided` differs from `disposition=decided`. All reviewed analysis records have resolved review status. Absent is an observed failure to express the claim and counts as nonsurvival in the CSR denominator. Reviewed disposition=missing does not mean engineering failure or a missing judgment file. Nonequivalence can also be semantic_negative, so disposition cannot replace claim_presence. Engineering failures, missing judgments and needs_review are not automatically zeros.

Edge ClaimRetention uses claim_event other than not_applicable as denominator. ExactSourceRetention uses retained/rewritten/split/merged, with its numerator restricted to the same event domain. ValidSubstitution uses valid/invalid substitution as denominator. Not_applicable is not an error. Multiple source_events can apply, so source-event distributions need not be mutually exclusive.

Primary in-scope tables use direct HT expansion. Each observation's estimated metric count is divided by its actual complete scope count, repetitions are averaged within question, and questions receive equal weight. Dataset aggregates weight strata by frozen question counts. Estimated group weights need not equal actual group scope counts; linear HT question, small-stratum or small-condition estimates can leave [0,1]. They are not question-level correctness probabilities and are not clipped. MuSiQue B0's 108.42% question-macro CSR illustrates this instability.

Candidate-assisted difference correction is also reported: original exact review + candidate metrics for the entire remainder + Σw×(sample human metric − original candidate metric). It uses the complete candidate structure to reduce direct-expansion variation, retaining HT as primary and assigning no new labels to unsampled records. It was added after the first grouped results, with its rationale and edge-numerator applicability correction recorded in `ANALYSIS_AMENDMENT.md`; it is not presented as preregistered. Edge rule proxies were reconstructed after review, so their difference correction is only a descriptive reference.

Intervals use 5,000 stratified question-level percentile-bootstrap replicates and seed 20261013, resampling within dataset-by-question-stratum cells while retaining every condition and r1/r2 pair of a question. They are **95% between-question descriptive bootstrap intervals with fixed audit weights**. Audit samples are not resampled; these are not full two-stage design confidence intervals and exclude unknown annotation bias. MuSiQue 4hop/2 has one question, so its between-question variation cannot be estimated. No confirmatory p-values, Holm results or significance claims are provided.

## 3. Overall node distributions


| Disposition | Original exact 769 | Reviewed sample 633 | Remaining 6329 estimate | Total 7098 estimate | Percentage of 7098 |
| --- | --- | --- | --- | --- | --- |
| decided | 269.00 | 186.00 | 1,862.62 | 2,131.62 | 30.03 |
| missing | 10.00 | 248.00 | 2,467.00 | 2,477.00 | 34.90 |
| semantic_negative | 490.00 | 199.00 | 1,999.38 | 2,489.38 | 35.07 |

The following is the weighted distribution over all message-node scopes, not a question macro or terminal CSR. Pooling models/protocols serves only to inventory the frozen panel, not estimate a population model effect.


| Message-node metric | HT estimated count | HT % | Original exact + candidate % | Difference-adjusted % |
| --- | --- | --- | --- | --- |
| CSR | 2,335.76 | 32.91 | 32.69 | 33.12 |
| ESS | 1,983.80 | 27.95 | 27.47 | 27.76 |
| VSSR | 128.20 | 1.81 | 1.72 | 2.00 |
| AA | 2,092.00 | 29.47 | 28.97 | 29.54 |


| Support outcome | HT estimated count | Percentage of 7098 |
| --- | --- | --- |
| FullSupport | 2,092.00 | 29.47 |
| PartialSupport | 20.00 | 0.28 |
| NotSupport | 5.00 | 0.07 |
| SourceMissing | 218.76 | 3.08 |
| ClaimDropped | 4,762.24 | 67.09 |

In this cross-sectional table, ClaimDropped includes absent, partial and uninterpretable outcomes, meaning the node does not fully express the equivalent claim. It cannot directly be called propagation-caused claim loss. Source identity differs from support: ESS can hold with insufficient support, while valid substitution does not count as ESS.

## 4. Message-node results for primary DeepSeek conditions

These are all-message-node question-macro percentage estimates. Each question contributes one two-repeat mean per condition, while its internal metric retains the node-by-truth-scope process denominator. Both initial-read and communication layers are included. Under division of labor, a node failing to express facts held by other nodes does not imply terminal information loss.


| Condition | Questions | CSR HT | ESS HT | VSSR HT | AA HT |
| --- | --- | --- | --- | --- | --- |
| 2wiki DS A1 1.0.4 | 40 | 31.24 | 18.62 | 1.66 | 20.28 |
| 2wiki DS A2 1.0.4 | 40 | 29.06 | 26.93 | 2.14 | 29.06 |
| 2wiki DS B0 1.0.4 | 40 | 94.53 | 93.28 | 1.25 | 94.53 |
| 2wiki DS B1 1.0.4 | 40 | 37.48 | 37.06 | 0.42 | 37.48 |
| 2wiki DS M 1.0.4 | 40 | 26.27 | 25.58 | 0.69 | 26.27 |
| musique DS B0 1.0.4 | 20 | 108.42 | 80.71 | 0.00 | 80.71 |
| musique DS B1 1.0.4 | 20 | 31.94 | 27.63 | 0.00 | 27.63 |
| musique DS M 1.0.4 | 20 | 31.69 | 22.44 | 1.68 | 24.12 |

Candidate-assisted difference-adjustment sensitivity results follow, as percentages [95% descriptive interval]. Both direct HT and adjusted views remain available. Full candidate baselines, sampled-item replacement views and communication-layer results are in the supplementary outputs.


| Condition | CSR adjusted | ESS adjusted | VSSR adjusted | AA adjusted |
| --- | --- | --- | --- | --- |
| 2wiki DS A1 1.0.4 | 30.38 [30.00, 31.00] | 18.81 [18.00, 19.56] | 1.56 [0.62, 2.69] | 20.38 [20.00, 21.00] |
| 2wiki DS A2 1.0.4 | 30.50 [30.00, 31.25] | 28.00 [26.50, 29.25] | 2.38 [1.00, 3.87] | 30.38 [29.75, 31.13] |
| 2wiki DS B0 1.0.4 | 100.00 [100.00, 100.00] | 94.06 [88.75, 98.12] | 5.94 [1.88, 11.25] | 100.00 [100.00, 100.00] |
| 2wiki DS B1 1.0.4 | 34.17 [33.33, 35.42] | 32.08 [30.83, 33.13] | 2.08 [0.62, 3.96] | 34.17 [33.33, 35.42] |
| 2wiki DS M 1.0.4 | 30.50 [30.00, 31.25] | 28.75 [27.50, 29.75] | 1.75 [0.50, 3.25] | 30.50 [30.00, 31.25] |
| musique DS B0 1.0.4 | 96.46 [92.71, 100.00] | 70.00 [50.00, 90.00] | 0.00 [0.00, 0.00] | 70.00 [50.00, 90.00] |
| musique DS B1 1.0.4 | 35.44 [32.92, 40.07] | 26.20 [20.00, 32.41] | 0.00 [0.00, 0.00] | 26.20 [20.00, 32.41] |
| musique DS M 1.0.4 | 35.04 [30.42, 40.33] | 24.19 [18.69, 29.07] | 1.68 [0.00, 5.05] | 25.87 [20.60, 30.46] |

For example, adjusted 2Wiki B0 CSR of 100% [100%,100%] only means that the candidate-assisted view has no between-question variation for these questions and observed audit discrepancies. It does not establish correctness of all unreviewed records. The same applies to 0% [0%,0%] and zero-width contrast intervals: they establish neither perfect reliability, no difference nor equivalence.

## 5. Paired condition contrasts

Differences are M minus comparator in percentage points; n counts paired questions after averaging r1/r2. HT/adjusted differences reflect sparse audit coverage and candidate assistance. Selective choice of estimation view cannot establish robustness.


| Dataset | Contrast | Metric | n questions | HT difference [interval] | Difference-adjusted contrast [interval] | Candidate-baseline contrast |
| --- | --- | --- | --- | --- | --- | --- |
| 2wiki | M-B0 | CSR | 40 | -68.26 [-107.07, -31.44] | -69.50 [-70.00, -68.75] | -69.50 |
| 2wiki | M-B0 | ESS | 40 | -67.70 [-107.15, -30.76] | -65.31 [-68.81, -60.62] | -65.31 |
| 2wiki | M-B0 | VSSR | 40 | -0.56 [-2.50, 1.44] | -4.19 [-8.44, -1.00] | -4.19 |
| 2wiki | M-B0 | AA | 40 | -68.26 [-107.07, -31.44] | -69.50 [-70.00, -68.75] | -69.50 |
| 2wiki | M-B1 | CSR | 40 | -11.20 [-22.38, -0.06] | -3.67 [-4.17, -3.33] | -3.67 |
| 2wiki | M-B1 | ESS | 40 | -11.48 [-22.72, -0.34] | -3.33 [-3.67, -2.92] | -3.33 |
| 2wiki | M-B1 | VSSR | 40 | 0.27 [-1.25, 2.07] | -0.33 [-1.17, 0.25] | -0.33 |
| 2wiki | M-B1 | AA | 40 | -11.20 [-22.38, -0.06] | -3.67 [-4.17, -3.33] | -3.67 |
| 2wiki | M-A1 | CSR | 40 | -4.97 [-16.12, 6.75] | 0.13 [0.00, 0.38] | 0.13 |
| 2wiki | M-A1 | ESS | 40 | 6.97 [-2.49, 16.33] | 9.94 [9.00, 10.88] | 9.94 |
| 2wiki | M-A1 | VSSR | 40 | -0.97 [-3.93, 1.25] | 0.19 [-0.81, 1.19] | 0.19 |
| 2wiki | M-A1 | AA | 40 | 5.99 [-3.65, 15.33] | 10.13 [10.00, 10.38] | 10.13 |
| 2wiki | M-A2 | CSR | 40 | -2.79 [-14.06, 7.77] | 0.00 [0.00, 0.00] | 0.00 |
| 2wiki | M-A2 | ESS | 40 | -1.34 [-12.67, 9.35] | 0.75 [0.00, 1.75] | 0.75 |
| 2wiki | M-A2 | VSSR | 40 | -1.45 [-4.72, 1.25] | -0.62 [-1.50, 0.00] | -0.62 |
| 2wiki | M-A2 | AA | 40 | -2.79 [-14.06, 7.77] | 0.12 [0.00, 0.37] | 0.12 |
| musique | M-B0 | CSR | 20 | -76.73 [-150.15, -18.18] | -61.42 [-68.25, -53.19] | -64.38 |
| musique | M-B0 | ESS | 20 | -58.27 [-130.04, -2.92] | -45.81 [-60.48, -29.42] | -47.08 |
| musique | M-B0 | VSSR | 20 | 1.68 [0.00, 5.05] | 1.68 [0.00, 5.05] | 0.00 |
| musique | M-B0 | AA | 20 | -56.59 [-128.91, -1.26] | -44.13 [-60.07, -26.85] | -47.08 |
| musique | M-B1 | CSR | 20 | -0.24 [-16.03, 13.86] | -0.40 [-6.96, 6.16] | -0.49 |
| musique | M-B1 | ESS | 20 | -5.19 [-19.72, 7.71] | -2.01 [-8.49, 4.46] | -0.42 |
| musique | M-B1 | VSSR | 20 | 1.68 [0.00, 5.05] | 1.68 [0.00, 5.05] | 0.00 |
| musique | M-B1 | AA | 20 | -3.51 [-18.68, 9.91] | -0.33 [-7.32, 6.66] | -0.42 |

M–B0 message-node differences cannot be written as communication reducing terminal system performance: B0 has one centralized node per question, whereas M has five initial-read/communication nodes per observation, with different node-coverage denominators. M–B1 likewise needs union analysis to answer terminal-set retention. M–A1/A2 have more similar node composition but still require edge and subsequent terminal-union context and remain associations within this frozen sample.

In the 2Wiki difference-adjusted view, M–A1 contrasts are 0.13 points for CSR, 9.94 for ESS and 10.13 for AA; direct HT contrasts are −4.97, 6.97 and 5.99 with wider intervals. One may describe different condition contrasts for source identity/support and claim expression in the candidate-assisted results, but not infer confirmatory causation. Small candidate-assisted M–A2 contrasts do not demonstrate equivalence. MuSiQue adjusted M–B1 CSR is −0.40 and ESS −2.01 points; both intervals cross zero, precluding claims of stable improvement or degradation.

## 6. Overall edge distributions and applicable events


| Disposition | Original exact 559 | Reviewed sample 189 | Remaining 1885 estimate | Total 2444 estimate | Percentage of 2444 |
| --- | --- | --- | --- | --- | --- |
| not_applicable | 393.00 | 140.00 | 1,397.00 | 1,790.00 | 73.24 |
| decided | 66.00 | 44.00 | 437.74 | 503.74 | 20.61 |
| semantic_negative | 100.00 | 5.00 | 50.26 | 150.26 | 6.15 |


| Metric | HT numerator | HT applicable denominator | Percentage within applicable denominator |
| --- | --- | --- | --- |
| EdgeClaimRetention | 626.00 | 654.00 | 95.72 |
| EdgeExactSourceRetention | 517.95 | 631.00 | 82.08 |
| EdgeValidSubstitution | 1.00 | 1.00 | 100.00 |

Exact source retention on an edge refers to parent–child event status, not canonical ESS or sufficient support. The 100% valid-substitution rate comes from **one applicable event**, so it cannot establish generally reliable substitution. Absence of sampled missing/needs_review outcomes does not prove absence among unreviewed edges.

Seventeen original formal Qwen edges have claim_event=claim_dropped together with source_set_retained_exact (five chain, twelve star). Labels and event frequencies are preserved, but these records lie outside ExactSourceRetention's domain and enter neither numerator nor denominator. An unconditional numerator from the older calculation function would yield condition rates above 100%. This report corrects the count/domain alignment with traceable excluded counts, without rewriting human adjudication.


| Condition | Questions/observations/scopes | ClaimRetention % (denominator) | ExactSourceRetention % (denominator) | ValidSubstitution % (denominator) |
| --- | --- | --- | --- | --- |
| 2wiki DS A1 1.0.4 | 40/80/400 | 98.04 (102.00) | 0.99 (101.00) | NA (0.00) |
| 2wiki DS A2 1.0.4 | 40/80/400 | 100.00 (102.00) | 100.00 (102.00) | NA (0.00) |
| 2wiki DS M 1.0.4 | 40/80/400 | 100.00 (83.37) | 100.00 (83.37) | NA (0.00) |
| musique DS M 1.0.4 | 20/40/244 | 95.90 (97.47) | 86.61 (97.47) | 100.00 (1.00) |
| 2wiki DS M 1.0.1c-r2 | 40/80/400 | 100.00 (62.32) | 100.00 (62.32) | NA (0.00) |
| 2wiki Qwen M 1.0.1 | 40/40/200 | 86.84 (53.21) | 100.00 (46.21) | NA (0.00) |
| 2wiki Qwen M 1.0.1 star | 40/40/400 | 90.24 (153.63) | 100.00 (138.63) | NA (0.00) |

B0/B1 have no communication edges, so every edge-condition metric is NA, never zero. Question-paired M–A1/A2 event-frequency contrasts are in `paired_condition_differences.csv`; they use all edge scopes within each question, unlike the applicable-event denominators above. Full claim/source/support event distributions are in supplementary tables.

## 7. Node-candidate usability


| Comparison field | Agreement/633 | Sample agreement % | Stratified weighted agreement % |
| --- | --- | --- | --- |
| alignment | 632/633 | 99.84 | 99.84 |
| all_primary_fields | 627/633 | 99.05 | 99.04 |
| claim_presence | 628/633 | 99.21 | 99.20 |
| content_truth | 632/633 | 99.84 | 99.84 |
| disposition | 628/633 | 99.21 | 99.20 |
| runtime_source_ids | 628/633 | 99.21 | 99.20 |
| source_marker_status | 628/633 | 99.21 | 99.20 |
| support_fine | 627/633 | 99.05 | 99.04 |

Comparisons normalize JSON booleans to M2 string enums. The six records with at least one discrepancy are 292, 571, 585, 619, 621 and 627. Record 292 changes only support_fine; the other five change disposition. Source localization/support for 571/619/621, valid alternative sources for 627 and the missing target predicate for 585 follow final review, not outdated table values. Itemwise discrepancies, reasons and confusion matrices are provided separately.

**Usability conclusion: original node candidates support clearly labeled descriptive statistics and sensitivity analysis, and can serve as auxiliary variables for human-sample-corrected estimation. They do not justify promoting all candidates to itemwise human semantic truth.** This judgment rests on empirical stratified-sample agreement within the remaining 6,329 records and comparisons between population metrics and candidate views. It implies neither a 99% correctness probability for each unsampled candidate nor equal accuracy for rare fields, small condition contrasts or cross-node union.

The 769 original reviews include risk-directed selection and are excluded from the 633-item agreement denominator. Agreement on seven primary fields is not accuracy on all M2 fields, qualification or union. The audit is not independent double-blind relabeling of every item; candidate exposure and common-method bias may occur and should be disclosed.

Across all node scopes, the largest difference between direct HT and original-exact-plus-original-candidate CSR/ESS/VSSR/AA is **0.51 percentage points**. This supports similarity of aggregate distributions, not stability in each question stratum or contrast. Direct HT varies substantially in sparse strata; grouped comparisons require the full supplements.

Edge-candidate evidence is separate: only three sampled records had genuine original candidates, with 3/3 agreement on four fields. The other 186 were post-review reconstructions using original node candidates and frozen rules: disposition agreement is 185/186 and four-field agreement 182/186. All 139 structurally clear inapplicable cases agree, whereas the harder E1 retained-endpoint stratum has four-field agreement of only 43/47 (91.49%). High node agreement cannot automatically raise confidence in edges or union.

## 8. Worst-case ranges and auxiliary models

The following ranges make no assumption that unreviewed candidates are valid. Assigning every unreviewed record metric values of 0 or 1 yields conservative identification bounds constrained by reviewed evidence, not 95% intervals or predictions. There are 5,696 unreviewed nodes and 1,696 unreviewed edges. With no additional missing/needs_review items to assign, their positive/negative sensitivity cases coincide, while unreviewed-candidate error remains possible.


| Scope | Metric | Reviewed scopes | Unreviewed scopes | Conservative lower bound % | Conservative upper bound % |
| --- | --- | --- | --- | --- | --- |
| node | CSR | 1402 | 5696 | 6.89 | 87.14 |
| node | ESS | 1402 | 5696 | 5.72 | 85.97 |
| node | VSSR | 1402 | 5696 | 0.66 | 80.91 |
| node | AA | 1402 | 5696 | 6.35 | 86.60 |
| edge | ClaimApplicable | 748 | 1696 | 8.80 | 78.19 |
| edge | ClaimRetained | 748 | 1696 | 7.65 | 77.05 |
| edge | SourceExact | 748 | 1696 | 4.30 | 73.69 |
| edge | SubstitutionValid | 748 | 1696 | 0.04 | 69.44 |

Auxiliary models use the same 40 questions only. Qwen chain is paired with DeepSeek 1.0.1c-r2 chain; Qwen star is listed separately. Differences in model, service, prompt and execution cannot be interpreted as causal model-size or topology effects.


| Auxiliary condition | CSR HT | ESS HT | AA HT | CSR difference-adjusted | ESS difference-adjusted | AA difference-adjusted |
| --- | --- | --- | --- | --- | --- | --- |
| 2wiki DS M 1.0.1c-r2 | 33.99 | 30.60 | 33.99 | 30.38 | 28.50 | 31.38 |
| 2wiki Qwen M 1.0.1 | 18.00 | 15.38 | 14.00 | 22.50 | 18.38 | 19.62 |
| 2wiki Qwen M 1.0.1 star | 18.93 | 15.09 | 18.21 | 21.43 | 17.05 | 18.12 |

## 9. Results wording for the paper

In the 60-question exploratory semantic panel fixed in advance, 680 original-protocol observations cover 7,098 message-node–truth-claim scopes and 2,444 dependency-edge–truth-claim scopes. The node population combines 769 existing formal human judgments with stratified human-sample estimation for the remaining 6,329 records. Among 633 sampled nodes, candidate/human disposition agrees for 628/633 (99.21%), and all seven primary fields agree for 627/633 (99.05%); weighted agreements are 99.20% and 99.04%, respectively. These results support labeled sensitivity analysis and sample-based correction using candidates, without granting itemwise human-final status to unreviewed records.

Across all message-node scopes, direct human-sample-weighted estimates are 32.91% complete semantic survival, 27.95% exact canonical source-set retention, 1.81% valid substitution and 29.47% simultaneous complete semantics and sufficient current support. These distinguish claim expression, source identity and current support, and do not measure terminal system performance. In the edge estimates, 73.24% of scopes have no applicable propagation event and cannot be counted as semantic errors. Applicable-denominator retention rates and event incidence over all scopes are reported separately.

Condition results aggregate by question, averaging DeepSeek r1/r2 before paired differences. Sparse human audits within questions and rare events produce substantial variation in direct weighted estimates and fixed-weight between-question descriptive intervals; complete-candidate and human-sample difference-adjusted sensitivity views are also reported. Interpretations are limited to this frozen exploratory panel; repair, supplemental and full-M3 confirmatory effects were not tested. **Historical status as of 2026-10-13:** terminal union had not been established, so this report does not conclude on terminal CSR/ESS contrasts. See the version notice above for the completed 2026-10-15 union analysis.

## 10. Verification and delivery boundaries

- All frozen-manifest hashes matched; original node/edge validators passed; existing overall distributions and candidate agreements were independently recomputed.
- M2 payload checks passed for 7098 node candidates, 769 original formal node judgments, 633 human-review analysis conversions, 1885 edge candidates, 559 original formal edge judgments and 189 sampled edge reviews. Original candidate-envelope batch/source-hash metadata remains available; audit provenance was not removed.
- Original inputs, candidates, human forms, approval identities and frozen sampling were unchanged. Statistical scripts, denominator ledgers, question-level tables, table SHA-256 values and version information are stored alongside this report.
- Complete four-stratum 2Wiki, six-stratum MuSiQue and hop-group results are in `SUPPLEMENTARY_TABLES.md` and CSVs. Degenerate single-question bootstrap intervals do not prove high precision.
- Completed node/edge review need not be repeated. **Historical next step at this report's date:** retaining the original terminal research question required terminal-union semantic judgments and quality review, as described separately. That work was subsequently completed on 2026-10-15.

File index: `panel_cells.csv` identifies the panel; `denominator_ledger.csv` records actual denominators and estimated represented totals; `observation_metrics.csv` and `question_metrics.csv` are analysis base tables; `condition_and_stratum_tables.csv` and `paired_condition_differences.csv` contain full paper statistics; `node_candidate_agreement.csv`, `node_candidate_disagreements.csv` and `node_candidate_confusion.csv` cover candidate audits; `scope_global_metrics.csv` contains totals and event frequencies; `unreviewed_worst_case_bounds.csv` contains conservative bounds; the two `*_analysis_ledger.jsonl` files record identities and judgment provenance; `verification.json`, `m2_validation.json` and `manifest.json` provide checks and hashes.
