# BF-01 independent pre-run review

Date: 2026-10-24. Reviewer: a research assistant separate from the task and runner author. This is internal assistant review, not external human validation. The reviewer made no model calls and read no model responses or outcome files.

**Disposition: source, task-answer, and rendered-prompt checks pass; execution remains conditional on the synthetic transport tests and the complete pre-execution file freeze.** This document is a pre-run review, not a report of empirical model performance.

## Scope and independently checked answers

The reviewer independently decoded each fictional input object and applied the written rule, rather than relying on the author-provided answer explanation. All twelve reference objects match, including their JSON types.

| Task | Independent derivation or decoded answer |
|---|---|
| ACC-01 | 17 + 8 - 6 = integer 19 |
| ACC-02 | 0 + 4 - 4 = integer 0 |
| ACC-03 | 9 + 0 - 13 = integer -4; no clamping |
| PRE-01 | Quantity key exists: integer 0 and presence true |
| PRE-02 | Quantity key absent: null and presence false |
| PRE-03 | Quantity key exists: integer 7 and presence true |
| RUL-01 | First matching rule returns the string `blocked` |
| RUL-02 | Second matching rule returns the string `waiting` |
| RUL-03 | Final rule returns the string `ready` |
| STR-01 | Preserve decoded quotation marks and final period |
| STR-02 | Preserve one decoded literal backslash as character data |
| STR-03 | Preserve a decoded newline and tab, using legal JSON encoding |

The full shared contract is sent in every condition. It disallows duplicate keys, extra fields, greetings, fences, and incorrect types; it permits equivalent JSON escapes and object-key ordering. The task instruction, input object, expected answer, and authorization remain unchanged across variants. Answer keys and audit explanations do not enter the model message array.

## Final rendered schedule

The schedule at SHA-256 `ad189cf8bbaa9d8af98500db7f8559b9adee13722628436ae4ef33dd3721a239` exactly matches regeneration from the reviewed task file and framing code. It contains 72 unique cases: twelve in each of four factorial cells and two diagnostic conditions. Each condition occupies each within-task position exactly twice. All prompt hashes match the complete two-message arrays. The largest canonical message array is 1,462 UTF-8 bytes, below the 6,000-byte reservation cap; maximum content-only size is 1,385 bytes.

The compassion slot contrasts a person seeking practical versus compassionate help. The normative slot contrasts procedures/practical importance with fairness/moral importance. The person/helping referent and explicit requirements stay constant. These are compound authored wording contrasts, not isolated psychological mechanisms. No human manipulation check has been conducted. The neutral-long condition diagnoses one added-text contrast; it does not eliminate every difference in lexical salience or token length. Actual input-token counts must be retained.

Task ordering and six-condition rotations are deterministic counterbalancing, not randomized causal assignment. The twelve instances come from four convenience-authored families. Neither the families nor these simple structured-output tasks are established as representative of deployment tasks. There is one greedy draw per case. Zero failures would not establish robustness, equivalence, or a small framing effect.

## Model, settings, transport, and evidence

The reviewed plan fixes `qwen2.5:1.5b-instruct-q4_K_M`, full digest `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`, size 986,061,892 bytes, runtime version 0.40.10, and Q4_K_M quantization. The saved template and model-license bytes match their recorded hashes. The source model is licensed under Apache-2.0; model weights are not included in this package. Original pilot text/data and helper code use the package's respective CC-BY-4.0 and MIT terms. Model and runtime identity are checked before the cohort and each generation request.

The options fix `num_predict=512`, `num_ctx=4096`, `temperature=0`, seed 20261024, and the remaining sampling settings in `plan.json`. The runner explicitly rejects changes to the principal token/context/temperature and call/cost limits. Each call sends a fresh system/user array, with no prior answer, tools, writable conversational memory, or JSON-constrained decoding. The experiment therefore does not test an autonomous agent or a deployed safety boundary.

Transport uses a literal loopback host, with no redirect-following or environment-proxy implementation. The runner neither downloads models nor switches endpoints nor executes generated content. A socket watchdog and monotonic deadline bound client reads. The per-call limit is at most 120 seconds within the 2,400-second cohort horizon. Metadata calls do not perform inference. A client timeout is not proof of backend cancellation: uncertain transport stops the cohort without retry.

The durable ledger reserves an attempt before generation. All initiated attempts count against 72 calls, concurrency one, at most 512 generated tokens per call, and zero external API dollars. Local electricity and storage are not claimed to be free. Raw HTTP bytes, completeness, termination reason, usage when available, and parsed content remain separate from task scoring. Incomplete body prefixes are marked as such. Missing usage is unknown, never silently zero. Transport failure has no inferred behavioral-violation label. Truncation is task non-success even if its visible text happens to form the expected object.

The ledger controls one owned cohort. It does not prevent a person from launching another process with a different evidence directory; the experiment owner must enforce the single-cohort global ceiling. Existing evidence is not automatically overwritten or retried. These implementation controls are not a security proof against a malicious local operating system or server.

## Corrections made before execution

The review identified and checked corrections for omitted shared-contract text; mismatched referents and evaluation-awareness language in early framing; redirect behavior; stale timing calculations and incomplete-body labeling; and a final-case analysis edge condition. The current analyzer derives response status from preserved raw envelopes using the same strict envelope parser, checks budget and prompt evidence, and uses the cohort's stop state when deciding whether a complete-cohort contrast may be reported. An interrupted cohort cannot become a complete analysis merely because its last scheduled attempt was initiated.

The corrected task and runner source were inspected before any outcomes were accessed by this reviewer. No claim is made that code inspection or synthetic regression controls constitute model observations.

## Synthetic checks and freeze gate

The reviewer ran the 37 offline scorer/ledger regression tests on Windows; all passed. These tests cover JSON/type/escape failures, truncation, unknown transport behavior, reservation persistence, caps, rollback, concurrency, and evidence preservation. They invoke no model. A separate implementation reviewer completed 19 synthetic transport/analysis tests, including local-only access, deadline interruption, raw-prefix preservation and tampered-evidence rejection. The experiment owner ran all 56 tests together before freezing; all passed. The mocked 72-case transport check is test code, not a model experiment and not part of the empirical result denominator.

Before the first generation, freeze exactly these thirteen files and require all hashes to match: `tasks.json`, `DESIGN.md`, `prepare.py`, `cases.jsonl`, `evaluate.py`, `test_evaluate.py`, `run_local.py`, `analyze.py`, `plan.json`, `MODEL-LICENSE.txt`, `model-template.txt`, `test_runner.py`, and `PRE_RUN_REVIEW.md`. The runner rejects duplicate, missing, or unexpected entries. The freeze record must be timestamped before the first ledger reservation. Its hash belongs in execution evidence, not recursively in this included review file.

This is a developmental feasibility pilot. All tasks are consumed development data. It cannot establish a universal attack, compassion-specific causation, population effect size, defense efficacy, or confirmatory statistical inference. Further confirmation requires newly authored independent task origins and a justified design.
