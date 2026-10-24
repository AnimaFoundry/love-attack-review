# Adapted from this repository pilot/bf01 (AnimaFoundry, MIT); original unchanged.
"""Independent offline runner/replay controls. All transport is synthetic.

MIT, AnimaFoundry 2026. No test connects to a model, network, or live service.
"""

import base64
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import analyze
from evaluate import score_response
from prepare import canonical, digest
import run_local


PILOT = Path(__file__).resolve().parent


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        parent = PILOT.parents[1] / 'build' / 'bf01-runner-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)


class FakeSocket:
    def __init__(self):
        self.timeouts = []
        self.shutdowns = []

    def settimeout(self, value):
        self.timeouts.append(value)

    def shutdown(self, how):
        self.shutdowns.append(how)


class FakeResponse:
    def __init__(self, chunks, status=200, after_read=None):
        self.chunks = list(chunks)
        self.status = status
        self.reads = 0
        self.after_read = after_read

    def read1(self, maximum):
        self.reads += 1
        if not self.chunks:
            return b''
        value = self.chunks.pop(0)
        if isinstance(value, Exception):
            raise value
        if len(value) > maximum:
            self.chunks.insert(0, value[maximum:])
            value = value[:maximum]
        if self.after_read:
            self.after_read()
        return value


class FakeConnection:
    def __init__(self, response):
        self.sock = FakeSocket()
        self.response = response
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


class TransportControls(unittest.TestCase):
    def invoke(self, response, deadline=10, clock=None):
        connection = FakeConnection(response)
        clock = clock or (lambda: 0)
        self.connection = connection
        with patch.object(run_local.http.client, 'HTTPConnection', return_value=connection) as factory, \
                patch.object(run_local.time, 'monotonic', side_effect=clock):
            try:
                return run_local.fetch('/api/chat', {'synthetic': True}, deadline)
            finally:
                factory.assert_called_once_with('127.0.0.1', 11434)
                self.assertTrue(connection.closed)

    def test_literal_loopback_ignores_proxy_environment(self):
        with patch.dict('os.environ', {'HTTP_PROXY': 'http://invalid.example:1',
                                       'HTTPS_PROXY': 'http://invalid.example:2'}):
            self.assertEqual(self.invoke(FakeResponse([b'{}'])), b'{}')
        self.assertEqual(self.connection.requests[0][0:2], ('POST', '/api/chat'))

    def test_redirect_is_refused_without_second_request(self):
        response = FakeResponse([b'not followed'], status=302)
        with self.assertRaises(run_local.TransportFailure) as caught:
            self.invoke(response)
        self.assertEqual(caught.exception.code, 'http_status_302')
        self.assertEqual(response.reads, 0)
        self.assertEqual(len(self.connection.requests), 1)

    def test_timeout_preserves_received_prefix(self):
        with self.assertRaises(run_local.TransportFailure) as caught:
            self.invoke(FakeResponse([b'original-prefix', TimeoutError('synthetic')]))
        self.assertEqual(caught.exception.prefix, b'original-prefix')
        self.assertEqual(caught.exception.code, 'TimeoutError')

    def test_deadline_between_chunks_preserves_prefix_and_stops(self):
        ticks = [0.0]
        response = FakeResponse([b'first', b'never-read'], after_read=lambda: ticks.__setitem__(0, 2.0))
        with self.assertRaises(run_local.TransportFailure) as caught:
            self.invoke(response, deadline=1, clock=lambda: ticks[0])
        self.assertEqual(caught.exception.code, 'absolute_deadline')
        self.assertEqual(caught.exception.prefix, b'first')
        self.assertEqual(response.reads, 1)

    def test_oversized_http_body_retains_bounded_prefix(self):
        with self.assertRaises(run_local.TransportFailure) as caught:
            self.invoke(FakeResponse([b'a' * 70000]))
        self.assertEqual(caught.exception.code, 'body_limit_prefix_only')
        self.assertEqual(caught.exception.prefix, b'a' * 65537)

    def test_watchdog_interrupts_header_wait_and_is_cancelled_on_exit(self):
        timers = []
        class ManualTimer:
            def __init__(self, interval, callback):
                self.interval, self.callback = interval, callback
                self.started, self.cancelled = False, False
                timers.append(self)
            def start(self):
                self.started = True
            def cancel(self):
                self.cancelled = True
        connection = FakeConnection(FakeResponse([]))
        def header_wait():
            # Deliver the deadline event while the header operation is pending.
            timers[0].callback()
            self.assertEqual(connection.sock.shutdowns, [run_local.socket.SHUT_RDWR])
            raise ConnectionResetError('synthetic socket shutdown during headers')
        connection.getresponse = header_wait
        with patch.object(run_local.http.client, 'HTTPConnection', return_value=connection), \
                patch.object(run_local.threading, 'Timer', ManualTimer), \
                patch.object(run_local.time, 'monotonic', return_value=0), self.assertRaises(run_local.TransportFailure):
            run_local.fetch('/api/chat', {}, 1)
        self.assertEqual(timers[0].interval, 1)
        self.assertTrue(timers[0].started)
        self.assertTrue(timers[0].cancelled)
        self.assertTrue(connection.closed)


