"""Tests for exact-hash recovery from retained local files."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from scripts.research.analysis.evidence.reconcile_missing_artifacts_from_filesystem import (
    reconcile_filesystem,
)


def _inputs(root: Path, content: bytes) -> tuple[Path, Path, Path]:
    search_root = root / "files"
    search_root.mkdir()
    (search_root / "recovered").mkdir()
    (search_root / "recovered" / "config.yaml").write_bytes(content)
    (search_root / "different").mkdir()
    (search_root / "different" / "config.yaml").write_bytes(b"different")
    report_path = root / "verification.json"
    node_id = "run_artifact:expected"
    report_path.write_text(
        json.dumps({"failures": [{"id": node_id, "kind": "run_artifact", "status": "missing"}]}),
        encoding="utf-8",
    )
    dag_path = root / "dag.json"
    dag_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": node_id,
                        "kind": "run_artifact",
                        "path": "outputs/campaign/config.yaml",
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return report_path, dag_path, search_root


def test_reconciles_exact_same_basename_file_by_hash(tmp_path: Path) -> None:
    report_path, dag_path, search_root = _inputs(tmp_path, b"expected bytes")

    result = reconcile_filesystem(
        report_path,
        dag_path,
        search_root,
        max_candidate_bytes=1024,
        workers=2,
    )

    assert result["status"] == "complete"
    assert result["candidate_file_count"] == 2
    assert len(result["matches"]) == 1
    assert result["matches"][0]["files"][0]["path"].endswith("recovered/config.yaml")
    assert result["unmatched_target_ids"] == []
    assert result["walk_error_count"] == 0


def test_hash_limit_prevents_reading_large_candidate_set(tmp_path: Path) -> None:
    report_path, dag_path, search_root = _inputs(tmp_path, b"expected bytes")

    result = reconcile_filesystem(
        report_path,
        dag_path,
        search_root,
        max_candidate_bytes=1,
    )

    assert result["status"] == "hash_limit_exceeded"
    assert result["matches"] == []
    assert "hashed_file_count" not in result


def test_walk_error_makes_filesystem_scan_incomplete(monkeypatch, tmp_path: Path) -> None:
    report_path, dag_path, search_root = _inputs(tmp_path, b"expected bytes")

    def walk_with_permission_error(root, *, followlinks, onerror):
        del followlinks
        onerror(PermissionError(13, "permission denied", str(root / "private")))
        yield str(root), [], []

    monkeypatch.setattr(os, "walk", walk_with_permission_error)
    result = reconcile_filesystem(
        report_path,
        dag_path,
        search_root,
        max_candidate_bytes=1024,
    )

    assert result["status"] == "incomplete_walk_errors"
    assert result["walk_error_count"] == 1
    assert result["walk_errors"] == [
        {"path": str(search_root / "private"), "error": "PermissionError"}
    ]
