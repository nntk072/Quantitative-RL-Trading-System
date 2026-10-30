"""Backtest settings and mutable state contracts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pandas as pd

from trading import AccountState
from trading.execution import (
    CostModel,
    Position,
)

if TYPE_CHECKING:
    from market_data.loading.ticks import TickBook

ExecutionEvent = tuple[tuple[float, float], pd.Timestamp, str, dict[str, Any]]
ResolveExecution = Callable[[], ExecutionEvent]


@dataclass(frozen=True)
class BacktestSettings:
    """Execution and strategy settings shared across backtest lifecycle stages."""

    cost_model: CostModel
    lots: float
    max_loss_per_trade_usd: float | None
    take_profit_per_trade_usd: float | None
    tickbook: TickBook | None
    fill_delay_ms: int
    randomized_fill_latency_ms: float
    max_tick_quote_wait_ms: int
    tick_execution_required: bool
    use_structure_sl_tp: bool
    risk_frac: float
    rr_ratio: float
    swing_buffer_pts: float
    min_lot: float
    max_lot: float
    contract_size: float
    hold_on_zero: bool
    exit_action: int | None
    block_overnight: bool


@dataclass
class BacktestState:
    """Mutable accounting, position, and reporting state for one backtest."""

    account: AccountState
    position: Position | None = None
    prev_session: int | None = None
    position_sequence: int = 0
    current_execution_meta: dict[str, Any] = field(default_factory=dict)
    equity_curve: list[float] = field(default_factory=list)
    equity_times: list[pd.Timestamp] = field(default_factory=list)
    trade_log: list[dict[str, Any]] = field(default_factory=list)
    breach_log: list[str] = field(default_factory=list)
    breach_events: list[dict[str, Any]] = field(default_factory=list)
    breached_sessions: set[int] = field(default_factory=set)
    session_set: set[int] = field(default_factory=set)
    sessions_with_trades: set[int] = field(default_factory=set)
