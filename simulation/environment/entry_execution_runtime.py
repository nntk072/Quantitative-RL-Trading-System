from __future__ import annotations

from typing import Any

import pandas as pd

from simulation.entry_state import EntryCandidate
from trading.execution import FILL_COST_PROVENANCE_SCHEMA_VERSION, Position

from .entry_order_runtime import EntryOrderRuntimeMixin
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
    """Resolve entry quotes, opposing positions, and accepted position opens."""

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
        """Resolve entry execution quote.

        Args:
            fill_bid: Numeric value used for the fill bid.
            fill_ask: Numeric value used for the fill ask.
            fill_time: Fill time used by the operation described above.
            order_submission_time: Order submission time used by the operation described above.

        Returns:
            Mapping from ``str`` keys to ``Any]`` values.
        """
        execution_meta: dict[str, Any] = {}
        active_execution = getattr(self, "_active_step_execution", None)
        if active_execution is not None:
            execution_quote = active_execution["quote"]
            execution_meta = dict(active_execution["metadata"])
            execution_order_time = execution_quote.order_time
            fill_bid, fill_ask = execution_quote.bid, execution_quote.ask
            fill_time = execution_quote.tick_time
            execution_meta["execution_order_time"] = execution_order_time
        elif (
            getattr(self, "tick_execution_required", False)
            or getattr(self, "randomized_fill_latency_ms", 0.0) > 0
        ):
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
        """Close opposing position.

        Args:
            discrete_action: Numeric value used for the discrete action.
            fill_bid: Numeric value used for the fill bid.
            fill_ask: Numeric value used for the fill ask.
            fill_time: Fill time used by the operation described above.
            bar_time: Bar time used by the operation described above.
            order_submission_time: Order submission time used by the operation described above.
            session_id: Numeric value used for the session id.
            execution_meta: Key-value data used for the execution meta.
        """
        if self.position is not None and self.position.direction != discrete_action:
            pnl, fill_price = self._close_at_quote(
                self.position,
                (fill_bid, fill_ask),
                tick_fill=True,
            )
            record = {
                "type": "close",
                "pnl": pnl,
                "price": fill_price,
                "fill_quote_source": execution_meta.get("fill_quote_source", "bar_open"),
                "bar": self.step_idx,
                "time": fill_time,
                "decision_time": (
                    pd.Timestamp(order_submission_time)
                    if order_submission_time is not None
                    else pd.Timestamp(bar_time) + pd.Timedelta(minutes=self._minutes_per_step)
                ),
                "decision_bar_time": bar_time,
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
        """Open entry position.

        Args:
            discrete_action: Numeric value used for the discrete action.
            fill_bid: Numeric value used for the fill bid.
            fill_ask: Numeric value used for the fill ask.
            lots: Numeric value used for the lots.
            sl_price: Sl price used by the operation described above.

        Returns:
            Whether open entry position meets the requested condition.
        """
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
                # Entry quote stress is applied before geometry and sizing in
                # _try_enter_position; applying it again here would double it.
                tick_fill=False,
            )
            if self.position is None:
                self._reject("insufficient_margin")
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
        order_id: str | None = None,
    ) -> None:
        """Attempt a flip or new entry through explicit execution stages.

        Args:
            discrete_action: Numeric value used for the discrete action.
            risk_frac: Numeric value used for the risk frac.
            rr_ratio: Numeric value used for the rr ratio.
            bar: Bar used by the operation described above.
            feat_row: Feature values for the current market bar.
            bar_time: Bar time used by the operation described above.
            session_id: Numeric value used for the session id.
            fill_bid: Numeric value used for the fill bid.
            fill_ask: Numeric value used for the fill ask.
            fill_time: Fill time used by the operation described above.
            entry_candidate: Entry candidate used by the operation described above.
            fill_bar_idx: Fill bar idx used by the operation described above.
            order_submission_time: Order submission time used by the operation described above.
            decision_bar_idx: Decision bar idx used by the operation described above.
            signal_bar_idx: Signal bar idx used by the operation described above.
            order_id: Pending order identity, when the entry came from a resting order.
        """
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
        # Size and place protection from the quote that will actually open a
        # market position. Resting limits retain their hard price bound and do
        # not receive adverse market slippage.
        market_fill = execution_meta.get("order_type") != "limit"
        pre_execution_quote = (float(fill_bid), float(fill_ask))
        if market_fill:
            fill_bid, fill_ask = self._adverse_tick_fill_quote(
                (fill_bid, fill_ask), discrete_action, opening=True
            )
            if self.tick_fill_slippage_points > 0.0:
                execution_meta["entry_slippage_applied"] = True
                execution_meta["entry_slippage_points"] = self.tick_fill_slippage_points
        execution_meta.update(
            {
                "fill_cost_provenance_schema_version": FILL_COST_PROVENANCE_SCHEMA_VERSION,
                "pre_execution_quote_bid": pre_execution_quote[0],
                "pre_execution_quote_ask": pre_execution_quote[1],
                "broker_execution_quote_bid": float(fill_bid),
                "broker_execution_quote_ask": float(fill_ask),
                "slippage_points_applied_here": (
                    float(self.tick_fill_slippage_points) if market_fill else 0.0
                ),
                "slippage_applied_here": bool(market_fill and self.tick_fill_slippage_points > 0.0),
                "slippage_application_mode": (
                    "transacted_side"
                    if market_fill and self.tick_fill_slippage_points > 0.0
                    else "none"
                ),
            }
        )
        entry_price, sl_price, tp_price, lots, has_levels, placed = self._build_entry_levels(
            discrete_action,
            risk_frac,
            rr_ratio,
            feat_row,
            fill_bid,
            fill_ask,
            entry_reference_price=(
                float(execution_meta["limit_price"])
                if execution_meta.get("order_type") == "limit"
                else None
            ),
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
            order_id=order_id,
        )
