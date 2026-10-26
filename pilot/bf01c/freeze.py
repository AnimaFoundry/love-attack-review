"""Explicit immutable file manifest for one BF-01C cohort. MIT license."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from envelope import strict_object


def _file(root: Path, name: str) -> Path:
    if type(name) is not str or not name or "\\" in name or ":" in name:
        raise ValueError("invalid_manifest_path")
    rel = Path(name)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in name.split("/")) or rel.as_posix() != name or name in {"FREEZE.json", "RUN_GUARD.json"} or rel.parts[0] == "run":
        raise ValueError("invalid_manifest_path")
    path = root / rel
    nodes = [root] + [root.joinpath(*rel.parts[:i]) for i in range(1, len(rel.parts) + 1)]
    if any(node.is_symlink() or getattr(node, "is_junction", lambda: False)() for node in nodes) or not path.is_file():
        raise ValueError("manifest_file_required")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("manifest_path_escaped_root")
    return path


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_freeze(root: Path, files: list[str]) -> dict:
    root = Path(root)
    if not files or len(set(files)) != len(files):
        raise ValueError("unique_explicit_files_required")
    records = [{"path": name, "sha256": _hash(_file(root, name)),
                "bytes": _file(root, name).stat().st_size} for name in sorted(files)]
    manifest = {"study_id": "BF01C", "created_utc": datetime.now(timezone.utc).isoformat(),
                "files": records}
    with (root / "FREEZE.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, indent=2, ensure_ascii=True)
        stream.write("\n")
    return verify_freeze(root)


def verify_freeze(root: Path) -> dict:
    root = Path(root)
    manifest = strict_object((root / "FREEZE.json").read_bytes())
    if manifest.get("study_id") != "BF01C" or type(manifest.get("files")) is not list or not manifest["files"]:
        raise ValueError("invalid_freeze")
    seen = set()
    for row in manifest["files"]:
        if type(row) is not dict or set(row) != {"path", "sha256", "bytes"} or type(row["path"]) is not str or row["path"] in seen:
            raise ValueError("invalid_freeze_record")
        if type(row["sha256"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise ValueError("invalid_freeze_digest")
        seen.add(row["path"])
        path = _file(root, row["path"])
        if type(row["bytes"]) is not int or path.stat().st_size != row["bytes"] or _hash(path) != row["sha256"]:
            raise ValueError("frozen_file_drift")
    return manifest
