from __future__ import annotations

import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path

from scripts.research.analysis.evidence.reconcile_missing_artifacts_from_nested_archives import (
    reconcile_nested_archives,
)


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_nested_archive_search_matches_exact_missing_bytes(tmp_path: Path) -> None:
    search_root = tmp_path / "scratch"
    search_root.mkdir()
    inner = _zip_bytes({"resolved_config.yaml": b"risk: percent_equity\n"})
    outer = search_root / "campaign.zip"
    with zipfile.ZipFile(outer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("checkpoint/model.zip", inner)

    missing_bytes = b"risk: percent_equity\n"
    missing_report = tmp_path / "missing.json"
    missing_report.write_text(
        json.dumps(
            {"failures": [{"kind": "run_artifact", "status": "missing", "id": "artifact-1"}]}
        ),
        encoding="utf-8",
    )
    provenance = tmp_path / "dag.json"
    provenance.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "artifact-1",
                        "path": "outputs/run/resolved_config.yaml",
                        "sha256": hashlib.sha256(missing_bytes).hexdigest(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    nested_report = tmp_path / "nested.json"
    nested_report.write_text(
        json.dumps(
            {
                "nested_archives": [
                    {
                        "archive": str(outer),
                        "member": "checkpoint/model.zip",
                        "uncompressed_size_bytes": len(inner),
                        "status": "scanned",
                    }
                ],
                "read_error_count": 2,
            }
        ),
        encoding="utf-8",
    )

    result = reconcile_nested_archives(
        missing_report,
        provenance,
        nested_report,
        search_root,
        max_container_bytes=1024 * 1024,
        max_uncompressed_bytes=1024 * 1024,
    )

    assert result["status"] == "complete_inventoried_nested_members_with_unreadable_outer_archives"
    assert result["nested_member_count"] == 1
    assert result["hashed_member_count"] == 1
    assert result["unmatched_target_ids"] == []
    assert result["matches"][0]["target"]["id"] == "artifact-1"
    assert result["matches"][0]["members"][0]["member"] == "resolved_config.yaml"


def test_nested_archive_search_fails_closed_above_expanded_size_limit(tmp_path: Path) -> None:
    search_root = tmp_path / "scratch"
    search_root.mkdir()
    inner = _zip_bytes({"large.txt": b"0123456789" * 100})
    outer = search_root / "campaign.zip"
    with zipfile.ZipFile(outer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("checkpoint/model.zip", inner)
    missing_report = tmp_path / "missing.json"
    missing_report.write_text('{"failures": []}', encoding="utf-8")
    provenance = tmp_path / "dag.json"
    provenance.write_text('{"nodes": []}', encoding="utf-8")
    nested_report = tmp_path / "nested.json"
    nested_report.write_text(
        json.dumps(
            {
                "nested_archives": [
                    {
                        "archive": str(outer),
                        "member": "checkpoint/model.zip",
                        "uncompressed_size_bytes": len(inner),
                        "status": "scanned",
                    }
                ],
                "read_error_count": 0,
            }
        ),
        encoding="utf-8",
    )

    result = reconcile_nested_archives(
        missing_report,
        provenance,
        nested_report,
        search_root,
        max_container_bytes=1024 * 1024,
        max_uncompressed_bytes=10,
    )

    assert result["status"] == "hash_limit_exceeded"
    assert result["hashed_member_count"] == 0
