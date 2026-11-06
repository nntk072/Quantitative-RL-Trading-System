#!/usr/bin/env python3
"""Refresh or verify repository-local hashes in a v2 research result manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.research.analysis.evidence.verify_result_manifest import (
    DEFAULT_SCHEMA_V2,
    _artifact_records,
    _contained_path,
)

from artifacts.atomic import write_text_atomic
from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_MANIFEST = (
    ROOT
    / "evidence/research/releases/negative-evidence-readiness/selected_pair_viability_manifest.json"
)


def _sha256(path: Path) -> str:
    """Hash one artifact in bounded chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def refresh_repository_artifact_hashes(
    manifest: dict[str, Any], *, repo_root: Path = ROOT
) -> tuple[int, list[str]]:
    """Update local artifact digests while leaving archived assets untouched."""
    updated = 0
    issues: list[str] = []
    root = repo_root.resolve()
    for artifact in _artifact_records(manifest):
        if artifact.get("storage_scope", "repository") != "repository":
            continue
        relative = artifact["path"]
        path = _contained_path(relative, root)
        if path is None:
            issues.append(f"repository artifact path escapes root: {relative}")
            continue
        if not path.is_file():
            issues.append(f"repository artifact is missing: {relative}")
            continue
        digest = _sha256(path)
        if artifact["sha256"] != digest:
            artifact["sha256"] = digest
            updated += 1
    return updated, issues


def main() -> int:
    """Refresh local hashes with ``--write`` or check them without mutation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", nargs="?", type=Path, default=DEFAULT_MANIFEST)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--write", action="store_true")
    operation.add_argument("--check", action="store_true")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    schema = json.loads(DEFAULT_SCHEMA_V2.read_text(encoding="utf-8"))
    from scripts.research.analysis.evidence.verify_result_manifest import (
        validate_result_manifest,
    )

    structure_errors = validate_result_manifest(
        manifest, schema, repo_root=ROOT, verify_artifact_hashes=False
    )
    if structure_errors:
        for error in structure_errors:
            print(error)
        return 1

    updated, issues = refresh_repository_artifact_hashes(manifest, repo_root=ROOT)
    if issues:
        for issue in issues:
            print(issue)
        return 1
    if args.write:
        write_text_atomic(manifest_path, json.dumps(manifest, indent=2) + "\n")
        print(f"Refreshed {updated} repository artifact hashes in {manifest_path}")
        return 0
    if updated:
        print(f"{updated} repository artifact hashes differ in {manifest_path}")
        return 1
    print(f"All repository artifact hashes match in {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
