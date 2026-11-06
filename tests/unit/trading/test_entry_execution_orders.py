from __future__ import annotations

import pandas as pd
import pytest

from trading.orders.entry_execution import limit_order_expiry, limit_price_from_atr_offset


@pytest.mark.parametrize(
    ("direction", "expected"),
    [(1, 99.5), (-1, 100.5)],
)
def test_limit_price_uses_directional_atr_offset_and_tick_rounding(
    direction: int, expected: float
) -> None:
    price = limit_price_from_atr_offset(
        direction=direction,
        reference_price=100.0,
        atr=2.0,
        offset_atr=0.25,
        point_size=0.5,
    )

    assert price == pytest.approx(expected)


@pytest.mark.parametrize(
    ("direction", "raw_price", "expected"),
    [(1, 100.26, 100.0), (-1, 100.26, 100.5)],
)
def test_limit_price_rounds_long_down_and_short_up(
    direction: int, raw_price: float, expected: float
) -> None:
    reference = raw_price + direction * 0.0
    price = limit_price_from_atr_offset(
        direction=direction,
        reference_price=reference,
        atr=1.0,
        offset_atr=0.0,
        point_size=0.5,
    )

    assert price == pytest.approx(expected)


def test_limit_order_expiry_uses_inclusive_bar_ttl() -> None:
    submitted = pd.Timestamp("2025-01-06 16:31:00", tz="UTC")

    expiry = limit_order_expiry(submitted, 5, pd.Timedelta(minutes=1))

    assert expiry == submitted + pd.Timedelta(minutes=5)


@pytest.mark.parametrize(
    ("ttl", "duration"),
    [(0, pd.Timedelta(minutes=1)), (True, pd.Timedelta(minutes=1)), (1, pd.Timedelta(0))],
)
def test_limit_order_expiry_rejects_invalid_ttl_or_bar_duration(
    ttl: int, duration: pd.Timedelta
) -> None:
    with pytest.raises(ValueError):
        limit_order_expiry(pd.Timestamp("2025-01-06 16:31:00", tz="UTC"), ttl, duration)
