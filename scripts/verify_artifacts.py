"""Offline integrity checks for the review/protocol publication artifacts.

These checks verify file consistency, traceable references and declared study
status. They do not evaluate a model, certify scientific claims, or check remote
URLs. The release manifest excludes itself and includes every public file.
Copyright (c) 2026 AnimaFoundry. See LICENSE-CODE.
"""

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import unicodedata
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "RELEASE_MANIFEST.json"
GENERATED = ("paper.md", "paper.pdf", "figures/framing_evaluation.svg")
REQUIRED_FILES = {
    "README.md", "manuscript.md", "references.json", "protocol.json",
    "EXPERIMENT_HANDOFF.md", "CITATION.cff", "citation.bib", "citation.csl.json",
    "LICENSE", "LICENSE-CODE", "LICENSE-TEXT", "SOURCE_AND_RIGHTS.md",
    "FONT-LICENSE.txt",
    "requirements.txt", "scripts/build_paper.py", "scripts/verify_metadata.py",
    "scripts/verify_artifacts.py", "tests/test_artifacts.py",
    ".github/workflows/validate.yml", *GENERATED,
}
IGNORED_DIRS = {"build", "__pycache__", ".pytest_cache", ".git", ".venv"}
PROTECTED_PARTS = {".auth", "input", "output", "exports", "quarantine"}
EXCLUDED_PUBLIC_FILES = {"case-observation.json"}
REF_PATTERN = re.compile(r"\[@([A-Z0-9]+)\]")
PLACEHOLDER_PATTERN = re.compile(r"CASE SECTION PLACEHOLDER|\b(?:TODO|TBD|FIXME)\b")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_mapping(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                      object_pairs_hook=unique_mapping)


def text_file(path):
    return Path(path).read_text(encoding="utf-8-sig")


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def web_url(value):
    if not isinstance(value, str) or any(char.isspace() for char in value):
        return False
    parsed = urlsplit(value)
    return (parsed.scheme == "https" and bool(parsed.netloc)
            and parsed.username is None and parsed.password is None)


def safe_path(root, relative):
    """Reject escapes and symlink traversal before reading a manifest entry."""
    require(nonempty(relative) and "\\" not in relative,
            "Artifact paths must be nonempty repository-relative POSIX paths")
    path = PurePosixPath(relative)
    require(not path.is_absolute() and str(path) == relative
            and not any(part in {".", ".."} or ":" in part for part in path.parts),
            "Unsafe artifact path: " + relative)
    require(path.name.lower() not in EXCLUDED_PUBLIC_FILES,
            "Excluded private-case artifact: " + relative)
    require(not any(part.lower() in PROTECTED_PARTS | IGNORED_DIRS for part in path.parts),
            "Protected or transient artifact path: " + relative)
    result = Path(root)
    for part in path.parts:
        result = result / part
        require(not result.is_symlink(), "Symlink artifact is not allowed: " + relative)
    return result


def public_inventory(root):
    """Inspect only this package; never descend into protected/transient trees."""
    root = Path(root)
    found = set()
    pending = [root]
    while pending:
        directory = pending.pop()
        for path in directory.iterdir():
            relative = path.relative_to(root).as_posix()
            if path.name in IGNORED_DIRS:
                continue
            require(path.name.lower() not in EXCLUDED_PUBLIC_FILES,
                    "Excluded private-case artifact in publication package: " + relative)
            require(path.name.lower() not in PROTECTED_PARTS,
                    "Protected path found in publication package: " + relative)
            require(not path.is_symlink(), "Symlink found in publication package: " + relative)
            if path.is_dir():
                pending.append(path)
            elif path.is_file() and relative != MANIFEST:
                found.add(relative)
    return found


