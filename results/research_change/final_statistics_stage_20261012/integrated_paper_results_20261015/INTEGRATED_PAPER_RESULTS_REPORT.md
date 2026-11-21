> Historical full-snapshot documentation. Some referenced inputs/outputs are now held in the separate editorial store after the rights review. This report does not establish public availability of those records.

# Integrated node, edge and terminal-union results for manuscript preparation

Date: 2026-10-15. This report integrates existing statistics without selecting new samples, changing the primary estimator or promoting unreviewed candidates to human adjudications. English publication rendering; the original Chinese report is retained in the external research archive.

## 1. Recommended paper narrative

The strongest supported narrative is that **message-node coverage, retention within applicable edge events and terminal-set verifiability measure different objects; complete claim expression, canonical source identity and current evidence support must also be reported separately.** In this frozen panel, M has lower terminal complete-equivalence point estimates than B0/B1. A1 shows that source masking can reduce terminal citation metrics to zero while some claims remain expressed. Small M–A2 differences do not yet establish stable benefits from source-maintenance instructions.

The results do not support a performance-improvement paper claiming that source-aware communication significantly outperforms centralized or noncommunicating reading. A measurement-and-audit study is more appropriate: different observational levels yield different results, and semantic presence does not ensure preservation of citation identity and support. All conclusions are restricted to DeepSeek 1.0.4, the fixed three-agent single-round chain protocol and the frozen questions.

## 2. Units, scope and versions across the three levels

| Level | Measurement question | Denominator / aggregation | Not interpretable as |
| --- | --- | --- | --- |
| Node | Does a message node express the target and retain its sources? | message-node×truth claim; initial-read and communication layers; average two repetitions within question | Terminal-set coverage or final-answer accuracy |
| Edge | Does a specific retention/source event occur between parent and child nodes? | Each metric has its applicable-event denominator; event frequency separately uses all edge scopes | All targets reaching the terminal; canonical ESS |
| Terminal union | Does the frozen output set fully express the target and carry supporting sources? | terminal×truth claim; each target counted once per observation; question-macro mean | Union of all historical messages, final-answer scoring or a new model answer |

The primary comparison uses 520 DeepSeek 1.0.4 original-protocol observations: 40 2Wiki questions, two repetitions each for M/B0/B1/A1/A2; 20 MuSiQue questions, two repetitions each for M/B0/B1. These correspond to 4898 node scopes, 1444 edge scopes and 1366 terminal scopes. Questions are the independent analysis units; 520 runs and repeated executions are not 520 independent questions.

The older overall node/edge report includes 680 observations, 7098 node scopes and 2444 edge scopes, additionally covering older M versions, Qwen chain and Qwen star. Its overall CSR=32.91% describes a mixed-panel inventory and cannot be subtracted from primary-scope terminal CSR=75.18% to claim terminal improvement. Main-text condition comparisons use only 1.0.4. Qwen/older-protocol results can be supplementary, but do not establish cross-model robustness of the current primary protocol.

**Version boundary:** node/edge results come from the 2026-10-13 report; terminal results come from human review and reuse corrections completed on 2026-10-15. New union review corrected several paragraph-citation errors, plus four reused union records TU-1165, TU-1182, TU-1224 and TU-1296. Older node/edge files were not updated. The levels are neither three independent replications nor a transition decomposition with fully harmonized itemwise labels. In particular, B0 node and terminal views represent the same observed content; their statistical differences mainly reflect sampling design, estimators and adjudication versions, not propagation changes within B0.

## 3. Primary condition results

CSR means complete equivalent target expression; ESS requires complete equivalence and exact canonical source-set equality; AA requires complete equivalence and sufficient current evidence; VSSR denotes valid source substitution. Node/terminal metrics use all truth scopes at the corresponding level. AA is not final-answer accuracy. M is the full communication protocol, B0 centralized reading, B1 independent reading without communication, A1 source masking and A2 removal of source-maintenance instructions.

The following values are primary HT equal-question macro estimates, in percent. Node views contain five message nodes per observation for M/A1/A2, three for B1 and one for B0; terminal scoring uses the common per-observation truth scope. Values may be compared conceptually but must not be subtracted across levels to calculate propagation effects.


