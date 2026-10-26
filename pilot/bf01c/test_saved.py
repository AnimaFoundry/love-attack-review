"""Independent retained-evidence corruption controls. MIT; see LICENSE-CODE.

All replies and metadata here are synthetic saved fixtures. No runner or model
is invoked. Manually authored study answer keys only construct these test replies.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import freeze
import run_local
from envelope import validate_envelope
from score import reference, score_study
from verify_saved import canonical, verify_run

PILOT = Path(__file__).resolve().parent


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class SavedEvidenceControls(unittest.TestCase):
    def setUp(self):
        parent = PILOT.parents[1] / "build" / "bf01c-saved-tests"
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent, prefix="saved-")
        self.root = Path(self.temp.name)
        self.assertTrue(self.root.resolve().is_relative_to(parent.resolve()))
        self.addCleanup(self.temp.cleanup)
        for name in run_local.REQUIRED_FROZEN:
            source = PILOT / name
            (self.root / name).write_bytes(source.read_bytes() if source.is_file()
                                          else b"explicit offline unit fixture placeholder\n")
        self.config = self.read("config.json")
        self.requests = json.loads((self.root / "requests.json").read_text(encoding="utf-8"))
        self.tasks = self.read("tasks.json")
        self.by_input = {task["input_id"]: task for task in self.tasks["tasks"]}
        self.schemas = {c: self.read(f"schema_{c}.json") for c in ("no_evidence", "evidence")}
        freeze.create_freeze(self.root, sorted(run_local.REQUIRED_FROZEN))
        self.freeze_sha = digest((self.root / "FREEZE.json").read_bytes())
        self.write("RUN_GUARD.json", {"study_id": "BF01C", "freeze_sha256": self.freeze_sha,
                                      "created_utc": "2026-10-26T12:00:00Z", "rule": "Synthetic unit guard"})
        (self.root / "run/requests").mkdir(parents=True)
        (self.root / "run/responses").mkdir()
        self.write("run/metadata_before.json", self.config["expected_metadata"])
        self.write("run/metadata_after.json", self.config["expected_metadata"])

    def write(self, path, value):
        (self.root / path).write_bytes(canonical(value))

    def read(self, path):
        return json.loads((self.root / path).read_text(encoding="utf-8"))

    def write_rows(self, path, values):
        (self.root / path).write_bytes(b"".join(canonical(value) + b"\n" for value in values))

    def make_run(self, stopped=False):
        self.journal, self.records = [], []
        selected = self.requests[:1] if stopped else self.requests
        for request in selected:
            rid = request["request_id"]
            req_path, res_path = f"run/requests/{rid}.json", f"run/responses/{rid}.bin"
            request_raw = canonical(request["request_body"])
            (self.root / req_path).write_bytes(request_raw)
            answer = reference(self.by_input[request["input_id"]], request["contract"])
            response_raw = canonical({"model": self.config["model"], "done": True, "done_reason": "stop",
                "message": {"role": "assistant", "content": canonical(answer).decode("utf-8")},
                "eval_count": 3, "prompt_eval_count": 40})
            (self.root / res_path).write_bytes(response_raw)
            entry = {key: request[key] for key in ("request_id", "input_id", "arm", "mode", "contract")}
            entry.update(started_utc="2026-10-26T12:00:00Z", request_body_path=req_path,
                         request_sha256=digest(request_raw), timeout_seconds=30)
            self.journal.append(copy.deepcopy(entry))
            delivered = validate_envelope(200, response_raw, self.config["model"], http_complete=not stopped)
            entry.update(finished_utc="2026-10-26T12:00:01Z", duration_seconds=0.1,
                         sent=True, dispatch_timeout_seconds=30,
                         transport_status="incomplete" if stopped else "ok", http_status=200,
                         body_complete=not stopped, envelope=delivered, error=None,
                         response_body_path=res_path, response_sha256=digest(response_raw))
            self.records.append(entry)
        ids = [r["request_id"] for r in selected]
        self.summary = {
            "status": "stopped" if stopped else "completed", "initiated_calls": len(ids),
            "completed_calls": 0 if stopped else len(ids), "initiated_request_ids": ids,
            "completed_request_ids": [] if stopped else ids,
            "unattempted_request_ids": [r["request_id"] for r in self.requests[len(ids):]],
            "output_tokens": 0 if stopped else len(ids) * 3, "usage_complete": not stopped,
            "metadata_match": True, "freeze_unchanged": True, "budget_ok": not stopped,
            "inference_wall_seconds": len(ids) * 0.1,
            "stop_reason": "incomplete_http" if stopped else None,
            "finished_utc": "2026-10-26T12:00:04Z", "freeze_sha256": self.freeze_sha,
            "external_api_cost_usd": 0, "model": self.config["model"], "limits": self.config["limits"],
        }
        self.persist()

    def persist(self):
        self.write_rows("run/initiation.jsonl", self.journal)
        self.write_rows("run/records.jsonl", self.records)
        self.write("run/summary.json", self.summary)

    def save_score(self):
        report = score_study(self.tasks, self.requests, self.records, self.summary, self.schemas)
        report["saved_evidence_verification"] = {
            "initiations": len(self.journal), "raw_request_response_pairs": len(self.records),
            "envelope_replay": "MATCHED_RETAINED_BYTES", "authenticity_claim": False,
        }
        self.write("run/score.json", report)

    def test_valid_complete_mock_replays_raw_evidence_and_score(self):
        self.make_run()
        self.save_score()
        result = verify_run(self.root, check_score=True)
        self.assertEqual(result["status"], "VERIFIED_COMPLETE")
        self.assertEqual(result["raw_envelopes_rederived"], 32)
        self.assertEqual(result["known_output_tokens"], 96)
        self.assertTrue(result["score"]["competence_gate"]["passed"])

    def test_consistent_stopped_prefix_is_auditable_without_gate_pass(self):
        self.make_run(stopped=True)
        self.save_score()
        result = verify_run(self.root, check_score=True)
        self.assertEqual(result["status"], "VERIFIED_STOPPED_PREFIX")
        self.assertEqual(len(result["unattempted_request_ids"]), 31)
        self.assertFalse(result["score"]["competence_gate"]["passed"])

    def test_per_call_overrun_requires_the_documented_envelope_override(self):
        self.make_run(stopped=True)
        row = self.records[0]
        raw = (self.root / row["response_body_path"]).read_bytes()
        derived = validate_envelope(200, raw, self.config["model"], http_complete=True)
        derived.update(valid=False, delivery_complete=False, reason="per_call_budget")
        row.update(body_complete=True, transport_status="ok", duration_seconds=31, envelope=derived)
        self.summary.update(output_tokens=3, usage_complete=True, inference_wall_seconds=31,
                            stop_reason="per_call_budget", budget_ok=False)
        self.persist()
        result = verify_run(self.root)
        self.assertEqual(result["status"], "VERIFIED_STOPPED_PREFIX")
        self.assertFalse(result["budget_ok"])
        row["envelope"] = validate_envelope(200, raw, self.config["model"], http_complete=True)
        self.persist()
        with self.assertRaisesRegex(ValueError, "saved_envelope_does_not_match_raw_bytes"):
            verify_run(self.root)

    def test_dispatch_timeout_after_journaling_is_the_actual_ceiling(self):
        self.make_run(stopped=True)
        row = self.records[0]
        raw = (self.root / row["response_body_path"]).read_bytes()
        derived = validate_envelope(200, raw, self.config["model"], http_complete=True)
        derived.update(valid=False, delivery_complete=False, reason="per_call_budget")
        row.update(body_complete=True, transport_status="ok", dispatch_timeout_seconds=0.05, envelope=derived)
        self.summary.update(output_tokens=3, usage_complete=True,
                            stop_reason="per_call_budget", budget_ok=False)
        self.persist()
        self.assertFalse(verify_run(self.root)["budget_ok"])
        row["envelope"] = validate_envelope(200, raw, self.config["model"], http_complete=True)
        self.persist()
        with self.assertRaisesRegex(ValueError, "saved_envelope_does_not_match_raw_bytes"):
            verify_run(self.root)

    def test_global_deadline_before_send_retains_auditable_unsent_reservation(self):
        self.make_run(stopped=True)
        row = self.records[0]
        (self.root / row["response_body_path"]).write_bytes(b"")
        row.update(sent=False, dispatch_timeout_seconds=0, duration_seconds=0,
                   http_status=None, transport_status="error", error="global_budget_before_send",
                   response_sha256=digest(b""),
                   envelope=validate_envelope(None, b"", self.config["model"], http_complete=False))
        self.summary.update(inference_wall_seconds=600, stop_reason="global_budget")
        self.persist()
        result = verify_run(self.root)
        self.assertEqual(result["sent_calls"], 0)
        self.assertEqual(result["unsent_reservations"], 1)
        self.assertEqual(result["status"], "VERIFIED_STOPPED_PREFIX")

    def test_changed_response_bytes_fail_the_recorded_hash(self):
        self.make_run()
        path = self.root / self.records[0]["response_body_path"]
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "response_hash_mismatch"):
            verify_run(self.root)

    def test_forged_saved_envelope_is_recomputed_from_raw_bytes(self):
        self.make_run()
        self.records[0]["envelope"]["content"] = '{"state":"absent","value":null}'
        self.persist()
        with self.assertRaisesRegex(ValueError, "saved_envelope_does_not_match_raw_bytes"):
            verify_run(self.root)

    def test_request_changed_with_repaired_local_hash_still_fails_frozen_bytes(self):
        self.make_run()
        raw = (self.root / self.records[0]["request_body_path"]).read_bytes() + b" "
        (self.root / self.records[0]["request_body_path"]).write_bytes(raw)
        self.records[0]["request_sha256"] = digest(raw)
        self.journal[0]["request_sha256"] = digest(raw)
        self.persist()
        with self.assertRaisesRegex(ValueError, "frozen_request_bytes_mismatch"):
            verify_run(self.root)

    def test_duplicate_journal_and_unmatched_initiation_fail_closed(self):
        self.make_run()
        original = copy.deepcopy(self.journal)
        self.journal[1] = copy.deepcopy(self.journal[0])
        self.persist()
        with self.assertRaises(ValueError):
            verify_run(self.root)
        self.journal = original
        self.records.pop()
        self.persist()
        with self.assertRaisesRegex(ValueError, "unmatched_or_excessive_initiations"):
            verify_run(self.root)

    def test_wrong_metadata_cannot_keep_a_successful_summary(self):
        self.make_run()
        self.write("run/metadata_after.json", {"unexpected": "synthetic drift"})
        with self.assertRaisesRegex(ValueError, "metadata_summary_mismatch"):
            verify_run(self.root)

    def test_forged_counts_usage_or_budget_flags_are_rejected(self):
        self.make_run()
        original = copy.deepcopy(self.summary)
        for key, value in (("initiated_calls", 31), ("output_tokens", 95),
                           ("usage_complete", False), ("budget_ok", False)):
            with self.subTest(key=key):
                self.summary = copy.deepcopy(original)
                self.summary[key] = value
                self.persist()
                with self.assertRaisesRegex(ValueError, "recomputed_summary_mismatch"):
                    verify_run(self.root)

    def test_duration_sum_cannot_exceed_recorded_wall_time(self):
        self.make_run()
        self.summary["inference_wall_seconds"] = 0
        self.persist()
        with self.assertRaisesRegex(ValueError, "inconsistent_inference_wall_time"):
            verify_run(self.root)

    def test_guard_or_summary_freeze_hash_mismatch_is_rejected(self):
        self.make_run()
        self.summary["freeze_sha256"] = "0" * 64
        self.persist()
        with self.assertRaisesRegex(ValueError, "summary_freeze_hash_mismatch"):
            verify_run(self.root)
        self.summary["freeze_sha256"] = self.freeze_sha
        self.persist()
        guard = self.read("RUN_GUARD.json")
        guard["freeze_sha256"] = "0" * 64
        self.write("RUN_GUARD.json", guard)
        with self.assertRaisesRegex(ValueError, "guard_freeze_hash_mismatch"):
            verify_run(self.root)

    def test_forged_saved_score_is_not_accepted(self):
        self.make_run()
        self.save_score()
        report = self.read("run/score.json")
        report["overall"]["joint_correct"] = 31
        self.write("run/score.json", report)
        with self.assertRaisesRegex(ValueError, "saved_score_mismatch"):
            verify_run(self.root, check_score=True)


if __name__ == "__main__":
    unittest.main()
