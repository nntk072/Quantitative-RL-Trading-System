from __future__ import annotations

import math

import pytest

from trading.orders.selection import (
    decode_tp_fractions,
    decode_tp_mode,
    decode_tp_selections,
    validate_tp_levels,
)


@pytest.mark.parametrize(
    ("value", "is_unit", "default", "expected"),
    [
        (-1.0, False, "trailing", ("fixed", True)),
        (0.0, False, "breakeven", ("breakeven", False)),
        (1.0, False, "fixed", ("trailing", True)),
        (-10.0, True, "fixed", ("fixed", True)),
        (10.0, True, "fixed", ("trailing", True)),
    ],
)
def test_tp_mode_decoder_clips_coordinates_and_preserves_defer_default(
    value: float, is_unit: bool, default: str, expected: tuple[str, bool]
) -> None:
    assert decode_tp_mode(value, default_mode=default, is_unit=is_unit) == expected


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ((None, None, None), (None, None, 0)),
        ((2, None, None), (None, None, 2)),
        ((0, 2, None), (0, None, 2)),
        ((1, 1, 3), (None, 1, 3)),
        ((3, 1, 2), (None, 1, 2)),
        ((0.25, 0.5, 0.75), (1, 2, 3)),
    ],
)
def test_tp_selection_decoder_preserves_a_valid_ordered_subset(
    values: tuple[object, object, object], expected: tuple[int | None, int | None, int | None]
) -> None:
    assert decode_tp_selections(*values, menu_size=4) == expected


def test_tp_selection_decoder_handles_disabled_and_invalid_raw_values() -> None:
    assert decode_tp_selections(None, "bad", float("nan"), menu_size=3) == (None, None, 0)
    assert decode_tp_selections(1.0, 2.0, 0.0, menu_size=3, continuous=False) == (
        None,
        None,
        0,
    )
    assert decode_tp_selections(0, 1, 2, menu_size=0) == (None, None, None)


def test_tp_fractions_renormalize_only_active_slots_and_reject_bad_mask() -> None:
    full = decode_tp_fractions(1.0, 0.0)
    assert sum(full) == pytest.approx(1.0)
    active = decode_tp_fractions(1.0, 0.0, active_slots=(None, 1, 2))
    assert len(active) == 2
    assert sum(active) == pytest.approx(1.0)
    assert decode_tp_fractions(1.0, 0.0, active_slots=(False, False, False)) == (1.0,)
    assert all(math.isfinite(value) for value in active)
    with pytest.raises(ValueError, match="active_slots must have length 3"):
        decode_tp_fractions(0.0, 0.0, active_slots=(True, False))


@pytest.mark.parametrize(
    ("direction", "entry", "stop", "targets"),
    [
        (1, 100.0, 95.0, (101.0, 102.0, 103.0)),
        (-1, 100.0, 105.0, (99.0, 98.0, 97.0)),
    ],
)
def test_tp_level_validator_accepts_monotone_levels_on_both_sides(
    direction: int, entry: float, stop: float, targets: tuple[float, float, float]
) -> None:
    assert validate_tp_levels(direction, entry, stop, targets)


@pytest.mark.parametrize(
    ("direction", "entry", "stop", "targets", "message"),
    [
        (1, 100.0, 100.0, (101.0,), "Long SL"),
        (1, 100.0, 95.0, (101.0, 100.0), "strictly increasing"),
        (-1, 100.0, 100.0, (99.0,), "Short SL"),
        (-1, 100.0, 105.0, (99.0, 100.0), "strictly decreasing"),
    ],
)
def test_tp_level_validator_reports_invalid_geometry(
    direction: int, entry: float, stop: float, targets: tuple[float, ...], message: str
) -> None:
    assert not validate_tp_levels(direction, entry, stop, targets)
    with pytest.raises(ValueError, match=message):
        validate_tp_levels(direction, entry, stop, targets, raise_exc=True)


def test_tp_level_validator_accepts_unknown_direction_without_order_contract() -> None:
    assert validate_tp_levels(0, 100.0, None, (90.0, 110.0))
