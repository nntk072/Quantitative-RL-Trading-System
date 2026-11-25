"""Hand-calculated semantic oracle for daily-loss floors and risk sizing (SEMANTIC-ORACLE).

Every expected value below is worked out by hand in the comment above the assertion. The
expectations do not reuse the production formulas, so a changed formula fails here.
"""

from __future__ import annotations

import pytest

from trading.account.limits import (
    canonical_daily_loss,
    daily_floor,
    remaining_account_capacity,
    remaining_daily_capacity,
)
from trading.risk.sizing import compute_lots, stop_loss_risk_usd

# --- account loss floors -------------------------------------------------------------


def test_daily_loss_is_start_minus_equity_when_losing() -> None:
    # 10000 - 9700 = 300
    assert canonical_daily_loss(10000.0, 9700.0) == pytest.approx(300.0)


def test_daily_loss_is_zero_when_equity_rose() -> None:
    # 10000 - 10200 = -200, floored at 0
    assert canonical_daily_loss(10000.0, 10200.0) == 0.0


def test_daily_floor_is_start_minus_limit() -> None:
    # 10000 - 500 = 9500
    assert daily_floor(10000.0, 500.0) == pytest.approx(9500.0)


def test_remaining_daily_capacity_is_equity_above_the_floor() -> None:
    # floor 9500; 9700 - 9500 = 200
    assert remaining_daily_capacity(10000.0, 9700.0, 500.0) == pytest.approx(200.0)


def test_remaining_daily_capacity_is_zero_once_breached() -> None:
    # floor 9500; 9400 - 9500 = -100, floored at 0 (breach latch input)
    assert remaining_daily_capacity(10000.0, 9400.0, 500.0) == 0.0


def test_remaining_account_capacity_above_floor_and_at_floor() -> None:
    # 9700 - 9000 = 700
    assert remaining_account_capacity(9700.0, 9000.0) == pytest.approx(700.0)
    # 8900 - 9000 = -100, floored at 0
    assert remaining_account_capacity(8900.0, 9000.0) == 0.0


# --- risk sizing ---------------------------------------------------------------------


def test_stop_loss_risk_uses_absolute_stop_distance() -> None:
    # |-2.5| * 0.1 lots * 100 contract size * 1.0 point value = 25.0
    assert stop_loss_risk_usd(-2.5, 0.1, 100.0, 1.0) == pytest.approx(25.0)


def test_lots_from_one_percent_risk_on_ten_thousand() -> None:
    # budget = 10000 * 0.01 = 100; SL distance = |1.1000 - 1.0990| = 0.0010
    # lots = 100 / (0.0010 * 100000 * 1) = 1.0, inside [0.01, 100]
    lots = compute_lots(
        equity=10000.0,
        risk_frac=0.01,
        entry_price=1.1000,
        sl_price=1.0990,
        contract_size=100000.0,
        point_value=1.0,
    )
    assert lots == pytest.approx(1.0)


def test_explicit_risk_usd_is_not_shrunk_by_the_loss_cap() -> None:
    # risk 500 USD; SL distance 0.0010; 500 / (0.0010 * 100000) = 5.0
    # max_loss_cap is ignored when risk_usd is given, so 100 does not clamp it.
    lots = compute_lots(
        equity=10000.0,
        risk_frac=0.01,
        entry_price=1.1000,
        sl_price=1.0990,
        contract_size=100000.0,
        point_value=1.0,
        max_loss_cap=100.0,
        risk_usd=500.0,
    )
    assert lots == pytest.approx(5.0)


def test_loss_cap_limits_fractional_sizing() -> None:
    # budget = 10000 * 0.05 = 500 -> lots 5.0; cap 100 -> 100 / 100 = 1.0; min(5.0, 1.0) = 1.0
    lots = compute_lots(
        equity=10000.0,
        risk_frac=0.05,
        entry_price=1.1000,
        sl_price=1.0990,
        contract_size=100000.0,
        point_value=1.0,
        max_loss_cap=100.0,
    )
    assert lots == pytest.approx(1.0)


def test_tiny_budget_is_clipped_up_to_minimum_lot() -> None:
    # budget = 1 * 0.01 = 0.01; lots = 0.01 / (0.0010 * 100000) = 0.0001 -> clipped to 0.01
    lots = compute_lots(
        equity=1.0,
        risk_frac=0.01,
        entry_price=1.1000,
        sl_price=1.0990,
        contract_size=100000.0,
        point_value=1.0,
    )
    assert lots == pytest.approx(0.01)


def test_zero_stop_distance_returns_minimum_lot() -> None:
    # SL equals entry: the function refuses to divide and returns min_lot.
    lots = compute_lots(
        equity=10000.0,
        risk_frac=0.01,
        entry_price=1.1000,
        sl_price=1.1000,
        contract_size=100000.0,
    )
    assert lots == pytest.approx(0.01)
