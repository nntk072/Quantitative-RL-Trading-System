"""Tests: DSR reward properties."""

from __future__ import annotations

import math

import pytest

from simulation.environment.rewards import DSRReward, PnLReward, RMultipleReward


def test_breach_returns_strong_terminal():
    r = DSRReward()
    val = r(0.0, breach=True)
    assert val == pytest.approx(-1.0)


def test_eval_breach_keeps_the_report_penalty():
    r = DSRReward(breach_penalty=-10.0)
    assert r(0.0, breach=True) == pytest.approx(-10.0)


def test_soft_band_charges_once_on_entry():
    from simulation.environment.rewards import PnLReward

    r = PnLReward()
    first = r(
        0.0,
        daily_loss=3500.0,
        daily_loss_limit=5000.0,
        soft_daily_loss_limit=2000.0,
        initial_balance=100_000.0,
    )
    second = r(
        0.0,
        daily_loss=3600.0,
        daily_loss_limit=5000.0,
        soft_daily_loss_limit=2000.0,
        initial_balance=100_000.0,
    )
    assert first < 0.0
    assert r.last_parts["soft_daily"] == 0.0
    assert second == pytest.approx(0.0)
    r.reset()
    again = r(
        0.0,
        daily_loss=3500.0,
        daily_loss_limit=5000.0,
        soft_daily_loss_limit=2000.0,
        initial_balance=100_000.0,
    )
    assert again < 0.0


def test_positive_pnl_eventually_positive():
    """After consistent positive returns DSR should be positive."""
    r = DSRReward(eta=0.1)
    rewards = [r(100.0, initial_balance=100_000.0) for _ in range(50)]
    assert rewards[-1] > 0.0


def test_negative_pnl_eventually_negative():
    r = DSRReward(eta=0.1)
    rewards = [r(-100.0, initial_balance=100_000.0) for _ in range(50)]
    assert rewards[-1] < 0.0


def test_soft_penalty_near_daily_limit():
    r = DSRReward(eta=0.01)
    val_safe = r(
        0.0,
        daily_loss=100.0,
        daily_loss_limit=5000.0,
        soft_daily_loss_limit=2000.0,
        initial_balance=100_000.0,
    )
    r.reset()
    val_near = r(
        0.0,
        daily_loss=4999.0,
        daily_loss_limit=5000.0,
        soft_daily_loss_limit=2000.0,
        initial_balance=100_000.0,
    )
    assert val_near < val_safe


def test_soft_penalty_uses_soft_brick_band():
    r = DSRReward(eta=0.01)
    val_below = r(
        0.0,
        daily_loss=1500.0,
        daily_loss_limit=5000.0,
        soft_daily_loss_limit=2000.0,
        initial_balance=100_000.0,
    )
    r.reset()
    val_in_band = r(
        0.0,
        daily_loss=3500.0,
        daily_loss_limit=5000.0,
        soft_daily_loss_limit=2000.0,
        initial_balance=100_000.0,
    )
    assert val_in_band < val_below


def test_soft_max_loss_shaping_band():
    r = DSRReward(eta=0.01)
    val_safe = r(
        0.0,
        loss_from_initial=1000.0,
        soft_max_loss_limit=5000.0,
        max_loss_limit=10000.0,
        initial_balance=100_000.0,
    )
    r.reset()
    val_near = r(
        0.0,
        loss_from_initial=8000.0,
        soft_max_loss_limit=5000.0,
        max_loss_limit=10000.0,
        initial_balance=100_000.0,
    )
    assert val_near < val_safe


def test_soft_trailing_dd_shaping_band():
    r = DSRReward(eta=0.01)
    val_safe = r(
        0.0,
        trailing_dd=0.02,
        soft_trailing_dd_limit=0.04,
        trailing_dd_limit=0.07,
        initial_balance=100_000.0,
    )
    r.reset()
    val_near = r(
        0.0,
        trailing_dd=0.06,
        soft_trailing_dd_limit=0.04,
        trailing_dd_limit=0.07,
        initial_balance=100_000.0,
    )
    assert val_near < val_safe


def test_reward_clipped():
    r = DSRReward(eta=0.5)
    # Extreme gains
    for _ in range(10):
        val = r(1_000_000.0, initial_balance=100_000.0)
    assert val <= 10.0
    assert val >= -10.0


def test_pnl_reward_adds_weighted_dsr_and_reset_restarts_dsr_state() -> None:
    reward = PnLReward(dsr_weight=0.5)
    first = reward(
        1_000.0,
        realized_close_pnl=500.0,
        initial_balance=100_000.0,
    )
    parts = dict(reward.last_parts)
    assert parts["pnl"] == pytest.approx(0.005)
    assert parts["dsr"] > 0.0
    assert math.fsum(parts.values()) == pytest.approx(first)

    reward.reset()
    second = reward(
        1_000.0,
        realized_close_pnl=500.0,
        initial_balance=100_000.0,
    )
    assert second == pytest.approx(first)


def test_r_multiple_reward_only_credits_finite_closed_trade_r_and_resets_total() -> None:
    reward = RMultipleReward(breach_penalty=-7.0)

    assert reward(500.0) == pytest.approx(0.0)
    assert reward(500.0, realized_r=float("nan")) == pytest.approx(0.0)
    assert reward.cumulative_r == pytest.approx(0.0)

    assert reward(0.0, realized_r=1.5) == pytest.approx(1.5)
    assert reward.cumulative_r == pytest.approx(1.5)
    assert reward(0.0) == pytest.approx(0.0)  # An open position earns no second R.
    assert reward(0.0, realized_r=-0.5) == pytest.approx(-0.5)
    assert reward.cumulative_r == pytest.approx(1.0)

    assert reward(0.0, breach=True) == pytest.approx(-7.0)
    assert reward.last_parts["breach"] == pytest.approx(-7.0)
    reward.reset()
    assert reward.cumulative_r == pytest.approx(0.0)
    assert reward(0.0) == pytest.approx(0.0)
    assert math.fsum(reward.last_parts.values()) == pytest.approx(0.0)
