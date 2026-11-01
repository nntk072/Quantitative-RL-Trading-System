#!/usr/bin/env python3
"""Refresh or verify the file hashes declared by the negative-result release manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from artifacts.atomic import write_json_atomic

ROOT = Path(__file__).resolve().parents[3]
RELEASE_DIR = ROOT / "evidence/research/releases/negative-evidence-readiness-2026-11-01"
MANIFEST_PATH = RELEASE_DIR / "RELEASE_MANIFEST.json"


def _sha256(path: Path) -> str:
    """Hash one bounded manifest file."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _refresh_hash_map(
    root: Path,
    entries: dict[str, str],
    *,
    description: str,
) -> tuple[dict[str, str], list[str]]:
    """Recompute a relative-path SHA-256 mapping and report missing files."""
    refreshed: dict[str, str] = {}
    missing: list[str] = []
    for relative in sorted(entries):
        path = root / relative
        try:
            path.resolve().relative_to(root.resolve())
        except ValueError:
            missing.append(f"{description}: path escapes root: {relative}")
            continue
        if not path.is_file():
            missing.append(f"{description}: missing file: {relative}")
            continue
        refreshed[relative] = _sha256(path)
    return refreshed, missing


def refresh_manifest(manifest_path: Path = MANIFEST_PATH) -> tuple[dict[str, Any], list[str]]:
    """Refresh the two manifest hash maps without hashing the manifest itself."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    release_dir = manifest_path.parent.resolve()
    content, content_missing = _refresh_hash_map(
        release_dir,
        manifest["content_hashes_sha256"],
        description="release content",
    )
    source, source_missing = _refresh_hash_map(
        ROOT,
        manifest["source_and_tracked_evidence_hashes_sha256"],
        description="source/evidence",
    )
    manifest["content_hashes_sha256"] = content
    manifest["source_and_tracked_evidence_hashes_sha256"] = source
    return manifest, content_missing + source_missing


def main() -> int:
    """Refresh hashes with ``--write`` or compare them with ``--check``."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="atomically refresh both hash maps")
    mode.add_argument("--check", action="store_true", help="verify both hash maps without writing")
    args = parser.parse_args()

    expected = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    updated, issues = refresh_manifest()
    if issues:
        for issue in issues:
            print(issue)
        return 1

    if args.write:
        write_json_atomic(MANIFEST_PATH, updated, default=None)
        print(
            "Updated hashes for "
            f"{len(updated['content_hashes_sha256'])} release files and "
            f"{len(updated['source_and_tracked_evidence_hashes_sha256'])} source/evidence files."
        )
        return 0

    mismatches: list[str] = []
    for field in ("content_hashes_sha256", "source_and_tracked_evidence_hashes_sha256"):
        before = expected.get(field, {})
        after = updated.get(field, {})
        for relative in sorted(set(before) | set(after)):
            if before.get(relative) != after.get(relative):
                mismatches.append(f"{field}: {relative}")
    if mismatches:
        for mismatch in mismatches:
            print(f"hash mismatch: {mismatch}")
        return 1
    print(
        "Verified hashes for "
        f"{len(updated['content_hashes_sha256'])} release files and "
        f"{len(updated['source_and_tracked_evidence_hashes_sha256'])} source/evidence files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
