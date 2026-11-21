# Analysis boundaries

## Units and configuration

The primary configuration includes 40 2Wiki and 20 MuSiQue questions, 520 runs, 4,898 node scopes, 1,444 edge scopes and 1,366 terminal scopes. Historical node/edge audit frames contain 7,098 and 2,444 scopes. Node, applicable-edge and terminal denominators are distinct. Qwen chain and star runs are different topologies, not repeated runs of one configuration. Provider, protocol and model differences are confounded.

## Audit coverage

Review was non-blind and candidate-assisted. Terminal evidence consists of 210 exact/reused units and 120 sampled units from 1,156 residual units; 1,036 units retain candidate-only evidence. Candidate agreement is not independent inter-annotator reliability. Most residual edge proxies were reconstructed after review. Dataset preparation review and output review concern different objects. Audit workload constrained the execution panel; fixed quotas and hash ordering do not establish population representativeness.

## Views and versions

Current released point values use the audit-updated candidate interpretation: reviewed units use human evidence and unreviewed units retain candidates. Node files call this candidate_sample_corrected; terminal files call it sample_replaced. The 2Wiki M terminal row was restored on 2026-11-21 to the frozen sample_replaced values. All displayed node and terminal percentages now match the corresponding frozen aggregates after rounding; see [numeric version log](results/current_release/NUMERIC_REVISION_LOG.md). No original judgments or historical estimators were modified.

Supplementary HT expansion and difference correction are unconstrained estimators. Values outside natural bounds are retained, not clipped. Question-level rates average repetitions within each question before equal-weight averaging across questions. Edge event rates pool applicable event counts and are not interchangeable with question-macro rates. A zero applicable denominator yields undefined, not zero.

## Uncertainty and interpretation

Historical whole-question bootstrap intervals fix audit assignments/weights and do not include unreviewed-candidate errors. Audit-design intervals describe finite-panel sampling uncertainty under within-stratum simple random sampling without replacement. These components are distinct; neither removes systematic judgment error. Old intervals are not attached to the current revised point values. No new intervals, confirmatory tests or equivalence claims are supplied.

Terminal source corrections were not back-propagated into old node/edge judgments. B0 node and terminal estimates share output content, so version differences cannot be treated as propagation transitions. Different reading boundaries and dataset composition prevent identifying a pure communication or reasoning-complexity effect from aggregate contrasts. The repository retains exploratory technical evidence, not universal causal or deployment claims.
