# Public and editorial evidence index

The 2026-11-21 redistribution review split the earlier full evidence checkout into a public candidate and a separate controlled editorial store. Original records and numerical results were not edited to perform this split. A file-level routing manifest is in docs/licensing/file_routing_20261121.json.

| Material | Public location or status |
| --- | --- |
| Audited input pool membership | datasets/public_metadata/input_pool_ids.json: 400 2Wiki and 167 MuSiQue identifiers and strata; no question or passage text |
| Document locators | datasets/public_metadata/source_locator_index.csv: 7,338 occurrences, titles, inferred Wikipedia links and text hashes; links are not individually verified license clearance |
| Historical observation identity | datasets/public_metadata/historical_selection_ids.json: identifiers from the frozen historical selection; not new observations |
| Numerical outputs | paper_figures/source_data/, analysis_support/tables/ and the two retained aggregate CSV files under results/research_change/ |
| Original runtime and estimators | platform/, results/src/ and retained historical .py analysis sources |
| Input schemas and conversion | datasets/schema/ and datasets/adapters/; examples are fictional, not benchmark excerpts |
| Full inputs, structured model messages, source catalogs and human explanations | Excluded from public distribution; unchanged copies preserved in the separate editorial store |
| Original DeepSeek/Qwen archives | Excluded from public distribution; original bytes and member manifests preserved in the editorial store |

The private archive preserves original repository-relative paths. Its pre-review snapshot supports the earlier full checks (datasets/validate_release.py, results/verify_snapshot.py and results/verify_original_archives.py); those checks require that private snapshot, not this reduced public tree. Original checkpoint coverage is 520 primary DeepSeek, 80 earlier DeepSeek and 40 Qwen chain checkpoints. Associated Qwen run snapshots and the 17-file input/annotation archive are also preserved.

The English editorial package supplies readable evaluation and annotation records with explicit original-versus-translated hashes. A complete vendor HTTP-response capture and individual reviewers' initial assignment folders remain outside the asserted scope. Public readers can obtain official benchmarks from the links in datasets/ACQUISITION.md. Authors must assess any request for full study records under the applicable rights; availability on request is not promised without that assessment.

Changing the public distribution boundary does not change the experimental data or conclusions. The manuscript's Data Availability paragraph must distinguish this public code/aggregate release from the separately provided editorial evidence before resubmission.
