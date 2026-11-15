"""Evaluation bundle manifest identity and parent lineage."""

from __future__ import annotations

import json
from pathlib import Path

from artifacts.identity import file_sha256
from evaluation.reporting.evaluation_manifest import (
    build_evaluation_manifest,
    write_evaluation_manifest,
)


def test_evaluation_manifest_hashes_numerical_artifacts_and_parent_manifest(
    tmp_path: Path,
) -> None:
    (tmp_path / "config.yaml").write_text("seed: 42\n", encoding="utf-8")
    training = tmp_path / "training"
    training.mkdir()
    metrics_path = training / "metrics.json"
    metrics_path.write_text('{"total_return_pct": 2.5}\n', encoding="utf-8")
    diagnostics_path = training / "evaluation_diagnostics.json"
    diagnostics_path.write_text(
        '{"policy_decisions_rows": 1, "policy_decisions_complete": true}\n',
        encoding="utf-8",
    )
    policy_decisions_path = training / "policy_decisions.csv"
    policy_decisions_path.write_text(
        "candidate_geometry_trace_schema_version,candidate_geometry_slot\n"
        "candidate-geometry-action-trace-v1,0\n",
        encoding="utf-8",
    )
    parent_path = tmp_path / "run_manifest.json"
    parent_path.write_text('{"schema_version": 1}\n', encoding="utf-8")

    manifest_path = write_evaluation_manifest(
        tmp_path,
        lineage={"checkpoint_sha256": "abc123", "source_run": "source-run"},
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "evaluation-artifacts-v1"
    assert manifest["partitions"] == ["training"]
    assert manifest["parent_manifests"]["run_manifest"]["sha256"] == file_sha256(parent_path)
    assert manifest["numerical_artifacts"] == [
        {"path": "training/metrics.json", "sha256": file_sha256(metrics_path)},
        {
            "path": "training/evaluation_diagnostics.json",
            "sha256": file_sha256(diagnostics_path),
        },
        {
            "path": "training/policy_decisions.csv",
            "sha256": file_sha256(policy_decisions_path),
        },
    ]
    assert manifest["lineage"] == {
        "checkpoint_sha256": "abc123",
        "source_run": "source-run",
    }
    assert build_evaluation_manifest(tmp_path) == {
        **manifest,
        "lineage": {},
    }

    diagnostics_path.write_text(
        '{"policy_decisions_rows": 0, "policy_decisions_complete": false}\n',
        encoding="utf-8",
    )
    updated = build_evaluation_manifest(tmp_path)
    diagnostics_record = next(
        item
        for item in updated["numerical_artifacts"]
        if item["path"] == "training/evaluation_diagnostics.json"
    )
    assert diagnostics_record["sha256"] == file_sha256(diagnostics_path)


def test_evaluation_manifest_hash_changes_when_diagnostics_change(tmp_path: Path) -> None:
    training = tmp_path / "training"
    training.mkdir()
    diagnostics_path = training / "evaluation_diagnostics.json"
    diagnostics_path.write_text('{"rows": 1}\n', encoding="utf-8")
    before = build_evaluation_manifest(tmp_path)
    diagnostics_path.write_text('{"rows": 2}\n', encoding="utf-8")

    after = build_evaluation_manifest(tmp_path)

    before_hash = next(
        item["sha256"]
        for item in before["numerical_artifacts"]
        if item["path"] == "training/evaluation_diagnostics.json"
    )
    after_hash = next(
        item["sha256"]
        for item in after["numerical_artifacts"]
        if item["path"] == "training/evaluation_diagnostics.json"
    )
    assert before_hash != after_hash
