"""Fill accounting and position-close recording for backtests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd

from trading.execution import (
    Broker,
    Position,
)

from .runtime import BacktestSettings, BacktestState

ExecutionEvent = tuple[tuple[float, float], pd.Timestamp, str, dict[str, Any]]
ResolveExecution = Callable[[], ExecutionEvent]


def stamp_exit(
    state: BacktestState,
    settings: BacktestSettings,
    pos: Position,
    record: dict[str, Any],
    fill_price: float,
) -> None:
    """Attach one exactly-once fill and completed-position accounting row."""
    for key, value in state.current_execution_meta.items():
        record.setdefault(key, value)
    record.setdefault("order_submission_time", record.get("decision_time", pos.entry_timestamp))
    if record.get("time_precision") == "bar_interval":
        record.setdefault("fill_time", None)
    else:
        record.setdefault("fill_time", record.get("time"))
    initial = float(pos.initial_size or pos.size)
    close_size = max(0.0, initial - float(pos.filled_size) - float(pos.size))
    pos.filled_size += close_size
    pos.fill_count += 1
    pos.position_id = pos.position_id or f"bt:p{state.position_sequence}"
    record["position_id"] = pos.position_id
    record["fill_id"] = f"{pos.position_id}:f{pos.fill_count}"
    record["size"] = close_size
    record["price"] = float(fill_price)
    record["position_complete"] = bool(pos.size <= 1e-9)
    entry_commission = float(settings.cost_model.total_cost(close_size))
    net_pnl = float(record.get("pnl", 0.0)) - entry_commission
    record["entry_commission_allocated"] = entry_commission
    record["net_pnl"] = net_pnl
    pos.position_net_pnl += net_pnl
    if record["position_complete"]:
        record["position_net_pnl"] = pos.position_net_pnl


def _record_close(
    state: BacktestState,
    settings: BacktestSettings,
    broker: Broker,
    position: Position,
    quote: tuple[float, float],
    record: dict[str, Any],
    session: int,
) -> None:
    pnl, fill_price = broker.close_position(state.account, position, quote)
    record["pnl"] = pnl
    record["price"] = fill_price
    record["equity"] = state.account.equity
    stamp_exit(state, settings, position, record, fill_price)
    state.trade_log.append(record)
    state.sessions_with_trades.add(session)
    state.position = None