| Dataset | Condition | Node CSR | Node ESS | Node AA | Terminal CSR | Terminal ESS | Terminal AA |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2wiki | M | 26.27 | 25.58 | 26.27 | 51.04 | 48.54 | 51.04 |
| 2wiki | B0 | 94.53 | 93.28 | 94.53 | 104.32 | 92.48 | 104.32 |
| 2wiki | B1 | 37.48 | 37.06 | 37.48 | 93.12 | 85.00 | 93.12 |
| 2wiki | A1 | 31.24 | 18.62 | 20.28 | 51.88 | 0.00 | 0.00 |
| 2wiki | A2 | 29.06 | 26.93 | 29.06 | 48.61 | 44.86 | 48.61 |
| musique | M | 31.69 | 22.44 | 24.12 | 59.87 | 58.20 | 59.87 |
| musique | B0 | 108.42 | 80.71 | 80.71 | 97.12 | 97.12 | 97.12 |
| musique | B1 | 31.94 | 27.63 | 27.63 | 91.53 | 89.87 | 91.53 |

Node MuSiQue B0 CSR=108.42% and terminal 2Wiki B0 CSR=104.32% are unconstrained linear audit-sampling estimates, not actual survival rates above 100%. Section 7 explains their interpretation and sensitivity.

### 3.1 M versus B0: centralized-reading reference

For both datasets, node and terminal primary estimates place M below B0. Terminal results provide the key evidence: M−B0 CSR is −53.27 percentage points for 2Wiki and −37.26 for MuSiQue; candidate-assisted difference estimates are −50.00 and −33.12 points, respectively.

A supported statement is: within frozen terminal evaluation, M has lower target-coverage point estimates than centralized reference B0, with the same direction in primary and candidate-assisted views. Large node gaps cannot directly be treated as system-performance gaps, because node counts and knowledge allocation differ. M/B0 is also not a pure single-factor causal effect of communication: it changes centralized/distributed reading and output organization simultaneously. B0 has no communication edges; edge metrics are NA.

### 3.2 M versus B1: terminal sets with and without communication

MuSiQue node M−B1 CSR is only −0.24 points, or −0.40 in the candidate-assisted view. Node averages alone could suggest similarity. Terminal M−B1 CSR, however, is −31.66 points, or −33.75 with candidate assistance. For 2Wiki terminal CSR, the corresponding differences are −42.08 and −50.00 points.

Thus **similar average node coverage does not imply similar terminal-set coverage**. B1's terminal contains three independent initial-read outputs; M's terminal contains only two final-communication outputs. The difference concerns information available within those terminal boundaries and cannot identify an edge that caused loss. Strict propagation-loss attribution would require an initial-union→terminal-union transition analysis aligned by run and truth claim. Existing reports did not estimate that joint transition.

### 3.3 M versus A1: separating semantic expression from source retention

A1 exists only for 2Wiki. Primary terminal HT M−A1 differences are −0.83 points for CSR, +48.54 for ESS and +51.04 for AA; candidate-assisted differences are 0, +47.50 and +50.00. A1 terminal ESS/AA estimates are zero while CSR remains approximately one half.

Process-level evidence has a consistent direction: node M−A1 ESS/AA primary differences are +6.97/+5.99 and candidate-assisted differences +9.94/+10.13. Applicable-edge exact source retention is 100% for M and approximately 0.99% for A1. A1's nonzero all-message-node source metrics include the initial-read layer and do not contradict zero terminal metrics.

One may state that source masking separates target expression from terminal citation verifiability. This matches A1's designed intervention and supports measurement validity and citation-dependence boundaries, but does not alone show that source-maintenance prompting improves reasoning. No equivalence test was conducted; small or zero CSR contrasts do not establish semantic equivalence between conditions.

### 3.4 M versus A2: no established stable instruction benefit

A2 exists only for 2Wiki. Primary terminal HT M−A2 CSR/ESS/AA differences are +2.43/+3.68/+2.43 points, with all between-question descriptive intervals crossing zero; candidate-assisted differences are 0/+1.25/0. Node primary differences have the opposite direction at −2.79/−1.34/−2.79, versus candidate-assisted 0/+0.75/+0.12. Applicable-edge retention is near 100% for both M and A2.

A supported description is that removing source-maintenance instructions did not produce a stable, large terminal difference in current estimates. Neither ineffective instructions nor a significantly better full protocol is established. Small contrasts reverse direction across primary node and terminal views; sparse auditing and version differences further discourage strong mechanistic conclusions.

## 4. Paired contrasts and uncertainty

All contrasts are M minus comparator, in percentage points. Primary and candidate-assisted sensitivity estimates are shown together; results are not selected by direction or interval.


