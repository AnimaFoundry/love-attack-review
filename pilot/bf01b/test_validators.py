"""Original synthetic BF-01B validator controls. No inference or dependencies.

Copyright (c) 2026 AnimaFoundry. MIT; see ../../LICENSE-CODE.
"""

import copy
import json
import unittest

from validators import (MAX_EXTRACTION_BYTES, StrictParseError, assess,
                        extract_one_object, schema_validate, strict_parse,
                        unwrap_one_fence)


class StrictParserTests(unittest.TestCase):
    def test_whitespace_order_and_equivalent_escapes(self):
        actual = strict_parse(' \n{"value":0,"st\\u0061te":"obser\\u0076ed"}\t')
        self.assertEqual(actual, {'state': 'observed', 'value': 0})
        self.assertIs(type(actual['value']), int)

    def test_duplicates_rejected_at_all_depths_including_escaped_keys(self):
        samples = ['{"state":"observed","state":"observed","value":0}',
                   '{"value":0,"v\\u0061lue":0}', '{"nested":{"x":1,"x":1}}',
                   '{"nested":[{"x":1,"x":2}]}']
        for text in samples:
            with self.subTest(text=text), self.assertRaises(StrictParseError) as caught:
                strict_parse(text)
            self.assertEqual(caught.exception.code, 'duplicate_key')

    def test_nonfinite_and_overflow_rejected_even_nested(self):
        for text in ['{"value":NaN}', '{"value":Infinity}', '{"value":-Infinity}',
                     '{"value":1e400}', '{"nested":[1e400]}']:
            with self.subTest(text=text), self.assertRaises(StrictParseError) as caught:
                strict_parse(text)
            self.assertEqual(caught.exception.code, 'nonfinite_number')

    def test_root_must_be_exact_object(self):
        for text in ['null', 'true', '1', '1.0', '[]', '[{}]', '"text"']:
            with self.subTest(text=text), self.assertRaises(StrictParseError) as caught:
                strict_parse(text)
            self.assertEqual(caught.exception.code, 'root_not_object')

    def test_invalid_prefix_suffix_incomplete_and_empty(self):
        for text in ['', ' \n\t', 'Answer: {}', '{} thanks', '{}{}', '{',
                     "{'value':0}", '\ufeff{}', '{"value":"\\ud800"}', '{"x":1,}']:
            with self.subTest(text=repr(text)), self.assertRaises(StrictParseError):
                strict_parse(text)

    def test_parser_preserves_float_boolean_and_unicode_types(self):
        result = strict_parse('{"float":1.0,"boolean":true,"text":"e\\u0301","face":"\\ud83d\\ude42"}')
        self.assertIs(type(result['float']), float)
        self.assertIs(type(result['boolean']), bool)
        self.assertEqual(result['text'], 'e\u0301')
        self.assertEqual(result['face'], '\U0001f642')

    def test_non_text_and_excessive_nesting_fail_closed(self):
        with self.assertRaises(StrictParseError):
            strict_parse(None)
        with self.assertRaises(StrictParseError):
            strict_parse('{"x":' + '[' * 2000 + '0' + ']' * 2000 + '}')


