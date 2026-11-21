> Public-scope update (2026-11-21): full mixed-content evidence referenced below is now in the separate editorial store. Only retained code, synthetic examples, identifiers and aggregate files are public candidates. Historical source paths describe the earlier full snapshot; consult the root DATA_AND_EVIDENCE_INDEX.md.

# English publication derivatives and original archives

The main reading edition contains English document editions with language-neutral filenames. Original-byte verification archives were added on 2026-11-21 under results/original_records and results/original_qwen_chain; their contents intentionally preserve original language and historical paths. The localization statements below apply to the reading derivatives, not these original archives. The original research folders are not modified. Chinese duplicates were removed only from this directory; the English document now occupies the canonical basename.

## What changed

- Translated Chinese review notes, repair reports, metadata, code comments and display labels.
- Rendered original-script proper-name annotations in English/romanization, retaining the surrounding factual content.
- Replaced machine-specific Chinese paths with repository-relative locations where available or explicit historical identifiers where the original input is not distributed.
- Updated document links, mock input hashes, dataset sidecar bindings and current package checksums.
- Removed the machine-specific dataset packaging helper, which was not a portable processing entry point.

Scientific IDs, truth claims, audit labels, scope membership, estimators and result numbers were not re-adjudicated or recomputed. English filenames do not signify a new experimental run.

## Provenance and offsets

Original hashes remain historical identifiers. Current checksum manifests validate the distributed English files. They are distinct byte representations and must not be presented as identical. The external change log records old/new paths and hashes, with original source paths retained outside this English repository.

The final dataset derivative remaps and validates offsets affected by proper-name localization, while retaining stable claim/source IDs and truth labels. In the results archive, all 112 affected question-text objects use paragraph granularity or complete-document catalogs; an explicit association check found no non-null character-offset/span fields tied to those changed objects. No result-coordinate remapping was required. Do not reinterpret an unrelated historical coordinate field as an offset into a translated string.

The root `verify_repository.py`, `results/verify_snapshot.py` and `datasets/validate_release.py` validate this edition. They do not assert bit-for-bit reproduction of the original model inputs. Mock configurations explicitly identify English-localized dataset IDs. Original frozen model observations retain their historical run identities.

## Technical-only distribution

Article text, bibliography mappings, document authoring helpers and chart exports are excluded from the current working tree. Historical statistical evidence remains unchanged. Current CSV display revisions are identified separately in results/current_release and do not amend the earlier localization claims.
