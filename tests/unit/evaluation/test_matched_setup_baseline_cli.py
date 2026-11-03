from __future__ import annotations

import pandas as pd
import pytest
from scripts.research.analysis.evaluation.run_matched_setup_baselines import (
    _additional_policies,
    parse_args,
    select_period,
)

from configuration.configuration_loader import load_config
from decisioning.trade_setup import TRADE_SETUP_IDEAS, TRADE_SETUP_TIMEFRAMES
from evaluation.rollout.matched_setup_baselines import RuleSetupBaselineArm
from evaluation.rollout.structure_priority_setup import StructurePrioritySetupRolloutModel


def _inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    index = pd.date_range("2025-01-01", periods=6, freq="D", tz="Etc/GMT-3")
    bars = pd.DataFrame({"close": range(6)}, index=index)
    features = pd.DataFrame({"feature": range(6)}, index=index)
    return bars, features


def test_period_selection_uses_declared_development_bounds() -> None:
    cfg = load_config(
        [
            "data.split.train_start=2025-01-02",
            "data.split.train_end=2025-01-04",
            "data.split.test_start=2025-01-05",
        ]
    )
    bars, features = _inputs()

    selected_bars, selected_features = select_period(bars, features, cfg, "development")

    assert selected_bars.index.equals(bars.index[1:4])
    assert selected_features.index.equals(selected_bars.index)


def test_period_selection_labels_exposed_report_split_explicitly() -> None:
    cfg = load_config(
        [
            "data.split.train_start=2025-12-30",
            "data.split.train_end=2025-12-31",
            "data.split.test_start=2026-01-01",
        ]
    )
    index = pd.DatetimeIndex(
        [
            "2025-12-31 23:59",
            "2026-01-01 00:00",
            "2026-10-16 23:59",
            "2026-10-17 00:00",
        ],
        tz="Etc/GMT-3",
    )
    bars = pd.DataFrame({"close": range(len(index))}, index=index)
    features = pd.DataFrame({"feature": range(len(index))}, index=index)

    selected_bars, selected_features = select_period(bars, features, cfg, "exposed_report_only")

    assert selected_bars.index.equals(bars.index[1:3])
    assert selected_features.index.equals(selected_bars.index)


def test_period_selection_rejects_unknown_role_and_empty_split() -> None:
    cfg = load_config(
        [
            "data.split.train_start=2025-01-01",
            "data.split.train_end=2025-01-03",
            "data.split.test_start=2025-01-04",
        ]
    )
    bars, features = _inputs()

    with pytest.raises(ValueError, match="period_role must be"):
        select_period(bars, features, cfg, "synthetic")
    with pytest.raises(ValueError, match="split is empty"):
        select_period(bars.iloc[:3], features.iloc[:3], cfg, "exposed_report_only")


def test_cli_requires_an_explicit_period_role() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--config", "config/base/default.yaml"])


def test_cli_opts_into_fixed_structure_priority_rule() -> None:
    cfg = load_config([])

    assert (
        _additional_policies(
            cfg,
            include_structure_priority=False,
            normalized_risk=0.5,
        )
        == {}
    )
    policies = _additional_policies(
        cfg,
        include_structure_priority=True,
        normalized_risk=0.25,
    )

    assert set(policies) == {"structure_priority"}
    arm = policies["structure_priority"]
    assert isinstance(arm, RuleSetupBaselineArm)
    assert isinstance(arm.model, StructurePrioritySetupRolloutModel)
    metadata = arm.model.policy_metadata
    assert metadata["baseline_tier"] == "tier_1_deterministic_structure_rule"
    assert metadata["idea_priority"] == list(TRADE_SETUP_IDEAS)
    assert metadata["timeframe_priority"] == list(TRADE_SETUP_TIMEFRAMES)
    assert metadata["normalized_risk"] == 0.25
    assert metadata["training_performed"] is False
    assert metadata["selection_or_tuning_performed"] is False


def test_structure_priority_cli_flag_is_opt_in() -> None:
    base = [
        "--config",
        "config/base/default.yaml",
        "--period-role",
        "development",
        "--execution-seed",
        "1",
        "--random-policy-seed",
        "2",
        "--absolute-risk-budget-usd",
        "250",
    ]

    assert parse_args(base).include_structure_priority is False
    assert parse_args([*base, "--include-structure-priority"]).include_structure_priority is True
