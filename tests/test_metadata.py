"""Regression controls for citation format, duplicated fields, and claim boundaries."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "love_package_metadata_verifier", ROOT / "scripts/verify_metadata.py")
metadata = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metadata)


class CitationMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = metadata.load_schema(ROOT)
        cls.cff = metadata.load_cff((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
        cls.csl = metadata.load_json((ROOT / "citation.csl.json").read_text(encoding="utf-8"))

    def test_real_exports_and_official_schema_pass(self):
        result = metadata.verify(ROOT)
        self.assertEqual(result["article_version"], "1.0.0")
        self.assertEqual(result["software_version"], "1.3.0")
        self.assertEqual(result["software_release_date"], "2026-10-26")
        self.assertEqual(result["article_release_date"], "2026-10-24")
        self.assertFalse(result["scientific_claim_validation"])

    def test_article_rejected_at_cff_root_by_official_schema(self):
        invalid = deepcopy(self.cff)
        invalid["type"] = "article"
        with self.assertRaises(ValidationError):
            metadata.validate_cff(invalid, self.schema)

    def test_article_allowed_under_preferred_citation(self):
        self.assertEqual(self.cff["preferred-citation"]["type"], "article")
        metadata.validate_cff(self.cff, self.schema)

    def test_software_update_does_not_relabel_article_date_or_cff_schema(self):
        self.assertEqual(self.cff["cff-version"], "1.2.0")
        self.assertEqual(self.cff["date-released"], "2026-10-26")
        self.assertEqual(self.cff["preferred-citation"]["date-released"], "2026-10-24")
        invalid = deepcopy(self.cff)
        invalid["preferred-citation"]["date-released"] = self.cff["date-released"]
        with self.assertRaisesRegex(ValueError, "Article citation mismatch: date-released"):
            metadata.validate_cff(invalid, self.schema)

    def test_stale_software_date_or_version_is_rejected(self):
        for key, value in (("date-released", "2026-10-24"), ("version", "1.2.0")):
            with self.subTest(key=key):
                invalid = deepcopy(self.cff)
                invalid[key] = value
                with self.assertRaisesRegex(ValueError, "Software citation mismatch: " + key):
                    metadata.validate_cff(invalid, self.schema)

    def test_article_metadata_mismatch_rejected(self):
        for key, value in (("version", "1.2.0"), ("title", "Another title"),
                           ("date-released", "2026-10-16"),
                           ("url", "https://example.com/unrelated")):
            with self.subTest(key=key):
                invalid = deepcopy(self.cff)
                invalid["preferred-citation"][key] = value
                with self.assertRaisesRegex(ValueError, "Article citation mismatch: " + key):
                    metadata.validate_cff(invalid, self.schema)

    def test_missing_preprint_status_or_scope_is_rejected(self):
        for key in ("status", "notes", "license"):
            with self.subTest(key=key):
                invalid = deepcopy(self.cff)
                del invalid["preferred-citation"][key]
                with self.assertRaisesRegex(ValueError, "Article citation mismatch"):
                    metadata.validate_cff(invalid, self.schema)

    def test_article_and_code_licenses_cannot_be_swapped(self):
        invalid = deepcopy(self.cff)
        invalid["license"] = "CC-BY-4.0"
        with self.assertRaisesRegex(ValueError, "Software citation mismatch: license"):
            metadata.validate_cff(invalid, self.schema)

    def test_duplicate_yaml_fields_rejected_at_both_levels(self):
        for text in ("version: '1.0.0'\nversion: '9.0.0'\n",
                     "preferred-citation:\n  version: '1.0.0'\n  version: '9.0.0'\n"):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, "Duplicate CFF key: version"):
                    metadata.load_cff(text)

    def test_duplicate_json_fields_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key: status"):
            metadata.load_json('[{"status":"preprint","status":"published"}]')

    def test_csl_author_version_and_experiment_boundary_required(self):
        for key, value in (("author", [{"family": "AnimaFoundry"}]),
                           ("version", "1.2.0"), ("status", "published"),
                           ("custom", {})):
            with self.subTest(key=key):
                invalid = deepcopy(self.csl)
                invalid[0][key] = value
                with self.assertRaises(ValueError):
                    metadata.validate_csl(invalid)

    def test_bibtex_mismatch_rejected(self):
        valid = (ROOT / "citation.bib").read_text(encoding="utf-8")
        metadata.validate_bibtex(valid)
        for invalid in (valid.replace("version 1.0.0", "version 1.2.0"),
                        valid.replace("not peer reviewed", "peer reviewed"),
                        valid.replace("AnimaFoundry}}", "Someone Else}}")):
            with self.assertRaises(ValueError):
                metadata.validate_bibtex(invalid)

    def test_invented_publication_identifier_rejected(self):
        invalid = deepcopy(self.cff)
        invalid["preferred-citation"]["doi"] = "10.1234/example"
        with self.assertRaisesRegex(ValueError, "No DOI or journal"):
            metadata.validate_cff(invalid, self.schema)

    def test_modified_schema_rejected_before_validation(self):
        with patch.object(Path, "read_bytes", return_value=b"{}"):
            with self.assertRaisesRegex(ValueError, "schema hash mismatch"):
                metadata.load_schema(ROOT)


if __name__ == "__main__":
    unittest.main()
