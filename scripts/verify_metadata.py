"""Validate citation exports with the pinned official CFF 1.2.0 schema.

The BibTeX and CSL checks validate this package's narrow export profile, not all
possible citation syntax. These checks do not validate scientific hypotheses.
No network access is required.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from jsonschema import Draft7Validator, FormatChecker
import yaml

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/AnimaFoundry/love-attack-review"
ARTICLE_TITLE = "Compassion and Legitimacy Framing in LLM Systems: Evidence, Threat Boundaries, and a Controlled Evaluation Protocol"
SOFTWARE_TITLE = "Compassion and Legitimacy Framing Review: Publication Software"
CITATION_KEY = "AnimaFoundry2026CompassionFraming"
SOFTWARE_VERSION = "1.3.0"
ARTICLE_VERSION = "1.0.0"
SOFTWARE_RELEASE_DATE = "2026-10-26"
ARTICLE_RELEASE_DATE = "2026-10-24"
SCHEMA_SHA256 = "17bc7993c67b95eec988dadca78b65cb29cd489d1fceba71040a141dfb9791df"
LICENSE_SHA256 = "d26e56663498f0f17dbcb8a9bd50d344828948be08265f4fc97b4fc612e9be71"
UPSTREAM_COMMIT = "dd51afe18fe23b4daaaf923d305e3046415b2c7c"
ARTICLE_URL = REPOSITORY + "/blob/v1.0.0/paper.md"
SOFTWARE_URL = REPOSITORY + "/releases/tag/v" + SOFTWARE_VERSION
ARTICLE_NOTE = (
    "Critical integrative review and prospective evaluation protocol; not peer reviewed. "
    "No original controlled model experiment, power analysis, or defense-effectiveness "
    "evaluation is reported. Article license: CC-BY-4.0."
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject duplicate fields instead of silently selecting the final value."""


def unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        require(isinstance(key, str), "CFF mapping keys must be strings")
        require(key not in mapping, "Duplicate CFF key: " + key)
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def load_cff(text):
    return yaml.load(text, Loader=UniqueKeyLoader)


def unique_json_mapping(pairs):
    mapping = {}
    for key, value in pairs:
        require(key not in mapping, "Duplicate JSON key: " + key)
        mapping[key] = value
    return mapping


def load_json(text):
    return json.loads(text, object_pairs_hook=unique_json_mapping)


