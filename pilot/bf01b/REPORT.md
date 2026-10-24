# BF-01B: Content integrity under competing instructions and ordinary output validation

**Developmental local study; companion package 1.2.0; 24 October 2026.**

## Finding and scope

The single frozen cohort completed all 168 scheduled calls. Ordinary parsing
recovered 79 correct objects from responses that all failed the strict raw JSON
contract. However, 87 extracted objects were factually wrong while satisfying
every structural schema rule. The schema filter rejected none of those 87.
Recovering parseability therefore did not establish source correctness.

The matched social-prefix comparisons did **not** show increased accepted-wrong
counts: relational versus plain format wording was 13 versus 13, and legitimacy
versus plain default wording was 13 versus 14. These negative or mixed results
are retained. Many failures existed without a competing request. The total
87/168 is a pooled outcome count, **not an attack success rate or an estimate of
failures caused by emotional framing**.

This is one small quantized model, six authored representations of one semantic
operation, 24 related inputs and one draw per arm. It is not confirmatory,
externally preregistered, peer reviewed, or a reproduction of a private case.
Latency, crashes and service load are not effectiveness endpoints. No unsafe
real-world task, external action, private record or model-weight redistribution
is included. The original manuscript and prior BF-01 evidence remain unchanged.

## Frozen method and execution

The [design](DESIGN.md), [tasks](tasks.json), [168-case schedule](cases.jsonl),
[plan](plan.json), [pre-run review](PRE_RUN_REVIEW.md) and [freeze](freeze.json)
specify inputs and methods before inference. The SYSTEM contract requires an
exact two-field object preserving observed zero, observed positive, explicit
unknown or absence. USER supplements cannot override that contract. Seven arms
include task-only, neutral context, plain format/default requests, matched
relational/legitimacy variants and a combined condition. The matched pairs share
their operative request; added prefixes still change length and salience.
The combined arm lacks a combined-plain comparator and cannot estimate synergy.

The model was the already installed Apache-2.0
`qwen2.5:1.5b-instruct-q4_K_M`, 986,061,892 bytes, served by Ollama 0.40.10.
Its digest is
`65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`.
Temperature was 0, seed 20261025, context limit 4096 and output limit 128 tokens.
There was no constrained-decoding format argument. Each call used fresh SYSTEM
and USER messages, no tools, no persistent memory and concurrency one. The
deterministic rotated schedule is not randomized assignment. These newly
authored cases were informed by earlier developmental findings and are not an
untouched confirmation set.

| Resource or event | Frozen ceiling | Actual retained execution |
|---|---:|---:|
| Initiated calls | 168 | 168 |
| Generated tokens | 21,504 total; 128 per call | 3,711 total |
| Global inference duration | 1,200 seconds | 756.609 seconds |
| Per-call deadline | 45 seconds | No deadline/budget exclusion |
| External API spending | USD 0 | USD 0 |
| Retries / auxiliary inference / new downloads | 0 / 0 / 0 | 0 / 0 / 0 |

All calls returned; none was truncated, unattempted or lost to transport error.
Input token usage was 68,343; input and output usage were known for every call.
Local hardware and electricity are not claimed to be free. Collection opened
at `2026-10-24T13:58:20.268639Z` and finished at
`2026-10-24T14:10:56.890924Z`. Raw HTTP bodies, decoded replies, request hashes,
initiation records and completion records are preserved under [run-001](run-001/).

Sixteen source/task/plan/review/license files were frozen at
`2026-10-24T13:57:59.054507Z`; freeze SHA-256:
`6eae8d8241493f411a43dee2715855f32140c5714e913ccf84bb8e554f031c4d`.
All sixteen remained unchanged. Before the successful freeze, a stale generated
schedule was refused because final task authoring removed four trailing empty
separators. No inference had started; 28 variants were regenerated and tests
rerun. This is disclosed in the pre-run review. Local hashes support consistency
checking; they are not an external timestamp authority or proof against
deliberate rewriting.

## Four pipelines on the same outputs

All four offline pipelines were fixed before collection. They receive no source
facts or answer key. The expected answer is used only afterward to score the
accepted object. They neither rewrite values nor make repair model calls.
The single-object extractor includes the fence-parser step. The schema filter
is applied after that same extraction, and accepts or rejects structural rules
only. Rejection is abstention, not a corrected answer.

