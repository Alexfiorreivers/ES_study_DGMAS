> Historical full-snapshot documentation. Some referenced inputs/outputs are now held in the separate editorial store after the rights review. This report does not establish public availability of those records.

# DeepSeek 1.0.4 terminal-union judgment and audit plan

English companion. Version terminal-union-primary-1.0, 2026-10-13. These additional evaluation rules apply to already frozen experiments and do not modify the original experiment, node/edge judgments, or earlier statistics. The plan was fixed before union rule proxies and sampling were generated. Node results were already known; no experiment-preregistration claim is made.

**Historical-status note:** future-tense review instructions describe the original plan. Review and terminal-union statistics were completed on 2026-10-15; the latest finalization status and final handoff govern current completion. This translation requests no repeat adjudication.

## 1. Objects and terminal boundaries

Include only DeepSeek/deepseek-flash, prompt 1.0.4, chain, original_protocol: M/B0/B1/A1/A2 for 2Wiki and M/B0/B1 for MuSiQue; r1/r2; 60 questions, 520 observations, and 1,366 terminal×truth-claim scopes. B0 has 322 single-node scopes and the other views have 1,044 multi-node scopes. Exclude older M, Qwen, and other topologies.

For M/A1/A2 select round=1 communication_output and exclude all initial-history nodes. B1 selects the three round=0 initial_output nodes; B0 selects its sole centralized output. Each observation has one union scope per truth claim. Scope IDs depend on observation_key, terminal node-ID set, truth-claim ID, and rule version. Do not merge conditions, repetitions, or identical texts into one observation.

Preserve every original terminal runtime claim, source_refs, qualification, summary, and node identity. Runtime claim IDs can repeat across nodes, so alignment uses the namespace node_id::claim_id with a reverse mapping. Nodes without terminal claims remain in scope_node_ids; empty outputs do not remove denominators.

## 2. Semantic and source rules

First determine whether the terminal set fully and equivalently expresses the target truth claim; then judge sources and support attached to the aligned expressions themselves. The view is nongenerative: no new model answers and no restoration of facts found only in initial history.

Identical text with different sources, qualifications, or contexts remains a separate occurrence. Recheck whether partial expressions jointly establish equivalence, whether expressions conflict, and whether cross-node coreference is clear. Contradiction/ambiguity requires human review and must not be concealed by an “at least one node is correct” OR.

Human-confirmed alignment should list all terminal occurrences relevant to full/partial expression and explain excluded distractor expressions. Do not choose favorable source subsets to improve ESS/support. Derive and deduplicate runtime_source_ids only from explicit references of accepted aligned expressions; do not borrow references from unaligned claims or historical nodes. Human reviewers determine sufficiency where joint support is inadequate, conflicting, or involves different resolvable source sets. Programs only compare sets and derive exact_set_survived/source_change_status under M2.

When missing/unidentifiable sources coexist with identifiable sources, or expressions carry different source sets, do not automatically pool them into identifiable/fully_supported. Human review must specify aligned expressions, reference attribution, and joint-support evidence. If unresolved, use valid needs_review reasons and preserve the pending state.

CSR, ESS, VSSR, AA, and five support outcomes retain M2 definitions with terminal truth-scope denominators, never message-node averages. Union-absence rule proxies use missing to indicate no target expression detected in that view. This is a proxy to be tested, not a final absent judgment without human evidence.

## 3. Reuse hierarchy for node evidence

Priority: current 769 formal node adjudications > completed 633 node human forms > original candidates. Each scope records the actual source, original fields, hashes, and candidate differences. Do not transfer node-sample weights to union or fill sources/support from another run.

**Equivalent views eligible for direct semantic reuse:** a B0 single node whose target was reviewed; or a terminal view with exactly one node containing claims and all other nodes valid no_new_information empty structures, where the sole nonempty node's target was reviewed. These are mappings of identical observed content and need no identical semantic re-adjudication. Preserve independent terminal scope IDs and reuse evidence without inventing a new human-final signature. Previously resolved substitution/inadequate-support/revision cases in identical views are not re-reviewed merely because of a risk label; identity or evidence-structure conflicts suspend reuse. The same risks across multiple nonempty nodes still require union adjudication.

Even when every nonempty node has human review, node labels cannot simply be copied into final multi-node union judgments. Positive alignments/source evidence can be reused and negatives can narrow search, but complementarity, conflict, and additional sources at other nodes must still be assessed.

