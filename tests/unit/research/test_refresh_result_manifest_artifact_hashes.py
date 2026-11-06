from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.research.analysis.evidence.refresh_result_manifest_artifact_hashes import (
    refresh_repository_artifact_hashes,
)


def test_refresh_updates_only_repository_local_artifact_hashes(tmp_path: Path) -> None:
    local = tmp_path / "local.md"
    local.write_text("updated local evidence\n", encoding="utf-8")
    manifest = {
        "runs": [
            {
                "artifacts": [
                    {
                        "path": "local.md",
                        "sha256": "0" * 64,
                        "role": "report",
                    },
                    {
                        "path": "archive/member.zip",
                        "sha256": "1" * 64,
                        "role": "checkpoint",
                        "storage_scope": "project_research_archive",
                    },
                ]
            }
        ]
    }

    updated, issues = refresh_repository_artifact_hashes(manifest, repo_root=tmp_path)

    assert issues == []
    assert updated == 1
    assert (
        manifest["runs"][0]["artifacts"][0]["sha256"]
        == hashlib.sha256(local.read_bytes()).hexdigest()
    )
    assert manifest["runs"][0]["artifacts"][1]["sha256"] == "1" * 64