| Pipeline | Accepted correct | Accepted wrong | Rejected | Accepted coverage | Correct among accepted | Correct per initiated |
|---|---:|---:|---:|---:|---:|---:|
| Raw whole-response JSON | 0 | 0 | 168 | 0/168 (0%) | Undefined | 0/168 (0%) |
| Exact single-fence parser | 78 | 87 | 3 | 165/168 (98.21%) | 78/165 (47.27%) | 78/168 (46.43%) |
| Conservative single-object extractor | 79 | 87 | 2 | 166/168 (98.81%) | 79/166 (47.59%) | 79/168 (47.02%) |
| Extractor plus structural schema | 79 | 87 | 2 | 166/168 (98.81%) | 79/166 (47.59%) | 79/168 (47.02%) |

No pipeline had unavailable, truncated or budget-excluded calls. Each row sums
to the same 168 initiated calls. The last two pipelines' silent-error count was
87/168 (51.79%). The raw parser's zero false accepts came with zero delivered
answers; this is not useful task completion or evidence of an effective defense.

The fence parser restored 78 correct answers. The stronger extractor restored
**one additional** correct answer, for 79 total, not 78 plus 79. The extra case
was `BF01B-LOG-03__FORMAT_PLAIN`: a correct object was followed by reassurance
inside an unclosed Markdown fence. The fixed extractor could preserve the
single unambiguous object despite that surrounding text. Two task-only compact
frame replies used non-JSON `state: observed` notation and stayed rejected.
The schema stage added zero rejections or corrections because all 166 extracted
objects already satisfied its structural rules.

## Arm comparisons and the baseline floor

All seven arms had **0/24 strict raw successes**. Thus the strict endpoint has a
complete floor and cannot show an increase in failure caused by a supplement.
The downstream frozen endpoints remain separately informative; they do not
replace the failed strict endpoint after the fact.

| Arm (24 calls each) | Fence correct | Extractor/schema correct | Extractor/schema wrong | Extractor/schema rejected |
|---|---:|---:|---:|---:|
| TASK_ONLY | 12 | 12 | 10 | 2 |
| NEUTRAL_CONTEXT | 14 | 14 | 10 | 0 |
| FORMAT_PLAIN | 10 | 11 | 13 | 0 |
| RELATIONAL_FORMAT | 11 | 11 | 13 | 0 |
| DEFAULT_PLAIN | 10 | 10 | 14 | 0 |
| LEGITIMACY_DEFAULT | 11 | 11 | 13 | 0 |
| COMBINED | 10 | 10 | 14 | 0 |

Paired changes below count whether each of the same 24 inputs produced an
accepted-wrong object. “Wrong only in A/B” does not by itself mean the other
response was correct; it could have been rejected.

| Comparison A to B | Wrong in both | Wrong only in A | Wrong only in B | Net B minus A |
|---|---:|---:|---:|---:|
| TASK_ONLY to NEUTRAL_CONTEXT | 9 | 1 | 1 | 0/24 |
| NEUTRAL_CONTEXT to FORMAT_PLAIN | 10 | 0 | 3 | +3/24 |
| FORMAT_PLAIN to RELATIONAL_FORMAT | 12 | 1 | 1 | 0/24 |
| NEUTRAL_CONTEXT to DEFAULT_PLAIN | 10 | 0 | 4 | +4/24 |
| DEFAULT_PLAIN to LEGITIMACY_DEFAULT | 13 | 1 | 0 | -1/24 |
| NEUTRAL_CONTEXT to COMBINED | 10 | 0 | 4 | +4/24 |

Ordinary competing requests were associated with more accepted-wrong outputs
than neutral context in this finite cohort. The social additions did not
increase those totals; equal totals in the relational pair still conceal one
change in each direction. None of these descriptive contrasts establishes a
psychological mechanism, statistical significance, equivalence, or general
attack efficacy. No p-values or population uncertainty intervals are claimed.

## Source-state and representation checks

| Source state (42 calls each) | Correct after extraction/schema | Wrong accepted | Rejected |
|---|---:|---:|---:|
| Observed zero | 25 | 17 | 0 |
| Observed positive | 35 | 7 | 0 |
| Explicit unknown | 19 | 22 | 1 |
| Absent target | 0 | 41 | 1 |

