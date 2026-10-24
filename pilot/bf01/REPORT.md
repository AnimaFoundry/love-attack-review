# BF-01: a bounded local feasibility pilot

**Completed 24 October 2026. Developmental evidence; not a confirmatory study.**

One local Qwen2.5-1.5B-Instruct Q4_K_M model completed all 72 scheduled calls on 12 original synthetic tasks. Forty-three responses satisfied the frozen strict JSON contract and 29 did not. The compassion wording contrast did **not** show increased failure in this sample: its descriptive risk difference was -4.17 percentage points. The normative wording contrast was +20.83 points. Four convenience-authored task families, deterministic counterbalancing and one greedy response per item do not support general causal, statistical-significance, equivalence or model-population claims.

This companion advances the original review's BF-01 feasibility stage. It does not retrospectively change the unchanged v1.0.0 manuscript or complete its broader confirmatory protocol. BF-02, BF-03 and BF-04 were not performed.

## What was fixed before generation

- Twelve tasks in four authored families: integer accounting, missing-versus-zero extraction, first-matching rule precedence, and exact JSON string preservation. Three related instances belong to each family; they are not twelve independently sampled origins.
- Four factorial conditions crossed compassion wording with normative wording. Neutral practical/procedural statements occupied the same slots when the respective cue was absent. Task facts, beneficiary category, authority, answer and output contract were unchanged. Separate task-only and neutral-long conditions checked two added-text baselines.
- Task order was hash-sorted, with cyclic condition rotations. Each condition appeared twice in each within-task position. This is deterministic counterbalancing, not randomized causal assignment.
- All requests used a fresh two-message array, no tools, no writable memory, no prior responses and no JSON-constrained decoder. There were no emoji runs, repeated-symbol cues or requests to override rules.
- The global ceiling was 72 calls, concurrency one, no retries or auxiliary model calls, 512 generated tokens per call, 120 seconds per call and 2,400 seconds overall. External API expenditure was USD 0. One approximately 1 GB local model download was approved; weights are not redistributed. Hardware and electricity are not described as costless.

The exact model tag is `qwen2.5:1.5b-instruct-q4_K_M`, digest `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`, with Ollama server 0.40.10. Temperature was 0, the seed 20261024 and the context limit 4096. Remaining settings, model-template and license hashes appear in [plan.json](plan.json). The model is supplied under the [upstream Apache 2.0 license](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct/blob/main/LICENSE); a complete copy is retained as [MODEL-LICENSE.txt](MODEL-LICENSE.txt).

[freeze.json](freeze.json) records thirteen reviewed source, data, plan and license files, sealed at **13:11:04.270561 UTC**, before the first reservation at **13:11:15.034447 UTC**. The freeze SHA-256 is `e7f48cab05503a528eea92a1bd2ac95377c960771b462e135c134683ce019a1a`. This is a local integrity record, not an external preregistration. Fifty-six offline synthetic checks passed before the freeze; mocked transport results are not empirical model calls.

## All initiated outcomes

Success required the complete response to be exactly one JSON object with the specified keys, decoded values and types. Object key order, legal escaping and whitespace outside strings were accepted. Markdown fences, extra prose, wrong values/types and duplicate keys were not accepted. No output repair was applied to the primary outcome.

| Condition | Successful / initiated | Non-success / initiated | Non-success rate |
|---|---:|---:|---:|
| C0L0: practical/procedural control | 8 / 12 | 4 / 12 | 33.33% |
| C1L0: compassion only | 8 / 12 | 4 / 12 | 33.33% |
| C0L1: normative appeal only | 5 / 12 | 7 / 12 | 58.33% |
| C1L1: both cues | 6 / 12 | 6 / 12 | 50.00% |
| Task only | 9 / 12 | 3 / 12 | 25.00% |
| Neutral longer text | 7 / 12 | 5 / 12 | 41.67% |
| **Total** | **43 / 72** | **29 / 72** | **40.28%** |

Every scheduled case was initiated and retained. There were no transport failures, truncations, hidden retries, missing usage values or uninitiated replacements. The run finished at **13:14:58.961235 UTC**, taking 223.968 seconds from ledger setup. Recorded usage totaled 16,800 input tokens and 1,018 generated tokens; the largest response used 21 generated tokens. These are observations of this local run, not an inference-speed benchmark.

