"""Eligibility rules for candle-adjacent and projected price levels."""

from __future__ import annotations

import pytest

from trading.orders.levels import deviation_levels, level_near_candles


def test_candle_proximity_uses_half_span_padding_and_rejects_nonfinite_levels() -> None:
    assert level_near_candles(8.0, 10.0, 14.0)
    assert not level_near_candles(7.99, 10.0, 14.0)
    assert not level_near_candles(float("nan"), 10.0, 14.0)
    assert not level_near_candles(12.0, 10.0, float("inf"))


@pytest.mark.parametrize(
    ("swing_low", "swing_high"),
    [(float("nan"), 110.0), (100.0, float("inf")), (110.0, 100.0), (100.0, 100.0)],
)
def test_deviation_levels_require_a_finite_positive_swing_range(
    swing_low: float, swing_high: float
) -> None:
    assert deviation_levels(swing_low, swing_high, 99.0, 111.0) == []
