"""Artifact admission confines referenced run manifests to the attempt directory."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from experiments.runs.artifact_validation import verify_run_artifacts


def test_artifact_admission_rejects_manifest_path_escape_before_reading_external_files(
    tmp_path: Path,
) -> None:
    run = tmp_path / "attempt"
    run.mkdir()
    identity = {"steps": 100, "jobs": ["variant__seed7"]}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    (run / "attempt_provenance.json").write_text(
        json.dumps(
            {
                "run_key": "variant__seed7",
                "variant": "variant",
                "seed": 7,
                "requested_timesteps": 100,
                "attempt": 1,
                "experiment_run_fingerprint": fingerprint,
                "identity": identity,
            }
        ),
        encoding="utf-8",
    )
    columns: list[str] = []
    config = {"variant": "variant", "seed": 7, "steps": 100}
    (tmp_path / "resolved_config.json").write_text(json.dumps(config), encoding="utf-8")
    payload: dict[str, Any] = {
        "timesteps_completed": 100,
        "timesteps": 100,
        "seed": 7,
        "algo": "ppo",
        "test_sharpe": 0.0,
        "test_max_dd": 0.0,
        "test_trades": 0,
        "test_return": 0.0,
        "test_survived_full_year": False,
        "train_equity_ok": True,
        "feature_cache_hash": "a" * 16,
        "feature_cache_name": "cache.parquet",
        "run_manifests": ["../external-run-manifest.json"],
        "feature_columns": columns,
        "feature_schema_sha256": hashlib.sha256(b"[]").hexdigest(),
        "effective_config_sha256": "b" * 64,
        "action_space_width": 1,
        "observation_space_shapes": {},
        "env_flags": {},
    }
    (run / "training_log.json").write_text(json.dumps(payload), encoding="utf-8")

    admitted, reason = verify_run_artifacts(
        run,
        "variant__seed7",
        100,
        expected_fingerprint=fingerprint,
        expected_attempt=1,
    )

    assert admitted is False
    assert reason == "missing valid training record/checkpoint at requested 100 steps"
    assert not (tmp_path / "external-run-manifest.json").exists()
