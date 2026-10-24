# Adapted from this repository pilot/bf01 (AnimaFoundry, MIT); original unchanged.
"""Offline BF-01B contract scorer and single-owner, append-only budget ledger.

Copyright (c) 2026 AnimaFoundry. MIT; see ../../LICENSE-CODE.

This module performs no inference, network requests, retries, or normalization.
The caller must enforce the reserved token limit and bound transport retrieval.
If an already-received response exceeds a limit, preserve it, record failure,
and prevent further calls; silently truncating it would destroy evidence.
Ledger ownership is single process, with an in-process lock, not a claim of
cross-process locking. A resumed ledger retains pending reservations: resolve
them explicitly with observed evidence or a transport-error outcome before any
new reservation. Never retry an uncertain external action implicitly.
"""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import threading
import time
from typing import Any, Callable


STATUSES = frozenset({"returned", "empty", "truncated", "transport_error"})


class BudgetError(RuntimeError):
    """No further call may be initiated under the requested conditions."""


class LedgerError(ValueError):
    """Ledger evidence is incomplete, inconsistent, or unsupported."""


class _InvalidJSON(ValueError):
    pass


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _validate_value(value: Any) -> None:
    """Reject non-JSON Python values, nonfinite numbers, and invalid Unicode."""
    kind = type(value)
    if value is None or kind in (bool, int):
        return
    if kind is float:
        if not math.isfinite(value):
            raise ValueError("nonfinite number")
        return
    if kind is str:
        value.encode("utf-8", errors="strict")
        return
    if kind is list:
        for item in value:
            _validate_value(item)
        return
    if kind is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("JSON object keys must be strings")
            _validate_value(key)
            _validate_value(item)
        return
    raise ValueError("not a JSON value")


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise _InvalidJSON("duplicate_key")
        result[key] = value
    return result


def _constant(_: str) -> None:
    raise _InvalidJSON("nonfinite_number")


