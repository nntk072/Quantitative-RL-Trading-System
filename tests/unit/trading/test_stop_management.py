"""Tests for shared protective-stop calculations."""

from __future__ import annotations

from typing import TypedDict, cast

import pytest

from trading.risk.stop_management import (
    breakeven_stop_price,
    confirmed_swing_trailing_stop_price,
    tightened_breakeven_stop_price,
)


class _BreakevenStopKwargs(TypedDict):
    direction: int
    entry_price: float
    initial_stop_price: float | None
    current_stop_price: float | None
    best_favorable_points: float
    trigger_r: float
    buffer_points: float


@pytest.mark.parametrize(
    ("direction", "swing", "close", "current_stop", "expected"),
    [
        (1, 100.0, 100.5, 99.5, 99.9),
        (-1, 100.0, 99.5, 100.5, 100.1),
        (1, 100.0, None, 99.5, 99.9),
        (1, 100.0, 100.5, 100.0, None),
        (-1, 100.0, 99.5, 100.0, None),
        (1, 100.0, None, 99.90000000000001, None),
        (-1, 100.5, None, 100.60000000000001, None),
        (1, 100.0, 99.9, 99.5, None),
        (-1, 100.0, 100.1, 100.5, None),
    ],
)
def test_confirmed_swing_trailing_stop_is_tighter_and_protective(
    direction: int,
    swing: float,
    close: float | None,
    current_stop: float | None,
    expected: float | None,
) -> None:
    result = confirmed_swing_trailing_stop_price(
        direction=direction,
        swing_price=swing,
        current_close=close,
        current_stop_price=current_stop,
        buffer_points=0.1,
    )

    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    ("direction", "swing", "close", "current_stop", "buffer", "message"),
    [
        (0, 100.0, 101.0, 99.0, 0.1, "direction must be -1 or 1"),
        (1, float("nan"), 101.0, 99.0, 0.1, "swing_price must be finite"),
        (1, 100.0, 101.0, 99.0, -0.1, "buffer_points must be non-negative"),
    ],
)
def test_confirmed_swing_trailing_stop_rejects_invalid_inputs(
    direction: int,
    swing: float,
    close: float,
    current_stop: float,
    buffer: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        confirmed_swing_trailing_stop_price(
            direction=direction,
            swing_price=swing,
            current_close=close,
            current_stop_price=current_stop,
            buffer_points=buffer,
        )


@pytest.mark.parametrize(
    ("direction", "initial_stop", "current_stop", "expected"),
    [(1, 99.0, 99.0, 102.0), (-1, 101.0, 101.0, 98.0)],
)
def test_breakeven_stop_mirrors_long_and_short(
    direction: int, initial_stop: float, current_stop: float, expected: float
) -> None:
    result = breakeven_stop_price(
        direction=direction,
        entry_price=100.0,
        initial_stop_price=initial_stop,
        current_stop_price=current_stop,
        best_favorable_points=1.0,
        trigger_r=1.0,
        buffer_points=2.0,
    )

    assert result == pytest.approx(expected)


@pytest.mark.parametrize(("direction", "current_stop"), [(1, 103.0), (-1, 97.0)])
def test_breakeven_stop_never_widens_an_existing_stop(direction: int, current_stop: float) -> None:
    result = breakeven_stop_price(
        direction=direction,
        entry_price=100.0,
        initial_stop_price=99.0 if direction == 1 else 101.0,
        current_stop_price=current_stop,
        best_favorable_points=5.0,
        trigger_r=1.0,
        buffer_points=2.0,
    )

    assert result is None


@pytest.mark.parametrize(
    ("direction", "current_stop", "expected"),
    [(1, 99.0, 100.2), (-1, 101.0, 99.8), (1, 100.3, None), (-1, 99.7, None)],
)
def test_tightened_breakeven_stop_only_returns_a_tighter_level(
    direction: int, current_stop: float, expected: float | None
) -> None:
    result = tightened_breakeven_stop_price(
        direction=direction,
        entry_price=100.0,
        current_stop_price=current_stop,
        buffer_points=0.2,
    )

    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


def test_breakeven_stop_requires_positive_initial_risk_and_reached_trigger() -> None:
    common: _BreakevenStopKwargs = {
        "direction": 1,
        "entry_price": 100.0,
        "initial_stop_price": None,
        "current_stop_price": 99.0,
        "best_favorable_points": 0.9,
        "trigger_r": 1.0,
        "buffer_points": 2.0,
    }

    assert breakeven_stop_price(**common) is None
    common["initial_stop_price"] = 100.0
    assert breakeven_stop_price(**common) is None
    common["initial_stop_price"] = 99.0
    assert breakeven_stop_price(**common) is None


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"direction": 0}, "direction must be -1 or 1"),
        ({"best_favorable_points": float("nan")}, "best_favorable_points must be finite"),
        ({"trigger_r": float("inf")}, "trigger_r must be finite"),
        ({"buffer_points": -0.1}, "buffer_points must be non-negative"),
        ({"initial_stop_price": 101.0}, "initial_stop_price must be beyond entry"),
        ({"best_favorable_points": -0.1}, "best_favorable_points must be non-negative"),
    ],
)
def test_breakeven_stop_rejects_invalid_geometry(overrides: dict[str, float], message: str) -> None:
    args: _BreakevenStopKwargs = {
        "direction": 1,
        "entry_price": 100.0,
        "initial_stop_price": 99.0,
        "current_stop_price": 99.0,
        "best_favorable_points": 1.0,
        "trigger_r": 1.0,
        "buffer_points": 0.5,
    }
    cast(dict[str, object], args).update(overrides)

    with pytest.raises(ValueError, match=message):
        breakeven_stop_price(
            direction=args["direction"],
            entry_price=args["entry_price"],
            initial_stop_price=args["initial_stop_price"],
            current_stop_price=args["current_stop_price"],
            best_favorable_points=args["best_favorable_points"],
            trigger_r=args["trigger_r"],
            buffer_points=args["buffer_points"],
        )


def test_breakeven_stop_rejects_overflowing_risk_distance() -> None:
    with pytest.raises(ValueError, match="initial risk.*finite"):
        breakeven_stop_price(
            direction=1,
            entry_price=1e308,
            initial_stop_price=-1e308,
            current_stop_price=None,
            best_favorable_points=1e308,
            trigger_r=1.0,
            buffer_points=0.0,
        )
