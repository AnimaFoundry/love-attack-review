# Compassion and Legitimacy Framing in LLM Systems

**Evidence, Threat Boundaries, and a Controlled Evaluation Protocol**  
AnimaFoundry · Companion package 1.3.0 · Manuscript 1.0.0 · 26 October 2026

A selective critical integrative review and a prospective benign evaluation protocol. **The manuscript is an unchanged research preprint, not peer reviewed.** Package 1.3.0 adds BF-01C, a task-only comparison of source-state correctness, output contracts and schema-constrained generation. Its [negative and mixed findings](pilot/bf01c/REPORT.md) accompany the retained [BF-01B report](pilot/bf01b/REPORT.md) and [first pilot report](pilot/bf01/REPORT.md); they are not retroactively inserted into the paper. No validated general defense or confirmatory framing result is claimed.

The informal project label *The Love Attack* names the originating question. It is not a demonstrated new exploit or an established attack class.

## Read and cite

- [Read the paper in Markdown](paper.md) or [download the PDF](paper.pdf).
- [Citation File Format](CITATION.cff), [BibTeX](citation.bib), and [CSL-JSON](citation.csl.json).
- [Source ledger and claim limitations](references.json).
- [Versioned releases](https://github.com/AnimaFoundry/love-attack-review/releases).

Suggested citation: AnimaFoundry. (2026). *Compassion and Legitimacy Framing in LLM Systems: Evidence, Threat Boundaries, and a Controlled Evaluation Protocol* (Version 1.0.0) [Preprint]. https://github.com/AnimaFoundry/love-attack-review

For observations from BF-01 or BF-01B, cite the corresponding pilot report and the [version 1.2.0 companion release](https://github.com/AnimaFoundry/love-attack-review/releases/tag/v1.2.0). The unchanged version 1.0.0 manuscript does not contain these pilot results.

For BF-01C, cite its [report](pilot/bf01c/REPORT.md) and the
[version 1.3.0 companion](https://github.com/AnimaFoundry/love-attack-review/releases/tag/v1.3.0).

## What this paper contributes

It separates useful emotional adaptation, task-contract failure, evaluator manipulation, unauthorized actions, repeated output, and service-level disruption. Existing findings about these outcomes have different tasks and denominators and cannot be combined into a single attack success rate.


## Historical research opportunities and current pilot

| Card | Question | Status in the unchanged v1.0.0 protocol |
|---|---|---|
| BF-01 | Can semantic compassion and legitimacy framing change adherence while task and authority remain fixed? | NOT_PERFORMED |
| BF-02 | Can a short repeated-symbol cue explain repetition independently of semantic framing? | NOT_PERFORMED |
| BF-03 | Can defenses retain legitimate utility under an equal total resource ceiling? | NOT_PERFORMED |
| BF-04 | Does an effect depend on retained context or an explicit toy-memory channel? | NOT_PERFORMED |

The original [EXPERIMENT_HANDOFF.md](EXPERIMENT_HANDOFF.md) and [protocol.json](protocol.json) remain historical prospective documents. Their `NOT_PERFORMED` statuses and unfrozen confirmatory designs are preserved. The retained BF-01 feasibility companion is a narrower developmental study; it does not complete the broad prospective card or change the status of BF-02, BF-03 or BF-04.

### BF-01C: task-only source-state and output-contract feasibility

Read the [report](pilot/bf01c/REPORT.md), [fixed plan](pilot/bf01c/PLAN.md),
[pre-run review](pilot/bf01c/PRE_RUN_REVIEW.md), [26-file freeze](pilot/bf01c/FREEZE.json),
[collection ledger](pilot/bf01c/run/summary.json) and
[machine-readable scores](pilot/bf01c/run/score.json).

Eight new original synthetic complete records were each sent in four conditions.
All **32/32** local calls completed once, using **1,114 output tokens in 61.719
seconds**, with **USD 0 external API fees**, no retries and no new model download.
The frozen ceilings were 32 calls, 8,192 tokens, 600 seconds total and 30 seconds
per call. The first schema compatibility observation counted toward the budget.
All raw request/response bytes are retained. No private case was used.

| Condition | Strict contract valid | State/value correct | Joint usable answer |
| --- | ---: | ---: | ---: |
| Schema + evidence | 0/8 | 5/8 | 0/8 |
| Raw, no evidence | 7/8 | 3/8 | 3/8 |
| Schema, no evidence | 8/8 | 4/8 | 4/8 |
| Raw + evidence | 5/8 | 4/8 | 3/8 |

All 32 replies were valid strict JSON. The schema-evidence condition nevertheless
omitted four mandatory evidence identity fields in all eight replies. This is
observed contract nonconformance in the model/runtime/schema combination; this
study does not isolate which component caused it. Successful API completion is
not evidence that every schema constraint was enforced. Its 0/8 joint score must
not be described as eight semantic state errors.

Structural validation accepted 10 correct and 10 wrong outputs, rejecting 12.
Source-consistency checking accepted 10 correct and no wrong outputs, rejecting
22: **31.25% coverage**, not a solution that supplies every answer. Deterministic
lookup already answered all eight sources correctly under both contracts. The
source gate and baseline share parsing code and apply only to this explicit
synthetic grammar; neither establishes external-world truth.

The predesignated schema-evidence competence gate **failed**. No joint-usable
unknown/absent answer was observed in any arm. Social-framing experiments stop
here; no new inference is automatically launched. This is one small development
cohort, not an emotional-attack success rate, general model comparison or product
novelty claim. Any later schema-compatibility work requires a new fixed scope and
budget; this consumed cohort cannot become a holdout.

```sh
python -m unittest discover -s pilot/bf01c -p 'test_*.py' -v
python pilot/bf01c/verify_saved.py --check
```

These commands use saved evidence only. The live runner has a one-run guard and
must not be rerun or have its guard removed to reset this research budget.

### BF-01B: content usefulness, correctness and trustworthiness

Read the [results report](pilot/bf01b/REPORT.md), [design](pilot/bf01b/DESIGN.md),
[plan](pilot/bf01b/plan.json), [pre-run review](pilot/bf01b/PRE_RUN_REVIEW.md),
[freeze](pilot/bf01b/freeze.json) and [machine-readable outcomes](pilot/bf01b/run-001/summary.json).
This study examines content integrity rather than latency, crashes or service load.
It authors 24 new inputs in six representations of one source-state operation:
observed zero, observed positive, explicit unknown and absent evidence.

All 168 calls completed once. Raw JSON acceptance was 0/168. Ordinary extraction
recovered 79 correct answers but also accepted 87 wrong objects; adding the
structural schema rejected none of those 87. Matched social prefixes did not
increase accepted-wrong counts over their plain counterparts. These pooled
counts include control failures and are not an emotional-attack success rate.

Seven arms compare task-only and neutral context against plain format/default
requests, matched relational/legitimacy variants, and a combined stress condition.
The authoritative SYSTEM contract never changes. Lower-priority requests try
to elicit added reassurance or fabricated observed zeros. The plain/social pairs
share the same operative request, but length/salience confounds remain; the
combined condition is not a factorial interaction test. These are developmental
wording interventions, not a reproduction of a private case or a new attack class.

The frozen ceiling is 168 calls on the already installed local model, 128 output
tokens per call, 20 minutes globally, 45 seconds per call, concurrency one and
USD 0 external API spending. No retry, auxiliary call or new download is included.
All initiated outcomes are retained. Actual completion is stated in the report;
scheduled calls alone are not observations.

Four source-independent offline pipelines process the same saved responses:
raw JSON, exact single-fence parsing, conservative single-object extraction,
and structural schema filtering after extraction. The answer key scores outputs
only after acceptance. The report distinguishes correct answers restored by
format repair, wrong answers rejected without correction, and wrong answers
accepted despite valid structure. Accepted coverage and false-acceptance counts
prevent a filter that rejects everything from appearing useful.

```sh
python -m unittest discover -s pilot/bf01b -p 'test_*.py' -v
python pilot/bf01b/analyze.py pilot/bf01b/run-001 --check
```

These commands are offline and do not repeat inference. A future live run needs
its own finite budget and unused destination; this development set is consumed
evidence and cannot become an untouched confirmation set. BF-02/03/04 remain
unperformed, and the original broader BF-01 protocol is not completed by these
small studies.

### Retained BF-01 feasibility companion

Read [REPORT.md](pilot/bf01/REPORT.md) for actual completion, all observed failures and interpretation. The [task design](pilot/bf01/DESIGN.md), [frozen plan](pilot/bf01/plan.json), [pre-run review](pilot/bf01/PRE_RUN_REVIEW.md), [source freeze](pilot/bf01/freeze.json) and [retained run evidence](pilot/bf01/run-001/) make the limited study auditable. Thirteen task, source, plan, review and model-license/template files are frozen before inference; raw outcomes and their analysis are retained separately.

The plan specifies 12 original synthetic tasks in **four authored template families**, with six conditions: four compassion-by-legitimacy wording combinations, a task-only control and a neutral longer-text diagnostic. It uses deterministic counterbalancing, not randomized causal assignment. Twelve task instances and 72 scheduled calls are not 12 or 72 independent task origins. All items are development data; no untouched confirmation set or power calculation is claimed. Length matching is approximate, and the wording contrasts do not isolate a psychological mechanism.

The exact local model is `qwen2.5:1.5b-instruct-q4_K_M`, 986,061,892 bytes, under the model's Apache-2.0 terms. Its digest, template, runtime and settings are recorded in the plan. The finite ceiling is 72 calls, temperature 0, at most 512 generated tokens per call, 40 minutes total inference time, 120 seconds per call and concurrency one. There are no retries or auxiliary inference calls. The approved download is approximately 1 GB and the external API budget is USD 0; local electricity and hardware are not claimed to be free. These are ceilings and scheduled counts, not assertions that every case completed.

#### Offline inspection and analysis

From the repository root, these commands make no model calls and download no model:

```sh
python pilot/bf01/prepare.py
python -m unittest discover -s pilot/bf01 -p 'test_*.py' -v
python pilot/bf01/analyze.py pilot/bf01/run-001 --check
```

`prepare.py` generates the finite schedule without inference. It is idempotent for the retained identical schedule and refuses to replace a different existing schedule. `analyze.py --check` reconstructs scores and descriptive summaries from the retained raw responses and checks the saved summary without changing it. Expected answers and audit reasoning are scoring materials; the live request contains only the frozen messages.

#### Live repetition is a separate decision

The runner requires an already installed local model and runtime matching the exact frozen metadata. It does not pull a model automatically. Before any separately authorized repetition, review the plan and source freeze, confirm rights and the complete attempt/token/time budget, and use a new, unused destination:

```sh
python pilot/bf01/run_local.py --destination pilot/bf01/run-new
```

This command can initiate a new 72-call cohort; **do not run it as part of an ordinary document rebuild or automatically repeat a failed or uninteresting cohort**. An existing destination is never resumed or overwritten. A new directory does not itself authorize resetting a research budget. Metadata mismatch, transport uncertainty or a budget breach stops collection; audit an incomplete run before deciding on new work. An independent repetition may produce different output even with the same seed and temperature. Preserve each initiated outcome and every unattempted ID, rather than replacing failures with retries.

## Rebuild the publication package

Use Python 3.12 from the repository root:

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m unittest discover -s pilot/bf01 -p 'test_*.py' -v
python pilot/bf01/analyze.py pilot/bf01/run-001 --check
python scripts/verify_metadata.py
python -m unittest discover -s pilot/bf01b -p 'test_*.py' -v
python pilot/bf01b/analyze.py pilot/bf01b/run-001 --check
python -m unittest discover -s pilot/bf01c -p 'test_*.py' -v
python pilot/bf01c/verify_saved.py --check
python scripts/build_paper.py --output-dir build/reproduced
python scripts/verify_artifacts.py --rebuild-dir build/reproduced
```

Document rebuilding and metadata tests validate publication artifacts. Offline pilot checks validate retained evidence and recompute its scores; they do not execute the model again. Ubuntu CI performs these offline checks and the paper rebuild, with no model download or live inference. It is not a Linux model replication, reproduction of cited studies, or empirical validation of the general framing hypothesis. The release manifest lists exact public files and SHA-256 digests. It excludes itself to avoid a recursive hash definition.

## Evidence and reuse boundaries

Original prose, schematic, protocol and synthetic pilot inputs: [CC BY 4.0](LICENSE-TEXT). Publication and pilot scripts, tests and workflows: [MIT](LICENSE-CODE). The third-party CFF schema carries its own license and provenance under `schemas/`. The model template and complete Apache-2.0 notice are retained in the pilot directory. See [SOURCE_AND_RIGHTS.md](SOURCE_AND_RIGHTS.md) for model sources and output boundaries.

The pilot retains raw model responses only to the project's original synthetic prompts. It includes no private conversation case or real customer record. This package does not redistribute third-party papers, benchmark prompts or model weights. Citation is not permission to copy those materials. No patent clearance, novelty, freedom-to-operate conclusion, peer-review status or empirical defense guarantee is claimed.

The paper and structured companion files can be read directly without executing code. We make no claim that search engines or agents have indexed, crawled, trained on, or endorsed them. Please file a reproducible correction through this repository's Issues, omitting credentials and private transcripts.
