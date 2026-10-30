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
HISTORICAL_SOURCE_PATHS = (
    "scripts/research/thesis/p6_monthly_entry_exit_decomposition.py",
    "scripts/research/thesis/p6_training_dynamics_control.py",
    "scripts/research/thesis/evidence/build_p7_paired_seed_payload.py",
    "scripts/research/thesis/evidence/build_p7_tick_cost_stress_reports.py",
    "scripts/research/thesis/evidence/run_p7_tick_cost_stress_replay.py",
    "scripts/research/audits/run_p1_schedule_freeze_gate.sh",
    "scripts/research/audits/run_p1_tick_fold_validation.sh",
    "scripts/research/audits/run_p1_tick_quality_validation.sh",
    "scripts/research/audits/run_p3_checkpoint_recovery_smoke.sh",
)


def _source_snapshot_manifest() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(
            (REPOSITORY_ROOT / "docs/thesis/evidence/source_snapshots/manifest.json").read_text(
                encoding="utf-8"
            )
        ),
    )


def _historical_source_record(historical_path: str) -> dict[str, str]:
    manifest = _source_snapshot_manifest()
    sources = manifest["sources"]
    assert isinstance(sources, list)
    records = [
        record
        for record in sources
        if isinstance(record, dict) and record.get("historical_path") == historical_path
    ]
    assert len(records) == 1
    return records[0]


@pytest.mark.parametrize("historical_path", HISTORICAL_SOURCE_PATHS)
def test_retired_phase_path_keeps_functional_source_and_historical_hash(
    historical_path: str,
) -> None:
    record = _historical_source_record(historical_path)
    retired_path = REPOSITORY_ROOT / historical_path
    canonical_path = REPOSITORY_ROOT / record["canonical_path"]

    assert not retired_path.exists()
    assert canonical_path.is_file()
    assert hashlib.sha256(canonical_path.read_bytes()).hexdigest() == record["sha256"]


@pytest.mark.parametrize(
    ("historical_path", "evidence_path", "manifest_field"),
    (
        (
            "scripts/research/thesis/p6_monthly_entry_exit_decomposition.py",
            "docs/thesis/evidence/p6_monthly_entry_exit_20261025/p6_monthly_entry_exit_decomposition.json",
            "analysis_script_sha256",
        ),
        (
            "scripts/research/thesis/p6_training_dynamics_control.py",
            "docs/thesis/evidence/p6_monthly_entry_exit_20261025/p6_training_dynamics_control.json",
            "analysis_script_sha256",
        ),
    ),
)
def test_frozen_p6_analysis_source_hashes_remain_verifiable(
    historical_path: str,
    evidence_path: str,
    manifest_field: str,
) -> None:
    evidence = json.loads((REPOSITORY_ROOT / evidence_path).read_text(encoding="utf-8"))
    recorded_hash = evidence[manifest_field]
    record = _historical_source_record(historical_path)

    assert record["sha256"] == recorded_hash


def test_frozen_paired_seed_source_hash_is_still_verifiable() -> None:
    manifest_path = (
        REPOSITORY_ROOT
        / "outputs/gpu_campaigns/rq1_entry_fsm_pair_seed101_105_train2025_test2026_20261021_scratch1"
        / "reports/p7_tick_cost_stress_20261022/baseline_5pt/replay1/control_seed101"
        / "reanalysis_manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    provenance = manifest["evaluation_provenance"]["source"]
    historical_relative_path = HISTORICAL_SOURCE_PATHS[2]
    matching_records = [
        record for record in provenance["dirty_files"] if record["path"] == historical_relative_path
    ]

    assert len(matching_records) == 1
    source_record = _historical_source_record(historical_relative_path)
    assert source_record["sha256"] == matching_records[0]["sha256"]


@pytest.mark.parametrize(
    "script_path",
    (
        "scripts/research/thesis/evidence/build_tick_cost_stress_reports.py",
        "scripts/research/thesis/evidence/replay_tick_cost_stress.py",
    ),
)
def test_cost_stress_command_help_exits_before_accessing_campaign_data(script_path: str) -> None:
    result = subprocess.run(
        [sys.executable, str(REPOSITORY_ROOT / script_path), "--help"],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert "--repo-root" in result.stdout


def test_paired_seed_payload_builder_has_a_functional_api_name() -> None:
    from scripts.research.thesis.evidence.build_paired_seed_payload import (
        build_paired_seed_payload,
    )

    assert callable(build_paired_seed_payload)
