"""Tests for byte-identical run artifact recovery from retained archives."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from scripts.research.analysis.evidence.reconcile_missing_artifacts_from_archives import (
    reconcile_archives,
)


def _inputs(root: Path, content: bytes) -> tuple[Path, Path, Path]:
    archive_root = root / "archives"
    archive_root.mkdir()
    with zipfile.ZipFile(archive_root / "retained.zip", "w") as archive:
        archive.writestr("campaign/run/config.yaml", content)
        archive.writestr("other/run/config.yaml", b"different content")
        archive.writestr("other/renamed.bin", content)
    node_id = "run_artifact:expected"
    report_path = root / "verification.json"
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
                        "path": "outputs/gpu_campaigns/campaign/run/config.yaml",
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return report_path, dag_path, archive_root


def test_reconciles_matching_archive_member_by_content_hash(tmp_path: Path) -> None:
    report_path, dag_path, archive_root = _inputs(tmp_path, b"expected bytes")

    report = reconcile_archives(
        report_path,
        dag_path,
        archive_root,
        hash_candidates=True,
        max_uncompressed_bytes=1024,
        workers=2,
    )

    assert report["status"] == "complete"
    assert report["target_count"] == 1
    assert report["member_candidate_count"] == 2
    assert len(report["matches"]) == 1
    assert report["matches"][0]["archive_members"][0]["member"] == "campaign/run/config.yaml"
    assert report["unmatched_target_ids"] == []


def test_inventory_mode_does_not_read_archive_member_contents(tmp_path: Path) -> None:
    report_path, dag_path, archive_root = _inputs(tmp_path, b"expected bytes")

    report = reconcile_archives(
        report_path,
        dag_path,
        archive_root,
        hash_candidates=False,
        max_uncompressed_bytes=1024,
    )

    assert report["status"] == "inventory_only"
    assert report["member_candidate_count"] == 2
    assert report["matches"] == []


def test_all_member_hashing_finds_identical_bytes_under_a_different_name(
    tmp_path: Path,
) -> None:
    report_path, dag_path, archive_root = _inputs(tmp_path, b"expected bytes")

    report = reconcile_archives(
        report_path,
        dag_path,
        archive_root,
        hash_candidates=True,
        all_members=True,
        max_uncompressed_bytes=1024,
        workers=2,
    )

    assert report["status"] == "complete"
    assert report["all_direct_members"] is True
    assert report["member_candidate_count"] == 3
    assert len(report["matches"]) == 1
    assert len(report["matches"][0]["archive_members"]) == 2


def test_hash_limit_prevents_decompressing_candidate_members(tmp_path: Path) -> None:
    report_path, dag_path, archive_root = _inputs(tmp_path, b"expected bytes")

    report = reconcile_archives(
        report_path,
        dag_path,
        archive_root,
        hash_candidates=True,
        max_uncompressed_bytes=1,
    )

    assert report["status"] == "hash_limit_exceeded"
    assert report["matches"] == []
    assert "hashed_candidate_count" not in report
