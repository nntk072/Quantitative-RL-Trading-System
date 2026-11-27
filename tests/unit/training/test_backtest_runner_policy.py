from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from configuration import load_config
from simulation.environment.trading_environment_factory import cost_model
from trading.policy.config import TradingPolicyConfig
from training.runner import backtest as backtest_runner
from training.runner.backtest import _configured_backtest_policy


class _Section(dict[str, object]):
    def __getattr__(self, name: str) -> object:
        return self[name]

    def get(self, key: str, default: object = None) -> object:
        return super().get(key, default)


def test_configured_backtest_runner_resolves_static_daily_loss_semantics() -> None:
    cfg = load_config()

    policy = _configured_backtest_policy(cfg)
    assert policy.daily_pnl_basis == "session_net_equity"
    assert policy.daily_loss_includes_open_pnl
    assert policy.daily_loss_limit_pct == 0.05
    assert cost_model(cfg).slippage_points == float(cfg.costs.slippage_points) == 5.0
    assert not policy.repeated_payout


def test_configured_backtest_runner_resolves_repeated_payout_lifecycle() -> None:
    cfg = load_config(["trading_policy.mode=repeated_payout"])

    policy = _configured_backtest_policy(cfg)
    assert policy.repeated_payout
    assert policy.daily_pnl_basis == "session_net_equity"
    assert policy.operating_balance == cfg.account.initial_balance
    assert policy.max_agent_risk_frac < 0.01


def test_historical_dollar_daily_limit_is_normalized_to_initial_equity_fraction() -> None:
    policy = TradingPolicyConfig.from_mapping(
        {
            "operating_balance": 100_000.0,
            "daily_loss_limit": 5_000.0,
            "account_floor": 90_000.0,
        }
    )

    assert policy.daily_loss_limit_pct == 0.05
    assert policy.daily_loss_limit == 5_000.0
    assert policy.account_floor == 90_000.0


def test_account_lifecycle_mode_does_not_change_daily_loss_basis() -> None:
    policy = TradingPolicyConfig(mode="legacy").validate()

    assert policy.daily_pnl_basis == "session_net_equity"
    assert policy.daily_loss_includes_open_pnl


def test_backtest_main_runs_both_splits_and_saves_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bars = pd.DataFrame({"close": [100.0, 101.0]})
    secondary = pd.DataFrame({"close": [200.0, 201.0]})
    features = pd.DataFrame({"signal": [0.0, 1.0]})
    cfg = _Section(
        data=_Section(
            primary="US100",
            secondary="US500",
            cache_dir=str(tmp_path),
            tz="UTC",
        ),
        env=_Section(obs_window=2, eod_risk={}),
        account=_Section(initial_balance=1000.0, contract_size=1.0),
        risk=_Section(
            default_risk_frac=0.01,
            rr_ratio_default=2.0,
            swing_buffer_pts=1.0,
            min_lot=0.01,
            max_lot=1.0,
        ),
        costs=_Section(use_tick_execution=False),
        execution=_Section(
            randomized_fill_latency_ms=0,
            max_tick_quote_wait_ms=0,
        ),
        session=_Section(tz="UTC"),
        backtest=_Section(
            validation=_Section(
                max_loss_per_trade_usd=100.0,
                take_profit_per_trade_usd=200.0,
            )
        ),
    )
    calls: list[dict[str, object]] = []

    class TickBook:
        def slice(self, *_args: object) -> object:
            return object()

    monkeypatch.setattr(sys, "argv", ["backtest", "--seed", "17", "--out", str(tmp_path)])
    monkeypatch.setattr(backtest_runner, "load_config", lambda _overrides: cfg)
    monkeypatch.setattr(
        backtest_runner,
        "_configured_backtest_policy",
        lambda _cfg: SimpleNamespace(
            daily_pnl_basis="session_net_equity",
            repeated_payout=True,
            operating_balance=1000.0,
            max_agent_risk_frac=0.005,
        ),
    )
    monkeypatch.setattr(
        backtest_runner,
        "run_pipeline",
        lambda *_args, **_kwargs: {"US100": {"M1": bars}, "US500": {"M1": secondary}},
    )
    monkeypatch.setattr(
        backtest_runner, "get_split_config", lambda _cfg: ("2025-01-01", "2025-01-02")
    )
    monkeypatch.setattr(backtest_runner, "get_train_start_config", lambda _cfg: "2024-01-01")
    monkeypatch.setattr(
        backtest_runner, "build_split_scoped_features", lambda *_args, **_kwargs: features
    )
    monkeypatch.setattr(
        backtest_runner,
        "split_train_test",
        lambda *_args: (bars, bars, features, features),
    )
    monkeypatch.setattr(backtest_runner, "split_bars", lambda *_args: (secondary, secondary))
    monkeypatch.setattr(
        backtest_runner, "build_tick_books", lambda *_args, **_kwargs: {"US100": TickBook()}
    )
    monkeypatch.setattr(backtest_runner, "cost_model", lambda _cfg: object())
    monkeypatch.setattr(backtest_runner, "eval_guardrail_kwargs", lambda _cfg: {})
    monkeypatch.setattr(backtest_runner, "news_guard_config", lambda _cfg: None)
    monkeypatch.setattr(
        backtest_runner,
        "run_backtest",
        lambda **kwargs: run_backtest(kwargs),
    )

    def save_run(**kwargs: object) -> Path:
        saved.append(kwargs)
        return tmp_path / "run"

    def run_backtest(kwargs: dict[str, object]) -> dict[str, object]:
        calls.append(kwargs)
        return {
            "equity": [1000.0, 1010.0],
            "total_economic_value_curve": [1000.0, 1010.0],
            "trades": [],
            "n_sessions": 1,
            "n_breach_sessions": 0,
        }

    monkeypatch.setattr(
        backtest_runner,
        "calculate_metrics",
        lambda *_args, **_kwargs: SimpleNamespace(
            sharpe=0.0,
            max_drawdown=0.0,
            n_trades=0,
            total_return_pct=1.0,
        ),
    )
    monkeypatch.setattr(backtest_runner, "account_path_metric_inputs", lambda _result: {})
    saved: list[dict[str, object]] = []
    monkeypatch.setattr(
        backtest_runner,
        "save_run",
        save_run,
    )

    backtest_runner.main()

    assert len(calls) == 2
    assert calls[0]["execution_seed"] == calls[1]["execution_seed"] == 17
    assert calls[0]["daily_pnl_basis"] == "session_net_equity"
    assert calls[0]["max_loss_per_trade_usd"] == 5.0
    assert calls[0]["take_profit_per_trade_usd"] is None
    assert calls[0]["use_structure_sl_tp"] is True
    assert len(saved) == 1
    assert saved[0]["train_secondary"] is secondary
