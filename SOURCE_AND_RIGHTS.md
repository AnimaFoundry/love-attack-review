# Source and rights ledger

Companion package 1.1.0 · Manuscript 1.0.0 · 24 October 2026

| Material | Origin | License / publication boundary |
|---|---|---|
| Original manuscript, rendered paper, schematic, README, handoff, and protocol | Newly prepared for AnimaFoundry with AI authoring assistance | CC BY 4.0; complete terms in LICENSE-TEXT |
| Publication scripts, tests and workflow | New work and adaptations of AnimaFoundry's MIT publication helpers in crossmodal-intelligence-review v1.0.0 | MIT; complete terms in LICENSE-CODE |
| BF-01 synthetic task facts, wording, framing, design, plan and report | Newly authored for this project; no copied benchmark or private case | Original text/data under CC BY 4.0; complete terms in LICENSE-TEXT |
| BF-01 preparation, local runner, scorer, analysis and tests | Newly written for this bounded feasibility pilot | MIT; complete terms in LICENSE-CODE |
| Retained BF-01 responses and machine records | Locally generated responses to the original synthetic prompts; runtime metadata, attempt records and derived summaries | Published as research evidence with provenance; no claim of exclusive copyright in machine output, and no additional restriction on factual measurements |
| Model chat template, model metadata and full model license | Qwen2.5-1.5B-Instruct Q4_K_M distribution through Ollama; exact template and license hashes recorded in pilot/bf01/plan.json | Apache-2.0 notice retained in pilot/bf01/MODEL-LICENSE.txt; template retained in pilot/bf01/model-template.txt; model weights not redistributed |
| Citation metadata and original bibliographic annotations | Factual metadata checked against primary records; annotations newly written | Original expression CC BY 4.0; cited works retain their rights |
| CFF 1.2.0 JSON schema | citation-file-format upstream, pinned source and hashes in schemas/CFF-SOURCE.md | Upstream CC BY 4.0 license retained as schemas/CFF-LICENSE |
| Cited research and official guidance | Linked in references.json | Not bundled; no third-party figures, full text, benchmark prompts or weights copied |

The original user outline supplied research motivation. Its roleplay language, unsupported causal assertions, and operational speculation are not adopted as scientific findings. Section 9 states the originating hypothesis in neutral academic language.

## Build dependencies

The pinned packages are installed separately: ReportLab 4.4.9 (BSD), pypdf 6.10.0 (BSD-3-Clause), PyYAML 6.0.2 (MIT), and jsonschema 4.26.0 (MIT). Their package sources and transitive dependencies retain their own terms. The PDF embeds Bitstream Vera fonts shipped with ReportLab; their redistribution notice is retained in `FONT-LICENSE.txt`. No weights, inference service, or third-party dataset is required to build the paper. GitHub Actions use pinned official checkout and setup-python revisions.

## BF-01 model provenance and reuse

The local pilot plan identifies `qwen2.5:1.5b-instruct-q4_K_M`, an approximately 1 GB quantized model (986,061,892 bytes). The distribution record is the [Ollama model entry](https://ollama.com/library/qwen2.5:1.5b-instruct-q4_K_M); the upstream model is [Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct), with the [upstream Apache-2.0 license](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct/blob/main/LICENSE). The checked local digest and template/license hashes, rather than a movable tag alone, define the pilot configuration. The complete retained license notice accompanies the copied model template. The local Ollama executable and weights are installed separately and are not part of this release.

The runner follows the documented [Ollama chat API](https://docs.ollama.com/api/chat) and records template/runtime metadata in accordance with the [Modelfile documentation](https://docs.ollama.com/modelfile). These links identify implementation sources; they do not imply endorsement by the model or runtime maintainers.

The 13-file pre-inference freeze covers the synthetic task set, design, schedule generator, schedule, scorer, scorer tests, runner, analyzer, plan, model license, model template, runner tests and pre-run review. Raw response envelopes, attempt records, completion metadata and summaries are separate evidence artifacts. The final release manifest binds the actual included files and hashes. No downloaded model archive or weight file is included.

Only original synthetic inputs are used. No individual conversation case, screenshot, private transcript, external customer record or third-party benchmark is included. Model output is preserved as output, not attributed to a human participant or promoted to independently verified truth. The package's CC BY 4.0 license covers the project's original text and data compilation; it does not relicense the model or assert rights over any third-party material a model might produce. Reuse must retain applicable notices and source attribution. Actual observations and exclusions belong to [the pilot report](pilot/bf01/REPORT.md).

## Scope of legal and evidence statements

This is a literature-and-protocol package with a separately identified developmental feasibility companion, not a claim of an original attack invention or a clearance opinion. No file-specific source dispute has been identified in the materials included here. That is not an exhaustive patent search or a freedom-to-operate conclusion. Any future implementation or imported dataset needs a new feature- and artifact-specific review. An applicable license may provide specific grants under its own terms; it does not establish clearance against unrelated third-party patents.

AI assistants supported drafting, source inspection, original task authoring and internal review. Internal assistant agreement and automated tests do not constitute independent external human review, peer review or reproduction of the cited research. The v1.0.0 manuscript and prospective protocol remain unchanged. Pilot outcomes are reported separately and do not validate a general compassion-specific mechanism or defense. Publication rebuilding and offline Ubuntu evidence analysis are not a fresh model execution or a Linux replication of the pilot.