def validate_manifest(root, manifest):
    require(isinstance(manifest, dict), "Manifest must be an object")
    require(manifest.get("version") == "1.0.0", "Unexpected publication version")
    require(manifest.get("self_excluded") is True, "Manifest must explicitly exclude itself")
    require(nonempty(manifest.get("scope")), "Manifest requires a truthful scope description")
    records = manifest.get("files")
    require(isinstance(records, list) and records, "Manifest files must be a nonempty list")
    paths = set()
    for record in records:
        require(isinstance(record, dict), "Manifest file record must be an object")
        relative = record.get("path")
        path = safe_path(root, relative)
        require(relative != MANIFEST and relative not in paths,
                "Duplicate or self-referential manifest entry: " + relative)
        paths.add(relative)
        size, digest = record.get("bytes"), record.get("sha256")
        require(type(size) is int and size >= 0, "Invalid file size: " + relative)
        require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest),
                "Invalid SHA-256: " + relative)
        require(path.is_file(), "Missing manifest file: " + relative)
        data = path.read_bytes()
        require(len(data) == size, "Byte count mismatch: " + relative)
        require(hashlib.sha256(data).hexdigest() == digest, "SHA-256 mismatch: " + relative)
    require(REQUIRED_FILES <= paths,
            "Required files absent from manifest: " + ", ".join(sorted(REQUIRED_FILES - paths)))
    inventory = public_inventory(root)
    require(paths == inventory,
            "Publication inventory differs from manifest; unlisted="
            + repr(sorted(inventory - paths)) + "; absent=" + repr(sorted(paths - inventory)))
    return len(paths)


def validate_references(records, manuscript):
    require(isinstance(records, list) and records, "References must be a nonempty list")
    ids = []
    for record in records:
        require(isinstance(record, dict), "Reference must be an object")
        key = record.get("id")
        require(isinstance(key, str) and re.fullmatch(r"[A-Z0-9]+", key),
                "Invalid reference ID")
        require(key not in ids, "Duplicate reference ID: " + key)
        ids.append(key)
        for field in ("authors", "title", "publication", "evidence_type", "reading_scope",
                      "supportable_claim", "limitation"):
            require(nonempty(record.get(field)), "Missing reference " + field + ": " + key)
        require(type(record.get("year")) is int and record["year"] > 0,
                "Invalid publication year: " + key)
        for field in ("url", "verified_at"):
            require(web_url(record.get(field)), "Invalid reference " + field + ": " + key)
        try:
            accessed = date.fromisoformat(record.get("accessed", ""))
        except (TypeError, ValueError) as error:
            raise ValueError("Invalid access date: " + key) from error
        require(record["year"] <= accessed.year, "Reference year follows access date: " + key)
        doi = record.get("doi")
        require(doi is None or (isinstance(doi, str)
                and re.fullmatch(r"10\.\d{4,9}/\S+", doi)), "Invalid DOI syntax: " + key)
    citations = list(dict.fromkeys(REF_PATTERN.findall(manuscript)))
    require(set(citations) == set(ids),
            "Reference/citation mismatch; unknown=" + repr(sorted(set(citations) - set(ids)))
            + "; uncited=" + repr(sorted(set(ids) - set(citations))))
    require("[@" not in REF_PATTERN.sub("", manuscript), "Malformed unresolved citation")
    return citations