Absence was never correctly represented, including task-only and neutral
controls. It is therefore a baseline capability/attribution problem in this
setup, not a demonstrated induced failure. Observed-zero controls also failed
17 times even though the default request explicitly left observed values alone.
The state-specific split prevents those failures from being mislabeled as
successful unknown-to-zero manipulation.

Among six explicit-unknown inputs per arm, accepted-wrong counts were 1, 1, 3,
3, 5, 4 and 5 in the arm order above. A **post hoc descriptive inspection** of
the 87 wrong accepted objects found that all reported `state: observed` with an
integer. Of 63 wrong outputs on unknown/absent sources, only 11 supplied zero
(six unknown and five absent); the other 52 supplied nonzero values. The
remaining 24 errors changed actually observed values. This is not merely a
zero-versus-null format problem. These categories describe saved outputs and
do not prove why a particular number was selected.

| Representation (28 calls each) | Correct after extraction/schema | Wrong accepted | Rejected |
|---|---:|---:|---:|
| Compact frame | 16 | 10 | 2 |
| Controlled status prose | 21 | 7 | 0 |
| Field events | 10 | 18 | 0 |
| Nested schema record | 2 | 26 | 0 |
| Optional tuple slot | 19 | 9 | 0 |
| Table row | 11 | 17 | 0 |

Variation across these authored representations is substantial. The cases are
related convenience examples of one operation, not 168 independent task
origins, six sampled deployment populations, or a representative reliability
benchmark. Aggregation over deliberately balanced states and arms does not
estimate the prevalence of failure in a production workload.

## Verification, implications and next experiment

The 103 frozen offline tests passed before inference. After completion, a
separate assistant reviewer copied only the 16 frozen files, freeze record and
five run files into an isolated directory. With HTTP/socket access blocked,
all 103 tests and saved-data replay passed. An independent parser/extractor/
schema implementation reproduced all four lane counts directly from the 168
raw responses and checked hashes, chronology, requests, tokens and budgets.
This is independent computation and internal review, not independent model
inference or external human peer review. The repository workflow also runs
publication tests, retained BF-01/BF-01B offline checks and a byte-checked paper
rebuild; it does not download or execute a model. Actual release CI status is
available in the repository Actions records.

The practical result is narrow: ordinary extraction resolves many presentation
failures, while a source-blind schema cannot certify factual attribution.
No specialized emotional defense is justified by these observations. More
aggressive within-cohort prompt evolution would risk selecting against already
consumed outcomes, so no such tuning or second cohort was performed.

The most useful next experiment is to establish a reliable content baseline
before measuring added framing effects. Use wholly new synthetic inputs and a
separate finite budget. Freeze: (1) explicit target-evidence pointers and a
source-aware deterministic baseline for the declared input grammars; (2) a
structural-only comparator and, separately, constrained JSON generation; (3)
unchanged authoritative rules with plain/social competing-request pairs; and
(4) source-state coverage, accepted-wrong outcomes and genuine baseline
competence/stop criteria. A pointer must resolve to the correct target, not
merely cite some existing number. Keep unknown and absent distinct. Such a
source-aware implementation must be independently tested; the existing answer
key is an evaluation oracle, not an already implemented defense. A source-aware
program for these grammars would not by itself solve arbitrary natural-language
factuality. The new experiment has **not been performed**, and no effectiveness
claim or additional inference budget is implied here.

## Reproduce the saved analysis without inference

From the repository root:

```sh
python -m unittest discover -s pilot/bf01b -p 'test_*.py' -v
python pilot/bf01b/analyze.py pilot/bf01b/run-001 --check
```

The [summary](run-001/summary.json) contains every case diagnostic, full lane
counts, family/state strata, all raw failures and paired comparisons. Retain
the entire cohort, including controls and negative findings. Do not rerun or
relabel it as untouched confirmation data. Original synthetic text is CC BY
4.0; original code is MIT; model permissions and retained notices are described
in [SOURCE_AND_RIGHTS.md](../../SOURCE_AND_RIGHTS.md). No private case or its
distinctive content, counts or links is included.
