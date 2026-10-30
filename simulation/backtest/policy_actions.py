"""Execution of policy-selected backtest actions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from trading.execution import (
    Broker,
)
from trading.risk import (
    FTMOGuardrails,
    compute_lots,
    compute_sl_tp_long,
    compute_sl_tp_short,
    stop_loss_risk_usd,
)

from .accounting import _record_close
from .runtime import BacktestSettings, BacktestState

ExecutionEvent = tuple[tuple[float, float], pd.Timestamp, str, dict[str, Any]]
ResolveExecution = Callable[[], ExecutionEvent]


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
) -> None:
    """Apply one policy action using the next executable quote."""
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
        entry_price_for_calc = float(fq[1] if action == 1 else fq[0])

        if settings.use_structure_sl_tp:
            feat_row = features.iloc[i]
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
                actual_lots = compute_lots(
                    state.account.equity,
                    settings.risk_frac,
                    entry_price_for_calc,
                    sl_price,
                    contract_size=settings.contract_size,
                    point_value=settings.cost_model.point_value,
                    min_lot=settings.min_lot,
                    max_lot=settings.max_lot,
                    max_loss_cap=settings.max_loss_per_trade_usd,
                )
            elif action == -1 and last_swing_high is not None:
                sl_price, tp_price = compute_sl_tp_short(
                    entry_price_for_calc,
                    last_swing_high,
                    buffer_pts=settings.swing_buffer_pts,
                    rr_ratio=settings.rr_ratio,
                )
                actual_lots = compute_lots(
                    state.account.equity,
                    settings.risk_frac,
                    entry_price_for_calc,
                    sl_price,
                    contract_size=settings.contract_size,
                    point_value=settings.cost_model.point_value,
                    min_lot=settings.min_lot,
                    max_lot=settings.max_lot,
                    max_loss_cap=settings.max_loss_per_trade_usd,
                )

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

        if trade_risk is not None and guardrails.check_trade_risk(trade_risk, state.account):
            return

        position = broker.open_position(state.account, fq, actual_lots, action)
        if position:
            state.position_sequence += 1
            position.position_id = f"bt:p{state.position_sequence}"
            position.entry_timestamp = execution_time
            position.sl_price = sl_price
            position.tp_price = tp_price
            position.risk_frac = settings.risk_frac
            position.rr_ratio = settings.rr_ratio
            state.position = position
            state.trade_log.append(
                {
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
                    "order_submission_time": bar_time,
                    "fill_time": execution_time,
                    "fill_quote_source": fill_source,
                    "equity": state.account.equity,
                    **execution_meta,
                }
            )
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
