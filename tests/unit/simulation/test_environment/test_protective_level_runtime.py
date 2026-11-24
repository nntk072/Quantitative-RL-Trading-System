from __future__ import annotations

import pandas as pd

from simulation.environment.env import TradingEnv
from tests.unit.simulation.test_environment._account_fixtures import (
    _make_bars,
    _make_features,
)
from trading.execution import Position


def test_tick_only_protection_keeps_position_open_for_pre_entry_excursion() -> None:
    bars = _make_bars(120)
    env = TradingEnv(bars=bars, features=_make_features(bars), obs_window=10)
    env.reset(seed=3)
    env.step_idx = 50
    env.tick_execution_required = True
    bar_time = env._bar_time(env.step_idx)
    bar = env._bar_at(env.step_idx)
    env.position = Position(
        direction=-1,
        size=0.1,
        entry_price=bar.close,
        margin_used=1.0,
        sl_price=bar.high + env.cost_model.spread_points / 2.0,
        entry_timestamp=bar_time + pd.Timedelta(seconds=10),
    )

    env._check_sl_tp(bar, bar.close, bar.close, env.step_idx)
    assert env.position is not None
    assert not any(row.get("type") == "stop_close" for row in env.trade_log)
