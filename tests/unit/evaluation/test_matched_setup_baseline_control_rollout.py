"""Standard matched setup controls share the same evaluation inputs."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

from decisioning.trade_setup import build_trade_setup_action_schema
from evaluation.reporting.run_manifest import dataframe_sha256
from evaluation.rollout import matched_setup_baselines


def test_standard_controls_use_fresh_environments_and_record_shared_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg: dict[str, Any] = {
        "env": {"strategy_actions": True, "trade_setup_actions": True},
        "account": {"initial_balance": 100.0},
    }
    index = pd.date_range("2025-02-03 15:00", periods=2, freq="min", tz="UTC")
    bars = pd.DataFrame({"close": [100.0, 100.5]}, index=index)
    features = pd.DataFrame({"signal": [0.0, 0.5]}, index=index)
    decisions = pd.DataFrame({"trade_setup": [0, 1]}, index=index)
    trades = pd.DataFrame(columns=["type", "time", "pnl"])
    equity = np.asarray([100.0, 100.5], dtype=np.float64)
    schema = build_trade_setup_action_schema()
    environments: list[dict[str, Any]] = []
    rollouts: list[dict[str, Any]] = []

    class SyntheticEnvironment:
        def __init__(
            self,
            bars: pd.DataFrame,
            features: pd.DataFrame,
            *,
            episodic: bool,
            tickbook: Any,
        ) -> None:
            self.action_schema = schema
            environments.append(
                {"bars": bars, "features": features, "episodic": episodic, "tickbook": tickbook}
            )

    def evaluate_model(
        model: Any,
        received_bars: pd.DataFrame,
        received_features: pd.DataFrame,
        *,
        env: Any,
        tickbook: Any,
        execution_seed: int,
        strategy_actions: bool,
        trade_setup_actions: bool,
        deterministic: bool,
    ) -> dict[str, Any]:
        rollouts.append(
            {
                "model": model,
                "bars": received_bars,
                "features": received_features,
                "env": env,
                "tickbook": tickbook,
                "execution_seed": execution_seed,
                "strategy_actions": strategy_actions,
                "trade_setup_actions": trade_setup_actions,
                "deterministic": deterministic,
            }
        )
        return {
            "equity": equity,
            "trades": trades,
            "trade_setup_decisions": decisions,
            "n_sessions": 1,
            "n_breach_sessions": 0,
            "n_steps": len(bars),
            "exposure_bars": 0,
            "exposure_fraction": 0.0,
            "breach_events": [],
            "completed_data_split": True,
            "episode_end_reason": "data_end",
        }

    metric_values = SimpleNamespace(total_return_pct=0.5, n_trades=0)
    interval = SimpleNamespace(estimate=0.5, lower=0.0, upper=1.0, level=0.95)
    monkeypatch.setattr(
        matched_setup_baselines,
        "build_eval_common",
        lambda *_args, **_kwargs: ({"initial_balance": 100.0}, None, None, None, None),
    )
    monkeypatch.setattr(matched_setup_baselines, "cost_model", lambda _cfg: None)
    monkeypatch.setattr(matched_setup_baselines, "TradingEnv", SyntheticEnvironment)
    monkeypatch.setattr(matched_setup_baselines, "evaluate_model", evaluate_model)
    monkeypatch.setattr(
        matched_setup_baselines, "calculate_metrics", lambda *_args, **_kwargs: metric_values
    )
    monkeypatch.setattr(matched_setup_baselines, "account_path_metric_inputs", lambda _raw: {})
    monkeypatch.setattr(matched_setup_baselines, "pair_trades", lambda _trades: [])
    monkeypatch.setattr(
        matched_setup_baselines, "metrics_with_ci", lambda *_args, **_kwargs: {"return": interval}
    )

    outputs = matched_setup_baselines.evaluate_tier0_setup_baselines(
        cfg,
        bars,
        features,
        None,
        execution_seed=13,
        random_policy_seed=17,
        period_role="synthetic",
        tick_fill_slippage_points=0.0,
        bootstrap_samples=4,
        baseline_names=("always_no_trade", "random_eligible_setup"),
    )

    assert set(outputs) == {"always_no_trade", "random_eligible_setup"}
    assert len(environments) == len(rollouts) == 2
    assert environments[0]["bars"] is bars and environments[1]["bars"] is bars
    assert all(environment["episodic"] is False for environment in environments)
    assert rollouts[0]["env"] is not rollouts[1]["env"]
    assert all(call["bars"] is bars and call["features"] is features for call in rollouts)
    assert all(call["execution_seed"] == 13 for call in rollouts)
    assert all(call["strategy_actions"] and call["trade_setup_actions"] for call in rollouts)
    assert all(call["deterministic"] for call in rollouts)
    assert outputs["always_no_trade"]["policy_metadata"]["random_policy_seed"] is None
    random_metadata = outputs["random_eligible_setup"]["policy_metadata"]
    assert random_metadata["random_policy_seed"] == 17
    assert random_metadata["input_hashes"]["bars"] == dataframe_sha256(bars)
    assert outputs["random_eligible_setup"]["decisions"] is decisions
    assert outputs["always_no_trade"]["metrics"] is metric_values
    assert outputs["always_no_trade"]["confidence_intervals"]["metrics"]["return"] == {
        "estimate": 0.5,
        "lower": 0.0,
        "upper": 1.0,
        "level": 0.95,
    }
