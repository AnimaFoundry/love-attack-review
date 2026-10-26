"""Independent original development controls for the BF-01C byte contracts.

Copyright (c) 2026 AnimaFoundry. SPDX-License-Identifier: MIT.
See LICENSE-CODE. These are authored controls, not model outputs or holdouts.
Expected state/value/row decisions are specified independently of contracts.py;
hashlib is used only to calculate exact-byte identity metadata.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

from contracts import decode_utf8, derive_response, evaluate_response, validate_response


CONTRACTS = ("no_evidence", "evidence")
HERE = Path(__file__).resolve().parent


def wire(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class SourceControl:
    control_id: str
    source: bytes
    target: str
    document_id: str
    revision: int
    state: str
    value: int | None
    row: int | None

    def expected(self, contract):
        result = {"state": self.state, "value": self.value}
        if contract == "evidence":
            result["evidence"] = {
                "document_id": self.document_id,
                "revision": self.revision,
                "sha256": hashlib.sha256(self.source).hexdigest(),
                "key": self.target,
                "row": self.row,
            }
        return result


SOURCES = (
    SourceControl("N01", b'{"document_id":"meter-north","revision":2,"complete":true,"entries":[{"key":"decoy","value":8},{"key":"count","value":0},{"key":"also-zero","value":0}]}',
                  "count", "meter-north", 2, "observed", 0, 1),
    SourceControl("N02", b'{"document_id":"crate-ledger","revision":4,"complete":true,"entries":[{"key":"units","value":7}]}',
                  "units", "crate-ledger", 4, "observed", 7, 0),
    SourceControl("N03", b'{"document_id":"pending-ledger","revision":6,"complete":true,"entries":[{"key":"units","value":null}]}',
                  "units", "pending-ledger", 6, "unknown", None, 0),
    SourceControl("N04", b'{"document_id":"partial-fields-complete-record","revision":3,"complete":true,"entries":[{"key":"recorded","value":1}]}',
                  "pending", "partial-fields-complete-record", 3, "absent", None, None),
    SourceControl("N05", b'{"document_id":"empty-ledger","revision":1,"complete":true,"entries":[]}',
                  "units", "empty-ledger", 1, "absent", None, None),
    SourceControl("N06", b'{"document_id":"signed-lower","revision":8,"complete":true,"entries":[{"key":"delta","value":-2147483648}]}',
                  "delta", "signed-lower", 8, "observed", -(2 ** 31), 0),
    SourceControl("N07", b'{"document_id":"signed-upper","revision":9,"complete":true,"entries":[{"key":"unmeasured","value":null},{"key":"delta","value":2147483647}]}',
                  "delta", "signed-upper", 9, "observed", 2 ** 31 - 1, 1),
    SourceControl("N08", '{"document_id":"unicode-ledger","revision":5,"complete":true,"entries":[{"key":"é","value":7},{"key":"é","value":3}]}'.encode("utf-8"),
                  "e\u0301", "unicode-ledger", 5, "observed", 3, 1),
)


@dataclass(frozen=True)
class GateControl:
    control_id: str
    source: bytes
    target: object
    response: bytes
    contract: str
    source_valid: bool
    structural_accept: bool
    source_accept: bool
    reason: str


def gate_controls():
    """Construct mutations with manually declared expected decisions."""
    cases = []

    def add(name, s, contract, response, structural, accepted=False,
            reason="invalid_response_structure", source=None, target=None,
            source_valid=True):
        cases.append(GateControl(name, s.source if source is None else source,
                                 s.target if target is None else target,
                                 response if isinstance(response, bytes) else wire(response),
                                 contract, source_valid, structural, accepted, reason))

    for s in SOURCES:
        for contract in CONTRACTS:
            add(f"{s.control_id}-correct-{contract}", s, contract, s.expected(contract),
                True, True, "source_consistent")

    semantic_mutations = (
        (0, "wrong-integer", "observed", 8),
        (0, "zero-as-unknown", "unknown", None),
        (2, "unknown-as-zero", "observed", 0),
        (2, "unknown-as-absent", "absent", None),
        (3, "absent-as-zero", "observed", 0),
        (3, "absent-as-unknown", "unknown", None),
    )
    for index, name, state, value in semantic_mutations:
        s = SOURCES[index]
        add(f"semantic-{name}", s, "no_evidence", {"state": state, "value": value},
            True, reason="source_semantics_mismatch")

    s = SOURCES[0]
    for name, field, value, reason in (
        ("document", "document_id", "other-ledger", "source_identity_mismatch"),
        ("revision", "revision", 3, "source_identity_mismatch"),
        ("hash", "sha256", "f" * 64, "source_identity_mismatch"),
        ("target", "key", "also-zero", "target_key_mismatch"),
        ("same-value-row", "row", 2, "evidence_row_mismatch"),
        ("possible-row63", "row", 63, "evidence_row_mismatch"),
    ):
        value_object = s.expected("evidence")
        value_object["evidence"][field] = value
        add(f"binding-{name}", s, "evidence", value_object, True, reason=reason)
    wrong_value = s.expected("evidence")
    wrong_value["value"] = 8
    add("evidence-wrong-value", s, "evidence", wrong_value, True,
        reason="source_semantics_mismatch")
    for i, name, row in ((0, "observed-null-row", None), (2, "unknown-null-row", None),
                         (3, "absent-integer-row", 0), (0, "row64", 64),
                         (0, "row-negative", -1), (0, "row-bool", True),
                         (0, "row-float", 1.0)):
        selected = SOURCES[i]
        value_object = selected.expected("evidence")
        value_object["evidence"]["row"] = row
        add(f"shape-{name}", selected, "evidence", value_object, False)

    for contract in CONTRACTS:
        base = s.expected(contract)
        for name, field, value in (("bool-value", "value", False),
                                  ("float-value", "value", 0.0),
                                  ("upper-overflow", "value", 2 ** 31),
                                  ("lower-overflow", "value", -(2 ** 31)-1),
                                  ("null-observed", "value", None),
                                  ("invalid-state", "state", "estimated")):
            mutated = copy.deepcopy(base)
            mutated[field] = value
            add(f"shape-{contract}-{name}", s, contract, mutated, False)
        for name, response in (
            ("empty", b""), ("array", b"[]"), ("null", b"null"),
            ("fenced", b"```json\n" + wire(base) + b"\n```"),
            ("suffix", wire(base) + b" explanation"),
            ("multiple", wire(base) + wire(base)),
            ("invalid-utf8", b"\xff"), ("bom", b"\xef\xbb\xbf" + wire(base)),
            ("oversized", wire(base) + b" " * (16_385-len(wire(base)))),
            ("duplicate-state", wire(base).replace(b'{"state":', b'{"state":"absent","state":', 1)),
        ):
            add(f"wire-{contract}-{name}", s, contract, response, False)
        extra = copy.deepcopy(base)
        extra["explanation"] = "synthetic extra member"
        add(f"shape-{contract}-extra", s, contract, extra, False)
        missing = copy.deepcopy(base)
        del missing["value"]
        add(f"shape-{contract}-missing", s, contract, missing, False)
        spaced = b" \r\n\t" + wire(base) + b" \n"
        add(f"wire-{contract}-legal-whitespace", s, contract, spaced,
            True, True, "source_consistent")
        exact_size = wire(base) + b" " * (16_384-len(wire(base)))
        add(f"wire-{contract}-exact-byte-limit", s, contract, exact_size,
            True, True, "source_consistent")

    add("no-evidence-rejects-added-evidence", s, "no_evidence", s.expected("evidence"), False)
    add("evidence-requires-evidence", s, "evidence", s.expected("no_evidence"), False)
    for name, field, value in (("empty-id", "document_id", ""),
                              ("long-name", "key", "q" * 81),
                              ("revision-zero", "revision", 0),
                              ("revision-float", "revision", 2.0),
                              ("revision-bool", "revision", True),
                              ("uppercase-hash", "sha256", "A" * 64),
                              ("short-hash", "sha256", "a" * 63),
                              ("hash-newline", "sha256", "a" * 64 + "\n")):
        obj = s.expected("evidence")
        obj["evidence"][field] = value
        add(f"shape-evidence-{name}", s, "evidence", obj, False)
    add("wire-escaped-surrogate", s, "evidence",
        wire(s.expected("evidence")).replace(b'"meter-north"', b'"\\ud800"'), False)
    add("wire-duplicate-nested-member", s, "evidence",
        wire(s.expected("evidence")).replace(b'"row":1', b'"row":1,"row":1'), False)
    for spelling in (b"NaN", b"Infinity", b"-Infinity", b"1e999", b"0e0"):
        add("wire-number-" + spelling.decode(), s, "no_evidence",
            b'{"state":"observed","value":' + spelling + b'}', False)

    # Raw byte identity is independent of semantic JSON equivalence.
    changed_bytes = s.source + b"\r\n"
    add("stale-after-whitespace", s, "evidence", s.expected("evidence"), True,
        reason="source_identity_mismatch", source=changed_bytes)
    new_hash_answer = s.expected("evidence")
    new_hash_answer["evidence"]["sha256"] = hashlib.sha256(changed_bytes).hexdigest()
    add("current-after-whitespace", s, "evidence", new_hash_answer, True, True,
        "source_consistent", source=changed_bytes)
    add("no-evidence-ignores-byte-only-change", s, "no_evidence", s.expected("no_evidence"),
        True, True, "source_consistent", source=changed_bytes)
    changed_revision = s.source.replace(b'"revision":2', b'"revision":3')
    add("stale-after-revision-change", s, "evidence", s.expected("evidence"), True,
        reason="source_identity_mismatch", source=changed_revision)

    invalid_sources = (
        ("utf8", b"\xff"), ("bom", b"\xef\xbb\xbf" + s.source),
        ("incomplete", s.source.replace(b'"complete":true', b'"complete":false')),
        ("complete-number", s.source.replace(b'"complete":true', b'"complete":1')),
        ("duplicate-member", s.source.replace(b'"revision":2', b'"revision":2,"revision":2')),
        ("duplicate-key", s.source.replace(b'"also-zero"', b'"count"')),
        ("value-float", s.source.replace(b'"value":8', b'"value":8.0')),
        ("revision-bool", s.source.replace(b'"revision":2', b'"revision":true')),
        ("unknown-member", s.source.replace(b'"entries":', b'"extra":1,"entries":')),
        ("byte-limit", s.source + b" " * (16_385-len(s.source))),
    )
    for name, bad_source in invalid_sources:
        add("source-invalid-" + name, s, "no_evidence", s.expected("no_evidence"),
            True, reason="invalid_source", source=bad_source, source_valid=False)
    for target in ("", 7, False, "t" * 81, "\ud800"):
        add(f"target-invalid-{len(cases)}", s, "no_evidence", s.expected("no_evidence"),
            True, reason="invalid_target", target=target)
    add("source-invalid-before-target-and-response", s, "evidence", b"not-json", False,
        reason="invalid_source", source=b"not-json", target="", source_valid=False)
    return tuple(cases)


GATE_CONTROLS = gate_controls()


class ByteContractControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validators = {}
        for contract in CONTRACTS:
            schema = json.loads((HERE / f"schema_{contract}.json").read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            cls.validators[contract] = Draft202012Validator(schema)

    def test_inventory_has_distinct_authored_controls(self):
        self.assertEqual(len(SOURCES), 8)
        self.assertEqual(len({s.control_id for s in SOURCES}), 8)
        self.assertEqual(len({c.control_id for c in GATE_CONTROLS}), len(GATE_CONTROLS))
        self.assertGreater(len(GATE_CONTROLS), 100)

    def test_direct_lookup_matches_manual_answers_in_both_contracts(self):
        for s in SOURCES:
            for contract in CONTRACTS:
                with self.subTest(source=s.control_id, contract=contract):
                    self.assertEqual(derive_response(s.source, s.target, contract), s.expected(contract))

    def test_named_gate_decisions_and_diagnostics(self):
        for case in GATE_CONTROLS:
            with self.subTest(case=case.control_id):
                result = evaluate_response(case.source, case.target, case.response, case.contract)
                self.assertEqual(result, {
                    "source_valid": case.source_valid,
                    "structural_accept": case.structural_accept,
                    "source_accept": case.source_accept,
                    "reason": case.reason,
                })

    def test_structural_validation_is_independent_of_source(self):
        for case in GATE_CONTROLS:
            with self.subTest(case=case.control_id):
                self.assertIs(validate_response(case.response, case.contract), case.structural_accept)

    def test_byte_decoder_preserves_exact_bytes_and_whitespace(self):
        for data in (b"", b" \r\n\t", b"x" * 16_384, "é".encode() * 8_192,
                     'é / é'.encode("utf-8")):
            with self.subTest(size=len(data)):
                self.assertEqual(decode_utf8(data).encode("utf-8"), data)

    def test_byte_decoder_rejects_noisy_or_wrong_type_transport(self):
        for data in ("{}", bytearray(b"{}"), memoryview(b"{}"), None, 0,
                     b"\xef\xbb\xbf{}", b"\xff", b"\xc0\xaf", b"\xe2\x82",
                     b"\x80", b"\xed\xa0\x80", b"x" * 16_385,
                     "é".encode() * 8_193):
            with self.subTest(type=type(data).__name__, sample=repr(data)[:30]):
                with self.assertRaises(ValueError):
                    decode_utf8(data)

    def test_invalid_contract_cannot_fall_back_to_another_mode(self):
        s = SOURCES[0]
        for contract in ("", "automatic", None, [], 1):
            with self.subTest(contract=contract):
                with self.assertRaises(ValueError):
                    derive_response(s.source, s.target, contract)
                with self.assertRaises(ValueError):
                    validate_response(wire(s.expected("no_evidence")), contract)
                with self.assertRaises(ValueError):
                    evaluate_response(s.source, s.target, b"{}", contract)

    def test_invalid_source_or_target_never_yields_a_direct_answer(self):
        for case in GATE_CONTROLS:
            if case.reason not in {"invalid_source", "invalid_target"}:
                continue
            with self.subTest(case=case.control_id):
                with self.assertRaises(ValueError):
                    derive_response(case.source, case.target, case.contract)

    def test_64_rows_are_valid_but_65_are_rejected(self):
        for count in (64, 65):
            source = wire({"document_id": "row-boundary", "revision": 1, "complete": True,
                           "entries": [{"key": f"item-{i}", "value": i} for i in range(count)]})
            if count == 64:
                self.assertEqual(derive_response(source, "item-63", "no_evidence"),
                                 {"state": "observed", "value": 63})
                self.assertEqual(derive_response(source, "item-63", "evidence")["evidence"]["row"], 63)
            else:
                with self.assertRaises(ValueError):
                    derive_response(source, "item-63", "no_evidence")

    def test_source_byte_limit_and_exact_hash(self):
        s = SOURCES[0]
        source = s.source + b" " * (16_384-len(s.source))
        answer = s.expected("evidence")
        answer["evidence"]["sha256"] = hashlib.sha256(source).hexdigest()
        self.assertEqual(derive_response(source, s.target, "evidence"), answer)
        with self.assertRaises(ValueError):
            derive_response(source + b" ", s.target, "evidence")

    def test_names_and_unicode_are_exact_not_normalized(self):
        s = SOURCES[7]
        self.assertEqual(derive_response(s.source, "é", "no_evidence"),
                         {"state": "observed", "value": 7})
        self.assertEqual(derive_response(s.source, "e\u0301", "no_evidence"),
                         {"state": "observed", "value": 3})
        self.assertEqual(derive_response(s.source, " É ", "no_evidence"),
                         {"state": "absent", "value": None})
        name = "界" * 80
        source = wire({"document_id": name, "revision": 1, "complete": True,
                       "entries": [{"key": name, "value": 0}]})
        self.assertEqual(derive_response(source, name, "no_evidence"),
                         {"state": "observed", "value": 0})

    def test_schema_accepts_correct_objects_and_rejects_state_row_conflicts(self):
        for s in SOURCES:
            for contract in CONTRACTS:
                self.assertTrue(self.validators[contract].is_valid(s.expected(contract)))
        for index, row in ((0, None), (2, None), (3, 0), (0, 64)):
            obj = SOURCES[index].expected("evidence")
            obj["evidence"]["row"] = row
            self.assertFalse(self.validators["evidence"].is_valid(obj))

    def test_schema_numeric_values_are_not_the_strict_wire_integer_rule(self):
        for contract in CONTRACTS:
            obj = SOURCES[0].expected(contract)
            obj["value"] = 0.0
            self.assertTrue(self.validators[contract].is_valid(obj))
            self.assertFalse(validate_response(wire(obj), contract))
        obj = SOURCES[0].expected("evidence")
        obj["evidence"]["row"] = 1.0
        obj["evidence"]["revision"] = 2.0
        self.assertTrue(self.validators["evidence"].is_valid(obj))
        self.assertFalse(validate_response(wire(obj), "evidence"))

    def test_schema_on_last_wins_json_cannot_detect_duplicate_members(self):
        raw = b'{"state":"absent","state":"observed","value":0}'
        decoded = json.loads(raw)
        self.assertTrue(self.validators["no_evidence"].is_valid(decoded))
        self.assertFalse(validate_response(raw, "no_evidence"))

    def test_schema_cannot_establish_the_source_value_or_same_value_row(self):
        for contract in CONTRACTS:
            wrong = SOURCES[0].expected(contract)
            wrong["value"] = 8
            self.assertTrue(self.validators[contract].is_valid(wrong))
            self.assertFalse(evaluate_response(SOURCES[0].source, "count", wire(wrong), contract)["source_accept"])
        wrong_row = SOURCES[0].expected("evidence")
        wrong_row["evidence"]["row"] = 2
        self.assertTrue(self.validators["evidence"].is_valid(wrong_row))
        self.assertFalse(evaluate_response(SOURCES[0].source, "count", wire(wrong_row), "evidence")["source_accept"])

    def test_results_are_fresh_and_no_network_is_used(self):
        s = SOURCES[0]
        changed = derive_response(s.source, s.target, "evidence")
        changed["evidence"]["row"] = 0
        self.assertEqual(derive_response(s.source, s.target, "evidence"), s.expected("evidence"))
        with patch("socket.socket", side_effect=AssertionError("offline controls forbid sockets")), \
                patch("socket.create_connection", side_effect=AssertionError("offline controls forbid connections")), \
                patch("socket.getaddrinfo", side_effect=AssertionError("offline controls forbid DNS")):
            for case in GATE_CONTROLS:
                evaluate_response(case.source, case.target, case.response, case.contract)


if __name__ == "__main__":
    unittest.main()
