"""Execution of policy-selected backtest actions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from decisioning.trade_setup import TradeSetupCandidate, TradeSetupGeometryChoice
from features.context.trade_setup_candidates import (
    TradeSetupEventIdentity,
    trade_setup_event_identity_record,
)
from trading.execution import (
    FILL_COST_PROVENANCE_SCHEMA_VERSION,
    TRADE_CASHFLOW_SCHEMA_VERSION,
    Broker,
    adverse_tick_fill_quote,
)
from trading.orders import OrderGeometry, place_strategy_order
from trading.risk import (
    FTMOGuardrails,
    approve_dynamic_risk,
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


def _finite_feature(row: pd.Series, name: str) -> float | None:
    """Return one finite feature value, or ``None`` when it is unavailable.

    Args:
        row: Current feature row.
        name: Feature field to read.

    Returns:
        Finite feature value, or ``None`` for invalid or missing data.
    """
    try:
        value = float(row.get(name, np.nan))
    except (TypeError, ValueError):
        return None
    return value if np.isfinite(value) else None


def _repeated_payout_size(
    state: BacktestState,
    settings: BacktestSettings,
    guardrails: FTMOGuardrails,
    *,
    risk_frac: float,
    entry_price: float,
    stop_price: float,
) -> tuple[float, dict[str, float]]:
    """Size one position against repeated-payout account capacity and reserves.

    Args:
        state: Mutable account state used for capacity calculations.
        settings: Backtest and execution settings for the position.
        guardrails: Account-level risk constraints.
        risk_frac: Policy-selected fraction of eligible risk capacity.
        entry_price: Planned entry price.
        stop_price: Planned stop price used to compute position risk.

    Returns:
        Approved lot size and a breakdown of requested, approved, and reserved risk.
    """
    policy = settings.trading_policy
    if policy is None or not policy.repeated_payout:
        raise ValueError("repeated-payout sizing requires its account policy")
    decision = approve_dynamic_risk(
        equity=state.account.equity,
        risk_frac=risk_frac,
        max_agent_risk_frac=policy.max_agent_risk_frac,
        daily_capacity=state.account.remaining_daily_capacity(policy.daily_loss_limit),
        account_capacity=state.account.remaining_account_capacity(
            guardrails.max_loss_floor_for(state.account)
        ),
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
        point_value=settings.cost_model.point_value,
    )
    lots = compute_lots_with_execution_reserve(
        total_risk_budget_usd=approved,
        equity=state.account.equity,
        risk_frac=risk_frac,
        entry_price=entry_price,
        sl_price=stop_price,
        contract_size=settings.contract_size,
        execution_reserve_per_lot=reserve_per_lot,
        min_lot=settings.min_lot,
        max_lot=settings.max_lot,
        point_value=settings.cost_model.point_value,
        lot_step=settings.lot_step,
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
    order_submission_time: pd.Timestamp | None = None,
    order_id: str | None = None,
    decision_id: str | None = None,
    trade_setup: TradeSetupCandidate | None = None,
    trade_setup_event_identity: TradeSetupEventIdentity | None = None,
    selected_risk_frac: float | None = None,
    selected_geometry: TradeSetupGeometryChoice | None = None,
    entry_reference_price: float | None = None,
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
        order_submission_time: Timestamp when the market/limit order became active.
        order_id: Identifier of a scheduled delayed entry.
        decision_id: Identifier of the policy decision that created this action.
        trade_setup: Canonical setup identity selected by the policy, when
            running the opt-in mask-aware action path.
        trade_setup_event_identity: Source-event timestamp identity selected
            for the setup, propagated through delayed orders and position events.
        selected_risk_frac: Risk fraction selected by a schema-versioned policy.
        selected_geometry: Stop, target, and exit coordinates selected by a
            schema-versioned setup policy.
        entry_reference_price: Intended order price used to size and place
            protection for a pending limit fill. The broker still records the
            actual executable quote as the position entry price.
    """
    selected_setup_context: dict[str, Any] = {}
    if trade_setup is not None:
        selected_setup_context = {
            "trade_setup_candidate_id": int(trade_setup.candidate_id),
            **trade_setup_event_identity_record(trade_setup_event_identity),
        }
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
                "decision_id": decision_id,
                "bar": i,
                "time": execution_time,
                "decision_time": bar_time,
                "decision_bar_time": bar_time,
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
                    "decision_id": decision_id,
                    "bar": i,
                    "time": execution_time,
                    "decision_time": bar_time,
                    "decision_bar_time": bar_time,
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
        entry_order_type = str(execution_meta.get("order_type", "market"))
        pre_execution_quote = tuple(map(float, fq))
        market_entry_slippage_applied = (
            entry_order_type == "market" and settings.tick_fill_slippage_points > 0.0
        )
        entry_quote = (
            adverse_tick_fill_quote(
                fq,
                action,
                settings.tick_fill_slippage_points,
                opening=True,
            )
            if market_entry_slippage_applied
            else fq
        )
        sl_price = None
        tp_price = None
        actual_lots = settings.lots
        repeated_risk_metadata: dict[str, float] = {}
        sized_risk_budget: float | None = None
        repeated_payout = bool(
            settings.trading_policy is not None and settings.trading_policy.repeated_payout
        )
        placed_geometry: OrderGeometry | None = None
        risk_frac = settings.risk_frac if selected_risk_frac is None else float(selected_risk_frac)
        max_loss_cap = guardrails.risk_per_trade_limit_for(state.account)
        if settings.max_loss_per_trade_usd is not None:
            max_loss_cap = min(max_loss_cap, settings.max_loss_per_trade_usd)
        actual_entry_price = float(entry_quote[1] if action == 1 else entry_quote[0])
        entry_price_for_calc = (
            actual_entry_price if entry_reference_price is None else float(entry_reference_price)
        )
        if not np.isfinite(entry_price_for_calc) or entry_price_for_calc <= 0.0:
            raise ValueError("entry_reference_price must be finite and positive")

        if settings.use_structure_sl_tp:
            feat_row = features.iloc[i if feature_index is None else feature_index]
            if settings.trade_setup_geometry:
                if trade_setup is None or selected_geometry is None:
                    state.trade_log.append(
                        {
                            "type": "reject",
                            "decision_id": decision_id,
                            "order_id": order_id,
                            **selected_setup_context,
                            "reason": "missing_setup_geometry_action",
                            "bar": i,
                            "time": execution_time,
                            "direction": action,
                        }
                    )
                    return
                atr_value = feat_row.get("atr_5", feat_row.get("atr", np.nan))
                try:
                    atr_value = float(atr_value)
                except (TypeError, ValueError):
                    atr_value = float("nan")
                min_distance = max(
                    settings.min_sl_points,
                    settings.min_sl_atr_mult * atr_value
                    if np.isfinite(atr_value) and atr_value > 0.0
                    else 0.0,
                )
                max_tp_distance = float("nan")
                if settings.geometry_max_tp_dist is not None:
                    feature_row_index = i if feature_index is None else feature_index
                    try:
                        max_tp_distance = float(
                            settings.geometry_max_tp_dist.iloc[feature_row_index]
                        )
                    except (IndexError, TypeError, ValueError):
                        max_tp_distance = float("nan")
                placed_geometry = place_strategy_order(
                    settings.strategy,
                    direction=action,
                    entry_price=entry_price_for_calc,
                    feat_row=feat_row,
                    min_dist=min_distance,
                    sl_fraction=selected_geometry.stop_anchor_fraction,
                    tp_fraction=selected_geometry.target_fraction,
                    exit_mode=selected_geometry.exit_mode,
                    buffer_pts=settings.sl_buffer_pts,
                    max_tp_distance=max_tp_distance,
                    rr_bounds=settings.policy_rr_ratio_range,
                    htf=settings.target_timeframes,
                    tp_selections=(
                        selected_geometry.target_selections if settings.allow_multi_tp else None
                    ),
                    tp_z=(
                        selected_geometry.simplex_logits
                        if settings.allow_multi_tp and settings.allow_simplex
                        else None
                    ),
                    allow_multi_tp=settings.allow_multi_tp,
                    allow_simplex=settings.allow_simplex,
                    price_increment=float(settings.cost_model.point_size),
                    ema_runner_fraction=(
                        settings.ema_runner_fraction
                        if selected_geometry.exit_mode == "ema_21"
                        else 0.0
                    ),
                    trade_setup=trade_setup,
                )
                sl_price = placed_geometry.sl_price
                tp_price = placed_geometry.tp_price
                order_valid = sl_price is not None and (
                    placed_geometry.exit_mode == "ema_21" or tp_price is not None
                )
                if not order_valid:
                    reason = {"tp": "no_valid_tp", "ema": "no_ema_exit"}.get(
                        placed_geometry.reject_kind, "no_valid_sl"
                    )
                    state.trade_log.append(
                        {
                            "type": "reject",
                            "decision_id": decision_id,
                            "order_id": order_id,
                            **selected_setup_context,
                            "reason": reason,
                            "bar": i,
                            "time": execution_time,
                            "direction": action,
                            "selected_geometry_action": {
                                "stop_anchor_fraction": selected_geometry.stop_anchor_fraction,
                                "target_fraction": selected_geometry.target_fraction,
                                "exit_mode": selected_geometry.exit_mode,
                            },
                        }
                    )
                    return
            else:
                low_raw = (
                    feat_row["last_swing_low"] if "last_swing_low" in feat_row.index else np.nan
                )
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
                elif action == -1 and last_swing_high is not None:
                    sl_price, tp_price = compute_sl_tp_short(
                        entry_price_for_calc,
                        last_swing_high,
                        buffer_pts=settings.swing_buffer_pts,
                        rr_ratio=settings.rr_ratio,
                    )

            if sl_price is not None and not repeated_payout:
                sized_risk_budget = min(
                    max(0.0, state.account.equity * risk_frac), max(0.0, max_loss_cap)
                )
                reserve_per_lot = modeled_execution_reserve_usd(
                    lots=1.0,
                    slippage_points=settings.cost_model.slippage_points,
                    commission_per_lot=settings.cost_model.commission_per_lot,
                    contract_size=settings.contract_size,
                    point_value=settings.cost_model.point_value,
                )
                actual_lots = compute_lots_with_execution_reserve(
                    total_risk_budget_usd=sized_risk_budget,
                    equity=state.account.equity,
                    risk_frac=risk_frac,
                    entry_price=entry_price_for_calc,
                    sl_price=sl_price,
                    contract_size=settings.contract_size,
                    execution_reserve_per_lot=reserve_per_lot,
                    min_lot=settings.min_lot,
                    max_lot=settings.max_lot,
                    point_value=settings.cost_model.point_value,
                    lot_step=settings.lot_step,
                )

        if repeated_payout:
            if sl_price is None:
                state.trade_log.append(
                    {
                        "type": "reject",
                        "decision_id": decision_id,
                        "order_id": order_id,
                        **selected_setup_context,
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
                risk_frac=risk_frac,
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
                        "decision_id": decision_id,
                        "order_id": order_id,
                        **selected_setup_context,
                        "reason": "risk_capacity",
                        "bar": i,
                        "time": execution_time,
                        "direction": action,
                        **repeated_risk_metadata,
                    }
                )
                return

        if settings.use_structure_sl_tp and actual_lots <= 0.0:
            state.trade_log.append(
                {
                    "type": "reject",
                    "decision_id": decision_id,
                    "order_id": order_id,
                    **selected_setup_context,
                    "reason": "risk_budget_below_minimum_lot",
                    "bar": i,
                    "time": execution_time,
                    "direction": action,
                    "risk_frac": risk_frac,
                    "risk_budget_usd": sized_risk_budget,
                    "minimum_lot": settings.min_lot,
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
            state.trade_log.append(
                {
                    "type": "reject",
                    "decision_id": decision_id,
                    "order_id": order_id,
                    **selected_setup_context,
                    "reason": "trade_risk_limit",
                    "bar": i,
                    "time": execution_time,
                    "direction": action,
                    "trade_risk_usd": float(trade_risk),
                }
            )
            return

        position = broker.open_position(state.account, entry_quote, actual_lots, action)
        if position is None:
            state.trade_log.append(
                {
                    "type": "reject",
                    "decision_id": decision_id,
                    "order_id": order_id,
                    **selected_setup_context,
                    "reason": "insufficient_margin",
                    "bar": i,
                    "time": execution_time,
                    "direction": action,
                    "requested_lots": float(actual_lots),
                }
            )
        if position:
            state.position_sequence += 1
            position.position_id = f"bt:p{state.position_sequence}"
            position.entry_timestamp = execution_time
            position.initial_size = float(position.size)
            entry_features = features.iloc[i if feature_index is None else feature_index]
            atr_value = entry_features.get("atr_5", entry_features.get("atr", np.nan))
            position.entry_atr = (
                float(atr_value) if pd.notna(atr_value) and float(atr_value) > 0 else 1.0
            )
            position.sl_price = sl_price
            position.sl_initial_price = sl_price
            position.sl_mode = (
                selected_geometry.sl_mode if selected_geometry is not None else settings.sl_mode
            )
            position.sl_mode_overridden = bool(
                selected_geometry is None
                or not selected_geometry.has_sl_mode
                or selected_geometry.sl_mode_explicit
            )
            position.tp_mode = (
                selected_geometry.tp_mode if selected_geometry is not None else settings.tp_mode
            )
            position.tp_mode_overridden = bool(
                selected_geometry is None
                or not selected_geometry.has_tp_mode
                or selected_geometry.tp_mode_explicit
            )
            position.tp_breakeven_done = False
            position.tp_hit_mask = 0
            position.exit_mode = "structural"
            position.entry_last_swing_high = _finite_feature(entry_features, "last_swing_high")
            position.entry_last_swing_low = _finite_feature(entry_features, "last_swing_low")
            if (
                placed_geometry is not None
                and placed_geometry.sl_ref == "sl_reference"
                and settings.strategy is not None
                and hasattr(settings.strategy, "sl_reference")
            ):
                reference = settings.strategy.sl_reference(direction=action, row=entry_features)
                if reference is not None and np.isfinite(float(reference)):
                    position.entry_sl_ref_price = float(reference)
            position.tp_price = tp_price
            if placed_geometry is not None and sl_price is not None:
                position.sl_ref = placed_geometry.sl_ref
                position.tp_ref = placed_geometry.tp_ref
                position.planned_rr = placed_geometry.planned_rr
                position.exit_mode = placed_geometry.exit_mode
                position.stop_distance = abs(entry_price_for_calc - float(sl_price))
                position.sl_buffer = placed_geometry.sl_buffer
                position.manipulation = placed_geometry.manipulation
                position.n_sl = placed_geometry.n_sl
                position.n_tp = placed_geometry.n_tp
                position.tp1_price = placed_geometry.tp1_price
                position.tp2_price = placed_geometry.tp2_price
                position.tp3_price = placed_geometry.tp3_price
                position.tp1_ref = placed_geometry.tp1_ref
                position.tp2_ref = placed_geometry.tp2_ref
                position.tp3_ref = placed_geometry.tp3_ref
                position.tp_lot_fractions = placed_geometry.tp_lot_fractions
                position.ema_runner_fraction = placed_geometry.ema_runner_fraction
                position.tp_initial_price = (
                    placed_geometry.tp3_price
                    if placed_geometry.tp3_price is not None
                    else placed_geometry.tp_price
                )
                position.tp_initial_size = float(position.size)
                position.tp_hit_mask = 0
            if sl_price is not None:
                position.planned_risk_usd = stop_loss_risk_usd(
                    entry_price_for_calc - sl_price,
                    actual_lots,
                    settings.contract_size,
                    settings.cost_model.point_value,
                )
            position.risk_frac = risk_frac
            position.rr_ratio = settings.rr_ratio
            state.position = position
            submitted_at = (
                pd.Timestamp(order_submission_time)
                if order_submission_time is not None
                else pd.Timestamp(bar_time)
            )
            open_event: dict[str, Any] = {
                "type": "open",
                "position_id": position.position_id,
                "direction": action,
                "price": position.entry_price,
                "lots": position.size,
                "cashflow_schema_version": TRADE_CASHFLOW_SCHEMA_VERSION,
                "contract_size": float(settings.contract_size),
                "commission_per_lot": float(settings.cost_model.commission_per_lot),
                "entry_commission": settings.cost_model.total_cost(position.size),
                **trade_setup_event_identity_record(trade_setup_event_identity),
                "sl_price": sl_price,
                "tp_price": tp_price,
                "risk_frac": risk_frac,
                "risk_budget_usd": sized_risk_budget,
                "risk_reference_price": entry_price_for_calc,
                "modeled_stop_risk_usd": trade_risk,
                "sl_mode": position.sl_mode,
                "sl_mode_overridden": position.sl_mode_overridden,
                "tp_mode": position.tp_mode,
                "tp_mode_overridden": position.tp_mode_overridden,
                "rr_ratio": settings.rr_ratio,
                "bar": i,
                "time": execution_time,
                "decision_time": submitted_at,
                "decision_bar_time": bar_time if decision_bar_time is None else decision_bar_time,
                "order_submission_time": submitted_at,
                "fill_time": execution_time,
                "fill_quote_source": fill_source,
                "fill_cost_provenance_schema_version": FILL_COST_PROVENANCE_SCHEMA_VERSION,
                "pre_execution_quote_bid": pre_execution_quote[0],
                "pre_execution_quote_ask": pre_execution_quote[1],
                "broker_execution_quote_bid": float(entry_quote[0]),
                "broker_execution_quote_ask": float(entry_quote[1]),
                "slippage_points_applied_here": (
                    float(settings.tick_fill_slippage_points)
                    if market_entry_slippage_applied
                    else 0.0
                ),
                "slippage_applied_here": market_entry_slippage_applied,
                "slippage_application_mode": (
                    "transacted_side" if market_entry_slippage_applied else "none"
                ),
                "entry_slippage_applied": market_entry_slippage_applied,
                "entry_slippage_points": (
                    float(settings.tick_fill_slippage_points)
                    if market_entry_slippage_applied
                    else 0.0
                ),
                "equity": state.account.equity,
                **execution_meta,
                **repeated_risk_metadata,
            }
            # The resolver's quote-lookup instant may be later than the
            # original submission for delayed orders. Keep lifecycle identity
            # anchored to the time the order became active.
            open_event["decision_time"] = submitted_at
            open_event["order_submission_time"] = submitted_at
            if order_id is not None:
                open_event["order_id"] = order_id
            if decision_id is not None:
                open_event["decision_id"] = decision_id
            if trade_setup is not None:
                open_event.update(
                    {
                        "trade_setup_candidate_id": trade_setup.candidate_id,
                        "trade_setup_idea": trade_setup.idea,
                        "trade_setup_timeframe": trade_setup.setup_timeframe,
                    }
                )
            if selected_geometry is not None:
                open_event["selected_geometry_action"] = {
                    "stop_anchor_fraction": selected_geometry.stop_anchor_fraction,
                    "target_fraction": selected_geometry.target_fraction,
                    "target_selections": selected_geometry.target_selections,
                    "simplex_logits": selected_geometry.simplex_logits,
                    "exit_mode": selected_geometry.exit_mode,
                    "sl_mode": selected_geometry.sl_mode,
                    "sl_mode_explicit": selected_geometry.sl_mode_explicit,
                    "has_sl_mode": selected_geometry.has_sl_mode,
                    "tp_mode": selected_geometry.tp_mode,
                    "tp_mode_explicit": selected_geometry.tp_mode_explicit,
                    "has_tp_mode": selected_geometry.has_tp_mode,
                }
            if placed_geometry is not None:
                open_event.update(
                    {
                        "sl_ref": placed_geometry.sl_ref,
                        "tp_ref": placed_geometry.tp_ref,
                        "planned_rr": placed_geometry.planned_rr,
                        "exit_mode": placed_geometry.exit_mode,
                        "stop_distance": position.stop_distance,
                        "sl_buffer": placed_geometry.sl_buffer,
                        "tp1_price": placed_geometry.tp1_price,
                        "tp2_price": placed_geometry.tp2_price,
                        "tp3_price": placed_geometry.tp3_price,
                        "tp_lot_fractions": placed_geometry.tp_lot_fractions,
                        "ema_runner_fraction": placed_geometry.ema_runner_fraction,
                    }
                )
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
                "decision_id": decision_id,
                "bar": i,
                "time": execution_time,
                "decision_time": bar_time,
                "fill_time": execution_time,
                "fill_quote_source": fill_source,
            },
            session,
        )
