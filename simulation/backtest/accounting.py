"""Fill accounting and position-close recording for backtests."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import pandas as pd

from trading.execution import (
    FILL_COST_PROVENANCE_SCHEMA_VERSION,
    TRADE_CASHFLOW_SCHEMA_VERSION,
    Broker,
    Position,
    adverse_tick_fill_quote,
    undo_adverse_quote_level_slippage,
)
from trading.policy import TradingPolicyConfig, build_payout_reset_event

from .runtime import BacktestSettings, BacktestState

ExecutionEvent = tuple[tuple[float, float], pd.Timestamp, str, dict[str, Any]]
ResolveExecution = Callable[[], ExecutionEvent]


def _needs_adverse_market_slippage(record: Mapping[str, Any]) -> bool:
    """Whether a close record represents a market quote needing slippage.

    Args:
        record: Close-event fields describing the quote source and event type.

    Returns:
        Whether the close quote receives the configured market slippage.
    """
    source = record.get("fill_quote_source")
    if source == "tick":
        return True
    return source in {"bar_open", "terminal_bar_close"} and record.get("type") in {
        "close",
        "eod_close",
        "forced_close",
    }


def process_repeated_payout(
    state: BacktestState,
    policy: TradingPolicyConfig | None,
    event_time: Any,
    *,
    max_drawdown_mode: str,
) -> dict[str, Any] | None:
    """Apply a flat realized-balance payout and reset operating capital.

    Args:
        state: Mutable backtest account and cycle state.
        policy: Repeated-payout settings, if enabled.
        event_time: Timestamp assigned to the payout event.
        max_drawdown_mode: Drawdown mode used to reset the account floor.

    Returns:
        Payout event after reset, or ``None`` when payout conditions are unmet.
    """
    if policy is None or not policy.repeated_payout or state.position is not None:
        return None
    event = build_payout_reset_event(
        balance=state.account.balance,
        policy=policy,
        cycle=state.cycle_count,
        event_time=event_time,
        max_drawdown_mode=max_drawdown_mode,
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
    state.account.reset_operating_balance(
        float(event["balance_after_reset"]), max_drawdown_mode=max_drawdown_mode
    )
    return event


def record_repeated_cycle_failure(
    state: BacktestState,
    event: Mapping[str, Any],
) -> dict[str, Any]:
    """Record one terminal repeated-payout cycle failure after an account breach.

    Args:
        state: Mutable account and repeated-payout cycle state.
        event: Breach event that ended the current cycle.

    Returns:
        Terminal cycle-failure event appended to the cycle and trade ledgers.
    """
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
    contract_size = float(settings.contract_size)
    commission_per_lot = float(settings.cost_model.commission_per_lot)
    exit_commission = float(settings.cost_model.total_cost(close_size))
    gross_price_pnl = (
        (float(fill_price) - float(pos.entry_price))
        * int(pos.direction)
        * close_size
        * contract_size
    )
    record.update(
        {
            "cashflow_schema_version": TRADE_CASHFLOW_SCHEMA_VERSION,
            "direction": int(pos.direction),
            "entry_price": float(pos.entry_price),
            "contract_size": contract_size,
            "commission_per_lot": commission_per_lot,
            "gross_price_pnl": gross_price_pnl,
            "exit_commission": exit_commission,
        }
    )
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
    pre_execution_quote = tuple(map(float, quote))
    slippage_applied_now = _needs_adverse_market_slippage(record)
    slippage_baked_into_quote = record.get("type") in {
        "stop_close",
        "tp_close",
        "tp_partial_close",
    } and (
        record.get("fill_quote_source") == "bar_range_level"
        or record.get("time_precision") == "bar_interval"
    )
    if slippage_baked_into_quote:
        record.setdefault("fill_quote_source", "bar_range_level")
    # Tick execution returns a raw executable quote and needs adverse
    # slippage here. Bar-open discretionary closes also need it, while
    # protective OHLC fills already embed the cost-model adjustment in their
    # trigger/exit quote and must not receive it a second time.
    if slippage_applied_now:
        quote = adverse_tick_fill_quote(
            quote,
            int(position.direction),
            settings.tick_fill_slippage_points,
            opening=False,
        )
    elif slippage_baked_into_quote:
        pre_execution_quote = undo_adverse_quote_level_slippage(
            quote,
            int(position.direction),
            float(settings.cost_model.slippage_points),
            opening=False,
        )
    slippage_points_applied = (
        float(settings.tick_fill_slippage_points)
        if slippage_applied_now
        else float(settings.cost_model.slippage_points)
        if slippage_baked_into_quote
        else 0.0
    )
    record.update(
        {
            "fill_cost_provenance_schema_version": FILL_COST_PROVENANCE_SCHEMA_VERSION,
            "pre_execution_quote_bid": pre_execution_quote[0],
            "pre_execution_quote_ask": pre_execution_quote[1],
            "broker_execution_quote_bid": float(quote[0]),
            "broker_execution_quote_ask": float(quote[1]),
            "slippage_points_applied_here": slippage_points_applied,
            "slippage_applied_here": slippage_points_applied > 0.0,
            "slippage_application_mode": (
                "transacted_side"
                if slippage_applied_now and slippage_points_applied > 0.0
                else "quote_level_shift"
                if slippage_baked_into_quote and slippage_points_applied > 0.0
                else "none"
            ),
        }
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
