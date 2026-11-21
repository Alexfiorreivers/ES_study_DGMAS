# Baseline and ablation experimental design v2

Source date: September 22, 2026; narrowed on September 23 to a single commercial DeepSeek API. Full English translation prepared on October 15, 2026.

**Historical design, not an execution report.** The 400/200-question, three-repetition and Qwen plans below are preserved from the original. Current frozen results take precedence: the primary DeepSeek 1.0.4 comparison uses 40 2Wiki and 20 MuSiQue questions, two repetitions, 520 runs; A1/A2 apply only to 2Wiki. Confirmatory Holm tests and the complete planned matrix must not be inferred to have been performed.

The second version incorporates an audit of 161 previously inaccessible files; the first version remains available in the original project for traceability. The object is changing source identity and evidential support of explicit claim–source pairs in a three-agent message graph. The main outcome is not answer accuracy: the platform currently emits candidate claims without generating a final answer.

## 1. Research questions and boundaries

1. With model, data, document assignment and budget held fixed, does multi-agent propagation degrade source identity relative to independent initial reading?
2. What separate effects do explicit source objects and propagation instructions have on claim retention, source-identity retention and sufficient support?
3. Are directions consistent across 2Wiki and MuSiQue and stable over three complete DeepSeek runs?

DeepSeek is the generator for all baselines and ablations in this section. Qwen3-8B belongs only to a separate small-model study and runs the main condition, not baselines or ablations. Freeze service name, version snapshot, available parameters and date at formal launch. `deepseek-flash` is the existing engineering-pilot name and cannot be assumed to be the later formal model without checking. DeepSeek weights are unavailable, so weight-level reproducibility cannot be claimed; repetitions quantify variation under the current service conditions only.

## 2. Samples and experimental units

| Module | 2Wiki | MuSiQue | Question addressed |
| --- | ---: | ---: | --- |
| DeepSeek main condition | 400 | 200 | Hop-level degradation, cross-dataset direction and difficulty strata |
| DeepSeek baselines | 400 | 200 | Incremental effect of propagation versus independent reading/centralized reading; robustness across datasets |
| DeepSeek ablations | 400 | 0 | Mechanistic contribution restricted to 2Wiki |
| Qwen3-8B main condition | 400 | 200 | Descriptive small-model performance and paired-question comparison with DeepSeek |

The 400/200 questions must be fixed existing final-silver IDs; failed questions must not be replaced. Stratify 2Wiki by four question types, and MuSiQue by 2/3/4 hops and decomposition templates. Freeze order, data and repair SHA-256, assignment policy and prompt hashes. Gates A/B have passed on both complete datasets, but establish structure and assignability only; silver claim–source semantics still require stratified human audit. Systematic mismatch requires a new data version and refreezing all conditions, not selective removal of unfavorable questions.

The independent analysis unit is the question. Its claims, nodes, edges and three repetitions are nested observations, not extra independent questions. Cross-dataset comparisons assess external robustness, not a causal dataset effect, because source granularity, reasoning structure and assignment differ.

### 2.1 Data-version gate after checking newly available files

The previously inaccessible MuSiQue pipeline also contains 200 questions in `final_silver/3.0`, SHA-256 `8221fdc3...520d7738`. The current platform uses a later repaired file, SHA-256 `3f7af62a...dbe9ada`. These are not interchangeable samples. Formal MuSiQue runs must use the current repaired file and repair manifest, with full hashes in every YAML and evaluation manifest. The older pipeline selection had 67 2-hop questions, 34/33 in 3hop1/2, and 23/20/23 in 4hop1/2/3, including one `review_required` item. This does not establish completed semantic human audit of the repaired version.

Four `2wiki_inference_*.json` files in the restricted directory contain 40 questions and 80 claim–evidence units, but `support_label`, `item_decision`, annotator and completion date are blank. They are forms awaiting annotation, not 40 audited questions. After freezing, perform stratified semantic claim–source review and report each support label and mismatch rate; preferably verify canonical sets for all 600 questions. If only sampling is feasible, retain silver status, use a prospectively randomized audit subset covering all four 2Wiki types and six MuSiQue templates, and report its conclusions and sensitivity relative to all silver data separately. Do not call the whole dataset human gold.

Another restricted pipeline contains 200 HotpotQA final-silver questions passing local format validation. They are outside this round's 2Wiki/MuSiQue samples and the current formal platform profile, and do not alter the matrix.

## 3. Conditions and operational definitions

Fix data version, model, temperature 0, thinking disabled, structured-JSON contract, question list, answer isolation, evaluation rules and maximum output budget across conditions; differences must be visible in configuration manifests. Use a chain and one communication round initially. Two rounds or star topology can belong to a preregistered topology analysis but must not be mixed into this ablation after observing results.

| ID | Type | Operational definition | Comparison | Interpretation boundary |
| --- | --- | --- | --- | --- |
| M | Main protocol | Assign documents to three agents using the frozen gold policy; chain propagation with structured EvidenceRef on candidate claims and source-transfer instructions | Common reference | Source-aware communication protocol, not a new automatic-verifier method |
| B0 | Centralized reading | One model call reads the same gold documents as M and emits the same StructuredPayload, without inter-agent propagation | M − B0 | Diagnoses propagation cost; calls and visible-document volume differ, so report tokens/calls and avoid a standalone causal-superiority claim |
| B1 | No communication | Agents read their own documents exactly as in M, stop at round 0, then offline-union candidate claims | M − B1 | Coverage/loss from communication; compare a common question-level terminal definition and do not invent B1 hop 1 |
| A1 | Source-object transmission ablation | Initial reading may cite evidence; mask `source_refs` in parent claims delivered downstream, preserving other content and output schema | M − A1 | Source-identity visibility; also measure CSR/support/missingness because some ESS reduction can be mechanical |
| A2 | Source-maintenance-prompt ablation | Keep EvidenceRef and all parent-message fields; remove instructions such as copying complete source objects and avoiding claims without locators; retain JSON shape, safety and valid-locator contract instructions | M − A2 | Behavioral instruction rather than structural capability; record prompt-length changes |

