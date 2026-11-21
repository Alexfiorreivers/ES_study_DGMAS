> Historical full-snapshot documentation. Some referenced inputs/outputs are now held in the separate editorial store after the rights review. This report does not establish public availability of those records.

# MuSiQue 167-item Schema 3.0 release validation

English release documentation localized from the accepted audit record.

Strict Schema 3.0, content/sidecar reversibility and mechanical checks passed. The M3-A format gate is `ready_for_platform_import`.

The core contains 167 records: 55 two-hop, 57 three-hop and 55 four-hop; 501 claims and 501 links. It excludes `human_audit`, link `supporting_sentences` and manually annotated document sentences. All 167 records have `normalization_status=normalized`. Repaired questions and claims remain in the core; repair history, human audit information and 486 sentence annotations are in the sidecar.

All recorded checks passed: unique core records; strict schema and relations; no extension fields or sentence payload in core; normalized status; claim/link totals and 55/57/55 distribution; unique, aligned sidecar records; aligned extended source; matching per-record core hashes; lossless extended-record reconstruction; ten human-repair entries; preservation of sentence-evidence counts; and matching primary manifest hashes.

Core and sidecar are aligned by sample order. The sidecar binds each record with `sample_id + core_record_sha256` and reconstructs the previously accepted extended release without loss. The manifest hashes the core, sidecar, extended file, repair report and formal schema.

Validation used the project Draft 2020-12 schema and the MuSiQue Schema3 converter's relational validator. Reasoning graphs were preserved; no new semantic judgments were made.
