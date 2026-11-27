"""Controller dry-run validates in-repository initial checkpoint map inputs."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest

from experiments.runs import execution


def _write_parent_lineage(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    run_key = "probe__seed7"
    parent = tmp_path / "parent-run"
    attempt = parent / "runs" / "attempts" / run_key / "attempt1"
    checkpoint = attempt / run_key / "20261126_000000_run" / "model" / "ppo_ckpt_50_steps.zip"
    checkpoint.parent.mkdir(parents=True)
    with zipfile.ZipFile(checkpoint, "w") as archive:
        archive.writestr("data", json.dumps({"num_timesteps": 50}))

    identity = {"experiment": "lineage-test", "revision": "abc"}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    provenance = {
        "experiment_run_fingerprint": fingerprint,
        "identity": identity,
        "run_key": run_key,
        "variant": "probe",
        "seed": 7,
        "attempt": 1,
        "requested_timesteps": 100,
    }
    provenance_path = attempt / "attempt_provenance.json"
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    (parent / "experiment_run.json").write_text(
        json.dumps(
            {
                "fingerprint": fingerprint,
                "git_sha": "a" * 40,
                "timesteps": 100,
                "jobs": [
                    {
                        "key": run_key,
                        "variant": "probe",
                        "seed": 7,
                        "attempts": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    record = {
        "key": run_key,
        "source_experiment_run_dir": str(parent),
        "source_experiment_run_fingerprint": fingerprint,
        "source_attempt": 1,
        "source_attempt_provenance_sha256": hashlib.sha256(
            provenance_path.read_bytes()
        ).hexdigest(),
        "source_num_timesteps": 50,
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
    }
    return parent, checkpoint, record


def test_dry_run_validates_checkpoint_map_and_reports_selected_lineage(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    root = tmp_path / "repo"
    run_config = root / "config" / "experiment_runs"
    (root / "config" / "base").mkdir(parents=True)
    run_config.mkdir(parents=True)
    (root / "config" / "base" / "default.yaml").write_text(
        "data:\n  split:\n    train_end: '2025-12-31'\n    test_start: '2026-01-01'\n",
        encoding="utf-8",
    )
    (root / "config" / "experiments.yaml").write_text(
        "variants:\n  - name: probe_variant\n", encoding="utf-8"
    )
    (run_config / "variant_list.txt").write_text("probe_variant\n", encoding="utf-8")
    spec = run_config / "probe.yaml"
    spec.write_text(
        "experiment_run_id: coverage_probe\n"
        "variant_file: config/experiment_runs/variant_list.txt\n"
        "variants: [probe_variant]\n"
        "seeds: [7]\n"
        "timesteps: 100\n"
        "data_source: frames\n"
        "split:\n  train_end: '2025-12-31'\n  test_start: '2026-01-01'\n"
        "evaluation:\n  locked_oos_role: final_report_only\n"
        "  selection_allowed: false\n  deterministic: true\n",
        encoding="utf-8",
    )
    checkpoint_map = run_config / "checkpoints.json"
    checkpoint_map.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(execution, "ROOT", root)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [])
    calls: list[tuple[Path, list[dict[str, Any]], int]] = []

    def validate(path: Path, jobs: list[dict[str, Any]], steps: int) -> dict[str, dict[str, Any]]:
        calls.append((path, jobs, steps))
        return {jobs[0]["key"]: {"checkpoint_path": "parent/model/ppo_ckpt_50_steps.zip"}}

    monkeypatch.setattr(execution, "validate_initial_checkpoints", validate)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "experiment_run_controller.py",
            "--experiment-run-spec",
            str(spec),
            "--initial-checkpoints",
            str(checkpoint_map),
            "--dry-run",
        ],
    )

    assert execution.main() == 0

    report = json.loads(capsys.readouterr().out)
    assert calls[0][0] == checkpoint_map.resolve()
    assert [job["key"] for job in calls[0][1]] == ["probe_variant__seed7"]
    assert calls[0][2] == 100
    assert report["initial_checkpoints"] == 1


def test_checkpoint_discovery_skips_corrupt_or_over_budget_candidates(tmp_path: Path) -> None:
    parent, checkpoint, record = _write_parent_lineage(tmp_path)
    run_key = "probe__seed7"
    model_dir = checkpoint.parent
    (model_dir / "ppo_ckpt_90_steps.zip").write_bytes(b"not a zip archive")
    with zipfile.ZipFile(model_dir / "ppo_ckpt_120_steps.zip", "w") as archive:
        archive.writestr("data", json.dumps({"num_timesteps": 120}))

    selected = execution.latest_resumable_checkpoint(
        parent,
        run_key,
        1,
        record["source_experiment_run_fingerprint"],
        max_steps=100,
    )

    assert selected == checkpoint
    archived = tmp_path / "successor" / "bootstrap" / "checkpoint.zip"
    archived.parent.mkdir(parents=True)
    archived.write_bytes(b"parent checkpoint")
    bootstrap = {run_key: archived}
    assert execution.choose_resume_checkpoint(parent, run_key, None, "unused", bootstrap) == (
        archived,
        "parent_experiment_run_checkpoint",
    )
    assert execution.choose_resume_checkpoint(
        parent,
        run_key,
        1,
        record["source_experiment_run_fingerprint"],
        bootstrap,
    ) == (
        model_dir / "ppo_ckpt_120_steps.zip",
        "interrupted_experiment_run_attempt",
    )


def test_checkpoint_lineage_validates_hash_and_variant_seed_identity(tmp_path: Path) -> None:
    _parent, _checkpoint, record = _write_parent_lineage(tmp_path)
    map_path = tmp_path / "initial-checkpoints.json"
    map_path.write_text(
        json.dumps({"schema_version": 1, "checkpoints": [record]}), encoding="utf-8"
    )

    validated = execution.validate_initial_checkpoints(
        map_path,
        [{"key": "probe__seed7", "variant": "probe", "seed": 7}],
        target_steps=100,
    )
    assert validated["probe__seed7"]["source_num_timesteps"] == 50
    assert validated["probe__seed7"]["checkpoint_sha256"] == record["checkpoint_sha256"]

    with pytest.raises(ValueError, match="identity mismatch"):
        execution.validate_initial_checkpoints(
            map_path,
            [{"key": "probe__seed7", "variant": "probe", "seed": 8}],
            target_steps=100,
        )

    tampered = {**record, "checkpoint_sha256": "0" * 64}
    map_path.write_text(
        json.dumps({"schema_version": 1, "checkpoints": [tampered]}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="hash-mismatched"):
        execution.validate_initial_checkpoints(
            map_path,
            [{"key": "probe__seed7", "variant": "probe", "seed": 7}],
            target_steps=100,
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"schema_version": 2, "checkpoints": []}, "schema_version=1"),
        ({"schema_version": 1, "checkpoints": {}}, "checkpoints list"),
        ({"schema_version": 1, "checkpoints": ["bad-record"]}, "entries must be mappings"),
    ],
)
def test_checkpoint_lineage_rejects_malformed_map_schemas(
    tmp_path: Path, payload: dict[str, Any], message: str
) -> None:
    map_path = tmp_path / "bad-checkpoints.json"
    map_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        execution.validate_initial_checkpoints(
            map_path,
            [{"key": "probe__seed7", "variant": "probe", "seed": 7}],
            target_steps=100,
        )


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ({"key": "other__seed7"}, "unknown or duplicate run key"),
        ({"key": "probe__seed7"}, "paths are missing"),
    ],
)
def test_checkpoint_lineage_rejects_unknown_or_incomplete_records(
    tmp_path: Path, entry: dict[str, Any], message: str
) -> None:
    map_path = tmp_path / "incomplete-checkpoints.json"
    map_path.write_text(json.dumps({"schema_version": 1, "checkpoints": [entry]}), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        execution.validate_initial_checkpoints(
            map_path,
            [{"key": "probe__seed7", "variant": "probe", "seed": 7}],
            target_steps=100,
        )
