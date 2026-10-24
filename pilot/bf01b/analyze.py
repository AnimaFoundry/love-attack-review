"""Recompute descriptive BF-01B outcomes from retained raw local responses. MIT."""
import argparse
import base64
from collections import Counter
import json
from dataclasses import asdict
from pathlib import Path

from evaluate import score_response, Limits
from validators import assess
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
    if completion["initiated"] != len(ids) or completion["planned"] != 168 or completion["not_attempted"] != [c["case_id"] for c in cases[len(ids):]]:
        raise ValueError("Completion counts differ from ledger")
    complete_run = len(ids) == 168 and completion["stop_reason"] is None
    if completion["status"] != ("COMPLETE" if complete_run else "INCOMPLETE"):
        raise ValueError("Completion status contradicts stop/attempt evidence")
    counts = {k: {"planned": 24, "initiated": 0, "success": 0, "non_success": 0,
                  "response_observed": 0, "behavioral_violation": 0,
                  "transport_error": 0, "truncated": 0} for k in CONDITIONS}
    failures = []
    diagnostics = []
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
        if start["input_bytes"] != len(start["prompt"].encode()) or start["input_bytes"] > limits["max_input_bytes"] or start["output_token_limit"] != 128:
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
        observed = response['status'] == 'returned' and not breaches
        diagnostic = assess(content, case['expected_json']) if observed else None
        diagnostics.append({'case_id':case['case_id'], 'task_id':case['task_id'],
                            'family':case['family_id'], 'condition':case['condition'],
                            'expected':case['expected_json'], 'status':response['status'],
                            'eligible_for_pipeline_assessment':observed, 'assessment':diagnostic})
        for token in ("input_tokens", "output_tokens"):
            n = end["usage"][token]
            usage[token + "_unknown_calls"] += int(n is None)
            if n is not None:
                usage[token + "_known_sum"] += n
    complete = complete_run
    for value in counts.values():
        value['not_attempted'] = value['planned'] - value['initiated']
        value['initiated_non_success_rate'] = value['non_success']/value['initiated'] if value['initiated'] else None
    return {'study':'BF-01B', 'phase':'developmental_content_integrity',
            'status':'COMPLETE' if complete else 'INCOMPLETE', 'planned_calls':168,
            'initiated_calls':len(ids), 'representation_families':6, 'task_instances':24,
            'conditions':counts, 'usage':usage, 'failures':failures,
            'pipeline_results':aggregate(diagnostics),
            'state_strata':{state:aggregate([d for d in diagnostics if state_label(d['expected'])==state])
                            for state in ('observed_zero','observed_positive','unknown','absent')},
            'family_strata':{f:aggregate([d for d in diagnostics if d['family']==f]) for f in sorted(family)},
            'paired_comparisons':paired(diagnostics) if complete else None,
            'case_diagnostics':diagnostics,
            'confirmatory_inference':'NOT_PERFORMED', 'p_values':None, 'uncertainty_intervals':None,
            'interpretation':'Six authored representations of one semantic operation, one small quantized model, one greedy draw per item. Descriptive content-integrity stress study, not deployment or psychological causal evidence. Rejection is abstention, never a corrected answer.'}


def state_label(expected):
    return ('observed_zero' if expected['value']==0 else 'observed_positive') if expected['state']=='observed' else expected['state']


def aggregate(items):
    result={}
    for condition in ['ALL']+CONDITIONS:
        group=items if condition=='ALL' else [x for x in items if x['condition']==condition]
        pipelines={}
        for lane,accept_key,correct_key in (
                ('raw_json','raw_parseable','raw_exact_correct'),
                ('single_fence_parser','repaired_parseable','repaired_exact_correct'),
                ('single_object_extractor','extracted_parseable','extracted_exact_correct'),
                ('schema_filter','schema_accept','schema_accepted_correct')):
            good=bad=rejected=unavailable=0
            for item in group:
                a=item['assessment']
                if a is None:
                    unavailable+=1
                elif not a[accept_key]:
                    rejected+=1
                elif a[correct_key]:
                    good+=1
                else:
                    bad+=1
            accepted=good+bad
            pipelines[lane]={'initiated':len(group),'accepted_correct':good,'accepted_wrong':bad,
                'rejected':rejected,'unavailable_truncated_or_budget_excluded':unavailable,
                'coverage':accepted/len(group) if group else None,
                'conditional_correctness':good/accepted if accepted else None,
                'correct_answers_per_initiated':good/len(group) if group else None,
                'silent_error_per_initiated':bad/len(group) if group else None}
        recovered=sum(bool(x['assessment'] and not x['assessment']['raw_exact_correct'] and x['assessment']['repaired_exact_correct']) for x in group)
        extracted=sum(bool(x['assessment'] and not x['assessment']['raw_exact_correct'] and x['assessment']['extracted_exact_correct']) for x in group)
        intercepted=sum(bool(x['assessment'] and x['assessment']['extracted_parseable'] and not x['assessment']['extracted_exact_correct'] and not x['assessment']['schema_accept']) for x in group)
        result[condition]={'pipelines':pipelines,'formatting_recovered_correct':recovered,
                           'extraction_recovered_correct':extracted,
                           'schema_intercepted_wrong_without_correction':intercepted}
    return result


def paired(items):
    by_task={}
    for item in items:
        by_task.setdefault(item['task_id'],{})[item['condition']]=item
    result={}
    for baseline,intervention in [('TASK_ONLY','NEUTRAL_CONTEXT'),
            ('NEUTRAL_CONTEXT','FORMAT_PLAIN'),('FORMAT_PLAIN','RELATIONAL_FORMAT'),
            ('NEUTRAL_CONTEXT','DEFAULT_PLAIN'),('DEFAULT_PLAIN','LEGITIMACY_DEFAULT'),
            ('NEUTRAL_CONTEXT','COMBINED')]:
        for endpoint in ('raw_exact_correct','schema_accepted_wrong'):
            table={'both_false':0,'baseline_only':0,'intervention_only':0,'both_true':0,'unavailable':0}
            for pair in by_task.values():
                a,b=pair[baseline]['assessment'],pair[intervention]['assessment']
                if a is None or b is None:
                    table['unavailable']+=1
                    continue
                av,bv=bool(a[endpoint]),bool(b[endpoint])
                table['both_true' if av and bv else 'baseline_only' if av else 'intervention_only' if bv else 'both_false']+=1
            table['intervention_minus_baseline_count']=table['intervention_only']-table['baseline_only']
            result[baseline+'__'+intervention+'__'+endpoint]=table
    return result


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