Equal weighting of the four families, and of their three instances, yields these prespecified descriptive contrasts on non-success risk:

| Contrast | Observed risk difference |
|---|---:|
| Compassion main contrast | -4.17 percentage points |
| Normative main contrast | +20.83 percentage points |
| Risk-difference interaction | -8.33 percentage points |

No p-values, confidence intervals, power estimate or equivalence conclusion are reported. Counts were small, family origins were not sampled independently from a deployment population, and the wording combines lexical and semantic changes. Recorded prompt-token counts were equal within each task across the four factorial conditions in this run; that observation does not establish semantic equivalence or matching for other tokenizers. Task-only and neutral-long inputs had different lengths by design.

## What the failures actually were

The frozen scorer recorded **27 invalid-JSON responses and two valid-JSON value/type mismatches**. Inspection after collection found that all 27 invalid responses were enclosed in Markdown JSON fences, despite the explicit no-fences requirement.

The following breakdown is **post hoc diagnostic inspection**, not a replacement endpoint or a tested defense:

- Sixteen failures contained the correct values inside a forbidden fence.
- Eleven combined a fence with a substantive wrong value.
- Two had wrong values without a fence.

The zero-quantity and missing-quantity tasks each failed in all six conditions: the model treated a present zero as absent, or supplied `1` where the specification required `null`. One arithmetic response returned `15` instead of `19`. By contrast, the zero and negative accounting cases passed all six conditions. All string-copy contents were correct after JSON decoding, although ten string-copy responses violated the outer-format requirement.

These observations distinguish task competence from framing sensitivity. A simple fence-removal adapter would change some saved outcomes, but a retrospective repair of these same examples is not evidence of a generally effective defense. The unmodified primary 43/72 result remains the reported result.

## Supported conclusions and next decision

The execution and scoring pipeline was feasible at the declared small local budget. It captured a reproducible record of contract failures, including substantive errors that occurred even with no framing. It therefore supplies useful test cases for strict machine-consumed JSON interfaces.

This pilot **does not support a claim that compassionate wording increased failure**. The positive normative contrast is a limited observation worth distinguishing from generic added-text effects and baseline task weakness. It does not establish a new attack class, an internal priority mechanism, a denial-of-service effect, or behavior of larger hosted models. Absence of a positive compassion contrast is not proof that every compassion intervention has no effect.

The next useful step is to separate formatting failures from substantive zero/missing-value errors on **new task origins**, and to compare a simple deterministic output-validation baseline before proposing a special defense. Any further generation requires a new finite budget and a separately frozen design. The current 72 cases are consumed development data and must not be tuned on and relabeled as untouched confirmation. No additional model calls were made for the diagnostic inspection.

## Reproduce the saved evidence

From the repository root, run the following offline commands:

```sh
python -m unittest discover -s pilot/bf01 -p 'test_*.py' -v
python pilot/bf01/analyze.py pilot/bf01/run-001 --check
```

The [raw HTTP envelopes](run-001/responses.jsonl), [append-only attempt ledger](run-001/ledger.jsonl), [environment](run-001/environment.json), [completion record](run-001/completion.json) and [machine-readable summary](run-001/summary.json) retain the full synthetic cohort. The analyzer checks the freeze, prompt/request hashes, response-derived status and usage, scoring and denominator linkage. Independent offline replay and clean Ubuntu CI validate these saved artifacts; they do not repeat the model inference on Linux or reproduce the cited literature.

An administrative review-paragraph correction arrived after collection started. Its original frozen bytes were restored and all thirteen hashes rechecked before analysis; no task, prompt, generation setting, runner, scorer or analysis code was changed after the freeze. The frozen review's conditional disposition is retained as history, alongside its recorded 56-test pre-run result. All subsequent reported outcomes use the original frozen analysis.

Only original synthetic material and model responses to that material are included. No private case, transcript, count derived from a private conversation, model weights or copied benchmark is published. The package's text/code licenses and third-party model attribution remain separate. The work asserts no patent clearance, invention novelty or guarantee that these artifacts are suitable for a production deployment.
