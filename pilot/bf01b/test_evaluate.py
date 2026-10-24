# Adapted from this repository pilot/bf01 (AnimaFoundry, MIT); original unchanged.
"""Synthetic, offline contract and accounting controls; no model evaluation.

Copyright (c) 2026 AnimaFoundry. MIT; see ../../LICENSE-CODE.
Run: python -m unittest discover -s pilot/bf01b -p test_evaluate.py -v
"""

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from evaluate import BudgetError, BudgetLedger, LedgerError, Limits, score_response


class ContractControls(unittest.TestCase):
    def test_valid_object_accepts_key_order_whitespace_and_unicode_escapes(self):
        expected = {"count": 2, "label": "caf\u00e9", "nested": {"ok": True}}
        raw = ' \n {"nested":{"ok":true}, "label":"caf\\u00e9", "count":2}\t '
        score = score_response(expected, raw)
        self.assertTrue(score["success"])
        self.assertFalse(score["behavioral_violation"])
        self.assertEqual(score["raw_text"], raw)
        self.assertEqual(score["raw_text_sha256"], hashlib.sha256(raw.encode()).hexdigest())

    def test_valid_repeated_arrays_are_successful(self):
        expected = {"values": [7] * 20, "strings": ["abc"] * 10}
        self.assertTrue(score_response(expected, json.dumps(expected))["success"])

    def test_escaped_supplementary_unicode_is_accepted(self):
        self.assertTrue(score_response({"value": "\U0001f642"}, '{"value":"\\ud83d\\ude42"}')["success"])

    def test_raw_unicode_is_not_normalized(self):
        raw = '{"value":"e\u0301"}'
        score = score_response({"value": "\u00e9"}, raw)
        self.assertFalse(score["success"])
        self.assertEqual(score["raw_text"], raw)

    def test_no_wrapper_prose_fences_or_second_object(self):
        for raw in ('```json\n{"x":1}\n```', 'Answer: {"x":1}',
                    '{"x":1} thanks', '{"x":1}{"x":1}', '\ufeff{"x":1}'):
            with self.subTest(raw=raw):
                score = score_response({"x": 1}, raw)
                self.assertFalse(score["success"])
                self.assertEqual(score["reason"], "invalid_json")

    def test_exact_object_required(self):
        for raw in ('[1]', 'null', '1', 'true', '"object"'):
            with self.subTest(raw=raw):
                self.assertEqual(score_response({"x": 1}, raw)["reason"], "not_object")

    def test_duplicate_keys_rejected_at_every_depth_even_if_values_equal(self):
        for raw in ('{"x":1,"x":1}', '{"x":1,"\\u0078":1}',
                    '{"nested":{"x":1,"x":1}}', '{"items":[{"x":1,"x":1}]}'):
            with self.subTest(raw=raw):
                self.assertEqual(score_response({}, raw)["reason"], "duplicate_key")

    def test_nonfinite_and_overflow_rejected(self):
        for raw in ('{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}',
                    '{"x":1e400}', '{"x":[NaN]}'):
            with self.subTest(raw=raw):
                self.assertFalse(score_response({"x": 0}, raw)["success"])

    def test_boolean_integer_and_float_types_are_distinct_recursively(self):
        cases = [({"x": 1}, '{"x":true}'), ({"x": True}, '{"x":1}'),
                 ({"x": 1}, '{"x":1.0}'), ({"x": 1.0}, '{"x":1}'),
                 ({"x": [1]}, '{"x":[true]}'),
                 ({"x": {"y": False}}, '{"x":{"y":0}}')]
        for expected, raw in cases:
            with self.subTest(expected=expected, raw=raw):
                self.assertEqual(score_response(expected, raw)["reason"], "value_or_type_mismatch")

    def test_exact_keys_values_and_array_order_required(self):
        for raw in ('{}', '{"x":1,"extra":null}', '{"x":2}', '{"x":[2,1]}'):
            with self.subTest(raw=raw):
                self.assertFalse(score_response({"x": 1}, raw)["success"])
        self.assertFalse(score_response({"x": [1, 2]}, '{"x":[2,1]}')["success"])

    def test_null_boolean_and_float_values_remain_valid(self):
        expected = {"none": None, "no": False, "number": 0.5, "empty": []}
        self.assertTrue(score_response(expected, json.dumps(expected))["success"])

    def test_incomplete_and_invalid_json(self):
        for raw in ('{"x":', '{"x":1,}', "{'x':1}", '{"x":"\\ud800"}', '{"x":"a\nb"}'):
            with self.subTest(raw=raw):
                self.assertFalse(score_response({"x": 1}, raw)["success"])

    def test_empty_returned_response_is_observed_non_success(self):
        for raw in ('', ' \n\t'):
            with self.subTest(raw=raw):
                result = score_response({}, raw)
                self.assertEqual(result["status"], "empty")
                self.assertTrue(result["empty"])
                self.assertTrue(result["response_observed"])
                self.assertTrue(result["behavioral_violation"])
                self.assertFalse(result["success"])

    def test_truncated_valid_object_is_non_success_without_invented_violation(self):
        result = score_response({"x": 1}, '{"x":1}', "truncated")
        self.assertFalse(result["success"])
        self.assertTrue(result["contract_match"])
        self.assertFalse(result["behavioral_violation"])
        self.assertTrue(result["truncated"])

    def test_truncated_invalid_prefix_has_observable_contract_failure(self):
        result = score_response({"x": 1}, '{"x":', "truncated")
        self.assertFalse(result["success"])
        self.assertTrue(result["behavioral_violation"])
        self.assertEqual(result["observed_contract_reason"], "invalid_json")

    def test_transport_error_never_creates_behavioral_label(self):
        for raw in (None, '', '{"x":', '{"x":1}'):
            with self.subTest(raw=raw):
                result = score_response({"x": 1}, raw, "transport_error")
                self.assertFalse(result["success"])
                self.assertIsNone(result["contract_match"])
                self.assertIsNone(result["behavioral_violation"])
                self.assertEqual(result["raw_text"], raw)

    def test_invalid_reference_contract_or_status_fails_fast(self):
        for expected in ([], {"x": float('nan')}, {1: "x"}, {"x": (1, 2)}, {"x": "\ud800"}):
            with self.subTest(expected=repr(expected)):
                with self.assertRaises(ValueError):
                    score_response(expected, '{}')
        with self.assertRaises(ValueError):
            score_response({}, '{}', 'success')
        with self.assertRaises(ValueError):
            score_response({}, None)
        with self.assertRaises(ValueError):
            score_response({}, '{}', 'empty')
        with self.assertRaises(TypeError):
            score_response({}, b'{}')


