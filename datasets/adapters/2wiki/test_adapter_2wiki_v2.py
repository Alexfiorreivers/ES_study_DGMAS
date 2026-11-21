"""Minimal standard-library tests for adapter_2wiki_v2.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import adapter_2wiki_v2 as adapter


HERE = Path(__file__).resolve().parent


def fixture_record(question_type: str = "compositional") -> dict:
    return {
        "_id": f"fixture-{question_type}",
        "type": question_type,
        "question": "Fixture question?",
        "answer": "Entity C",
        "context": [
            ["Entity A", ["Entity A is connected to Entity B."]],
            ["Entity B", ["Entity B was educated at Entity C."]],
        ],
        "supporting_facts": [["Entity A", 0], ["Entity B", 0]],
        "evidences": [
            ["Entity A", "creator", "Entity B"],
            ["Entity B", "educated at", "Entity C"],
        ],
        "evidences_id": [
            ["Q1", "creator", "Q2"],
            ["Q2", "educated at", "Q3"],
        ],
        "entity_ids": "Q1_Q2",
        "answer_id": "Q3",
    }


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.relations = adapter.load_relation_templates(HERE / "relation_templates.json")
        cls.aliases = adapter.AliasIndex({})
        cls.formal_schema = adapter.read_json(
            HERE / "schema2.json"
        )

    def test_all_34_relation_templates_render(self) -> None:
        self.assertEqual(len(self.relations), 34)
        for relation in self.relations:
            rendered = adapter.render_claim(["Subject", relation, "Object"], self.relations)
            self.assertTrue(rendered.endswith("."), relation)
            self.assertNotIn("{", rendered, relation)

    def test_possessive_rule(self) -> None:
        self.assertEqual(adapter.possessive("James"), "James'")
        self.assertEqual(adapter.possessive("Ada"), "Ada's")

    def test_lcs_confidence(self) -> None:
        self.assertEqual(adapter.normalized_lcs("  ENTITY A ", "entity a"), 1.0)
        self.assertGreater(adapter.normalized_lcs("Entity A (film)", "Entity A"), 0.9)

    def test_candidate_contract_and_parent_graph(self) -> None:
        candidate = adapter.build_candidate(
            fixture_record(), 7, Path("fixture.json"), "0" * 64,
            self.aliases, self.relations,
        )
        self.assertEqual(adapter.validate_contract(candidate), [])
        self.assertEqual(adapter.validate_json_schema(candidate, self.formal_schema), [])
        self.assertEqual(candidate["claims"][0]["claim_kind"], "direct")
        self.assertEqual(candidate["claims"][0]["annotation_status"], "candidate")
        self.assertEqual(candidate["claim_source_links"][0]["validation_status"], "unreviewed")
        self.assertEqual(set(candidate["semantic_screening"]), {
            "method", "model", "reasoning_effort", "prompt_version", "rule_version",
            "screened_at", "requires_human_audit",
        })
        self.assertEqual(candidate["claims"][1]["parent_claim_ids"], [candidate["claims"][0]["claim_id"]])
        self.assertEqual(candidate["reasoning_graph"]["reasoning_hop_count"], 2)
        self.assertEqual(candidate["sources"][0]["entity_qid"], "Q1")
        self.assertEqual(candidate["schema_version"], "2.0")
        self.assertEqual(len(candidate["documents"]), 2)
        self.assertEqual(candidate["documents"][0]["context_index"], 0)
        self.assertEqual(
            candidate["documents"][0]["text"],
            "Entity A is connected to Entity B.",
        )
        self.assertTrue(candidate["documents"][0]["is_supporting_context"])
        self.assertEqual(candidate["sources"][0]["context_index"], 0)
        self.assertNotIn("document_id", candidate["sources"][0])
        self.assertEqual(
            candidate["sources"][0]["text"],
            candidate["documents"][0]["sentences"][0]["text"],
        )

    def test_comparison_edge_uses_full_claim_ids(self) -> None:
        candidate = adapter.build_candidate(
            fixture_record("bridge_comparison"), 0, Path("fixture.json"), "0" * 64,
            self.aliases, self.relations,
        )
        comparison = [edge for edge in candidate["reasoning_graph"]["edges"] if edge["relation"] == "comparison"]
        self.assertEqual(len(comparison), 1)
        self.assertIsNone(comparison[0]["target_node_id"])
        self.assertTrue(all(":claim:" in node for node in comparison[0]["source_node_ids"]))

    def test_hard_exclusion_on_count_mismatch(self) -> None:
        record = fixture_record()
        record["supporting_facts"] = record["supporting_facts"][:1]
        with self.assertRaises(adapter.AdapterError) as caught:
            adapter.build_candidate(record, 0, Path("fixture.json"), "0" * 64, self.aliases, self.relations)
        self.assertEqual(caught.exception.code, "sf_evidence_count_mismatch")

    def test_hard_exclusion_on_invalid_locator(self) -> None:
        record = fixture_record()
        record["supporting_facts"][0][1] = 99
        with self.assertRaises(adapter.AdapterError) as caught:
            adapter.build_candidate(record, 0, Path("fixture.json"), "0" * 64, self.aliases, self.relations)
        self.assertEqual(caught.exception.code, "invalid_locator")

    def test_cli_fixture_outputs_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "dev.json"
            aliases_path = root / "aliases.json"
            output = root / "out"
            input_path.write_text(json.dumps([fixture_record()], ensure_ascii=False), encoding="utf-8")
            aliases_path.write_text("", encoding="utf-8")
            argv = [
                "--input", str(input_path), "--aliases", str(aliases_path),
                "--output-dir", str(output), "--skip-hash-check",
            ]
            self.assertEqual(adapter.main(argv), 0)
            first = (output / "candidate_pool/compositional.jsonl").read_bytes()
            self.assertEqual(adapter.main(argv), 0)
            second = (output / "candidate_pool/compositional.jsonl").read_bytes()
            self.assertEqual(first, second)


    def test_document_text_uses_single_space_join(self) -> None:
        record = fixture_record()
        record["context"][0][1] = ["Entity A", "is connected to Entity B."]
        candidate = adapter.build_candidate(
            record, 0, Path("fixture.json"), "0" * 64,
            self.aliases, self.relations,
        )
        self.assertEqual(candidate["documents"][0]["text"], "Entity A is connected to Entity B.")
        self.assertEqual(
            [row["sentence_index"] for row in candidate["documents"][0]["sentences"]],
            [0, 1],
        )

    def test_ambiguous_supporting_title_is_rejected(self) -> None:
        record = fixture_record()
        record["context"].append(["Entity A", ["Another sentence."]])
        with self.assertRaises(adapter.AdapterError) as caught:
            adapter.build_candidate(
                record, 0, Path("fixture.json"), "0" * 64,
                self.aliases, self.relations,
            )
        self.assertEqual(caught.exception.code, "ambiguous_locator")

    def test_manifest_and_sample_dataset_fields_must_match(self) -> None:
        candidate = adapter.build_candidate(
            fixture_record(), 0, Path("fixture.json"), "0" * 64,
            self.aliases, self.relations,
        )
        candidate["dataset_manifest"]["dataset_name"] = "wrong-dataset"
        self.assertIn(
            "manifest/sample dataset_name values differ",
            adapter.validate_contract(candidate),
        )

    def test_inference_graph_cycle_is_rejected(self) -> None:
        candidate = adapter.build_candidate(
            fixture_record(), 0, Path("fixture.json"), "0" * 64,
            self.aliases, self.relations,
        )
        first_id, second_id = candidate["reasoning_graph"]["node_ids"]
        candidate["reasoning_graph"]["edges"].append({
            "source_node_ids": [second_id],
            "target_node_id": first_id,
            "relation": "inference",
        })
        self.assertIn(
            "reasoning graph contains an inference cycle",
            adapter.validate_contract(candidate),
        )

    def test_reasoning_hop_count_is_recomputed(self) -> None:
        candidate = adapter.build_candidate(
            fixture_record(), 0, Path("fixture.json"), "0" * 64,
            self.aliases, self.relations,
        )
        candidate["reasoning_graph"]["reasoning_hop_count"] = 1
        errors = adapter.validate_contract(candidate)
        self.assertTrue(any(error.startswith("reasoning_hop_count differs") for error in errors))

    def test_qualified_claims_require_accepted_links(self) -> None:
        candidate = adapter.build_candidate(
            fixture_record(), 0, Path("fixture.json"), "0" * 64,
            self.aliases, self.relations,
        )
        candidate["validation"]["status"] = "qualified"
        errors = adapter.validate_contract(candidate)
        self.assertEqual(
            sum(error.startswith("qualified claim has no accepted source link") for error in errors),
            len(candidate["claims"]),
        )
        for link in candidate["claim_source_links"]:
            link["validation_status"] = "accepted"
        self.assertFalse(any(
            error.startswith("qualified claim has no accepted source link")
            for error in adapter.validate_contract(candidate)
        ))


if __name__ == "__main__":
    unittest.main(verbosity=2)
