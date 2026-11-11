from __future__ import annotations

from typing import Any

import pandas as pd
import pytest
from scripts.research.analysis.evaluation import run_matched_setup_baselines as matched_baselines
from scripts.research.analysis.evaluation.run_matched_setup_baselines import (
    _additional_policies,
    _clip_frames_to_development_end,
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


def test_development_baseline_inputs_drop_report_only_rows_before_feature_build() -> None:
    bars, _ = _inputs()

    clipped = _clip_frames_to_development_end({"M1": bars}, train_end="2025-01-04")

    assert clipped["M1"].index.equals(bars.index[:4])


def test_development_baseline_input_path_clips_sentinel_before_features(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    cfg = load_config(config_path="config/research/trade_setup_mtf_reasoning_2m.yaml")
    primary = str(cfg.data.primary)
    secondary = str(cfg.data.secondary)
    index = pd.DatetimeIndex(["2025-12-31 14:30", "2026-01-01 14:30"])
    bars = pd.DataFrame({"close": [100.0, 900_001.0]}, index=index)
    observed: dict[str, Any] = {}
    tickbook = object()

    def fake_run_pipeline(
        _cfg, *, datasets: list[str], end_inclusive: str | None
    ) -> dict[str, dict[str, pd.DataFrame]]:
        observed["bar_cutoff"] = end_inclusive
        assert datasets == ["training"]
        return {
            primary: {"M1": bars.copy()},
            secondary: {"M1": bars.copy()},
        }

    def fake_build_features(primary_m1: pd.DataFrame, **_kwargs: object) -> pd.DataFrame:
        observed["feature_input"] = primary_m1.copy()
        return pd.DataFrame({"feature": primary_m1["close"]}, index=primary_m1.index)

    def fake_tick_books(_cfg, **kwargs: object) -> dict[str, object]:
        observed["tick_cutoff"] = kwargs.get("end_inclusive")
        return {primary: tickbook}

    monkeypatch.setattr(matched_baselines, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(matched_baselines, "build_features", fake_build_features)
    monkeypatch.setattr(
        matched_baselines,
        "feature_cache_path",
        lambda *_args, **_kwargs: tmp_path / "features.parquet",
    )
    monkeypatch.setattr(matched_baselines, "build_tick_books", fake_tick_books)
    monkeypatch.setattr(
        matched_baselines,
        "attach_policy_market_context",
        lambda _bars, features, *_args, **_kwargs: features,
    )
    monkeypatch.setattr(
        matched_baselines, "_source_files", lambda *_args, **_kwargs: {"config": tmp_path}
    )

    selected_bars, selected_features, selected_ticks, _sources = matched_baselines._prepare_inputs(
        cfg,
        dataset_name="training",
        period_role="development",
        config_path=tmp_path / "config.yaml",
    )

    assert observed["bar_cutoff"] == "2025-12-31"
    assert observed["tick_cutoff"] == "2025-12-31"
    assert observed["feature_input"].index.equals(index[:1])
    assert observed["feature_input"]["close"].tolist() == [100.0]
    assert selected_bars.index.equals(index[:1])
    assert selected_features.index.equals(index[:1])
    assert selected_ticks is tickbook


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
    cfg = load_config(
        [
            "env.strategy_actions=true",
            "env.trade_setup_actions=true",
            "ppo.policy_distribution=trade_setup_hybrid_v1",
        ]
    )

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


def test_structure_priority_baseline_uses_configured_entry_execution_schema() -> None:
    cfg = load_config(
        [
            "env.strategy_actions=true",
            "env.trade_setup_actions=true",
            "env.agent_entry_execution=true",
            "ppo.policy_distribution=trade_setup_hybrid_v1",
        ]
    )

    policies = _additional_policies(
        cfg,
        include_structure_priority=True,
        normalized_risk=0.5,
    )

    arm = policies["structure_priority"]
    assert "entry_execution" in arm.model.hybrid_action_coordinates
    assert arm.model.policy_metadata["entry_execution"] == "market"


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
