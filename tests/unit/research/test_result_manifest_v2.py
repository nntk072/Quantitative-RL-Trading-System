"""Compatibility and identity completeness tests for research result manifests v2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from scripts.research.analysis.evidence.verify_result_manifest import (
    validate_result_manifest,
)

ROOT = Path(__file__).resolve().parents[3]


def _schema() -> dict[str, Any]:
    path = ROOT / "schemas/research_result_manifest_v2.schema.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _manifest() -> dict[str, Any]:
    path = (
        ROOT
        / "evidence/research/releases/negative-evidence-readiness/selected_pair_viability_manifest.json"
    )
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_selected_pair_v2_manifest_validates_all_linked_artifact_hashes() -> None:
    errors = validate_result_manifest(_manifest(), _schema(), repo_root=ROOT)

    assert errors == []


def test_v2_rejects_unknown_identity_without_reason() -> None:
    manifest = _manifest()
    manifest["runs"][0]["identity"]["source_tree_hash"] = {
        "status": "unknown",
        "reason": "",
    }

    errors = validate_result_manifest(
        manifest, _schema(), repo_root=ROOT, verify_artifact_hashes=False
    )

    assert any("source_tree_hash" in error and "reason" in error for error in errors)


def test_frozen_v2_rejects_explicit_unknown_identity() -> None:
    manifest = _manifest()
    manifest["manifest_status"] = "frozen"
    manifest["frozen_at_utc"] = "2026-11-02T00:00:00Z"

    errors = validate_result_manifest(
        manifest, _schema(), repo_root=ROOT, verify_artifact_hashes=False
    )

    assert any("frozen run" in error and "source_tree_hash" in error for error in errors)


def test_v2_requires_explicit_archive_scope_for_moved_run_outputs() -> None:
    manifest = _manifest()
    archived_artifact = manifest["runs"][0]["artifacts"][0]
    assert archived_artifact["storage_scope"] == "project_research_archive"
    archived_artifact.pop("storage_scope")

    errors = validate_result_manifest(manifest, _schema(), repo_root=ROOT)

    assert any("escapes repository root" in error for error in errors)