| Dataset | Contrast | Metric | Node HT | Node difference-adjusted | Terminal HT | Terminal difference-adjusted |
| --- | --- | --- | --- | --- | --- | --- |
| 2wiki | M-B0 | CSR | -68.26 | -69.50 | -53.27 | -50.00 |
| 2wiki | M-B0 | ESS | -67.70 | -65.31 | -43.94 | -40.66 |
| 2wiki | M-B0 | AA | -68.26 | -69.50 | -53.27 | -50.00 |
| 2wiki | M-B1 | CSR | -11.20 | -3.67 | -42.08 | -50.00 |
| 2wiki | M-B1 | ESS | -11.48 | -3.33 | -36.46 | -44.38 |
| 2wiki | M-B1 | AA | -11.20 | -3.67 | -42.08 | -50.00 |
| 2wiki | M-A1 | CSR | -4.97 | 0.13 | -0.83 | 0.00 |
| 2wiki | M-A1 | ESS | 6.97 | 9.94 | 48.54 | 47.50 |
| 2wiki | M-A1 | AA | 5.99 | 10.13 | 51.04 | 50.00 |
| 2wiki | M-A2 | CSR | -2.79 | 0.00 | 2.43 | 0.00 |
| 2wiki | M-A2 | ESS | -1.34 | 0.75 | 3.68 | 1.25 |
| 2wiki | M-A2 | AA | -2.79 | 0.12 | 2.43 | 0.00 |
| musique | M-B0 | CSR | -76.73 | -61.42 | -37.26 | -33.12 |
| musique | M-B0 | ESS | -58.27 | -45.81 | -38.92 | -48.65 |
| musique | M-B0 | AA | -56.59 | -44.13 | -37.26 | -46.98 |
| musique | M-B1 | CSR | -0.24 | -0.40 | -31.66 | -33.75 |
| musique | M-B1 | ESS | -5.19 | -2.01 | -31.66 | -32.36 |
| musique | M-B1 | AA | -3.51 | -0.33 | -31.66 | -32.36 |

Primary terminal HT paired intervals follow. These are 95% between-question descriptive bootstrap intervals with fixed audit weights, not confidence intervals encompassing audit sampling, judgment error and question-sampling uncertainty together.


| Dataset | Contrast | CSR difference [interval] | ESS difference [interval] | AA difference [interval] |
| --- | --- | --- | --- | --- |
| 2wiki | M-B0 | -53.27 [-92.88, -13.76] | -43.94 [-82.15, -6.55] | -53.27 [-92.88, -13.76] |
| 2wiki | M-B1 | -42.08 [-89.24, 2.85] | -36.46 [-84.17, 8.13] | -42.08 [-89.24, 2.85] |
| 2wiki | M-A1 | -0.83 [-31.18, 29.52] | 48.54 [25.14, 74.93] | 51.04 [27.15, 77.29] |
| 2wiki | M-A2 | 2.43 [-30.07, 37.43] | 3.68 [-28.75, 38.89] | 2.43 [-30.07, 37.43] |
| musique | M-B0 | -37.26 [-96.93, 14.72] | -38.92 [-97.88, 13.02] | -37.26 [-96.93, 14.72] |
| musique | M-B1 | -31.66 [-87.47, 17.39] | -31.66 [-87.47, 17.39] | -31.66 [-87.47, 17.39] |

For example, MuSiQue M−B0 CSR has interval [−96.93,+14.72] and M−B1 [−87.47,+17.39]. Even when point estimates and the alternative view agree in direction, confirmatory significant-decrease wording is inappropriate. Some 2Wiki intervals exclude zero, but this does not change the exploratory scope or fixed-audit-weight interpretation.

## 5. Why high edge retention and lower terminal coverage are compatible

For 2Wiki M, claim retention and exact source retention are both 100% within applicable edge events, each with an HT applicable denominator of approximately 83.37 out of 400 total edge truth scopes. MuSiQue M has 95.90% and 86.61%, both with applicable denominators near 97.47 out of 244 total scopes. These rates ask how much is retained within the applicable-event set, not how many targets survive at the terminal.

Terminal CSR includes every target, including targets outside applicable edge events and targets not fully expressed in final outputs. High conditional edge retention therefore does not ensure high terminal coverage. The rates cannot be subtracted or multiplied to estimate end-to-end retention. Source-set retention relative to a parent node also need not equal terminal ESS relative to canonical sources.

A1 applicable-edge exact source retention is approximately 0.99% while claim retention is approximately 98.04%, supporting separate evaluation of source identity and semantic expression. MuSiQue M's 100% valid-substitution rate has only one applicable event and does not establish generally reliable substitution. B0/B1 have no communication edges and must be NA, not zero.

