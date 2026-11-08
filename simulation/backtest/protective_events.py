"""Protective exits, account guardrails, and session-close handling."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import numpy as np
import pandas as pd

from market_data.loading.ticks import (
    TickExecutionUnavailable,
    event_keyed_execution_rng,
    resolve_tick_execution_by_deadline,
    resolve_tick_exit,
)
from trading.execution import (
    FILL_COST_PROVENANCE_SCHEMA_VERSION,
    Broker,
    CostModel,
    Position,
    adverse_tick_fill_quote,
    bar_stop_trigger_price,
    exit_side_bar_range,
)
from trading.positions import reorder_remaining_targets, target_close_size
from trading.risk import (
    RISK_BREACH_EVENT_SCHEMA_V1,
    FTMOGuardrails,
    adverse_position_loss_limit_usd,
    breakeven_stop_price,
    confirmed_swing_trailing_stop_price,
    guardrail_breach_scope,
)

from .accounting import _record_close, stamp_exit
from .runtime import BacktestSettings, BacktestState

ExecutionEvent = tuple[tuple[float, float], pd.Timestamp, str, dict[str, Any]]
ResolveExecution = Callable[[], ExecutionEvent]


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


def process_protective_and_account_events(
    state: BacktestState,
    settings: BacktestSettings,
    broker: Broker,
    guardrails: FTMOGuardrails,
    bars: pd.DataFrame,
    row: pd.Series,
    *,
    feature_row: pd.Series | None = None,
    i: int,
    bar_time: pd.Timestamp,
    bar_duration: pd.Timedelta,
    session: int,
    is_ny: bool,
    bar_quote: tuple[float, float],
    entry_time: pd.Timestamp | None,
    position_active_in_bar: bool,
    full_bar_available_after_entry: bool,
    execution_rng: np.random.Generator,
    resolve_bar_execution: ResolveExecution,
    fill_quote_event: Callable[..., ExecutionEvent],
    sl_tp_fill_quote: Callable[[int, float, CostModel], tuple[float, float]],
    bar_spread_price_units: Callable[[pd.Series, CostModel], float | None],
    is_last_ny_bar: Callable[[pd.DataFrame, int, bool], bool],
    eod_guard_due: bool,
) -> bool:
    """Apply protective exits, guardrail liquidation, and session-end close.

    Args:
        state: State object read or updated by the operation.
        settings: Settings used by the operation described above.
        broker: Broker used by the operation described above.
        guardrails: Guardrails used by the operation described above.
        bars: Market bars to process.
        row: Row index or record being processed.
        feature_row: Causal feature values for the completed decision bar.
        i: Numeric value used for the i.
        bar_time: Bar time used by the operation described above.
        bar_duration: Bar duration used by the operation described above.
        session: Session identifier used by the operation.
        is_ny: Whether to enable or require the is ny.
        bar_quote: Items supplied for the bar quote, in input order.
        entry_time: Entry time used by the operation described above.
        position_active_in_bar: Whether to enable or require the position active in bar.
        full_bar_available_after_entry: Whether to enable or require the full bar available after entry.
        execution_rng: Execution rng used by the operation described above.
        resolve_bar_execution: Resolve bar execution used by the operation described above.
        fill_quote_event: Fill quote event used by the operation described above.
        sl_tp_fill_quote: Items supplied for the sl tp fill quote, in input order.
        bar_spread_price_units: Tabular data used for the bar spread price units.
        is_last_ny_bar: Tabular data used for the is last ny bar.
        eod_guard_due: Whether this NY bar is followed by skipped bars before the next NY bar.

    Returns:
        Whether process protective and account events meets the requested condition.
    """
    tick_only_execution = (
        settings.tick_execution_required or settings.randomized_fill_latency_ms > 0
    )
    effective_stop_time = pd.Timestamp(bars.index[i + 1]) if i + 1 < len(bars) else None
    position = state.position
    tick_hit: tuple[str, pd.Timestamp, float, float, dict[str, Any]] | None = None
    multi_target_position = position is not None and any(
        getattr(position, f"tp{slot}_price") is not None for slot in (1, 2, 3)
    )
    multi_target_tick_fill = False
    if (
        multi_target_position
        and position is not None
        and position_active_in_bar
        and settings.tickbook is not None
    ):
        active_slots = _active_target_slots(position)
        position.tp_price = (
            getattr(position, f"tp{active_slots[0]}_price") if active_slots else None
        )
        cursor_time = entry_time
        while state.position is position and position.size > 0.0:
            if settings.tick_execution_required or settings.randomized_fill_latency_ms > 0:
                resolved_exit = resolve_tick_exit(
                    settings.tickbook,
                    bar_time,
                    int(position.direction),
                    None if position.sl_price is None else float(position.sl_price),
                    None if position.tp_price is None else float(position.tp_price),
                    execution_rng,
                    bar_minutes=max(1, int(round(bar_duration.total_seconds() / 60.0))),
                    max_latency_ns_exclusive=int(settings.randomized_fill_latency_ms * 1_000_000),
                    max_quote_wait_ns=settings.max_tick_quote_wait_ms * 1_000_000,
                    earliest_time=cursor_time,
                    event_seed=settings.execution_seed,
                    server_side_protective=settings.server_side_protective_orders,
                )
                if resolved_exit is None:
                    break
                target_quote = (resolved_exit.quote.bid, resolved_exit.quote.ask)
                fill_time = resolved_exit.quote.tick_time
                metadata = {
                    "order_submission_time": resolved_exit.trigger_time,
                    "execution_order_time": resolved_exit.quote.order_time,
                    "execution_arrival_time": resolved_exit.quote.arrival_time,
                    "execution_latency_ns": resolved_exit.quote.latency_ns,
                    "actual_tick_time": resolved_exit.quote.tick_time,
                    "fill_quote_source": "tick",
                }
                kind = resolved_exit.kind
            else:
                legacy_hit = settings.tickbook.delayed_exit_event(
                    bar_time,
                    int(position.direction),
                    None if position.sl_price is None else float(position.sl_price),
                    None if position.tp_price is None else float(position.tp_price),
                    pd.Timedelta(milliseconds=settings.fill_delay_ms),
                    earliest_time=cursor_time,
                )
                if legacy_hit is None:
                    break
                kind, fill_time, bid, ask = legacy_hit
                target_quote = (bid, ask)
                metadata = {
                    "order_submission_time": fill_time
                    - pd.Timedelta(milliseconds=settings.fill_delay_ms),
                    "execution_order_time": fill_time
                    - pd.Timedelta(milliseconds=settings.fill_delay_ms),
                    "execution_arrival_time": fill_time,
                    "execution_latency_ns": int(
                        pd.Timedelta(milliseconds=settings.fill_delay_ms).value
                    ),
                    "actual_tick_time": fill_time,
                    "fill_quote_source": "tick",
                }
            multi_target_tick_fill = True
            if kind == "sl":
                _record_close(
                    state,
                    settings,
                    broker,
                    position,
                    target_quote,
                    {
                        "type": "stop_close",
                        "reason": "structure_sl",
                        "bar": i,
                        "time": fill_time,
                        **metadata,
                    },
                    session,
                )
                break
            active_slots = _active_target_slots(position)
            if not active_slots:
                break
            target_slot = active_slots[0]
            _record_target_slot(
                state,
                settings,
                broker,
                position,
                bar_index=i,
                slot=target_slot,
                quote=target_quote,
                fill_time=fill_time,
                session=session,
                metadata=metadata,
            )
            cursor_time = fill_time

    if (
        position is not None
        and position_active_in_bar
        and settings.tickbook is not None
        and not multi_target_position
        and (position.sl_price is not None or position.tp_price is not None)
    ):
        if settings.tick_execution_required or settings.randomized_fill_latency_ms > 0:
            resolved_exit = resolve_tick_exit(
                settings.tickbook,
                bar_time,
                int(position.direction),
                None if position.sl_price is None else float(position.sl_price),
                None if position.tp_price is None else float(position.tp_price),
                execution_rng,
                bar_minutes=max(1, int(round(bar_duration.total_seconds() / 60.0))),
                max_latency_ns_exclusive=int(settings.randomized_fill_latency_ms * 1_000_000),
                max_quote_wait_ns=settings.max_tick_quote_wait_ms * 1_000_000,
                earliest_time=entry_time,
                event_seed=settings.execution_seed,
                server_side_protective=settings.server_side_protective_orders,
            )
            if resolved_exit is not None:
                quote = resolved_exit.quote
                tick_hit = (
                    resolved_exit.kind,
                    quote.tick_time,
                    quote.bid,
                    quote.ask,
                    {
                        "order_submission_time": resolved_exit.trigger_time,
                        "execution_order_time": quote.order_time,
                        "execution_arrival_time": quote.arrival_time,
                        "execution_latency_ns": quote.latency_ns,
                        "actual_tick_time": quote.tick_time,
                        "fill_quote_source": "tick",
                    },
                )
        else:
            legacy_hit = settings.tickbook.delayed_exit_event(
                bar_time,
                int(position.direction),
                None if position.sl_price is None else float(position.sl_price),
                None if position.tp_price is None else float(position.tp_price),
                pd.Timedelta(milliseconds=settings.fill_delay_ms),
                earliest_time=entry_time,
            )
            if legacy_hit is not None:
                tick_hit = (*legacy_hit, {"fill_quote_source": "tick"})

    if tick_hit is not None and state.position is not None and not multi_target_position:
        kind, fill_time, bid, ask, tick_execution_meta = tick_hit
        state.current_execution_meta = tick_execution_meta
        _record_close(
            state,
            settings,
            broker,
            state.position,
            (bid, ask),
            {
                "type": "stop_close" if kind == "sl" else "tp_close",
                "reason": "structure_sl" if kind == "sl" else "structure_tp",
                "bar": i,
                "time": fill_time,
                **tick_execution_meta,
            },
            session,
        )

    position = state.position
    exit_low = float(row["low"])
    exit_high = float(row["high"])
    if position is not None:
        spread_price = bar_spread_price_units(row, settings.cost_model)
        exit_low, exit_high = exit_side_bar_range(
            int(position.direction),
            exit_low,
            exit_high,
            spread_price,
            settings.cost_model,
        )
    if (
        (settings.tick_execution_required or settings.randomized_fill_latency_ms > 0)
        and position is not None
        and (tick_hit is None or multi_target_tick_fill)
        and full_bar_available_after_entry
    ):
        sl_touched = position.sl_price is not None and (
            exit_low <= position.sl_price
            if position.direction == 1
            else exit_high >= position.sl_price
        )
        active_targets = (
            [getattr(position, f"tp{slot}_price") for slot in _active_target_slots(position)]
            if multi_target_position
            else [position.tp_price]
        )
        tp_touched = any(
            target is not None
            and (
                (position.direction == 1 and exit_high >= target)
                or (position.direction == -1 and exit_low <= target)
            )
            for target in active_targets
        )
        if sl_touched or tp_touched:
            target_text = ", ".join(
                f"tp{slot}={getattr(position, f'tp{slot}_price')}" for slot in (1, 2, 3)
            )
            raise TickExecutionUnavailable(
                "OHLC indicates a protective level was reached, but no matching "
                "tick trigger was found; candle fallback is disabled "
                f"(bar_idx={i}, bar_time={bar_time.isoformat()}, "
                f"direction={position.direction}, open={row['open']}, "
                f"high={row['high']}, low={row['low']}, close={row['close']}, "
                f"exit_low={exit_low}, exit_high={exit_high}, "
                f"sl={position.sl_price}, {target_text})"
            )

    position = state.position
    if (
        position is not None
        and position_active_in_bar
        and full_bar_available_after_entry
        and tick_hit is None
        and not multi_target_tick_fill
        and not tick_only_execution
    ):
        sl_hit = False
        if position.sl_price is not None:
            if position.direction == 1 and exit_low <= position.sl_price:
                sl_hit = True
            elif position.direction == -1 and exit_high >= position.sl_price:
                sl_hit = True

        if sl_hit:
            assert position.sl_price is not None
            stop_price = float(position.sl_price)
            raw_spread = bar_spread_price_units(row, settings.cost_model)
            opening_spread = settings.cost_model.spread_points if raw_spread is None else raw_spread
            stop_price = bar_stop_trigger_price(
                position.direction,
                stop_price,
                float(row["open"]),
                opening_spread,
            )
            _record_close(
                state,
                settings,
                broker,
                position,
                sl_tp_fill_quote(position.direction, stop_price, settings.cost_model),
                {
                    "type": "stop_close",
                    "reason": "structure_sl",
                    "bar": i,
                    "time": bar_time,
                    "event_time_start": bar_time,
                    "event_time_end": bar_time + bar_duration,
                    "time_precision": "bar_interval",
                },
                session,
            )

    position = state.position
    tp_hit = False
    if (
        multi_target_position
        and position is not None
        and position_active_in_bar
        and full_bar_available_after_entry
        and not multi_target_tick_fill
        and not tick_only_execution
    ):
        for slot in _active_target_slots(position):
            if state.position is not position:
                break
            target_price = float(getattr(position, f"tp{slot}_price"))
            target_hit = (position.direction == 1 and exit_high >= target_price) or (
                position.direction == -1 and exit_low <= target_price
            )
            if target_hit:
                _record_target_slot(
                    state,
                    settings,
                    broker,
                    position,
                    bar_index=i,
                    slot=slot,
                    quote=sl_tp_fill_quote(
                        int(position.direction), target_price, settings.cost_model
                    ),
                    fill_time=bar_time,
                    session=session,
                    bar_duration=bar_duration,
                )

    if (
        position is not None
        and position_active_in_bar
        and full_bar_available_after_entry
        and tick_hit is None
        and not multi_target_position
        and position.tp_price is not None
        and not tick_only_execution
    ):
        if position.direction == 1 and exit_high >= position.tp_price:
            tp_hit = True
        elif position.direction == -1 and exit_low <= position.tp_price:
            tp_hit = True

    if tp_hit and state.position is not None:
        position = state.position
        assert position.tp_price is not None
        _record_close(
            state,
            settings,
            broker,
            position,
            sl_tp_fill_quote(position.direction, position.tp_price, settings.cost_model),
            {
                "type": "tp_close",
                "reason": "structure_tp",
                "bar": i,
                "time": bar_time,
                "event_time_start": bar_time,
                "event_time_end": bar_time + bar_duration,
                "time_precision": "bar_interval",
            },
            session,
        )
    elif (
        not settings.use_structure_sl_tp
        and settings.take_profit_per_trade_usd is not None
        and state.position is not None
        and state.account.open_pnl >= abs(settings.take_profit_per_trade_usd)
    ):
        fq, execution_time, fill_source, _ = resolve_bar_execution()
        _record_close(
            state,
            settings,
            broker,
            state.position,
            fq,
            {
                "type": "tp_close",
                "reason": "take_profit_per_trade",
                "bar": i,
                "time": execution_time,
                "decision_time": bar_time,
                "fill_time": execution_time,
                "fill_quote_source": fill_source,
            },
            session,
        )

    # Match TradingEnv: protective stops and targets take precedence; an
    # EMA-21 exit is considered from the completed bar only while a position
    # with the selected EMA exit remains open.
    position = state.position
    ema_value = (
        float(feature_row.get("ema_21", np.nan)) if feature_row is not None else float("nan")
    )
    if (
        position is not None
        and position.exit_mode == "ema_21"
        and position_active_in_bar
        and full_bar_available_after_entry
        and np.isfinite(ema_value)
        and position.stop_distance > 1e-12
    ):
        runner_waiting = position.ema_runner_fraction > 0.0 and (
            position.tp_hit_mask == 0
            or any(getattr(position, f"tp{slot}_price") is not None for slot in (1, 2, 3))
        )
        if not runner_waiting:
            favorable = (
                float(row["high"]) - position.entry_price
                if position.direction == 1
                else position.entry_price - float(row["low"])
            )
            position.best_favorable = max(float(position.best_favorable), favorable)
            crossed = (
                float(row["close"]) < ema_value
                if position.direction == 1
                else float(row["close"]) > ema_value
            )
            if position.best_favorable + 1e-12 >= position.stop_distance and crossed:
                if tick_only_execution:
                    close_quote, fill_time, fill_source, metadata = resolve_bar_execution()
                else:
                    close_quote = bar_quote
                    fill_time = bar_time + bar_duration
                    fill_source = "bar_close"
                    metadata = {}
                _record_close(
                    state,
                    settings,
                    broker,
                    position,
                    close_quote,
                    {
                        "type": "close",
                        "reason": "ema_21_exit",
                        "bar": i,
                        "time": fill_time,
                        "decision_time": bar_time,
                        "fill_time": fill_time,
                        "fill_quote_source": fill_source,
                        **metadata,
                    },
                    session,
                )

    position = state.position
    if (
        position is not None
        and settings.eod_risk is not None
        and position_active_in_bar
        and entry_time is not None
    ):
        age_hours = (bar_time - entry_time).total_seconds() / 3600.0
        max_age_hours = float(settings.eod_risk.get("max_age_hours", 8.0))
        if age_hours > max_age_hours:
            fq, execution_time, fill_source, _ = resolve_bar_execution()
            _record_close(
                state,
                settings,
                broker,
                position,
                fq,
                {
                    "type": "eod_close",
                    "reason": "max_age",
                    "bar": i,
                    "time": bar_time,
                    "decision_time": bar_time,
                    "fill_time": execution_time,
                    "fill_quote_source": fill_source,
                },
                session,
            )

    position = state.position
    if position is not None and position_active_in_bar and settings.eod_risk is not None:
        favorable = (
            float(row["high"]) - position.entry_price
            if position.direction == 1
            else position.entry_price - float(row["low"])
        )
        progress_threshold = float(settings.eod_risk.get("progress_threshold_atr", 0.25)) * float(
            position.entry_atr or 0.0
        )
        if (
            progress_threshold > 0.0
            and favorable - position.last_progress_favorable >= progress_threshold
        ):
            position.last_progress_favorable = favorable
            position.stale_counter = 0
        else:
            position.stale_counter += 1

    if position is not None and position_active_in_bar and full_bar_available_after_entry:
        if position.direction == 1:
            favorable = max(0.0, float(row["high"]) - position.entry_price)
            adverse = max(0.0, position.entry_price - float(row["low"]))
        else:
            favorable = max(0.0, position.entry_price - float(row["low"]))
            adverse = max(0.0, float(row["high"]) - position.entry_price)
        position.best_favorable = max(position.best_favorable, favorable)
        position.mfe = max(position.mfe, favorable)
        position.mae = max(position.mae, adverse)
        _advance_management_modes(position, feature_row)
        _apply_tp_management(
            position,
            settings,
            state,
            feature_row,
            bar_index=i,
            bar_time=bar_time,
            next_bar_time=effective_stop_time,
            current_price=float(row["close"]),
        )

    position = state.position
    if (
        position is not None
        and position.sl_mode in {"breakeven", "trailing"}
        and position_active_in_bar
        and full_bar_available_after_entry
    ):
        eod = settings.eod_risk or {}
        new_stop = breakeven_stop_price(
            direction=position.direction,
            entry_price=position.entry_price,
            initial_stop_price=position.sl_initial_price,
            current_stop_price=position.sl_price,
            best_favorable_points=position.best_favorable,
            trigger_r=float(eod.get("breakeven_trigger_r", 0.0)),
            buffer_points=float(eod.get("breakeven_buffer_pts", 2.0)),
        )
        if new_stop is not None:
            previous_stop = position.sl_price
            position.sl_price = new_stop
            position.breakeven_done = True
            state.trade_log.append(
                {
                    "type": "sl_update",
                    "position_id": position.position_id,
                    "time": bar_time,
                    "effective_time": effective_stop_time,
                    "direction": position.direction,
                    "previous_price": previous_stop,
                    "price": new_stop,
                    "reference": "entry",
                    "reference_price": position.entry_price,
                    "bar": i,
                    "buffer_points": float(eod.get("breakeven_buffer_pts", 2.0)),
                    "reason": "breakeven_trigger",
                }
            )

    position = state.position
    if (
        position is not None
        and position.sl_mode == "trailing"
        and position_active_in_bar
        and full_bar_available_after_entry
    ):
        reference = "last_swing_low" if position.direction == 1 else "last_swing_high"
        raw_swing = None if feature_row is None else feature_row.get(reference)
        try:
            swing = float(cast(Any, raw_swing))
        except (TypeError, ValueError):
            swing = float("nan")
        if np.isfinite(swing):
            previous_stop = position.sl_price
            candidate_stop = confirmed_swing_trailing_stop_price(
                direction=position.direction,
                swing_price=swing,
                current_close=float(row["close"]),
                current_stop_price=position.sl_price,
                buffer_points=settings.sl_buffer_pts,
            )
            if candidate_stop is not None:
                position.sl_price = candidate_stop
                state.trade_log.append(
                    {
                        "type": "sl_update",
                        "position_id": position.position_id,
                        "time": bar_time,
                        "effective_time": effective_stop_time,
                        "direction": position.direction,
                        "previous_price": previous_stop,
                        "price": candidate_stop,
                        "reference": reference,
                        "reference_price": swing,
                        "bar": i,
                        "buffer_points": settings.sl_buffer_pts,
                        "reason": "confirmed_swing",
                    }
                )

    position = state.position
    if (
        position is not None
        and position_active_in_bar
        and full_bar_available_after_entry
        and tick_hit is None
        and not multi_target_tick_fill
    ):
        if settings.eod_risk is not None:
            guard = settings.eod_risk
            adverse = (
                position.entry_price - float(row["low"])
                if position.direction == 1
                else float(row["high"]) - position.entry_price
            )
            adverse_usd = max(0.0, adverse) * position.size * settings.contract_size
            cutoff = adverse_position_loss_limit_usd(
                float(guard.get("max_loss_usd", 500.0)),
                float(position.planned_risk_usd or 0.0),
                respect_planned_risk=bool(guard.get("respect_planned_risk", True)),
                planned_risk_multiplier=float(guard.get("planned_risk_mult", 1.1)),
            )
            if adverse_usd >= cutoff:
                fq, execution_time, fill_source, _ = resolve_bar_execution()
                _record_close(
                    state,
                    settings,
                    broker,
                    position,
                    fq,
                    {
                        "type": "eod_close",
                        "reason": "eod_max_loss",
                        "bar": i,
                        "time": execution_time,
                        "decision_time": bar_time,
                        "fill_time": execution_time,
                        "fill_quote_source": fill_source,
                    },
                    session,
                )
        elif settings.max_loss_per_trade_usd is not None and state.account.open_pnl <= -abs(
            settings.max_loss_per_trade_usd
        ):
            fq, execution_time, fill_source, _ = resolve_bar_execution()
            _record_close(
                state,
                settings,
                broker,
                position,
                fq,
                {
                    "type": "stop_close",
                    "reason": "max_loss_cap",
                    "bar": i,
                    "time": execution_time,
                    "decision_time": bar_time,
                    "fill_time": execution_time,
                    "fill_quote_source": fill_source,
                },
                session,
            )

    reason = None if state.year_failed else guardrails.breach_reason(state.account)
    if reason and session not in state.breached_sessions:
        state.breached_sessions.add(session)
        if guardrail_breach_scope(reason) == "rollout":
            state.year_failed = True
        state.breach_log.append(reason)
        state.breach_events.append(
            {
                "schema_version": RISK_BREACH_EVENT_SCHEMA_V1,
                "time": bar_time,
                "detection_time": pd.Timestamp(bar_time) + bar_duration,
                "trade_event_count": len(state.trade_log),
                "session_id": session,
                "reason": reason,
                "equity": state.account.equity,
                "daily_loss": state.account.daily_loss,
            }
        )
        if state.position is not None:
            fq, execution_time, fill_source, _ = resolve_bar_execution()
            _record_close(
                state,
                settings,
                broker,
                state.position,
                fq,
                {
                    "type": "forced_close",
                    "reason": reason,
                    "bar": i,
                    "time": execution_time,
                    "decision_time": bar_time,
                    "fill_time": execution_time,
                    "fill_quote_source": fill_source,
                },
                session,
            )

    position = state.position
    if (
        position is not None
        and eod_guard_due
        and not settings.block_overnight
        and settings.eod_risk is not None
    ):
        # TradingEnv runs the same final-bar guard once more before replaying
        # skipped overnight bars, so preserve that second progress update.
        favorable = (
            float(row["high"]) - position.entry_price
            if position.direction == 1
            else position.entry_price - float(row["low"])
        )
        progress_threshold = float(settings.eod_risk.get("progress_threshold_atr", 0.25)) * float(
            position.entry_atr or 0.0
        )
        if (
            progress_threshold > 0.0
            and favorable - position.last_progress_favorable >= progress_threshold
        ):
            position.last_progress_favorable = favorable
            position.stale_counter = 0
        else:
            position.stale_counter += 1
        if position.stale_counter >= int(settings.eod_risk.get("stale_bars", 60)):
            fq, execution_time, fill_source, _ = resolve_bar_execution()
            _record_close(
                state,
                settings,
                broker,
                position,
                fq,
                {
                    "type": "eod_close",
                    "reason": "stale",
                    "bar": i,
                    "time": bar_time,
                    "decision_time": bar_time,
                    "fill_time": execution_time,
                    "fill_quote_source": fill_source,
                },
                session,
            )

    last_ny = is_last_ny_bar(bars, i, is_ny)
    if settings.block_overnight and last_ny and state.position is not None:
        session_close_time = bar_time + bar_duration
        if settings.tick_execution_required or settings.randomized_fill_latency_ms > 0:
            if not 0.0 <= settings.randomized_fill_latency_ms <= 30.0:
                raise ValueError("randomized_fill_latency_ms must be in [0, 30]")
            if settings.max_tick_quote_wait_ms <= 0:
                raise ValueError("max_tick_quote_wait_ms must be positive")
            if settings.tickbook is None:
                raise TickExecutionUnavailable("tick-only fills require a TickBook")
            execution = resolve_tick_execution_by_deadline(
                settings.tickbook,
                bar_time,
                session_close_time,
                event_keyed_execution_rng(
                    settings.execution_seed,
                    f"scheduled_session_close:{pd.Timestamp(bar_time).value}",
                ),
                max_latency_ns_exclusive=int(settings.randomized_fill_latency_ms * 1_000_000),
                max_quote_wait_ns=settings.max_tick_quote_wait_ms * 1_000_000,
            )
            if execution is None:
                raise TickExecutionUnavailable(
                    "no executable tick between order submission and scheduled session close "
                    f"{session_close_time} within {settings.max_tick_quote_wait_ms}ms"
                )
            session_quote = (execution.bid, execution.ask)
            session_fill_time = execution.tick_time
            session_source = "tick"
            session_execution_meta = {
                "order_submission_time": execution.order_time,
                "execution_order_time": execution.order_time,
                "execution_arrival_time": execution.arrival_time,
                "execution_latency_ns": execution.latency_ns,
                "actual_tick_time": execution.tick_time,
                "fill_quote_source": "tick",
            }
            state.current_execution_meta = session_execution_meta
        else:
            session_quote = bar_quote
            session_fill_time = session_close_time
            session_source = "permitted_session_bar_close"
            session_execution_meta = {}
        _record_close(
            state,
            settings,
            broker,
            state.position,
            session_quote,
            {
                "type": "eod_close",
                "reason": "session_end",
                "bar": i,
                "time": bar_time if session_execution_meta else session_fill_time,
                "fill_time": session_fill_time,
                "fill_quote_source": session_source,
                **session_execution_meta,
            },
            session,
        )
    if last_ny:
        # The EOD floor for the next session uses completed-session equity,
        # after any configured session-end liquidation.
        state.account.record_eod_equity()
    return last_ny


def liquidate_terminal_position(
    state: BacktestState,
    settings: BacktestSettings,
    broker: Broker,
    bars: pd.DataFrame,
    bar_times: pd.DatetimeIndex,
    bar_duration: pd.Timedelta,
    execution_rng: np.random.Generator,
    *,
    fill_quote_event: Callable[..., ExecutionEvent],
    bar_quote: Callable[[pd.Series, CostModel], tuple[float, float]],
) -> None:
    """Realize any remaining position at the final bar-close valuation point.

    Args:
        state: State object read or updated by the operation.
        settings: Settings used by the operation described above.
        broker: Broker used by the operation described above.
        bars: Market bars to process.
        bar_times: Bar times used by the operation described above.
        bar_duration: Bar duration used by the operation described above.
        execution_rng: Execution rng used by the operation described above.
        fill_quote_event: Fill quote event used by the operation described above.
        bar_quote: Tabular data used for the bar quote.
    """
    if state.position is None:
        return

    last_row = bars.iloc[-1]
    last_time = bar_times[-1]
    terminal_close_time = last_time + bar_duration
    if settings.tick_execution_required or settings.randomized_fill_latency_ms > 0:
        terminal_rng = (
            event_keyed_execution_rng(
                settings.execution_seed, f"bar_fill:{terminal_close_time.value}"
            )
            if settings.randomized_fill_latency_ms > 0
            else execution_rng
        )
        last_fq, terminal_close_time, terminal_source, terminal_execution_meta = fill_quote_event(
            terminal_close_time,
            last_row,
            settings.cost_model,
            settings.tickbook,
            rng=terminal_rng,
            randomized_fill_latency_ms=settings.randomized_fill_latency_ms,
            max_tick_quote_wait_ms=settings.max_tick_quote_wait_ms,
            tick_execution_required=settings.tick_execution_required,
        )
        state.current_execution_meta = terminal_execution_meta
    else:
        last_fq = bar_quote(last_row, settings.cost_model)
        terminal_source = "terminal_bar_close"
        terminal_execution_meta = {}

    position = state.position
    pre_execution_quote = tuple(map(float, last_fq))
    terminal_slippage_applied = terminal_source in {
        "tick",
        "terminal_bar_close",
        "bar_open",
    }
    if terminal_slippage_applied:
        last_fq = adverse_tick_fill_quote(
            last_fq,
            int(position.direction),
            settings.tick_fill_slippage_points,
            opening=False,
        )
    pnl, fill_price = broker.close_position(state.account, position, last_fq)
    record = {
        "type": "eod_close",
        "pnl": pnl,
        "price": fill_price,
        "bar": len(bars) - 1,
        "time": terminal_close_time,
        "fill_time": terminal_close_time,
        "fill_quote_source": terminal_source,
        "fill_cost_provenance_schema_version": FILL_COST_PROVENANCE_SCHEMA_VERSION,
        "pre_execution_quote_bid": pre_execution_quote[0],
        "pre_execution_quote_ask": pre_execution_quote[1],
        "broker_execution_quote_bid": float(last_fq[0]),
        "broker_execution_quote_ask": float(last_fq[1]),
        "slippage_points_applied_here": (
            float(settings.tick_fill_slippage_points) if terminal_slippage_applied else 0.0
        ),
        "slippage_applied_here": bool(
            terminal_slippage_applied and settings.tick_fill_slippage_points > 0.0
        ),
        "slippage_application_mode": (
            "transacted_side"
            if terminal_slippage_applied and settings.tick_fill_slippage_points > 0.0
            else "none"
        ),
        "equity": state.account.equity,
        **terminal_execution_meta,
    }
    stamp_exit(state, settings, position, record, fill_price)
    state.trade_log.append(record)
    state.position = None

    if state.equity_curve:
        state.equity_curve[-1] = state.account.equity
    else:
        state.equity_curve.append(state.account.equity)
        state.equity_times.append(pd.Timestamp(last_time) + bar_duration)
