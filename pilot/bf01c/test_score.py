"""Original deterministic tests for BF-01C scoring; no inference or network.

Copyright (c) 2026 AnimaFoundry. MIT; see LICENSE-CODE.
"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from prepare_study import build_requests, build_tasks
from score import reference, score_record, score_study, strict_object, verify_saved_evidence
from envelope import validate_envelope

HERE = Path(__file__).resolve().parent


class ScoreControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = build_tasks()
        cls.requests = build_requests(cls.tasks, "qwen2.5:1.5b-instruct-q4_K_M")
        cls.by_task = {t["input_id"]: t for t in cls.tasks["tasks"]}
        cls.schemas = {c: json.loads((HERE / f"schema_{c}.json").read_text()) for c in ("no_evidence", "evidence")}
        cls.good_summary = {"status": "completed", "metadata_match": True,
                            "freeze_unchanged": True, "budget_ok": True, "usage_complete": True,
                            "output_tokens": 320, "initiated_calls": 32, "completed_calls": 32,
                            "initiated_request_ids": [r["request_id"] for r in cls.requests],
                            "completed_request_ids": [r["request_id"] for r in cls.requests],
                            "unattempted_request_ids": []}

    def record(self, request, content=None):
        task = self.by_task[request["input_id"]]
        if content is None:
            content = json.dumps(reference(task, request["contract"]))
        return {k: request[k] for k in ("request_id", "input_id", "arm", "mode", "contract")} | {
            "transport_status": "ok", "http_status": 200, "body_complete": True,
            "envelope": {"valid": bool(content.strip()), "delivery_complete": True, "content": content,
                         "eval_count": 10, "prompt_eval_count": 200}}

    def request(self, input_id="T01", arm="schema_evidence"):
        return next(r for r in self.requests if r["input_id"] == input_id and r["arm"] == arm)

    def score_one(self, request, record):
        return score_record(self.by_task[request["input_id"]], request, record, self.schemas)

    def test_manual_sources_and_balanced_prepared_schedule(self):
        self.assertEqual(len(self.tasks["tasks"]), 8)
        self.assertEqual(len(self.requests), 32)
        self.assertEqual(self.requests[0]["arm"], "schema_evidence")
        self.assertEqual(len({r["request_id"] for r in self.requests}), 32)
        for arm in {r["arm"] for r in self.requests}:
            self.assertEqual(sum(r["arm"] == arm for r in self.requests), 8)
            for position in range(4):
                self.assertEqual(sum(self.requests[i * 4 + position]["arm"] == arm for i in range(8)), 2)
        for task in self.tasks["tasks"]:
            for contract in ("no_evidence", "evidence"):
                pair = [r for r in self.requests if r["input_id"] == task["input_id"] and r["contract"] == contract]
                self.assertEqual(pair[0]["request_body"]["messages"], pair[1]["request_body"]["messages"])

    def test_complete_perfect_control_passes_gate(self):
        records = [self.record(r) for r in self.requests]
        report = score_study(self.tasks, self.requests, records, self.good_summary, self.schemas)
        self.assertEqual(report["overall"]["joint_correct"], 32)
        self.assertTrue(report["competence_gate"]["passed"])
        self.assertEqual(report["competence_gate"]["designated_unknown_absent_correct"], 4)
        self.assertEqual(len(report["direct_baseline"]), 16)

    def test_no_evidence_has_no_missing_citation_penalty(self):
        req = self.request(arm="raw_no_evidence")
        row = self.score_one(req, self.record(req))
        self.assertTrue(row["joint_correct"])
        self.assertFalse(row["binding_applicable"])
        self.assertIsNone(row["binding_correct"])

    def test_integral_float_is_format_only_not_state_error(self):
        req = self.request("T03", "schema_no_evidence")
        row = self.score_one(req, self.record(req, '{"state":"observed","value":11.0}'))
        self.assertTrue(row["strict_wire_json"])
        self.assertTrue(row["decoded_schema_valid"])
        self.assertFalse(row["strict_contract"])
        self.assertTrue(row["semantic_correct"])
        self.assertFalse(row["joint_correct"])
        self.assertTrue(row["pipelines"]["decoded_schema"]["accepted_format_only"])
        self.assertFalse(row["pipelines"]["decoded_schema"]["accepted_semantic_wrong"])

    def test_bool_cannot_be_numeric_zero(self):
        req = self.request(arm="raw_no_evidence")
        row = self.score_one(req, self.record(req, '{"state":"observed","value":false}'))
        self.assertFalse(row["semantic_correct"])
        self.assertFalse(row["strict_contract"])

    def test_zero_unknown_absent_confusions_are_semantic_errors(self):
        for task_id, text in [("T01", '{"state":"unknown","value":null}'),
                              ("T05", '{"state":"observed","value":0}'),
                              ("T07", '{"state":"unknown","value":null}')]:
            with self.subTest(task=task_id):
                req = self.request(task_id, "raw_no_evidence")
                row = self.score_one(req, self.record(req, text))
                self.assertTrue(row["strict_contract"])
                self.assertFalse(row["semantic_correct"])
                self.assertEqual(row["pipelines"]["strict_contract"]["outcome"], "accepted_wrong")
                self.assertEqual(row["pipelines"]["source_gate"]["outcome"], "rejected")

    def test_fences_are_not_repaired_and_semantics_are_unscorable(self):
        req = self.request(arm="raw_no_evidence")
        row = self.score_one(req, self.record(req, '```json\n{"state":"observed","value":0}\n```'))
        self.assertTrue(row["delivered"])
        self.assertIsNone(row["semantic_correct"])
        self.assertFalse(row["strict_wire_json"])
        self.assertEqual(row["pipelines"]["decoded_schema"]["outcome"], "rejected")

    def test_duplicate_members_are_schema_only_acceptance_not_scored_truth(self):
        req = self.request(arm="raw_no_evidence")
        row = self.score_one(req, self.record(req, '{"state":"observed","value":8,"value":0}'))
        self.assertTrue(row["decoded_schema_valid"])
        self.assertFalse(row["strict_wire_json"])
        self.assertIsNone(row["semantic_correct"])
        self.assertTrue(row["pipelines"]["decoded_schema"]["accepted_semantic_unscorable"])

    def test_complete_empty_reply_is_content_rejection(self):
        req = self.request()
        row = self.score_one(req, self.record(req, ""))
        self.assertTrue(row["delivered"])
        self.assertEqual(row["pipelines"]["source_gate"]["outcome"], "rejected")
        self.assertIsNone(row["semantic_correct"])

    def test_valid_json_from_incomplete_transport_is_unavailable(self):
        req = self.request()
        record = self.record(req)
        record["body_complete"] = False
        row = self.score_one(req, record)
        self.assertFalse(row["delivered"])
        self.assertEqual(row["pipelines"]["source_gate"]["outcome"], "unavailable")
        self.assertIsNone(row["semantic_correct"])

    def test_nonterminal_or_error_response_is_unavailable(self):
        req = self.request()
        for field in ("http", "envelope", "transport"):
            record = self.record(req)
            if field == "http":
                record["http_status"] = 400
            elif field == "envelope":
                record["envelope"]["delivery_complete"] = False
            else:
                record["transport_status"] = "error"
            self.assertFalse(self.score_one(req, record)["delivered"])

    def test_wrong_in_range_row_is_binding_not_state_error(self):
        req = self.request()
        obj = reference(self.by_task["T01"], "evidence")
        obj["evidence"]["row"] = 2  # Same numeric value, wrong source field.
        row = self.score_one(req, self.record(req, json.dumps(obj)))
        self.assertTrue(row["semantic_correct"])
        self.assertFalse(row["binding_correct"])
        self.assertTrue(row["strict_contract"])
        self.assertTrue(row["pipelines"]["strict_contract"]["accepted_binding_wrong"])
        self.assertEqual(row["pipelines"]["source_gate"]["outcome"], "rejected")

    def test_one_observed_failure_allowed_but_unknown_failure_stops_gate(self):
        for input_id, expected_pass in [("T01", True), ("T05", False)]:
            records = [self.record(r) for r in self.requests]
            for index, req in enumerate(self.requests):
                if req["input_id"] == input_id and req["arm"] == "schema_evidence":
                    records[index]["envelope"]["content"] = "{}"
            report = score_study(self.tasks, self.requests, records, self.good_summary, self.schemas)
            self.assertIs(report["competence_gate"]["passed"], expected_pass)
            self.assertEqual(report["competence_gate"]["designated_joint_correct"], 7)

    def test_incomplete_and_unproven_runs_never_pass(self):
        records = [self.record(r) for r in self.requests]
        shortened = score_study(self.tasks, self.requests, records[:-1], self.good_summary, self.schemas)
        self.assertFalse(shortened["competence_gate"]["passed"])
        self.assertEqual(len(shortened["unattempted_ids"]), 1)
        for flag in ("metadata_match", "freeze_unchanged", "budget_ok", "usage_complete"):
            summary = dict(self.good_summary)
            summary.pop(flag)
            report = score_study(self.tasks, self.requests, records, summary, self.schemas)
            self.assertFalse(report["competence_gate"]["passed"])

    def test_inconsistent_usage_and_summary_inventory_fail_gate(self):
        records = [self.record(r) for r in self.requests]
        for key, value in [("output_tokens", 319), ("initiated_calls", 31),
                           ("completed_request_ids", []), ("unattempted_request_ids", ["invented"])]:
            summary = copy.deepcopy(self.good_summary)
            summary[key] = value
            self.assertFalse(score_study(self.tasks, self.requests, records, summary, self.schemas)["competence_gate"]["passed"])
        records[0]["envelope"]["eval_count"] = None
        self.assertFalse(score_study(self.tasks, self.requests, records, self.good_summary, self.schemas)["competence_gate"]["passed"])

    def test_duplicate_unknown_and_misidentified_records_fail_closed(self):
        good = self.record(self.requests[0])
        with self.assertRaises(ValueError):
            score_study(self.tasks, self.requests, [good, good], self.good_summary, self.schemas)
        wrong = copy.deepcopy(good)
        wrong["request_id"] = "not-scheduled"
        with self.assertRaises(ValueError):
            score_study(self.tasks, self.requests, [wrong], self.good_summary, self.schemas)
        wrong = copy.deepcopy(good)
        wrong["arm"] = "raw_evidence"
        with self.assertRaises(ValueError):
            self.score_one(self.requests[0], wrong)

    def test_unavailable_and_rejected_preserve_zero_coverage_denominator(self):
        records = [self.record(r, "[]") for r in self.requests[:2]]
        records[1]["body_complete"] = False
        report = score_study(self.tasks, self.requests, records, self.good_summary, self.schemas)
        counts = report["overall"]["pipelines"]["source_gate"]
        self.assertEqual(counts["rejected"], 1)
        self.assertEqual(counts["unavailable"], 1)
        self.assertEqual(counts["coverage"], 0)
        self.assertIsNone(counts["correct_among_accepted"])

    def test_strict_object_rejects_bad_unicode_nonfinite_and_nonobjects(self):
        for content in ('{"state":"observed","value":NaN}',
                        '{"state":"observed","value":1e999}',
                        '{"value":"\\ud800"}', '\ufeff{}', '[]', 'null', ''):
            self.assertIsNone(strict_object(content), content)

    def test_duplicate_task_identity_and_repeated_arm_schedule_rejected(self):
        tasks = copy.deepcopy(self.tasks)
        tasks["tasks"].append(copy.deepcopy(tasks["tasks"][0]))
        with self.assertRaises(ValueError):
            score_study(tasks, self.requests, [], {}, self.schemas)
        requests = copy.deepcopy(self.requests)
        requests[1]["arm"] = requests[0]["arm"]
        with self.assertRaises(ValueError):
            score_study(self.tasks, requests, [], {}, self.schemas)

    def test_saved_evidence_requires_raw_bytes_journal_and_envelope_agreement(self):
        req = self.requests[0]
        ident = req["request_id"]
        raw_request = json.dumps(req["request_body"], ensure_ascii=False, separators=(",", ":")).encode()
        raw_response = json.dumps({"model": req["request_body"]["model"], "done": True, "done_reason": "stop",
                                   "message": {"role": "assistant", "content": "{}"},
                                   "eval_count": 2, "prompt_eval_count": 40}).encode()
        entry = {k: req[k] for k in ("request_id", "input_id", "arm", "mode", "contract")}
        entry.update(started_utc="2026-10-26T00:00:00Z", request_body_path=f"run/requests/{ident}.json",
                     request_sha256=hashlib.sha256(raw_request).hexdigest(), timeout_seconds=30)
        record = dict(entry, response_body_path=f"run/responses/{ident}.bin",
                      response_sha256=hashlib.sha256(raw_response).hexdigest(), duration_seconds=1,
                      sent=True, dispatch_timeout_seconds=30,
                      http_status=200, body_complete=True, transport_status="ok",
                      envelope=validate_envelope(200, raw_response, req["request_body"]["model"]))
        temporary_root = (HERE / "build").resolve()
        if not temporary_root.is_relative_to(HERE.resolve()):
            raise ValueError("test_temporary_root_outside_package")
        temporary_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary_root) as temporary:
            run = Path(temporary)
            if not run.resolve().is_relative_to(temporary_root):
                raise ValueError("test_temporary_directory_outside_root")
            (run / "requests").mkdir()
            (run / "responses").mkdir()
            (run / "requests" / f"{ident}.json").write_bytes(raw_request)
            path = run / "responses" / f"{ident}.bin"
            path.write_bytes(raw_response)
            (run / "initiation.jsonl").write_text(json.dumps(entry) + "\n")
            self.assertEqual(verify_saved_evidence(run, self.requests, [record])["raw_request_response_pairs"], 1)
            record["dispatch_timeout_seconds"] = 0.5
            with self.assertRaisesRegex(ValueError, "saved_envelope_replay_mismatch"):
                verify_saved_evidence(run, self.requests, [record])
            record["envelope"].update(valid=False, delivery_complete=False, reason="per_call_budget")
            self.assertEqual(verify_saved_evidence(run, self.requests, [record])["raw_request_response_pairs"], 1)
            record["dispatch_timeout_seconds"] = 30
            record["envelope"] = validate_envelope(200, raw_response, req["request_body"]["model"])
            record["envelope"]["content"] = '{"changed":true}'
            with self.assertRaises(ValueError):
                verify_saved_evidence(run, self.requests, [record])
            record["envelope"] = validate_envelope(200, raw_response, req["request_body"]["model"])
            path.write_bytes(raw_response + b" ")
            with self.assertRaises(ValueError):
                verify_saved_evidence(run, self.requests, [record])
            path.write_bytes(raw_response)
            (run / "initiation.jsonl").write_text("")
            with self.assertRaises(ValueError):
                verify_saved_evidence(run, self.requests, [record])


if __name__ == "__main__":
    unittest.main()