**Simple rule proxies:** single-node candidates; multi-node views with only one present_equivalent and all others absent; or all nodes absent. The first two copy corresponding existing fields and create explicit union identity; the last produces only an absence proxy for sampling. All remain automatic_candidate, is_final=false, without a claim of independent completed union semantic reading. All-absent multi-node proxies particularly require checks for individually incomplete expressions that become complete together.

**Complex items:** retain node judgments and evidence as component proposals. Do not force a full Union NodeJudgment or treat unknown as negative. Humans complete union alignment/source/support fields.

## 4. Risk routing requiring itemwise human adjudication

Any of the following enters the certainty/high-risk stratum instead of probability sampling:

- Partial, uninterpretable, or needs_review expressions that may require cross-node combination.
- Two or more nodes with equivalent/partial expressions of the target; matching labels still require joint-source/conflict checks.
- Valid/invalid substitution, unidentifiable sources, or equivalent expressions with partial/contradicted/insufficient support.
- false/undetermined content truth, qualification_change, or unsupported_spans.
- A reviewed terminal node differing from its original candidate on seven principal fields, requiring clarification of the revision's union consequences.
- Alignment references that cannot map to a real runtime claim in that terminal node, or inconsistent canonical/source structure. Suspend identity/structure failures first rather than hiding data errors through human voting.

Absent source markers alone, such as expected A1 masking, do not automatically create high risk; sampling must nevertheless check missing references and support inapplicability. High risk does not imply a wrong outcome, and absence of a high-risk flag does not establish proxy correctness.

## 5. Independent union sampling of simple proxies

After excluding high-risk items and direct semantic reuse, stratify the simple-proxy population by dataset×condition×proxy_pattern. For each stratum, `n_h=min(N_h,max(2,ceil(0.10*N_h)))`. Use seed terminal-union-primary-audit-20261013-v1 and select the first n_h after sorting SHA256(seed|scope_id). Every stratum has positive inclusion probability; small strata may be fully audited. Freeze candidate/evidence hashes before sampling and never change samples after viewing human results.

This is a new audit of union rule proxies; the earlier node agreement of 99% is not transferable. Check all terminal nodes in each sampled item, including other unaligned expressions and their sources, rather than confirming only a prefilled positive. Candidates reside in a separate sidecar; evidence text first displays raw terminal material. Record candidate viewing truthfully and do not call it independent blind review.

The author review queue comprises all high-risk items plus the stratified simple-proxy sample. Direct semantic reuse needs no repeat adjudication but retains a traceable list. Unsampled proxies remain non-final. A fresh human signature for every union item would require reviewing the remainder; the default continues the node/edge exact-component-plus-sample-estimation approach.

## 6. Review form and quality gates

Each item retains stable scope ID, queue number, question, condition, replicate, truth claim, all terminal nodes, reviewed fields, and source evidence. human_review is initially empty. The author supplies reviewer_id, reviewed_at, viewed_candidate, decision, aligned occurrence IDs, claim_presence, source_marker_status, runtime_source_ids, support_fine, content_truth, qualification_change, unsupported_spans, disposition, review_status, reason_codes, and a specific rationale. Simple proxies may be explicitly accepted; incomplete complex items require new judgments rather than “retain candidate.”

Generation scripts must not supply human answers, automatic timestamp signatures, or default affirmative opinions. Before later import, validate occurrence identity, reference attribution, canonical sets, M2 cross-field constraints, review provenance, and audit lineage. After reviewing all high-risk and sampled items, separately report actual review, direct reuse, unsampled estimates, and candidate sensitivity; never write fractional expanded counts into individual records.

The primary total combines exact direct reuse + exact exhaustive high-risk review + weighted simple-sample human results. Count each truth scope once within question; average r1/r2 and then use paired question comparisons. Compute only after review completion. Stratum agreement is not an individual correctness probability for unaudited items. If systematic alignment/source-rule defects emerge, record a new version and affected domain for review; do not silently change current labels or delete samples.

## 7. Delivery scope at the planning stage

Produce 520 terminal observation evidence packages, 1,366 scope identities, direct-reuse mappings, simple rule candidates, complex-item component proposals, frozen samples, human work forms, and readable evidence. The original delivery was reviewable judgment material and a plan, not a claim that then-unmade author decisions were complete. Qwen, older M, and initial hop_union were excluded. Subsequent completion is governed by the 2026-10-15 finalization records.
