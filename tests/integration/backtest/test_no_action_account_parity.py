"""No-action account parity for environment and event-driven backtest."""

from __future__ import annotations

import numpy as np
import pandas as pd

from market_data.loading.ticks import TickBook
from simulation.backtest import run_backtest
from simulation.environment.env import TradingEnv
from trading.execution import CostModel


def test_no_action_preserves_account_state_without_tick_quotes() -> None:
    index = pd.date_range("2025-01-06 14:00", periods=6, freq="1min", tz="UTC")
    bars = pd.DataFrame(
        {
            "open": 100.0,
            "high": 100.1,
            "low": 99.9,
            "close": 100.0,
            "spread": 0.0,
            "session_id": 0,
            "session": "ny",
        },
        index=index,
    )
    features = pd.DataFrame(index=index)
    cost_model = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0)
    empty_tickbook = TickBook(
        np.asarray([], dtype=np.int64),
        np.asarray([], dtype=np.float64),
        np.asarray([], dtype=np.float64),
    )
    initial_balance = 100_000.0
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        initial_balance=initial_balance,
        cost_model=cost_model,
        guardrail_kwargs={
            "daily_loss_limit": 10_000.0,
            "max_loss_limit": 20_000.0,
            "risk_per_trade_limit": 10_000.0,
            "soft_daily_loss_limit": 0.0,
            "soft_max_loss_limit": 0.0,
        },
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        block_overnight=False,
    )
    env.reset(seed=7)

    for _ in range(len(bars) - 1):
        env.step(0)

    backtest = run_backtest(
        bars,
        features,
        lambda _observation: 0,
        obs_window=1,
        cost_model=cost_model,
        tickbook=empty_tickbook,
        randomized_fill_latency_ms=30.0,
        hold_on_zero=True,
        block_overnight=False,
    )

    assert not env.trade_log
    assert env.account.balance == initial_balance
    assert env.account.equity == initial_balance
    assert env.account.daily_loss == 0.0
    assert backtest["trades"].empty
    assert backtest["account"].balance == initial_balance
    assert backtest["account"].equity == initial_balance
    assert backtest["account"].daily_loss == 0.0
