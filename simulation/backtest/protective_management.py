"""Stop, target, and position-management helpers for event-driven backtests."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from market_data.loading.ticks import nearest_exit_tick_quote
from trading.execution import Broker, Position, protective_level_fill_quote
from trading.positions import reorder_remaining_targets, target_close_size

from .accounting import _record_close
from .runtime import BacktestSettings, BacktestState


def _active_target_slots(position: Any) -> list[int]:
    """Return unfilled take-profit slots in ascending order.

    Args:
        position: Open position whose target prices and hit mask are inspected.

    Returns:
        Active target slot numbers in ascending order.
    """
    return [
        slot
        for slot in (1, 2, 3)
        if getattr(position, f"tp{slot}_price") is not None
        and not (position.tp_hit_mask & (1 << (slot - 1)))
    ]


def _finite_feature(feature_row: pd.Series | None, name: str) -> float | None:
    """Return a finite feature value, or ``None`` when unavailable.

    Args:
        feature_row: Current feature values, if present.
        name: Feature column to read.

    Returns:
        Finite numeric feature value, or ``None`` for missing or invalid data.
    """
    if feature_row is None:
        return None
    try:
        value = float(feature_row.get(name, np.nan))
    except (TypeError, ValueError):
        return None
    return value if np.isfinite(value) else None


def _default_sl_mode(position: Position | None, feature_row: pd.Series | None) -> str:
    """Choose a structure-aware stop mode from the open trade context.

    Args:
        position: Current position with entry, stop, and swing references.
        feature_row: Latest structural features available for the position.

    Returns:
        Stop mode: ``fixed``, ``breakeven``, or ``trailing``.
    """
    if position is None:
        return "fixed"
    reference_taken = False
    if position.entry_sl_ref_price is not None:
        distance_to_reference = (
            position.entry_price - float(position.entry_sl_ref_price)
            if position.direction == 1
            else float(position.entry_sl_ref_price) - position.entry_price
        )
        reference_taken = position.mae >= distance_to_reference
    current_swing = _finite_feature(
        feature_row, "last_swing_high" if position.direction == 1 else "last_swing_low"
    )
    target_farther = (
        current_swing is not None
        and position.tp_price is not None
        and position.direction * (float(position.tp_price) - current_swing) > 0
    )
    entry_swing = (
        position.entry_last_swing_high if position.direction == 1 else position.entry_last_swing_low
    )
    new_swing = (
        current_swing is not None
        and entry_swing is not None
        and (
            current_swing > entry_swing if position.direction == 1 else current_swing < entry_swing
        )
    )
    if not reference_taken and target_farther:
        return "fixed"
    if reference_taken:
        return "breakeven"
    return "trailing" if new_swing else "fixed"


def _advance_management_modes(position: Position, feature_row: pd.Series | None) -> None:
    """Advance deferred learned management modes using the environment rules.

    Args:
        position: Open position whose non-overridden modes may advance.
        feature_row: Current swing features used to confirm management changes.
    """
    sl_rank = {"fixed": 0, "breakeven": 1, "trailing": 2}
    tp_rank = {"fixed": 0, "breakeven": 1, "trailing": 2}
    if not position.sl_mode_overridden:
        desired = _default_sl_mode(position, feature_row)
        if sl_rank.get(desired, 0) > sl_rank.get(position.sl_mode, 0):
            position.sl_mode = desired

    if not position.tp_mode_overridden:
        initial_stop = (
            position.sl_initial_price
            if position.sl_initial_price is not None
            else position.sl_price
        )
        if initial_stop is not None and abs(position.entry_price - float(initial_stop)) > 0.0:
            risk_distance = abs(position.entry_price - float(initial_stop))
            if position.best_favorable >= 0.5 * risk_distance:
                current_swing = _finite_feature(
                    feature_row,
                    "last_swing_high" if position.direction == 1 else "last_swing_low",
                )
                entry_swing = (
                    position.entry_last_swing_high
                    if position.direction == 1
                    else position.entry_last_swing_low
                )
                desired = (
                    "trailing"
                    if current_swing is not None
                    and entry_swing is not None
                    and (
                        current_swing > entry_swing
                        if position.direction == 1
                        else current_swing < entry_swing
                    )
                    else "breakeven"
                )
                if tp_rank.get(desired, 0) > tp_rank.get(position.tp_mode, 0):
                    position.tp_mode = desired


def _apply_tp_management(
    position: Position,
    settings: BacktestSettings,
    state: BacktestState,
    feature_row: pd.Series | None,
    *,
    bar_index: int,
    bar_time: pd.Timestamp,
    next_bar_time: pd.Timestamp | None,
    current_price: float,
) -> None:
    """Apply the selected TP breakeven/trailing behavior after current triggers.

    Args:
        position: Open position whose target levels may be updated.
        settings: Backtest execution and management settings.
        state: Mutable account and trade-event state.
        feature_row: Current structural features for trailing references.
        bar_index: Current bar index in the backtest.
        bar_time: Timestamp for the bar being processed.
        next_bar_time: Timestamp of the next bar, if available.
        current_price: Price used to ensure updated targets remain ahead.
    """
    if position.tp_mode == "breakeven" and not position.tp_breakeven_done:
        initial_stop = (
            position.sl_initial_price
            if position.sl_initial_price is not None
            else position.sl_price
        )
        if initial_stop is not None:
            risk_distance = abs(position.entry_price - float(initial_stop))
            if risk_distance > 0.0:
                new_target = position.entry_price + (
                    position.direction * settings.tp_breakeven_alpha * risk_distance
                )
                for slot in (1, 2, 3):
                    bit = 1 << (slot - 1)
                    attr = f"tp{slot}_price"
                    current_target = getattr(position, attr)
                    if position.tp_hit_mask & bit or current_target is None:
                        continue
                    position.tp_breakeven_done = True
                    tightens = position.direction * (new_target - float(current_target)) < 0.0
                    still_ahead = position.direction * (new_target - current_price) > 0.0
                    if tightens and still_ahead:
                        setattr(position, attr, new_target)
                        state.trade_log.append(
                            {
                                "type": "tp_update",
                                "position_id": position.position_id,
                                "time": bar_time,
                                "effective_time": next_bar_time,
                                "direction": position.direction,
                                "tp_slot": slot,
                                "previous_price": float(current_target),
                                "price": new_target,
                                "mode": position.tp_mode,
                                "reference": "legacy_tp_pullback_initial_r_v1",
                                "reference_price": float(initial_stop),
                                "reason": "favorable_excursion_reached_alpha_initial_r",
                                "bar": bar_index,
                            }
                        )
                    break

    if position.tp_mode != "trailing":
        return
    reference = "last_swing_high" if position.direction == 1 else "last_swing_low"
    swing = _finite_feature(feature_row, reference)
    if swing is None or position.direction * (swing - current_price) <= 0:
        return
    increment = float(settings.cost_model.point_size)
    scaled = swing / increment
    candidate = (
        float(np.ceil(scaled - 1e-12) * increment)
        if position.direction == 1
        else float(np.floor(scaled + 1e-12) * increment)
    )
    if position.direction * (candidate - current_price) <= 0.0:
        return
    for slot in (1, 2, 3):
        if position.tp_hit_mask & (1 << (slot - 1)):
            continue
        attr = f"tp{slot}_price"
        current_target = getattr(position, attr)
        if current_target is None:
            continue
        if position.direction * (candidate - float(current_target)) > 0.0:
            overtakes = any(
                not (position.tp_hit_mask & (1 << (later - 1)))
                and getattr(position, f"tp{later}_price") is not None
                and position.direction * (candidate - float(getattr(position, f"tp{later}_price")))
                >= -max(1e-4, increment / 2.0)
                for later in range(slot + 1, 4)
            )
            if overtakes:
                return
            setattr(position, attr, candidate)
            state.trade_log.append(
                {
                    "type": "tp_update",
                    "position_id": position.position_id,
                    "time": bar_time,
                    "effective_time": next_bar_time,
                    "direction": position.direction,
                    "tp_slot": slot,
                    "previous_price": float(current_target),
                    "price": candidate,
                    "mode": position.tp_mode,
                    "reference": reference,
                    "reference_price": swing,
                    "reason": "new_confirmed_favorable_swing",
                    "bar": bar_index,
                }
            )
        break
    reorder_remaining_targets(position, point_size=increment, price_tolerance=1e-4)


def _record_target_slot(
    state: BacktestState,
    settings: BacktestSettings,
    broker: Broker,
    position: Position,
    *,
    bar_index: int,
    slot: int,
    quote: tuple[float, float],
    fill_time: pd.Timestamp,
    session: int,
    metadata: dict[str, Any] | None = None,
    bar_duration: pd.Timedelta | None = None,
) -> None:
    """Record a target fill and update the position and account state.

    Args:
        state: Mutable backtest account and event-log state.
        settings: Backtest settings used for trade accounting.
        broker: Broker model used to apply the close fill.
        position: Position being reduced or closed by the target.
        bar_index: Index of the bar containing the target event.
        slot: Target slot number that filled.
        quote: Bid and ask used to execute the close.
        fill_time: Event time assigned to the target fill.
        session: Current session identifier.
        metadata: Optional execution provenance attached to the event.
        bar_duration: Optional interval used to bound bar-level event timing.
    """
    remaining_slots = [
        candidate for candidate in _active_target_slots(position) if candidate > slot
    ]
    close_size = target_close_size(position, slot, is_final=not remaining_slots)
    record: dict[str, Any] = {
        "type": "tp_close" if close_size >= position.size - 1e-9 else "tp_partial_close",
        "reason": f"structure_tp{slot}",
        "bar": bar_index,
        "time": fill_time,
        "tp_slot": slot,
        **(metadata or {}),
    }
    if bar_duration is not None:
        record.update(
            {
                "event_time_start": fill_time,
                "event_time_end": fill_time + bar_duration,
                "time_precision": "bar_interval",
            }
        )
    state.current_execution_meta = dict(metadata or {})
    _record_close(
        state,
        settings,
        broker,
        position,
        quote,
        record,
        session,
        size=close_size,
    )
    position.tp_hit_mask |= 1 << (slot - 1)
    setattr(position, f"tp{slot}_price", None)
    if state.position is position:
        next_slots = _active_target_slots(position)
        position.tp_price = getattr(position, f"tp{next_slots[0]}_price") if next_slots else None


def _tick_touch_quote(
    settings: BacktestSettings,
    bar_time: pd.Timestamp,
    direction: int,
    level: float,
    entry_time: pd.Timestamp | None,
    bar_duration: pd.Timedelta,
) -> tuple[float, float]:
    """Fill quote for a stop or target that OHLC reached with no crossing tick.

    Mirrors the environment's rule: the nearest tick in the bar window, within the
    wait cap; the level quote when no such tick exists or when the tick is better
    than the level for the position.

    Args:
        settings: Backtest settings holding the tick book and wait cap.
        bar_time: Start of the bar whose OHLC reached the level.
        direction: Signed position direction.
        level: Stop or target price.
        entry_time: Position entry time, a lower bound for the window.
        bar_duration: Bar length.

    Returns:
        ``(bid, ask)`` of the fill.
    """
    book = settings.tickbook
    if book is None:
        return protective_level_fill_quote(direction, level, settings.cost_model)
    quote = nearest_exit_tick_quote(
        book,
        pd.Timestamp(bar_time),
        direction,
        level,
        bar_minutes=max(1, int(round(bar_duration.total_seconds() / 60.0))),
        earliest_time=entry_time,
        max_gap_ns=settings.max_tick_quote_wait_ms * 1_000_000,
    )
    if quote is None:
        return protective_level_fill_quote(direction, level, settings.cost_model)
    bid, ask = quote
    exit_price = bid if direction == 1 else ask
    tick_is_worse = exit_price <= level if direction == 1 else exit_price >= level
    if not tick_is_worse:
        return protective_level_fill_quote(direction, level, settings.cost_model)
    return quote
