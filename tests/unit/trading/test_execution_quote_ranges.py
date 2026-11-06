from __future__ import annotations

import pytest

from trading.execution import CostModel, exit_side_bar_range


def test_exit_bar_range_uses_bid_for_longs_and_spread_adjusted_ask_for_shorts() -> None:
    cost_model = CostModel(spread_points=0.6, point_size=0.01)

    assert exit_side_bar_range(1, 20790.45, 20817.25, 1.2, cost_model) == (
        20790.45,
        20817.25,
    )
    short_low, short_high = exit_side_bar_range(-1, 20790.45, 20817.25, 1.2, cost_model)
    assert short_low == pytest.approx(20791.65)
    assert short_high == pytest.approx(20818.45)


def test_exit_bar_range_uses_default_spread_when_bar_spread_is_missing() -> None:
    cost_model = CostModel(spread_points=1.25, point_size=0.01)

    assert exit_side_bar_range(-1, 100.0, 102.0, None, cost_model) == (101.25, 103.25)


def test_exit_bar_range_rejects_invalid_direction() -> None:
    with pytest.raises(ValueError, match=r"direction must be -1 or \+1"):
        exit_side_bar_range(0, 100.0, 102.0, 1.0, CostModel())
