"""Tests for the baseline strategy runner (``training.runner.baselines``).

Specifically covers the new ``_make_indexed_policy`` and the real indicator
precomputation that the EMA / RSI baselines now use instead of the legacy
returns-heuristic placeholder. The contract under test is:

- ``_make_indexed_policy(actions, obs_window)`` returns a callable that
  emits ``actions.iloc[i]`` for the ``i``-th call, starting at
  ``obs_window`` (so the absolute bar index in ``run_backtest`` lines up
  with the precomputed action series).
- The policy advances its internal index exactly once per call, and
  past-the-end calls fall back to ``0`` (flat) instead of raising.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest
from omegaconf import OmegaConf

from training.runner import baselines
from training.runner.baselines import _make_indexed_policy


def _make_bars(n: int = 60, trend: float = 0.5) -> pd.DataFrame:
    """Synthetic OHLCV bars with DatetimeIndex — shared with the runner."""
    rng = np.random.default_rng(42)
    close = 20_000.0 + np.cumsum(rng.normal(trend, 2.0, n))
    index = pd.date_range("2025-01-02 16:30", periods=n, freq="5min")
    return pd.DataFrame(
        {
            "open": close + rng.normal(0, 1.0, n),
            "high": close + rng.uniform(1.0, 3.0, n),
            "low": close - rng.uniform(1.0, 3.0, n),
            "close": close,
            "volume": rng.uniform(900, 1_100, n),
        },
        index=index,
    )


def test_make_indexed_policy_starts_at_obs_window() -> None:
    """First emitted action must be ``actions.iloc[obs_window]``."""
    actions = pd.Series([0, 0, 0, 1, 1, 0, -1, 0, 0], dtype=int)
    policy = _make_indexed_policy(actions, obs_window=3)
    dummy_obs = np.zeros((1, 1), dtype=np.float32)

    first = policy(dummy_obs)
    assert first == 1  # actions.iloc[3]


def test_make_indexed_policy_advances_one_per_call() -> None:
    """Successive calls must return successive actions from the series."""
    actions = pd.Series([0, 0, 0, 1, -1, 1, 0, -1, 0], dtype=int)
    policy = _make_indexed_policy(actions, obs_window=2)
    dummy_obs = np.zeros((1, 1), dtype=np.float32)

    # First call: actions.iloc[2] = 0 (warmup region).
    # Then the EMA crosses / RSI flips we encoded at indices 3..7.
    emitted = [policy(dummy_obs) for _ in range(6)]
    assert emitted == [0, 1, -1, 1, 0, -1]


def test_make_indexed_policy_past_end_returns_flat() -> None:
    """When the index walks past the end, the policy must yield 0 (flat)."""
    actions = pd.Series([1] * 5, dtype=int)
    policy = _make_indexed_policy(actions, obs_window=2)
    dummy_obs = np.zeros((1, 1), dtype=np.float32)

    for _ in range(3):
        assert policy(dummy_obs) == 1
    # Two more calls land past the end → must fall back to 0, never raise.
    assert policy(dummy_obs) == 0
    assert policy(dummy_obs) == 0


def test_make_indexed_policy_ignores_obs_argument() -> None:
    """The runner never inspects the obs; the closure owns the index."""
    actions = pd.Series([0, 0, 0, 0, 1, 0], dtype=int)
    policy = _make_indexed_policy(actions, obs_window=4)
    sentinel_obs = np.full((10, 5), 99.0, dtype=np.float32)

    assert policy(sentinel_obs) == 1  # still actions.iloc[4]


def test_main_development_ema_flow_uses_training_data_and_forwards_cli_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = OmegaConf.create(
        {
            "evaluation": {"development_only": True},
            "data": {
                "primary": "PRIMARY",
                "secondary": "SECONDARY",
                "cache_dir": str(tmp_path / "cache"),
                "tz": "UTC",
                "timestamp_clock": "native",
            },
            "env": {"obs_window": 2, "eod_risk": {}, "sl_buffer_pts": 0.0},
            "account": {"initial_balance": 100_000.0, "contract_size": 1.0},
            "risk": {
                "default_risk_frac": 0.01,
                "rr_ratio_default": 2.0,
                "swing_buffer_pts": 1.0,
                "max_lot": 10.0,
                "min_lot": 0.01,
                "lot_step": 0.01,
                "sl_mode": "fixed",
            },
            "backtest": {"validation": {"max_loss_per_trade_usd": 500.0}},
            "costs": {"use_tick_execution": False},
            "execution": {
                "server_side_protective_orders": False,
                "fill_latency_bars": 0,
                "randomized_fill_latency_ms": 0.0,
                "max_tick_quote_wait_ms": 60_000,
            },
            "session": {"tz": "UTC"},
            "trading_policy": {"daily_loss_reset_source": "utc_midnight"},
        }
    )
    bars = _make_bars(6)
    features = pd.DataFrame({"close": bars["close"]}, index=bars.index)
    actions = pd.Series([0, 0, -1, 1, 0, 0], index=bars.index, dtype=int)
    captured: dict[str, Any] = {"backtests": []}

    def fake_load_config(overrides: list[str]) -> Any:
        captured["overrides"] = overrides
        return cfg

    def fake_run_pipeline(
        config: object, *, force: bool, end_inclusive: str | None = None
    ) -> dict[str, dict[str, pd.DataFrame]]:
        captured["pipeline"] = (config, force, end_inclusive)
        return {"PRIMARY": {"M1": bars}}

    def fake_split_bars(
        data: pd.DataFrame, *args: object, **kwargs: object
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        captured["development_split"] = (args, kwargs)
        return data, data.iloc[:0]

    def fake_feature_build(data: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
        captured["feature_build"] = (data, kwargs)
        return features

    def fake_split_train_test(
        bar_data: pd.DataFrame,
        feature_data: pd.DataFrame,
        *args: object,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        captured["split_inputs"] = (bar_data, feature_data, args)
        return bar_data, bar_data.iloc[:0], feature_data, feature_data.iloc[:0]

    def fake_run_backtest(**kwargs: Any) -> dict[str, object]:
        policy = kwargs["policy"]
        assert callable(policy)
        action = policy(np.zeros((1, 1), dtype=np.float32))
        captured["backtests"].append((kwargs, action))
        return {"equity": pd.Series([100_000.0]), "trades": pd.DataFrame()}

    monkeypatch.setattr(baselines, "load_config", fake_load_config)
    monkeypatch.setattr(baselines, "get_split_config", lambda config: ("2025-01-03", "2025-01-04"))
    monkeypatch.setattr(baselines, "get_train_start_config", lambda config: "2025-01-02")
    monkeypatch.setattr(baselines, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(baselines, "split_bars", fake_split_bars)
    monkeypatch.setattr(baselines, "build_split_scoped_features", fake_feature_build)
    monkeypatch.setattr(baselines, "split_train_test", fake_split_train_test)
    monkeypatch.setattr(baselines, "build_tick_books", lambda *args, **kwargs: {})
    monkeypatch.setattr(baselines, "ema_crossover", lambda data, *, fast, slow: actions)
    monkeypatch.setattr(
        baselines, "resolve_trading_policy", lambda config: SimpleNamespace(daily_pnl_basis="utc")
    )
    monkeypatch.setattr(baselines, "cost_model", lambda config: "cost-model")
    monkeypatch.setattr(
        baselines, "eval_guardrail_kwargs", lambda config: {"daily_loss_limit": 100}
    )
    monkeypatch.setattr(baselines, "run_backtest", fake_run_backtest)
    monkeypatch.setattr(
        baselines,
        "calculate_metrics",
        lambda *args, **kwargs: SimpleNamespace(
            sharpe=1.0, max_drawdown=0.1, n_trades=1, total_return_pct=2.0
        ),
    )
    monkeypatch.setattr(baselines, "account_path_metric_inputs", lambda result: {})
    monkeypatch.setattr(
        baselines, "save_run", lambda **kwargs: pytest.fail("--no-save must skip save_run")
    )
    seeded: list[int] = []
    monkeypatch.setattr(np.random, "seed", seeded.append)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "baselines",
            "--strategy",
            "ema",
            "--seed",
            "19",
            "--force",
            "--no-save",
            "--out",
            str(tmp_path / "outputs"),
            "sentinel.override=true",
        ],
    )

    baselines.main()

    assert seeded == [19]
    assert captured["overrides"] == ["sentinel.override=true"]
    assert captured["pipeline"] == (cfg, True, "2025-01-03")
    assert len(captured["backtests"]) == 1
    backtest_kwargs, first_action = captured["backtests"][0]
    assert first_action == -1  # EMA action at the configured observation window.
    assert backtest_kwargs["hold_on_zero"] is False
    assert backtest_kwargs["exit_action"] is None
    assert backtest_kwargs["daily_pnl_basis"] == "utc"
    assert backtest_kwargs["use_structure_sl_tp"] is False


def test_main_rejects_policy_without_daily_pnl_basis_before_loading_market_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = OmegaConf.create({"evaluation": {"development_only": False}})
    called = False

    def fail_pipeline(*args: object, **kwargs: object) -> object:
        nonlocal called
        called = True
        raise AssertionError("market data must not load without a daily PnL basis")

    monkeypatch.setattr(baselines, "load_config", lambda overrides: cfg)
    monkeypatch.setattr(
        baselines, "resolve_trading_policy", lambda config: SimpleNamespace(daily_pnl_basis=None)
    )
    monkeypatch.setattr(baselines, "run_pipeline", fail_pipeline)
    monkeypatch.setattr(sys, "argv", ["baselines"])

    with pytest.raises(ValueError, match="must define a daily PnL basis"):
        baselines.main()

    assert called is False
