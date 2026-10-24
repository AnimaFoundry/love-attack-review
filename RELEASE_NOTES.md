# Companion package 1.2.0

Add BF-01B: original synthetic content-integrity stress tests and four fixed
offline output-processing baselines. See [the new report](pilot/bf01b/REPORT.md)
for the actual retained outcomes, rather than treating the planned 168 cases as
completed observations. The original manuscript, first pilot and prior tags
remain unchanged.

The cohort did complete all 168 calls, with no retries, truncations or transport
errors. All strict raw replies failed format. Fence parsing recovered 78 correct
answers and single-object extraction recovered one more. Extraction plus schema
accepted 79 correct and 87 wrong objects, rejecting two; schema added no error
interception. Relational versus plain-format arms each had 13 wrong accepts;
legitimacy versus plain-default arms had 13 versus 14. Baseline errors and a raw
score floor prevent interpreting pooled failures as successful emotional attacks.

The new design distinguishes format recovery, rejection/abstention and accepted
factual error. Seven arms include plain requests matched to social wording;
24 instances cover six representations of one semantic operation. All inputs,
strategies, validators, scoring and the finite budget are frozen before collection.
It targets content usefulness and source-state truth, not performance faults.
No private case, new model download, paid API or outcome-driven prompt revision.
The 128-token/call, 168-call and 20-minute global ceilings are safeguards.

Offline tests and saved-output replay are added to Ubuntu CI. They do not repeat
model inference or validate a universal defense. The two studies are developmental
companions, not completion of the broader prospective research cards.

# Companion package 1.1.0

BF-01 developmental feasibility companion, 24 October 2026. The manuscript, PDF and historical prospective protocol remain at version 1.0.0; the original tag is preserved.

- Add 12 original synthetic task instances in four authored template families, a six-condition schedule, strict JSON scoring and a bounded local-only runner.
- Record the exact Qwen2.5-1.5B-Instruct Q4_K_M model configuration, model template and complete Apache-2.0 license. No model weights are redistributed.
- Freeze 13 task/source/plan/review/license files before inference and retain raw outcomes, attempt records and offline analysis separately. See [REPORT.md](pilot/bf01/REPORT.md) for actual execution status and observations; the planned 72 calls are not a claim that all calls completed.
- Add offline scorer/transport tests and raw-evidence analysis to publication validation. Ubuntu CI does not download a model or perform inference. Reproducing the saved summary is distinct from executing the model again.

The frozen ceiling is 72 calls, temperature 0, 512 generated tokens per call, one concurrent call, 120 seconds per call, 40 minutes total inference time and USD 0 external API expenditure, with no retries or auxiliary inference. The authorized model download is approximately 1 GB. Counterbalancing is deterministic; framing contrasts are descriptive and input lengths are not exactly tokenizer-matched. Four convenience-authored families and one quantized model do not support a powered confirmatory conclusion, equivalence, general robustness or a new attack mechanism.

The BF-01 companion is a limited development study, not completion of the broader historical BF-01 protocol. BF-02, BF-03 and BF-04 remain prospective. No individual conversation case, private transcript, active jailbreak payload, propagation mechanism or service-load experiment is included. Live repetition requires a separately reviewed budget and an unused destination; it is not part of an ordinary offline rebuild.

# Version 1.0.0

Initial English research preprint and companion package, 24 October 2026.

- Selective critical integrative review of 17 sources, with claim-level limitations.
- Four prospective experiment cards, including separate semantic-framing and repeated-symbol controls.
- PDF, readable Markdown, citation metadata, deterministic publication builder, and integrity checks.

No controlled model experiment, power analysis, preregistration, validated defense, or new attack mechanism is reported. No individual conversation case or private transcript is included. Version and artifact verification concern this publication package, not empirical confirmation of its hypotheses.