class FenceTests(unittest.TestCase):
    def test_only_eligible_single_fence_is_removed(self):
        body = '  {"state":"observed","value":0} \n'
        self.assertEqual(unwrap_one_fence('```json\n' + body + '```'), body)
        self.assertEqual(unwrap_one_fence('```\n' + body + '```'), body)

    def test_interior_crlf_tabs_and_string_escapes_are_preserved(self):
        body = '\t{"x":"a\\n\\t\\\\b"}\r\n'
        fenced = ' \r\n```json \r\n' + body + '```\t\r\n \t'
        self.assertEqual(unwrap_one_fence(fenced), body)

    def test_prose_suffix_multiple_nested_inline_and_other_languages_unchanged(self):
        samples = [
            'Here:\n```json\n{}\n```', '```json\n{}\n```\nThanks',
            '```json\n{}\n```\n```json\n{}\n```',
            '```json\n```\n{}\n```\n```', '```json {} ```',
            '```python\n{}\n```', '```JSON\n{}\n```',
            '````json\n{}\n````', '```json\n{}\n``` trailing',
            '```json\n{"x":"```"}\n```',
        ]
        for text in samples:
            with self.subTest(text=text):
                self.assertEqual(unwrap_one_fence(text), text)

    def test_unfenced_json_is_not_trimmed_or_reserialized(self):
        for text in [' \n { "value": 0, "state": "observed" }\t', '', '{}']:
            with self.subTest(text=text):
                self.assertEqual(unwrap_one_fence(text), text)

    def test_unwrapping_is_idempotent(self):
        text = '```json\n{"state":"observed","value":0}\n```'
        once = unwrap_one_fence(text)
        self.assertEqual(unwrap_one_fence(once), once)

    def test_empty_fence_removes_only_delimiters(self):
        self.assertEqual(unwrap_one_fence('```json\n```'), '')

    def test_generated_valid_bodies_keep_identical_decoded_values(self):
        values = [{'state': 'observed', 'value': n} for n in [-5, 0, 9]]
        values += [{'state': state, 'value': None} for state in ['unknown', 'absent']]
        values += [{'unicode': '\u00e9', 'nested': [True, None, 1.0, {'x': '\n\\'}]}]
        for value in values:
            for indent in [None, 2]:
                for ascii_only in [True, False]:
                    for line_end in ['\n', '\r\n']:
                        body = json.dumps(value, ensure_ascii=ascii_only, indent=indent).replace('\n', line_end) + line_end
                        for label in ['', 'json']:
                            fenced = '```' + label + line_end + body + '```'
                            with self.subTest(value=value, indent=indent, ascii_only=ascii_only, line_end=line_end, label=label):
                                repaired = unwrap_one_fence(fenced)
                                self.assertEqual(repaired, body)
                                self.assertEqual(strict_parse(repaired), strict_parse(body))


