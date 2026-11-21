# Dataset schemas and public identifiers

This public candidate includes structural adapters, Schema 3.0, fictional examples, validation specifications and public_metadata/. Full audited datasets and repair descriptions quoting questions are held in the private editorial store following the rights review.

public_metadata/input_pool_ids.json identifies the 400 accepted 2Wiki and 167 MuSiQue input records, with releases, splits and strata. source_locator_index.csv records 7,338 document occurrences with title-derived Wikipedia links and text hashes. These links have not been individually checked against a historical revision or imported-content notice. historical_selection_ids.json identifies the 680 historical observations, including but not limited to the 520 primary runs. No source paragraphs or question wording are included in these metadata files.

The schemas and synthetic examples remain usable without the private data. Historical adapters require upstream files and explicit paths. They do not recreate human adjudications. Full dataset validation requires the preserved private snapshot, including its original manifest; do not run validate_release.py against this reduced tree and interpret missing-data errors as research failures.

See [acquisition instructions](ACQUISITION.md), [third-party rights](../THIRD_PARTY_NOTICES.md) and [the evidence index](../DATA_AND_EVIDENCE_INDEX.md). Dataset-code licenses and content licenses are distinct. The public metadata is an extraction of existing identifiers and hashes; no sampling, judgments or statistics were changed.
