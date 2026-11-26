"""Runtime oracle for the backtest take-profit leg caller (SEMANTIC-ORACLE, O4).

``simulation.backtest.protective_management._record_target_slot`` turns a target slot into a
broker close. Fixture defect C3 (fixed in fixture version 2.0.0) made a zero leg close the
whole position. These tests drive the real function and observe the broker close through
``_record_close``. Expected values are hand-derived in the comments.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from simulation.backtest import protective_management as management
from trading.execution.broker import Position


def _position(*, size: float, initial: float, fractions: tuple[float, ...]) -> Position:
    position = Position(
        direction=1,
        size=size,
        entry_price=100.0,
        margin_used=0.0,
        initial_size=initial,
        tp_initial_size=initial,
        tp_lot_fractions=fractions,
    )
    position.tp1_price = 101.0
    position.tp2_price = 102.0
    return position


def _call_slot_one(position: Position) -> Any:
    state: Any = SimpleNamespace(position=position, current_execution_meta={})
    settings: Any = SimpleNamespace()
    broker: Any = SimpleNamespace()
    management._record_target_slot(
        state,
        settings,
        broker,
        position,
        bar_index=5,
        slot=1,
        quote=(101.0, 101.6),
        fill_time=pd.Timestamp("2025-01-06 17:00", tz="Etc/GMT-3"),
        session=1,
    )
    return state


def test_non_zero_target_leg_closes_its_hand_calculated_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Positive: 1.0 lot, TP1 fraction 0.5 with two active slots -> leg 0.5 lots is closed."""
    closes: list[dict[str, Any]] = []

    def record_close(
        state: Any,
        settings: Any,
        broker: Any,
        position: Any,
        quote: Any,
        record: Any,
        session: Any,
        *,
        size: float,
    ) -> None:
        closes.append({"size": size, "reason": record["reason"], "bar": record["bar"]})

    monkeypatch.setattr(management, "_record_close", record_close)
    position = _position(size=1.0, initial=1.0, fractions=(0.5, 0.5))

    _call_slot_one(position)

    # leg = round(0.5 * 1.0, 2) = 0.5 lots, below the 1.0 lot position
    assert closes == [{"size": pytest.approx(0.5), "reason": "structure_tp1", "bar": 5}]
    assert position.tp1_price is None
    assert position.tp_hit_mask & 1 == 1


def test_zero_target_leg_consumes_slot_without_any_broker_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adverse (C3 regression): 0.01 lots, TP1 fraction 0.3 -> leg 0.003, rounds to 0.0.

    The slot is consumed, the position keeps its 0.01 lots, and no close or trade record is
    produced. Before the 2.0.0 fix the whole position was closed here.
    """
    calls: list[Any] = []
    monkeypatch.setattr(
        management, "_record_close", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    position = _position(size=0.01, initial=0.01, fractions=(0.3, 0.7))

    state = _call_slot_one(position)

    assert calls == []
    assert position.size == pytest.approx(0.01, abs=1e-12)
    assert position.tp1_price is None
    assert position.tp_hit_mask & 1 == 1
    assert state.current_execution_meta == {}


def test_runner_clamped_final_leg_consumes_slot_and_keeps_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adverse: final slot with a 0.2 runner on a 0.2 lot position leaves nothing to close.

    With size 0.2 and runner 0.2 the clamp gives max(0, 0.2 - 0.2) = 0, so the leg is zero.
    The runner is kept whole and nothing is closed.
    """
    calls: list[Any] = []
    monkeypatch.setattr(
        management, "_record_close", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    position = Position(
        direction=1,
        size=0.2,
        entry_price=100.0,
        margin_used=0.0,
        initial_size=1.0,
        tp_initial_size=1.0,
        tp_lot_fractions=(0.5,),
        ema_runner_fraction=0.2,
    )
    position.tp1_price = 101.0
    position.tp2_price = None
    position.tp3_price = None

    _call_slot_one(position)

    assert calls == []
    assert position.size == pytest.approx(0.2, abs=1e-12)
    assert position.tp1_price is None