def all_refs(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "$ref":
                yield child
            yield from all_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_refs(child)


def load_schema(root=ROOT):
    root = Path(root)
    schema_bytes = (root / "schemas/cff-1.2.0.schema.json").read_bytes()
    require(hashlib.sha256(schema_bytes).hexdigest() == SCHEMA_SHA256,
            "Pinned official CFF schema hash mismatch")
    license_bytes = (root / "schemas/CFF-LICENSE").read_bytes()
    require(hashlib.sha256(license_bytes).hexdigest() == LICENSE_SHA256,
            "Pinned upstream CFF license hash mismatch")
    provenance = (root / "schemas/CFF-SOURCE.md").read_text(encoding="utf-8")
    require(all(x in provenance for x in (UPSTREAM_COMMIT, SCHEMA_SHA256,
            LICENSE_SHA256, "CC-BY-4.0", "unmodified")),
            "Missing CFF upstream attribution or integrity metadata")
    schema = load_json(schema_bytes.decode("utf-8"))
    require(schema["$id"] == "https://citation-file-format.github.io/1.2.0/schema.json",
            "Unexpected CFF schema identity")
    require(all(ref.startswith("#/") for ref in all_refs(schema)),
            "CFF schema must remain self-contained for offline validation")
    Draft7Validator.check_schema(schema)
    return schema


def validate_cff(document, schema):
    Draft7Validator(schema, format_checker=FormatChecker()).validate(document)
    for key, expected in {
        "cff-version": "1.2.0", "type": "software", "title": SOFTWARE_TITLE,
        "authors": [{"name": "AnimaFoundry"}], "version": SOFTWARE_VERSION,
        "date-released": SOFTWARE_RELEASE_DATE, "url": SOFTWARE_URL,
        "repository-code": REPOSITORY, "license": "MIT",
    }.items():
        require(document.get(key) == expected, "Software citation mismatch: " + key)
    require("helper code" in document.get("abstract", "")
            and "CC-BY-4.0" in document.get("abstract", ""),
            "Missing software/article license boundary")
    article = document.get("preferred-citation", {})
    for key, expected in {
        "type": "article", "title": ARTICLE_TITLE,
        "authors": [{"name": "AnimaFoundry"}], "version": ARTICLE_VERSION,
        "year": 2026, "date-released": ARTICLE_RELEASE_DATE, "status": "preprint",
        "license": "CC-BY-4.0", "url": ARTICLE_URL, "notes": ARTICLE_NOTE,
    }.items():
        require(article.get(key) == expected, "Article citation mismatch: " + key)
    require(not any(k in document or k in article for k in ("doi", "journal", "issn")),
            "No DOI or journal publication has been assigned to this review")


def expected_csl():
    return [{
        "id": CITATION_KEY, "type": "article", "title": ARTICLE_TITLE,
        "author": [{"literal": "AnimaFoundry"}],
        "issued": {"date-parts": [[2026, 10, 24]]},
        "version": ARTICLE_VERSION, "status": "preprint",
        "genre": "Critical integrative review and prospective evaluation protocol",
        "URL": ARTICLE_URL, "language": "en", "note": ARTICLE_NOTE,
        "custom": {"license": "CC-BY-4.0", "peer_reviewed": False,
                   "original_controlled_model_experiments": False,
                   "power_analysis_performed": False,
                   "defense_effectiveness_evaluated": False,
                   "publication_software_version": SOFTWARE_VERSION,
                   "publication_software_date_released": SOFTWARE_RELEASE_DATE},
    }]


def validate_csl(document):
    require(document == expected_csl(),
            "CSL-JSON citation or evidence boundary mismatch")


def expected_bibtex():
    # Traditional BibTeX uses @misc for this preprint without a journal.
    # Inner braces protect the corporate author and title capitalization.
    fields = [
        ("author", "{AnimaFoundry}"), ("title", "{" + ARTICLE_TITLE + "}"),
        ("year", "2026"), ("month", "October"),
        ("howpublished", "Research preprint, version " + ARTICLE_VERSION),
        ("url", ARTICLE_URL), ("note", ARTICLE_NOTE),
    ]
    return "@misc{" + CITATION_KEY + ",\n" + ",\n".join(
        "  " + key + " = {" + value + "}" for key, value in fields) + "\n}\n"


def validate_bibtex(text):
    require(text.replace("\r\n", "\n") == expected_bibtex(),
            "BibTeX citation or evidence boundary mismatch")


def verify(root=ROOT):
    root = Path(root)
    schema = load_schema(root)
    validate_cff(load_cff((root / "CITATION.cff").read_text(encoding="utf-8")), schema)
    validate_csl(load_json((root / "citation.csl.json").read_text(encoding="utf-8")))
    validate_bibtex((root / "citation.bib").read_text(encoding="utf-8"))
    manuscript = (root / "manuscript.md").read_text(encoding="utf-8-sig")
    require(manuscript.splitlines()[0] == "# " + ARTICLE_TITLE,
            "Manuscript title disagrees with citation exports")
    require(re.search(r"version\s+1\.0\.0", manuscript[:900], re.IGNORECASE),
            "Manuscript must identify version 1.0.0 near its title")
    require("not peer reviewed" in manuscript[:900],
            "Manuscript must identify its preprint status near its title")
    return {"cff_schema": "1.2.0", "cff_schema_sha256": SCHEMA_SHA256,
            "software_version": SOFTWARE_VERSION, "article_version": ARTICLE_VERSION,
            "software_release_date": SOFTWARE_RELEASE_DATE,
            "article_release_date": ARTICLE_RELEASE_DATE,
            "article_status": "preprint", "citation_exports": 3,
            "scientific_claim_validation": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="Package directory; defaults to the script's parent package")
    args = parser.parse_args()
    print(json.dumps(verify(args.root), indent=2))
