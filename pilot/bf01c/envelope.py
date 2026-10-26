"""Strict non-streaming local response delivery checks. MIT; see LICENSE-CODE.

Delivery validation is separate from output-content correctness. No inference,
repair, tool execution or network access occurs in this module.
"""
from __future__ import annotations

import json
import math
from typing import Any

MAX_BODY_BYTES = 1_048_576


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate_member")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("nonfinite_number")


def strict_object(body: bytes, maximum: int = MAX_BODY_BYTES) -> dict[str, Any]:
    """Parse exact UTF-8 bytes without BOM, duplicates or invalid scalars."""
    if type(body) is not bytes or len(body) > maximum or body.startswith(b"\xef\xbb\xbf"):
        raise ValueError("invalid_body_bytes")
    try:
        obj = json.loads(body.decode("utf-8", errors="strict"),
                         object_pairs_hook=_pairs, parse_constant=_constant)
        if type(obj) is not dict:
            raise ValueError("object_required")
        pending = [obj]
        while pending:
            value = pending.pop()
            if type(value) is str:
                value.encode("utf-8", errors="strict")
            elif type(value) is float and not math.isfinite(value):
                raise ValueError("nonfinite_number")
            elif type(value) is dict:
                pending.extend(value.keys())
                pending.extend(value.values())
            elif type(value) is list:
                pending.extend(value)
        return obj
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid_json_bytes") from exc


def validate_envelope(http_status: int, body: bytes, expected_model: str,
                      *, http_complete: bool = True) -> dict[str, Any]:
    """Validate delivery and usage, preserving content for separate scoring.

    Empty/whitespace content has valid=False and delivery_complete=True when
    the envelope is otherwise complete. It is a content failure, not a reason
    to retry or silently replace the call. All other invalid envelopes have
    delivery_complete=False and must stop the finite cohort.
    """
    result = {"valid": False, "reason": "incomplete_http", "content": None,
              "eval_count": None, "prompt_eval_count": None,
              "delivery_complete": False}
    if http_complete is not True:
        return result
    if type(http_status) is not int or http_status != 200:
        result["reason"] = "http_status"
        return result
    if type(body) is not bytes or len(body) > MAX_BODY_BYTES:
        result["reason"] = "body_limit_or_type"
        return result
    try:
        obj = strict_object(body)
    except ValueError:
        result["reason"] = "invalid_envelope_json"
        return result
    if "error" in obj:
        result["reason"] = "api_error"
        return result
    if type(expected_model) is not str or obj.get("model") != expected_model:
        result["reason"] = "model_mismatch"
        return result
    if obj.get("done") is not True or obj.get("done_reason") != "stop":
        result["reason"] = "not_complete_stop"
        return result
    message = obj.get("message")
    if type(message) is not dict or message.get("role") != "assistant":
        result["reason"] = "invalid_assistant_message"
        return result
    if set(message) - {"role", "content", "thinking", "tool_calls"}:
        result["reason"] = "unexpected_message_field"
        return result
    if "tool_calls" in message and message["tool_calls"] not in (None, []):
        result["reason"] = "unexpected_tools"
        return result
    if "thinking" in message and message["thinking"] not in (None, ""):
        result["reason"] = "unexpected_thinking"
        return result
    if "tool_calls" in obj and obj["tool_calls"] not in (None, []):
        result["reason"] = "unexpected_tools"
        return result
    if "thinking" in obj and obj["thinking"] not in (None, ""):
        result["reason"] = "unexpected_thinking"
        return result
    content = message.get("content")
    if type(content) is not str:
        result["reason"] = "content_not_string"
        return result
    count, prompt_count = obj.get("eval_count"), obj.get("prompt_eval_count")
    if type(count) is not int or not 0 <= count <= 256:
        result["reason"] = "invalid_eval_count"
        return result
    if type(prompt_count) is not int or prompt_count < 0:
        result["reason"] = "invalid_prompt_eval_count"
        return result
    result.update(content=content, eval_count=count, prompt_eval_count=prompt_count,
                  delivery_complete=True)
    if not content.strip():
        result["reason"] = "empty_content"
    else:
        result.update(valid=True, reason="complete")
    return result
