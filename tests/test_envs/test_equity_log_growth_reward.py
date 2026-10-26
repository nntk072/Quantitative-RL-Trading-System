from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from simulation.environment.env import TradingEnv
from simulation.environment.rewards import DSRReward, EquityLogGrowthReward


def test_log_growth_sign_and_zero_change() -> None:
    reward = EquityLogGrowthReward(scale=100.0)
    assert reward(100.0, previous_equity=100_000.0, equity=100_100.0) > 0.0
    assert reward(-100.0, previous_equity=100_000.0, equity=99_900.0) < 0.0
    assert reward(0.0, previous_equity=100_000.0, equity=100_000.0) == pytest.approx(0.0)


def test_undiscounted_rewards_telescope_to_scaled_terminal_log_growth() -> None:
    equity = np.asarray([100_000.0, 100_125.0, 99_950.0, 100_400.0])
    reward = EquityLogGrowthReward(scale=100.0)
    rewards = [
        reward(0.0, previous_equity=float(before), equity=float(after))
        for before, after in zip(equity[:-1], equity[1:], strict=True)
    ]
    assert sum(rewards) == pytest.approx(100.0 * np.log(equity[-1] / equity[0]))


def test_reset_clears_reward_diagnostics() -> None:
    reward = EquityLogGrowthReward()
    reward(0.0, previous_equity=100_000.0, equity=100_100.0)
    assert reward.last_parts["equity_growth"] != 0.0
    reward.reset()
    assert reward.last_parts["equity_growth"] == 0.0


def test_dsr_reward_is_unchanged_by_equity_endpoint_kwargs() -> None:
    baseline = DSRReward(eta=0.01)
    with_extra_ledger_fields = DSRReward(eta=0.01)
    expected = baseline(125.0)
    actual = with_extra_ledger_fields(125.0, equity=100_125.0)
    assert actual == pytest.approx(expected)


def test_equity_endpoints_avoid_double_counting_step_pnl() -> None:
    reward = EquityLogGrowthReward(scale=100.0)
    net_equity = 100_080.0  # account equity after a $20 execution cost
    actual = reward(1_000.0, previous_equity=100_000.0, equity=net_equity)
    assert actual == pytest.approx(100.0 * np.log(net_equity / 100_000.0))
    assert reward.last_parts["equity_growth"] == pytest.approx(actual)


def test_hard_breach_uses_realized_equity_change_and_nonpositive_is_explicit() -> None:
    reward = EquityLogGrowthReward(scale=100.0, breach_penalty=-10.0)
    # A guardrail termination does not substitute an arbitrary reward for the
    # measured account loss; the hard limit remains enforced by the environment.
    assert reward(0.0, previous_equity=100_000.0, equity=90_000.0) == pytest.approx(
        100.0 * np.log(0.9)
    )
    assert reward(0.0, previous_equity=100_000.0, equity=0.0) == -10.0
    with pytest.raises(ValueError, match="positive previous_equity"):
        reward(0.0, previous_equity=0.0, equity=1.0)


@pytest.mark.parametrize(
    ("before", "after"),
    [(float("nan"), 100.0), (100.0, float("inf"))],
)
def test_nonfinite_equity_is_rejected(before: float, after: float) -> None:
    reward = EquityLogGrowthReward()
    with pytest.raises(ValueError, match="finite equity endpoints"):
        reward(0.0, previous_equity=before, equity=after)


def test_growth_reward_is_selected_by_environment_and_uses_ledger_equity() -> None:
    count = 40
    index = pd.date_range("2025-01-06 08:00", periods=count, freq="1min")
    close = np.linspace(100.0, 101.0, count)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
            "volume": np.full(count, 100.0),
            "session_id": np.zeros(count, dtype=int),
        },
        index=index,
    )
    features = pd.DataFrame({"close": close}, index=index)
    env = TradingEnv(
        bars,
        features,
        obs_window=10,
        reward_mode="equity_log_growth",
        equity_log_growth_scale=100.0,
    )
    assert isinstance(env.reward_fn, EquityLogGrowthReward)

    before = float(env.account.equity)
    env.account.close_trade(80.0)
    env.equity_curve.append(float(env.account.equity))
    result = env._calculate_reward(
        80.0,
        env._bar_at(0),
        env._feature_row_at(0),
        done=False,
        truncated=False,
    )
    assert result == pytest.approx(100.0 * np.log(env.account.equity / before))

    dsr_env = TradingEnv(bars, features, obs_window=10)
    dsr_env.account.close_trade(80.0)
    dsr_env.equity_curve.append(float(dsr_env.account.equity))
    dsr_reward = dsr_env._calculate_reward(
        80.0,
        dsr_env._bar_at(0),
        dsr_env._feature_row_at(0),
        done=False,
        truncated=False,
    )
    assert np.isfinite(dsr_reward)
