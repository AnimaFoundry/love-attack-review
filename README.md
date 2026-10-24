# Compassion and Legitimacy Framing in LLM Systems

**Evidence, Threat Boundaries, and a Controlled Evaluation Protocol**  
AnimaFoundry · Version 1.0.0 · 24 October 2026

A selective critical integrative review and a prospective benign evaluation protocol. **Research preprint; not peer reviewed. No new controlled model experiment or validated defense is reported.**

The informal project label *The Love Attack* names the originating question. It is not a demonstrated new exploit or an established attack class.

## Read and cite

- [Read the paper in Markdown](paper.md) or [download the PDF](paper.pdf).
- [Citation File Format](CITATION.cff), [BibTeX](citation.bib), and [CSL-JSON](citation.csl.json).
- [Source ledger and claim limitations](references.json).
- [Versioned releases](https://github.com/AnimaFoundry/love-attack-review/releases).

Suggested citation: AnimaFoundry. (2026). *Compassion and Legitimacy Framing in LLM Systems: Evidence, Threat Boundaries, and a Controlled Evaluation Protocol* (Version 1.0.0) [Preprint]. https://github.com/AnimaFoundry/love-attack-review

## What this paper contributes

It separates useful emotional adaptation, task-contract failure, evaluator manipulation, unauthorized actions, repeated output, and service-level disruption. Existing findings about these outcomes have different tasks and denominators and cannot be combined into a single attack success rate.


## Research opportunities and handoff

| Card | Question | Status |
|---|---|---|
| BF-01 | Can semantic compassion and legitimacy framing change adherence while task and authority remain fixed? | NOT_PERFORMED |
| BF-02 | Can a short repeated-symbol cue explain repetition independently of semantic framing? | NOT_PERFORMED |
| BF-03 | Can defenses retain legitimate utility under an equal total resource ceiling? | NOT_PERFORMED |
| BF-04 | Does an effect depend on retained context or an explicit toy-memory channel? | NOT_PERFORMED |

Start with [EXPERIMENT_HANDOFF.md](EXPERIMENT_HANDOFF.md) and the machine-readable [protocol.json](protocol.json). Model versions, stimuli, sample size, power/precision plan, and finite budgets remain unfrozen. No inference runner, attack prompts, propagation mechanism, or service-load experiment is supplied. The first useful next step is a reviewed matched-item set and bounded feasibility plan; a negative or inconclusive result is an acceptable research outcome.

## Rebuild the publication package

Use Python 3.12 from the repository root:

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/verify_metadata.py
python scripts/build_paper.py --output-dir build/reproduced
python scripts/verify_artifacts.py --rebuild-dir build/reproduced
```

Document rebuilding and metadata tests validate publication artifacts only. They do not reproduce the cited studies or validate the proposed framing hypothesis. The release manifest lists exact public files and SHA-256 digests. It excludes itself to avoid a recursive hash definition.

## Evidence and reuse boundaries

Original prose, schematic, and protocol: [CC BY 4.0](LICENSE-TEXT). Publication scripts, tests, and workflows: [MIT](LICENSE-CODE). The third-party CFF schema carries its own license and provenance under `schemas/`. See [SOURCE_AND_RIGHTS.md](SOURCE_AND_RIGHTS.md).

This package does not redistribute third-party papers, benchmark prompts, model weights, or private conversations. Citation is not permission to copy those materials. No patent clearance, novelty, peer-review status, or empirical defense guarantee is claimed.

The paper and structured companion files can be read directly without executing code. We make no claim that search engines or agents have indexed, crawled, trained on, or endorsed them. Please file a reproducible correction through this repository's Issues, omitting credentials and private transcripts.
