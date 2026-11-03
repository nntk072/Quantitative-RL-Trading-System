from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from scripts.research.analysis.evaluation.summarize_ppo_training_dynamics import (
    build_report,
    summarize_training_log,
)


def test_training_log_summary_preserves_missing_and_nonfinite_metrics(tmp_path: Path) -> None:
    path = tmp_path / "training_log.csv"
    pd.DataFrame(
        {
            "timestep": [8192, 16384, 24576, 32768],
            "train/approx_kl": [float("nan"), 0.01, 0.02, float("inf")],
            "train/value_loss": ["bad", 3.0, 1.0, 2.0],
        }
    ).to_csv(path, index=False)

    summary = summarize_training_log(path)

    kl = summary["metrics"]["train/approx_kl"]
    assert kl["row_count"] == 4
    assert kl["finite_count"] == 2
    assert kl["missing_count"] == 1
    assert kl["positive_infinity_count"] == 1
    assert kl["first_finite_step"] == 16384
    assert kl["last_finite_step"] == 24576
    assert kl["median"] == pytest.approx(0.015)
    assert summary["metrics"]["train/entropy_loss"]["status"] == "missing_column"
    value_loss = summary["metrics"]["train/value_loss"]
    assert value_loss["nonnumeric_count"] == 1
    assert value_loss["finite_count"] == 3


def test_training_dynamics_report_is_hash_linked_and_repeatable(tmp_path: Path) -> None:
    path = tmp_path / "training_log.csv"
    pd.DataFrame(
        {
            "timestep": [1, 2, 3],
            "train/entropy_loss": [-2.0, -1.0, -0.5],
        }
    ).to_csv(path, index=False)

    report = build_report([("arm_a", path)])
    serialized = json.loads(json.dumps(report))
    arm = serialized["arms"]["arm_a"]

    assert serialized["evidence_class"] == "descriptive_training_telemetry"
    assert serialized["thresholds_applied"] is False
    assert len(arm["source_sha256"]) == 64
    assert arm["row_count"] == 3
    assert arm["step_min"] == 1
    assert arm["step_max"] == 3
    assert arm["metrics"]["train/entropy_loss"]["median"] == pytest.approx(-1.0)


def test_training_dynamics_report_requires_unique_existing_inputs(tmp_path: Path) -> None:
    path = tmp_path / "training_log.csv"
    pd.DataFrame({"timestep": [1]}).to_csv(path, index=False)

    with pytest.raises(ValueError, match="unique"):
        build_report([("arm", path), ("arm", path)])
    with pytest.raises(FileNotFoundError, match="missing"):
        build_report([("missing", tmp_path / "not_found.csv")])
