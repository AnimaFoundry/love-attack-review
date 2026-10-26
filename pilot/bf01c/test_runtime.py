"""Independent synthetic BF-01C delivery and finite-run controls.

MIT, AnimaFoundry 2026; see repository LICENSE-CODE. Newly authored controls,
informed by this repository's owned BF-01B testing approach. No private data,
model inference, live HTTP connection, or external service is used by tests.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import envelope
import freeze
import run_local


PILOT = Path(__file__).resolve().parent
MODEL = "synthetic-unit-model:local"


def encoded(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def good_envelope(**overrides):
    value = {
        "model": MODEL, "done": True, "done_reason": "stop",
        "message": {"role": "assistant", "content": '{"state":"observed","value":0}'},
        "eval_count": 14, "prompt_eval_count": 91,
    }
    value.update(overrides)
    return value


class EnvelopeControls(unittest.TestCase):
    def parse(self, value, status=200, complete=True):
        raw = value if isinstance(value, bytes) else encoded(value)
        return envelope.validate_envelope(status, raw, MODEL, http_complete=complete)

    def assert_invalid(self, value, **kwargs):
        result = self.parse(value, **kwargs)
        self.assertIs(result["valid"], False)
        self.assertIsInstance(result["reason"], str)
        self.assertTrue(result["reason"])
        return result

    def test_complete_assistant_reply_exposes_original_content_and_usage(self):
        result = self.parse(good_envelope())
        self.assertIs(result["valid"], True)
        self.assertEqual(result["content"], '{"state":"observed","value":0}')
        self.assertEqual(result["eval_count"], 14)
        self.assertEqual(result["prompt_eval_count"], 91)

    def test_incomplete_http_cannot_be_rescued_by_complete_json_prefix(self):
        raw = encoded(good_envelope())
        self.assertTrue(self.parse(raw)["valid"])
        self.assert_invalid(raw, complete=False)
        self.assert_invalid(raw, complete=1)

    def test_http_status_failure_or_redirect_is_not_delivered_content(self):
        for status in (400, 401, 404, 429, 500, 302, True):
            with self.subTest(status=status):
                self.assert_invalid(good_envelope(), status=status)

    def test_termination_and_model_identity_fail_closed(self):
        for changes in (
            {"done": False}, {"done": 1}, {"done": None},
            {"done_reason": "length"}, {"done_reason": "tool_call"},
            {"done_reason": None}, {"model": "another:local"}, {"model": None},
        ):
            with self.subTest(changes=changes):
                self.assert_invalid(good_envelope(**changes))
        for missing in ("model", "done", "done_reason"):
            value = good_envelope()
            del value[missing]
            self.assert_invalid(value)

    def test_missing_invalid_or_excessive_usage_is_not_budget_evidence(self):
        for field in ("eval_count", "prompt_eval_count"):
            value = good_envelope()
            del value[field]
            self.assert_invalid(value)
            for count in (None, True, False, -1, 1.0, "14"):
                with self.subTest(field=field, count=count):
                    self.assert_invalid(good_envelope(**{field: count}))
        self.assert_invalid(good_envelope(eval_count=257))
        self.assertTrue(self.parse(good_envelope(eval_count=256))["valid"])

    def test_content_role_tools_and_thinking_are_distinct_from_task_correctness(self):
        for message in (
            None, [], {}, {"role": "user", "content": "x"},
            {"role": "assistant", "content": None},
            {"role": "assistant", "content": 7},
            {"role": "assistant", "content": ""},
            {"role": "assistant", "content": " \n\t"},
            {"role": "assistant", "content": "x", "tool_calls": [{"function": {"name": "unexpected"}}]},
            {"role": "assistant", "content": "x", "thinking": "unexpected channel"},
        ):
            with self.subTest(message=message):
                self.assert_invalid(good_envelope(message=message))
        # Task errors are retained and scored separately, not transport errors.
        result = self.parse(good_envelope(message={"role": "assistant", "content": "ordinary incorrect answer"}))
        self.assertTrue(result["valid"])
        self.assertEqual(result["content"], "ordinary incorrect answer")

    def test_explicit_server_error_cannot_hide_behind_valid_content(self):
        self.assert_invalid(good_envelope(error="synthetic schema rejection"))

    def test_raw_envelope_utf8_duplicates_nonfinite_and_bounds_are_strict(self):
        raw_good = encoded(good_envelope())
        invalids = (
            b"\xff", b"\xef\xbb\xbf" + raw_good, b"[]", b"null", b"",
            raw_good + b"garbage", raw_good + raw_good,
            raw_good.replace(b'"done":true', b'"done":false,"done":true'),
            raw_good.replace(b'"role":"assistant"', b'"role":"user","role":"assistant"'),
            raw_good.replace(b'"eval_count":14', b'"eval_count":NaN'),
            raw_good.replace(b'"eval_count":14', b'"eval_count":1e999'),
            raw_good.replace(b'"role":"assistant"', b'"role":"\\ud800"'),
            b"[" * 2000 + b"0" + b"]" * 2000,
            raw_good + b" " * (1_048_577 - len(raw_good)),
        )
        for raw in invalids:
            with self.subTest(prefix=raw[:35], size=len(raw)):
                self.assert_invalid(raw)


class WorkspaceControls(unittest.TestCase):
    def setUp(self):
        parent = PILOT.parents[1] / "build" / "bf01c-runtime-tests"
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="bf01c-offline-", dir=parent)
        self.root = Path(self.temp.name)
        self.assertTrue(self.root.resolve().is_relative_to(parent.resolve()))
        self.addCleanup(self.temp.cleanup)

    def write_json(self, name, value):
        (self.root / name).write_bytes(encoded(value))


class FreezeControls(WorkspaceControls):
    def test_exact_file_hashes_are_verified_and_later_drift_fails(self):
        (self.root / "first.txt").write_bytes(b"original synthetic first\n")
        (self.root / "second.txt").write_bytes(b"original synthetic second\n")
        freeze.create_freeze(self.root, ["first.txt", "second.txt"])
        freeze.verify_freeze(self.root)
        (self.root / "second.txt").write_bytes(b"changed synthetic second\n")
        with self.assertRaises(ValueError):
            freeze.verify_freeze(self.root)

    def test_freeze_cannot_overwrite_a_previous_snapshot(self):
        (self.root / "first.txt").write_bytes(b"original synthetic\n")
        freeze.create_freeze(self.root, ["first.txt"])
        original = (self.root / "FREEZE.json").read_bytes()
        with self.assertRaises(FileExistsError):
            freeze.create_freeze(self.root, ["first.txt"])
        self.assertEqual((self.root / "FREEZE.json").read_bytes(), original)

    def test_unsafe_missing_duplicate_and_empty_freeze_lists_fail(self):
        (self.root / "first.txt").write_bytes(b"original synthetic\n")
        for files in ([], ["../outside.txt"], ["/outside.txt"], ["missing.txt"],
                      ["first.txt", "first.txt"]):
            with self.subTest(files=files), self.assertRaises((ValueError, FileNotFoundError)):
                freeze.create_freeze(self.root, files)
            self.assertFalse((self.root / "FREEZE.json").exists())


class MutableClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value


class RunnerControls(WorkspaceControls):
    def setUp(self):
        super().setUp()
        self.clock = MutableClock()
        self.metadata_value = {"model": MODEL, "digest": "synthetic-model-digest"}
        self.config = {
            "study_id": "BF01C", "model": MODEL,
            "expected_metadata": copy.deepcopy(self.metadata_value),
            "options": {"num_predict": 256, "num_ctx": 4096, "temperature": 0, "seed": 2601},
            "limits": {"max_calls": 32, "per_call_seconds": 30,
                       "global_seconds": 600, "max_generated_tokens": 8192,
                       "max_body_bytes": 1_048_576},
        }
        schemas = {}
        for contract in ("no_evidence", "evidence"):
            raw = (PILOT / f"schema_{contract}.json").read_bytes()
            (self.root / f"schema_{contract}.json").write_bytes(raw)
            schemas[contract] = json.loads(raw)
        self.requests = []
        # The first schema/evidence operation checks the intended constrained arm.
        for mode, contract in (("schema", "evidence"), ("raw", "no_evidence"),
                               ("raw", "evidence"), ("schema", "no_evidence")):
            for index in range(8):
                body = {
                    "model": MODEL, "stream": False,
                    "messages": [{"role": "system", "content": "Synthetic offline unit test."},
                                 {"role": "user", "content": f"Independent synthetic input {index}."}],
                    "options": copy.deepcopy(self.config["options"]),
                }
                if mode == "schema":
                    body["format"] = schemas[contract]
                self.requests.append({
                    "request_id": f"unit-{mode}-{contract}-{index}",
                    "input_id": f"unit-input-{index}",
                    "arm": f"{mode}_{contract}", "mode": mode, "contract": contract,
                    "request_body": body,
                })
        self.calls = []
        self.metadata_calls = 0

    def freeze_inputs(self):
        self.write_json("config.json", self.config)
        self.write_json("requests.json", self.requests)
        self.write_json("tasks.json", {"status": "SYNTHETIC_OFFLINE_UNIT_FIXTURE"})
        for name in run_local.REQUIRED_FROZEN:
            if (self.root / name).exists():
                continue
            source = PILOT / name
            # This scratch manifest exercises the runner's inventory rules;
            # only config/requests/schemas and currently imported runner code
            # execute. Pending study prose is an explicit unit placeholder.
            value = source.read_bytes() if source.is_file() else b"synthetic offline unit placeholder\n"
            (self.root / name).write_bytes(value)
        (self.root / "synthetic-source.txt").write_bytes(b"immutable unit-test input\n")
        freeze.create_freeze(self.root, sorted(run_local.REQUIRED_FROZEN | {"synthetic-source.txt"}))

    def metadata(self):
        self.metadata_calls += 1
        return copy.deepcopy(self.metadata_value)

    def transport(self, request_body, timeout):
        index = len(self.calls)
        self.assertGreater(timeout, 0)
        self.assertLessEqual(timeout, 30)
        self.assertEqual(json.loads(request_body), self.requests[index]["request_body"])
        rows = self.read_rows("initiation.jsonl")
        self.assertEqual(len(rows), index + 1, "initiation must be durable before send")
        self.assertTrue((self.root / "RUN_GUARD.json").exists())
        self.calls.append(request_body)
        return {"status": 200, "body": encoded(good_envelope()), "complete": True}

    def invoke(self, transport=None, metadata=None):
        return run_local.run(self.root, transport=transport or self.transport,
                             metadata=metadata or self.metadata, clock=self.clock,
                             utcnow=lambda: "2026-10-27T00:00:00Z")

    def read_rows(self, name):
        path = self.root / "run" / name
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_exactly_32_calls_are_journaled_and_single_run_cannot_resume(self):
        self.freeze_inputs()
        result = self.invoke()
        self.assertEqual(len(self.calls), 32)
        self.assertEqual(result["initiated_calls"], 32)
        self.assertEqual(result["completed_calls"], 32)
        self.assertEqual(result["output_tokens"], 32 * 14)
        self.assertEqual(result["unattempted_request_ids"], [])
        self.assertEqual(len(self.read_rows("initiation.jsonl")), 32)
        self.assertEqual(len(self.read_rows("records.jsonl")), 32)
        with self.assertRaises(FileExistsError):
            self.invoke()
        self.assertEqual(len(self.calls), 32)

    def test_transport_exception_stops_once_and_leaves_31_unattempted(self):
        self.freeze_inputs()
        def broken(body, timeout):
            self.transport(body, timeout)
            raise TimeoutError("synthetic no network timeout")
        result = self.invoke(transport=broken)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result["initiated_calls"], 1)
        self.assertEqual(len(result["unattempted_request_ids"]), 31)
        self.assertEqual(result["stop_reason"], "transport_error")

    def test_incomplete_http_with_valid_json_stops_without_retry(self):
        self.freeze_inputs()
        def incomplete(body, timeout):
            value = self.transport(body, timeout)
            value["complete"] = False
            return value
        result = self.invoke(transport=incomplete)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result["stop_reason"], "incomplete_http")
        self.assertEqual(len(result["unattempted_request_ids"]), 31)

    def test_http_schema_error_and_missing_usage_stop_before_next_call(self):
        for mode in ("schema_error", "missing_usage"):
            with self.subTest(mode=mode):
                self.setUp()
                self.freeze_inputs()
                def failed(body, timeout):
                    value = self.transport(body, timeout)
                    if mode == "schema_error":
                        value.update(status=400, body=b'{"error":"synthetic unsupported schema"}')
                    else:
                        obj = good_envelope()
                        del obj["eval_count"]
                        value["body"] = encoded(obj)
                    return value
                result = self.invoke(transport=failed)
                self.assertEqual(len(self.calls), 1)
                self.assertEqual(len(result["unattempted_request_ids"]), 31)
                self.assertTrue(result["stop_reason"].startswith("invalid_envelope:"))

    def test_incorrect_or_empty_content_is_preserved_and_does_not_trigger_retries(self):
        self.freeze_inputs()
        def incorrect(body, timeout):
            value = self.transport(body, timeout)
            content = "" if len(self.calls) == 1 else "incorrect synthetic text"
            value["body"] = encoded(good_envelope(message={"role": "assistant", "content": content}))
            return value
        result = self.invoke(transport=incorrect)
        self.assertEqual(len(self.calls), 32)
        self.assertEqual(result["initiated_calls"], 32)
        self.assertEqual(len(self.read_rows("records.jsonl")), 32)

    def test_per_call_30_second_ceiling_stops_after_one_slow_return(self):
        self.freeze_inputs()
        def slow(body, timeout):
            value = self.transport(body, timeout)
            self.clock.value += 30.001
            return value
        result = self.invoke(transport=slow)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result["stop_reason"], "per_call_budget")

    def test_global_600_second_ceiling_prevents_the_31st_call(self):
        self.freeze_inputs()
        def measured(body, timeout):
            value = self.transport(body, timeout)
            self.clock.value += 20
            return value
        result = self.invoke(transport=measured)
        self.assertEqual(len(self.calls), 30)
        self.assertEqual(result["stop_reason"], "global_budget")
        self.assertEqual(len(result["unattempted_request_ids"]), 2)

    def test_8192_token_ceiling_is_32_times_256_without_an_extra_request(self):
        self.freeze_inputs()
        def full_tokens(body, timeout):
            value = self.transport(body, timeout)
            value["body"] = encoded(good_envelope(eval_count=256))
            return value
        result = self.invoke(transport=full_tokens)
        self.assertEqual(len(self.calls), 32)
        self.assertEqual(result["output_tokens"], 8192)
        self.assertEqual(result["unattempted_request_ids"], [])

    def test_over_256_reported_tokens_is_invalid_and_never_retried(self):
        self.freeze_inputs()
        def excess_tokens(body, timeout):
            value = self.transport(body, timeout)
            value["body"] = encoded(good_envelope(eval_count=257))
            return value
        result = self.invoke(transport=excess_tokens)
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(result["stop_reason"].startswith("invalid_envelope:"))

    def test_drifted_freeze_is_refused_before_any_call(self):
        self.freeze_inputs()
        (self.root / "synthetic-source.txt").write_bytes(b"drift before run")
        with self.assertRaises(ValueError):
            self.invoke()
        self.assertEqual(self.calls, [])

    def test_midrun_file_drift_stops_before_next_send(self):
        self.freeze_inputs()
        def drift(body, timeout):
            value = self.transport(body, timeout)
            (self.root / "synthetic-source.txt").write_bytes(b"drift after one reply")
            return value
        result = self.invoke(transport=drift)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result["stop_reason"], "freeze_drift")

    def test_rewritten_manifest_cannot_replace_the_initial_guard_hash(self):
        self.freeze_inputs()
        def rewritten_manifest(body, timeout):
            value = self.transport(body, timeout)
            manifest = json.loads((self.root / "FREEZE.json").read_text())
            manifest["created_utc"] = "changed after the first request"
            self.write_json("FREEZE.json", manifest)
            return value
        result = self.invoke(transport=rewritten_manifest)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result["stop_reason"], "freeze_drift")

    def test_initial_metadata_drift_is_refused_without_any_model_request(self):
        self.freeze_inputs()
        result = self.invoke(metadata=lambda: {"model": "other:local"})
        self.assertEqual(self.calls, [])
        self.assertEqual(result["initiated_calls"], 0)
        self.assertEqual(result["stop_reason"], "metadata_drift")
        self.assertEqual(len(result["unattempted_request_ids"]), 32)

    def test_postrun_metadata_drift_is_preserved_as_incomplete_evidence(self):
        self.freeze_inputs()
        visits = [0]
        def changing_metadata():
            visits[0] += 1
            return copy.deepcopy(self.metadata_value) if visits[0] == 1 else {"model": "other:local"}
        result = self.invoke(metadata=changing_metadata)
        self.assertEqual(len(self.calls), 32)
        self.assertEqual(result["stop_reason"], "metadata_drift")

    def test_limits_cannot_be_expanded_by_configuration(self):
        for field, value in (("max_calls", 33), ("max_generated_tokens", 8193),
                             ("per_call_seconds", 31), ("global_seconds", 601)):
            with self.subTest(field=field):
                self.setUp()
                self.config["limits"][field] = value
                self.freeze_inputs()
                with self.assertRaises(ValueError):
                    self.invoke()
                self.assertEqual(self.calls, [])

    def test_duplicate_or_33_request_schedule_is_refused_before_send(self):
        for extra in (False, True):
            with self.subTest(extra_request=extra):
                self.setUp()
                if extra:
                    self.requests.append(copy.deepcopy(self.requests[0]))
                else:
                    self.requests[-1]["request_id"] = self.requests[0]["request_id"]
                self.freeze_inputs()
                with self.assertRaises(ValueError):
                    self.invoke()
                self.assertEqual(self.calls, [])


class FakeSocket:
    def __init__(self):
        self.shutdowns = []
        self.timeouts = []

    def settimeout(self, value):
        self.timeouts.append(value)

    def shutdown(self, value):
        self.shutdowns.append(value)


class FakeHTTPResponse:
    def __init__(self, chunks, status=200, length=0):
        self.chunks, self.status, self.length = list(chunks), status, length

    def read1(self, size):
        if not self.chunks:
            return b""
        value = self.chunks.pop(0)
        if isinstance(value, Exception):
            raise value
        if len(value) > size:
            self.chunks.insert(0, value[size:])
            value = value[:size]
        return value


class FakeHTTPConnection:
    def __init__(self, response):
        self.response = response
        self.sock = FakeSocket()
        self.requests = []
        self.closed = False

    def connect(self):
        pass

    def request(self, method, path, **kwargs):
        self.requests.append((method, path, kwargs))

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


class TransportMetadataControls(unittest.TestCase):
    def fetch(self, response):
        self.connection = FakeHTTPConnection(response)
        with patch.object(run_local.http.client, "HTTPConnection", return_value=self.connection) as connection_factory, \
                patch.object(run_local.time, "monotonic", return_value=0):
            try:
                return run_local._fetch("/api/chat", b"{}", 30)
            finally:
                connection_factory.assert_called_once_with("127.0.0.1", 11434, timeout=30)
                self.assertTrue(self.connection.closed)

    def test_loopback_transport_ignores_proxy_and_does_not_follow_redirect(self):
        with patch.dict("os.environ", {"HTTP_PROXY": "http://invalid.example:1",
                                       "HTTPS_PROXY": "http://invalid.example:2"}):
            result = self.fetch(FakeHTTPResponse([b"redirect body"], status=302))
        self.assertEqual(result["status"], 302)
        self.assertEqual(len(self.connection.requests), 1)
        self.assertEqual(self.connection.requests[0][:2], ("POST", "/api/chat"))

    def test_read_failure_retains_prefix_and_incomplete_length_is_not_success(self):
        for response in (FakeHTTPResponse([b"prefix", TimeoutError("synthetic")]),
                         FakeHTTPResponse([b"prefix"], length=20)):
            with self.subTest(length=response.length), self.assertRaises(run_local.TransportFailure) as caught:
                self.fetch(response)
            self.assertEqual(caught.exception.body, b"prefix")

    def test_body_limit_keeps_only_bounded_prefix(self):
        with self.assertRaises(run_local.TransportFailure) as caught:
            self.fetch(FakeHTTPResponse([b"x" * 1_048_600]))
        self.assertEqual(caught.exception.code, "body_limit")
        self.assertEqual(len(caught.exception.body), 1_048_577)

    def test_watchdog_closes_socket_during_header_wait(self):
        timers = []
        class ManualTimer:
            def __init__(self, interval, callback):
                self.interval, self.callback = interval, callback
                self.started = self.cancelled = False
                timers.append(self)
            def start(self):
                self.started = True
            def cancel(self):
                self.cancelled = True
        connection = FakeHTTPConnection(FakeHTTPResponse([]))
        def blocked_headers():
            timers[0].callback()
            raise ConnectionResetError("synthetic watchdog interruption")
        connection.getresponse = blocked_headers
        with patch.object(run_local.http.client, "HTTPConnection", return_value=connection), \
                patch.object(run_local.threading, "Timer", ManualTimer), \
                patch.object(run_local.time, "monotonic", return_value=0), \
                self.assertRaises(run_local.TransportFailure):
            run_local._fetch("/api/chat", b"{}", 30)
        self.assertEqual(connection.sock.shutdowns, [run_local.socket.SHUT_RDWR])
        self.assertTrue(connection.closed)
        self.assertTrue(timers[0].started)
        self.assertTrue(timers[0].cancelled)
        self.assertEqual(timers[0].interval, 30)

    def test_metadata_collection_uses_only_three_metadata_endpoints(self):
        responses = {
            "/api/tags": {"models": [{"name": MODEL, "digest": "a" * 64, "size": 100}]},
            "/api/show": {"template": "unit template", "system": "", "parameters": "",
                          "license": "synthetic license metadata", "details": {"family": "unit"}},
            "/api/version": {"version": "synthetic"},
        }
        calls = []
        def metadata_fetch(path, payload, timeout):
            calls.append(path)
            self.assertIn(path, responses)
            self.assertEqual(timeout, 10)
            return {"status": 200, "complete": True, "body": encoded(responses[path])}
        with patch.object(run_local, "_fetch", side_effect=metadata_fetch):
            result = run_local.collect_metadata(MODEL)
        self.assertEqual(calls, ["/api/tags", "/api/show", "/api/version"])
        self.assertEqual(result["tag"], MODEL)
        self.assertEqual(result["digest"], "a" * 64)


if __name__ == "__main__":
    unittest.main()