def _matches(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return actual.keys() == expected.keys() and all(
            _matches(actual[key], value) for key, value in expected.items()
        )
    if type(expected) is list:
        return len(actual) == len(expected) and all(
            _matches(a, b) for a, b in zip(actual, expected)
        )
    return actual == expected


def score_response(
    expected: dict[str, Any], raw_text: str | None, status: str = "returned"
) -> dict[str, Any]:
    """Score one initiated case, without modifying or repairing its raw text.

    Success requires complete returned text matching the exact object contract.
    A transport failure has no behavioral label, even if partial text exists.
    Truncation is always task non-success; its observed JSON contract match is
    retained separately. Thus a complete-looking but truncated object need not
    be labeled a behavioral violation. Empty *returned* text is observable and
    violates this nonempty-object contract. No-output transport failure does not.
    """
    if type(expected) is not dict:
        raise ValueError("expected must be a JSON object")
    _validate_value(expected)
    if status not in STATUSES:
        raise ValueError("unsupported response status")
    if raw_text is not None and type(raw_text) is not str:
        raise TypeError("raw_text must be a string or None")
    if status != "transport_error" and raw_text is None:
        raise ValueError("non-transport outcomes require returned text")
    raw = None if raw_text is None else raw_text.encode("utf-8", errors="strict")
    if status == "empty" and raw_text.strip():
        raise ValueError("empty status contradicts nonempty text")
    observed_empty = raw_text is not None and not raw_text.strip()
    effective = "empty" if status == "returned" and observed_empty else status
    result = {
        "schema_version": "bf01b.score.v1",
        "reported_status": status,
        "status": effective,
        "success": False,
        "contract_match": None,
        "behavioral_violation": None,
        "response_observed": raw_text is not None,
        "empty": observed_empty,
        "truncated": status == "truncated",
        "reason": "transport_error",
        "raw_text": raw_text,
        "raw_text_sha256": None if raw is None else _sha(raw),
        "raw_text_bytes": None if raw is None else len(raw),
    }
    if status == "transport_error":
        return result
    reason = "empty_response"
    match = False
    if not observed_empty:
        try:
            actual = json.loads(raw_text, object_pairs_hook=_object, parse_constant=_constant)
            _validate_value(actual)
            if type(actual) is not dict:
                reason = "not_object"
            else:
                match = _matches(actual, expected)
                reason = "ok" if match else "value_or_type_mismatch"
        except _InvalidJSON as exc:
            reason = str(exc)
        except (ValueError, RecursionError):
            reason = "invalid_json"
    result.update(
        success=match and status == "returned",
        contract_match=match,
        behavioral_violation=not match,
        reason="truncated" if status == "truncated" else reason,
        observed_contract_reason=reason,
    )
    return result


@dataclass(frozen=True)
class Limits:
    max_calls: int = 168
    max_input_bytes: int = 6000
    max_output_tokens: int = 128
    max_response_bytes: int = 16384
    max_concurrency: int = 1
    max_seconds: int = 1200
    external_api_dollars: int = 0

    def __post_init__(self) -> None:
        ceilings = {
            "max_calls": 168, "max_input_bytes": 6000, "max_output_tokens": 128,
            "max_response_bytes": 16384, "max_concurrency": 1, "max_seconds": 1200,
        }
        for key, ceiling in ceilings.items():
            value = getattr(self, key)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError(f"{key} must be a positive integer at most {ceiling}")
        if type(self.external_api_dollars) is not int or self.external_api_dollars != 0:
            raise ValueError("external API dollar budget is fixed at zero")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("clock must return an aware UTC timestamp")
    return value.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


class BudgetLedger:
    """Single-owner JSONL ledger; reservations are persisted before caller work.

    Open an existing ledger only with resume=True. Limits must exactly match.
    Corrupt/truncated evidence fails closed. Wall UTC counts downtime on resume;
    monotonic elapsed time prevents same-process clock rollback extending time.
    """

    def __init__(
        self, path: str | Path, limits: Limits | None = None, *, resume: bool = False,
        now_utc: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.path = Path(path)
        self.limits = limits or Limits()
        self._clock = now_utc or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._pending: dict[str, dict[str, Any]] = {}
        self._seen: set[str] = set()
        self._calls = 0
        self._seq = 0
        self._halted = False
        now = _utc(self._clock())
        self._last_utc = now
        self._mono_start = self._read_mono()
        if resume:
            self._replay()
            if now < self._last_utc:
                raise BudgetError("UTC clock precedes persisted evidence")
            self._elapsed_base = (now - self._origin).total_seconds()
            self._last_utc = now
        else:
            self._origin = now
            self._elapsed_base = 0.0
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("x", encoding="utf-8", newline="\n") as handle:
                event = {
                    "schema_version": "bf01b.ledger.v1", "sequence": 0,
                    "event": "opened", "utc": _stamp(now), "limits": asdict(self.limits),
                }
                handle.write(json.dumps(event, ensure_ascii=True, allow_nan=False) + "\n")
                handle.flush()
                import os
                os.fsync(handle.fileno())
            self._seq = 1

    def _read_mono(self) -> float:
        value = self._monotonic()
        if type(value) not in (float, int) or not math.isfinite(value):
            raise BudgetError("invalid monotonic clock")
        return float(value)

    def _elapsed(self) -> tuple[datetime, float]:
        now = _utc(self._clock())
        mono_delta = self._read_mono() - self._mono_start
        if mono_delta < 0 or now < self._last_utc:
            self._halted = True
            raise BudgetError("clock rollback; evidence cannot establish remaining budget")
        elapsed = max((now - self._origin).total_seconds(), self._elapsed_base + mono_delta)
        self._last_utc = now
        return now, elapsed

    def _append(self, event: dict[str, Any], now: datetime) -> dict[str, Any]:
        row = {"schema_version": "bf01b.ledger.v1", "sequence": self._seq,
               "utc": _stamp(now), **event}
        serialized = json.dumps(row, ensure_ascii=True, allow_nan=False)
        try:
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(serialized + "\n")
                handle.flush()
                import os
                os.fsync(handle.fileno())
        except OSError:
            # The disk may contain a partial event; do not continue in memory.
            self._halted = True
            raise
        self._seq += 1
        return row

    def _replay(self) -> None:
        raw = self.path.read_bytes()
        if not raw or not raw.endswith(b"\n"):
            raise LedgerError("incomplete ledger; do not restart or erase pending evidence")
        try:
            rows = [json.loads(line, object_pairs_hook=_object, parse_constant=_constant)
                    for line in raw.decode("utf-8").splitlines()]
            if rows[0]["event"] != "opened" or rows[0]["limits"] != asdict(self.limits):
                raise LedgerError("ledger limits or opening event do not match")
            self._origin = _utc(datetime.fromisoformat(rows[0]["utc"].replace("Z", "+00:00")))
            previous = self._origin
            for index, row in enumerate(rows):
                _validate_value(row)
                if (row["schema_version"] != "bf01b.ledger.v1"
                        or type(row["sequence"]) is not int or row["sequence"] != index):
                    raise LedgerError("unsupported schema or discontinuous sequence")
                stamp = _utc(datetime.fromisoformat(row["utc"].replace("Z", "+00:00")))
                if stamp < previous:
                    raise LedgerError("nonmonotonic UTC event sequence")
                previous = stamp
                if index == 0:
                    continue
                case_id = row["case_id"]
                if type(case_id) is not str or not case_id.strip():
                    raise LedgerError("invalid case identity")
                if row["event"] == "started":
                    if case_id in self._seen or self._pending:
                        raise LedgerError("duplicate case or concurrent reservation")
                    prompt_bytes = row["prompt"].encode("utf-8")
                    cap = row["output_token_limit"]
                    if (row["input_bytes"] != len(prompt_bytes)
                            or len(prompt_bytes) > self.limits.max_input_bytes
                            or row["prompt_sha256"] != _sha(prompt_bytes)
                            or type(cap) is not int or not 1 <= cap <= self.limits.max_output_tokens
                            or row["external_api_dollars_reserved"] != 0
                            or row["attempt_id"] != f"attempt-{self._calls + 1:04d}"):
                        raise LedgerError("reservation evidence or budget does not match")
                    self._seen.add(case_id)
                    self._pending[case_id] = row
                    self._calls += 1
                elif row["event"] in {"completed", "failed"}:
                    start = self._pending.pop(case_id)
                    if row["attempt_id"] != start["attempt_id"]:
                        raise LedgerError("completion does not match reservation")
                    if (type(row["success"]) is not bool
                            or row["success"] != (row["event"] == "completed")
                            or type(row["budget_breaches"]) is not list
                            or set(row["budget_breaches"]).difference(
                                {"response_bytes", "output_tokens", "elapsed_seconds"})):
                        raise LedgerError("invalid completion accounting")
                    self._halted |= bool(row["budget_breaches"])
                else:
                    raise LedgerError("unknown event")
            if self._calls > self.limits.max_calls:
                raise LedgerError("recorded calls exceed budget")
            self._last_utc = previous
            self._seq = len(rows)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise LedgerError("invalid ledger; no new calls permitted") from exc

    @property
    def pending(self) -> tuple[str, ...]:
        return tuple(self._pending)

    @property
    def calls_reserved(self) -> int:
        return self._calls

    def reserve(
        self, case_id: str, prompt: str, *, task_id: str | None = None,
        condition: str | None = None, output_token_limit: int | None = None,
        external_api_dollars: int = 0,
    ) -> dict[str, Any]:
        """Persist started before making one explicit, bounded caller action."""
        if type(case_id) is not str or not case_id.strip() or type(prompt) is not str:
            raise ValueError("case_id and prompt must be strings; case_id cannot be empty")
        if any(value is not None and type(value) is not str for value in (task_id, condition)):
            raise ValueError("task_id and condition must be strings or None")
        raw = prompt.encode("utf-8", errors="strict")
        cap = self.limits.max_output_tokens if output_token_limit is None else output_token_limit
        if type(cap) is not int or not 1 <= cap <= self.limits.max_output_tokens:
            raise BudgetError("output token reservation exceeds fixed limit")
        if type(external_api_dollars) not in (int, float) or external_api_dollars != 0:
            raise BudgetError("external API dollar budget is zero")
        if len(raw) > self.limits.max_input_bytes:
            raise BudgetError("input UTF-8 byte limit exceeded")
        with self._lock:
            now, elapsed = self._elapsed()
            if self._halted or elapsed >= self.limits.max_seconds:
                raise BudgetError("ledger halted or elapsed-time budget exhausted")
            if self._pending:
                raise BudgetError("pending reservation; concurrency is one")
            if case_id in self._seen:
                raise BudgetError("case already initiated; no hidden retry")
            if self._calls >= self.limits.max_calls:
                raise BudgetError("call budget exhausted")
            row = self._append({
                "event": "started", "case_id": case_id,
                "attempt_id": f"attempt-{self._calls + 1:04d}", "task_id": task_id,
                "condition": condition, "prompt": prompt,
                "prompt_sha256": _sha(raw), "input_bytes": len(raw),
                "output_token_limit": cap, "external_api_dollars_reserved": 0,
                "elapsed_seconds": elapsed,
            }, now)
            self._seen.add(case_id)
            self._pending[case_id] = row
            self._calls += 1
            return row

    def finish(
        self, case_id: str, expected: dict[str, Any], raw_text: str | None,
        status: str = "returned", *, raw_bytes: bytes | None = None,
        usage: dict[str, int | None] | None = None, error: str | None = None,
    ) -> dict[str, Any]:
        """Append observed completion/failure, retaining raw response evidence.

        Pass raw_bytes with transport_error for undecodable transport output;
        bytes are preserved as base64 with their hash, never replaced by a flag.
        Missing usage stays null. Known excess usage/response length halts all
        future reservations; the violating response itself is preserved intact.
        """
        if raw_bytes is not None and type(raw_bytes) is not bytes:
            raise TypeError("raw_bytes must be bytes or None")
        if raw_bytes is not None and raw_text is not None and raw_bytes != raw_text.encode("utf-8"):
            raise ValueError("raw byte and text evidence disagree")
        if raw_bytes is not None and raw_text is None and status != "transport_error":
            raise ValueError("undecoded output requires transport_error status")
        if error is not None and type(error) is not str:
            raise TypeError("error must be a string or None")
        score = score_response(expected, raw_text, status)
        values = {"input_tokens": None, "output_tokens": None, "total_tokens": None}
        if usage is not None:
            if type(usage) is not dict or set(usage).difference(values):
                raise ValueError("usage accepts input_tokens, output_tokens, total_tokens only")
            for key, value in usage.items():
                if value is not None and (type(value) is not int or value < 0):
                    raise ValueError("known usage must be a nonnegative integer")
                values[key] = value
        raw = raw_bytes if raw_bytes is not None else (
            None if raw_text is None else raw_text.encode("utf-8")
        )
        with self._lock:
            if case_id not in self._pending:
                raise LedgerError("completion has no pending reservation")
            now, elapsed = self._elapsed()
            start = self._pending[case_id]
            breaches = []
            if raw is not None and len(raw) > self.limits.max_response_bytes:
                breaches.append("response_bytes")
            if values["output_tokens"] is not None and values["output_tokens"] > start["output_token_limit"]:
                breaches.append("output_tokens")
            if elapsed > self.limits.max_seconds:
                breaches.append("elapsed_seconds")
            success = score["success"] and not breaches
            row = self._append({
                "event": "completed" if success else "failed", "case_id": case_id,
                "attempt_id": start["attempt_id"], "elapsed_seconds": elapsed,
                "success": success, "score": score, "usage": values,
                "error": error, "budget_breaches": breaches,
                "raw_bytes_base64": None if raw_bytes is None else base64.b64encode(raw_bytes).decode("ascii"),
                "response_bytes": None if raw is None else len(raw),
                "response_sha256": None if raw is None else _sha(raw),
            }, now)
            del self._pending[case_id]
            self._halted |= bool(breaches)
            return row
