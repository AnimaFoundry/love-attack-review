"""Offline BF-01C response contracts and exact UTF-8 byte boundary.

Copyright (c) 2026 AnimaFoundry. SPDX-License-Identifier: MIT.
See LICENSE-CODE. No model, network, answer key, fixture ID or repair is used.

The two accompanying Draft 2020-12 schemas describe decoded JSON value shapes.
They do not enforce this module's raw-byte limit, strict UTF-8/no-BOM boundary,
duplicate-member rejection or lexical integer requirement. In particular JSON
Schema's integer type can accept the decoded value 1.0; this wire contract does
not. Schema validation alone is therefore not the complete acceptance rule.

The unchanged source parser is a shared dependency of both contracts. The
source-aware gates derive from the supplied closed record, not an independent
observation of reality. A matching hash identifies bytes, not authentic authors,
real-world truth or completeness. This is an established deterministic lookup
baseline, not a general factuality defense or claimed new product.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

from evidence_gate import InvalidSource, InvalidTarget, parse_source


MAX_TEXT_BYTES = 16_384
MAX_NAME_LENGTH = 80
MIN_VALUE = -(2 ** 31)
MAX_VALUE = 2 ** 31 - 1
MAX_ROW = 63
_HASH = re.compile(r"[0-9a-f]{64}")
_CONTRACTS = {"no_evidence", "evidence"}


def _contract(contract: str) -> None:
    if type(contract) is not str or contract not in _CONTRACTS:
        raise ValueError("contract_must_be_no_evidence_or_evidence")


def decode_utf8(data: bytes) -> str:
    """Decode exact bytes without coercion, replacement, stripping or repair.

    A UTF-8 byte-order marker at the start is rejected. Interior U+FEFF is
    ordinary string data, not a transport marker. Empty bytes decode to an empty
    string; JSON/source/response validity is checked by the appropriate parser.
    """
    if type(data) is not bytes:
        raise ValueError("bytes_required")
    if len(data) > MAX_TEXT_BYTES:
        raise ValueError("text_byte_limit")
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError("byte_order_mark_forbidden")
    try:
        return data.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ValueError("invalid_utf8") from exc


def _unique_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_member")
        result[key] = value
    return result


def _forbid_constant(_: str) -> None:
    raise ValueError("nonfinite_json_constant")


def _read_response(data: bytes) -> dict[str, Any] | None:
    try:
        text = decode_utf8(data)
        value = json.loads(text, object_pairs_hook=_unique_members,
                           parse_constant=_forbid_constant)
        if type(value) is not dict:
            return None
        pending = [value]
        while pending:
            item = pending.pop()
            if type(item) is str:
                item.encode("utf-8", errors="strict")
            elif type(item) is float and not math.isfinite(item):
                return None
            elif type(item) is dict:
                pending.extend(item.keys())
                pending.extend(item.values())
            elif type(item) is list:
                pending.extend(item)
    except (ValueError, UnicodeError, RecursionError):
        return None
    return value


def _name(value: Any) -> bool:
    # _read_response has already rejected invalid Unicode scalar values.
    return type(value) is str and 1 <= len(value) <= MAX_NAME_LENGTH


def _measurement(value: Any) -> bool:
    return type(value) is int and MIN_VALUE <= value <= MAX_VALUE


def _response(data: bytes, contract: str) -> dict[str, Any] | None:
    response = _read_response(data)
    required = {"state", "value"}
    if contract == "evidence":
        required.add("evidence")
    if response is None or set(response) != required:
        return None
    state, value = response["state"], response["value"]
    if type(state) is not str or state not in {"observed", "unknown", "absent"}:
        return None
    if state == "observed":
        if not _measurement(value):
            return None
    elif value is not None:
        return None
    if contract == "no_evidence":
        return response
    evidence = response["evidence"]
    if type(evidence) is not dict or set(evidence) != {
            "document_id", "revision", "sha256", "key", "row"}:
        return None
    if not _name(evidence["document_id"]) or not _name(evidence["key"]):
        return None
    revision = evidence["revision"]
    if type(revision) is not int or revision < 1:
        return None
    content_hash = evidence["sha256"]
    if type(content_hash) is not str or not _HASH.fullmatch(content_hash):
        return None
    row = evidence["row"]
    if state == "absent":
        if row is not None:
            return None
    elif type(row) is not int or not 0 <= row <= MAX_ROW:
        return None
    return response


def validate_response(response_bytes: bytes, contract: str) -> bool:
    """Check the named response contract without reading source evidence.

    A plausible false value, in-range wrong row or well-formed stale identity
    can pass. Contract absence is not a missing-evidence failure: no_evidence
    explicitly requires only state/value and disallows an evidence member.
    """
    _contract(contract)
    return _response(response_bytes, contract) is not None


def derive_response(source_bytes: bytes, target_key: str, contract: str) -> dict[str, Any]:
    """Derive either response solely from source bytes and external target.

    Invalid bytes are InvalidSource; the unchanged source parser distinguishes
    a malformed/incomplete source from InvalidTarget. Invalid contracts raise
    ValueError before inspecting source data. Returned dicts are fresh values.
    """
    _contract(contract)
    try:
        source_text = decode_utf8(source_bytes)
    except ValueError as exc:
        raise InvalidSource(str(exc)) from exc
    response = parse_source(source_text, target_key)
    if contract == "no_evidence":
        return {"state": response["state"], "value": response["value"]}
    return response


def evaluate_response(source_bytes: bytes, target_key: str,
                      response_bytes: bytes, contract: str) -> dict[str, Any]:
    """Report structure and source consistency without correcting the response.

    Source errors precede target and response diagnostics; structure remains a
    source-blind result even if the source or target is invalid. True source
    acceptance means consistency with this supplied record under its closed
    producer assumptions. No external authenticity claim follows.
    """
    _contract(contract)
    response = _response(response_bytes, contract)
    result = {"source_valid": False, "structural_accept": response is not None,
              "source_accept": False, "reason": "invalid_source"}
    try:
        derived = derive_response(source_bytes, target_key, contract)
    except InvalidTarget:
        result["source_valid"] = True
        result["reason"] = "invalid_target"
        return result
    except InvalidSource:
        return result
    result["source_valid"] = True
    if response is None:
        result["reason"] = "invalid_response_structure"
        return result
    if contract == "evidence":
        evidence, required = response["evidence"], derived["evidence"]
        if any(evidence[name] != required[name]
               for name in ("document_id", "revision", "sha256")):
            result["reason"] = "source_identity_mismatch"
            return result
        if evidence["key"] != target_key:
            result["reason"] = "target_key_mismatch"
            return result
        if evidence["row"] != required["row"]:
            result["reason"] = "evidence_row_mismatch"
            return result
    if response["state"] != derived["state"] or response["value"] != derived["value"]:
        result["reason"] = "source_semantics_mismatch"
    else:
        result["source_accept"] = True
        result["reason"] = "source_consistent"
    return result