def validate_protocol(document):
    require(isinstance(document, dict), "Protocol must be an object")
    require(document.get("schema_version") == "1.0", "Unsupported protocol schema")
    require(document.get("status") == "NOT_PERFORMED", "Protocol must remain prospective")
    require(document.get("preregistered") is False, "No completed preregistration is claimed")
    require(document.get("prompts_frozen") is False, "Prompts are not frozen")
    require(document.get("sample_size") is None, "No sample size has been established")
    require(document.get("power_analysis_status") == "NOT_PERFORMED",
            "Power analysis has not been performed")
    require(nonempty(document.get("evidence_boundary")), "Protocol needs an evidence boundary")
    rules = document.get("global_rules")
    require(isinstance(rules, dict), "Missing global protocol rules")
    for field in ("inputs_and_rights", "execution_boundary", "sampling_and_inference",
                  "release_interpretation"):
        require(isinstance(rules.get(field), list) and rules[field]
                and all(nonempty(item) for item in rules[field]), "Missing protocol rule: " + field)
    resources = rules.get("resource_controls", {})
    require(isinstance(resources, dict) and resources.get("caps_frozen") is False,
            "Resource caps have not been frozen")
    for field in ("global_attempt_cap", "output_token_cap", "wall_time_cap", "monetary_budget"):
        require(field in resources and resources[field] is None,
                "Unresolved resource field must be null: " + field)
    for field in ("accounting_rule", "comparability_rule", "exhaustion_rule"):
        require(nonempty(resources.get(field)), "Missing resource rule: " + field)
    outcomes = rules.get("outcome_accounting", {})
    for field in ("primary_endpoint", "case_denominator", "attempt_denominator",
                  "behavior_diagnostic", "first_attempt_and_recovery", "truncation_and_empty",
                  "usage", "ledger"):
        require(nonempty(outcomes.get(field)), "Missing outcome-accounting rule: " + field)
    experiments = document.get("experiments")
    require(isinstance(experiments, list) and experiments, "Protocol needs experiment cards")
    ids = set()
    for experiment in experiments:
        require(isinstance(experiment, dict), "Experiment must be an object")
        key = experiment.get("id")
        require(nonempty(key) and key not in ids, "Missing or duplicate experiment ID")
        ids.add(key)
        require(experiment.get("status") == "NOT_PERFORMED",
                "Experiment status is not prospective: " + key)
        for field in ("title", "question", "rights", "resource_controls", "independent_units",
                      "interpretation"):
            require(nonempty(experiment.get(field)), "Missing experiment " + field + ": " + key)
        for field in ("inputs", "baselines", "unresolved"):
            require(isinstance(experiment.get(field), list) and experiment[field]
                    and all(nonempty(item) for item in experiment[field]),
                    "Missing experiment " + field + ": " + key)
        outcome = experiment.get("outcomes", {})
        require(isinstance(outcome, dict) and nonempty(outcome.get("primary")),
                "Missing primary outcome: " + key)
        for field in ("secondary", "negative_controls"):
            require(isinstance(outcome.get(field), list) and outcome[field]
                    and all(nonempty(item) for item in outcome[field]),
                    "Missing outcome " + field + ": " + key)
        gate = experiment.get("go_no_go", {})
        require(isinstance(gate, dict) and all(nonempty(gate.get(field)) for field in
                ("go_to_pilot", "go_to_confirmation", "no_go")), "Missing go/no-go rules: " + key)
    require(ids == {"BF-01", "BF-02", "BF-03", "BF-04"},
            "Expected semantic, symbol-cue, defense and history cards")
    return len(ids)


def numbered_markdown(manuscript, references, citation_order):
    numbers = {key: index + 1 for index, key in enumerate(citation_order)}
    records = {record["id"]: record for record in references}
    body = REF_PATTERN.sub(lambda match: f"[{numbers[match.group(1)]}]", manuscript)
    entries = []
    for key in citation_order:
        record = records[key]
        entry = (f"[{numbers[key]}] {record['authors']}. {record['title']}. "
                 f"{record['publication']}, {record['year']}.")
        if record.get("doi"):
            entry += f" DOI: https://doi.org/{record['doi']}."
        entries.append(entry + " " + record["url"])
    return body + "\n## References\n\n" + "\n\n".join(entries) + "\n"


def plain_inline(text):
    text = re.sub(r"\[([^\]]+)\]\((?:https?://[^\s)]+)\)", r"\1", text)
    return text.replace("**", "").replace("*", "").replace("`", "")


