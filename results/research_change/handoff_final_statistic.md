> Historical full-snapshot documentation. Some referenced inputs/outputs are now held in the separate editorial store after the rights review. This report does not establish public availability of those records.

# Handoff after final statistics: manuscript preparation

English companion. Updated 2026-10-15 (Asia/Shanghai), for a new session without conversational context.

**Node, edge, terminal-union statistics, and the integrated report are complete; all raised human-adjudication items are closed. The next step is manuscript preparation, not resampling, re-adjudication, or new experiments.** This supersedes the next-step status in handoff_before_final_statistic.md; older handoffs remain historical audit provenance.

## 1. Study purpose

The study asks how semantic expression, source identity, and evidential support of target claims survive multi-agent communication, and why node, dependency-edge, and terminal-set views require separate evaluation. It is an exploratory reduced semantic substudy over a frozen panel, not the full M3 confirmatory experiment.

The original working root is `source_archive/agent_experiment_platform/research_change`. Below, `S` means `final_statistics_stage_20261012`. The original paper-design/old-draft entry is `source_archive/manuscript/original_paper_work_plan.md`. It was read but not overwritten in this handoff. Historical plans cannot override actual execution; specifically revise claims of three repetitions, confirmatory p-values/Holm, the complete M3 panel, or unfinished terminal analysis.

M is the full communication protocol; B0 is centralized reading; B1 is independent reading without communication; A1 masks source identities; A2 removes source-maintenance instructions. Main scope: DeepSeek 1.0.4, three-agent single-round chain, original_protocol. No repair or matched supplemental-contract observations exist, so their effects were not measured.

## 2. Read first

1. `S/integrated_paper_results_20261015/INTEGRATED_PAPER_RESULTS_REPORT.md`: primary writing entry, with condition comparisons, inference boundaries, sampling/out-of-range explanations, and Chinese Results/Discussion drafts.
2. `S/terminal_union_statistics_20261015/TERMINAL_UNION_STATISTICS_REPORT.md`, `SUPPLEMENTARY_TABLES.md`, and `ANALYSIS_SPEC.md`: final terminal statistics/methods.
3. `S/paper_node_edge_statistics_20261013/NODE_EDGE_PAPER_STATISTICS_REPORT.md`, `ANALYSIS_SPEC.md`, and `ANALYSIS_AMENDMENT.md`: process statistics and later sensitivity-version notes.
4. The paper work plan above, to identify useful structure and outdated definitions.
5. For evidence tracing, `RULES_FROZEN.md`, `ANALYSIS_AND_QUALITY_PLAN.md`, `frozen_v1/manifest.json`, and original `src/agent_lab/m2_contracts.py`.

Do not treat pending-review statements in `S/REPORT.md`, old handoffs, or initial audit packages as current status. Final reports and `S/terminal_union_primary_20261013/FINALIZATION_STATUS_20261015.json` govern completion.

## 3. Completed work and authoritative files

### 3.1 Node and edge

- The full older-report panel contains 60 questions, 680 observations, 7,098 node scopes, and 2,444 edge scopes, including older M and Qwen chain/star descriptive references outside the main scope.
- Node: 769 originally exact human-reviewed records plus 633 sampled from the remaining 6,329 across 24 strata. The 5,696 unsampled records have no individual human-final identity.
- Edge: 559 originally exact human-reviewed records plus 189 sampled from the remaining 1,885 across eight strata. The 1,696 unsampled records have no individual human-final identity.
- Condition tables, question-paired differences, between-question bootstrap intervals, and candidate sensitivity are in `S/paper_node_edge_statistics_20261013/`; primary base tables are `condition_and_stratum_tables.csv` and `paired_condition_differences.csv`. See verification.json and manifest.json for checks/hashes.
- Earlier itemwise evidence: `final_node_audit_20261011/node_judgments_adjudicated_final.jsonl`, `final_edge_audit_20261012/`, `S/remaining_node_sample_20261013/human_review_form_633.json`, and `S/final_sample_edge_audit_20261013/edge_judgments_adjudicated_sample_189.jsonl`.
- The final distribution of the original 769 nodes is 269 decided, 490 semantic_negative, and 10 missing. The earlier 270/489/10 is obsolete. Review of edge item 181 changed a formal node judgment; earlier copies must not overwrite it.

