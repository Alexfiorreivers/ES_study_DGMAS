# Evidence traceability in document-grounded multi-agent systems

This is the public-candidate working tree for the ES_study_DGMAS study. It contains project code, synthetic schema examples, study identifiers, statistical aggregates and figure generators. Mixed full-text inputs, model checkpoints and quoted audit records have been moved to a private editorial store after the 2026-11-21 rights review. No remote push or visibility change has occurred.

**Do not push the existing Git history.** Earlier commits contain full-text evidence removed from this working tree. Use the separately prepared history-free public export as the source for a new clean release after approval. Deleting files in a later commit does not remove older copies.

## Contents

| Path | Contents |
| --- | --- |
| [platform/](platform/README.md) | Experiment runtime, prompt registry and eight mock configurations; no model weights or credentials |
| [datasets/](datasets/README.md) | Adapters, schemas, synthetic examples, pool IDs, source locator/hash index and historical selection metadata; no full source passages |
| [results/](results/README.md) | Retained analysis code and two aggregate source tables for current numerical validation |
| [analysis_support/](analysis_support/README.md) | Twenty historical aggregate CSV tables, provenance and interpretation boundaries |
| [paper_figures/](paper_figures/README.md) | Current table/figure source values and generators for the workflow and Figures 3–7 |
| [docs/](docs/) | Evaluation definitions, design, deployment notes and licensing evidence |
| [DATA_AND_EVIDENCE_INDEX.md](DATA_AND_EVIDENCE_INDEX.md) | Public/private evidence map and access limitations |
| [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) | Official license findings, attribution and material held from public release |
| [UPLOAD_READINESS.md](UPLOAD_READINESS.md) | Clean-history requirement, checks and remaining release actions |

## Supported public checks

Use Python 3.11 for the platform (its declared version). From the repository root:

```sh
python -m pip install -e ./platform -r datasets/requirements.txt -r paper_figures/requirements.txt
python verify_repository.py
python verify_public_release.py
python platform/scripts/smoke_check.py
python results/current_release/validate_release_alignment.py
```

These checks do not call models, rerun experiments or recalculate record-level statistics. The mock check validates configuration and prompt contracts; it does not execute a dataset-backed experiment. Optional figures can be generated with `python paper_figures/build_figures.py`. Historical analysis builders need private evidence and can write files; they are not public-checkout reproduction commands.

## Scientific scope

The primary comparison uses 60 questions and 520 DeepSeek runs. The 680-row historical selection includes additional comparison configurations. Terminal review covers 330 exact/reused/sampled scopes; 1,036 other scopes remain candidate-only. Aggregates and labels must not be described as complete human verification. The public package supports inspection of definitions, identifiers, published aggregates and plotting. It does not alone reproduce human judgments or full model traces; those are in the editorial evidence store.

Original software is [Apache-2.0](LICENSE); original non-software contributions are [CC BY 4.0](LICENSE-DATA.md) to the extent of author-held or authorized rights. Copyright 2026 Rongrong Li and Jiecai Zheng personally. Third-party rights remain separate. The intended remote is https://github.com/Alexfiorreivers/ES_study_DGMAS; no public accessibility or study DOI is asserted.
