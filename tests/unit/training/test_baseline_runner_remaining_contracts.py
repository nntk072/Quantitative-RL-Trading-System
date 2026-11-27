"""MACD baseline runner contracts without data or backtest execution."""

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


def test_development_macd_uses_aligned_actions_and_exit_semantics(
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
            "execution": {},
            "session": {"tz": "UTC"},
            "trading_policy": {"daily_loss_reset_source": "utc_midnight"},
        }
    )
    index = pd.date_range("2025-12-01 16:30", periods=4, freq="min", tz="UTC")
    bars = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [101.0, 102.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0, 102.0],
            "close": [100.5, 101.5, 102.5, 103.5],
        },
        index=index,
    )
    features = pd.DataFrame({"close": bars["close"]}, index=index)
    actions = pd.Series([0, 0, 2, 1], index=index, dtype=int)
    captured: dict[str, Any] = {}

    monkeypatch.setattr(baselines, "load_config", lambda _overrides: cfg)
    monkeypatch.setattr(baselines, "get_split_config", lambda _cfg: ("2025-12-01", "2025-12-02"))
    monkeypatch.setattr(baselines, "get_train_start_config", lambda _cfg: "2025-12-01")
    monkeypatch.setattr(
        baselines,
        "run_pipeline",
        lambda *_args, **_kwargs: {"PRIMARY": {"M1": bars}},
    )
    monkeypatch.setattr(
        baselines, "split_bars", lambda frame, *_args, **_kwargs: (frame, frame.iloc[:0])
    )
    monkeypatch.setattr(
        baselines, "build_split_scoped_features", lambda *_args, **_kwargs: features
    )
    monkeypatch.setattr(
        baselines,
        "split_train_test",
        lambda frame, feature_frame, *_args: (
            frame,
            frame.iloc[:0],
            feature_frame,
            feature_frame.iloc[:0],
        ),
    )
    monkeypatch.setattr(baselines, "build_tick_books", lambda *_args, **_kwargs: {})

    def fake_macd(frame: pd.DataFrame) -> pd.Series:
        captured["bars"] = frame
        return actions

    monkeypatch.setattr(baselines, "macd_ema50_baseline", fake_macd)
    monkeypatch.setattr(
        baselines, "resolve_trading_policy", lambda _cfg: SimpleNamespace(daily_pnl_basis="utc")
    )
    monkeypatch.setattr(baselines, "cost_model", lambda _cfg: "cost-model")
    monkeypatch.setattr(baselines, "eval_guardrail_kwargs", lambda _cfg: {})

    def fake_backtest(**kwargs: Any) -> dict[str, object]:
        policy = kwargs["policy"]
        emitted = [policy(np.zeros((1, 1), dtype=np.float32)) for _ in range(4)]
        captured["backtest"] = kwargs
        captured["actions"] = emitted
        return {"equity": pd.Series([100_000.0]), "trades": pd.DataFrame()}

    monkeypatch.setattr(baselines, "run_backtest", fake_backtest)
    monkeypatch.setattr(
        baselines,
        "calculate_metrics",
        lambda *_args, **_kwargs: SimpleNamespace(
            sharpe=0.0, max_drawdown=0.0, n_trades=0, total_return_pct=0.0
        ),
    )
    monkeypatch.setattr(baselines, "account_path_metric_inputs", lambda _result: {})
    monkeypatch.setattr(
        baselines, "save_run", lambda **_kwargs: pytest.fail("--no-save must skip save_run")
    )
    monkeypatch.setattr(np.random, "seed", lambda _seed: None)
    monkeypatch.setattr(sys, "argv", ["baselines", "--strategy", "macd", "--no-save"])

    baselines.main()

    assert captured["bars"] is bars
    assert captured["actions"] == [2, 1, 0, 0]
    assert captured["backtest"]["hold_on_zero"] is True
    assert captured["backtest"]["exit_action"] == 2
    assert captured["backtest"]["max_loss_per_trade_usd"] is None
