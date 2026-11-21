# Numeric release version 2026-11-21

## Restoration of the 2Wiki M terminal row

The author clarified that the previous manual changes reflected a semantic reporting discrepancy. The current terminal row is CSR 50.00%, ESS 47.50%, VSSR 2.50%, and AA 50.00%. These values match the frozen `sample_replaced` rows for 2Wiki M in `results/research_change/final_statistics_stage_20261012/terminal_union_statistics_20261015/condition_question_macro.csv` after multiplication by 100. The same row appears in Tables 3, 4 and 5. `release_changes_20261121.csv` records the previous and restored display values. ESS was already 47.50% and did not change.

This correction was checked against the existing small aggregate CSV. It did not rerun models, relabel scopes, rescan ledgers, change sampling weights or recompute statistical estimators. All-message-node rates in Table 2 and supplementary HT expansions retain their distinct units and values.

## Author-confirmed restoration of the ablations

The authors subsequently instructed that A1 CSR, A2 CSR and A2 AA on 2Wiki be restored to 50.00%, matching the frozen sample_replaced aggregates. confirmed_restorations_20261121.csv records the three previous display values. value_changes.csv now contains its header only: no displayed node or terminal percentage differs from the corresponding frozen aggregate after rounding. A2 and M have identical CSR and AA; ESS decreases by 1.25 percentage points and VSSR increases by 1.25 points.

Point figures omit error bars. Historical uncertainty analyses remain available separately and were not recalculated. Agreement with frozen point estimates does not convert unreviewed candidate judgments into human annotations.

## Version and evidence preservation

Original judgments, candidate/human distinctions, selection identities, and historical statistical files are unchanged. HT and difference expansions remain supplementary historical views. Bounded current rates are not clipped HT estimates. Original checkpoint and annotation archives added for verification have their own member hashes and are distinguished from English reading derivatives in `DATA_AND_EVIDENCE_INDEX.md`.