### 3.2 Terminal union

Completed primary scope: DeepSeek 1.0.4; 40 2Wiki questions with M/B0/B1/A1/A2 twice each, and 20 MuSiQue questions with M/B0/B1 twice each. Totals: 520 observations and 1,366 terminal truth scopes; corresponding main-scope node/edge counts are 4,898/1,444.

Terminal sets follow the frozen protocol, not concatenation of all historical messages. B1 uses three independent initial-read outputs; M uses two outputs from the final communication layer; B0 uses the centralized output. Each target counts once per observation in the union. Offline union auditing made no new model calls and does not establish every hop union.

Audit composition: 74 reused earlier adjudications + 136 exhaustively reviewed complex items + 120 stratified samples from 1,156 simple items. The exact component is 210; 330 items have review/reuse evidence; the 1,036 unsampled simple items remain unknown.

Authoritative author-review package: `S/terminal_union_primary_20261013/`:

- human_review_form.json: all 136+120=256 items complete; 145 adjudicate and 111 accept_proposal.
- human_review_reason.md: detailed reasons/field adjudications; table rationales are abbreviated.
- FINALIZATION_STATUS_20261015.json: pending_rows=0 and all author decisions complete.
- union_reuse_author_corrections_20261015.json: four explicitly authorized union-reuse corrections.
- The six-item pending list and summaries under completion_20261015 are historical snapshots, not grounds for repeat adjudication.

Preserve the final decision chain: TU-0310 accepts its own candidate and disregards the mistakenly pasted TU-0258 conclusion. The other five of the earlier six pending items follow the author's “1085–1307” instruction: adjudicate, fully_supported, unchanged, exact_set_survived=true. This does **not** mean bulk-changing every consecutive ID from 1085 through 1307.

The author additionally authorized corrections only to TU-1165, TU-1182, TU-1224, and TU-1296 union reuse: identifiable, fully_supported, unchanged, exact_set_survived=true, while retaining prior semantic alignment and old node files. Canonical paragraph references were actually present; the old records had incorrectly marked source loss.

Statistical delivery at `S/terminal_union_statistics_20261015/`:

- terminal_analysis_ledger.jsonl: 1,366 analysis records; judgment remains empty for 1,036 unaudited records, not automatically final.
- human_terminal_judgments_256.jsonl: M2 judgments for this analysis; retain original record identity, without converting them to production-final because author review is complete.
- condition_question_macro.csv and paired_condition_differences.csv: primary paper comparisons.
- observed_and_expanded_counts.csv and estimates_and_audit_uncertainty.csv: directly observed/expanded counts and audit-sampling uncertainty.
- sampling_allocation.csv, simple_proxy_agreement.csv, simple_proxy_disagreements.json, unreviewed_worst_case_bounds.csv: sampling and sensitivity.
- verification.json passed; manifest.json records input/output hashes.

### 3.3 Integrated paper results

`S/integrated_paper_results_20261015/` is complete: an 11-section integrated report with reusable prose; integrated_condition_comparisons.csv with 72 node/terminal, HT/difference-assisted, CSR/ESS/AA contrasts and intervals plus source files; manifest.json with 12 checked input hashes and output hashes; and build_integrated_report.py for rebuilding the report.

## 4. Conclusions now supported

CSR is full equivalent expression. ESS additionally requires exact equality of runtime and canonical source sets. AA requires full equivalence and sufficient current evidential support. VSSR is valid substitution. AA is not final-answer accuracy. Node/terminal metrics use their respective complete truth-scope denominators; each edge metric has its own applicable denominator.

Primary terminal HT question-macro paired differences, percentage points, all M−control:

| Dataset | Control | CSR | ESS | AA |
| --- | --- | ---: | ---: | ---: |
| 2Wiki | B0 | -53.27 | -43.94 | -53.27 |
| 2Wiki | B1 | -42.08 | -36.46 | -42.08 |
| 2Wiki | A1 | -0.83 | +48.54 | +51.04 |
| 2Wiki | A2 | +2.43 | +3.68 | +2.43 |
| MuSiQue | B0 | -37.26 | -38.92 | -37.26 |
| MuSiQue | B1 | -31.66 | -31.66 | -31.66 |

