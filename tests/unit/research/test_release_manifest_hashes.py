"""Tests for the release manifest hash verifier."""

from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.research.audits.update_release_manifest_hashes import _refresh_hash_map


def test_refresh_hash_map_recomputes_relative_file_hash(tmp_path: Path) -> None:
    payload = b"release evidence fixture\n"
    (tmp_path / "report.md").write_bytes(payload)

    hashes, issues = _refresh_hash_map(
        tmp_path,
        {"report.md": "stale"},
        description="fixture",
    )

    assert hashes == {"report.md": hashlib.sha256(payload).hexdigest()}
    assert issues == []


def test_refresh_hash_map_rejects_paths_outside_root(tmp_path: Path) -> None:
    hashes, issues = _refresh_hash_map(
        tmp_path,
        {"../outside.json": "unused"},
        description="fixture",
    )

    assert hashes == {}
    assert issues == ["fixture: path escapes root: ../outside.json"]
