"""Independent fake-clock controls for durable-journal deadline consumption.

MIT, AnimaFoundry 2026. No live HTTP or model calls occur. Tests use the existing
synthetic runner fixture and independently impose storage-time counterexamples.
"""
import unittest
from unittest.mock import patch

import run_local
import test_runtime as runtime_fixture


class DurableJournalDeadlineControls(unittest.TestCase):
    def setUp(self):
        self.fixture = runtime_fixture.RunnerControls()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def test_budget_expired_by_journal_retains_unsent_slot(self):
        fixture = self.fixture
        fixture.freeze_inputs()
        append = run_local._append

        def delayed_append(path, value):
            append(path, value)
            if path.name == "initiation.jsonl":
                fixture.clock.value = 600.25

        with patch.object(run_local, "_append", side_effect=delayed_append):
            summary = run_local.run(fixture.root, transport=fixture.transport,
                                    metadata=fixture.metadata, clock=fixture.clock)
        self.assertEqual(len(fixture.calls), 0)
        self.assertEqual(summary["initiated_calls"], 1)
        self.assertEqual(summary["stop_reason"], "global_budget")
        self.assertFalse(summary["budget_ok"])
        self.assertEqual(len(summary["unattempted_request_ids"]), 31)
        journal = fixture.read_rows("initiation.jsonl")
        records = fixture.read_rows("records.jsonl")
        self.assertEqual(len(journal), 1)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertIs(record["sent"], False)
        self.assertEqual(record["dispatch_timeout_seconds"], 0)
        self.assertEqual(record["error"], "global_budget_before_send")
        self.assertIsNone(record["http_status"])
        self.assertIs(record["body_complete"], False)
        self.assertEqual((fixture.root / record["response_body_path"]).read_bytes(), b"")

    def test_dispatch_grant_is_reduced_after_slow_durable_journal(self):
        fixture = self.fixture
        fixture.freeze_inputs()
        append = run_local._append
        grants = []

        def delayed_append(path, value):
            append(path, value)
            if path.name == "initiation.jsonl":
                fixture.clock.value = 590.0

        def transport(raw_request, timeout):
            grants.append(timeout)
            self.assertEqual(len(fixture.read_rows("initiation.jsonl")), 1)
            fixture.clock.value = 600.1
            return {"status": 200, "body": runtime_fixture.encoded(runtime_fixture.good_envelope()), "complete": True}

        with patch.object(run_local, "_append", side_effect=delayed_append):
            summary = run_local.run(fixture.root, transport=transport,
                                    metadata=fixture.metadata, clock=fixture.clock)
        self.assertEqual(grants, [10.0])
        record = fixture.read_rows("records.jsonl")[0]
        self.assertEqual(record["timeout_seconds"], 30)
        self.assertEqual(record["dispatch_timeout_seconds"], 10.0)
        self.assertIs(record["sent"], True)
        self.assertEqual(record["envelope"]["reason"], "per_call_budget")
        self.assertFalse(record["envelope"]["delivery_complete"])
        self.assertEqual(summary["initiated_calls"], 1)
        self.assertEqual(summary["stop_reason"], "per_call_budget")

    def test_fetch_rejects_already_expired_absolute_deadline_before_connection(self):
        with patch.object(run_local.time, "monotonic", return_value=70.0), \
                patch.object(run_local.http.client, "HTTPConnection") as connection:
            with self.assertRaises(run_local.TransportFailure):
                run_local._fetch("/api/chat", b"{}", 30, absolute_deadline=69.0)
            connection.assert_not_called()
