"""Terminal position liquidation for event-driven backtests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from market_data.loading.ticks import TickExecutionUnavailable, last_tick_quote_before
from trading.execution import (
    FILL_COST_PROVENANCE_SCHEMA_VERSION,
    Broker,
    CostModel,
    adverse_tick_fill_quote,
)

from .accounting import stamp_exit
from .runtime import BacktestSettings, BacktestState

ExecutionEvent = tuple[tuple[float, float], pd.Timestamp, str, dict[str, Any]]


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
        # Close at the last tick of the final minute of data. With no tick in that
        # minute, the final bar close is the fill, as in non-tick mode.
        if settings.tickbook is None:
            raise TickExecutionUnavailable("tick-only fills require a TickBook")
        last_tick = last_tick_quote_before(
            settings.tickbook, terminal_close_time, pd.Timedelta(minutes=1)
        )
        if last_tick is not None:
            last_fq = (last_tick.bid, last_tick.ask)
            terminal_close_time = last_tick.tick_time
            terminal_source = "tick"
            terminal_execution_meta = {
                "order_submission_time": last_tick.order_time,
                "execution_order_time": last_tick.order_time,
                "execution_arrival_time": last_tick.arrival_time,
                "execution_latency_ns": last_tick.latency_ns,
                "actual_tick_time": last_tick.tick_time,
                "fill_quote_source": "tick",
            }
        else:
            last_fq = bar_quote(last_row, settings.cost_model)
            terminal_source = "terminal_bar_close"
            terminal_execution_meta = {}
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
