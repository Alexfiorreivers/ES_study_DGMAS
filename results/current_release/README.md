# Current numerical release

Standalone CSVs in [source_data](../../paper_figures/source_data/) supply released point values. Table_2 through Table_6 are authoritative percentage inputs; figure_source_data.csv is a checked long-form mirror. Stable numeric identifiers do not require a document. Labels identify model/protocol, dataset and condition.

The audit-updated candidate view uses human judgments for reviewed/reused records and candidates otherwise. Node files call it candidate_sample_corrected; terminal files call it sample_replaced. Question-macro aggregation averages repetitions within questions, then questions equally. Edge rates pool applicable event counts. Terminal coverage includes 330 reviewed/reused and 1,036 candidate-only scopes. The node row in audit_coverage.csv represents the larger historical audit frame.

Current displayed aggregates match the frozen values after the author-confirmed restorations. [Numeric changes](value_changes.csv) compare current values to historical aggregates rounded to two percentage decimals. [Version log](NUMERIC_REVISION_LOG.md) defines the reconstruction boundary. Frozen estimators and intervals remain unchanged.

Run `python results/current_release/validate_release_alignment.py` from any directory. This standard-library check reads small aggregate tables only. It performs no document parsing, ledger rescan, resampling or model call. Optional plotting dependencies are separate.
