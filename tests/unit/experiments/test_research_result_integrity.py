"""Research output identity must be verified before metrics are published."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from artifacts.identity import file_sha256
from experiments.research.reporting import (
    consolidate_execution_manifests,
    rows_from_execution_manifest,
)


def _manifest(path: Path, artifact: Path, digest: str | None) -> Path:
    hashes = {} if digest is None else {str(artifact): digest}
    payload = {
        "schema_version": 1,
        "source_commit": "a" * 40,
        "domain": "features",
        "experiment_id": "feature_inputs",
        "commands": [
            {
                "command_id": "observation_validity",
                "variant_id": "observation_validity",
                "component": "observations",
                "status": "passed",
                "result_artifact": str(artifact),
                "artifact_sha256": hashes,
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_consolidation_rejects_modified_result_artifact(tmp_path: Path) -> None:
    result = tmp_path / "metrics.json"
    result.write_text('{"metrics":{"observations":12}}', encoding="utf-8")
    manifest = _manifest(tmp_path / "run.json", result, file_sha256(result))
    result.write_text('{"metrics":{"observations":13}}', encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        consolidate_execution_manifests([manifest], tmp_path / "changed")


def test_consolidation_rejects_missing_declared_result(tmp_path: Path) -> None:
    result = tmp_path / "missing.json"
    manifest = _manifest(tmp_path / "run.json", result, "a" * 64)
    with pytest.raises(FileNotFoundError, match="declared result artifact is missing"):
        consolidate_execution_manifests([manifest], tmp_path / "missing")


@pytest.mark.parametrize("digest", [None, "not-a-sha256"])
def test_consolidation_rejects_invalid_result_hash(tmp_path: Path, digest: str | None) -> None:
    result = tmp_path / "metrics.json"
    result.write_text('{"status":"passed"}', encoding="utf-8")
    manifest = _manifest(tmp_path / "run.json", result, digest)
    if digest is None:
        with pytest.raises(ValueError, match="not present in artifact manifest"):
            consolidate_execution_manifests([manifest], tmp_path / "missing_hash")
    else:
        with pytest.raises(ValueError, match="SHA-256 mismatch"):
            consolidate_execution_manifests([manifest], tmp_path / "invalid_hash")



def test_pending_command_does_not_require_result_bytes(tmp_path: Path) -> None:
    result = tmp_path / "not_produced.json"
    manifest = _manifest(tmp_path / "execution_manifest.json", result, None)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["commands"][0]["status"] = "pending"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    rows = rows_from_execution_manifest(manifest)
    assert len(rows) == 1
    assert rows[0].status == "pending"
    assert rows[0].metrics == {}
