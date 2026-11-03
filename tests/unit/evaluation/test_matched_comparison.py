from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from evaluation.metrics.matched_comparison import paired_equity_metric_differences
from evaluation.reporting.matched_setup_baseline_bundle import _paired_interval_record

ROOT = Path(__file__).resolve().parents[3]


def test_paired_equity_metric_intervals_use_shared_bar_timestamps() -> None:
    index = pd.date_range("2025-01-01", periods=5, freq="min", tz="UTC")
    treatment = pd.Series([100.0, 102.0, 101.0, 103.0, 104.0], index=index)
    control = pd.Series([100.0, 101.0, 100.0, 101.0, 102.0], index=index)

    intervals = paired_equity_metric_differences(
        treatment,
        control,
        initial_balance=100.0,
        periods_per_year=100,
        n_boot=50,
        rng_seed=17,
        block_len=2,
    )

    assert set(intervals) == {"mean_bar_return", "sharpe", "sortino", "max_drawdown"}
    assert intervals["mean_bar_return"].estimate == pytest.approx(
        np.mean(np.diff(treatment.to_numpy()) / treatment.to_numpy()[:-1])
        - np.mean(np.diff(control.to_numpy()) / control.to_numpy()[:-1])
    )
    assert intervals["max_drawdown"].estimate < 0.0
    assert all(interval.level == 0.95 for interval in intervals.values())


def test_paired_equity_metric_intervals_reject_unaligned_timestamps() -> None:
    treatment = pd.Series(
        [100.0, 101.0, 102.0],
        index=pd.date_range("2025-01-01", periods=3, freq="min", tz="UTC"),
    )
    control = pd.Series(
        [100.0, 101.0, 102.0],
        index=pd.date_range("2025-01-01 00:01", periods=3, freq="min", tz="UTC"),
    )

    with pytest.raises(ValueError, match="indexes must match exactly"):
        paired_equity_metric_differences(
            treatment,
            control,
            initial_balance=100.0,
            periods_per_year=100,
            n_boot=10,
        )


def test_paired_bundle_interval_record_matches_manifest_schema() -> None:
    index = pd.date_range("2025-01-01", periods=4, freq="min", tz="UTC")
    protocol = {
        "n_boot": 20,
        "level": 0.95,
        "seed": 5,
        "block_length_bars": 2,
    }
    outputs = {
        "treatment": {
            "equity": pd.Series([100.0, 101.0, 100.5, 102.0], index=index),
            "policy_metadata": {"confidence_interval_protocol": protocol},
        },
        "control": {
            "equity": pd.Series([100.0, 100.5, 100.2, 100.8], index=index),
            "policy_metadata": {"confidence_interval_protocol": protocol},
        },
    }

    record = _paired_interval_record(
        outputs,
        "treatment",
        "control",
        {"account": {"initial_balance": 100.0}, "evaluation": {"periods_per_year": 100}},
    )
    schema = json.loads(
        (ROOT / "schemas/research_result_manifest_v2.schema.json").read_text(encoding="utf-8")
    )

    paired_schema = {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        **schema["$defs"]["pairedTimeSeriesConfidenceIntervals"],
    }
    Draft202012Validator(paired_schema).validate(record)
    assert record["schema"] == "paired_matched_bar_metric_ci_v2"
    assert record["status"] == "estimated"


def test_paired_bundle_interval_record_reports_insufficient_returns() -> None:
    index = pd.date_range("2025-01-01", periods=2, freq="min", tz="UTC")
    protocol = {"n_boot": 20, "level": 0.95, "seed": 5, "block_length_bars": 2}
    outputs = {
        name: {
            "equity": pd.Series([100.0, 100.0], index=index),
            "policy_metadata": {"confidence_interval_protocol": protocol},
        }
        for name in ("treatment", "control")
    }

    record = _paired_interval_record(
        outputs,
        "treatment",
        "control",
        {"account": {"initial_balance": 100.0}, "evaluation": {"periods_per_year": 100}},
    )
    schema = json.loads(
        (ROOT / "schemas/research_result_manifest_v2.schema.json").read_text(encoding="utf-8")
    )
    paired_schema = {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        **schema["$defs"]["pairedTimeSeriesConfidenceIntervals"],
    }

    Draft202012Validator(paired_schema).validate(record)
    assert record["schema"] == "paired_matched_bar_metric_ci_v2"
    assert record["status"] == "not_estimable"
    assert record["paired_return_observations"] == 1
    assert record["reason"] == "paired bootstrap requires at least two aligned bar returns"
    assert record["metrics"] == {}


def test_paired_bundle_rejects_misaligned_paths_when_interval_is_not_estimable() -> None:
    treatment_index = pd.date_range("2025-01-01", periods=2, freq="min", tz="UTC")
    control_index = pd.date_range("2025-01-01 00:01", periods=2, freq="min", tz="UTC")
    protocol = {"n_boot": 20, "level": 0.95, "seed": 5, "block_length_bars": 2}
    outputs = {
        "treatment": {
            "equity": pd.Series([100.0, 100.0], index=treatment_index),
            "policy_metadata": {"confidence_interval_protocol": protocol},
        },
        "control": {
            "equity": pd.Series([100.0, 100.0], index=control_index),
            "policy_metadata": {"confidence_interval_protocol": protocol},
        },
    }

    with pytest.raises(ValueError, match="indexes must match exactly"):
        _paired_interval_record(
            outputs,
            "treatment",
            "control",
            {"account": {"initial_balance": 100.0}, "evaluation": {"periods_per_year": 100}},
        )
