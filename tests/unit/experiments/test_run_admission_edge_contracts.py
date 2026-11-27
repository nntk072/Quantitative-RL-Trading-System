"""Synthetic artifact-admission and checkpoint-resume edge contracts."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from experiments.runs import execution


def test_controller_marks_zero_exit_worker_failed_when_artifacts_are_rejected(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """A zero worker exit is insufficient when required artifacts fail admission."""
    repository = tmp_path / "repo"
    config = repository / "config"
    (config / "base").mkdir(parents=True)
    (config / "experiments.yaml").write_text(
        "variants:\n  - name: probe_variant\n", encoding="utf-8"
    )
    (config / "base" / "default.yaml").write_text(
        "data:\n  raw_dir: data\n  split:\n"
        "    train_end: '2025-12-31'\n    test_start: '2026-01-01'\n",
        encoding="utf-8",
    )
    variant_file = repository / "variants.txt"
    variant_file.write_text("probe_variant\n", encoding="utf-8")

    monkeypatch.setattr(execution, "ROOT", repository)
    monkeypatch.setattr(
        execution,
        "runtime_metadata",
        lambda: {"python": "test", "machine": "test", "packages": {}},
    )
    source_files = [config / "experiments.yaml", variant_file]
    monkeypatch.setattr(execution, "experiment_run_source_files", lambda *_args: source_files)
    monkeypatch.setattr(
        execution,
        "write_experiment_run_source_snapshot",
        lambda *_args, **_kwargs: {
            "path": "source_snapshot.zip",
            "sha256": "a" * 64,
            "manifest_sha256": "b" * 64,
            "file_count": 2,
        },
    )
    monkeypatch.setattr(
        execution,
        "available_resources",
        lambda: {"cpu_affinity": 4, "memory_limit_bytes": 128 * 1024**3},
    )
    monkeypatch.setattr(execution, "sample_resources", lambda *_args: None)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(execution.__dict__["signal"], "signal", lambda *_args: None)
    monkeypatch.setattr(
        execution.__dict__["subprocess"],
        "check_output",
        lambda *_args, **_kwargs: "a" * 40,
    )
    monkeypatch.setattr(
        execution,
        "verify_run_artifacts",
        lambda *_args, **_kwargs: (False, "synthetic checkpoint admission failure"),
    )
    monkeypatch.setattr(
        execution.__dict__["subprocess"],
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    class CompletedWorker:
        pid = 1234

        def poll(self) -> int:
            return 0

    monkeypatch.setattr(
        execution.__dict__["subprocess"],
        "Popen",
        lambda *_args, **_kwargs: CompletedWorker(),
    )
    monkeypatch.setenv("SLURM_JOB_ID", "test-allocation")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "experiment_run_controller.py",
            "--variant-file",
            str(variant_file),
            "--seeds",
            "7",
            "--timesteps",
            "100",
            "--workers",
            "1",
            "--n-envs",
            "4",
            "--experiment-run-id",
            "artifact-rejection",
        ],
    )

    assert execution.main() == 1

    run_dir = repository / "outputs" / "gpu_experiment_runs" / "artifact-rejection"
    manifest = json.loads((run_dir / "experiment_run.json").read_text(encoding="utf-8"))
    job = manifest["jobs"][0]
    assert job["status"] == "failed"
    assert job["exit_code"] == 0
    assert job["artifact_error"] == "synthetic checkpoint admission failure"
    assert not (run_dir / "markers" / "probe_variant__seed7.done").exists()


def test_artifact_admission_rejects_checkpoint_observation_shape_mismatch(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """The loaded model must retain the observation schema recorded by training."""
    run = tmp_path / "variant" / "attempt1"
    run.mkdir(parents=True)
    config_text = '{"env":{"normalize":true}}\n'
    (run / "config.yaml").write_text(config_text, encoding="utf-8")
    (run.parent / "resolved_config.json").write_text(
        json.dumps({"variant": "variant", "seed": 7, "steps": 8}), encoding="utf-8"
    )
    cache = tmp_path / "feature-cache.parquet"
    cache.write_bytes(b"feature cache")
    cache_hash = "a" * 16
    Path(f"{cache}.hash").write_text(cache_hash + "\n", encoding="utf-8")
    fingerprint_identity = {"jobs": ["variant__seed7"], "steps": 8}
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_identity, sort_keys=True).encode()
    ).hexdigest()
    (tmp_path / "attempt_provenance.json").write_text(
        json.dumps(
            {
                "run_key": "variant__seed7",
                "variant": "variant",
                "seed": 7,
                "requested_timesteps": 8,
                "attempt": 1,
                "experiment_run_fingerprint": fingerprint,
                "identity": fingerprint_identity,
            }
        ),
        encoding="utf-8",
    )
    feature_columns = ["close"]
    config_hash = hashlib.sha256(config_text.encode()).hexdigest()
    (run / "training_log.json").write_text(
        json.dumps(
            {
                "timesteps_completed": 8,
                "timesteps": 8,
                "seed": 7,
                "algo": "ppo",
                "test_sharpe": 0.1,
                "test_max_dd": 0.1,
                "test_trades": 1,
                "test_return": 0.1,
                "test_survived_full_year": True,
                "train_equity_ok": True,
                "feature_cache_hash": cache_hash,
                "feature_cache_name": cache.name,
                "run_manifests": ["run_manifest.json"],
                "feature_columns": feature_columns,
                "feature_schema_sha256": hashlib.sha256(
                    json.dumps(feature_columns, separators=(",", ":")).encode()
                ).hexdigest(),
                "effective_config_sha256": config_hash,
                "action_space_width": 2,
                "observation_space_shapes": {"observation": [3]},
                "env_flags": {"normalize": True},
            }
        ),
        encoding="utf-8",
    )
    model_path = run / "model" / "ppo_final.zip"
    model_path.parent.mkdir()
    with zipfile.ZipFile(model_path, "w") as archive:
        archive.writestr("checkpoint", "valid zip")
    (run / "run_manifest.json").write_text(
        json.dumps(
            {
                "feature_cache": {
                    "path": str(cache),
                    "identity": cache.name,
                    "sha256": cache_hash,
                    "file_sha256": hashlib.sha256(cache.read_bytes()).hexdigest(),
                },
                "checkpoint": {"sha256": hashlib.sha256(model_path.read_bytes()).hexdigest()},
                "config": {"sha256": config_hash},
            }
        ),
        encoding="utf-8",
    )

    from stable_baselines3 import PPO

    monkeypatch.setattr(
        PPO,
        "load",
        staticmethod(
            lambda *_args, **_kwargs: SimpleNamespace(
                num_timesteps=8,
                action_space=SimpleNamespace(shape=(2,)),
                observation_space=SimpleNamespace(
                    spaces={"observation": SimpleNamespace(shape=(4,))}
                ),
            )
        ),
    )

    admitted, reason = execution.verify_run_artifacts(
        tmp_path,
        "variant__seed7",
        8,
        expected_fingerprint=fingerprint,
        expected_attempt=1,
    )

    assert admitted is False
    assert reason == "missing valid training record/checkpoint at requested 8 steps"


def test_resume_skips_corrupt_newest_checkpoint_and_uses_earlier_valid_state(
    tmp_path: Path,
) -> None:
    """An unreadable newest checkpoint must not hide an intact earlier state."""
    key = "variant__seed7"
    fingerprint = "c" * 64
    attempt = tmp_path / "runs" / "attempts" / key / "attempt3"
    model = attempt / "model"
    model.mkdir(parents=True)
    (attempt / "attempt_provenance.json").write_text(
        json.dumps(
            {
                "experiment_run_fingerprint": fingerprint,
                "run_key": key,
                "attempt": 3,
            }
        ),
        encoding="utf-8",
    )
    earlier = model / "ppo_ckpt_1000_steps.zip"
    with zipfile.ZipFile(earlier, "w") as archive:
        archive.writestr("checkpoint", "valid earlier state")
    (model / "ppo_ckpt_2000_steps.zip").write_bytes(b"truncated zip")

    selected = execution.latest_resumable_checkpoint(
        tmp_path,
        key,
        3,
        fingerprint,
    )

    assert selected == earlier
