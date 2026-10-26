"""Independent synthetic controls for a source-bound evidence gate.

Copyright (c) 2026 AnimaFoundry. MIT; see LICENSE-CODE.
No model inference, network, prior pilot input, or private record is used.
The fixture expectations were authored independently of evidence_gate.py.
"""

import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from evidence_gate import evaluate_gate, parse_source, validate_structure


FIXTURE_PATH = Path(__file__).with_name("fixtures.json")


class EvidenceGateControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.sources = {s["source_id"]: s for s in cls.fixtures["sources"]}
        cls.cases = cls.fixtures["cases"]

    def inputs(self, case):
        source = self.sources[case["source_id"]]
        return (case.get("source_text_override", source["source_text"]),
                case.get("target_key_override", source["target_key"]),
                case["response_text"])

    def test_fixture_inventory_preserves_unique_control_ids(self):
        self.assertEqual(self.fixtures["status"], "CONTROL_DEVELOPMENT")
        self.assertEqual(self.fixtures["source_count"], 8)
        self.assertEqual(len(self.sources), 8)
        self.assertEqual(self.fixtures["case_count"], 110)
        self.assertEqual(len(self.cases), 110)
        self.assertEqual(len({c["case_id"] for c in self.cases}), 110)
        for case in self.cases:
            self.assertIn(case["source_id"], self.sources)
            self.assertEqual(set(case["expected"]),
                             {"source_valid", "structural_accept", "source_accept"})
            self.assertTrue(all(type(v) is bool for v in case["expected"].values()))

    def test_eight_manually_authored_reference_objects(self):
        for source in self.sources.values():
            with self.subTest(source=source["source_id"]):
                self.assertEqual(parse_source(source["source_text"], source["target_key"]),
                                 source["expected_output"])

    def test_reference_hashes_bind_exact_utf8_bytes(self):
        for source in self.sources.values():
            with self.subTest(source=source["source_id"]):
                expected_hash = hashlib.sha256(source["source_text"].encode("utf-8")).hexdigest()
                self.assertEqual(source["expected_output"]["evidence"]["sha256"], expected_hash)

    def test_110_author_defined_gate_decisions(self):
        for case in self.cases:
            with self.subTest(case=case["case_id"]):
                source, target, response = self.inputs(case)
                actual = evaluate_gate(source, target, response)
                self.assertEqual(set(actual),
                                 {"source_valid", "structural_accept", "source_accept", "reason"})
                for name, expected in case["expected"].items():
                    self.assertIs(actual[name], expected, name)
                self.assertIsInstance(actual["reason"], str)
                self.assertTrue(actual["reason"])
                if "expected_reason" in case:
                    self.assertEqual(actual["reason"], case["expected_reason"])
                self.assertFalse(actual["source_accept"] and
                                 not (actual["source_valid"] and actual["structural_accept"]))

    def test_structural_decisions_use_response_only(self):
        for case in self.cases:
            with self.subTest(case=case["case_id"]):
                self.assertIs(validate_structure(case["response_text"]),
                              case["expected"]["structural_accept"])

    def test_all_accepted_controls_match_manually_specified_output(self):
        for case in self.cases:
            if not case["expected"]["source_accept"]:
                continue
            with self.subTest(case=case["case_id"]):
                source, target, response = self.inputs(case)
                self.assertEqual(parse_source(source, target), json.loads(response))

    def test_invalid_sources_and_targets_raise_instead_of_inventing_answers(self):
        for case in self.cases:
            if case.get("expected_reason") not in {"invalid_source", "invalid_target"}:
                continue
            with self.subTest(case=case["case_id"]):
                source, target, _ = self.inputs(case)
                with self.assertRaises(ValueError):
                    parse_source(source, target)

    def test_structure_cannot_establish_source_truth(self):
        source = self.sources["S01"]
        correct = json.dumps(source["expected_output"])
        wrong = copy.deepcopy(source["expected_output"])
        wrong["value"] = 17  # Existing decoy value; same target and evidence pointer.
        wrong_text = json.dumps(wrong)
        self.assertTrue(validate_structure(correct))
        self.assertTrue(validate_structure(wrong_text))
        self.assertTrue(evaluate_gate(source["source_text"], source["target_key"], correct)["source_accept"])
        self.assertFalse(evaluate_gate(source["source_text"], source["target_key"], wrong_text)["source_accept"])

    def test_parse_results_do_not_share_mutable_reference_state(self):
        source = self.sources["S01"]
        changed = parse_source(source["source_text"], source["target_key"])
        changed["value"] = 123
        changed["evidence"]["row"] = 0
        self.assertEqual(parse_source(source["source_text"], source["target_key"]),
                         source["expected_output"])

    def test_controls_perform_no_network_calls(self):
        with patch("socket.socket", side_effect=AssertionError("Network forbidden in controls")) as socket_call, \
                patch("socket.create_connection", side_effect=AssertionError("Network forbidden in controls")) as connection_call:
            for case in self.cases:
                evaluate_gate(*self.inputs(case))
            socket_call.assert_not_called()
            connection_call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
