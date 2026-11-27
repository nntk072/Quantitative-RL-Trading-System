"""Behavior contracts for deterministic quote and stop-fill calculations."""

from __future__ import annotations

import pytest

from trading.execution import (
    CostModel,
    adverse_tick_fill_quote,
    bar_stop_fill_quote,
    bar_stop_trigger_price,
    protective_level_fill_quote,
    quote_from_bar_price,
    raw_spread_to_price,
    undo_adverse_quote_level_slippage,
    undo_adverse_tick_slippage_quote,
)


@pytest.mark.parametrize(
    ("direction", "opening", "expected"),
    [
        (1, True, (100.0, 102.25)),
        (-1, True, (98.75, 101.0)),
        (1, False, (98.75, 101.0)),
        (-1, False, (100.0, 102.25)),
    ],
)
def test_tick_slippage_and_inverse_adjust_only_the_transacted_side(
    direction: int, opening: bool, expected: tuple[float, float]
) -> None:
    adjusted = adverse_tick_fill_quote((100.0, 101.0), direction, 1.25, opening=opening)

    assert adjusted == expected
    assert undo_adverse_tick_slippage_quote(adjusted, direction, 1.25, opening=opening) == (
        100.0,
        101.0,
    )


@pytest.mark.parametrize("direction", [0, 2, -2])
def test_tick_slippage_rejects_invalid_directions(direction: int) -> None:
    with pytest.raises(ValueError, match=r"direction must be -1 or \+1"):
        adverse_tick_fill_quote((100.0, 101.0), direction, 0.1, opening=True)
    with pytest.raises(ValueError, match=r"direction must be -1 or \+1"):
        undo_adverse_tick_slippage_quote((100.0, 101.0), direction, 0.1, opening=False)
    with pytest.raises(ValueError, match=r"direction must be -1 or \+1"):
        undo_adverse_quote_level_slippage((100.0, 101.0), direction, 0.1, opening=False)


@pytest.mark.parametrize("slippage", [-0.1, float("nan"), float("inf")])
def test_quote_slippage_rejects_negative_or_nonfinite_amounts(slippage: float) -> None:
    with pytest.raises(ValueError, match="finite and non-negative"):
        adverse_tick_fill_quote((100.0, 101.0), 1, slippage, opening=True)
    with pytest.raises(ValueError, match="finite and non-negative"):
        undo_adverse_tick_slippage_quote((100.0, 101.0), -1, slippage, opening=False)
    with pytest.raises(ValueError, match="finite and non-negative"):
        undo_adverse_quote_level_slippage((100.0, 101.0), 1, slippage, opening=False)


@pytest.mark.parametrize(
    ("direction", "opening", "expected"),
    [
        (1, True, (99.8, 100.8)),
        (-1, True, (100.2, 101.2)),
        (1, False, (100.2, 101.2)),
        (-1, False, (99.8, 100.8)),
    ],
)
def test_quote_level_slippage_is_whole_quote_and_reversible(
    direction: int, opening: bool, expected: tuple[float, float]
) -> None:
    shifted = undo_adverse_quote_level_slippage((100.0, 101.0), direction, 0.2, opening=opening)

    assert shifted == pytest.approx(expected)


def test_raw_spread_and_bar_quote_preserve_missing_and_bad_spreads() -> None:
    costs = CostModel(spread_points=0.6, point_size=0.01)

    assert raw_spread_to_price(None, 0.01) is None
    assert raw_spread_to_price(25, 0.01) == pytest.approx(0.25)
    assert raw_spread_to_price(float("nan"), 0.01) is None
    assert raw_spread_to_price(float("inf"), 0.01) is None
    assert quote_from_bar_price(costs, 100.0, 25) == pytest.approx((100.0, 100.25))
    assert quote_from_bar_price(costs, 100.0, None) == (100.0, 100.6)


@pytest.mark.parametrize(("direction", "expected"), [(1, (99.8, 100.4)), (-1, (99.6, 100.2))])
def test_protective_level_fill_applies_adverse_slippage_on_position_side(
    direction: int, expected: tuple[float, float]
) -> None:
    costs = CostModel(spread_points=0.6, slippage_points=0.2)

    assert protective_level_fill_quote(direction, 100.0, costs) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("direction", "stop", "bar_open", "spread", "trigger"),
    [
        (1, 99.0, 98.0, 0.5, 98.0),
        (1, 99.0, 100.0, 0.5, 99.0),
        (-1, 101.0, 101.0, 0.5, 101.5),
        (-1, 101.0, 102.0, 0.5, 102.5),
    ],
)
def test_bar_stop_trigger_accounts_for_gaps_and_short_open_spread(
    direction: int, stop: float, bar_open: float, spread: float, trigger: float
) -> None:
    assert bar_stop_trigger_price(direction, stop, bar_open, spread) == trigger


def test_bar_stop_fill_uses_recorded_spread_or_default_and_protective_slippage() -> None:
    costs = CostModel(spread_points=0.6, slippage_points=0.2, point_size=0.01)

    # Long stop is triggered at the gapped bid open and sells below it.
    assert bar_stop_fill_quote(1, 99.0, 98.0, 25, costs) == pytest.approx((97.8, 98.4))
    # Short stop defaults to the configured opening spread when the bar omits it.
    assert bar_stop_fill_quote(-1, 101.0, 100.0, None, costs) == pytest.approx((100.6, 101.2))
