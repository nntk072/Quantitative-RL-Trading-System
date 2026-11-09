"""Verify retired source paths map to functional files with unchanged hashes."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_SOURCE_BASENAMES = (
    "p6_monthly_entry_exit_decomposition.py",
    "p6_training_dynamics_control.py",
    "build_p7_paired_seed_payload.py",
    "build_p7_tick_cost_stress_reports.py",
    "run_p7_tick_cost_stress_replay.py",
    "run_p1_schedule_freeze_gate.sh",
    "run_p1_tick_fold_validation.sh",
    "run_p1_tick_quality_validation.sh",
    "run_p3_checkpoint_recovery_smoke.sh",
)


def _source_snapshot_manifest() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(
            (
                REPOSITORY_ROOT
                / "evidence/research/historical_source_provenance/source_mapping.json"
            ).read_text(encoding="utf-8")
        ),
    )


def _historical_source_record(basename: str) -> dict[str, str]:
    manifest = _source_snapshot_manifest()
    sources = manifest["sources"]
    assert isinstance(sources, list)
    records = [
        record
        for record in sources
        if isinstance(record, dict)
        and Path(str(record.get("historical_path", ""))).name == basename
    ]
    assert len(records) == 1
    return records[0]


def _recorded_path(path: str) -> Path:
    candidate = REPOSITORY_ROOT / path
    if candidate.is_file():
        return candidate
    migration = json.loads(
        (
            REPOSITORY_ROOT
            / "docs/architecture/migrations/research_directory_classification_20261031.json"
        ).read_text(encoding="utf-8")
    )
    matches = [record["new_path"] for record in migration["files"] if record["old_path"] == path]
    assert len(matches) == 1
    migrated_path = matches[0]
    assert isinstance(migrated_path, str)
    return REPOSITORY_ROOT / migrated_path


@pytest.mark.parametrize("basename", HISTORICAL_SOURCE_BASENAMES)
def test_retired_phase_path_keeps_functional_source_and_historical_hash(
    basename: str,
) -> None:
    record = _historical_source_record(basename)
    retired_path = REPOSITORY_ROOT / record["historical_path"]
    canonical_path = _recorded_path(record["canonical_path"])

    assert not retired_path.exists()
    assert canonical_path.is_file()
    assert len(record["sha256"]) == 64
    assert all(character in "0123456789abcdef" for character in record["sha256"])
    historical_snapshot = record.get("historical_source_snapshot")
    if historical_snapshot is not None:
        snapshot_path = _recorded_path(historical_snapshot)
        assert snapshot_path.is_file()
        assert hashlib.sha256(snapshot_path.read_bytes()).hexdigest() == record["sha256"]
        assert record["status"] == (
            "historical alias retired; canonical source evolved; exact historical bytes retained separately"
        )
    elif hashlib.sha256(canonical_path.read_bytes()).hexdigest() != record["sha256"]:
        assert record["status"] == (
            "historical digest retained; canonical source evolved and exact historical bytes are unavailable"
        )


@pytest.mark.parametrize(
    ("historical_basename", "evidence_path", "manifest_field"),
    (
        (
            "p6_monthly_entry_exit_decomposition.py",
            "evidence/research/entry_and_exit_attribution/monthly_entry_exit_summary.json",
            "analysis_script_sha256",
        ),
        (
            "p6_training_dynamics_control.py",
            "evidence/research/entry_and_exit_attribution/training_dynamics_control.json",
            "analysis_script_sha256",
        ),
    ),
)
def test_frozen_p6_analysis_source_hashes_remain_verifiable(
    historical_basename: str,
    evidence_path: str,
    manifest_field: str,
) -> None:
    evidence = json.loads((REPOSITORY_ROOT / evidence_path).read_text(encoding="utf-8"))
    recorded_hash = evidence[manifest_field]
    record = _historical_source_record(historical_basename)

    assert record["sha256"] == recorded_hash


def test_frozen_paired_seed_source_hash_is_still_verifiable() -> None:
    source_record = _historical_source_record("build_p7_paired_seed_payload.py")
    provenance_dag = json.loads(
        (
            REPOSITORY_ROOT
            / "evidence/research/releases/negative-evidence-readiness/EXPERIMENT_PROVENANCE_DAG.json"
        ).read_text(encoding="utf-8")
    )
    source_nodes = [
        node
        for node in provenance_dag["nodes"]
        if node.get("kind") == "source_file"
        and node.get("path") == source_record["historical_path"]
    ]

    assert len(source_nodes) == 1
    assert source_nodes[0]["sha256"] == source_record["sha256"]
    snapshot_path = _recorded_path(source_record["historical_source_snapshot"])
    assert hashlib.sha256(snapshot_path.read_bytes()).hexdigest() == source_record["sha256"]


@pytest.mark.parametrize(
    "script_path",
    (
        "scripts/research/analysis/evidence/build_tick_cost_stress_reports.py",
        "scripts/research/analysis/evidence/replay_tick_cost_stress.py",
    ),
)
def test_cost_stress_command_help_exits_before_accessing_experiment_run_data(
    script_path: str,
) -> None:
    result = subprocess.run(
        [sys.executable, str(REPOSITORY_ROOT / script_path), "--help"],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert "--repo-root" in result.stdout


def test_paired_seed_payload_builder_has_a_functional_api_name() -> None:
    from scripts.research.analysis.evidence.build_paired_seed_payload import (
        build_paired_seed_payload,
    )

    assert callable(build_paired_seed_payload)
