from __future__ import annotations

from typing import Any

import pandas as pd

from trading.execution import Position

from .entry_order_runtime import EntryOrderRuntimeMixin
from .entry_state import EntryCandidate
from .market_view import BarView, FeatureRow
from .mixin_base import RuntimeMixinBase
from .position_open_runtime import PositionOpenRuntimeMixin
from .trade_entry_record_runtime import TradeEntryRecordRuntimeMixin


class EntryExecutionRuntimeMixin(
    EntryOrderRuntimeMixin,
    PositionOpenRuntimeMixin,
    TradeEntryRecordRuntimeMixin,
    RuntimeMixinBase,
):
    position: Position | None
    _opened_this_step: bool
    _position_sequence: int

    def _resolve_entry_execution_quote(
        self,
        fill_bid: float,
        fill_ask: float,
        fill_time: Any,
        order_submission_time: Any | None,
    ) -> tuple[float, float, Any, dict[str, Any]]:
        execution_meta: dict[str, Any] = {}
        if (
            getattr(self, "tick_execution_required", False)
            or getattr(self, "randomized_fill_latency_ms", 0.0) > 0
        ):
            active_execution = getattr(self, "_active_step_execution", None)
            if active_execution is not None:
                execution_quote = active_execution["quote"]
                execution_meta = dict(active_execution["metadata"])
                execution_order_time = execution_quote.order_time
            else:
                execution_order_time = (
                    pd.Timestamp(fill_time)
                    if self.fill_latency_bars > 0
                    else pd.Timestamp(
                        fill_time if order_submission_time is None else order_submission_time
                    )
                )
                execution_quote, execution_meta = self._resolve_randomized_tick_quote(
                    execution_order_time
                )
            fill_bid, fill_ask = execution_quote.bid, execution_quote.ask
            fill_time = execution_quote.tick_time
            execution_meta["execution_order_time"] = execution_order_time
        return fill_bid, fill_ask, fill_time, execution_meta

    def _close_opposing_position(
        self,
        discrete_action: int,
        fill_bid: float,
        fill_ask: float,
        fill_time: Any,
        bar_time: Any,
        order_submission_time: Any | None,
        session_id: int,
        execution_meta: dict[str, Any],
    ) -> None:
        if self.position is not None and self.position.direction != discrete_action:
            pnl, fill_price = self._close_at_quote(
                self.position,
                (fill_bid, fill_ask),
                tick_fill=bool(execution_meta),
            )
            record = {
                "type": "close",
                "pnl": pnl,
                "price": fill_price,
                "fill_quote_source": "tick" if execution_meta else "bar_open",
                "bar": self.step_idx,
                "time": fill_time,
                "decision_time": bar_time,
                "order_submission_time": (
                    bar_time if order_submission_time is None else order_submission_time
                ),
                "fill_time": fill_time,
                "equity": self.account.equity,
                **execution_meta,
            }
            self._stamp_exit(record, fill_price)
            self.trade_log.append(record)
            self.position = None
            self.sessions_with_trades.add(session_id)
            self._note_close(pnl)

    def _open_entry_position(
        self,
        discrete_action: int,
        fill_bid: float,
        fill_ask: float,
        lots: float,
        sl_price: float | None,
    ) -> tuple[float, bool]:
        entry_equity = float(self.account.equity)
        sl_already_hit = False
        if sl_price is not None:
            if discrete_action == 1 and fill_bid <= sl_price:
                sl_already_hit = True
            elif discrete_action == -1 and fill_ask >= sl_price:
                sl_already_hit = True
        if not sl_already_hit:
            self.position = self._open_at_quote(
                (fill_bid, fill_ask),
                lots,
                discrete_action,
                tick_fill=(
                    bool(getattr(self, "tick_execution_required", False))
                    or float(getattr(self, "randomized_fill_latency_ms", 0.0)) > 0.0
                ),
            )
        else:
            self.position = None
            self._reject("sl_already_hit")
        return entry_equity, self.position is not None

    def _try_enter_position(
        self,
        discrete_action: int,
        risk_frac: float,
        rr_ratio: float,
        bar: BarView,
        feat_row: FeatureRow | pd.Series,
        bar_time: Any,
        session_id: int,
        fill_bid: float,
        fill_ask: float,
        fill_time: Any,
        entry_candidate: EntryCandidate | None = None,
        fill_bar_idx: int | None = None,
        order_submission_time: Any | None = None,
        decision_bar_idx: int | None = None,
        signal_bar_idx: int | None = None,
    ) -> None:
        """Attempt a flip or new entry through explicit execution stages."""
        fill_bid, fill_ask, fill_time, execution_meta = self._resolve_entry_execution_quote(
            fill_bid, fill_ask, fill_time, order_submission_time
        )
        self._close_opposing_position(
            discrete_action,
            fill_bid,
            fill_ask,
            fill_time,
            bar_time,
            order_submission_time,
            session_id,
            execution_meta,
        )
        if self.position is not None or discrete_action not in (1, -1):
            return
        entry_price, sl_price, tp_price, lots, has_levels, placed = self._build_entry_levels(
            discrete_action, risk_frac, rr_ratio, feat_row, fill_bid, fill_ask
        )
        if not has_levels:
            return
        if not self._entry_risk_capacity_allows(entry_price, sl_price, lots, has_levels):
            return
        entry_equity, opened = self._open_entry_position(
            discrete_action, fill_bid, fill_ask, lots, sl_price
        )
        if not opened:
            return
        entry_level, sweep_delay, signal_bar, signal_time = self._initialize_open_position(
            discrete_action,
            risk_frac,
            rr_ratio,
            entry_price,
            sl_price,
            tp_price,
            placed,
            feat_row,
            fill_time,
            session_id,
            entry_candidate,
            bar_time,
            signal_bar_idx,
        )
        self._append_open_trade(
            discrete_action=discrete_action,
            risk_frac=risk_frac,
            bar=bar,
            feat_row=feat_row,
            bar_time=bar_time,
            session_id=session_id,
            fill_time=fill_time,
            sl_price=sl_price,
            tp_price=tp_price,
            placed=placed,
            entry_price=entry_price,
            entry_equity=entry_equity,
            execution_meta=execution_meta,
            entry_candidate=entry_candidate,
            fill_bar_idx=fill_bar_idx,
            order_submission_time=order_submission_time,
            decision_bar_idx=decision_bar_idx,
            signal_bar=signal_bar,
            signal_time=signal_time,
            entry_level=entry_level,
            sweep_delay=sweep_delay,
        )