Existing edge M−A1/A2 paired tables use event frequencies over all edge scopes, not paired differences in applicable-denominator retention rates. The older node/edge report corrected 17 Qwen edges whose source-retention numerator extended outside its applicable domain. This numerator/denominator error is distinct from HT small-domain estimates above 100%.

## 6. What sample expansion represents

| Object | Exact portion | Remaining population and sample | Not reviewed itemwise |
| --- | --- | --- | --- |
| Node, full older-report scope | 769 | 6329 population, 633 sampled; 24 strata | 5696 |
| Edge, full older-report scope | 559 | 1885 population, 189 sampled; 8 strata | 1696 |
| Terminal, primary scope | 74 reused + 136 complete complex reviews = 210 | 1156 population, 120 sampled; 12 strata | 1036 |

The primary estimate is T̂=T_exact+Σ_h(N_h/n_h)Σ_{i∈s_h}y_i. Risk-directed human review enters the exact portion, without extrapolating its proportions. Sampled observations already represent the remaining population and must not be added again after expansion.

For terminal exact canonical source-set retention, exact counts are 66+52=118; the simple-population estimate is 755.5625; the total is 873.5625, or 63.95% of 1366. The unsampled 1036-item portion contributes an estimated 676.5625. Fractions are weighted counts, not fractional human decisions.

The candidate-assisted difference estimate is T̂_diff=T_exact+Σ_remaining p_i+Σ_sample w_i(y_i−p_i). It corrects the complete candidate distribution using sampled discrepancies, without assigning labels to unreviewed items. Complex union cases have no complete older candidate set, so all union-candidate sensitivity views share the 210 exact outcomes as their anchor. Node difference sensitivity was added after initial results; most edge proxies were reconstructed after review, so their correction is not independent prospective validation.

Node sample agreement across seven primary fields is 627/633=99.05% (weighted 99.04%); terminal agreement across nine fields is 111/120=92.50% (weighted 92.59%). Their populations, fields and tasks differ: one cannot directly test how much worse union is or transfer high node agreement to union. The nine terminal discrepancies mainly concern source fields plus one newly aligned alias, showing that presence agreement does not imply reliable citation judgments.

## 7. Estimates above 100%: retain, explain and limit their use

**Principle.** True proportions lie in [0,1], but unconstrained HT estimates have no such guarantee. Weights arise from broader audit strata. Records sampled in a question/small domain may overrepresent that domain; dividing the expanded numerator by the actual domain denominator can exceed one.

For example, a domain has four scopes and happens to contribute one sampled positive with an expansion weight of ten. Its HT total contribution is ten, which divided by four yields 250%. There are not ten actual positive cases; this is a high-variance domain estimate. Positive sampling probabilities and design-unbiasedness under the relevant random-sampling working assumption do not force every realized estimate into natural bounds.

Question-macro averaging also gives different coefficients to questions with different truth counts. Correct overall weight totals do not guarantee in-range condition macros. Difference correction is similarly unbounded: a high candidate baseline plus expanded positive sample residuals can exceed 100% or yield estimated AA>CSR.

| Observed example | Estimate | Explanation |
| --- | --- | --- |
| Node MuSiQue B0, HT CSR | 108.42% | Small-domain weighted variation |
| Terminal 2Wiki B0, HT CSR | 104.32% | Question-macro HT small-domain variation |
| Terminal MuSiQue B0, difference-adjusted ESS/AA | 107.17% | Weighted candidate residuals are also unbounded |

For the paper:

1. Call these weighted estimates or estimated contributions, not observed accuracy; retain original table values.
2. Present HT, candidate-assisted and candidate sensitivity views with actual denominators, sample sizes, intervals and out-of-range explanations; do not select favorable directions after observing results.
3. Do not clip 104.32% to 100%. Clipping changes the estimator, introduces bias and hides instability. Any bounded/calibrated alternative requires explicit methods and assumptions as a separately versioned sensitivity analysis.
4. Avoid out-of-range small-domain values as precise abstract performance figures. The text can describe directions and instability, with full numbers in tables/supplements.
5. If precise bounded condition rates are later required, increase audit coverage in those domains or prespecify calibration/model-based estimation in a new analysis version. The current results do not justify inventing narrower intervals.

**Intervals have boundaries too.** Node/edge intervals fix audit weights and resample questions only; terminal outputs additionally provide finite-population audit-design standard errors. The first describes between-question variation and the second audit-sampling variation within the fixed panel. They are not endpoints of the same confidence interval and cannot simply be added. Neither covers unknown systematic annotation bias. Zero sampled residuals or a one-question stratum may give zero-width intervals; these do not establish perfect reliability, no error or equivalence.