def compact(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", text))


def strip_running_footer(text):
    # ReportLab emits the on-page footer before body text. Remove only the
    # identified footer and its adjacent page number, never arbitrary numbers.
    return re.sub(r"(?m)^AnimaFoundry \| Review and protocol v\S+ \| Not peer reviewed"
                  r"[ \t]*\r?\n\d+[ \t]*\r?\n", "", text)


def source_pieces(markdown):
    """Yield content units for PDF coverage, independently of PDF layout."""
    block = []
    code = False
    for line in markdown.splitlines() + [""]:
        if line.startswith("```"):
            if block:
                yield " ".join(block)
                block = []
            code = not code
            continue
        if code:
            if line.strip():
                yield line
            continue
        if not line.strip() or line.startswith(("#", "|", "![")):
            if block:
                yield plain_inline(" ".join(block))
                block = []
            if line.startswith("#"):
                yield plain_inline(re.sub(r"^#+\s+", "", line))
            elif line.startswith("|"):
                for cell in line.strip().strip("|").split("|"):
                    if cell.strip() and not re.fullmatch(r":?-+:?", cell.strip()):
                        yield plain_inline(cell.strip())
            continue
        block.append(line.strip())
    require(not code, "Unclosed Markdown code fence")


def validate_pdf(path, title, markdown):
    from pypdf import PdfReader

    reader = PdfReader(path)
    require(not reader.is_encrypted and bool(reader.pages), "PDF must be readable and nonempty")
    require(reader.metadata and reader.metadata.title == title, "PDF title metadata mismatch")
    require(reader.metadata.author == "AnimaFoundry", "PDF author metadata mismatch")
    pages = [page.extract_text() or "" for page in reader.pages]
    require(all(page.strip() for page in pages), "PDF contains a text-empty page")
    extracted = "\n".join(pages)
    require(not PLACEHOLDER_PATTERN.search(extracted), "PDF contains an unfinished placeholder")
    require("[@" not in extracted and "\ufffd" not in extracted,
            "PDF contains unresolved citations or replacement characters")
    pdf_text = compact("\n".join(strip_running_footer(page) for page in pages))
    for piece in source_pieces(markdown):
        require(compact(piece) in pdf_text, "Content missing from PDF: " + piece[:120])
    return len(pages)


def validate_svg(path):
    text = text_file(path)
    require("<!DOCTYPE" not in text.upper() and "<!ENTITY" not in text.upper(),
            "External declarations are not allowed in the original SVG")
    tree = ET.fromstring(text)
    require(tree.tag == "{http://www.w3.org/2000/svg}svg", "Figure is not an SVG")
    tags = {node.tag.split("}")[-1] for node in tree.iter()}
    require({"title", "desc"} <= tags, "SVG needs accessible title and description")
    require(not tags.intersection({"script", "foreignObject", "image"}),
            "Unexpected executable or external SVG content")
    for node in tree.iter():
        for name, value in node.attrib.items():
            require(not name.lower().startswith("on"), "SVG event handler is not allowed")
            if name.split("}")[-1] == "href":
                require(value.startswith("#"), "External SVG references are not allowed")


def compare_rebuild(root, rebuild):
    root, rebuild = Path(root).resolve(), Path(rebuild).resolve()
    require(root != rebuild, "Rebuild must use a separate destination")
    require(rebuild.is_dir(), "Rebuild directory does not exist")
    found = {path.relative_to(rebuild).as_posix() for path in rebuild.rglob("*") if path.is_file()}
    require(found == set(GENERATED), "Unexpected or missing files in rebuild output")
    for relative in GENERATED:
        candidate = safe_path(rebuild, relative)
        require(candidate.is_file(), "Missing rebuilt artifact: " + relative)
        require((root / relative).read_bytes() == candidate.read_bytes(),
                "Rebuild differs from committed artifact: " + relative)


def verify(root=ROOT, rebuild=None):
    root = Path(root)
    count = validate_manifest(root, load_json(root / MANIFEST))
    source = text_file(root / "manuscript.md")
    require(source.startswith("# "), "Manuscript needs a title")
    require(not PLACEHOLDER_PATTERN.search(source), "Manuscript contains an unfinished placeholder")
    require("not peer reviewed" in source[:900], "Preprint status missing near title")
    title = source.splitlines()[0][2:]
    citation = load_json(root / "citation.csl.json")
    require(isinstance(citation, list) and len(citation) == 1
            and citation[0].get("title") == title, "Article title disagrees with CSL export")
    refs = load_json(root / "references.json")
    order = validate_references(refs, source)
    experiments = validate_protocol(load_json(root / "protocol.json"))
    handoff = text_file(root / "EXPERIMENT_HANDOFF.md")
    require("NOT PERFORMED" in handoff and all(key in handoff for key in
            ("BF-01", "BF-02", "BF-03", "BF-04")), "Handoff lacks prospective study cards")
    require(not PLACEHOLDER_PATTERN.search(handoff), "Handoff contains an unfinished placeholder")
    paper = text_file(root / "paper.md")
    require(paper == numbered_markdown(source, refs, order),
            "Generated Markdown does not preserve source and ordered references")
    require("figures/framing_evaluation.svg" in source, "Original schematic is not cited in manuscript")
    validate_svg(root / GENERATED[2])
    pages = validate_pdf(root / "paper.pdf", title, paper)
    if rebuild is not None:
        compare_rebuild(root, rebuild)
    return {"manifest_files": count, "references": len(refs), "pdf_pages": pages,
            "prospective_studies": experiments, "model_experiments_performed": False,
            "rebuild_byte_identical": rebuild is not None,
            "remote_urls_checked": False, "scientific_claim_validation": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--rebuild", "--rebuild-dir", dest="rebuild", type=Path,
                        help="Separately rebuilt output to compare byte for byte")
    args = parser.parse_args()
    print(json.dumps(verify(args.root, args.rebuild), indent=2))
