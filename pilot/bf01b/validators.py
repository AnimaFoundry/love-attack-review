"""Four offline BF-01B lanes: raw, fence, object extraction, schema filtering.

Copyright (c) 2026 AnimaFoundry. MIT; see ../../LICENSE-CODE.

No inference, network access, normalization, coercion, or semantic repair.
Only the evaluation oracle in assess() receives an expected answer. The
format-only sanitizer and ordinary schema filter cannot know task truth.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any


class StrictParseError(ValueError):
    """JSON rejected under the declared whole-object response contract."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise StrictParseError("duplicate_key")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise StrictParseError("nonfinite_number")


def _check_values(value: Any) -> None:
    """Also reject overflowing exponents and unpaired Unicode surrogates."""
    if type(value) is float and not math.isfinite(value):
        raise StrictParseError("nonfinite_number")
    if type(value) is str:
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise StrictParseError("invalid_unicode") from exc
    elif type(value) is dict:
        for key, item in value.items():
            _check_values(key)
            _check_values(item)
    elif type(value) is list:
        for item in value:
            _check_values(item)


def strict_parse(text: str) -> dict[str, Any]:
    """Parse the complete text as one JSON object, preserving decoded types.

    JSON whitespace, key order and legal equivalent escapes are accepted.
    Duplicate keys at any depth, nonfinite values and non-object roots fail.
    Floats are valid JSON here; the separate schema rejects float-valued
    observations. No prefix/suffix, fence removal, or normalization occurs.
    """
    if type(text) is not str:
        raise StrictParseError("not_text")
    if not text or all(char in " \t\r\n" for char in text):
        raise StrictParseError("empty_response")
    try:
        value = json.loads(text, object_pairs_hook=_unique_object,
                           parse_constant=_reject_constant)
        _check_values(value)
    except StrictParseError:
        raise
    except (ValueError, RecursionError) as exc:
        raise StrictParseError("invalid_json") from exc
    if type(value) is not dict:
        raise StrictParseError("root_not_object")
    return value


# Narrow declared syntax: lowercase optional json label, newline after the
# opening delimiter, closing delimiter on its own line, ASCII outer whitespace.
# The captured body is returned byte-for-byte as a Python string, including its
# own line endings and whitespace. Internal triple-backticks are not repaired.
_ONE_FENCE = re.compile(
    r"\A[ \t\r\n]*```(?:json)?[ \t]*\r?\n"
    r"(?P<body>[\s\S]*?)^```[ \t]*(?:\r?\n[ \t\r\n]*)?\Z",
    flags=re.MULTILINE,
)


def unwrap_one_fence(text: str) -> str:
    """Remove exactly one whole-response eligible fence, otherwise do nothing.

    This does not parse, trim, reserialize, fix escaping, add missing fields,
    change values, or accept surrounding prose. Uppercase/other language tags,
    nested/multiple fences and inline fences are outside this narrow sanitizer.
    """
    if type(text) is not str:
        raise TypeError("text must be a string")
    if text.count("```") != 2:
        return text
    match = _ONE_FENCE.fullmatch(text)
    return match.group("body") if match else text


MAX_EXTRACTION_BYTES = 16384


def extract_one_object(text: str) -> str:
    """Extract one unambiguous top-level JSON object, or return text unchanged.

    The entire input must fit the 16,384-byte UTF-8 extraction cap. A complete
    valid object is left untouched, including outer whitespace. Otherwise a
    single linear brace/bracket/string-aware scan allows prose around exactly
    one object. Top-level arrays, multiple objects, unmatched/mismatched
    delimiters or unterminated quotes fail closed. Delimiters inside quoted
    strings are ignored. This conservative rule also rejects ambiguous prose.

    The one outer candidate must pass strict_parse; invalid wrappers are never
    retried as nested candidates. Its exact original substring is returned:
    no trimming of its interior, serialization, value changes or oracle input.
    """
    if type(text) is not str:
        raise TypeError("text must be a string")
    if len(text) > MAX_EXTRACTION_BYTES:
        return text
    try:
        if len(text.encode("utf-8", errors="strict")) > MAX_EXTRACTION_BYTES:
            return text
    except UnicodeError:
        return text
    try:
        strict_parse(text)
        return text
    except StrictParseError:
        pass

    stack: list[str] = []
    quoted = escaped = False
    start = end = None
    for index, char in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char in "{[":
            if not stack:
                if char != "{" or start is not None:
                    return text
                start = index
            stack.append(char)
        elif char in "}]":
            if not stack or stack[-1] != {"}": "{", "]": "["}[char]:
                return text
            stack.pop()
            if not stack:
                end = index + 1
    if quoted or stack or start is None or end is None:
        return text
    candidate = text[start:end]
    try:
        strict_parse(candidate)
    except StrictParseError:
        return text
    return candidate


