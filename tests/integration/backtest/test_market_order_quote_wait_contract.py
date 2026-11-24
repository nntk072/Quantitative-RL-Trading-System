from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from market_data.loading.ticks import TickBook
from simulation.backtest import run_backtest
from trading.execution.costs import CostModel


@pytest.mark.parametrize("block_overnight", [False, True])
def test_market_order_wait_is_measured_from_order_submission_not_next_bar(
    block_overnight: bool,
) -> None:
    index = pd.DatetimeIndex(
        [
            "2025-12-02T14:29:00Z",
            "2025-12-02T14:30:00Z",
            "2025-12-02T14:32:00Z",
            "2025-12-02T14:33:00Z",
            "2025-12-02T14:34:00Z",
            "2025-12-02T14:35:00Z",
            "2025-12-02T14:36:00Z",
        ]
    )
    bars = pd.DataFrame(
        {
            "open": [100.0] * len(index),
            "high": [101.0] * len(index),
            "low": [99.0] * len(index),
            "close": [100.0] * len(index),
            "spread": [0.25] * len(index),
            "session_id": [0] * len(index),
            "session": ["london", "ny", "ny", "ny", "ny", "ny", "ny"],
        },
        index=index,
    )
    features = pd.DataFrame(
        {"last_swing_low": [99.0] * len(index), "last_swing_high": [101.0] * len(index)},
        index=index,
    )
    # The market order is submitted at 14:31 UTC. The first tick is at 14:32:12.064,
    # 72.064 seconds later; another tick allows the rest of the trace to finish if
    # the entry path incorrectly ignores its 60-second order-arrival cap.
    tick_times = pd.DatetimeIndex(["2025-12-02T14:32:12.064Z"]).append(
        pd.date_range("2025-12-02T14:33:00.065Z", periods=20, freq="1min")
    )
    tickbook = TickBook(
        tick_times.to_numpy(dtype="datetime64[ns]").astype(np.int64),
        np.asarray([100.0] * len(tick_times)),
        np.asarray([100.25] * len(tick_times)),
    )
    calls = 0

    def policy(_observation: object) -> int:
        nonlocal calls
        calls += 1
        return 1 if calls == 1 else 0

    result = run_backtest(
        bars,
        features,
        policy,
        obs_window=1,
        initial_balance=50_000.0,
        cost_model=CostModel(spread_points=0.25, point_size=0.25),
        risk_frac=0.001,
        policy_risk_frac_range=(0.001, 0.001),
        rr_ratio=1.0,
        policy_rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        tickbook=tickbook,
        tick_execution_required=True,
        max_tick_quote_wait_ms=60_000,
        randomized_fill_latency_ms=0.0,
        block_overnight=block_overnight,
        open_manipulation_bars=0,
        hold_on_zero=True,
    )
    # The first tick is beyond the 60 s cap from submission, so the order is refused
    # rather than filled at that late tick.
    trades = result["trades"]
    assert not trades["type"].eq("open").any()
    assert (
        trades.loc[trades["type"].eq("reject"), "reason"].eq("no_executable_tick_within_wait").any()
    )

    assert calls >= 1
