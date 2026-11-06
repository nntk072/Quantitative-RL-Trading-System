from __future__ import annotations

import pandas as pd

from simulation.environment.env import TradingEnv
from tests.unit.simulation.test_environment._account_fixtures import (
    _make_bars,
    _make_features,
)
from trading.execution import Position


def test_tick_protection_check_skips_pre_entry_excursions_in_entry_bar() -> None:
    bars = _make_bars(120)
    env = TradingEnv(bars=bars, features=_make_features(bars), obs_window=10)
    env.reset(seed=3)
    env.step_idx = 50
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

    env._assert_tick_protective_events_observed(bar, env.step_idx)
