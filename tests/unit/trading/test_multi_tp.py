from __future__ import annotations

import pytest

from trading.execution import Position
from trading.positions import target_close_size


def test_final_target_closes_remainder_without_runner() -> None:
    pos = Position(
        direction=1,
        size=0.4,
        entry_price=100.0,
        margin_used=0.0,
        initial_size=1.0,
        tp_initial_size=1.0,
        tp3_price=103.0,
        tp_lot_fractions=(0.4,),
    )

    assert target_close_size(pos, 3, is_final=True) == pytest.approx(0.4)


def test_final_target_reserves_ema_runner_from_initial_size() -> None:
    pos = Position(
        direction=1,
        size=1.0,
        entry_price=100.0,
        margin_used=0.0,
        initial_size=1.0,
        tp_initial_size=1.0,
        tp3_price=103.0,
        tp_lot_fractions=(0.75,),
        ema_runner_fraction=0.25,
    )

    assert target_close_size(pos, 3, is_final=True) == pytest.approx(0.75)


def test_missing_slot_fraction_falls_back_to_equal_active_allocation() -> None:
    pos = Position(
        direction=1,
        size=0.8,
        entry_price=100.0,
        margin_used=0.0,
        initial_size=1.0,
        tp_initial_size=1.0,
        tp1_price=101.0,
        tp2_price=102.0,
        tp_lot_fractions=(0.2,),
    )

    assert target_close_size(pos, 2, is_final=False) == pytest.approx(0.5)
