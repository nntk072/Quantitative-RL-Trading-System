"""Fill accounting and position-close recording for backtests."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import pandas as pd

from trading.execution import (
    Broker,
    Position,
    adverse_tick_fill_quote,
)
from trading.policy import TradingPolicyConfig, build_payout_reset_event

from .runtime import BacktestSettings, BacktestState

ExecutionEvent = tuple[tuple[float, float], pd.Timestamp, str, dict[str, Any]]
ResolveExecution = Callable[[], ExecutionEvent]


def process_repeated_payout(
    state: BacktestState,
    policy: TradingPolicyConfig | None,
    event_time: Any,
) -> dict[str, Any] | None:
    """Apply a flat realized-balance payout and reset operating capital."""
    if policy is None or not policy.repeated_payout or state.position is not None:
        return None
    event = build_payout_reset_event(
        balance=state.account.balance,
        policy=policy,
        cycle=state.cycle_count,
        event_time=event_time,
    )
    if event is None:
        return None
    payout = float(event["payout"])
    state.cumulative_payouts += payout
    state.cycle_successes += 1
    state.payout_events.append(dict(event))
    state.cycle_events.append({**event, "outcome": "success"})
    state.trade_log.append(dict(event))
    state.cycle_count += 1
    state.account.reset_operating_balance(policy.operating_balance)
    return event


def record_repeated_cycle_failure(
    state: BacktestState,
    event: Mapping[str, Any],
) -> dict[str, Any]:
    """Record one terminal repeated-payout cycle failure after an account breach."""
    failure = {
        "type": "cycle_failure",
        "time": event.get("time"),
        "cycle": int(state.cycle_count),
        "outcome": "failure",
        "reason": event.get("reason", "account_breach"),
        "equity": float(state.account.equity),
        "cumulative_payouts": float(state.cumulative_payouts),
        "total_economic_value": float(state.account.equity + state.cumulative_payouts),
    }
    state.cycle_failures += 1
    state.cycle_events.append(failure)
    state.trade_log.append(dict(failure))
    return failure


def stamp_exit(
    state: BacktestState,
    settings: BacktestSettings,
    pos: Position,
    record: dict[str, Any],
    fill_price: float,
) -> None:
    """Attach one exactly-once fill and completed-position accounting row.

    Args:
        state: State object read or updated by the operation.
        settings: Settings used by the operation described above.
        pos: Pos used by the operation described above.
        record: Key-value data used for the record.
        fill_price: Numeric value used for the fill price.
    """
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
    *,
    size: float | None = None,
) -> None:
    """Record close.

    Args:
        state: State object read or updated by the operation.
        settings: Settings used by the operation described above.
        broker: Broker used by the operation described above.
        position: Position used by the operation described above.
        quote: Items supplied for the quote, in input order.
        record: Key-value data used for the record.
        session: Session identifier used by the operation.
        size: Optional position quantity to close; ``None`` closes all remaining size.
    """
    if record.get("fill_quote_source") == "tick":
        quote = adverse_tick_fill_quote(
            quote,
            int(position.direction),
            settings.tick_fill_slippage_points,
            opening=False,
        )
    pnl, fill_price = broker.close_position(state.account, position, quote, size=size)
    record["pnl"] = pnl
    record["price"] = fill_price
    record["equity"] = state.account.equity
    stamp_exit(state, settings, position, record, fill_price)
    state.trade_log.append(record)
    state.sessions_with_trades.add(session)
    if position.size <= 1e-9:
        state.position = None
