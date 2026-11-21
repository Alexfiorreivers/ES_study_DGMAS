> Historical full-snapshot documentation. Some referenced inputs/outputs are now held in the separate editorial store after the rights review. This report does not establish public availability of those records.

# 2Wiki audit gold

English release documentation localized from the accepted audit record.

This package uses `2wiki_final_400_silver.jsonl` as its sole data basis and synchronizes the final human-audit decisions.

- 400 records; Schema 3.0.
- Four question types, 100 each: bridge_comparison, comparison, compositional and inference.
- All claims have `gold_audit` status.
- Combined file: `2wiki_audit_gold.jsonl`.
- Each `2wiki_audit_gold_<question_type>.jsonl` partition contains 100 records.

Passed items retain the silver content with human gold metadata. For items requiring revision, only adjudicated fields were synchronized. Four special items were processed after the regular items and placed at the end of the combined JSONL. The manifest records field changes, coverage checks and SHA-256 values.
