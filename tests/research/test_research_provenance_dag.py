"""Tests for the manifest-based research provenance graph export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.research.analysis.evidence.build_research_provenance_dag import build_dag


def _write_manifest(root: Path, relative: str, payload: dict[str, Any]) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_dag_links_manifest_source_input_job_and_artifact(tmp_path: Path) -> None:
    relative = "outputs/gpu_experiment_runs/run_a/experiment_run.json"
    _write_manifest(
        tmp_path,
        relative,
        {
            "run_id": "run-a",
            "fingerprint": "fingerprint-a",
            "source_commit": "commit-a",
            "data_inputs": {"ticks": {"sha256": "a" * 64}},
            "source_hashes": {"features/pipeline.py": "b" * 64},
            "jobs": [
                {
                    "key": "control",
                    "seed": 42,
                    "status": "failed",
                    "artifact_hashes": {"report.json": "c" * 64},
                }
            ],
        },
    )

    result = build_dag(tmp_path)

    assert result["manifest_count"] == 1
    assert result["issues"] == []
    nodes = {node["kind"]: node for node in result["nodes"]}
    assert nodes["manifest"]["availability"] == "present_and_hashed"
    assert nodes["run"]["run_id"] == "run-a"
    assert {node["kind"] for node in result["nodes"]} >= {
        "data_input",
        "source_file",
        "job",
        "run_artifact",
    }
    assert len(result["edges"]) == 5


def test_build_dag_reports_malformed_manifest_without_dropping_other_runs(
    tmp_path: Path,
) -> None:
    _write_manifest(
        tmp_path,
        "outputs/gpu_experiment_runs/valid/experiment_run.json",
        {"run_id": "valid"},
    )
    malformed = tmp_path / "outputs/gpu_campaigns/broken/campaign.json"
    malformed.parent.mkdir(parents=True)
    malformed.write_text("{", encoding="utf-8")

    result = build_dag(tmp_path)

    assert result["manifest_count"] == 2
    assert len([node for node in result["nodes"] if node["kind"] == "run"]) == 1
    assert result["issues"][0]["path"] == "outputs/gpu_campaigns/broken/campaign.json"