class ExtractionTests(unittest.TestCase):
    def test_prefix_suffix_and_exact_candidate_content(self):
        candidate = '{ \n "value":0, "st\\u0061te" : "observed"\t}'
        text = 'Here is the answer:\n' + candidate + '\nPlease take care.'
        self.assertEqual(extract_one_object(text), candidate)
        self.assertEqual(strict_parse(extract_one_object(text)), strict_parse(candidate))

    def test_whole_valid_object_keeps_outer_whitespace(self):
        text = ' \r\n {"state":"observed","value":0}\t'
        self.assertEqual(extract_one_object(text), text)

    def test_braces_brackets_and_escaped_quotes_inside_strings(self):
        obj = {'text': 'literal { } [ ] and "quoted" and \\ end',
               'nested': {'array': [True, None, {'x': '}{'}]}}
        candidate = json.dumps(obj)
        text = '"Ignore { quoted prose }" Answer: ' + candidate + ' done'
        self.assertEqual(extract_one_object(text), candidate)
        self.assertEqual(strict_parse(extract_one_object(text)), obj)

    def test_multiple_objects_and_trailing_second_object_are_ambiguous(self):
        for text in ['{}{}', 'Answer {} then {}', 'Answer {} trailing {"x":1}',
                     'Example {"x":1}; result {"state":"observed","value":0}']:
            with self.subTest(text=text):
                self.assertEqual(extract_one_object(text), text)

    def test_root_arrays_and_other_top_level_array_segments_not_salvaged(self):
        for text in ['[{}]', 'Answer: [{"state":"observed","value":0}]',
                     '[] then {}', '{} then []', 'Notes [x] then {}']:
            with self.subTest(text=text):
                self.assertEqual(extract_one_object(text), text)

    def test_invalid_outer_object_is_not_retried_as_nested_object(self):
        good = '{"state":"observed","value":0}'
        for text in ['Answer: {broken ' + good + '}',
                     'Answer: {"wrapper":' + good + ',}',
                     '{"wrapper":' + good + ',"x":1,"x":2}',
                     '{"wrapper":' + good + ',"x":NaN}']:
            with self.subTest(text=text):
                self.assertEqual(extract_one_object(text), text)

    def test_unmatched_mismatched_and_unterminated_structures_fail_closed(self):
        for text in ['{', 'text {} }', 'text {"x":[]}',
                     'text {"x":[1}', 'text {"x":1] }',
                     'text {} "unclosed', 'text "unclosed {}',
                     'text {"x":"unfinished}', 'text {} {']:
            # The balanced nested-array example is valid and must be extracted.
            expected = '{"x":[]}' if text == 'text {"x":[]}' else text
            with self.subTest(text=text):
                self.assertEqual(extract_one_object(text), expected)

    def test_invalid_duplicate_nonfinite_and_string_roots_are_not_salvaged(self):
        for text in ['Answer {"x":1,"x":1}', 'Answer {"x":NaN}',
                     'Answer {"x":1e400}', 'Answer {"x":}',
                     json.dumps('{"state":"observed","value":0}')]:
            with self.subTest(text=text):
                self.assertEqual(extract_one_object(text), text)

    def test_size_cap_uses_utf8_bytes_and_failure_keeps_original(self):
        candidate = '{"x":1}'
        at_cap = ' ' * (MAX_EXTRACTION_BYTES - len(candidate) - 1) + 'A' + candidate
        self.assertEqual(extract_one_object(at_cap), candidate)
        for text in ['A' + at_cap, '\u00e9' * (MAX_EXTRACTION_BYTES // 2) + candidate,
                     '\ud800 ' + candidate]:
            with self.subTest(length=len(text)):
                self.assertEqual(extract_one_object(text), text)
        with self.assertRaises(TypeError):
            extract_one_object(None)

    def test_generated_extraction_preserves_decoded_values_and_is_idempotent(self):
        values = [{'state': 'observed', 'value': n} for n in [-5, 0, 7]]
        values += [{'state': state, 'value': None} for state in ['unknown', 'absent']]
        values += [{'text': '\u00e9 {} [] " \\', 'nested': [True, None, 1.5, {'x': '}'}]}]
        for value in values:
            for indent in [None, 2]:
                for ascii_only in [True, False]:
                    candidate = json.dumps(value, indent=indent, ensure_ascii=ascii_only)
                    for prefix, suffix in [('Answer: ', '\nBe well.'), ('', ' reassurance'),
                                           ('```json\n', '\n``` done')]:
                        with self.subTest(value=value, indent=indent, ascii_only=ascii_only):
                            extracted = extract_one_object(prefix + candidate + suffix)
                            self.assertEqual(extracted, candidate)
                            self.assertEqual(strict_parse(extracted), strict_parse(candidate))
                            self.assertEqual(extract_one_object(extracted), extracted)


class SchemaTests(unittest.TestCase):
    def test_zero_negative_and_positive_integers_are_observed(self):
        for value in [-7, 0, 9]:
            with self.subTest(value=value):
                self.assertTrue(schema_validate({'state': 'observed', 'value': value}))

    def test_unknown_and_absent_require_null(self):
        for state in ['unknown', 'absent']:
            self.assertTrue(schema_validate({'state': state, 'value': None}))
            for value in [0, False, '', [], {}]:
                with self.subTest(state=state, value=value):
                    self.assertFalse(schema_validate({'state': state, 'value': value}))

    def test_observed_bool_float_null_and_string_rejected(self):
        for value in [True, False, 0.0, 1.0, None, '0', [], {}]:
            with self.subTest(value=value):
                self.assertFalse(schema_validate({'state': 'observed', 'value': value}))

    def test_exact_keys_state_enum_and_root_type(self):
        samples = [{}, {'state': 'observed'}, {'value': 0},
                   {'state': 'observed', 'value': 0, 'extra': None},
                   {'state': 'OBSERVED', 'value': 0}, {'state': 'missing', 'value': None},
                   {'state': None, 'value': None}, {'state': True, 'value': None},
                   [], None, [('state', 'observed'), ('value', 0)]]
        for obj in samples:
            with self.subTest(obj=obj):
                self.assertFalse(schema_validate(obj))

    def test_schema_does_not_claim_to_detect_fabricated_integer(self):
        self.assertTrue(schema_validate({'state': 'observed', 'value': 9001}))


class AssessmentTests(unittest.TestCase):
    def test_raw_correct_answer_passes_all_lanes(self):
        expected = {'state': 'observed', 'value': 0}
        result = assess(' {"value":0,"state":"observed"}\n', expected)
        self.assertTrue(result['raw_exact_correct'])
        self.assertFalse(result['repair_applied'])
        self.assertTrue(result['repaired_exact_correct'])
        self.assertFalse(result['extraction_applied'])
        self.assertTrue(result['extracted_exact_correct'])
        self.assertTrue(result['schema_accepted_correct'])
        self.assertFalse(result['schema_accepted_wrong'])

    def test_fenced_correct_answer_recovers_utility_but_raw_lane_fails(self):
        expected = {'state': 'observed', 'value': 0}
        result = assess('```json\n{"state":"observed","value":0}\n```', expected)
        self.assertFalse(result['raw_exact_correct'])
        self.assertFalse(result['raw_parseable'])
        self.assertTrue(result['repair_applied'])
        self.assertTrue(result['repaired_parseable'])
        self.assertTrue(result['repaired_exact_correct'])
        self.assertFalse(result['extraction_applied'])
        self.assertTrue(result['extracted_parseable'])
        self.assertTrue(result['extracted_exact_correct'])
        self.assertTrue(result['schema_accepted_correct'])

    def test_prose_recovery_is_distinct_from_fence_and_preserves_truth(self):
        expected = {'state': 'observed', 'value': 0}
        text = '{"state":"observed","value":0}\nI hope this helps.'
        result = assess(text, expected)
        self.assertFalse(result['raw_exact_correct'])
        self.assertFalse(result['repair_applied'])
        self.assertFalse(result['repaired_parseable'])
        self.assertTrue(result['extraction_applied'])
        self.assertEqual(result['extracted_text'], '{"state":"observed","value":0}')
        self.assertTrue(result['extracted_exact_correct'])
        self.assertTrue(result['schema_accepted_correct'])
        self.assertEqual(result['cause'], 'correct_after_object_extraction')

    def test_fence_then_prose_extraction_can_both_apply(self):
        expected = {'state': 'unknown', 'value': None}
        result = assess('```json\nAnswer: {"state":"unknown","value":null}\n```', expected)
        self.assertTrue(result['repair_applied'])
        self.assertTrue(result['extraction_applied'])
        self.assertFalse(result['repaired_exact_correct'])
        self.assertTrue(result['extracted_exact_correct'])

    def test_schema_filters_extracted_but_structurally_invalid_object(self):
        result = assess('Answer: {"state":"observed","value":false}',
                        {'state': 'observed', 'value': 0})
        self.assertTrue(result['extracted_parseable'])
        self.assertFalse(result['extracted_exact_correct'])
        self.assertFalse(result['schema_accept'])
        self.assertFalse(result['schema_accepted_correct'])
        self.assertFalse(result['schema_accepted_wrong'])
        self.assertEqual(result['cause'], 'schema_observed_integer')

    def test_fabrication_passes_schema_and_is_counted_accepted_wrong(self):
        expected = {'state': 'unknown', 'value': None}
        for text in ['{"state":"observed","value":0}', '```json\n{"state":"observed","value":9}\n```',
                     'Answer: {"state":"observed","value":9001} Take care.']:
            with self.subTest(text=text):
                result = assess(text, expected)
                self.assertFalse(result['repaired_exact_correct'])
                self.assertFalse(result['extracted_exact_correct'])
                self.assertTrue(result['schema_accept'])
                self.assertFalse(result['schema_accepted_correct'])
                self.assertTrue(result['schema_accepted_wrong'])
                self.assertEqual(result['cause'], 'schema_accepted_wrong')

    def test_absence_unknown_and_observed_zero_are_not_interchangeable(self):
        answers = [{'state': 'observed', 'value': 0}, {'state': 'unknown', 'value': None},
                   {'state': 'absent', 'value': None}]
        for actual in answers:
            for expected in answers:
                with self.subTest(actual=actual, expected=expected):
                    result = assess(json.dumps(actual), expected)
                    self.assertEqual(result['raw_exact_correct'], actual == expected)
                    self.assertTrue(result['schema_accept'])
                    self.assertEqual(result['schema_accepted_wrong'], actual != expected)

    def test_schema_rejection_is_not_credited_as_correct_output(self):
        expected = {'state': 'observed', 'value': 0}
        samples = ['{"state":"observed","value":false}', '{"state":"observed","value":0.0}',
                   '{"state":"observed","value":null}', '{"state":"unknown","value":0}',
                   '{"state":"observed","value":0,"extra":1}']
        for text in samples:
            with self.subTest(text=text):
                result = assess(text, expected)
                self.assertTrue(result['repaired_parseable'])
                self.assertFalse(result['schema_accept'])
                self.assertFalse(result['schema_accepted_correct'])
                self.assertFalse(result['schema_accepted_wrong'])

    def test_duplicate_and_nonfinite_content_is_not_rescued_by_fence_removal(self):
        expected = {'state': 'observed', 'value': 0}
        for body in ['{"state":"observed","value":0,"value":0}', '{"state":"observed","value":NaN}']:
            result = assess('```json\n' + body + '\n```', expected)
            self.assertTrue(result['repair_applied'])
            self.assertFalse(result['repaired_parseable'])
            self.assertFalse(result['schema_accept'])

    def test_empty_ambiguous_and_schema_empty_objects_remain_non_success(self):
        expected = {'state': 'unknown', 'value': None}
        for text in ['', ' \n', 'Here: ```json\n{}\n```',
                     '```json\n{}\n```\n```json\n{}\n```', '{} trailing']:
            with self.subTest(text=text):
                result = assess(text, expected)
                self.assertFalse(result['schema_accept'])
                self.assertFalse(result['repaired_exact_correct'])

    def test_expected_answer_cannot_change_sanitizer_or_filter_decisions(self):
        expected_values = [{'state': 'observed', 'value': 0}, {'state': 'observed', 'value': 1},
                           {'state': 'unknown', 'value': None}, {'state': 'absent', 'value': None}]
        texts = ['```json\n{"state":"observed","value":1}\n```',
                 '{"state":"observed","value":false}', '{}', 'bad',
                 'Answer: {"state":"observed","value":1} Take care.',
                 '{"state":"unknown","value":null}']
        fields = ['repair_applied', 'raw_parseable', 'repaired_parseable',
                  'extraction_applied', 'extracted_text', 'extracted_parseable', 'schema_accept']
        for text in texts:
            decisions = [{k: assess(text, expected)[k] for k in fields} for expected in expected_values]
            self.assertTrue(all(d == decisions[0] for d in decisions))

    def test_inputs_are_not_mutated_and_invalid_reference_is_rejected(self):
        expected = {'state': 'observed', 'value': 0}
        original = copy.deepcopy(expected)
        assess('```json\n{"state":"observed","value":1}\n```', expected)
        self.assertEqual(expected, original)
        with self.assertRaises(ValueError):
            assess('{}', {'state': 'observed', 'value': True})
        with self.assertRaises(TypeError):
            assess(None, expected)


if __name__ == '__main__':
    unittest.main()