## 8. Supported and unsupported manuscript conclusions

| Conclusion | Support | Recommended wording |
| --- | --- | --- |
| Three observational levels are not interchangeable | Supported | Node coverage, applicable-edge retention and terminal-set coverage describe different objects and should be measured together |
| Semantic expression and source verifiability can separate | Supported, most directly by A1 | Under source masking, some claims remain expressed while terminal canonical-source and support estimates are zero |
| M outperforms B0/B1 at the terminal | Unsupported | M terminal point estimates are lower in this frozen panel, with consistent direction across primary/assisted views |
| Communication universally causes information loss | Universal causal claim unsupported | This protocol and terminal boundary show descriptive evidence of lower coverage |
| Source-maintenance instructions stably improve performance | Insufficient evidence | M−A2 differences are small and unstable; no strong conclusion |
| High edge retention guarantees system completeness | Unsupported | High retention applies only to the relevant event set |
| Valid substitution always damages sources | Unsupported | Separate identity changes from sufficient support; adding valid sources can also make ESS zero |
| Candidates directly replace all human review | Unsupported | They can be auxiliary variables and sensitivity baselines; unreviewed items remain candidates |
| Cross-model/topology generalization is established | Unsupported | This integrated primary comparison is restricted to DeepSeek 1.0.4 chain |

## 9. Draft Results text

We compared centralized reading, independent reading, communication and two source-protocol ablations in the frozen DeepSeek 1.0.4 panel. The primary comparison contains 60 questions, two repetitions per condition and 520 runs. Message nodes, dependency edges and terminal sets provide separate measurement views; condition results average repetitions within question before equal-question aggregation. Since human review does not cover every record, population metrics combine exact evidence with stratified audit-sample expansion and candidate-assisted difference estimates.

Terminal complete-expression point estimates for M are lower than B0 and B1 in both datasets. The 2Wiki HT paired differences are −53.27 and −42.08 percentage points; MuSiQue differences are −37.26 and −31.66. Candidate-assisted views retain the same directions. Direct expansion is unstable in some question domains and several between-question descriptive intervals cross zero, so these are descriptive differences under the frozen protocol, not confirmatory or universal causal conclusions.

The 2Wiki source-masking condition A1 has zero estimated terminal canonical-source exact retention and sufficient current support, while complete expression remains around one half. Differences between M and A2, which removes source-maintenance instructions, are smaller and show no stable large changes across observational levels and estimators. High retention within applicable edge events can coexist with lower terminal coverage, reinforcing that edge-event retention and terminal availability of all targets are distinct metrics.

## 10. Draft Discussion text

The central implication is to distinguish claim content, source identity and sufficient current support, as well as node, edge and terminal-set observational levels. With independent reading, knowledge can be distributed across nodes, yielding low average node coverage but high terminal-set coverage. Conversely, when terminal observation is restricted to final communication outputs, high applicable-edge retention does not guarantee availability of every target. Multi-agent communication should therefore not be evaluated solely through average node quality or conditional edge-retention rates.

The results also show why citation judgments need separate auditing. Simple union proxies agreed with sampled semantic-completeness judgments, yet paragraph citations were sometimes misclassified as missing sources and alias expressions/additional sources were incompletely aligned. Audit expansion can also exceed natural proportion bounds in sparse domains. Current evidence is thus better suited to a measurement framework and conditional description than precise performance rankings. Scope is constrained by the fixed model version, single-round chain, limited questions, two repetitions and nonblind review. Event-level mechanism attribution and cross-model generalization require additional analysis.

## 11. Manuscript implementation and traceability

A recommended Results order is scope/audit → terminal primary comparisons → node/edge process evidence → estimator sensitivity. Discussion should develop differences across levels, separation of semantics from sources and estimator boundaries. Retain terminal condition contrasts and intervals in the main tables, with full node/edge tables and four estimation views in supplementary material.

This integrated report requires no new adjudication. A stronger claim that a specific edge caused a particular terminal loss, or an exact transition decomposition across the three levels, would require run-aligned analysis and harmonized adjudication versions; existing aggregate tables do not already prove those claims. Older statements about three repetitions, confirmatory p-values/Holm, the full M3 panel and incomplete terminal analysis must be revised to match actual data and the latest reports.

This report does not rewrite the manuscript or older node/edge results. Extracted numbers are in `integrated_condition_comparisons.csv`; input hashes are in `manifest.json`. The three reports share questions, candidates and some human evidence and are not three independent validations.
