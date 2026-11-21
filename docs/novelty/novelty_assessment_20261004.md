# Paper A: final novelty assessment and writing boundaries

Date of source: 2026-10-04. English translation prepared for repository packaging on 2026-10-15.

**Historical document.** This translates the original assessment, including its then-current plans. Statements below about three repetitions, Holm correction, failure sensitivity and sample sizes are historical, not evidence of completed analyses. The frozen October 15 analysis uses 40 2Wiki and 20 MuSiQue questions, two repetitions and 520 main-panel observations. Current manifests and results take precedence. Literature judgments below reproduce the author's assessment; this packaging step did not perform a new literature search.

Scope: metadata from the full texts of 48 orange-tagged papers already read in `daily-literature-digest/paper-vault-site`, together with the Paper A proposal, data audit, evaluation specification, baseline/ablation design and frozen formal-experiment configuration. This is a pre-submission assessment of research novelty and wording risks, not a patent-law novelty opinion or a replacement for an incremental database search on the submission date.

## 1. Conclusion

None of the 48 papers fully covers the joint research object already implemented for Paper A. Writing can continue, and additional large-scale experiments solely to establish novelty are not recommended at this stage.

Broad claims in the original proposal are no longer safe. Multi-agent information degradation, provenance lineage, evidence grounding, loss of handoff metadata, shared-state contamination, process-level auditing, structured messages, topology and propagation, and correct answers masking incorrect states have each been substantially addressed. None should independently be claimed as a first.

The defensible novelty should be narrowed to the following:

> Bind each atomic truth claim to a human-audited canonical source set as an evaluation object traceable across messages. In a fixed three-agent document communication chain, separately measure semantic claim survival, exact canonical-source-set retention, valid source substitution, current evidential support and qualification changes. Use centralized reading, no communication, source-object masking and source-maintenance-instruction ablation to identify how communication and explicit source maintenance affect these states.

The central contribution is the inseparable combination of:

1. Human-audited truth claims and canonical source sets.
2. Explicit separation of claim survival, source identity, sufficient evidential support and factual correctness.
3. Joint reporting of CSR, ESS, VSSR and five support outcomes, rather than one provenance score.
4. Replayable state transitions at message nodes and dependency edges.
5. Controlled M/B0/B1/A1/A2 comparisons that separate communication, source-object visibility and source-maintenance instructions.
6. Human-audited 2WikiMultiHopQA and MuSiQue data, question-level pairing, three repetitions and failure sensitivity analysis.

## 2. Boundaries of the contributions available at that time

The formal design had narrowed substantially from the early proposal. Writing must follow the implemented configuration, not the August plan.

| Dimension | Implemented fact recorded on October 4 | Permissible claim |
| --- | --- | --- |
| Tracked object | Truth claim with a unique, nonempty canonical source set | Core contribution |
| Content/source separation | CSR, ESS, VSSR, support outcome, content truth, qualification change | Core contribution |
| Process resolution | Round-0 nodes, communication-output nodes, parent–child dependency edges | Node- and edge-level transitions |
| Communication structure | Three agents, chain, one communication round, structured messages | Fixed-chain protocol; no multi-topology claim |
| Hop | Successive observable communication edges in the fixed chain | Edge position or first-loss position, not systematically manipulated depth |
| Message format | Structured JSON in every formal arm; A1 masks source objects, A2 removes source-maintenance instructions | Source-protocol component ablations, not free-text versus structured formats |
| Data | 2Wiki: 400 questions, 1,000 claims; MuSiQue: 167 questions, 501 claims; human audit completed | Stronger audited references than unaudited or synthetic references in principal neighboring work |
| Conditions | M/B0/B1, with A1/A2 additionally on 2Wiki | Communication increment and source-maintenance mechanisms |
| Repetitions/statistics | r1/r2/r3, question pairing, cluster bootstrap, Holm and worst-case failure sensitivity | Credibility support, not methodological novelty |

The proposal's claim to jointly investigate propagation hops, communication topologies and message formats should therefore not be copied into the abstract or contributions. Without additional experiments, use “controlled analysis of communication edges and source-maintenance mechanisms within a fixed-chain communication protocol.”

## 3. Closest work requiring direct comparison

