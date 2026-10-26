"""Independent saved-byte/ledger replay for BF-01C. MIT; see LICENSE-CODE.

No inference or network requests are made. This checks consistency of retained
artifacts, not external authenticity or whether a recorded clock was truthful.
An internally consistent stopped prefix is auditable; an unmatched initiation,
changed freeze or unsupported completion claim fails closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from envelope import MAX_BODY_BYTES, strict_object, validate_envelope
from freeze import verify_freeze
from run_local import _load
from score import score_study

HERE = Path(__file__).resolve().parent
IDENTITY = ("request_id", "input_id", "arm", "mode", "contract")
INIT_KEYS = set(IDENTITY) | {"started_utc", "request_body_path", "request_sha256", "timeout_seconds"}
RECORD_KEYS = INIT_KEYS | {"finished_utc", "duration_seconds", "transport_status", "http_status",
                         "body_complete", "envelope", "error", "response_body_path", "response_sha256",
                         "sent", "dispatch_timeout_seconds"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def same(left, right):
    """JSON equality that does not equate bool/int or int/float notation."""
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def read_bytes(root, relative):
    path = root / relative
    require(path.resolve().is_relative_to(root.resolve()), "artifact_path_escaped_root")
    current = path
    while current != root:
        require(not current.is_symlink() and not (hasattr(current, "is_junction") and current.is_junction()),
                "linked_artifact_forbidden")
        current = current.parent
    return path.read_bytes()


def obj(root, relative):
    return strict_object(read_bytes(root, relative))


def rows(root, relative):
    result = []
    for line in read_bytes(root, relative).splitlines():
        require(bool(line.strip()), "blank_journal_record")
        result.append(strict_object(line))
    return result


def finite_nonnegative(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def exact_directory(root, relative, names):
    directory = root / relative
    require(directory.is_dir() and not directory.is_symlink(), "artifact_directory_required")
    actual = set()
    for path in directory.iterdir():
        require(path.is_file() and not path.is_symlink(), "unexpected_artifact_entry")
        actual.add(path.name)
    require(actual == set(names), "raw_artifact_inventory_mismatch")


def metadata_state(root, config, stage):
    value_path = f"run/metadata_{stage}.json"
    error_path = f"run/metadata_{stage}_error.json"
    has_value, has_error = (root / value_path).is_file(), (root / error_path).is_file()
    require(not (has_value and has_error), "ambiguous_metadata_record")
    if has_value:
        return "match" if same(obj(root, value_path), config["expected_metadata"]) else "drift"
    if has_error:
        failure = obj(root, error_path)
        require(type(failure.get("error_type")) is str and bool(failure["error_type"]), "invalid_metadata_error_record")
        return "error"
    return "missing"


def verify_run(study_root, check_score=False):
    root = Path(study_root).resolve()
    verify_freeze(root)
    config, schedule = _load(root)
    pinned_hash = sha(read_bytes(root, "FREEZE.json"))
    guard, summary = obj(root, "RUN_GUARD.json"), obj(root, "run/summary.json")
    require(guard.get("study_id") == "BF01C" and guard.get("freeze_sha256") == pinned_hash,
            "guard_freeze_hash_mismatch")
    require(summary.get("freeze_sha256") == pinned_hash, "summary_freeze_hash_mismatch")
    require(summary.get("freeze_unchanged") is True, "reported_freeze_drift_requires_separate_audit")
    require(same(summary.get("limits"), config["limits"]) and summary.get("model") == config["model"],
            "summary_configuration_mismatch")
    require(type(summary.get("external_api_cost_usd")) is int and summary["external_api_cost_usd"] == 0,
            "unexpected_external_api_cost")
    journal, records = rows(root, "run/initiation.jsonl"), rows(root, "run/records.jsonl")
    require(len(journal) == len(records) <= 32, "unmatched_or_excessive_initiations")
    actual_ids = [row.get("request_id") for row in journal]
    require(actual_ids == [row["request_id"] for row in schedule[:len(journal)]], "initiation_not_schedule_prefix")
    require([row.get("request_id") for row in records] == actual_ids, "record_journal_identity_mismatch")
    require(len(set(actual_ids)) == len(actual_ids), "duplicate_initiation_id")
    completed_ids, known_tokens, usage_complete, duration_sum = [], 0, True, 0.0
    sent_calls, unsent_reservations = 0, 0
    terminal_reason = None
    terminal_precedes_global = False
    any_call_budget_failure = False
    for index, (planned, initiated, recorded) in enumerate(zip(schedule, journal, records)):
        require(set(initiated) == INIT_KEYS and set(recorded) == RECORD_KEYS, "ledger_member_mismatch")
        require(all(same(initiated[key], recorded[key]) for key in INIT_KEYS), "record_initiation_fields_mismatch")
        require(all(same(recorded[key], planned[key]) for key in IDENTITY), "record_schedule_fields_mismatch")
        require(terminal_reason is None, "request_after_terminal_failure")
        rid = planned["request_id"]
        request_path, response_path = f"run/requests/{rid}.json", f"run/responses/{rid}.bin"
        require(recorded["request_body_path"] == request_path and recorded["response_body_path"] == response_path,
                "unexpected_raw_artifact_path")
        request_raw, response_raw = read_bytes(root, request_path), read_bytes(root, response_path)
        require(request_raw == canonical(planned["request_body"]), "frozen_request_bytes_mismatch")
        require(recorded["request_sha256"] == sha(request_raw), "request_hash_mismatch")
        require(recorded["response_sha256"] == sha(response_raw), "response_hash_mismatch")
        timeout, duration = recorded["timeout_seconds"], recorded["duration_seconds"]
        require(finite_nonnegative(timeout) and 0 < timeout <= 30, "invalid_recorded_timeout")
        require(finite_nonnegative(duration), "invalid_recorded_duration")
        sent, dispatch_timeout = recorded["sent"], recorded["dispatch_timeout_seconds"]
        require(type(sent) is bool and finite_nonnegative(dispatch_timeout), "invalid_dispatch_metadata")
        if sent:
            require(0 < dispatch_timeout <= timeout, "invalid_dispatch_timeout")
            sent_calls += 1
        else:
            require(dispatch_timeout == 0 and duration == 0 and response_raw == b"" and
                    recorded["http_status"] is None and recorded["body_complete"] is False and
                    recorded["transport_status"] == "error" and
                    recorded["error"] == "global_budget_before_send", "invalid_unsent_reservation")
            unsent_reservations += 1
        duration_sum += duration
        require(type(recorded["body_complete"]) is bool, "invalid_http_completion_flag")
        transport = recorded["transport_status"]
        require(transport in {"ok", "incomplete", "error"}, "invalid_transport_status")
        if recorded["error"] is not None:
            require(type(recorded["error"]) is str and bool(recorded["error"]), "invalid_transport_error")
            require(recorded["body_complete"] is False, "errored_transport_marked_complete")
            terminal_reason = "transport_error" if sent else "global_budget"
            terminal_precedes_global = True
        else:
            require(transport != "error", "missing_transport_error")
            require(type(recorded["http_status"]) is int, "invalid_http_status_type")
        if len(response_raw) > MAX_BODY_BYTES:
            require(transport == "incomplete" and recorded["body_complete"] is False, "oversized_body_marked_complete")
            terminal_reason = terminal_reason or "invalid_envelope:body_limit_or_type"
            terminal_precedes_global = True
        elif recorded["error"] is None:
            require(transport == ("ok" if recorded["body_complete"] else "incomplete"), "transport_completion_mismatch")
        expected_envelope = validate_envelope(recorded["http_status"], response_raw, config["model"],
                                              http_complete=recorded["body_complete"])
        if sent and duration > dispatch_timeout:
            any_call_budget_failure = True
            expected_envelope.update(valid=False, delivery_complete=False, reason="per_call_budget")
            terminal_reason = terminal_reason or "per_call_budget"
            terminal_precedes_global = True
        require(same(recorded["envelope"], expected_envelope), "saved_envelope_does_not_match_raw_bytes")
        count = expected_envelope["eval_count"]
        if type(count) is int:
            known_tokens += count
        else:
            usage_complete = False
        if expected_envelope["delivery_complete"]:
            completed_ids.append(rid)
        if not recorded["body_complete"]:
            terminal_reason = terminal_reason or "incomplete_http"
        elif not expected_envelope["valid"] and expected_envelope["reason"] != "empty_content":
            terminal_reason = terminal_reason or "invalid_envelope:" + expected_envelope["reason"]
        if terminal_reason is not None:
            require(index == len(records) - 1, "continued_after_invalid_delivery")
    exact_directory(root, "run/requests", [f"{rid}.json" for rid in actual_ids])
    exact_directory(root, "run/responses", [f"{rid}.bin" for rid in actual_ids])
    before, after = metadata_state(root, config, "before"), metadata_state(root, config, "after")
    require(before != "missing", "missing_initial_metadata_evidence")
    if before != "match":
        require(not actual_ids and after == "missing", "inference_after_initial_metadata_failure")
    else:
        require(after != "missing", "missing_final_metadata_evidence")
    metadata_match = before == after == "match"
    require(summary.get("metadata_match") is metadata_match, "metadata_summary_mismatch")
    wall = summary.get("inference_wall_seconds")
    require(finite_nonnegative(wall) and duration_sum <= wall + 1e-6, "inconsistent_inference_wall_time")
    require(not unsent_reservations or wall >= 600, "unsent_reservation_without_elapsed_global_budget")
    reason = summary.get("stop_reason")
    # The global deadline may have been reached in overhead between calls;
    # a per-call duration alone cannot reconstruct that overhead.
    if before != "match":
        expected_reason = "metadata_error" if before == "error" else "metadata_drift"
    elif terminal_reason is not None:
        expected_reason = terminal_reason
        if wall >= 600 and reason == "global_budget" and not terminal_precedes_global:
            expected_reason = "global_budget"
    elif wall >= 600:
        expected_reason = "global_budget"
    elif known_tokens > 8192 or (len(records) < 32 and known_tokens + 256 > 8192):
        expected_reason = "token_budget"
    elif after != "match":
        expected_reason = "metadata_error" if after == "error" else "metadata_drift"
    else:
        expected_reason = None
    require(reason == expected_reason, "unsubstantiated_stop_reason")
    require(reason is not None or len(records) == 32, "incomplete_prefix_without_stop_reason")
    budget_ok = (usage_complete and known_tokens <= 8192 and wall <= 600 and
                 not any_call_budget_failure and reason not in {"per_call_budget", "global_budget", "token_budget"})
    expected_summary = {
        "initiated_calls": len(records), "completed_calls": len(completed_ids),
        "initiated_request_ids": actual_ids, "completed_request_ids": completed_ids,
        "unattempted_request_ids": [row["request_id"] for row in schedule[len(records):]],
        "output_tokens": known_tokens, "usage_complete": usage_complete,
        "budget_ok": budget_ok, "status": "completed" if reason is None and len(records) == 32 else "stopped",
    }
    for key, value in expected_summary.items():
        require(same(summary.get(key), value), "recomputed_summary_mismatch:" + key)
    tasks = obj(root, "tasks.json")
    schemas = {contract: obj(root, f"schema_{contract}.json") for contract in ("no_evidence", "evidence")}
    report = score_study(tasks, schedule, records, summary, schemas)
    report["saved_evidence_verification"] = {
        "initiations": len(journal), "raw_request_response_pairs": len(records),
        "envelope_replay": "MATCHED_RETAINED_BYTES", "authenticity_claim": False,
    }
    if check_score:
        require(same(obj(root, "run/score.json"), report), "saved_score_mismatch")
    return {
        "status": "VERIFIED_COMPLETE" if summary["status"] == "completed" else "VERIFIED_STOPPED_PREFIX",
        "initiated_calls": len(records), "completed_calls": len(completed_ids),
        "sent_calls": sent_calls, "unsent_reservations": unsent_reservations,
        "known_output_tokens": known_tokens, "usage_complete": usage_complete,
        "unattempted_request_ids": expected_summary["unattempted_request_ids"],
        "metadata_match": metadata_match, "budget_ok": budget_ok, "stop_reason": reason,
        "raw_envelopes_rederived": len(records), "score_checked": bool(check_score),
        "freeze_sha256": pinned_hash, "score": report,
        "scope": "Saved-artifact consistency replay, not second inference or external authenticity verification.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=HERE)
    parser.add_argument("--check", action="store_true", help="Also compare the saved score.json exactly")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_run(args.root, check_score=args.check)
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(result, stream, indent=2, ensure_ascii=True)
            stream.write("\n")
    print(json.dumps({key: value for key, value in result.items() if key != "score"}))


if __name__ == "__main__":
    main()
