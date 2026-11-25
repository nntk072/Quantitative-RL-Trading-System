"""Parity of the native daily-loss limits with the Python oracle (NATIVE-DOMAIN).

The expected values are the same hand calculations as
tests/unit/trading/test_semantic_oracle_limits_sizing.py, expressed in cents.
"""

import pytest

from trading.account.limits import canonical_daily_loss as oracle_daily_loss
from trading.account.limits import daily_floor as oracle_daily_floor
from trading.account.limits import remaining_daily_capacity as oracle_remaining_capacity

qrl_native = pytest.importorskip("qrl_native")


def _cents(dollars: float) -> int:
    """Converts the oracle's float currency amount to integer cents; exact for these grids."""
    return round(dollars * 100)


@pytest.mark.parametrize("start", [0, 1, 50_000, 1_000_000, 2_500_050])
@pytest.mark.parametrize("limit", [1, 50, 50_000, 123_457])
def test_native_matches_python_oracle_on_a_grid(start: int, limit: int) -> None:
    # Equities cover losses, gains, the floor exactly and points on both sides of it.
    floor = start - limit
    equities = {0, start, floor, floor - 1, floor + 1, start - 1, start + 1, 970_000, 940_000}
    assert qrl_native.daily_floor_cents(start, limit) == _cents(
        oracle_daily_floor(start / 100, limit / 100)
    )
    for equity in sorted(equities):
        if equity < 0:
            continue
        assert qrl_native.canonical_daily_loss_cents(start, equity) == _cents(
            oracle_daily_loss(start / 100, equity / 100)
        )
        assert qrl_native.remaining_daily_capacity_cents(start, equity, limit) == _cents(
            oracle_remaining_capacity(start / 100, equity / 100, limit / 100)
        )


def test_breach_point_is_zero_capacity_in_both_implementations() -> None:
    # Equity exactly on the floor (9500.00) has no capacity left in either implementation.
    assert qrl_native.remaining_daily_capacity_cents(1_000_000, 950_000, 50_000) == 0
    assert oracle_remaining_capacity(10_000.0, 9_500.0, 500.0) == 0.0


def test_daily_loss_matches_the_oracle() -> None:
    # 10000.00 - 9700.00 = 300.00
    assert qrl_native.canonical_daily_loss_cents(1_000_000, 970_000) == 30_000
    # 10000.00 - 10200.00 floored at 0
    assert qrl_native.canonical_daily_loss_cents(1_000_000, 1_020_000) == 0


def test_floor_matches_the_oracle() -> None:
    # 10000.00 - 500.00 = 9500.00
    assert qrl_native.daily_floor_cents(1_000_000, 50_000) == 950_000


def test_remaining_capacity_matches_the_oracle() -> None:
    # floor 9500.00; 9700.00 - 9500.00 = 200.00
    assert qrl_native.remaining_daily_capacity_cents(1_000_000, 970_000, 50_000) == 20_000
    # 9400.00 - 9500.00 floored at 0 (breached)
    assert qrl_native.remaining_daily_capacity_cents(1_000_000, 940_000, 50_000) == 0


def test_overflow_raises_in_python() -> None:
    with pytest.raises(OverflowError):
        qrl_native.daily_floor_cents(-(2**63), 1)
