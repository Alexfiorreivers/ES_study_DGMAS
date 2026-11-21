> Historical full-snapshot documentation. Some referenced inputs/outputs are now held in the separate editorial store after the rights review. This report does not establish public availability of those records.

# Exploratory semantic substudy: analysis and quality gates

English companion. **Historical status in the source:** design and evidence had been frozen, but no GPT semantic judgments, human adjudications, or semantic results had yet been generated. Numbers at that stage were sample/workload/structure counts, not model-quality metrics. **Current-status clarification:** these statements document the original plan; subsequent completed node/edge/terminal results and the 2026-10-15 finalization records take precedence. Do not reopen completed work.

## Research objects and reportable scope

Fix 60 questions: 10 in each of four 2Wiki graph types; MuSiQue's six (question_stratum, hop_count) strata are 2hop/2:6, 3hop/2:4, 3hop/3:3, 4hop/2:1, 4hop/3:4, and 4hop/4:2. Selection uses frozen-seed question-ID hashing within strata and takes the first N, without outcome-based selection. DeepSeek retains completed r1+r2. Qwen3 retains existing remote observations for the same 40 2Wiki questions without reruns or condition changes. Original and repair are distinct observation versions that never overwrite one another, but **all 680 selected observations are original_protocol; none is repair**, so this substudy cannot estimate repair comparisons. Matched supplemental-contract observations number zero.

The panel contains 680 main observations, 1,520 same-question/same-text groups across all nodes, 8,676 claim occurrences, 7,098 mechanical node truth-claim scopes, 960 dependency edges, and 2,444 edge truth-claim scopes. The 1,520 groups provide node coverage for later edges; 1,398 are terminal. The earlier “about 1,389” was an estimate, not the frozen size. Incomplete exhaustive human blind checking of the original 50-group pilot is not evidence of this panel's accuracy.

Describe the paper as an exploratory, prospectively fixed reduced substudy. Separate full-population engineering completion from this semantic substudy. Inference concerns these 60 selected questions and corresponding completed observations, not confirmatory generalization to all 2Wiki/MuSiQue/M3 or provider populations. Explicitly identify unmeasured cells, indeterminate scopes, B0/B1's lack of edges, and unconstructed union scopes; none is zero or a negative case by default.

## Order of result generation

1. Three independent persistent sessions complete their mutually exclusive node batches. Finish group alignment, every occurrence's source/support/truth judgments, and within-batch scope integration together, then validate before reporting. Each session delivers candidates, unresolved cases, and batch reports.
2. Consolidate node results: verify current candidates for every selected mechanical scope, empty-node lineage, unresolved reasons, M2 schema, nonoverlap across sessions, and completion of every question. Missingness/ambiguity stays missingness/ambiguity, not automatic counterexamples. Construct union scopes separately or exclude their metrics.
3. Only after all node sessions finish, process edges jointly using selected node candidates. First validate E0/E1 mechanically and against endpoints per truth claim; then review E2 by dependency. Structural classes determine priority, not semantic conclusions. All candidates retain is_final=false.
4. After independent blind samples and high-risk reviews, create a separate adjudication layer and quality report. If Potato is unavailable, use local forms with the same fields; this does not justify skipping blind samples or promoting GPT candidates to human final.
5. Compute exploratory semantic results only after denominator inventories, deduplication, and quality gates. If candidate-only results are shown, label them “GPT/mechanical candidate sensitivity analysis,” not “final human-review results.”

## Prospectively fixed quality-audit framework

Before viewing panel GPT outputs, freeze question-level `blind_audit_questions.json` using an independent seed: one question per 2Wiki graph type (four total), and one each from MuSiQue's 2hop and 4hop question strata, totaling six questions and 151 groups. Within strata, rank `sha256("exploratory-blind-20261006-v1" + separator + question_id)` and take the minimum. The file contains IDs, strata, and workload only, not labels. Changes require a version/reason before candidate exposure.

Blind-check group alignment, every citation, and node scopes for those questions; check edges in questions with edges stratified by E0/E1/E2. Additionally perform exhaustive or targeted review for high-risk E2, contextual conflicts within groups, source substitutions, and M2 abstentions. Reviewers should view original evidence before GPT labels where possible, recording disagreements, adjudications, and time. Six questions can detect workflow defects but **cannot establish a low error rate**. If disagreements cluster or are excessive, suspend bulk adoption, amend rules, and review affected candidates. Without a predefined verifiable error threshold, a post hoc “passed” blind sample cannot confer final status on all candidates.

## Statistical definitions, executed only after results are complete

- Specify dataset, model, condition, topology, observation_version, r1/r2, applicable scope, and judgment status for every metric. Footnote original/repair treatment. Engineering completion uses its original denominator; semantic rates use predefined applicable-observation denominators and report indeterminate counts/rates. Preserve counts of questions, observations, node scopes, and edge scopes instead of reporting only claims.
- Average DeepSeek r1/r2 within identical question×condition cells before question-paired differences. Replicates and multiple claims are not independent questions. Show four 2Wiki and six MuSiQue strata first. Any overall estimate must state equal-stratum, sample-proportion, or original-design weighting; do not select favorable weights after seeing outcomes.
- If intervals are computed, resample questions stratified by dataset/stratum and preserve all within-question condition/replicate pairing. Question-bootstrap 95% descriptive intervals and raw question means may be reported. With 60 questions and one MuSiQue stratum containing only one question, stratified intervals can be unstable; label this. Do not apply independent-binomial standard errors to 7,098 node or 2,444 edge scopes. Confirmatory p-values, significance claims, and full-M3 generalization are outside this plan.
- Qwen3 provides descriptive references only for prespecified conditions on the same 2Wiki questions. Provider/protocol/run conditions may confound comparisons; differences are not direct causal model effects.
- Report the human-adjudication primary view if coverage suffices, candidate-only sensitivity, simple all-positive/all-negative bounds for unresolved cases, and sensitivity stratified by original/repair where available. Missingness must not implicitly remove denominators. The selected panel has no repair observations, as specified above.

## Conditions insufficient for primary paper results

With only mechanical/GPT candidates and no independent blind review/adjudication, uncovered node endpoints, mixed union scopes, or missing/duplicate/hash-drifted batches, report exploratory workflow feasibility/coverage/pending workload only, not final semantic effects. If human work cannot meet quality gates, transparently state that semantic evaluation is unfinished rather than shrinking denominators until a publishable result appears.
