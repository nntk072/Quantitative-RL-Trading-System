"""Protective exits, account guardrails, and session-close handling."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from market_data.loading.ticks import TickExecutionUnavailable, resolve_tick_exit
from trading.execution import (
    Broker,
    CostModel,
    bar_stop_trigger_price,
)
from trading.risk import (
    FTMOGuardrails,
)

from .accounting import _record_close, stamp_exit
from .runtime import BacktestSettings, BacktestState

ExecutionEvent = tuple[tuple[float, float], pd.Timestamp, str, dict[str, Any]]
ResolveExecution = Callable[[], ExecutionEvent]


def process_protective_and_account_events(
    state: BacktestState,
    settings: BacktestSettings,
    broker: Broker,
    guardrails: FTMOGuardrails,
    bars: pd.DataFrame,
    row: pd.Series,
    *,
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
) -> bool:
    """Apply protective exits, guardrail liquidation, and session-end close."""
    position = state.position
    tick_hit: tuple[str, pd.Timestamp, float, float, dict[str, Any]] | None = None
    if (
        position is not None
        and position_active_in_bar
        and settings.tickbook is not None
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

    if tick_hit is not None and state.position is not None:
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
    if (
        (settings.tick_execution_required or settings.randomized_fill_latency_ms > 0)
        and position is not None
        and tick_hit is None
    ):
        sl_touched = position.sl_price is not None and (
            (position.direction == 1 and float(row["low"]) <= position.sl_price)
            or (position.direction == -1 and float(row["high"]) >= position.sl_price)
        )
        tp_touched = position.tp_price is not None and (
            (position.direction == 1 and float(row["high"]) >= position.tp_price)
            or (position.direction == -1 and float(row["low"]) <= position.tp_price)
        )
        if sl_touched or tp_touched:
            raise TickExecutionUnavailable(
                "OHLC indicates a protective level was reached, but no matching "
                "tick trigger was found; candle fallback is disabled"
            )

    position = state.position
    if (
        position is not None
        and position_active_in_bar
        and full_bar_available_after_entry
        and tick_hit is None
    ):
        sl_hit = False
        if position.sl_price is not None:
            if position.direction == 1 and float(row["low"]) <= position.sl_price:
                sl_hit = True
            elif position.direction == -1 and float(row["high"]) >= position.sl_price:
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

    position = state.position
    tp_hit = False
    if (
        position is not None
        and position_active_in_bar
        and full_bar_available_after_entry
        and tick_hit is None
        and position.tp_price is not None
    ):
        if position.direction == 1 and float(row["high"]) >= position.tp_price:
            tp_hit = True
        elif position.direction == -1 and float(row["low"]) <= position.tp_price:
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

    reason = guardrails.breach_reason(state.account)
    if reason and session not in state.breached_sessions:
        state.breached_sessions.add(session)
        state.breach_log.append(reason)
        state.breach_events.append(
            {
                "time": bar_time,
                "session_id": session,
                "reason": reason,
                "equity": state.account.equity,
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

    last_ny = is_last_ny_bar(bars, i, is_ny)
    if settings.block_overnight and last_ny and state.position is not None:
        session_close_time = bar_time + bar_duration
        if settings.tick_execution_required or settings.randomized_fill_latency_ms > 0:
            session_quote, session_fill_time, session_source, session_execution_meta = (
                fill_quote_event(
                    session_close_time,
                    row,
                    settings.cost_model,
                    settings.tickbook,
                    rng=execution_rng,
                    randomized_fill_latency_ms=settings.randomized_fill_latency_ms,
                    max_tick_quote_wait_ms=settings.max_tick_quote_wait_ms,
                    tick_execution_required=settings.tick_execution_required,
                )
            )
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
                "time": session_fill_time,
                "fill_time": session_fill_time,
                "fill_quote_source": session_source,
                **session_execution_meta,
            },
            session,
        )
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
    """Realize any remaining position at the final bar-close valuation point."""
    if state.position is None:
        return

    last_row = bars.iloc[-1]
    last_time = bar_times[-1]
    terminal_close_time = last_time + bar_duration
    if settings.tick_execution_required or settings.randomized_fill_latency_ms > 0:
        last_fq, terminal_close_time, terminal_source, terminal_execution_meta = fill_quote_event(
            terminal_close_time,
            last_row,
            settings.cost_model,
            settings.tickbook,
            rng=execution_rng,
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
    pnl, fill_price = broker.close_position(state.account, position, last_fq)
    record = {
        "type": "eod_close",
        "pnl": pnl,
        "price": fill_price,
        "bar": len(bars) - 1,
        "time": terminal_close_time,
        "fill_time": terminal_close_time,
        "fill_quote_source": terminal_source,
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
