> Historical full-snapshot documentation. Some referenced inputs/outputs are now held in the separate editorial store after the rights review. This report does not establish public availability of those records.

# Why terminal union is needed in the existing paper design

English companion to the historical design assessment. **Status note:** its statements that union adjudication is still needed describe the 2026-10-13 node/edge stage. Terminal-union review and statistics were completed on 2026-10-15. Follow the latest finalization status and final handoff; do not reopen completed review.

Based on sections 6, 8, 9.1, 10, and 11 of the paper work plan, frozen substudy rules, and M2 contracts: terminal union is required if the current research questions and terminal primary metrics are retained. Node/edge statistics can be completed first but cannot replace terminal statistics. A paper limited to exploratory message-node and dependency-edge process results could omit union, but would need narrower questions and conclusions.

## What union answers

Node judgment asks whether a truth claim is fully expressed at one message node, whether its sources survive, and whether current sources support it. Edge judgment asks what changes are observed across a visible parent–child dependency. Terminal union asks which claims and attributable evidence remain across all outputs designated as terminal for that condition. The three objects are complementary.

If only one of three independent readers sees and fully expresses a fact, node-average CSR is 1/3 although the terminal set may contain the fact. Directly comparing that average with B0's single-node 1/1 mixes division-of-labor absence into terminal differences. Conversely, a fact present only at initial reading and absent in final communication cannot be restored to “terminal retention” by adding initial-history nodes back into the terminal set.

Source metrics present another risk: a fact at one node and an unrelated citation at another do not establish support merely because both occur in the terminal set. Union must preserve claim–source attribution, qualifications, and occurrence identity; it must neither choose favorable citations automatically nor merge all historical sources.

## Where the original design depends on union

| Paper location | Existing design | Consequence without union |
| --- | --- | --- |
| Section 6 | Frozen terminal-offline-union@1.0.0: last communication layer for M/A1/A2, three initial nodes for B1, sole centralized node for B0 | No common question-level measurement object for multiple terminal nodes |
| Section 9.1 | M–B1 compares communication with independent reading; M–B0 compares distributed protocol with centralized reading | Node-average contrasts describe process, not terminal CSR/ESS differences |
| Section 10 | Each truth claim contributes at most once to a question-level metric | Node summation duplicates counts; averaging changes metric meaning |
| Section 10.2 | CSR, ESS, VSSR, Attribution Adequacy, and five support outcomes | Terminal metrics require claim alignment and source/support judgment over the specified view |
| Section 11 | Within-question aggregation before macro means, repetition averages, and paired comparisons | Define the within-question view first; statistical averaging cannot create missing semantic union judgments |

## Why existing offline merging is insufficient

`src/agent_lab/m3_execution.py::_terminal_union` already selects outputs by condition and stores occurrences/deduplication groups using text, source, and qualification signatures. It is a nongenerative run record. M2 `TerminalObservationView` further constrains condition-specific selection and same-signature merging.

These objects establish visible terminal outputs and mechanically collapsible duplicates. They do not establish whether expressions jointly provide complete equivalence to a specified truth claim, whether conflicts exist, or whether sources jointly suffice. M2 `NodeJudgment` already supports `scope_kind=hop_union/terminal_union` and `scope_node_ids`; at the time of this assessment, formal semantic union judgments had not yet been supplied. `requires_explicit_hop_union` denotes a requirement, not completed review.

None of the following substitutes for formal union: averaging node CSR/ESS, applying a simple OR to node labels, string-only deduplication, pooling sources across truth claims, or changing candidate scope_kind to terminal_union without rechecking evidence.

## Frozen-panel inventory

See the read-only `union_scope_inventory.csv`; scope identities use communication layers of frozen runtime nodes. Counts measure task size, not new human conclusions.

| View | Observations or question-layer views | Truth-claim scopes |
| --- | ---: | ---: |
| All terminal views | 680 | 1,766 |
| Multi-node terminal views | 560 | 1,444 |
| B0 single-node terminal views | 120 | 322 |
| All question×observation×communication-layer views, including terminal layers | 1,120 | 2,888 |
| Multi-node communication-layer views | 1,000 | 2,566 |

The last two rows already include terminal scopes; do not add them as independent new workload. hop_union and terminal_union over identical node sets may share verified evidence and semantics but must retain distinct view identities and purposes.

These counts cover the full frozen panel, including older DeepSeek M and auxiliary Qwen topologies, and do not imply inclusion in the main comparison. Prioritize DeepSeek 1.0.4 terminal views and keep auxiliary comparisons separate. B0 has no multi-node merge problem and may reuse applicable judgments and evidence for the same node, but candidates remain candidates: view equivalence does not promote them to formal human-final records.

## Proposed minimum additional work at that stage

1. Add terminal union first, selecting frozen terminal node IDs: final communication outputs for M/A1/A2, three initial outputs for B1, centralized output for B0. No extra model calls or trajectory changes.
2. Freeze annotation rules: count each truth claim once; specify joint alignment, conflicts, duplicate/different source sets, and cross-node joint support. Extract sources from aligned runtime claims, not indiscriminate message-wide source unions; do not select a source subset afterward to improve ESS.
3. Reuse reviewed evidence while retaining independent union judgments. Prefill simple verifiable single-contributor candidates; route multi-node complementarity, contradiction, valid substitution, and source/support conflicts to human adjudication. The old node sample agreement of about 99% cannot be transferred to union.
4. Establish a separate union quality gate through human review or a frozen sampling/estimation plan with explicit evidence levels and weights. Claims that every primary-analysis item is individually human-final must meet that requirement; weighted-audit analysis requires corresponding method wording.
5. Add hop union if initial and terminal states are compared. Terminal union suffices for terminal condition comparisons; question-level CSR/ESS trajectories require comparable initial hop union. Existing node/edge process delivery does not justify inventing union judgments.

## Human adjudication requirements at that stage

Completed node/edge review need not be repeated. Statistical conversion and verification found no new field conflicts requiring semantic adjudication. The original terminal conclusions required new union semantics and quality review, not re-reviewing the existing 633 nodes or 189 edges, and not a determination that all 1,444 multi-node scopes must be manually reviewed from scratch. Workload depends on directly reusable evidence, conflicts, and exhaustive versus sample-based review.

## Manuscript wording to revise

- Describe the reduced exploratory study as 60 questions and DeepSeek r1/r2, separately from the original full r1/r2/r3 plan.
- Replace “all primary analyses use human final judgments” with the actual exact-review plus stratified human-sample weighted estimation; unaudited records have not individually passed human review.
- Restrict primary comparisons to DeepSeek 1.0.4 and list older M separately. Qwen chain and star_bidirectional are not repetitions of one condition. Star is auxiliary description, not grounds for reframing the study as a systematic topology comparison.
- Use descriptive intervals for this node/edge round, not the old Holm/three-repetition confirmatory plan. Full-population engineering-failure and failure-worst analyses have other denominators; the frozen successful-observation panel cannot replace them.

At the time of the source document, only node/edge statistics and the union design assessment were completed; the original paper was unchanged and no new union human judgments were generated. This historical statement is superseded by subsequent completed union review, as noted above.
