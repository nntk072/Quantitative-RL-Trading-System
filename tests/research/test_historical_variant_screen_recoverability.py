import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import scripts.research.audits.audit_historical_variant_screen_recoverability as audit
from scripts.research.audits.audit_historical_variant_screen_recoverability import (
    build_workspace_availability_report,
    mainplan_checkpoints,
)


def test_mainplan_checkpoint_inventory_handles_nested_run_directories(
    tmp_path: Path,
) -> None:
    checkpoint = (
        tmp_path
        / "runs"
        / "attempts"
        / "variant"
        / "attempt1"
        / "variant"
        / "timestamped_run"
        / "model"
        / "ppo_ckpt_1000000_steps.zip"
    )
    checkpoint.parent.mkdir(parents=True)
    checkpoint.touch()

    assert mainplan_checkpoints(tmp_path) == [checkpoint]


def test_workspace_availability_is_path_only_and_reports_missing_source_trees(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "archive"
    probe = archive / "gpu_campaigns" / "ladder18_seed50_cpu_buffer_probe_20261016"
    probe.mkdir(parents=True)
    (probe / "campaign.json").write_text("{}", encoding="utf-8")
    (probe / "source_snapshot.zip").write_bytes(b"source only")

    report = build_workspace_availability_report(
        archive_outputs=archive,
        thesis_checkout=tmp_path / "missing_thesis_checkout",
    )

    assert report["scope"]["type"] == "path_and_filename_inventory"
    assert report["scope"]["archive_checkpoint_archive_count"] == 1
    assert report["scope"]["archive_contents_hashed"] is False
    assert report["scope"]["full_scratch_search_performed"] is False
    assert report["known_paths"]["thesis_checkout"]["exists"] is False
    assert report["known_paths"]["mainplan"]["exists"] is False
    assert report["known_paths"]["source"]["exists"] is False
    assert report["known_paths"]["recovery"]["exists"] is False
    assert report["retained_cpu_buffer_probe"]["checkpoint_archive_count"] == 1


def test_source_state_records_head_and_dirty_paths() -> None:
    responses = iter(("abc123\n", " M tracked.py\n?? untracked.py\n"))
    with patch(
        "scripts.research.audits.audit_historical_variant_screen_recoverability.subprocess.check_output",
        side_effect=responses,
    ):
        state = audit.source_state()

    assert state == {
        "head": "abc123",
        "dirty_paths": [" M tracked.py", "?? untracked.py"],
    }


def test_build_report_accounts_for_missing_runs_and_matching_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = tmp_path / "outputs"
    recovery_dir = outputs / "recovery"
    source_dir = outputs / "source"
    mainplan_dir = outputs / "mainplan"
    summary_path = recovery_dir / "reports" / "experiment_run_results_summary_v2.json"
    experiment_run_path = recovery_dir / "experiment_run.json"
    report_only_archive = outputs / "restored-checkpoint.zip"
    archive_bytes = b"checkpoint archive fixture"
    outputs.mkdir()
    report_only_archive.write_bytes(archive_bytes)
    source_hashes = {
        f"variant_{index}": hashlib.sha256(f"source-{index}".encode()).hexdigest()
        for index in range(18)
    }
    source_hashes["variant_0"] = hashlib.sha256(archive_bytes).hexdigest()
    final_hashes = {
        f"variant_{index}": hashlib.sha256(f"final-{index}".encode()).hexdigest()
        for index in range(18)
    }
    experiment_run = {
        "initial_checkpoint_lineage": {
            key: {"checkpoint_sha256": digest} for key, digest in source_hashes.items()
        },
        "jobs": [
            {
                "key": key,
                "artifact_hashes": {"model/ppo_final.zip": final_hashes[key]},
            }
            for key in source_hashes
        ],
    }
    summary = {
        "experiment_run_dir": str(recovery_dir),
        "jobs": [
            {
                "variant": key,
                "controller_status": "succeeded",
                "run_artifact_dir": f"runs/{key}",
                "train_metrics": {"return": 0.0},
                "test_metrics_report_only": {"return": 0.0},
                "evidence_sha256": {"manifest.json": "0" * 64},
            }
            for key in source_hashes
        ],
    }
    experiment_run_path.parent.mkdir(parents=True)
    experiment_run_path.write_text(json.dumps(experiment_run), encoding="utf-8")
    summary_path.parent.mkdir(parents=True)
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    for base in (recovery_dir, source_dir):
        manifest = base / "reports" / "replay" / "reanalysis_manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("{}", encoding="utf-8")
    for index in range(18):
        checkpoint = (
            mainplan_dir / f"variant-{index}" / "attempt1" / "model" / audit.MAINPLAN_CHECKPOINT
        )
        checkpoint.parent.mkdir(parents=True)
        checkpoint.write_bytes(f"mainplan-{index}".encode())

    monkeypatch.setattr(audit, "OUTPUTS", outputs)
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "RECOVERY_DIR", recovery_dir)
    monkeypatch.setattr(audit, "SOURCE_DIR", source_dir)
    monkeypatch.setattr(audit, "MAINPLAN_DIR", mainplan_dir)
    monkeypatch.setattr(audit, "SUMMARY_PATH", summary_path)
    monkeypatch.setattr(audit, "source_state", lambda: {"head": "test", "dirty_paths": []})

    report = audit.build_report()

    assert report["scope"]["archive_count"] == 19
    assert report["inputs"]["audit_script_sha256"] == audit.sha256(Path(audit.__file__).resolve())
    assert report["screen"]["present_1m_mainplan_checkpoints"] == 18
    assert report["screen"]["present_run_artifact_directories"] == 0
    assert report["screen"]["available_replay_manifest_count"] == 2
    assert report["checkpoint_recoverability"]["source_attempt3_hash_matches_in_outputs"] == 1
    assert report["checkpoint_recoverability"]["recovery_final_hash_matches_in_outputs"] == 0
    assert report["checkpoint_recoverability"]["disposition"].startswith("partial or exact")


def test_main_writes_report_and_refuses_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "recoverability.json"
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["audit", "--out", str(output)])
    monkeypatch.setattr(
        audit,
        "build_report",
        lambda: {"checkpoint_recoverability": {"disposition": "fixture"}},
    )

    assert audit.main() == 0
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "checkpoint_recoverability": {"disposition": "fixture"}
    }
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        audit.main()


def test_main_workspace_availability_mode_writes_path_only_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "workspace_availability.json"
    report = {
        "schema": "qrl.historical_variant_screen_workspace_availability.v1",
        "known_paths": {},
        "scope": {"archive_checkpoint_archive_count": 0},
    }
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "build_workspace_availability_report", lambda: report)
    monkeypatch.setattr(
        sys,
        "argv",
        ["audit", "--workspace-availability", "--out", str(output)],
    )

    assert audit.main() == 0
    assert json.loads(output.read_text(encoding="utf-8")) == report


def test_current_workspace_availability_record_matches_packet_manifest() -> None:
    packet = audit.ROOT / "evidence/research/historical_variant_screen_recoverability"
    report_path = packet / "current_workspace_availability.json"
    manifest = json.loads((packet / "evidence_manifest.json").read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    asset = next(item for item in manifest["assets"] if item["path"].endswith(report_path.name))

    assert hashlib.sha256(report_path.read_bytes()).hexdigest() == asset["sha256"]
    assert report_path.stat().st_size == asset["bytes"]
    assert report["schema"] == "qrl.historical_variant_screen_workspace_availability.v1"
    assert report["scope"]["archive_contents_hashed"] is False