class FakeClock:
    def __init__(self):
        self.wall = datetime(2026, 10, 24, tzinfo=timezone.utc)
        self.mono = 100.0

    def now(self):
        return self.wall

    def monotonic(self):
        return self.mono

    def advance(self, seconds, *, wall=True, mono=True):
        if wall:
            self.wall += timedelta(seconds=seconds)
        if mono:
            self.mono += seconds


class LedgerControls(unittest.TestCase):
    def setUp(self):
        # Keep synthetic test files within the project on restricted hosts.
        temp_parent = Path(__file__).resolve().parents[2] / 'build' / 'bf01-tests'
        temp_parent.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=temp_parent)
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'ledger.jsonl'
        self.clock = FakeClock()

    def ledger(self, limits=None, resume=False):
        return BudgetLedger(self.path, limits, resume=resume,
                            now_utc=self.clock.now, monotonic=self.clock.monotonic)

    def rows(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def test_reservation_is_persisted_before_caller_action_and_append_only(self):
        ledger = self.ledger()
        opened = self.path.read_bytes()
        start = ledger.reserve('case-1', 'original prompt', task_id='task-1', condition='C0L0')
        prefix = self.path.read_bytes()
        self.assertTrue(prefix.startswith(opened))
        self.assertEqual(self.rows()[-1]['event'], 'started')
        self.assertEqual(start['output_token_limit'], 128)
        self.assertEqual(ledger.pending, ('case-1',))
        result = ledger.finish('case-1', {'x': 1}, '{"x":1}')
        self.assertTrue(self.path.read_bytes().startswith(prefix))
        self.assertEqual(result['event'], 'completed')
        self.assertEqual([r['sequence'] for r in self.rows()], [0, 1, 2])
        self.assertEqual(result['usage'], {'input_tokens': None, 'output_tokens': None, 'total_tokens': None})

    def test_single_inflight_and_no_same_case_retry(self):
        ledger = self.ledger()
        ledger.reserve('one', 'x')
        with self.assertRaises(BudgetError):
            ledger.reserve('two', 'x')
        ledger.finish('one', {}, None, 'transport_error')
        with self.assertRaises(BudgetError):
            ledger.reserve('one', 'x')
        ledger.reserve('two', 'x')
        self.assertEqual(ledger.calls_reserved, 2)

    def test_parallel_threads_cannot_both_reserve(self):
        ledger = self.ledger()
        outcomes = []
        def attempt(case):
            try:
                ledger.reserve(case, 'x')
                outcomes.append('started')
            except BudgetError:
                outcomes.append('blocked')
        threads = [threading.Thread(target=attempt, args=(f'case-{i}',)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertCountEqual(outcomes, ['started', 'blocked'])

    def test_every_failed_attempt_consumes_call_budget(self):
        ledger = self.ledger(Limits(max_calls=2))
        for i in range(2):
            ledger.reserve(str(i), 'x')
            result = ledger.finish(str(i), {}, None, 'transport_error')
            self.assertFalse(result['success'])
        with self.assertRaises(BudgetError):
            ledger.reserve('extra', 'x')
        self.assertEqual(ledger.calls_reserved, 2)

    def test_utf8_bytes_are_counted_instead_of_characters(self):
        ledger = self.ledger()
        ledger.reserve('exact', '\u4e09' * 2000)
        self.assertEqual(self.rows()[-1]['input_bytes'], 6000)
        ledger.finish('exact', {}, '{}')
        with self.assertRaises(BudgetError):
            ledger.reserve('over', '\u4e09' * 2001)
        self.assertEqual(ledger.calls_reserved, 1)

    def test_invalid_reservations_do_not_start_a_call(self):
        ledger = self.ledger()
        for kw in ({'output_token_limit': 513}, {'output_token_limit': True},
                   {'output_token_limit': 0}, {'external_api_dollars': 0.01},
                   {'external_api_dollars': float('nan')}):
            with self.subTest(kw=kw), self.assertRaises(BudgetError):
                ledger.reserve('x', 'x', **kw)
        self.assertEqual(ledger.calls_reserved, 0)
        self.assertEqual(len(self.rows()), 1)

    def test_limits_cannot_silently_increase_or_be_infinite(self):
        for kw in ({'max_calls': 169}, {'max_concurrency': 2}, {'max_seconds': float('inf')},
                   {'max_calls': True}, {'max_response_bytes': 16385}, {'external_api_dollars': 1}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                Limits(**kw)

    def test_wall_or_monotonic_expiry_blocks_start(self):
        for wall, mono in ((True, False), (False, True)):
            with self.subTest(wall=wall):
                self.path = self.path.with_name(f'{wall}.jsonl')
                self.clock = FakeClock()
                ledger = self.ledger()
                self.clock.advance(1200, wall=wall, mono=mono)
                with self.assertRaises(BudgetError):
                    ledger.reserve('late', 'x')

    def test_oversized_raw_response_retained_and_future_calls_halted(self):
        ledger = self.ledger(Limits(max_response_bytes=16))
        ledger.reserve('x', 'x')
        raw = '{"value":"' + 'a' * 20 + '"}'
        result = ledger.finish('x', {'value': 'a' * 20}, raw)
        self.assertFalse(result['success'])
        self.assertTrue(result['score']['success'])
        self.assertEqual(result['score']['raw_text'], raw)
        self.assertEqual(result['budget_breaches'], ['response_bytes'])
        with self.assertRaises(BudgetError):
            ledger.reserve('later', 'x')

    def test_known_token_overrun_and_late_completion_are_failures(self):
        ledger = self.ledger()
        ledger.reserve('x', 'x', output_token_limit=4)
        self.clock.advance(2401)
        result = ledger.finish('x', {}, '{}', usage={'output_tokens': 5})
        self.assertCountEqual(result['budget_breaches'], ['output_tokens', 'elapsed_seconds'])
        self.assertFalse(result['success'])
        self.assertIsNone(result['usage']['input_tokens'])

    def test_undecodable_raw_bytes_are_preserved_not_replaced(self):
        ledger = self.ledger()
        ledger.reserve('x', 'x')
        raw = b'\xff\xfe{"x":'
        result = ledger.finish('x', {}, None, 'transport_error', raw_bytes=raw, error='utf8_decode_error')
        self.assertEqual(base64.b64decode(result['raw_bytes_base64']), raw)
        self.assertEqual(result['response_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertIsNone(result['score']['behavioral_violation'])

    def test_inconsistent_raw_evidence_is_rejected_without_losing_pending(self):
        ledger = self.ledger()
        ledger.reserve('x', 'x')
        with self.assertRaises(ValueError):
            ledger.finish('x', {}, '{}', raw_bytes=b'different')
        self.assertEqual(ledger.pending, ('x',))
        self.assertEqual(len(self.rows()), 2)

    def test_invalid_usage_or_unreserved_completion_is_rejected(self):
        ledger = self.ledger()
        with self.assertRaises(LedgerError):
            ledger.finish('never-started', {}, '{}')
        ledger.reserve('x', 'x')
        for usage in ({'output_tokens': True}, {'output_tokens': -1}, {'output_tokens': 1.5}, {'unknown': 1}):
            with self.subTest(usage=usage), self.assertRaises(ValueError):
                ledger.finish('x', {}, '{}', usage=usage)
        self.assertEqual(ledger.pending, ('x',))

    def test_existing_ledger_cannot_be_overwritten(self):
        self.ledger()
        before = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            self.ledger()
        self.assertEqual(self.path.read_bytes(), before)

    def test_failed_append_halts_in_memory_so_no_call_can_follow_partial_evidence(self):
        ledger = self.ledger()
        with patch.object(Path, 'open', side_effect=OSError('synthetic disk failure')):
            with self.assertRaises(OSError):
                ledger.reserve('first', 'x')
        with self.assertRaises(BudgetError):
            ledger.reserve('second', 'x')
        self.assertEqual(ledger.calls_reserved, 0)

    def test_resume_rejects_corrupted_reservation_and_retains_budget_halt(self):
        ledger = self.ledger(Limits(max_response_bytes=1))
        ledger.reserve('x', 'x')
        ledger.finish('x', {}, '{}')
        resumed = self.ledger(Limits(max_response_bytes=1), resume=True)
        with self.assertRaises(BudgetError):
            resumed.reserve('later', 'x')
        rows = self.rows()
        rows[1]['input_bytes'] = 999
        self.path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
        with self.assertRaises(LedgerError):
            self.ledger(Limits(max_response_bytes=1), resume=True)

    def test_resume_preserves_pending_and_requires_explicit_resolution(self):
        ledger = self.ledger()
        ledger.reserve('unknown', 'x')
        self.clock.advance(3)
        resumed = self.ledger(resume=True)
        self.assertEqual(resumed.calls_reserved, 1)
        with self.assertRaises(BudgetError):
            resumed.reserve('new', 'x')
        result = resumed.finish('unknown', {}, None, 'transport_error', error='process_exit_outcome_unknown')
        self.assertFalse(result['success'])
        resumed.reserve('new', 'x')
        self.assertEqual(resumed.calls_reserved, 2)

    def test_resume_counts_downtime_and_prior_failures(self):
        ledger = self.ledger(Limits(max_calls=1))
        ledger.reserve('x', 'x')
        ledger.finish('x', {}, '', 'empty')
        self.clock.advance(2401)
        self.clock.mono = 0.0
        resumed = self.ledger(Limits(max_calls=1), resume=True)
        self.assertEqual(resumed.calls_reserved, 1)
        with self.assertRaises(BudgetError):
            resumed.reserve('new', 'x')

    def test_resume_rejects_changed_limits_and_incomplete_or_corrupt_evidence(self):
        self.ledger()
        original = self.path.read_bytes()
        with self.assertRaises(LedgerError):
            self.ledger(Limits(max_calls=1), resume=True)
        for broken in (original.rstrip(b'\n'), original + b'{bad}\n', original.replace(b'"sequence": 0', b'"sequence": 3')):
            self.path.write_bytes(broken)
            with self.subTest(broken=broken[:50]), self.assertRaises(LedgerError):
                self.ledger(resume=True)

    def test_clock_rollback_fails_closed(self):
        ledger = self.ledger()
        self.clock.advance(-1, mono=False)
        with self.assertRaises(BudgetError):
            ledger.reserve('x', 'x')
        self.clock.advance(1, mono=False)
        with self.assertRaises(BudgetError):
            ledger.reserve('x', 'x')


if __name__ == '__main__':
    unittest.main()
