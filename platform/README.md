> Public-scope update (2026-11-21): full mixed-content evidence referenced below is now in the separate editorial store. Only retained code, synthetic examples, identifiers and aggregate files are public candidates. Historical source paths describe the earlier full snapshot; consult the root DATA_AND_EVIDENCE_INDEX.md.

# Minimal experiment platform

This directory packages the Python runtime used by the local experiment platform, with the frozen 1.0.4 prompt registry. Source modules retain English output labels in acceptance.py and narrowly scoped English-input support in m3_execution.py and contracts_v0_1.py; other modules are copied unchanged from `agent_experiment_platform/src`; `SOURCE_COMPARISON.json` compares each module with the earlier `agent-platform` remote Qwen snapshot. That older snapshot has only prompt versions 1.0.0/1.0.1 and is therefore not an adequate substitute for the main-study runtime.

## Scope

The paper analyzes a frozen exploratory subset: DeepSeek 1.0.4, three agents, one synchronous chain communication round, original protocol. 2Wiki compares M/B0/B1/A1/A2; MuSiQue compares M/B0/B1. The observed subset comprises 40 and 20 questions respectively, two repetitions, and 520 observations. Source code also retains older capabilities because the CLI imports them; their presence does not mean the paper evaluated them. `m3_statistics.py` belongs to the general platform CLI and is **not** the final node/edge/terminal-union estimator; use the separately packaged final statistics for paper results.

M preserves sources; B0 reads centrally; B1 reads independently without communication; A1 masks parent sources; A2 removes source-maintenance instructions. A1/A2 are defined for 2Wiki only. The runtime keeps frozen mailboxes, structured messages, document-assignment rules, trace identities, and terminal-node boundaries. Offline union auditing is separate from model generation.

## Installation and offline checks

Use Python 3.11, from this directory:

```sh
python -m pip install -e .
python scripts/smoke_check.py
agent-lab --help
```

`requirements.lock` is the direct-dependency pin list from the minimal snapshot, not a complete transitive lock or evidence of the exact historical environment. Installation may require network access. The smoke check itself has no provider calls: it imports the package, validates all eight mock configurations, verifies the prompt registry hash, resolves prompts, and checks condition contracts. It does not run or reproduce the paper experiment.

`configs/examples/*_mock.yaml` are flattened, portable development examples derived from the existing fake-provider configs, updated to prompt version 1.0.4. Their pilot question lists are intentionally retained and are **not** the frozen analysis sample. Dataset paths are relative to this platform directory; see the dataset package. The example provider is a deterministic mock. For actual generation, users must explicitly configure a supported provider and their own environment-held credentials; no credentials or remote deployment endpoints are distributed here.

## Selection and provenance

Retained: core Python dependency closure, package metadata, frozen prompt registry, portable mock examples, offline validation script, and module comparison. Omitted: Git history, environments, caches, remote deployment details, historical shell launchers, pilot run outputs, duplicate datasets, obsolete prompt versions, and archived web pages. Final observations and audit results are distributed outside this runtime directory.

Original project software is licensed under Apache-2.0; see LICENSE and NOTICE in this directory and ../LICENSING.md for scope. Check repository-level rights information and the originating datasets' terms before redistribution. Hashes and per-file selection reasons are recorded in the external packaging checklist. This package has not rerun model experiments and makes no claim that historical outputs can be regenerated identically.

## English-localized dataset inputs

The mock examples now bind to the English-localized dataset files and their current SHA-256 hashes. Their dataset IDs explicitly identify this derivative. These are demonstration inputs, not the byte-identical historical experiment inputs; frozen observation identifiers in the results archive retain their original identity. Only display text, proper-name annotations and supporting offsets were localized; research labels and numerical results were not recomputed.

The English-input identity exception requires both `run_intent=development` and the `lineage_replay_mock` provider. Formal inputs remain subject to the original frozen-identity checks.