Recommended narrative: a **measurement and audit study separating semantics, provenance, and support across nodes, edges, and terminal sets**, not a claim that the full communication protocol significantly improves performance.

- M terminal-coverage point estimates are below B0/B1, with the same direction in candidate-assisted views, but several between-question intervals cross zero. Avoid universal causal or confirmatory-significance claims. M–B0 also changes centralized/distributed reading; M–B1 has different terminal output boundaries.
- A1 terminal CSR is about 51.88%, with ESS/AA zero: expression can persist while source verifiability disappears. This matches the intervention design and does not establish improved reasoning from source prompts.
- M–A2 differences are small and unstable. Neither “maintenance instructions are ineffective” nor “full M is significantly superior” is supported. Small differences/cross-zero intervals do not establish equivalence.
- High conditional edge retention does not guarantee high terminal coverage. 2Wiki M applicable-edge retention can be 100%, but the applicable denominator is about 83.37 of 400 scopes. Do not multiply/subtract cross-level ratios to estimate propagation loss.
- Node averaging and union coverage differ: M/A1/A2 have five nodes, B1 three, and B0 one, with different knowledge allocation. MuSiQue node M−B1 CSR is about -0.24 versus -31.66 terminal; do not selectively tell only one story.
- Existing summaries do not align initial union→terminal union transitions for the same run and target. They cannot attribute a quantity of loss to a particular edge.

## 5. Audit expansion, candidate availability, and values above 100%

The primary estimate is exact counts plus each stratum's `(N_h/n_h) * sample positives`. Risk-targeted review is exact, not a positive rate to extrapolate. The sample is included in the expanded population and must not be added twice.

Weighted terminal totals over all scopes: CSR 1027/1366=75.18%; ESS 873.5625/1366=63.95%; VSSR 53.4375/1366=3.91%; AA 927/1366=67.86%. These pool conditions at scope level, not one condition's question-macro rate. Fractions denote estimated counts, not fractional human adjudications.

Simple terminal proxies agree on all nine fields for 111/120=92.50%, weighted about 92.59%. CSR/presence agree in that sample; differences mainly concern provenance and one alias. Nodes agree on seven fields for 627/633=99.05%, weighted about 99.04%. Objects/fields differ, so these are not directly comparable accuracies and node agreement cannot be transferred to union.

Only three sampled edges had genuinely pre-existing candidates, agreeing 3/3; the other 186 had post-review reconstructed proxies and cannot validate prospective candidates. A high proportion of structurally easy items also inflates agreement.

Unconstrained HT expands small-domain numerators with coarse-stratum weights and divides by true domain counts; it may exceed 100%. A domain with four actual items, one sampled positive, and weight ten yields 10/4=250%, not ten actually correct items. Question-macro aggregation does not remove this behavior. Actual examples: node MuSiQue B0 CSR 108.42%; terminal 2Wiki B0 CSR 104.32%. Candidate-assisted difference estimators are also unbounded: terminal MuSiQue B0 ESS/AA can reach 107.17%, with even estimated AA>CSR.

Never silently clip to 100%, change denominators, or choose a prettier estimator. Preserve values labeled weighted estimates, show HT and candidate-assisted sensitivity, and explain small-domain instability. A calibrated/bounded alternative would require a new analysis version and explicit assumptions, not replacement of frozen results. Unaudited records never receive individual human conclusions.

Between-question bootstrapping fixes audit weights and preserves within-question condition/repetition pairing. Terminal analysis additionally reports audit-design standard errors. They characterize different uncertainty and cannot simply be added or claimed to combine all error. Zero residuals, constant samples, or single-question strata can produce zero-width intervals without proving zero error. No confirmatory p-values/Holm or equivalence tests were completed; do not invent them.

## 6. Pitfalls to avoid

