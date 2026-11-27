"""Boundary behavior for account loss floors and available capacity."""

from __future__ import annotations

import pytest

from trading.account.limits import (
    canonical_daily_loss,
    daily_floor,
    remaining_account_capacity,
    remaining_daily_capacity,
)


@pytest.mark.parametrize(
    ("start", "equity", "expected"),
    [(100_000.0, 99_200.0, 800.0), (100_000.0, 100_100.0, 0.0)],
)
def test_daily_loss_is_positive_only_when_equity_is_below_session_start(
    start: float, equity: float, expected: float
) -> None:
    assert canonical_daily_loss(start, equity) == expected


def test_loss_floors_and_remaining_capacity_respect_exact_and_breached_boundaries() -> None:
    assert daily_floor(100_000.0, 2_500.0) == 97_500.0
    assert remaining_daily_capacity(100_000.0, 99_000.0, 2_500.0) == 1_500.0
    assert remaining_daily_capacity(100_000.0, 97_500.0, 2_500.0) == 0.0
    assert remaining_daily_capacity(100_000.0, 96_000.0, 2_500.0) == 0.0
    assert remaining_account_capacity(98_000.0, 95_000.0) == 3_000.0
    assert remaining_account_capacity(95_000.0, 95_000.0) == 0.0
    assert remaining_account_capacity(94_000.0, 95_000.0) == 0.0
