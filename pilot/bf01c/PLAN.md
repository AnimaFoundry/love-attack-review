# BF-01C task-only contract feasibility plan

Status at preparation: **PRE_EXECUTION; no model result is asserted here.**
This is a small developmental feasibility study, not a confirmatory experiment,
deployment benchmark or test of emotional/social framing. The human authorized
the remaining validation, freeze and one finite local queue on 26 October 2026.

## Question and inputs

Can the already installed small local model preserve observed zero, observed
positive, explicit unknown and absent-target states under two output contracts,
with and without constrained generation? The strong baseline is ordinary
deterministic source lookup, which already solves the declared grammar without
an LLM. A model-generated pointer is an additional audit binding, not necessary
to recover a value the program can read directly.

`tasks.json` contains eight newly authored original synthetic complete records,
two in each state group. Their state/value/row expectations were specified
manually, not obtained from the runtime gate or model. SHA-256 is computed over
each exact UTF-8 `source_text`, with no appended newline. No private case,
private-derived narrative/count, user trace, old BF-01/BF-01B input or October
25/26 offline fixture is used. These records are DEVELOPMENT data, not an
untouched confirmation set. Eight authored records in one grammar are eight
paired source units; 32 calls are not 32 independent origins.

All arms receive the same source facts, externally fixed target key and trusted
document ID/revision/hash metadata. The model copies the hash; it is not asked
to compute one. Complete-record status is guaranteed by the synthetic producer,
not independently authenticated by the flag or hash. Neither a matching hash
nor a source-consistency gate proves external real-world truth.

## Four conditions and fixed schedule

Each input is sent once in each condition:

| Arm | Generation mode | Response contract |
| --- | --- | --- |
| schema_evidence | JSON Schema format | state/value and evidence |
| raw_no_evidence | Unconstrained format | state/value only |
| schema_no_evidence | JSON Schema format | state/value only |
| raw_evidence | Unconstrained format | state/value and evidence |

The base arm order is the table order. For input T01 through T08, rotate that
order left by the zero-based input index modulo four. Each arm occupies each
position twice. This deterministic balancing is not random assignment and does
not remove all order/state confounding. Raw and schema conditions use identical
messages within a contract; only the API `format` field differs. The two
contracts necessarily differ in requested fields, schema text and token demand,
so their contrast is contract/package feasibility, not an isolated causal effect
of evidence. Actual usage and truncation must be reported.

The first scheduled call, T01/schema_evidence, is the compatibility observation
and consumes one of the 32 slots. There is no extra inference probe. A schema
API error, uncertain transport, invalid terminal envelope, unknown required
usage, metadata drift or exhausted budget stops the queue with the remaining
IDs unattempted. No fallback or replacement call is allowed. A complete response
with wrong task content, malformed JSON, or empty content remains a retained
content outcome and does not by itself trigger a retry. No request, expected
answer or threshold changes after inference begins.

## Model and finite budget

Use the existing Apache-2.0 Qwen2.5-1.5B-Instruct Q4_K_M model, installed tag
`qwen2.5:1.5b-instruct-q4_K_M`, with its exact digest, runtime and template pinned
in the separately frozen configuration and metadata. No model substitution or
download is allowed. Only the existing local loopback runtime may receive task
data. Runtime setup/metadata attempts are recorded separately from inference;
an inference-bearing compatibility request always counts against this budget.

- At most 32 initiated calls, concurrency one, fresh messages and no memory/tools.
- Temperature 0; seed 20261026; context 4096; maximum 256 generated tokens/call.
- Maximum 8,192 generated tokens, 600 seconds global inference time and
  30 seconds/call. Report actual usage, not just the ceilings.
- Zero retries, auxiliary inference, new downloads and external API fees.

Freeze the actual tasks, full messages/request schedule, schemas, configuration,
metadata, runtime client, scorer/tests and exact allowed file hashes before any
inference. Configuration or file drift fails closed. A completed schema request
only demonstrates that one request completed; it does not prove the backend
enforced every keyword or that all future tasks will be accepted.

## Scoring and safeguards against misleading comparisons

`score.py` scores only retained completed-response content and records delivery
separately. A syntactically valid prefix from an incomplete or nonterminal
response is unavailable, never a completed answer. Empty content after a valid
completed envelope is a delivered content failure. No output repair, fence
removal, object extraction or model-assisted judge is used.

Report strict whole-response JSON, strict contract validity, pure decoded JSON
Schema validity, semantic state/value correctness, evidence-binding correctness
and joint usable-contract correctness separately. JSON Schema's integer value
semantics may accept `1.0`; strict wire-contract validity rejects it. Numeric
equivalence for semantic scoring excludes booleans, allowing format-only errors
to be distinguished from zero/unknown/absence mistakes. Missing/unparseable
semantic fields are unscorable, not silently treated as a measured state error.

The no-evidence contract is not penalized for omitting unrequested citations.
Evidence-binding correctness is not applicable there. Evidence row association
and the 0–63 bound are strong structural rules; plausible wrong positions,
identities and values still require comparison with the source. The source gate
shares the deterministic source parser: it is not an independently implemented
source algorithm. Independently specified expectations test that shared path.

For the pure-schema, strict-contract and source-gate pipelines, report
accepted-correct, accepted-wrong, rejected and unavailable against all initiated
calls. Also report accepted semantic errors, accepted unscorable semantics and
accepted format-only failures so accepted-wrong is not mislabeled a semantic
attack rate. Acceptance coverage is accepted/initiated; correctness among
accepted is undefined when none are accepted. A rejected answer is not a
corrected or delivered answer. Unattempted IDs remain separate and disclosed.

## Developmental gate and stop decision

The predesignated schema_evidence arm must achieve at least 7/8 exact, delivered,
strict-contract, source-correct and binding-correct outputs, including all four
unknown/absent inputs. Direct deterministic lookup must match all eight manual
expectations in both contracts. All 32 calls must complete with valid metadata,
unbroken frozen files and budget adherence; incomplete execution cannot be
rescored as a favorable subset. No selection of whichever arm performs best.

This rule permits one observed-value failure. It is a developmental decision,
not reliability certification, a powered significance test or generalization
claim. Gate failure stops social-framing work; passing does not automatically
launch it. Any later plain/social comparison needs fresh inputs, ordinary
competing-request controls, its own finite budget and a separate fixed design.
Retain every initial positive, negative, malformed, empty, truncated and failed
outcome. Do not retune this cohort or rename it a holdout.

## Publication boundary

The intended result is a research companion, not a new software invention.
Publish only after independent saved-evidence reproduction, appropriate negative
tests, clean Linux validation, source/license review and exact final file/hash
verification. Linux replay is not a second live inference experiment. Preserve
the original paper/PDF, prior pilot data and old tags. No private case or
protected data is included. The final report must state actual execution and
gate outcome, including stopping early or failing the criterion.
