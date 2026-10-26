"""Original deterministic BF-01C source-evidence gate, with no model or network.

Copyright (c) 2026 AnimaFoundry. SPDX-License-Identifier: MIT.
See LICENSE-CODE in this preflight directory for the complete license.

The source is assumed trusted. Its SHA-256 identifies exact UTF-8 content;
neither a matching hash nor this gate authenticates the document or its author.
This module checks consistency with a small, explicit source schema. It does
not certify real-world truth, provenance, or the completeness of the process
that produced a document claiming complete=true.

Rows are zero-based. Strings are compared exactly, without trimming, Unicode
normalization, case folding, coercion or projection. String length limits count
Unicode code points. Both input documents and response texts are bounded to
16,384 UTF-8 bytes; no discarded prefix/suffix or repaired JSON is accepted.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any


MAX_TEXT_BYTES = 16_384
MAX_NAME_LENGTH = 80
MAX_ENTRIES = 64
MIN_VALUE = -(2 ** 31)
MAX_VALUE = 2 ** 31 - 1
_LOWER_SHA256 = re.compile(r"[0-9a-f]{64}")


class InvalidSource(ValueError):
    """The supplied source is malformed, incomplete, or outside the contract."""


class InvalidTarget(ValueError):
    """The externally specified target is not a nonempty string of <=80 chars."""


class _InvalidDocument(ValueError):
    """Internal static diagnostic, never containing arbitrary input text."""


def _object_from_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [name for name, _ in pairs]
    if len(keys) != len(set(keys)):
        raise _InvalidDocument("duplicate_json_member")
    return dict(pairs)


def _forbid_json_constant(_: str) -> None:
    raise _InvalidDocument("nonfinite_json_constant")


def _validate_decoded_values(value: Any) -> None:
    """Reject exponent overflow and lone surrogates after JSON decoding."""
    pending = [value]
    while pending:
        item = pending.pop()
        if type(item) is str:
            try:
                item.encode("utf-8", errors="strict")
            except UnicodeError as exc:
                raise _InvalidDocument("invalid_unicode") from exc
        elif type(item) is float and not math.isfinite(item):
            raise _InvalidDocument("nonfinite_json_number")
        elif type(item) is dict:
            pending.extend(item.keys())
            pending.extend(item.values())
        elif type(item) is list:
            pending.extend(item)


def _read_object(text: str) -> tuple[dict[str, Any], bytes]:
    if type(text) is not str:
        raise _InvalidDocument("text_required")
    # The character precheck bounds allocation before UTF-8 encoding.
    if len(text) > MAX_TEXT_BYTES:
        raise _InvalidDocument("text_byte_limit")
    try:
        raw = text.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise _InvalidDocument("invalid_unicode") from exc
    if len(raw) > MAX_TEXT_BYTES:
        raise _InvalidDocument("text_byte_limit")
    try:
        decoded = json.loads(text, object_pairs_hook=_object_from_pairs,
                             parse_constant=_forbid_json_constant)
    except _InvalidDocument:
        raise
    except (ValueError, RecursionError) as exc:
        raise _InvalidDocument("invalid_json") from exc
    if type(decoded) is not dict:
        raise _InvalidDocument("object_root_required")
    _validate_decoded_values(decoded)
    return decoded, raw


def _name(value: Any) -> bool:
    if type(value) is not str or not 1 <= len(value) <= MAX_NAME_LENGTH:
        return False
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeError:
        return False
    return True


def _positive_integer(value: Any) -> bool:
    return type(value) is int and value > 0


def _measurement(value: Any) -> bool:
    return type(value) is int and MIN_VALUE <= value <= MAX_VALUE


def _source(source_text: str) -> tuple[dict[str, Any], bytes]:
    try:
        source, raw = _read_object(source_text)
        if set(source) != {"document_id", "revision", "complete", "entries"}:
            raise _InvalidDocument("source_members")
        if not _name(source["document_id"]):
            raise _InvalidDocument("source_document_id")
        if not _positive_integer(source["revision"]):
            raise _InvalidDocument("source_revision")
        if source["complete"] is not True:
            raise _InvalidDocument("incomplete_source")
        entries = source["entries"]
        if type(entries) is not list or len(entries) > MAX_ENTRIES:
            raise _InvalidDocument("source_entries")
        seen = set()
        for entry in entries:
            if type(entry) is not dict or set(entry) != {"key", "value"}:
                raise _InvalidDocument("entry_members")
            key = entry["key"]
            if not _name(key):
                raise _InvalidDocument("entry_key")
            if key in seen:
                raise _InvalidDocument("duplicate_entry_key")
            seen.add(key)
            if entry["value"] is not None and not _measurement(entry["value"]):
                raise _InvalidDocument("entry_value")
        return source, raw
    except _InvalidDocument as exc:
        raise InvalidSource(str(exc)) from exc


def _target(target_key: str) -> None:
    if not _name(target_key):
        raise InvalidTarget("target_key_must_be_nonempty_string_of_at_most_80_codepoints")


def _derive(source: dict[str, Any], raw: bytes, target_key: str) -> dict[str, Any]:
    state, value, row = "absent", None, None
    for index, entry in enumerate(source["entries"]):
        if entry["key"] == target_key:
            row, value = index, entry["value"]
            state = "unknown" if value is None else "observed"
            break
    return {
        "state": state,
        "value": value,
        "evidence": {
            "document_id": source["document_id"],
            "revision": source["revision"],
            "sha256": hashlib.sha256(raw).hexdigest(),
            "key": target_key,
            "row": row,
        },
    }


def parse_source(source_text: str, target_key: str) -> dict[str, Any]:
    """Derive the response solely from a valid source and external target.

    Returns a fresh dict containing state/value/evidence. An explicit null is
    unknown and has its actual row; an absent key has state absent and row null.
    A zero-valued observation remains observed. Source validation is performed
    first, then target validation. Raises InvalidSource or InvalidTarget
    (both ValueError subclasses); it never returns an apparent answer for an
    invalid or incomplete source. No answer key is consumed.
    """
    source, raw = _source(source_text)
    _target(target_key)
    return _derive(source, raw, target_key)


def _response(response_text: str) -> dict[str, Any] | None:
    try:
        response, _ = _read_object(response_text)
    except _InvalidDocument:
        return None
    if set(response) != {"state", "value", "evidence"}:
        return None
    state, value = response["state"], response["value"]
    if type(state) is not str or state not in {"observed", "unknown", "absent"}:
        return None
    if state == "observed":
        if not _measurement(value):
            return None
    elif value is not None:
        return None
    evidence = response["evidence"]
    if type(evidence) is not dict or set(evidence) != {"document_id", "revision", "sha256", "key", "row"}:
        return None
    if not _name(evidence["document_id"]) or not _name(evidence["key"]):
        return None
    if not _positive_integer(evidence["revision"]):
        return None
    content_hash = evidence["sha256"]
    if type(content_hash) is not str or not _LOWER_SHA256.fullmatch(content_hash):
        return None
    row = evidence["row"]
    if row is not None and not (type(row) is int and row >= 0):
        return None
    return response


def validate_structure(response_text: str) -> bool:
    """Validate only response syntax and declared structure, without a source.

    A structurally acceptable response may contain fabricated values, stale
    source identity, a wrong target or an out-of-range row. Such acceptance is
    not a claim of source consistency. Row semantics belong to evaluate_gate.
    """
    return _response(response_text) is not None


def evaluate_gate(source_text: str, target_key: str, response_text: str) -> dict[str, Any]:
    """Return source_valid/structural_accept/source_accept/reason, without repair.

    Source accept means exact consistency with this supplied source contract.
    It never means authenticated or independently verified real-world truth.
    Invalid source has diagnostic precedence over invalid target or response.
    Structural acceptance is computed independently even for invalid sources.
    """
    response = _response(response_text)
    result = {"source_valid": False, "structural_accept": response is not None,
              "source_accept": False, "reason": "invalid_source"}
    try:
        source, raw = _source(source_text)
    except InvalidSource:
        return result
    result["source_valid"] = True
    try:
        _target(target_key)
    except InvalidTarget:
        result["reason"] = "invalid_target"
        return result
    if response is None:
        result["reason"] = "invalid_response_structure"
        return result
    derived = _derive(source, raw, target_key)
    evidence, required = response["evidence"], derived["evidence"]
    if any(evidence[name] != required[name] for name in ("document_id", "revision", "sha256")):
        result["reason"] = "source_identity_mismatch"
    elif evidence["key"] != target_key:
        result["reason"] = "target_key_mismatch"
    elif evidence["row"] != required["row"]:
        result["reason"] = "evidence_row_mismatch"
    elif response["state"] != derived["state"] or response["value"] != derived["value"]:
        result["reason"] = "source_semantics_mismatch"
    else:
        result["source_accept"] = True
        result["reason"] = "source_consistent"
    return result