B0/B1 are in-house controlled baselines, not reproductions of published systems. A1/A2 remove existing M components only. If A2 has excessive schema/model failures, run a separate small contract pilot. Report failures themselves without treating failed requests as semantic claim loss. Do not list verifier removal because no verifier exists. A1 requires versioned parent-message projection; B0/B1 require new execution modes. Prompt edits alone cannot implement these behaviors.

**Version-2 comparison clarification.** B0/B1 have no M-like communication edges, so do not directly compare their edge retention or hop 1. Define the last observable output set for each condition before terminal comparison. For M, use designated final-round receiver(s)/predefined terminal nodes, or the same offline-union rule across all conditions. Comparing M's all-history UnionAggregator with B1's round-0 union would retain historical initial claims and can hide propagation loss. Compare hop curves only among M/A1/A2.

The main condition and both baselines were planned for all 600 questions; the two ablations for 400 2Wiki questions only. A1/A2 conclusions cannot be generalized to a MuSiQue ablation. DeepSeek runs M/B0/B1/A1/A2; Qwen3-8B runs M only.

## 4. Three complete repetitions

For each model × condition × dataset, independently run the same question list three times, r1/r2/r3, matching comparisons by question and repetition. Each repetition creates new runs without overwriting older files. Save request time, response model name, provider-visible version, full parameters, prompt hash, usage, errors and actual attempts. Temperature 0 does not guarantee byte-identical remote API responses. Repetitions quantify run variation; invisible weights are not a statistical rationale for three repetitions, and three runs cannot eliminate silent provider updates.

First average three repetitions within each question/condition, then macro-average over questions. Report individual r1/r2/r3 values, mean, standard deviation or range, and a question-level bootstrap 95% interval. Compute paired condition differences before aggregation. Bootstrap question clusters with their three repetitions and strata intact; do not treat 1,200/600 runs as independent questions. Three repetitions describe run variance only roughly and do not support precise stochasticity estimates. Prespecify missingness: separate request completion and failure reasons; calculate primary semantic metrics only on complete evaluable questions with condition denominators; paired differences use questions evaluable in both arms. Also provide a worst-case failure sensitivity bound; do not silently add replacement questions.

Approximate calls, if M/A1/A2 use five model calls per question: 9,000/6,000/6,000 for the respective DeepSeek conditions over three repetitions; B1 5,400 (3 × 600 × 3); B0 1,800 (1 × 600 × 3), totaling approximately 28,200 logical calls. This excludes retries, evaluators and Qwen3 and is not a cost estimate. Rebudget from pilot input/output tokens, current prices and maximum retries before execution. Qwen3 M adds approximately 9,000 calls. Two rounds or star topology require a separate incremental budget.

## 5. Metrics, comparisons and manuscript presentation

Use Task D v0.2 question-level CSR, ESS, VSSR, the five support outcomes and ReviewRate; additionally report source precision/recall, edge-level transitions and first-loss hop. Judge factual correctness separately from current support. Show `needs_review` counts and reasons with each table rather than only post-filter rates. Separate evaluator and generator versions and hide condition names in blind evaluation. At minimum use stratified human calibration/review. LLM candidate judgments require human accuracy checks and retained difficult cases, rather than being accepted directly as truth.

Suggested result groups were: (1) DeepSeek M CSR/ESS by hop on both datasets; (2) M versus B0/B1 paired differences and cost; (3) 2Wiki A1/A2 differences from M and failure rates; (4) descriptive Qwen3 versus DeepSeek M. The model contrast is between model instances, not parameter size alone, because training data, service mode and versions differ. Without final-answer generation, do not report QA EM/F1. Claims about answer quality require a separately implemented and validated final-answer module and common scoring protocol.

## 6. Execution order and freeze gates

1. Complete M2 node/edge semantic judgments and human calibration on the existing eight real trajectories; ensure every metric can be replayed to numerator, denominator and source text.
2. Implement the prompt registry, B0/B1 execution modes, A1 message projection and versioned A2 prompt. Verify truth isolation, request reconstruction, failure classification and condition differences.
3. Run small same-question DeepSeek pilots for new conditions to check structural success and token bounds. Pilot questions may come from the formal set, but formal analyses must use complete new post-freeze runs; pilots do not count as repetitions.
4. Freeze conditions, main comparisons, samples, exclusions, statistical-script version and human audit plan; then run three complete repetitions.
5. M3 produces claim/question/condition detail and question-paired statistics. Manually check samples, anomalies and model-version drift before manuscript tables and figures.

The proposed minimum publishable package combined degradation of source identity relative to claim retention, the communication increment, two mechanism ablations and cross-dataset/model replication. If reliable nonzero degradation is absent or the semantic gold audit fails, report this and reconsider the question; do not manufacture an effect by changing metrics or selecting questions.
