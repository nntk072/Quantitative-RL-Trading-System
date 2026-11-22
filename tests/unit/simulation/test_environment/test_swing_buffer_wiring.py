"""Regression coverage for configured swing-stop buffer propagation."""

from __future__ import annotations

import pandas as pd
import pytest

from simulation.environment.env import TradingEnv


def test_legacy_entry_uses_swing_buffer_points() -> None:
    index = pd.date_range("2020-06-01T13:30:00Z", periods=6, freq="1min")
    bars = pd.DataFrame(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "spread": 0.0,
            "session_id": 1,
            "session": "ny",
        },
        index=index,
    )
    features = pd.DataFrame(
        {"last_swing_low": 97.0, "last_swing_high": 103.0},
        index=index,
    )
    env = TradingEnv(
        bars,
        features,
        obs_window=1,
        swing_buffer_pts=1.5,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        max_loss_per_trade_usd=1_000.0,
        block_overnight=False,
    )
    env.reset(seed=7)

    opened = False
    for _ in range(4):
        _, _, terminated, truncated, _ = env.step(1)
        if env.position is not None:
            opened = True
            break
        if terminated or truncated:
            break

    assert opened
    assert env.position is not None
    assert env.position.sl_price == pytest.approx(95.5)
    assert env.position.tp_price == pytest.approx(104.5)
