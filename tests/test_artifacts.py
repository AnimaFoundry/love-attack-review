"""Focused regressions for publication integrity, not model behavior."""

import copy
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_artifacts", ROOT / "scripts/verify_artifacts.py")
artifacts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(artifacts)


@contextmanager
def temporary_workspace():
    # Some managed Windows sessions cannot write into the OS temporary folder.
    base = ROOT / "build" / "test-artifacts"
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base, prefix="case-") as directory:
        assert Path(directory).resolve().is_relative_to(base.resolve())
        yield directory


class ReferenceValidationTests(unittest.TestCase):
    def setUp(self):
        self.record = {"id": "SOURCE2024", "authors": "A. Researcher", "title": "A study",
                       "publication": "Example journal", "year": 2024,
                       "url": "https://example.org/study", "verified_at": "https://example.org/study",
                       "doi": None, "accessed": "2026-10-24", "evidence_type": "primary study",
                       "reading_scope": "Full text", "supportable_claim": "A bounded observation",
                       "limitation": "No generalization beyond tested settings"}

    def test_valid_reference_order_deduplicates_occurrences(self):
        self.assertEqual(artifacts.validate_references([self.record],
                         "A [@SOURCE2024]. B [@SOURCE2024]."), ["SOURCE2024"])

    def test_unknown_or_uncited_reference_rejected(self):
        for source in ("[@UNKNOWN]", "No citation"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                artifacts.validate_references([self.record], source)

    def test_duplicate_reference_or_missing_boundary_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate reference"):
            artifacts.validate_references([self.record, self.record], "[@SOURCE2024]")
        broken = dict(self.record, limitation="")
        with self.assertRaisesRegex(ValueError, "limitation"):
            artifacts.validate_references([broken], "[@SOURCE2024]")

    def test_malformed_citation_rejected(self):
        with self.assertRaisesRegex(ValueError, "Malformed"):
            artifacts.validate_references([self.record], "[@SOURCE2024] and [@source2024]")

    def test_credentials_in_reference_url_rejected(self):
        broken = dict(self.record, url="https://user:password@example.org/study")
        with self.assertRaisesRegex(ValueError, "url"):
            artifacts.validate_references([broken], "[@SOURCE2024]")


class ProtocolValidationTests(unittest.TestCase):
    def setUp(self):
        self.protocol = artifacts.load_json(ROOT / "protocol.json")

    def test_current_protocol_is_prospective(self):
        self.assertEqual(artifacts.validate_protocol(self.protocol), 4)

    def test_false_empirical_or_preregistration_claim_rejected(self):
        for key, value in (("status", "COMPLETE"), ("preregistered", True),
                           ("sample_size", 24000), ("power_analysis_status", "COMPLETE")):
            document = copy.deepcopy(self.protocol)
            document[key] = value
            with self.subTest(field=key), self.assertRaises(ValueError):
                artifacts.validate_protocol(document)

    def test_missing_denominator_or_silent_frozen_cap_rejected(self):
        document = copy.deepcopy(self.protocol)
        del document["global_rules"]["outcome_accounting"]["case_denominator"]
        with self.assertRaisesRegex(ValueError, "case_denominator"):
            artifacts.validate_protocol(document)
        document = copy.deepcopy(self.protocol)
        document["global_rules"]["resource_controls"]["global_attempt_cap"] = 25000
        with self.assertRaisesRegex(ValueError, "global_attempt_cap"):
            artifacts.validate_protocol(document)

    def test_missing_control_card_or_finished_experiment_rejected(self):
        document = copy.deepcopy(self.protocol)
        document["experiments"].pop(1)
        with self.assertRaisesRegex(ValueError, "symbol-cue"):
            artifacts.validate_protocol(document)
        document = copy.deepcopy(self.protocol)
        document["experiments"][0]["status"] = "COMPLETE"
        with self.assertRaisesRegex(ValueError, "prospective"):
            artifacts.validate_protocol(document)


class FilesystemIntegrityTests(unittest.TestCase):
    def test_paths_cannot_escape_or_read_protected_trees(self):
        with temporary_workspace() as directory:
            for path in ("../outside", "/absolute", "C:/outside", "a\\b", "./file",
                         "a/../file", "build/result.json", ".auth/token", "output/log"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    artifacts.safe_path(directory, path)
            self.assertEqual(artifacts.safe_path(directory, "paper.md"), Path(directory) / "paper.md")

    def test_duplicate_json_keys_are_not_silently_overwritten(self):
        with temporary_workspace() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text('{"status":"NOT_PERFORMED","status":"COMPLETE"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                artifacts.load_json(path)

    def test_private_case_artifact_cannot_enter_manifest(self):
        with temporary_workspace() as directory:
            manifest = {"version": "1.2.0", "scope": "Review and protocol", "self_excluded": True,
                        "files": [{"path": "case-observation.json", "bytes": 0,
                                   "sha256": hashlib.sha256(b"").hexdigest()}]}
            with self.assertRaisesRegex(ValueError, "Excluded private-case"):
                artifacts.validate_manifest(directory, manifest)
            for path in ("case-observation.json", "notes/case-observation.json"):
                with self.subTest(path=path), self.assertRaisesRegex(ValueError, "Excluded private-case"):
                    artifacts.safe_path(directory, path)

    def test_manifest_detects_hash_drift_and_unlisted_files(self):
        with temporary_workspace() as directory:
            root = Path(directory)
            (root / "paper.md").write_bytes(b"original\n")
            data = (root / "paper.md").read_bytes()
            manifest = {"version": "1.2.0", "scope": "Test fixture", "self_excluded": True,
                        "files": [{"path": "paper.md", "bytes": len(data),
                                   "sha256": hashlib.sha256(data).hexdigest()}]}
            with patch.object(artifacts, "REQUIRED_FILES", {"paper.md"}):
                self.assertEqual(artifacts.validate_manifest(root, manifest), 1)
                (root / "extra.txt").write_text("not allowlisted", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "inventory"):
                    artifacts.validate_manifest(root, manifest)
                (root / "extra.txt").unlink()
                (root / "paper.md").write_bytes(b"modified\n")
                with self.assertRaisesRegex(ValueError, "mismatch"):
                    artifacts.validate_manifest(root, manifest)

    def test_rebuild_detects_mismatch_and_extra_artifact(self):
        with temporary_workspace() as directory:
            root, rebuild = Path(directory) / "root", Path(directory) / "rebuild"
            for base in (root, rebuild):
                for relative in artifacts.GENERATED:
                    path = base / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(relative.encode("ascii"))
            artifacts.compare_rebuild(root, rebuild)
            (rebuild / "paper.pdf").write_bytes(b"different")
            with self.assertRaisesRegex(ValueError, "differs"):
                artifacts.compare_rebuild(root, rebuild)
            (rebuild / "paper.pdf").write_bytes(b"paper.pdf")
            (rebuild / "extra.txt").write_text("unexpected", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unexpected"):
                artifacts.compare_rebuild(root, rebuild)


class RenderedContentTests(unittest.TestCase):
    def test_footer_stripping_preserves_body_numbers(self):
        source = "AnimaFoundry | Review and protocol v1.0.0 | Not peer reviewed\n2\nBody\n137\n"
        self.assertEqual(artifacts.strip_running_footer(source), "Body\n137\n")

    def test_content_coverage_handles_structure_without_losing_body(self):
        source = ("# Title\n\nA **bold** [link](https://example.org).\nWrapped text.\n\n"
                  "| Key | Value |\n|---|---|\n| x | 2 |\n\n"
                  "```\ny = x + 1\n```\n\n![Diagram](figures/a.svg)\n\nFigure 1. Caption.\n")
        self.assertEqual(list(artifacts.source_pieces(source)),
                         ["Title", "A bold link. Wrapped text.", "Key", "Value", "x", "2",
                          "y = x + 1", "Figure 1. Caption."])

    def test_unclosed_code_fence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unclosed"):
            list(artifacts.source_pieces("```\nunclosed"))

    def test_svg_requires_accessibility_and_no_external_content(self):
        with temporary_workspace() as directory:
            path = Path(directory) / "figure.svg"
            prefix = '<svg xmlns="http://www.w3.org/2000/svg"><title>Title</title><desc>Plan</desc>'
            path.write_text(prefix + '<rect width="1" height="1"/></svg>', encoding="utf-8")
            artifacts.validate_svg(path)
            for content in ('<script>bad()</script>', '<image href="https://example.org/x"/>',
                            '<rect onclick="bad()"/>'):
                path.write_text(prefix + content + "</svg>", encoding="utf-8")
                with self.subTest(content=content), self.assertRaises(ValueError):
                    artifacts.validate_svg(path)


if __name__ == "__main__":
    unittest.main()
