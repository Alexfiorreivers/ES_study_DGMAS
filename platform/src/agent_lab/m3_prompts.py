"""Versioned M3 prompt registry with frozen snapshots and deterministic rendering."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml

from agent_lab.adapters.datasets.data_truth_v3 import file_sha256
from agent_lab.domain.contracts_v0_1 import ExperimentConfig, ProviderMessage


def canonical_hash(value: Any) -> str:
    material = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResolvedPromptSet:
    prompt_ref: str
    registry_id: str
    registry_version: str
    registry_sha256: str
    condition_id: str
    system: str
    initial_template: str
    communication_template: str
    empty_document_reminder: str
    component_hashes: dict[str, str]
    prompt_set_hash: str

    def snapshot(self) -> dict[str, Any]:
        return {
            "prompt_ref": self.prompt_ref, "registry_id": self.registry_id,
            "registry_version": self.registry_version, "registry_sha256": self.registry_sha256,
            "condition_id": self.condition_id,
            "templates": {"system": self.system, "initial": self.initial_template,
                          "communication": self.communication_template,
                          "empty_document_reminder": self.empty_document_reminder},
            "component_hashes": self.component_hashes, "prompt_set_hash": self.prompt_set_hash,
        }


def resolve_prompt_set(config: ExperimentConfig) -> ResolvedPromptSet:
    condition = config.m3_condition
    if condition is None:
        raise ValueError("M3 prompt resolution requires m3_condition")
    path = Path(condition.prompt_registry.path).resolve()
    actual_hash = file_sha256(path)
    if actual_hash != condition.prompt_registry.expected_sha256:
        raise ValueError("PROMPT_REGISTRY_HASH_MISMATCH")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    entry = raw.get("prompt_sets", {}).get(condition.prompt_ref)
    if entry is None:
        raise ValueError(f"PROMPT_REF_NOT_FOUND: {condition.prompt_ref}")
    if entry.get("condition_id") != condition.condition_id:
        raise ValueError("PROMPT_CONDITION_MISMATCH")
    components = raw["components"]
    system = "\n".join(components[name].rstrip() for name in entry["system_components"])
    initial = components[entry["initial_component"]].rstrip()
    communication = components[entry["communication_component"]].rstrip()
    empty = components["empty_document_reminder"].rstrip()
    texts = {"system": system, "initial": initial, "communication": communication,
             "empty_document_reminder": empty}
    hashes = {name: sha256(text.encode("utf-8")).hexdigest() for name, text in texts.items()}
    set_hash = canonical_hash({"prompt_ref": condition.prompt_ref, "components": hashes})
    return ResolvedPromptSet(condition.prompt_ref, raw["registry_id"], raw["registry_version"],
                             actual_hash, condition.condition_id, system, initial, communication,
                             empty, hashes, set_hash)


def render_initial(prompt: ResolvedPromptSet, question: str, documents: str):
    content = prompt.initial_template.format(question=question, documents=documents)
    if not documents:
        content += "\n\n" + prompt.empty_document_reminder
    return (ProviderMessage(role="system", content=prompt.system),
            ProviderMessage(role="user", content=content))


def render_communication(prompt: ResolvedPromptSet, question: str, parent_views: list[dict]):
    parents = json.dumps(parent_views, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    content = prompt.communication_template.format(question=question, parents=parents)
    return (ProviderMessage(role="system", content=prompt.system),
            ProviderMessage(role="user", content=content))


def a2_prompt_diff(registry_path: str | Path, expected_sha256: str) -> dict[str, Any]:
    path = Path(registry_path).resolve()
    if file_sha256(path) != expected_sha256:
        raise ValueError("PROMPT_REGISTRY_HASH_MISMATCH")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    version = raw["registry_version"]
    base_ref, ablation_ref = f"m3-M@{version}", f"m3-A2@{version}"
    entries = raw["prompt_sets"]
    if base_ref not in entries or ablation_ref not in entries:
        raise ValueError("A2_PROMPT_DIFF_REFS_MISSING")
    components = raw["components"]
    def system(ref: str) -> str:
        return "\n".join(components[name].rstrip() for name in entries[ref]["system_components"])
    base, ablation = system(base_ref), system(ablation_ref)
    base_lines, ablation_lines = base.splitlines(), ablation.splitlines()
    removed = [line for line in base_lines if line not in ablation_lines]
    added = [line for line in ablation_lines if line not in base_lines]
    if not removed or base == ablation:
        raise ValueError("A2_PROMPT_DIFF_INVALID")
    return {"base_prompt_ref": base_ref, "ablation_prompt_ref": ablation_ref,
            "removed_lines": removed, "added_lines": added,
            "base_system_sha256": sha256(base.encode("utf-8")).hexdigest(),
            "ablation_system_sha256": sha256(ablation.encode("utf-8")).hexdigest(),
            "diff_sha256": canonical_hash({"removed_lines": removed, "added_lines": added})}