class EnvelopeControls(unittest.TestCase):
    def envelope(self, **changes):
        value = {'model': 'synthetic:unit', 'done': True, 'done_reason': 'stop',
                 'message': {'content': '{"x":1}'}, 'prompt_eval_count': 20, 'eval_count': 5}
        value.update(changes)
        return value

    def parse(self, value, complete=True):
        raw = value if isinstance(value, bytes) else canonical(value).encode()
        return run_local.parse_envelope(raw, 'synthetic:unit', complete)

    def test_stop_length_and_partial_http_are_distinct(self):
        self.assertEqual(self.parse(self.envelope())['status'], 'returned')
        self.assertEqual(self.parse(self.envelope(done_reason='length'))['status'], 'truncated')
        partial = self.parse(self.envelope(), complete=False)
        self.assertEqual(partial['status'], 'transport_error')
        self.assertEqual(partial['content'], '{"x":1}')

    def test_malformed_model_content_termination_and_usage_are_transport_failures(self):
        variants = [self.envelope(model='wrong'), self.envelope(done=False),
                    self.envelope(done=1), self.envelope(done_reason='other'),
                    self.envelope(message={'content': 3}), self.envelope(message=None),
                    self.envelope(eval_count=True), self.envelope(eval_count=-1),
                    self.envelope(prompt_eval_count=2.5), []]
        for value in variants:
            with self.subTest(value=value):
                parsed = self.parse(value)
                self.assertEqual(parsed['status'], 'transport_error')
                self.assertIsNotNone(parsed['error'])
                self.assertNotEqual(parsed['usage']['output_tokens'], True)

    def test_invalid_utf8_duplicate_nonfinite_and_deep_json_fail_closed(self):
        values = [b'\xff\xfe', b'{"model":"x","model":"y"}',
                  b'{"x":NaN}', b'[' * 2000 + b'0' + b']' * 2000]
        for raw in values:
            with self.subTest(prefix=raw[:30]):
                self.assertEqual(self.parse(raw)['status'], 'transport_error')


class FreezeControls(WorkspaceTest):
    def write_freeze(self):
        entries = []
        for name in sorted(run_local.FROZEN_REQUIRED):
            (self.root / name).write_bytes(b'original synthetic fixture\n')
            entries.append({'path': name, 'sha256': digest((self.root / name).read_bytes())})
        (self.root / 'freeze.json').write_text(json.dumps({'files': entries}), encoding='utf-8')
        return entries

    def test_exact_inventory_hashes_pass_and_changed_file_fails(self):
        self.write_freeze()
        with patch.object(run_local, 'ROOT', self.root):
            run_local.verify_freeze()
            (self.root / 'cases.jsonl').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                run_local.verify_freeze()

    def test_empty_partial_duplicate_and_unsafe_inventories_fail(self):
        entries = self.write_freeze()
        for bad in ([], entries[:-1], entries + entries[:1],
                    [{'path': '../outside', 'sha256': '0' * 64}]):
            (self.root / 'freeze.json').write_text(json.dumps({'files': bad}), encoding='utf-8')
            with self.subTest(count=len(bad)), patch.object(run_local, 'ROOT', self.root), self.assertRaises(ValueError):
                run_local.verify_freeze()


