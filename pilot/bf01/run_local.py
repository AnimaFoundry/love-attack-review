"""Bounded, single-cohort local Ollama pilot. No cloud, retries or automatic pull.

MIT, AnimaFoundry 2026. Supply an unused evidence directory. An existing directory
is never resumed or overwritten; an interrupted run needs an explicit audit.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import platform
import time
import socket
import threading

from evaluate import BudgetLedger, BudgetError, _object, _constant
from prepare import canonical, digest

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 11434
FROZEN_REQUIRED = {"tasks.json", "DESIGN.md", "prepare.py", "cases.jsonl", "evaluate.py",
                   "test_evaluate.py", "run_local.py", "analyze.py", "plan.json",
                   "MODEL-LICENSE.txt", "model-template.txt", "test_runner.py", "PRE_RUN_REVIEW.md"}


class TransportFailure(Exception):
    def __init__(self, code, prefix=b""):
        super().__init__(code)
        self.code = code
        self.prefix = prefix


def fetch(path, payload, deadline):
    """Literal loopback only, no redirect/proxy behavior; absolute read deadline."""
    connection = http.client.HTTPConnection(HOST, PORT)
    pieces = []
    size = 0
    socket_holder = []
    def expire():
        if socket_holder:
            try:
                socket_holder[0].shutdown(socket.SHUT_RDWR)
            except (OSError, AttributeError):
                pass
        connection.close()
    watchdog = threading.Timer(max(0, deadline - time.monotonic()), expire)
    watchdog.daemon = True
    watchdog.start()
    def left():
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise TransportFailure("absolute_deadline", b"".join(pieces))
        return seconds
    try:
        connection.timeout = left()
        connection.connect()
        sock = connection.sock
        socket_holder.append(sock)
        sock.settimeout(left())
        connection.request("GET" if payload is None else "POST", path,
                           body=None if payload is None else canonical(payload).encode(),
                           headers={"Content-Type": "application/json"})
        sock.settimeout(left())
        response = connection.getresponse()
        if response.status != 200:
            raise TransportFailure("http_status_" + str(response.status))
        while True:
            sock.settimeout(left())
            chunk = response.read1(min(4096, 65537 - size))
            if not chunk:
                break
            pieces.append(chunk)
            size += len(chunk)
            if size > 65536:
                raise TransportFailure("body_limit_prefix_only", b"".join(pieces))
        left()
        return b"".join(pieces)
    except TransportFailure:
        raise
    except Exception as exc:
        raise TransportFailure(type(exc).__name__, b"".join(pieces)) from exc
    finally:
        watchdog.cancel()
        connection.close()


def utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def request(path, payload=None, timeout=10, deadline=None):
    limit = time.monotonic() + timeout
    if deadline is not None:
        limit = min(limit, deadline)
    return json.loads(fetch(path, payload, limit))


def model_state(model, deadline=None):
    tags = request("/api/tags", deadline=deadline)
    found = [x for x in tags["models"] if x["name"] == model]
    if len(found) != 1:
        raise ValueError("Expected exact locally installed model tag; no automatic download")
    show = request("/api/show", {"model": model}, deadline=deadline)
    return {"tag": model, "digest": found[0]["digest"], "size_bytes": found[0]["size"],
            "server_version": request("/api/version", deadline=deadline)["version"],
            "template_sha256": digest(show.get("template", "").encode()),
            "system_sha256": digest(show.get("system", "").encode()),
            "parameters": show.get("parameters", ""), "details": show.get("details"),
            "license_sha256": digest(show.get("license", "").encode())}


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n")


def parse_envelope(raw, model_tag, body_complete=True):
    """Derive status solely from the preserved envelope, never a later label."""
    result = {"response": None, "content": None, "status": "transport_error",
              "error": None, "usage": {"input_tokens": None, "output_tokens": None}}
    try:
        value = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
        result["response"] = value
        if not isinstance(value, dict):
            raise ValueError("non_object_envelope")
        content = value.get("message", {}).get("content")
        if isinstance(content, str):
            content.encode("utf-8", errors="strict")
            result["content"] = content
        for key, field in (("input_tokens", "prompt_eval_count"), ("output_tokens", "eval_count")):
            count = value.get(field)
            if count is not None and (type(count) is not int or count < 0):
                raise ValueError("invalid_usage")
            result["usage"][key] = count
        if not body_complete:
            raise ValueError("incomplete_http_body")
        if value.get("model") != model_tag:
            raise ValueError("wrong_model")
        if value.get("done") is not True:
            raise ValueError("incomplete_generation")
        if result["content"] is None:
            raise ValueError("nontext_content")
        if value.get("done_reason") not in {"stop", "length"}:
            raise ValueError("unknown_termination_reason")
        result["status"] = "truncated" if value["done_reason"] == "length" else "returned"
    except (ValueError, TypeError, AttributeError, RecursionError) as exc:
        # Only our static codes or exception class, never arbitrary body text.
        result["error"] = str(exc) if type(exc) is ValueError else type(exc).__name__
    return result


def verify_freeze():
    freeze = json.loads((ROOT / "freeze.json").read_text(encoding="utf-8"))
    names = [entry["path"] for entry in freeze["files"]]
    if len(names) != len(set(names)) or set(names) != FROZEN_REQUIRED:
        raise ValueError("Frozen inventory is incomplete or unexpected")
    for entry in freeze["files"]:
        path = ROOT / entry["path"]
        if path.parent.resolve() != ROOT.resolve() or path.is_symlink():
            raise ValueError("Unsafe frozen path")
        if digest(path.read_bytes()) != entry["sha256"]:
            raise ValueError("Frozen file mismatch: " + entry["path"])
    return freeze


def run(destination):
    freeze = verify_freeze()
    plan = json.loads((ROOT / "plan.json").read_text(encoding="utf-8"))
    if plan["options"]["num_predict"] != 512 or plan["options"]["num_ctx"] != 4096 or plan["options"]["temperature"] != 0:
        raise ValueError("Plan violates fixed pilot generation limits")
    if plan["budget"]["max_calls"] != 72 or plan["budget"]["external_api_dollars"] != 0:
        raise ValueError("Plan violates fixed pilot budget")
    cases = [json.loads(line) for line in (ROOT / "cases.jsonl").read_text(encoding="utf-8").splitlines()]
    state = model_state(plan["model"]["tag"])
    if state != plan["model"]:
        raise ValueError("Local model/runtime metadata differ from the frozen plan")
    # Exclusive directory creation also prevents concurrent owners sharing a run.
    destination.mkdir(parents=True, exist_ok=False)
    write_json(destination / "environment.json", {
        "started_utc": utc(), "model": state, "python": platform.python_version(),
        "os": platform.system(), "os_release": platform.release(),
        "freeze_sha256": digest((ROOT / "freeze.json").read_bytes()),
        "execution": "local loopback only; fresh message array; no tools; no JSON-constrained decoding"})
    ledger = BudgetLedger(destination / "ledger.jsonl")
    start = time.monotonic()
    stopped = None
    attempted = []
    with (destination / "responses.jsonl").open("x", encoding="utf-8", newline="\n") as log:
        for case in cases:
            remaining = 2400 - (time.monotonic() - start)
            if remaining <= 1:
                stopped = "wall_time_before_next_case"
                break
            try:
                if model_state(state["tag"], start + 2400) != state:
                    stopped = "model_or_server_changed"
                    break
            except Exception:
                stopped = "metadata_check_unavailable"
                break
            remaining = 2400 - (time.monotonic() - start)
            if remaining <= 1:
                stopped = "wall_time_after_metadata"
                break
            payload = {"model": state["tag"], "messages": case["messages"],
                       "stream": False, "keep_alive": 0, "options": plan["options"]}
            try:
                ledger.reserve(case["case_id"], canonical(case["messages"]),
                               task_id=case["task_id"], condition=case["condition"])
            except BudgetError as exc:
                stopped = str(exc)
                break
            attempted.append(case["case_id"])
            raw = b""
            value = None
            status = "transport_error"
            content = None
            error = None
            body_complete = False
            call_start = time.monotonic()
            try:
                raw = fetch("/api/chat", payload, min(call_start + 120, start + 2400))
                body_complete = True
            except Exception as exc:
                status = "transport_error"
                if isinstance(exc, TransportFailure):
                    raw = exc.prefix
                    error = exc.code
                else:
                    error = type(exc).__name__
            envelope = parse_envelope(raw, state["tag"], body_complete)
            value, content, status = envelope["response"], envelope["content"], envelope["status"]
            error = error or envelope["error"]
            row = {"case_id": case["case_id"], "condition": case["condition"],
                   "task_id": case["task_id"], "family_id": case["family_id"],
                   "utc": utc(), "latency_seconds": time.monotonic() - call_start,
                   "request_sha256": digest(canonical(payload).encode()),
                   "raw_http_body_base64": base64.b64encode(raw).decode(),
                   "http_body_sha256": digest(raw), "http_body_complete": body_complete,
                   "response": value,
                   "status": status, "error": error}
            log.write(canonical(row) + "\n")
            log.flush()
            os.fsync(log.fileno())
            finished = ledger.finish(case["case_id"], case["expected_json"], content, status,
                                     usage=envelope["usage"],
                                     error=error)
            print(canonical({"completed": len(attempted), "case_id": case["case_id"],
                             "success": finished["success"], "reason": finished["score"]["reason"]}), flush=True)
            if status == "transport_error" or finished["budget_breaches"]:
                # A client timeout is NOT evidence of server cancellation: do not retry.
                stopped = "transport_uncertainty_or_budget_breach"
                break
    write_json(destination / "completion.json", {
        "finished_utc": utc(), "planned": len(cases), "initiated": len(attempted),
        "not_attempted": [c["case_id"] for c in cases if c["case_id"] not in attempted],
        "stop_reason": stopped, "external_api_dollars": 0,
        "retries": 0, "auxiliary_inference_calls": 0,
        "elapsed_seconds": time.monotonic() - start,
        "status": "COMPLETE" if len(attempted) == len(cases) and not stopped else "INCOMPLETE"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    run(parser.parse_args().destination)