def _schema_cause(obj: Any) -> str | None:
    if type(obj) is not dict:
        return "schema_root_type"
    if any(type(key) is not str for key in obj) or set(obj) != {"state", "value"}:
        return "schema_keys"
    state = obj["state"]
    if type(state) is not str or state not in {"observed", "unknown", "absent"}:
        return "schema_state"
    if state == "observed":
        return None if type(obj["value"]) is int else "schema_observed_integer"
    return None if obj["value"] is None else "schema_unobserved_null"


def schema_validate(obj: Any) -> bool:
    """Check structure/invariants only, with no expected answer or source data.

    Exactly state/value; observed has a Python int decoded from integer JSON
    (never bool or float); unknown/absent have null. Zero is an observation.
    An invented but well-formed integer or a wrong state can pass this filter.
    """
    return _schema_cause(obj) is None


def _exact_equal(actual: Any, expected: Any) -> bool:
    """Evaluation oracle only: exact JSON types, keys and semantic values."""
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return actual.keys() == expected.keys() and all(
            _exact_equal(actual[key], value) for key, value in expected.items()
        )
    if type(expected) is list:
        return len(actual) == len(expected) and all(
            _exact_equal(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def assess(text: str, expected: dict[str, Any]) -> dict[str, Any]:
    """Evaluate all four lanes on the same saved text, with no new inference.

    schema_accept applies after fence removal and object extraction.
    extraction_applied describes that last incremental operation, so a fence
    alone can be repaired without extraction being applied. accepted_correct and
    accepted_wrong partition accepted responses using the separate oracle;
    rejection is not counted as a correct delivered answer. The cause label is
    an evaluation diagnosis, not an input to sanitation or schema acceptance.
    """
    if type(text) is not str:
        raise TypeError("text must be a string")
    if not schema_validate(expected):
        raise ValueError("expected answer must satisfy the declared schema")
    try:
        raw = strict_parse(text)
        raw_parseable = True
    except StrictParseError:
        raw, raw_parseable = None, False

    repaired_text = unwrap_one_fence(text)
    repair_applied = repaired_text != text
    try:
        repaired = strict_parse(repaired_text)
        repaired_parseable = True
    except StrictParseError:
        repaired, repaired_parseable = None, False

    extracted_text = extract_one_object(repaired_text)
    extraction_applied = extracted_text != repaired_text
    try:
        extracted = strict_parse(extracted_text)
        extracted_parseable, parse_cause = True, None
    except StrictParseError as exc:
        extracted, extracted_parseable, parse_cause = None, False, exc.code

    # Sanitizer and filter decisions are complete before invoking the oracle.
    schema_accept = extracted_parseable and schema_validate(extracted)
    raw_correct = raw_parseable and _exact_equal(raw, expected)
    repaired_correct = repaired_parseable and _exact_equal(repaired, expected)
    extracted_correct = extracted_parseable and _exact_equal(extracted, expected)
    if not extracted_parseable:
        cause = parse_cause
    elif not schema_accept:
        cause = _schema_cause(extracted)
    elif not extracted_correct:
        cause = "schema_accepted_wrong"
    elif extraction_applied:
        cause = "correct_after_object_extraction"
    else:
        cause = "correct_after_fence_unwrap" if repair_applied else "raw_correct"
    return {
        "raw_exact_correct": raw_correct,
        "repair_applied": repair_applied,
        "repaired_exact_correct": repaired_correct,
        "raw_parseable": raw_parseable,
        "repaired_parseable": repaired_parseable,
        "extraction_applied": extraction_applied,
        "extracted_text": extracted_text,
        "extracted_parseable": extracted_parseable,
        "extracted_exact_correct": extracted_correct,
        "schema_accept": schema_accept,
        "schema_accepted_correct": schema_accept and extracted_correct,
        "schema_accepted_wrong": schema_accept and not extracted_correct,
        "cause": cause,
    }