class RunnerReplayControls(WorkspaceTest):
    def setUp(self):
        super().setUp()
        self.cases = [json.loads(line) for line in (PILOT / 'cases.jsonl').read_text(encoding='utf-8').splitlines()]
        self.plan = {'model': {'tag': 'synthetic:unit'},
                     'budget': {'max_calls': 168, 'external_api_dollars': 0},
                     'options': {'num_predict': 128, 'num_ctx': 4096, 'temperature': 0}}
        (self.root / 'cases.jsonl').write_text(''.join(canonical(c) + '\n' for c in self.cases), encoding='utf-8')
        (self.root / 'plan.json').write_text(canonical(self.plan), encoding='utf-8')
        (self.root / 'freeze.json').write_text('{"synthetic_fixture":true}\n', encoding='utf-8')
        self.destination = self.root / 'run'

    def invoke(self, *, complete=False, failure=None, modify=None):
        states = [0]
        def state(*args):
            states[0] += 1
            if not complete and states[0] > 2:
                raise RuntimeError('synthetic metadata stop after one case')
            return copy.deepcopy(self.plan['model'])
        calls = [0]
        def fetch(path, payload, deadline):
            self.assertEqual(path, '/api/chat')
            index = calls[0]
            calls[0] += 1
            self.assertEqual(payload['messages'], self.cases[index]['messages'])
            self.assertEqual(payload['options']['num_predict'], 128)
            self.assertFalse(payload['stream'])
            self.assertEqual(payload['keep_alive'], 0)
            if failure:
                raise failure
            value = {'model': self.plan['model']['tag'], 'done': True, 'done_reason': 'stop',
                     'message': {'content': canonical(self.cases[index]['expected_json'])},
                     'prompt_eval_count': 50, 'eval_count': 8}
            if modify:
                modify(value)
            return canonical(value).encode()
        with patch.object(run_local, 'ROOT', self.root), patch.object(run_local, 'verify_freeze', return_value={}), \
                patch.object(run_local, 'model_state', side_effect=state), \
                patch.object(run_local, 'fetch', side_effect=fetch), redirect_stdout(io.StringIO()):
            run_local.run(self.destination)
        return calls[0]

    def report(self):
        with patch.object(analyze, 'ROOT', self.root), patch.object(run_local, 'ROOT', self.root), \
                patch.object(run_local, 'verify_freeze', return_value={}):
            return analyze.analyze(self.destination)

    def read_rows(self, name):
        return [json.loads(line) for line in (self.destination / name).read_text(encoding='utf-8').splitlines()]

    def write_rows(self, name, rows):
        (self.destination / name).write_text(''.join(canonical(row) + '\n' for row in rows), encoding='utf-8')

    def test_successful_168_case_synthetic_transport_is_replayable_and_finite(self):
        self.assertEqual(self.invoke(complete=True), 168)
        report = self.report()
        self.assertEqual(report['status'], 'COMPLETE')
        self.assertEqual(report['initiated_calls'], 168)
        self.assertEqual(report['failures'], [])
        self.assertTrue(all(c['success'] == 24 for c in report['conditions'].values()))
        self.assertEqual(report['confirmatory_inference'], 'NOT_PERFORMED')

    def test_timeout_partial_bytes_are_retained_and_no_retry_occurs(self):
        raw = b'\xffpartial-original-http'
        self.assertEqual(self.invoke(complete=True, failure=run_local.TransportFailure('absolute_deadline', raw)), 1)
        response = self.read_rows('responses.jsonl')[0]
        self.assertEqual(base64.b64decode(response['raw_http_body_base64']), raw)
        self.assertFalse(response['http_body_complete'])
        report = self.report()
        self.assertEqual(report['status'], 'INCOMPLETE')
        self.assertEqual(report['initiated_calls'], 1)
        self.assertEqual(sum(x['transport_error'] for x in report['conditions'].values()), 1)
        self.assertEqual(sum(x['behavioral_violation'] for x in report['conditions'].values()), 0)

    def test_malformed_response_can_close_ledger_and_replay_as_failure(self):
        self.assertEqual(self.invoke(modify=lambda value: value.update(message={'content': 5}, eval_count=True)), 1)
        report = self.report()
        self.assertEqual(report['initiated_calls'], 1)
        self.assertEqual(report['usage']['output_tokens_unknown_calls'], 1)
        self.assertEqual(self.read_rows('ledger.jsonl')[-1]['event'], 'failed')

    def test_truncated_response_cannot_be_relabelled_complete(self):
        self.invoke(modify=lambda value: value.update(done_reason='length'))
        response = self.read_rows('responses.jsonl')
        ledger = self.read_rows('ledger.jsonl')
        response[0]['status'] = 'returned'
        ledger[-1]['score'] = score_response(self.cases[0]['expected_json'], response[0]['response']['message']['content'])
        ledger[-1]['success'] = True
        ledger[-1]['event'] = 'completed'
        self.write_rows('responses.jsonl', response)
        self.write_rows('ledger.jsonl', ledger)
        with self.assertRaises(ValueError):
            self.report()

    def test_replay_rejects_broken_hash_usage_attempt_or_completion_link(self):
        self.invoke()
        original_response = self.read_rows('responses.jsonl')
        original_ledger = self.read_rows('ledger.jsonl')
        completion_path = self.destination / 'completion.json'
        original_completion = json.loads(completion_path.read_text())
        changes = ['http_hash', 'request_hash', 'usage', 'attempt', 'event', 'completion']
        for change in changes:
            response, ledger, completion = copy.deepcopy(original_response), copy.deepcopy(original_ledger), copy.deepcopy(original_completion)
            if change == 'http_hash': response[0]['http_body_sha256'] = '0' * 64
            if change == 'request_hash': response[0]['request_sha256'] = '0' * 64
            if change == 'usage': ledger[-1]['usage']['output_tokens'] += 1
            if change == 'attempt': ledger[-1]['attempt_id'] = 'unrelated'
            if change == 'event': ledger[-1]['event'] = 'failed'
            if change == 'completion': completion['status'] = 'COMPLETE'
            self.write_rows('responses.jsonl', response)
            self.write_rows('ledger.jsonl', ledger)
            completion_path.write_text(canonical(completion), encoding='utf-8')
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.report()

    def test_output_budget_breach_cannot_be_erased_from_ledger(self):
        self.invoke(modify=lambda value: value.update(eval_count=513))
        self.assertEqual(self.report()['initiated_calls'], 1)
        ledger = self.read_rows('ledger.jsonl')
        ledger[-1]['budget_breaches'] = []
        ledger[-1]['success'] = True
        ledger[-1]['event'] = 'completed'
        self.write_rows('ledger.jsonl', ledger)
        with self.assertRaises(ValueError):
            self.report()

    def test_existing_destination_and_unbounded_configuration_are_refused(self):
        self.destination.mkdir()
        with self.assertRaises(FileExistsError):
            self.invoke()
        self.destination = self.root / 'other-run'
        self.plan['options']['num_predict'] = -1
        (self.root / 'plan.json').write_text(canonical(self.plan), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.invoke()

    def test_model_drift_is_rejected_before_any_inference_reservation(self):
        with patch.object(run_local, 'ROOT', self.root), patch.object(run_local, 'verify_freeze', return_value={}), \
                patch.object(run_local, 'model_state', return_value={'tag': 'changed:unit'}), \
                patch.object(run_local, 'fetch') as fetch, self.assertRaises(ValueError):
            run_local.run(self.destination)
        fetch.assert_not_called()
        self.assertFalse(self.destination.exists())


if __name__ == '__main__':
    unittest.main()
