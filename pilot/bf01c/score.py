"""Deterministic, no-repair BF-01C saved-response scorer.

Copyright (c) 2026 AnimaFoundry. MIT; see LICENSE-CODE.
No model, network, output repair or fixture answer lookup is used by a gate.
The manually authored task expectations are used here only as evaluation oracles.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator
from contracts import decode_utf8, derive_response, evaluate_response, validate_response
from envelope import validate_envelope
from freeze import verify_freeze

HERE = Path(__file__).resolve().parent
ARMS = ("schema_evidence", "raw_no_evidence", "schema_no_evidence", "raw_evidence")


def _no_constant(_):
    raise ValueError("nonfinite")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_member")
        result[key] = value
    return result


def strict_object(content):
    """Whole bounded JSON object, unique members and Unicode scalars; no repair.

    Numeric notation is retained by Python's decoded int/float types, permitting
    separate strict-contract and semantic-value evaluation.
    """
    try:
        if type(content) is not str:
            return None
        text = decode_utf8(content.encode("utf-8", errors="strict"))
        value = json.loads(text, object_pairs_hook=_unique, parse_constant=_no_constant)
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
        return value
    except (ValueError, UnicodeError, RecursionError):
        return None


def _value_equal(actual, expected):
    if expected is None:
        return actual is None
    if type(expected) is int:
        if type(actual) is int:
            return actual == expected
        return type(actual) is float and math.isfinite(actual) and actual == expected
    return type(actual) is type(expected) and actual == expected


def reference(task, contract):
    expected = task["expected"]
    result = {"state": expected["state"], "value": expected["value"]}
    if contract == "evidence":
        result["evidence"] = {**task["trusted_metadata"], "key": task["target_key"], "row": expected["row"]}
    return result


def _semantic_correct(obj, expected):
    if obj is None or "state" not in obj or "value" not in obj:
        return None
    return type(obj["state"]) is str and obj["state"] == expected["state"] and _value_equal(obj["value"], expected["value"])


def _binding_correct(obj, expected):
    if obj is None or type(obj.get("evidence")) is not dict:
        return None
    evidence = obj["evidence"]
    if any(key not in evidence for key in expected):
        return None
    return all(_value_equal(evidence[key], value) for key, value in expected.items())


def schema_valid(content, schema):
    """Pure decoded-value schema comparator; duplicate names are last-wins here.

    This intentionally does NOT claim wire safety. It is scored alongside the
    strict unique-member parser, so schema-only acceptance of duplicate members
    or integer-valued floating notation remains visible.
    """
    try:
        value = json.loads(content, parse_constant=_no_constant)
        return Draft202012Validator(schema).is_valid(value)
    except (ValueError, TypeError, RecursionError, OverflowError):
        return False


def score_record(task, request, record, schemas):
    for key in ("request_id", "input_id", "arm", "mode", "contract"):
        if record.get(key) != request[key]:
            raise ValueError("record_schedule_identity_mismatch")
    envelope = record.get("envelope") or {}
    delivered = (record.get("transport_status") == "ok" and
                 record.get("http_status") == 200 and record.get("body_complete") is True and
                 envelope.get("delivery_complete") is True and type(envelope.get("content")) is str)
    contract = request["contract"]
    expected = reference(task, contract)
    content = envelope.get("content", "") if delivered else ""
    obj = strict_object(content) if delivered else None
    sem = _semantic_correct(obj, expected) if delivered else None
    binding = _binding_correct(obj, expected["evidence"]) if delivered and contract == "evidence" else None
    try:
        raw = content.encode("utf-8", errors="strict")
    except UnicodeError:
        raw = b""
    strict = delivered and validate_response(raw, contract)
    gate = evaluate_response(task["source_text"].encode("utf-8"), task["target_key"], raw, contract) if delivered else None
    pure_schema = delivered and schema_valid(content, schemas[contract])
    meaning_correct = sem is True and (contract == "no_evidence" or binding is True)
    joint = bool(strict and meaning_correct)
    row = {"request_id": request["request_id"], "input_id": task["input_id"],
           "group": task["group"], "arm": request["arm"], "contract": contract,
           "delivered": delivered, "strict_wire_json": obj is not None,
           "strict_contract": bool(strict), "decoded_schema_valid": bool(pure_schema),
           "semantic_correct": sem, "binding_correct": binding,
           "binding_applicable": contract == "evidence", "joint_correct": joint,
           "source_gate_reason": gate["reason"] if gate else "unavailable",
           "pipelines": {}}
    accepts = {"decoded_schema": bool(pure_schema), "strict_contract": bool(strict),
               "source_gate": bool(delivered and gate and gate["source_accept"])}
    for pipeline, accepted in accepts.items():
        outcome = "unavailable" if not delivered else ("rejected" if not accepted else
                                                        "accepted_correct" if joint else "accepted_wrong")
        row["pipelines"][pipeline] = {"outcome": outcome,
            "accepted_semantic_wrong": bool(accepted and sem is False),
            "accepted_semantic_unscorable": bool(accepted and sem is None),
            "accepted_format_only": bool(accepted and meaning_correct and not strict),
            "accepted_binding_wrong": bool(accepted and contract == "evidence" and binding is False)}
    return row


def summarize_rows(rows):
    result = {"initiated": len(rows), "delivered": sum(r["delivered"] for r in rows),
              "strict_wire_json": sum(r["strict_wire_json"] for r in rows),
              "strict_contract": sum(r["strict_contract"] for r in rows),
              "decoded_schema_valid": sum(r["decoded_schema_valid"] for r in rows),
              "semantic_correct": sum(r["semantic_correct"] is True for r in rows),
              "semantic_wrong": sum(r["semantic_correct"] is False for r in rows),
              "semantic_unscorable": sum(r["semantic_correct"] is None for r in rows),
              "binding_applicable": sum(r["binding_applicable"] for r in rows),
              "binding_correct": sum(r["binding_correct"] is True for r in rows),
              "joint_correct": sum(r["joint_correct"] for r in rows), "pipelines": {}}
    for pipeline in ("decoded_schema", "strict_contract", "source_gate"):
        entries = [r["pipelines"][pipeline] for r in rows]
        counts = Counter(e["outcome"] for e in entries)
        values = {key: counts[key] for key in ("accepted_correct", "accepted_wrong", "rejected", "unavailable")}
        accepted = values["accepted_correct"] + values["accepted_wrong"]
        values["coverage"] = accepted / len(rows) if rows else None
        values["correct_among_accepted"] = values["accepted_correct"] / accepted if accepted else None
        for key in ("accepted_semantic_wrong", "accepted_semantic_unscorable", "accepted_format_only", "accepted_binding_wrong"):
            values[key] = sum(e[key] for e in entries)
        result["pipelines"][pipeline] = values
    return result


def score_study(task_document, requests, records, run_summary, schemas):
    tasks = {task["input_id"]: task for task in task_document["tasks"]}
    by_id = {r["request_id"]: r for r in requests}
    if len(task_document["tasks"]) != 8 or len(tasks) != 8 or len(requests) != 32 or len(by_id) != 32:
        raise ValueError("unexpected_frozen_schedule_inventory")
    if {(r["input_id"], r["arm"]) for r in requests} != {(task, arm) for task in tasks for arm in ARMS}:
        raise ValueError("schedule_missing_or_repeated_input_arm")
    if any((r["mode"], r["contract"]) != tuple(r["arm"].split("_", 1)) for r in requests):
        raise ValueError("schedule_arm_metadata_mismatch")
    if len({r["request_id"] for r in records}) != len(records):
        raise ValueError("duplicate_record_id")
    if any(r["request_id"] not in by_id for r in records):
        raise ValueError("unknown_record_id")
    baseline = []
    for task in tasks.values():
        if hashlib.sha256(task["source_text"].encode("utf-8")).hexdigest() != task["source_sha256"]:
            raise ValueError("task_source_hash_mismatch")
        for contract in ("no_evidence", "evidence"):
            derived = derive_response(task["source_text"].encode("utf-8"), task["target_key"], contract)
            baseline.append({"input_id": task["input_id"], "contract": contract,
                             "matches_manual_expectation": derived == reference(task, contract)})
    rows = [score_record(tasks[by_id[r["request_id"]]["input_id"]], by_id[r["request_id"]], r, schemas) for r in records]
    by_arm = {arm: summarize_rows([r for r in rows if r["arm"] == arm]) for arm in ARMS}
    by_group = {group: summarize_rows([r for r in rows if r["group"] == group]) for group in sorted({t["group"] for t in tasks.values()})}
    by_arm_and_group = {arm: {group: summarize_rows([r for r in rows if r["arm"] == arm and r["group"] == group])
                             for group in by_group} for arm in ARMS}
    scheduled_ids = [r["request_id"] for r in requests]
    actual_ids = [r["request_id"] for r in records]
    usage_values = [(r.get("envelope") or {}).get("eval_count") for r in records]
    usage_known = all(type(value) is int and 0 <= value <= 256 for value in usage_values)
    usage_matches = (usage_known and type(run_summary.get("output_tokens")) is int and
                     run_summary["output_tokens"] == sum(usage_values) and sum(usage_values) <= 8192)
    summary_inventory_matches = (run_summary.get("initiated_calls") == len(records) and
                                 run_summary.get("completed_calls") == sum(r["delivered"] for r in rows) and
                                 run_summary.get("initiated_request_ids") == actual_ids and
                                 run_summary.get("completed_request_ids") == [r["request_id"] for r in rows if r["delivered"]] and
                                 run_summary.get("unattempted_request_ids") == [i for i in scheduled_ids if i not in actual_ids])
    provenance_ok = (run_summary.get("status") == "completed" and
                     run_summary.get("metadata_match") is True and
                     run_summary.get("freeze_unchanged") is True and
                     run_summary.get("budget_ok") is True and
                     run_summary.get("usage_complete") is True and usage_matches and summary_inventory_matches)
    all_completed = actual_ids == scheduled_ids and len(rows) == 32 and all(r["delivered"] for r in rows)
    designated = [r for r in rows if r["arm"] == "schema_evidence"]
    unknown_absent = [r for r in designated if r["group"] in {"explicit_unknown", "absent_target"}]
    baseline_ok = all(b["matches_manual_expectation"] for b in baseline)
    content_gate = (len(designated) == 8 and sum(r["joint_correct"] for r in designated) >= 7 and
                    len(unknown_absent) == 4 and all(r["joint_correct"] for r in unknown_absent))
    passed = provenance_ok and all_completed and baseline_ok and content_gate
    return {"study": "BF-01C", "interpretation": "Developmental task-only cohort; no causal, social-framing, deployment or product-value inference.",
            "scheduled": 32, "initiated": len(rows), "unattempted_ids": [i for i in scheduled_ids if i not in actual_ids],
            "overall": summarize_rows(rows), "by_arm": by_arm, "by_group": by_group,
            "by_arm_and_group": by_arm_and_group,
            "direct_baseline": baseline,
            "competence_gate": {"passed": bool(passed), "provenance_ok": provenance_ok,
                "summary_inventory_matches": summary_inventory_matches, "usage_matches": usage_matches,
                "all_32_complete_in_order": all_completed, "direct_baseline_all_16": baseline_ok,
                "designated_joint_correct": sum(r["joint_correct"] for r in designated),
                "designated_unknown_absent_correct": sum(r["joint_correct"] for r in unknown_absent),
                "content_threshold_passed": bool(content_gate),
                "next_framing_phase": "NOT_AUTHORIZED_OR_AUTOMATICALLY_LAUNCHED"}, "rows": rows}


def verify_saved_evidence(run_dir, requests, records):
    """Reparse the preserved raw bytes and initiation journal before scoring.

    This verifies agreement with the retained collection record. It does not
    establish authenticity of an untrusted recorder or reconstruct an HTTP
    exchange that was not retained.
    """
    journal = [json.loads(line) for line in (run_dir / "initiation.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if [j["request_id"] for j in journal] != [r["request_id"] for r in records]:
        raise ValueError("initiation_outcome_inventory_mismatch")
    by_id = {r["request_id"]: r for r in requests}
    for entry, record in zip(journal, records):
        request_id = record["request_id"]
        if request_id not in by_id:
            raise ValueError("unknown_record_id")
        request = by_id[request_id]
        expected_request_path = f"run/requests/{request_id}.json"
        expected_response_path = f"run/responses/{request_id}.bin"
        if record.get("request_body_path") != expected_request_path or record.get("response_body_path") != expected_response_path:
            raise ValueError("unexpected_saved_evidence_path")
        for key, value in entry.items():
            if record.get(key) != value:
                raise ValueError("initiation_record_disagreement")
        raw_request = (run_dir / "requests" / f"{request_id}.json").read_bytes()
        expected_bytes = json.dumps(request["request_body"], ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        if raw_request != expected_bytes or hashlib.sha256(raw_request).hexdigest() != record.get("request_sha256"):
            raise ValueError("saved_request_bytes_mismatch")
        raw_response = (run_dir / "responses" / f"{request_id}.bin").read_bytes()
        if hashlib.sha256(raw_response).hexdigest() != record.get("response_sha256"):
            raise ValueError("saved_response_hash_mismatch")
        checked = validate_envelope(record.get("http_status"), raw_response, request["request_body"]["model"],
                                    http_complete=record.get("body_complete"))
        duration, timeout = record.get("duration_seconds"), record.get("timeout_seconds")
        sent, dispatch_timeout = record.get("sent"), record.get("dispatch_timeout_seconds")
        if type(duration) not in (int, float) or type(timeout) not in (int, float) or not (math.isfinite(duration) and math.isfinite(timeout) and duration >= 0 and 0 < timeout <= 30):
            raise ValueError("invalid_record_timing")
        if type(sent) is not bool or type(dispatch_timeout) not in (int, float) or not math.isfinite(dispatch_timeout):
            raise ValueError("invalid_dispatch_metadata")
        if sent and not 0 < dispatch_timeout <= timeout:
            raise ValueError("invalid_dispatch_timeout")
        if not sent and not (dispatch_timeout == 0 and duration == 0 and raw_response == b"" and
                             record.get("http_status") is None and record.get("body_complete") is False and
                             record.get("transport_status") == "error" and record.get("error") == "global_budget_before_send"):
            raise ValueError("invalid_unsent_reservation")
        if sent and duration > dispatch_timeout:
            checked.update(valid=False, delivery_complete=False, reason="per_call_budget")
        if checked != record.get("envelope"):
            raise ValueError("saved_envelope_replay_mismatch")
    return {"initiations": len(journal), "raw_request_response_pairs": len(records),
            "envelope_replay": "MATCHED_RETAINED_BYTES", "authenticity_claim": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=HERE / "run")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    read = lambda p: json.loads(p.read_text(encoding="utf-8"))
    tasks, requests = read(HERE / "tasks.json"), read(HERE / "requests.json")
    schemas = {c: read(HERE / f"schema_{c}.json") for c in ("no_evidence", "evidence")}
    records = [json.loads(line) for line in (args.run_dir / "records.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    verify_freeze(HERE)
    audit = verify_saved_evidence(args.run_dir, requests, records)
    report = score_study(tasks, requests, records, read(args.run_dir / "summary.json"), schemas)
    report["saved_evidence_verification"] = audit
    output = args.output or args.run_dir / "score.json"
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(json.dumps({"initiated": report["initiated"], "gate": report["competence_gate"]}))


if __name__ == "__main__":
    main()