1. Do not reopen completed human review: 256 items and four reuse corrections are accepted, pending=0. Raise a new issue only with specific new evidence conflicts and identify that evidence.
2. Do not mix scopes: 680/7098/2444 is the older mixed panel; 520/4898/1444/1366 is the DeepSeek main scope. Older overall node CSR 32.91% cannot be subtracted from terminal 75.18% as an improvement.
3. Distinguish questions, runs, scopes, occurrences, and dependencies. Questions are independent units; two repetitions are not two independent questions and thousands of scopes are not independent binomial trials.
4. Preserve version differences: latest union corrections did not rewrite nodes/edges. B0 node and terminal describe the same output; estimate differences reflect sampling, estimators, and judgment versions, not propagation. Three views are not three independent replications.
5. Do not code edge NA as failure/zero. B0/B1 lack communication edges; other edges have applicability conditions. Repairing 17 Qwen exact-source numerators outside the applicable set corrected counting, unlike legitimate HT overshoot.
6. Do not replace source judgment with string appearance. Resolve paragraph references against canonical mapping; check aliases, references shared by claims, and additional valid sources. Source existence, exact canonical equality, support sufficiency, and factual truth are distinct.
7. Noncanonical sources are not automatically wrong. Valid alternatives can fully support a claim with ESS zero; a source marker alone does not establish support.
8. Preserve M2 cross-field constraints. Handle source/support applicability under the contract for nonequivalence; when equivalent and locatable, check source sets, exact_set_survived, and source_change_status. Normalize JSON booleans and M2 true/false strings before comparisons. Statistical materialization is not production-contract import.
9. Do not fabricate final/blind-review identity. Candidates, author forms, analysis materializations, and production-final records differ. Do not bulk-modify origin/is_final for consistency; report actual author–Codex collaboration truthfully.
10. Do not conceal revisions with template reasons. Fields were once changed while rationale still said “retain candidate,” and TU-0310 once received another item's pasted conclusion. Resolve detailed reasons by item_id and retain revision lineage.
11. Do not rerun one-off field-completion scripts over author decisions. Old finalize/completion scripts are historical change records, not daily refresh tools. Read their purpose first and prefer read-only checks.
12. Do not change analysis to obtain preferred conclusions: no resampling, significance-based question selection, silent boundary changes, or sensitivity-as-independent-confirmation claims. New methods retain old versions and document changes/impacts.

## 7. Recommended next steps for a new writing session

1. Read section 2 inputs and establish actual scope, conditions, units, review identities, primary estimators, and interval boundaries.
2. Correct historical design/execution mismatches and settle the paper narrative and Results structure.
3. Recommended Results order: scope/audit → terminal primary comparisons → node/edge process supplementation → sampling/estimator sensitivity. Discussion explains view differences, semantics/provenance separation, and limitations.
4. Prioritize terminal condition differences and descriptive intervals in the main text. Put full node/edge results, four estimator views, sampling allocation, audit lineage, and overshoot explanations in supplements. Read machine base tables directly, without hand-entered recalculation, clipping, or selective rows.
5. Check abstract, methods, results, captions, and supplements for consistent sample sizes/definitions. Complete literature and submission work as needed; finished statistics do not imply a completed manuscript or verified bibliography.

No new adjudications are needed for writing. Mechanistic propagation attribution would require within-run alignment and harmonized versions first. Precisely bounded condition rates need additional coverage/estimator design; neither may be described as already completed.

## 8. Rebuilding and operational notes

Read local README, ANALYSIS_SPEC, manifest, and verification files first. Historical terminal rebuild order: build_terminal_statistics.py → build_report.py → verify_terminal_statistics.py using project `.venv\Scripts\python.exe`. The original machine had NumPy 1.26.4 in system Python but an older Pydantic; the project virtual environment supplied required Pydantic. Scripts handled NumPy-path precedence, so interpreter replacement could break contracts. Integrated-report generation uses only the standard library. These are historical environment notes; consult repository portability guidance before rebuilding copied scripts.

After regenerating files, recheck and update output hashes; an old passing verification does not verify changed inputs. Integrated delivery checked 12 source hashes, output hashes, and 72 comparison rows.

**This handoff requests no statistical rerun. Read final results and paper design, then write/revise the manuscript.**
