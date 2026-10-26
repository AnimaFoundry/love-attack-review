"""One-shot bounded BF-01C local runner. MIT; see LICENSE-CODE.

Only literal loopback HTTP is used. http.client does not consult proxy settings
or follow redirects. A socket-shutdown watchdog enforces an absolute deadline.
The output contract is scored separately from this delivery/collection layer.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import socket
import threading
import time

from envelope import MAX_BODY_BYTES, strict_object, validate_envelope
from freeze import verify_freeze

HOST, PORT = "127.0.0.1", 11434
REQUIRED_FROZEN = {
    "config.json", "requests.json", "tasks.json", "schema_no_evidence.json",
    "schema_evidence.json", "envelope.py", "freeze.py", "run_local.py",
    "contracts.py", "evidence_gate.py",
    "prepare_study.py", "score.py", "PLAN.md", "PRE_RUN_REVIEW.md",
    "test_runtime.py", "test_score.py", "test_evidence_gate.py", "test_contracts.py",
    "fixtures.json", "LICENSE-CODE", "LICENSE-TEXT", "MODEL-LICENSE.txt", "model-template.txt",
    "verify_saved.py", "test_saved.py",
    "test_deadline.py",
}
_ID = re.compile(r"[A-Za-z0-9_-]{1,100}")


class TransportFailure(Exception):
    def __init__(self, code, body=b"", status=None):
        super().__init__(code)
        self.code, self.body, self.status = code, body, status


def _utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8", errors="strict")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _fetch(path, payload, timeout, *, absolute_deadline=None):
    """Read one fixed local endpoint with a bounded body and hard deadline."""
    if path not in {"/api/chat", "/api/tags", "/api/show", "/api/version"}:
        raise ValueError("endpoint_not_allowlisted")
    if not 0 < timeout <= 30:
        raise ValueError("timeout_outside_limit")
    now = time.monotonic()
    deadline = now + timeout
    if absolute_deadline is not None:
        deadline = min(deadline, absolute_deadline)
    remaining = deadline - now
    if remaining <= 0:
        raise TransportFailure("absolute_deadline")
    connection = http.client.HTTPConnection(HOST, PORT, timeout=remaining)
    sockets, chunks = [], []
    received, status = 0, None

    def expire():
        for sock in sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        connection.close()

    def left():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TransportFailure("absolute_deadline", b"".join(chunks), status)
        return remaining

    watchdog = threading.Timer(remaining, expire)
    watchdog.daemon = True
    watchdog.start()
    try:
        connection.connect()
        sock = connection.sock
        sockets.append(sock)
        sock.settimeout(left())
        connection.request("GET" if payload is None else "POST", path,
                           body=payload, headers={"Content-Type": "application/json"})
        sock.settimeout(left())
        response = connection.getresponse()
        status = response.status
        while True:
            sock.settimeout(left())
            chunk = response.read1(min(4096, MAX_BODY_BYTES + 1 - received))
            if not chunk:
                break
            chunks.append(chunk)
            received += len(chunk)
            if received > MAX_BODY_BYTES:
                raise TransportFailure("body_limit", b"".join(chunks), status)
        left()
        if response.length not in (None, 0):
            raise TransportFailure("incomplete_http", b"".join(chunks), status)
        return {"status": status, "body": b"".join(chunks), "complete": True}
    except TransportFailure:
        raise
    except http.client.IncompleteRead as exc:
        if type(exc.partial) is bytes:
            chunks.append(exc.partial)
        raise TransportFailure("incomplete_http", b"".join(chunks), status) from exc
    except Exception as exc:
        raise TransportFailure(type(exc).__name__, b"".join(chunks), status) from exc
    finally:
        watchdog.cancel()
        connection.close()


def collect_metadata(model):
    """Query allowlisted local metadata only; this function never generates."""
    def get(path, payload=None):
        response = _fetch(path, None if payload is None else _canonical(payload), 10)
        if response["status"] != 200 or not response["complete"]:
            raise ValueError("metadata_http_failure")
        return strict_object(response["body"])

    tags = get("/api/tags")
    models = tags.get("models")
    if type(models) is not list:
        raise ValueError("invalid_tags_metadata")
    found = [row for row in models if type(row) is dict and row.get("name") == model]
    if len(found) != 1:
        raise ValueError("exact_installed_model_required")
    tag = found[0]
    if type(tag.get("digest")) is not str or not re.fullmatch(r"[0-9a-f]{64}", tag["digest"]):
        raise ValueError("invalid_model_digest")
    if type(tag.get("size")) is not int or tag["size"] <= 0:
        raise ValueError("invalid_model_size")
    show, version = get("/api/show", {"model": model}), get("/api/version")
    if type(version.get("version")) is not str or not version["version"]:
        raise ValueError("invalid_server_version")
    for key in ("template", "system", "parameters", "license"):
        if type(show.get(key, "")) is not str:
            raise ValueError("invalid_show_metadata")
    if type(show.get("details")) is not dict:
        raise ValueError("invalid_model_details")
    return {"tag": model, "digest": tag["digest"], "size_bytes": tag["size"],
            "server_version": version["version"],
            "template_sha256": _sha(show.get("template", "").encode("utf-8")),
            "system_sha256": _sha(show.get("system", "").encode("utf-8")),
            "parameters": show.get("parameters", ""), "details": show["details"],
            "license_sha256": _sha(show.get("license", "").encode("utf-8"))}


def _write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def _append(path, value):
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=True, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _load(root):
    manifest = verify_freeze(root)
    if not REQUIRED_FROZEN <= {row["path"] for row in manifest["files"]}:
        raise ValueError("incomplete_frozen_inventory")
    config = strict_object((root / "config.json").read_bytes())
    requests = strict_object(b'{"items":' + (root / "requests.json").read_bytes() + b'}')["items"]
    limits = config.get("limits")
    expected = {"max_calls": 32, "per_call_seconds": 30, "global_seconds": 600,
                "max_generated_tokens": 8192, "max_body_bytes": MAX_BODY_BYTES}
    if type(limits) is not dict or set(limits) != set(expected):
        raise ValueError("invalid_limit_keys")
    if any(type(limits[k]) is not int or limits[k] != v for k, v in expected.items()):
        raise ValueError("limits_must_match_frozen_ceiling")
    if config.get("study_id") != "BF01C" or type(config.get("model")) is not str or not config["model"]:
        raise ValueError("invalid_study_model")
    if type(config.get("expected_metadata")) is not dict or not config["expected_metadata"]:
        raise ValueError("expected_metadata_required")
    options = config.get("options")
    if type(options) is not dict or type(options.get("num_predict")) is not int or options["num_predict"] != 256:
        raise ValueError("num_predict_must_be_256")
    if type(requests) is not list or len(requests) != 32:
        raise ValueError("exact_32_request_schedule_required")
    ids, pairs = set(), {}
    for row in requests:
        if type(row) is not dict or set(row) != {"request_id", "input_id", "arm", "mode", "contract", "request_body"}:
            raise ValueError("invalid_schedule_entry")
        for key in ("request_id", "input_id", "arm"):
            if type(row[key]) is not str or not _ID.fullmatch(row[key]):
                raise ValueError("invalid_schedule_identifier")
        if row["request_id"] in ids:
            raise ValueError("duplicate_request_id")
        ids.add(row["request_id"])
        pair = (row["mode"], row["contract"])
        if pair not in {("raw", "no_evidence"), ("raw", "evidence"), ("schema", "no_evidence"), ("schema", "evidence")}:
            raise ValueError("invalid_condition")
        old = pairs.setdefault(row["input_id"], set())
        if pair in old:
            raise ValueError("duplicate_condition")
        old.add(pair)
        body = row["request_body"]
        keys = {"model", "messages", "stream", "options"} | ({"format"} if row["mode"] == "schema" else set())
        if type(body) is not dict or set(body) != keys or body["model"] != config["model"] or body["stream"] is not False or body["options"] != options:
            raise ValueError("request_not_frozen_configuration")
        messages = body["messages"]
        if type(messages) is not list or not messages or len(messages) > 3:
            raise ValueError("invalid_messages")
        for message in messages:
            if type(message) is not dict or set(message) != {"role", "content"} or message["role"] not in {"system", "user"} or type(message["content"]) is not str:
                raise ValueError("invalid_message")
        if messages[-1]["role"] != "user":
            raise ValueError("final_user_message_required")
        if row["mode"] == "schema":
            schema = strict_object((root / ("schema_" + row["contract"] + ".json")).read_bytes())
            if body["format"] != schema:
                raise ValueError("request_schema_mismatch")
        _canonical(body)
    if len(pairs) != 8 or any(len(v) != 4 for v in pairs.values()):
        raise ValueError("eight_complete_paired_inputs_required")
    if (requests[0]["mode"], requests[0]["contract"]) != ("schema", "evidence"):
        raise ValueError("first_call_must_test_constrained_evidence")
    return config, requests


def run(study_root: Path, *, transport=None, metadata=None, clock=None, utcnow=None):
    """Run once, journaling before sends; injectable dependencies are for tests."""
    root = Path(study_root)
    config, requests = _load(root)
    clock, utcnow = clock or time.monotonic, utcnow or _utc
    # start is assigned after the pre-run metadata phase, before any dispatch.
    transport = transport or (lambda body, timeout: _fetch(
        "/api/chat", body, timeout, absolute_deadline=start + 600))
    metadata = metadata or (lambda: collect_metadata(config["model"]))
    destination = root / "run"
    if destination.exists():
        raise FileExistsError("run_directory_already_exists")
    pinned_freeze = _sha((root / "FREEZE.json").read_bytes())
    _write_json(root / "RUN_GUARD.json", {"study_id": "BF01C", "created_utc": utcnow(),
                "freeze_sha256": pinned_freeze, "rule": "No resume, retry or second cohort."})
    destination.mkdir()
    (destination / "requests").mkdir()
    (destination / "responses").mkdir()
    (destination / "initiation.jsonl").touch(exist_ok=False)
    (destination / "records.jsonl").touch(exist_ok=False)
    initiated, completed, output_tokens, usage_complete = [], [], 0, True
    stop_reason, metadata_ok, metadata_match, freeze_unchanged = None, False, False, True

    def frozen():
        if _sha((root / "FREEZE.json").read_bytes()) != pinned_freeze:
            raise ValueError("freeze_manifest_drift")
        verify_freeze(root)

    try:
        before = metadata()
        _write_json(destination / "metadata_before.json", before)
        if before != config["expected_metadata"]:
            stop_reason = "metadata_drift"
        else:
            metadata_ok = True
    except Exception as exc:
        stop_reason = "metadata_error"
        _write_json(destination / "metadata_before_error.json", {"error_type": type(exc).__name__})
    start = clock()
    for row in requests:
        if stop_reason is not None:
            break
        try:
            frozen()
        except (ValueError, OSError):
            freeze_unchanged = False
            stop_reason = "freeze_drift"
            break
        elapsed = clock() - start
        if elapsed >= 600:
            stop_reason = "global_budget"
            break
        if len(initiated) >= 32 or output_tokens + 256 > 8192:
            stop_reason = "token_budget"
            break
        timeout = min(30, 600 - elapsed)
        request_id = row["request_id"]
        request_path = "run/requests/" + request_id + ".json"
        response_path = "run/responses/" + request_id + ".bin"
        raw_request = _canonical(row["request_body"])
        with (root / request_path).open("xb") as stream:
            stream.write(raw_request)
            stream.flush()
            os.fsync(stream.fileno())
        entry = {key: row[key] for key in ("request_id", "input_id", "arm", "mode", "contract")}
        entry.update(started_utc=utcnow(), request_body_path=request_path,
                     request_sha256=_sha(raw_request), timeout_seconds=timeout)
        _append(destination / "initiation.jsonl", entry)
        initiated.append(request_id)
        call_start = clock()
        error, raw_body, status, complete = None, b"", None, False
        sent, dispatch_timeout = False, 0
        transport_status = "error"
        remaining = 600 - (clock() - start)
        if remaining <= 0:
            # The reserved slot is retained even if durable journaling exhausted
            # the global budget before a network dispatch was attempted.
            error, stop_reason = "global_budget_before_send", "global_budget"
        else:
            dispatch_timeout = min(timeout, remaining)
            try:
                # sent means the transport was invoked, not server receipt.
                sent = True
                outcome = transport(raw_request, dispatch_timeout)
                if type(outcome) is not dict or type(outcome.get("body")) is not bytes or type(outcome.get("status")) is not int or type(outcome.get("complete")) is not bool:
                    raise ValueError("invalid_transport_result")
                raw_body, status, complete = outcome["body"], outcome["status"], outcome["complete"]
                transport_status = "ok" if complete else "incomplete"
            except Exception as exc:
                error = getattr(exc, "code", type(exc).__name__)
                raw_body = getattr(exc, "body", b"")
                status = getattr(exc, "status", None)
                if type(raw_body) is not bytes:
                    raw_body = b""
                stop_reason = "transport_error"
        duration = clock() - call_start
        if len(raw_body) > MAX_BODY_BYTES:
            complete = False
            transport_status = "incomplete"
            stop_reason = stop_reason or "invalid_envelope:body_limit_or_type"
        envelope = validate_envelope(status, raw_body, config["model"], http_complete=complete)
        if sent and duration > dispatch_timeout:
            envelope["valid"] = False
            envelope["delivery_complete"] = False
            envelope["reason"] = "per_call_budget"
            stop_reason = stop_reason or "per_call_budget"
        if clock() - start >= 600:
            stop_reason = stop_reason or "global_budget"
        if type(envelope["eval_count"]) is int:
            output_tokens += envelope["eval_count"]
        else:
            usage_complete = False
        if output_tokens > 8192:
            stop_reason = stop_reason or "token_budget"
        if not complete:
            stop_reason = stop_reason or "incomplete_http"
        elif not envelope["valid"] and envelope["reason"] != "empty_content":
            stop_reason = stop_reason or "invalid_envelope:" + envelope["reason"]
        if envelope["delivery_complete"]:
            completed.append(request_id)
        with (root / response_path).open("xb") as stream:
            stream.write(raw_body)
            stream.flush()
            os.fsync(stream.fileno())
        entry.update(finished_utc=utcnow(), duration_seconds=duration,
                     sent=sent, dispatch_timeout_seconds=dispatch_timeout,
                     transport_status=transport_status, http_status=status,
                     body_complete=complete, envelope=envelope, error=error,
                     response_body_path=response_path, response_sha256=_sha(raw_body))
        _append(destination / "records.jsonl", entry)
    try:
        frozen()
    except (ValueError, OSError):
        freeze_unchanged = False
        stop_reason = stop_reason or "freeze_drift"
    inference_wall_seconds = clock() - start
    if metadata_ok:
        try:
            after = metadata()
            _write_json(destination / "metadata_after.json", after)
            if after != config["expected_metadata"]:
                stop_reason = stop_reason or "metadata_drift"
            else:
                metadata_match = True
        except Exception as exc:
            stop_reason = stop_reason or "metadata_error"
            _write_json(destination / "metadata_after_error.json", {"error_type": type(exc).__name__})
    summary = {"status": "completed" if stop_reason is None and len(initiated) == 32 else "stopped",
               "initiated_calls": len(initiated), "completed_calls": len(completed),
               "initiated_request_ids": initiated, "completed_request_ids": completed,
               "unattempted_request_ids": [r["request_id"] for r in requests if r["request_id"] not in initiated],
               "output_tokens": output_tokens, "usage_complete": usage_complete,
               "metadata_match": metadata_match, "freeze_unchanged": freeze_unchanged,
               "budget_ok": usage_complete and output_tokens <= 8192 and inference_wall_seconds <= 600 and stop_reason not in {"per_call_budget", "global_budget", "token_budget"},
               "inference_wall_seconds": inference_wall_seconds,
               "stop_reason": stop_reason, "finished_utc": utcnow(),
               "freeze_sha256": pinned_freeze, "external_api_cost_usd": 0,
               "model": config["model"], "limits": config["limits"]}
    _write_json(destination / "summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    report = run(args.root)
    print(json.dumps({key: report[key] for key in
                      ("status", "initiated_calls", "completed_calls", "output_tokens", "usage_complete", "stop_reason")}))
