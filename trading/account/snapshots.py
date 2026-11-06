"""Versioned account and guardrail snapshots for evaluation traces."""

from __future__ import annotations

from typing import Any

from trading.account.account_state import AccountState

ACCOUNT_STATE_TRACE_SCHEMA = "account_state_trace.v2"


def account_state_snapshot(
    account: AccountState,
    *,
    valuation_time: Any,
    decision_time: Any,
    session_id: int | None,
    state_phase: str = "post_action_valuation",
    daily_loss_limit_usd: float,
    soft_daily_loss_limit_usd: float,
    max_loss_limit_usd: float,
    max_loss_floor_equity: float,
    max_drawdown_mode: str,
    max_drawdown_from_reference_usd: float,
    soft_max_loss_limit_usd: float,
    trailing_drawdown_limit_usd: float,
    soft_trailing_drawdown_limit_usd: float,
    risk_per_trade_limit_usd: float,
    position: Any | None = None,
    pending_order: dict[str, Any] | None = None,
    cumulative_payouts: float = 0.0,
    cycle_count: int = 1,
    breach_reason: str = "",
    trade_event_count: int | None = None,
    contract_size: float | None = None,
) -> dict[str, Any]:
    """Build a self-contained account state row at one valuation boundary.

    Guardrail values are supplied by their policy owner so this trace contract
    does not couple account storage to a particular simulator or risk policy.

    Args:
        account: Account state at the requested valuation boundary.
        valuation_time: Timestamp used to value equity and open exposure.
        decision_time: Timestamp at which the policy may observe account state.
        session_id: Active session identifier, when one is available.
        state_phase: Label identifying the side of an action represented by the row.
        daily_loss_limit_usd: Hard daily-loss allowance in dollars.
        soft_daily_loss_limit_usd: Soft daily-loss threshold in dollars.
        max_loss_limit_usd: Hard maximum-loss allowance in dollars.
        max_loss_floor_equity: Equity floor implied by the maximum-loss policy.
        max_drawdown_mode: Selected static, EOD, or intraday trailing mode.
        max_drawdown_from_reference_usd: Current drawdown from the policy reference.
        soft_max_loss_limit_usd: Soft maximum-loss threshold in dollars.
        trailing_drawdown_limit_usd: Hard trailing drawdown allowance in dollars.
        soft_trailing_drawdown_limit_usd: Soft trailing drawdown threshold in dollars.
        risk_per_trade_limit_usd: Maximum permitted risk for one trade.
        position: Open position snapshot, if a position is active.
        pending_order: Pending entry-order fields, if an order is active.
        cumulative_payouts: Total payouts already withdrawn from the account.
        cycle_count: Repeated-payout cycle number.
        breach_reason: Risk-breach reason attached to this state, if any.
        trade_event_count: Number of trade events recorded so far.
        contract_size: Instrument contract size used in the account valuation.

    Returns:
        Versioned mapping of account equity, guardrails, position, and order state.
    """
    direction = 0 if position is None else int(position.direction)
    size = 0.0 if position is None else float(position.size)
    entry_price = None if position is None else float(position.entry_price)
    stop_price = None if position is None or position.sl_price is None else float(position.sl_price)
    target_price = (
        None if position is None or position.tp_price is None else float(position.tp_price)
    )
    order = pending_order or {}
    payouts = float(cumulative_payouts)
    return {
        "schema_version": ACCOUNT_STATE_TRACE_SCHEMA,
        "valuation_time": str(valuation_time),
        "decision_time": str(decision_time),
        "session_id": None if session_id is None else int(session_id),
        "state_phase": str(state_phase),
        "initial_balance": float(account.initial_balance),
        "balance": float(account.balance),
        "equity": float(account.equity),
        "open_pnl": float(account.open_pnl),
        "session_start_balance": float(account.session_start_balance),
        "session_start_equity": float(account.session_start_equity),
        "daily_pnl_basis": str(account.daily_pnl_basis),
        "daily_loss": float(account.canonical_daily_loss()),
        "daily_loss_limit_usd": float(daily_loss_limit_usd),
        "soft_daily_loss_limit_usd": float(soft_daily_loss_limit_usd),
        "daily_floor_equity": float(account.daily_floor(daily_loss_limit_usd)),
        "loss_from_initial_usd": float(account.loss_from_initial()),
        "max_drawdown_usd": float(account.max_drawdown),
        "max_loss_limit_usd": float(max_loss_limit_usd),
        "max_loss_floor_equity": float(max_loss_floor_equity),
        "max_drawdown_mode": str(max_drawdown_mode),
        "max_drawdown_from_reference_usd": float(max_drawdown_from_reference_usd),
        "soft_max_loss_limit_usd": float(soft_max_loss_limit_usd),
        "peak_equity": float(account.peak_equity),
        "peak_eod_equity": float(account.peak_eod_equity),
        "peak_eod_drawdown_usd": float(account.peak_eod_drawdown_usd),
        "max_peak_eod_drawdown_usd": float(account.max_peak_eod_drawdown_usd),
        "payout_drawdown_floor": (
            None if account.payout_drawdown_floor is None else float(account.payout_drawdown_floor)
        ),
        "trailing_drawdown_usd": max(0.0, float(account.peak_equity) - float(account.equity)),
        "trailing_drawdown_fraction": float(account.trailing_drawdown_pct()),
        "trailing_drawdown_limit_usd": float(trailing_drawdown_limit_usd),
        "soft_trailing_drawdown_limit_usd": float(soft_trailing_drawdown_limit_usd),
        "risk_per_trade_limit_usd": float(risk_per_trade_limit_usd),
        "position_direction": direction,
        "position_size": size,
        "position_entry_price": entry_price,
        "position_stop_price": stop_price,
        "position_target_price": target_price,
        "pending_order_id": order.get("order_id"),
        "pending_order_type": (None if not order else str(order.get("order_type", "market"))),
        "pending_order_direction": (
            None
            if order.get("direction", order.get("action")) is None
            else int(order.get("direction", order.get("action", 0)) or 0)
        ),
        "pending_order_limit_price": (
            None if order.get("limit_price") is None else float(order["limit_price"])
        ),
        "pending_order_submission_time": (
            None
            if order.get("order_submission_time") is None
            else str(order["order_submission_time"])
        ),
        "pending_order_expiry_time": (
            None if order.get("expiry_time") is None else str(order["expiry_time"])
        ),
        "pending_order_scheduled_fill_time": (
            None if order.get("scheduled_fill_time") is None else str(order["scheduled_fill_time"])
        ),
        "pending_order_decision_id": order.get("decision_id"),
        "pending_order_risk_fraction": (
            None if order.get("risk_frac") is None else float(order["risk_frac"])
        ),
        "pending_order_reward_risk_ratio": (
            None if order.get("rr_ratio") is None else float(order["rr_ratio"])
        ),
        "cumulative_payouts": payouts,
        "total_economic_value": float(account.equity + payouts),
        "cycle_count": int(cycle_count),
        "breach_reason": str(breach_reason),
        "trade_event_count": (None if trade_event_count is None else int(trade_event_count)),
        "position_mark_price": (
            None if position is None or position.mark_price is None else float(position.mark_price)
        ),
        "contract_size": None if contract_size is None else float(contract_size),
    }


__all__ = ["ACCOUNT_STATE_TRACE_SCHEMA", "account_state_snapshot"]
