"""Parity of the native daily-loss limits with the Python oracle (NATIVE-DOMAIN).

The expected values are the same hand calculations as
tests/unit/trading/test_semantic_oracle_limits_sizing.py, expressed in cents.
"""

import pytest

qrl_native = pytest.importorskip("qrl_native")


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
