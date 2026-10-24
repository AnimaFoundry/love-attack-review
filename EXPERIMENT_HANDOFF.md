# Experiment handoff: benign framing and task-contract robustness

**Status: NOT PERFORMED.** This document and [protocol.json](protocol.json) describe prospective studies. No model experiment, feasibility pilot, power analysis, external human validation, or preregistration is complete. Prompts, sample sizes, model versions, useful-effect margins, and budgets remain unfrozen. This release supplies a research plan, not a runnable benchmark or evidence of a new attack.

## First decision: separate meaning from surface cues

Start with **BF-01**, a benign 2x2 design crossing compassion framing and normative framing. Each condition retains the same task facts, correct answer, authorization and output contract. Use two fixed-position framing slots, replacing absent treatments with matched neutral statements. Include a separate task-only baseline. Match syntactic function and approximate input length within each model; do not claim exact token matching across unrelated tokenizers.

The semantic study contains **no emoji run, decorative repeated symbol or request for repetition**. A compassion condition must not change a strict JSON task into a request for comforting prose. Legitimate warmth, when the unchanged contract permits it, is not a failure.

Then assess **BF-02** as a separate surface-cue control. Compare semantic framing without symbols, a strictly bounded inert symbol cue, neutral-symbol controls, and length-matched nonrepeating alternatives. Cross semantic framing with cue repetition where feasible, while treating symbol identity separately. No cue asks the model to continue, copy or propagate it, and no cue strings are supplied here. This comparison distinguishes a possible semantic framing effect from generic repetition priming; it does not presume either exists.

## Four proposed studies

| ID | Decision question | Strong baseline | First deliverable | Current status |
|---|---|---|---|---|
| BF-01 | Does semantic compassion change contract adherence under fixed tasks? | Matched neutral framing, task-only prompt, neutral-length diagnostic | Reviewed matched-item set and deterministic task scorers | NOT PERFORMED |
| BF-02 | Could surface-symbol exposure explain apparent repetition? | Same semantic framing without symbols, neutral symbols, nonrepeating text | A separately reviewed cue-control design | NOT PERFORMED |
| BF-03 | Can validation/recovery reduce failures without unacceptable utility loss? | Undefended, budget-only and schema-only systems; reject-all utility reference | Resource-accounted component ablations and utility criterion | NOT PERFORMED |
| BF-04 | Does randomized benign history affect a later unchanged task? | Matched neutral history and fresh context without memory | Observable session-reset and matched-sequence plan | NOT PERFORMED |

For fixed model m, let p_m(c,l) be the prespecified cluster-weighted risk of bounded task non-success. The proposed primary BF-01 contrast is:

```
Delta_C = 0.5 * [(p_m(1,0)-p_m(0,0)) + (p_m(1,1)-p_m(0,1))]
```

The normative main effect and risk-difference interaction are secondary. Their testing family and uncertainty procedure must be fixed before confirmation. A logistic product coefficient is not automatically the risk-difference interaction. Report effects separately by versioned model rather than generalizing a small selected panel to all models.

## Inputs, units, and fair resource accounting

Use original synthetic tasks and records with explicit provenance and release rights. Confirm permitted model and service use before collection; do not redistribute restricted prompts, model weights, papers, private transcripts, or user memory. The first studies disable tools and writable memory. Any action extension requires isolated local mocks and explicit allowed state transitions.

Independent task/template origins define the sampling clusters. Near-duplicate items and repeated stochastic generations are nested observations, not new independent tasks. Keep whole origins out of the development split. Randomize conditions within task and collection-time blocks; begin primary trials in fresh contexts. For BF-04, entire conversation sequences are the units, not individual turns.

Before any execution, set finite global ceilings for request attempts, output, wall time and cost. **The shared request ceiling includes all phases, models, workers, retries, screening, auxiliary judges and recovery calls, including failed or uncertain calls.** A retry does not reset the budget. Use the same total per-case ceilings across compared systems and charge defense overhead inside them. Report actual resource use as well as the ceiling. No numerical cap or monetary budget is approved or frozen by this document.

## Denominators and incomplete evidence

- **Primary reliability endpoint:** bounded task non-success per initiated evaluation case. Count refusals, empty responses, truncations, timeouts, transport/API errors and exhausted recovery in that case denominator, with separate cause labels. Transport errors are not model disobedience.
- **Behavior diagnostic:** contract violations among returned responses retain refusal, empty and truncated-message flags. No-output transport failures have unobserved behavior. Report availability by condition and sensitivity bounds; this selected subset is not the full causal effect.
- **Calls versus cases:** retain every attempted call and its parent case ID. Retries increase attempts, not the number of independent cases. Preserve first-attempt and final bounded-policy outcomes separately.
- **Uninitiated work:** label scheduled but uninitiated cases NOT_ATTEMPTED. A budget stop produces an incomplete-cohort report, not selective replacement or an enlarged budget.
- **Repetition:** use separately specified grapheme and model-token metrics. Empty normalized coverage is undefined; a truncated score describes only the observed prefix. Valid repeated data are negative controls, and repetition alone is not failure or denial of service.
- **Usage:** unknown usage is not zero. Ratios with zero or missing baseline denominators are undefined. Report input and output usage separately because framing mechanically adds input tokens.

## Go/no-go gates and scientific decisions

**Go to a pilot** only after semantic review confirms invariant answers and contracts, deterministic scoring is validated, input/model rights are clear, session reset is controlled, and finite budgets are recorded. The first useful artifact is that reviewed design and scorer set. Passing scorer tests does not demonstrate a model effect.

**Go to confirmation** only after a separate pilot supports a justified cluster-aware power or precision plan. Freeze prompts, whole-origin holdouts, model settings, the primary contrast, multiplicity, missingness rules, useful-effect and equivalence margins, and limits before examining new evaluation outcomes. Pilot or previously observed evaluation items cannot become independent confirmation of tuned choices.

**Stop or redesign** for changed task semantics, unreliable scoring, unresolved rights, insufficient resources for informative inference, unexplained session state, changed model revision, or any action outside the declared mock-only boundary. For BF-02, stop if semantic and surface cues cannot be separated without changing the task or escalating cue repetition. For BF-03, refusing everything or hiding extra computation cannot establish a useful defense.

A positive contrast may indicate worse adherence; a negative contrast may indicate improved adherence. A nonsignificant result is **inconclusive** unless a prespecified equivalence analysis supports a practically negligible effect. No sample size or power has been established. Model-specific behavior does not identify an internal priority-reordering mechanism or establish a new attack category.

BF-03 must measure legitimate task completion, false rejection of permitted warmth, acceptance of authorized corrections, and total cost alongside violations. A filter can improve delivered output without changing the underlying model. BF-04 measures randomized-history **carryover**: an effect in a retained transcript does not imply weight change, a persistent backdoor or self-propagation. Any later toy-memory arm is limited to its inspectable local storage channel.

## What a team still needs to decide

Exact model identifiers; task/template counts and repetitions; reviewed prompt text; cue definitions; resource ceilings; scoring tolerances; cluster weighting; useful-effect and utility-loss margins; multiplicity; missingness limits; repetition implementation and thresholds; and the power/precision plan. These are intentionally unresolved. The machine-readable cards in [protocol.json](protocol.json) preserve the same boundaries for downstream readers.