| Work | Overlapping elements | Elements of Paper A not covered | Assessment |
| --- | --- | --- | --- |
| Digital Pantheon | Multi-agent hub-and-spoke structure, lineage, five states, external outcome associations | Exact canonical-set transitions for each truth claim at nodes/edges; A1/A2 ablations; CSR/ESS/VSSR separation | Strongest conceptual competitor; incomplete coverage |
| CoMemBench | Multiple topologies, each handoff, grounded dependency graphs, contamination boundaries, public benchmark | Evaluates applicability/isolation rather than exact document-citation identity, valid substitution and support transitions | Strongest execution-benchmark competitor; different object |
| Right Answers Wrong States | Distributed evidence, misleading sources, verification, shared-state reconstruction, answer/state separation | Stable document source IDs, canonical sets, six-dimensional edge states and source-protocol ablations | Strong neighbor; incomplete coverage |
| Facts Without Rules | Handoff compression, separate survival of facts and boundary metadata, prompt interventions | Metadata concerns privacy/use boundaries rather than document identity; no canonical sets or support judgments | Useful for qualification changes; different object |
| ProvenanceGuard | Atomic claims, stable sources, source exchange, cross-source conflation | Primarily terminal verification; no multi-agent propagation, edge dynamics or communication ablations | Source-mismatch evaluation reference; not a dynamic study |
| LedgerMind | Source-constrained state machines, evidence ledgers, non-amplifying repair | Focuses on multimodal trajectories/runtime constraints, not inter-agent identity transitions or A1/A2 | Closely related structure; different experimental question |
| Evidence-First Multi-LLM | Multiple models, evidence binding, unresolved states, human reference graphs | Independent extraction then fusion, not survival through sequential handoffs | Evidence-fusion neighbor; not propagation |
| Epistemic Sybil Resistance | Evidence roots, repeated retelling, multiple agents do not imply independent evidence | No measurement of source-label loss/mismatch, valid substitution or edge support | Supports the distinction between source count and evidence independence |
| Skill Use or Skill Theater | Retained influence with lost provenance in multi-agent systems, counterfactual intervention | Sources are skills rather than documentary evidence; no canonical sets or stable transitions | Causal-attribution neighbor; different object |
| Semantic Tracing | Cross-hop semantic drift, weakened constraints, 450 experiments | Limited source identity and real human audit; no exact-set source survival | Semantic-degradation background; not the core metric |
| VST | Structured agent-to-agent transport, replayability, free-text ablation | Does not evaluate whether source semantics are preserved correctly | Engineering-protocol neighbor; different scientific question |
| MASTraceBench | Proposal trajectories, degradation of strong initial proposals during collaboration, process metrics | Tracks proposal quality rather than claim–source identity | Methodological neighbor; not provenance |
| Active Provenance Gate | Unsupported/wrong-source terminal synthesis and strict release gates | Terminal synthesis audit only; no multi-hop transitions | Terminal-audit neighbor; not dynamics |
| GuidelineGuard and GANDR | Sentence-/claim-level citation-support auditing | No multi-agent propagation or source-identity dynamics | Relevant support-evaluator work |

Other papers address topology, collective errors, retrieval poisoning, memory, governance, long-term propagation or evaluation. None combines all six components above. Within these 48 Paper Vault papers, the judgment of complete coverage is negative.

## 4. Claims that must be removed or downgraded

Do not claim in the title, abstract, introductory contributions or conclusion:

1. The first study of source-lineage degradation in multi-agent systems.
2. The first discovery that correct answers can mask incorrect intermediate states.
3. The first study of metadata or qualification loss during handoffs.
4. The first preservation of provenance or source IDs in multi-agent systems.
5. The first hop-, process- or topology-level propagation analysis.
6. The first distinction between content correctness and source correctness.
7. Systematic comparison of multiple topologies, propagation depths, or free-text and structured formats.
8. A new automatic verifier or defense. M is currently a source-aware communication protocol, not a new method with an independent verifier.

## 5. Recommended contribution wording

### One-sentence positioning

> We study not whether evidence is present at the end of a multi-agent workflow, but how a truth-anchored claim and its canonical source set survive, change, or decouple across document-grounded agent communication.

### Three contributions

1. **Truth-anchored measurement object.** We define a claim-level evaluation object that binds each audited truth claim to a canonical source set, allowing semantic claim survival to be measured separately from exact source identity and current evidential support.
2. **Decomposed transition measurement.** We reconstruct message-node and dependency-edge transitions and jointly report claim survival, exact-set source survival, valid source substitution, support outcomes, and qualification changes instead of collapsing provenance into one score.
3. **Controlled protocol decomposition.** On human-audited 2WikiMultiHopQA and MuSiQue instances, we compare a source-aware communication protocol with centralized reading, no communication, source-object masking, and source-maintenance-prompt ablation under paired questions and repeated runs.

