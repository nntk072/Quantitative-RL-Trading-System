"""Execution of policy-selected backtest actions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from trading.execution import (
    Broker,
    adverse_tick_fill_quote,
)
from trading.risk import (
    FTMOGuardrails,
    approve_dynamic_risk,
    compute_lots,
    compute_lots_with_execution_reserve,
    compute_sl_tp_long,
    compute_sl_tp_short,
    modeled_execution_reserve_usd,
    stop_loss_risk_usd,
)

from .accounting import _record_close
from .runtime import BacktestSettings, BacktestState

ExecutionEvent = tuple[tuple[float, float], pd.Timestamp, str, dict[str, Any]]
ResolveExecution = Callable[[], ExecutionEvent]


def _repeated_payout_size(
    state: BacktestState,
    settings: BacktestSettings,
    guardrails: FTMOGuardrails,
    *,
    entry_price: float,
    stop_price: float,
) -> tuple[float, dict[str, float]]:
    """Size one position against repeated-payout account capacity and reserves."""
    policy = settings.trading_policy
    if policy is None or not policy.repeated_payout:
        raise ValueError("repeated-payout sizing requires its account policy")
    decision = approve_dynamic_risk(
        equity=state.account.equity,
        risk_frac=settings.risk_frac,
        max_agent_risk_frac=policy.max_agent_risk_frac,
        daily_capacity=state.account.remaining_daily_capacity(policy.daily_loss_limit),
        account_capacity=state.account.remaining_account_capacity(policy.account_floor),
        execution_reserve_usd=policy.execution_reserve_usd,
    )
    per_trade_cap = guardrails.risk_per_trade_limit_for(state.account)
    if settings.max_loss_per_trade_usd is not None:
        per_trade_cap = min(per_trade_cap, settings.max_loss_per_trade_usd)
    approved = min(decision.approved_usd, max(0.0, float(per_trade_cap)))
    reserve_per_lot = modeled_execution_reserve_usd(
        lots=1.0,
        slippage_points=settings.cost_model.slippage_points,
        commission_per_lot=settings.cost_model.commission_per_lot,
        contract_size=settings.contract_size,
    )
    lots = compute_lots_with_execution_reserve(
        total_risk_budget_usd=approved,
        equity=state.account.equity,
        risk_frac=settings.risk_frac,
        entry_price=entry_price,
        sl_price=stop_price,
        contract_size=settings.contract_size,
        execution_reserve_per_lot=reserve_per_lot,
        min_lot=settings.min_lot,
        max_lot=settings.max_lot,
    )
    stop_risk = stop_loss_risk_usd(
        entry_price - stop_price,
        lots,
        settings.contract_size,
        settings.cost_model.point_value,
    )
    modeled_reserve = reserve_per_lot * lots
    return lots, {
        "requested_risk_usd": float(decision.requested_usd),
        "approved_risk_usd": float(approved),
        "execution_reserve_usd": float(decision.execution_reserve_usd + modeled_reserve),
        "modeled_stop_risk_usd": float(stop_risk),
        "risk_cash": float(stop_risk),
        "all_in_risk_usd": float(stop_risk + modeled_reserve),
    }


def apply_policy_action(
    state: BacktestState,
    settings: BacktestSettings,
    broker: Broker,
    guardrails: FTMOGuardrails,
    bars: pd.DataFrame,
    features: pd.DataFrame,
    *,
    i: int,
    bar_time: pd.Timestamp,
    session: int,
    action: int,
    resolve_bar_execution: ResolveExecution,
    is_last_ny_bar: Callable[[pd.DataFrame, int, bool], bool],
    feature_index: int | None = None,
    decision_bar_time: pd.Timestamp | None = None,
    order_id: str | None = None,
) -> None:
    """Apply one policy action using the next executable quote.

    Args:
        state: State object read or updated by the operation.
        settings: Settings used by the operation described above.
        broker: Broker used by the operation described above.
        guardrails: Guardrails used by the operation described above.
        bars: Market bars to process.
        features: Feature values supplied to the operation.
        i: Numeric value used for the i.
        bar_time: Bar time used by the operation described above.
        session: Session identifier used by the operation.
        action: Action to apply to the current state.
        resolve_bar_execution: Resolve bar execution used by the operation described above.
        is_last_ny_bar: Predicate for the last bar in the active session.
        feature_index: Original decision row for a scheduled delayed entry.
        decision_bar_time: Original policy decision bar for a delayed entry.
        order_id: Identifier of a scheduled delayed entry.
    """
    if action == settings.exit_action and state.position is not None:
        fq, execution_time, fill_source, _ = resolve_bar_execution()
        _record_close(
            state,
            settings,
            broker,
            state.position,
            fq,
            {
                "type": "close",
                "bar": i,
                "time": execution_time,
                "decision_time": bar_time,
                "fill_time": execution_time,
                "fill_quote_source": fill_source,
            },
            session,
        )
        return

    if action in (1, -1):
        if state.position is not None and state.position.direction != action:
            fq, execution_time, fill_source, _ = resolve_bar_execution()
            _record_close(
                state,
                settings,
                broker,
                state.position,
                fq,
                {
                    "type": "close",
                    "bar": i,
                    "time": execution_time,
                    "decision_time": bar_time,
                    "fill_time": execution_time,
                    "fill_quote_source": fill_source,
                },
                session,
            )

        if state.position is not None:
            return
        if settings.block_overnight and is_last_ny_bar(
            bars,
            i + 1,
            "session" not in bars.iloc[i + 1].index or str(bars.iloc[i + 1]["session"]) == "ny",
        ):
            return

        fq, execution_time, fill_source, execution_meta = resolve_bar_execution()
        sl_price = None
        tp_price = None
        actual_lots = settings.lots
        repeated_risk_metadata: dict[str, float] = {}
        repeated_payout = bool(
            settings.trading_policy is not None and settings.trading_policy.repeated_payout
        )
        max_loss_cap = guardrails.risk_per_trade_limit_for(state.account)
        if settings.max_loss_per_trade_usd is not None:
            max_loss_cap = min(max_loss_cap, settings.max_loss_per_trade_usd)
        entry_price_for_calc = float(fq[1] if action == 1 else fq[0])

        if settings.use_structure_sl_tp:
            feat_row = features.iloc[i if feature_index is None else feature_index]
            low_raw = feat_row["last_swing_low"] if "last_swing_low" in feat_row.index else np.nan
            high_raw = (
                feat_row["last_swing_high"] if "last_swing_high" in feat_row.index else np.nan
            )
            last_swing_low = float(low_raw) if pd.notna(low_raw) else None
            last_swing_high = float(high_raw) if pd.notna(high_raw) else None

            if action == 1 and last_swing_low is not None:
                sl_price, tp_price = compute_sl_tp_long(
                    entry_price_for_calc,
                    last_swing_low,
                    buffer_pts=settings.swing_buffer_pts,
                    rr_ratio=settings.rr_ratio,
                )
                if not repeated_payout:
                    actual_lots = compute_lots(
                        state.account.equity,
                        settings.risk_frac,
                        entry_price_for_calc,
                        sl_price,
                        contract_size=settings.contract_size,
                        point_value=settings.cost_model.point_value,
                        min_lot=settings.min_lot,
                        max_lot=settings.max_lot,
                        max_loss_cap=max_loss_cap,
                    )
            elif action == -1 and last_swing_high is not None:
                sl_price, tp_price = compute_sl_tp_short(
                    entry_price_for_calc,
                    last_swing_high,
                    buffer_pts=settings.swing_buffer_pts,
                    rr_ratio=settings.rr_ratio,
                )
                if not repeated_payout:
                    actual_lots = compute_lots(
                        state.account.equity,
                        settings.risk_frac,
                        entry_price_for_calc,
                        sl_price,
                        contract_size=settings.contract_size,
                        point_value=settings.cost_model.point_value,
                        min_lot=settings.min_lot,
                        max_lot=settings.max_lot,
                        max_loss_cap=max_loss_cap,
                    )

        if repeated_payout:
            if sl_price is None:
                state.trade_log.append(
                    {
                        "type": "reject",
                        "reason": "missing_structural_stop",
                        "bar": i,
                        "time": execution_time,
                        "direction": action,
                    }
                )
                return
            actual_lots, repeated_risk_metadata = _repeated_payout_size(
                state,
                settings,
                guardrails,
                entry_price=entry_price_for_calc,
                stop_price=sl_price,
            )
            if (
                actual_lots <= 0.0
                or repeated_risk_metadata["all_in_risk_usd"]
                > repeated_risk_metadata["approved_risk_usd"] + 1e-9
            ):
                state.trade_log.append(
                    {
                        "type": "reject",
                        "reason": "risk_capacity",
                        "bar": i,
                        "time": execution_time,
                        "direction": action,
                        **repeated_risk_metadata,
                    }
                )
                return

        if sl_price is not None:
            trade_risk = stop_loss_risk_usd(
                entry_price_for_calc - sl_price,
                actual_lots,
                settings.contract_size,
                settings.cost_model.point_value,
            )
        elif settings.max_loss_per_trade_usd is not None:
            trade_risk = settings.max_loss_per_trade_usd
        else:
            trade_risk = None
        if repeated_payout:
            trade_risk = repeated_risk_metadata["all_in_risk_usd"]

        if trade_risk is not None and guardrails.check_trade_risk(trade_risk, state.account):
            return

        fill_quote = (
            adverse_tick_fill_quote(
                fq,
                action,
                settings.tick_fill_slippage_points,
                opening=True,
            )
            if fill_source == "tick"
            else fq
        )
        position = broker.open_position(state.account, fill_quote, actual_lots, action)
        if position:
            state.position_sequence += 1
            position.position_id = f"bt:p{state.position_sequence}"
            position.entry_timestamp = execution_time
            entry_features = features.iloc[i if feature_index is None else feature_index]
            atr_value = entry_features.get("atr_5", entry_features.get("atr", np.nan))
            position.entry_atr = (
                float(atr_value) if pd.notna(atr_value) and float(atr_value) > 0 else 1.0
            )
            position.sl_price = sl_price
            position.sl_initial_price = sl_price
            position.sl_mode = settings.sl_mode
            position.tp_price = tp_price
            if sl_price is not None:
                position.planned_risk_usd = stop_loss_risk_usd(
                    entry_price_for_calc - sl_price,
                    actual_lots,
                    settings.contract_size,
                )
            position.risk_frac = settings.risk_frac
            position.rr_ratio = settings.rr_ratio
            state.position = position
            open_event: dict[str, Any] = {
                "type": "open",
                "position_id": position.position_id,
                "direction": action,
                "price": position.entry_price,
                "lots": position.size,
                "entry_commission": settings.cost_model.total_cost(position.size),
                "sl_price": sl_price,
                "tp_price": tp_price,
                "risk_frac": settings.risk_frac,
                "rr_ratio": settings.rr_ratio,
                "bar": i,
                "time": execution_time,
                "decision_time": bar_time,
                "decision_bar_time": bar_time if decision_bar_time is None else decision_bar_time,
                "order_submission_time": bar_time,
                "fill_time": execution_time,
                "fill_quote_source": fill_source,
                "equity": state.account.equity,
                **execution_meta,
                **repeated_risk_metadata,
            }
            if order_id is not None:
                open_event["order_id"] = order_id
            state.trade_log.append(open_event)
            state.sessions_with_trades.add(session)
        return

    if action == 0 and state.position is not None and not settings.hold_on_zero:
        fq, execution_time, fill_source, _ = resolve_bar_execution()
        _record_close(
            state,
            settings,
            broker,
            state.position,
            fq,
            {
                "type": "close",
                "bar": i,
                "time": execution_time,
                "decision_time": bar_time,
                "fill_time": execution_time,
                "fill_quote_source": fill_source,
            },
            session,
        )
