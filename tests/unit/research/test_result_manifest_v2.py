"""Compatibility and identity completeness tests for research result manifests v2."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from scripts.research.analysis.evidence.verify_result_manifest import (
    _contained_path,
    validate_result_manifest,
)

ROOT = Path(__file__).resolve().parents[3]


def _schema() -> dict[str, Any]:
    path = ROOT / "schemas/research_result_manifest_v2.schema.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _manifest(root: Path) -> dict[str, Any]:
    """Build a small synthetic manifest independent of retired run evidence."""
    schema = _schema()
    identity_fields = schema["$defs"]["identity"]["required"]
    artifact_path = root / "artifact.txt"
    artifact_path.write_text("fixture artifact", encoding="utf-8")
    digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    identity = {field: {"status": "unknown", "reason": "test fixture"} for field in identity_fields}
    return {
        "schema": "qrl.research_result_manifest.v2",
        "manifest_status": "draft",
        "created_at_utc": "2026-01-01T00:00:00Z",
        "finding_id": "fixture",
        "research_question": "Does the fixture validate?",
        "hypothesis": "Schema validation accepts an explicit draft.",
        "finding_status": "not_estimated",
        "evidence_grade": "fixture",
        "protocol_path": "fixture_protocol.yaml",
        "runs": [
            {
                "run_id": "run-1",
                "variant_id": "control",
                "seed": 1,
                "role": "development",
                "status": "not_run",
                "identity": identity,
                "artifacts": [{"path": "artifact.txt", "sha256": digest, "role": "fixture"}],
            }
        ],
        "comparisons": [],
        "claims": [],
        "supporting_artifacts": [],
        "limitations": ["Synthetic test fixture."],
    }


def test_synthetic_v2_manifest_validates_all_linked_artifact_hashes(tmp_path: Path) -> None:
    errors = validate_result_manifest(_manifest(tmp_path), _schema(), repo_root=tmp_path)

    assert errors == []


def test_v2_rejects_unknown_identity_without_reason(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest["runs"][0]["identity"]["source_tree_hash"] = {
        "status": "unknown",
        "reason": "",
    }

    errors = validate_result_manifest(
        manifest, _schema(), repo_root=tmp_path, verify_artifact_hashes=False
    )

    assert any("source_tree_hash" in error and "reason" in error for error in errors)


def test_frozen_v2_rejects_explicit_unknown_identity(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest["manifest_status"] = "frozen"
    manifest["frozen_at_utc"] = "2026-11-02T00:00:00Z"

    errors = validate_result_manifest(
        manifest, _schema(), repo_root=tmp_path, verify_artifact_hashes=False
    )

    assert any("frozen run" in error and "source_tree_hash" in error for error in errors)


def test_v2_canonical_repository_artifacts_do_not_require_archive_scope(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    repository_artifact = manifest["runs"][0]["artifacts"][0]
    assert "storage_scope" not in repository_artifact

    errors = validate_result_manifest(manifest, _schema(), repo_root=tmp_path)

    assert errors == []


def test_archive_scope_hashes_paths_inside_repository_outputs(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    archive_root = tmp_path / "outputs" / "research_archive"
    archive_asset = archive_root / "historical_research_archive/README.md"
    archive_asset.parent.mkdir(parents=True)
    archive_asset.write_text("archive fixture", encoding="utf-8")
    manifest["supporting_artifacts"].append(
        {
            "path": "historical_research_archive/README.md",
            "sha256": hashlib.sha256(archive_asset.read_bytes()).hexdigest(),
            "role": "fixture",
            "storage_scope": "project_research_archive",
        }
    )

    errors = validate_result_manifest(manifest, _schema(), repo_root=tmp_path)

    assert errors == []


def test_archive_scope_resolves_relative_paths_under_sibling_archive(tmp_path: Path) -> None:
    repo_root = tmp_path / "project"
    archive_root = tmp_path / "project-research-archive"
    repo_root.mkdir()
    archive_root.mkdir()

    resolved = _contained_path(
        "outputs/run.json",
        repo_root,
        research_archive_root=archive_root,
    )

    assert resolved == (archive_root / "outputs/run.json").resolve()
    assert (
        _contained_path(
            "../outside.json",
            repo_root,
            research_archive_root=archive_root,
        )
        is None
    )