### Conditional result templates

Do not write in advance of formal statistics that sources necessarily decrease monotonically with hop. Select wording according to the actual results:

- If ESS decreases while CSR remains stable, emphasize separation of semantic and source-identity retention.
- If VSSR increases, explain that changed identity need not imply lost support; distinguish exact survival from attribution adequacy.
- If A1 is significant and A2 weaker, emphasize source-object visibility over behavioral reminders.
- If A2 is significant and A1 weaker, emphasize the effect of maintenance instructions despite retained schema capability.
- If M differs little from B1/B0, report a constraint on inevitable-degradation claims in a highly structured, audited setting; do not manufacture degradation.

## 6. Are additional experiments needed?

### Default decision

Do not add experiments solely for novelty. The current joint object and mechanism decomposition are not fully covered by any single paper in the reviewed set. Stronger positioning, direct related-work comparison and narrow generalization are the most effective improvements.

Adding star/dense topologies, two communication rounds or free text is not currently recommended because:

1. It would alter frozen questions and comparison families and risk post-result design expansion.
2. New conditions need prompt/configuration hashes, pilots, failure policies and evaluation/statistical inclusion rules; the six-hour window cannot support the full matrix at equivalent procedural rigor.
3. The strongest distinction relies on canonical sets and multidimensional states, not multiple topologies.
4. A small added topology/free-text experiment would not support broad causal claims and would expose limited sample size, repetitions and multiple-comparison coverage.

### Hard triggers for considering a minimal extension

Only consider a minimal extension in a separate session after formal evaluation if:

1. Node/edge artifacts cannot reconstruct any genuine parent–child claim–source transition, leaving terminal metrics only.
2. Requests or child-visible snapshots cannot demonstrate the intended unique M/A1/A2 differences, making the ablation uninterpretable.
3. Most claims become unevaluable after round 0, leaving insufficient ESS/VSSR denominators.
4. The manuscript insists on message-format comparison or topology effects as a contribution and will not remove the claim.

For trigger 4, prefer a minimal condition explicitly downgraded to an exploratory appendix: fix 2Wiki, model and questions, freeze a small stratified subset, and compare structured transport in M with information-matched free text. Keep it outside the main confirmatory comparison family and do not claim cross-topology laws. At the then-observed approximately 15-hour full-batch throughput, six hours permits a small validation, not a full confirmatory matrix matching the main study's size and repetition count.

## 7. Suggested manuscript structure

1. Lead with the fact that correct outcomes do not establish preservation of a claim's canonical source identity; avoid an overly long general hallucination-propagation opening.
2. Organize related work into dynamic multi-agent propagation, claim-level attribution, provenance/runtime, and shared-state/memory boundaries.
3. Define four independent questions first: does the claim remain, does its canonical source remain, does the current source support it sufficiently, and is the claim still true?
4. Directly compare Digital Pantheon, CoMemBench, Right Answers Wrong States, Facts Without Rules and ProvenanceGuard in a table of objects and observables.
5. State the fixed chain, one round and structured JSON in experimental boundaries and limitations so the older plan is not mistaken for completed topology/depth manipulation.
6. Call B0/B1 in-house controlled baselines and A1/A2 source-protocol component ablations, without claiming replication of external systems.
7. Restrict conclusions to the tested document-grounded, structured three-agent chain; do not generalize to open-ended long-term autonomy, multimodality, arbitrary topologies or naturally occurring malicious collaboration.

## 8. Final judgment

| Question | Judgment |
| --- | --- |
| Does any one of the 48 papers provide complete coverage? | No |
| Is broad source-lineage degradation itself novel? | No; strong neighbors cover its components |
| Is the implemented joint measurement/ablation defensible? | Yes |
| Must new experiments be added to retain novelty? | No |
| Can multi-topology/depth causal comparison still be claimed? | No, unless experiments are added and the design refrozen |
| Main current risk | Overbroad wording rather than complete prior coverage |
| Recommendation | Do not expand the matrix; freeze narrowed title, abstract, contributions and comparison table |

Suggested title direction:

> When Claims Keep Their Meaning but Lose Their Sources: Measuring Canonical Source-Set Survival in Document-Grounded Multi-Agent Communication

The original concludes with an equivalent Chinese working title.
