> Historical full-snapshot documentation. Some referenced inputs/outputs are now held in the separate editorial store after the rights review. This report does not establish public availability of those records.

# Exploratory semantic substudy: frozen processing rules

English companion. Version `exploratory-semantic-panel-1.0.0`. These rules apply only to the reduced panel identified by `frozen_v1/manifest.json`; they do not modify the full original M3 study, original runs, truth data, mechanical artifacts, or the 50-group pilot. Rule changes require a new version and an affected-scope record; do not combine incompatible versions of candidates.

**Historical-status note:** this is the original processing protocol, not a request to repeat completed review. Node, edge, and terminal-union statistics and all raised adjudications were completed by 2026-10-15. The latest finalization status and final handoff govern current work.

## 0. At every start, resumption, or context compaction

Read this entire file, `ANALYSIS_AND_QUALITY_PLAN.md`, the assigned `frozen_v1/sessions/session_XX.json`, current `frozen_v1/batches/sXX_bYY.json`, `frozen_v1/manifest.json`, and the `NodeJudgment`/`EdgeJudgment` fields and validators in the original project's `src/agent_lab/m2_contracts.py`. Check input SHA values and completed-batch output indexes/progress. Do not continue review from conversational memory. Stop the batch and report conflicting hashes, rule versions, schemas, identities, or existing outputs.

## 1. Sample and identity

- The primary reduced selection comprises 40 2Wiki questions (10 per graph type) and 20 MuSiQue questions (fixed hop×difficulty quotas in the manifest). DeepSeek uses r1+r2 only; Qwen3 uses existing remote observations for the same selected 40 2Wiki questions without reruns. There are 60 distinct questions and 680 main observations. Repair retains its own observation_version and must not overwrite/merge with original, but **every selected observation here is original; there are no repair observations**. There are zero matched supplemental-contract observations; absence is not failure.
- The fixed seed/quota selection defines a replayable, prospectively fixed **exploratory reduced sample**. It is not claimed to randomly represent full M3 and does not update existing full-study formal results. Questions are independent statistical clusters; groups, claims, occurrences, and edges are not independent questions.
- A group key is `dataset_sha256 + question_id + exactly identical runtime claim text`. The 1,520 groups cover all message nodes, with 1,398 terminal groups. Do not substitute terminal groups for complete node coverage when inferring edge endpoints. Identical text permits reuse of semantic-alignment candidates only, not occurrence-specific source, support, content-truth, or qualification judgments.
- `truth_view` is frozen truth; runtime claims, source_refs, dependencies, and mechanical scopes are observations. Resolvable locators establish mechanical facts, not valid sources, sufficient support, or factual truth. Pilot GPT/preliminary human labels are regression references only, not bulk labels for formal observations. A pilot-completed group is not complete in this panel until inputs, rules, and occurrences have been checked.

## 2. Complete a batch in one pass

Do not align the first 50 groups and then perform source review in a second pass. `session_XX.json` is the exclusive session boundary; `sXX_bYY.json` is the atomic batch boundary. The three sessions do not write one another's outputs. Each batch contains complete questions, targeting at most 50 groups. If one question exceeds 50 groups, give that question its own larger batch; never split it to meet the target. Groupwise checkpoints are allowed, but report a batch complete and start the next only after every group and occurrence is completed and validated. Do not split all-group alignment and all-occurrence review into separate stages.

For each group:

1. Read `groups/<group_id>.json`, question, all truth claims, reasoning graph, and relevant context. Propose alignment of the text to each truth claim, permitting partial, uninterpretable, many-to-many, or abstention outcomes. Identical strings or fuzzy-score thresholds do not establish equivalence. If pronouns/context change meaning within the group, flag the conflict and disable groupwise filling.
2. In the same processing pass, inspect every occurrence's node, runtime_claim, source_evidence, and mechanical scope. Independently record qualifications, source markers, locatable sources, exact canonical-source-set equality, source validity, support level, and content truth. Do not copy the preceding occurrence's support conclusion.
3. Write candidates and evidence sidecars and check that no occurrence ID is omitted. Group outputs have origin=automatic_candidate and is_final=false. If a complete M2 NodeJudgment cannot yet be formed, explicitly mark incomplete_candidate/pending rather than filling defaults with negative values. Use needs_review and legal reason codes only for genuine M2-permitted ambiguity. Determinable absence, wrong references, and contradictions may receive negative candidates.
4. After all groups in the batch, integrate group candidates and `selected_empty_node_candidates.jsonl.gz` at observation/run/node/truth-claim scope. Empty-node candidates remain non-final. For a truth claim missing at a nonempty node, judge alignment across **all runtime claims in that node**, not absence of a match in one group. Allow no more than one current candidate per scope; validate NodeJudgment fields and abstention reasons. At batch end, inventory complete-question node scopes and retain unresolved queues rather than portraying them as adjudicated.

Suggested completed-batch outputs under `reviews/session_XX/batch_YY/`: `group_candidates.jsonl`, `occurrence_candidates.jsonl`, `node_candidates.jsonl` where M2-complete, `unresolved.jsonl`, and `batch_report.json` containing input/rule/model/output hashes, counts, elapsed time, cost, and unresolved reasons. This was a future work-output location; the frozen package prefilled no judgments. Interrupted work may save checkpoint.json, but incomplete batches must not be reported as complete.

## 3. Process edges jointly only after all nodes

Start unified mechanical/GPT/review edge processing only after all three sessions finish their node batches, coverage/unresolved categories for 7,098 selected mechanical node scopes are summarized, cross-session candidates are deduplicated, and M2 validation passes. Do not infer edge events from partial session results. `edge_inventory.jsonl.gz` is structural inventory, not semantic edge judgments.

Review by `observation_key + dependency_id + truth_claim_id`:

- E0, both endpoints empty: not_applicable candidate for each truth claim.
- E1, unchanged structure: still inspect corresponding parent/child node alignment. Unique equivalence at both endpoints may support retention/exact-source-set/relative-support-maintenance candidates; absence at both is not_applicable. Partial, conflicting, or missing node judgments remain queued. Relative maintenance does not establish truth or sufficient evidence.
- E2, other structures: package by dependency, but supply separate events/evidence per truth claim. Never copy one dependency label across all truth claims. Use M2 enumerations; claim_retained_equivalent is not a valid source_events value.

GPT edge results remain automatic_candidate, is_final=false. Independently review all uncertain cases and frozen-plan blind samples. Preserve original candidates and audit lineage when human adjudications are added, rather than overwriting. An equivalent local form may replace an undeployed Potato interface. Changing is_final alone never creates a human adjudication.

## 4. Quality, statistics, and stopping conditions

Record missingness, abstention, human blind-check disagreement, and question-clustered uncertainty. The 35 minutes for the original 50-group pilot estimates workload, not accuracy. Without sufficient independent auditing, GPT candidates appear only in clearly labeled candidate/sensitivity results, not a “human-final semantic truth” table. Separate engineering-completion denominators from semantic-quality denominators. B0/B1 absence of edges is not edge=0. requires_explicit_hop_union requires a separately constructed union scope; message-node candidates are not union judgments.

Pause a batch and report specific blockers for missing input, evidence conflict, M2 validation failure, duplicate current scope, cross-batch/session identity overlap, hash drift, or inability to finish the batch. Do not silently fill values, skip records, or reduce denominators.
