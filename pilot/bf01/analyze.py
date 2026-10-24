"""Recompute descriptive BF-01 outcomes from retained raw local responses. MIT."""
import argparse
import base64
from collections import Counter
import json
from dataclasses import asdict
from pathlib import Path

from evaluate import score_response, Limits
from prepare import CONDITIONS, canonical, digest
import run_local

ROOT = Path(__file__).resolve().parent


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def analyze(directory):
    run_local.verify_freeze()
    plan = json.loads((ROOT / "plan.json").read_text(encoding="utf-8"))
    environment = json.loads((directory / "environment.json").read_text(encoding="utf-8"))
    completion = json.loads((directory / "completion.json").read_text(encoding="utf-8"))
    if environment["freeze_sha256"] != digest((ROOT / "freeze.json").read_bytes()) or environment["model"] != plan["model"]:
        raise ValueError("Environment does not match frozen plan")
    cases = rows(ROOT / "cases.jsonl")
    by_id = {c["case_id"]: c for c in cases}
    responses = rows(directory / "responses.jsonl")
    ledger = rows(directory / "ledger.jsonl")
    limits = asdict(Limits())
    if not ledger or ledger[0].get("event") != "opened" or ledger[0].get("limits") != limits:
        raise ValueError("Ledger budget differs from frozen limits")
    if [r["sequence"] for r in ledger] != list(range(len(ledger))):
        raise ValueError("Ledger sequence discontinuity")
    starts = [r for r in ledger if r["event"] == "started"]
    ends = [r for r in ledger if r["event"] in {"completed", "failed"}]
    ids = [r["case_id"] for r in responses]
    if len(set(ids)) != len(ids) or ids != [r["case_id"] for r in starts] or ids != [r["case_id"] for r in ends]:
        raise ValueError("Duplicate or unmatched initiated/response/completion evidence")
    if ids != [c["case_id"] for c in cases[:len(ids)]]:
        raise ValueError("Run does not follow the frozen schedule prefix")
    if completion["initiated"] != len(ids) or completion["planned"] != 72 or completion["not_attempted"] != [c["case_id"] for c in cases[len(ids):]]:
        raise ValueError("Completion counts differ from ledger")
    complete_run = len(ids) == 72 and completion["stop_reason"] is None
    if completion["status"] != ("COMPLETE" if complete_run else "INCOMPLETE"):
        raise ValueError("Completion status contradicts stop/attempt evidence")
    counts = {k: {"planned": 12, "initiated": 0, "success": 0, "non_success": 0,
                  "response_observed": 0, "behavioral_violation": 0,
                  "transport_error": 0, "truncated": 0} for k in CONDITIONS}
    failures = []
    family = {}
    usage = {"input_tokens_known_sum": 0, "output_tokens_known_sum": 0,
             "input_tokens_unknown_calls": 0, "output_tokens_unknown_calls": 0}
    for response, start, end in zip(responses, starts, ends):
        case = by_id[response["case_id"]]
        if start["attempt_id"] != end["attempt_id"] or start["task_id"] != case["task_id"] or start["condition"] != case["condition"]:
            raise ValueError("Attempt/condition linkage mismatch")
        if start["prompt"] != canonical(case["messages"]):
            raise ValueError("Initiated prompt differs from frozen case")
        if start["prompt_sha256"] != digest(start["prompt"].encode()):
            raise ValueError("Ledger prompt hash mismatch")
        if start["input_bytes"] != len(start["prompt"].encode()) or start["input_bytes"] > limits["max_input_bytes"] or start["output_token_limit"] != 512:
            raise ValueError("Invalid reserved input/output budget")
        payload = {"model": plan["model"]["tag"], "messages": case["messages"],
                   "stream": False, "keep_alive": 0, "options": plan["options"]}
        if response["request_sha256"] != digest(canonical(payload).encode()):
            raise ValueError("Request hash differs from frozen configuration")
        raw = base64.b64decode(response["raw_http_body_base64"], validate=True)
        if digest(raw) != response["http_body_sha256"]:
            raise ValueError("Raw HTTP evidence hash mismatch")
        envelope = run_local.parse_envelope(raw, plan["model"]["tag"], response["http_body_complete"])
        if envelope["response"] != response["response"] or envelope["status"] != response["status"]:
            raise ValueError("Response status/value differs from raw envelope")
        content = envelope["content"]
        for key, value in envelope["usage"].items():
            if end["usage"][key] != value:
                raise ValueError("Usage differs from raw envelope")
        breaches = []
        if content is not None and len(content.encode()) > limits["max_response_bytes"]:
            breaches.append("response_bytes")
        if envelope["usage"]["output_tokens"] is not None and envelope["usage"]["output_tokens"] > start["output_token_limit"]:
            breaches.append("output_tokens")
        if end["elapsed_seconds"] > limits["max_seconds"]:
            breaches.append("elapsed_seconds")
        if end["budget_breaches"] != breaches:
            raise ValueError("Recorded budget breaches differ from recomputation")
        expected_score = score_response(case["expected_json"], content, response["status"])
        if expected_score != end["score"]:
            raise ValueError("Retained score differs from independent recomputation")
        success = expected_score["success"] and not end["budget_breaches"]
        if success != end["success"]:
            raise ValueError("Ledger final status inconsistent")
        if end["event"] != ("completed" if success else "failed"):
            raise ValueError("Ledger event contradicts success")
        count = counts[case["condition"]]
        count["initiated"] += 1
        count["success"] += int(success)
        count["non_success"] += int(not success)
        for key in ("response_observed", "behavioral_violation", "truncated"):
            count[key] += int(expected_score[key] is True)
        count["transport_error"] += int(response["status"] == "transport_error")
        family.setdefault(case["family_id"], {}).setdefault(case["condition"], []).append(int(not success))
        if not success:
            failures.append({"case_id": case["case_id"], "condition": case["condition"],
                             "reason": expected_score["reason"],
                             "expected": case["expected_json"], "raw_text": content})
        for token in ("input_tokens", "output_tokens"):
            n = end["usage"][token]
            usage[token + "_unknown_calls"] += int(n is None)
            if n is not None:
                usage[token + "_known_sum"] += n
    complete = complete_run
    for value in counts.values():
        value["not_attempted"] = value["planned"] - value["initiated"]
        value["initiated_non_success_rate"] = value["non_success"] / value["initiated"] if value["initiated"] else None
    risks = None
    contrasts = None
    if complete:
        risks = {condition: sum(sum(group[condition]) / len(group[condition]) for group in family.values()) / len(family)
                 for condition in CONDITIONS}
        contrasts = {"compassion_risk_difference": .5 * ((risks["C1L0"] - risks["C0L0"]) + (risks["C1L1"] - risks["C0L1"])),
                     "normative_risk_difference": .5 * ((risks["C0L1"] - risks["C0L0"]) + (risks["C1L1"] - risks["C1L0"])),
                     "risk_difference_interaction": risks["C1L1"] - risks["C1L0"] - risks["C0L1"] + risks["C0L0"]}
    return {"study": "BF-01", "phase": "developmental_feasibility",
            "status": "COMPLETE" if complete else "INCOMPLETE", "planned_calls": 72,
            "initiated_calls": len(ids), "template_families": 4, "task_instances": 12,
            "conditions": counts, "family_equal_weight_non_success_risk": risks,
            "descriptive_contrasts": contrasts, "usage": usage, "failures": failures,
            "confirmatory_inference": "NOT_PERFORMED", "p_values": None,
            "uncertainty_intervals": None, "effect_generalization": False,
            "interpretation": "Four convenience-authored task families, one greedy draw per case, one small quantized model. Descriptive feasibility evidence only; no universal attack, causal mechanism, equivalence or robustness certification."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--check", action="store_true", help="Compare against retained summary without changing it")
    args = parser.parse_args()
    report = analyze(args.directory)
    path = args.directory / "summary.json"
    if args.check:
        if json.loads(path.read_text(encoding="utf-8")) != report:
            raise SystemExit("Summary differs from raw-evidence recomputation")
        print("Retained summary reproduced from raw evidence")
    else:
        with path.open("x", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
        print(json.dumps({"initiated": report["initiated_calls"], "failures": len(report["failures"])}))
