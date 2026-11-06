"""Focused simulation transition service."""

from __future__ import annotations

from typing import Any, cast

import pandas as pd

from features.context.trade_setup_candidates import (
    trade_setup_event_identity_record,
    trade_setup_event_is_current,
)

from .market_view import BarView, FeatureRow
from .mixin_base import RuntimeMixinBase


class StepConstraintsRuntimeMixin(RuntimeMixinBase):
    """Apply eligibility and risk constraints before executing a step action."""

    _decision_action: dict[str, float]
    _pending_entry_order: dict[str, Any] | None
    _current_decision_id: str

    def _enforce_step_constraints(
        self,
        bar: BarView,
        feat_row: FeatureRow | pd.Series,
        bar_time: Any,
        session_id: int,
        fill_bid: float,
        fill_ask: float,
        fill_time: Any,
        pending_due: bool,
        entry_fill_bid: float,
        entry_fill_ask: float,
        entry_fill_time: Any,
        market_fill_idx: int,
    ) -> tuple[bool, bool, bool, bool]:
        # Check guardrails
        """Process step constraints.

        Args:
            bar: Bar used by the operation described above.
            feat_row: Feature values for the current market bar.
            bar_time: Bar time used by the operation described above.
            session_id: Numeric value used for the session id.
            fill_bid: Numeric value used for the fill bid.
            fill_ask: Numeric value used for the fill ask.
            fill_time: Fill time used by the operation described above.
            pending_due: Whether to enable or require the pending due.
            entry_fill_bid: Numeric value used for the entry fill bid.
            entry_fill_ask: Numeric value used for the entry fill ask.
            entry_fill_time: Entry fill time used by the operation described above.
            market_fill_idx: Numeric value used for the market fill idx.

        Returns:
            Whether enforce step constraints meets the requested condition.
        """
        position_has_completed_bar = True
        if self.position is not None and self.position.entry_timestamp is not None:
            bar_end = bar_time + pd.Timedelta(minutes=self._minutes_per_step)
            position_has_completed_bar = (
                pd.Timestamp(cast(Any, self.position.entry_timestamp)) < bar_end
            )
        if position_has_completed_bar:
            # A bar-close entry is effective at this bar's end. Its earlier
            # high/low cannot trigger a stop/target or position guard.
            self._check_sl_tp(bar, fill_bid, fill_ask)
            self._apply_position_guards(
                bar,
                bar_time,
                fill_bid,
                fill_ask,
                eod=False,
                feat_row=feat_row,
                bar_idx=self.step_idx,
                fill_time=fill_time,
            )

        # Apply account-level breaches after protective events on this bar,
        # matching the event-driven backtest. Otherwise a marked loss can
        # force-close a position before an already-triggered stop or target.
        reason, session_blocked, done, truncated = self._check_guardrails(
            bar_time, session_id, fill_bid, fill_ask, fill_time=fill_time
        )

        self._peak_dd_fired = False
        peak_dd_block = self._apply_peak_trailing_dd(
            fill_bid, fill_ask, bar_time, fill_time=fill_time
        )
        peak_dd_block = (
            self._apply_peak_eod_trailing_dd(
                fill_bid,
                fill_ask,
                bar_time,
                is_eod=self._is_ny_session_boundary(),
                fill_time=fill_time,
            )
            or peak_dd_block
        )

        # A resting limit order must not survive an account or session block
        # and fill later. Market orders keep their existing scheduled-fill
        # behavior; only policy-selected resting limits are canceled here.
        pending = self._pending_entry_order
        if pending is not None and pending.get("order_type") == "limit":
            pending_soft_block = self.guardrails.check_soft_daily(
                self.account
            ) or self.guardrails.check_soft_trailing_dd(self.account)
            cancel_reason = None
            selected = pending.get("selected", {})
            selected_setup = selected.get("_selected_trade_setup")
            if done:
                cancel_reason = "account_failed_before_limit_fill"
            elif self.block_overnight and int(pending["session_id"]) != int(session_id):
                cancel_reason = "session_changed_before_limit_fill"
            elif session_blocked:
                cancel_reason = "session_blocked_before_limit_fill"
            elif peak_dd_block:
                cancel_reason = "trailing_drawdown_blocked_before_limit_fill"
            elif pending_soft_block:
                cancel_reason = "soft_guardrail_blocked_before_limit_fill"
            else:
                if selected_setup is not None:
                    setup_validity = pending.pop("_source_setup_validity_at_current_row", None)
                    if setup_validity is None:
                        setup_validity = trade_setup_event_is_current(
                            selected.get("_selected_trade_setup_event_identity"), feat_row
                        )
                    setup_is_current, setup_reason = setup_validity
                    if not setup_is_current:
                        cancel_reason = setup_reason
            if cancel_reason is not None:
                self._pending_entry_order = None
                pending_due = False
                self.trade_log.append(
                    {
                        "type": "order_cancel",
                        "order_id": pending["order_id"],
                        "order_type": "limit",
                        "reason": cancel_reason,
                        "decision_id": pending.get("decision_id", self._current_decision_id),
                        "trade_setup_candidate_id": (
                            None if selected_setup is None else int(selected_setup.candidate_id)
                        ),
                        **trade_setup_event_identity_record(
                            selected.get("_selected_trade_setup_event_identity")
                        ),
                        "decision_bar_time": pending["decision_bar_time"],
                        "order_submission_time": pending["order_submission_time"],
                        "expiry_time": pending["expiry_time"],
                        "limit_price": pending["limit_price"],
                        "time": fill_time,
                    }
                )

        # A delayed entry becomes active only when its scheduled quote is the
        # market bar being processed. It cannot be marked or stopped earlier.
        if pending_due:
            pending = self._pending_entry_order
            self._pending_entry_order = None
            pending_soft_block = self.guardrails.check_soft_daily(
                self.account
            ) or self.guardrails.check_soft_trailing_dd(self.account)
            if (
                pending is not None
                and not done
                and not session_blocked
                and not peak_dd_block
                and not pending_soft_block
            ):
                pending_decision_id = str(pending.get("decision_id", self._current_decision_id))
                current_decision = self._decision_action
                current_decision_id = self._current_decision_id
                selected_names = (
                    "_selected_trade_setup",
                    "_selected_trade_setup_event_identity",
                    "_last_action_trade_setup_candidate_id",
                    "_last_action_trade_setup_eligible",
                    "_selected_sl_anchor",
                    "_selected_tp_fraction",
                    "_selected_exit_mode",
                    "_selected_sl_mode",
                    "_sl_mode_explicit",
                    "_selected_tp_mode",
                    "_tp_mode_explicit",
                    "_selected_tp_selections",
                    "_selected_tp_z",
                    "_selected_entry_execution",
                    "_selected_limit_offset_atr",
                    "_selected_limit_ttl_bars",
                )
                current_selected = {name: getattr(self, name) for name in selected_names}
                self._decision_action = dict(pending["decision_action"])
                self._current_decision_id = pending_decision_id
                for name, value in pending["selected"].items():
                    setattr(self, name, value)
                selected = pending.get("selected", {})
                selected_setup = selected.get("_selected_trade_setup")
                is_limit_order = pending.get("order_type") == "limit"
                quote = pending.get("fill_quote") if is_limit_order else None
                if is_limit_order:
                    if quote is None:
                        raise RuntimeError("due limit order has no executable tick quote")
                    limit_fill_event = {
                        "type": "order_fill",
                        "order_id": pending["order_id"],
                        "decision_id": pending.get("decision_id"),
                        "order_type": "limit",
                        "direction": int(pending["direction"]),
                        "trade_setup_candidate_id": (
                            None if selected_setup is None else int(selected_setup.candidate_id)
                        ),
                        **trade_setup_event_identity_record(
                            selected.get("_selected_trade_setup_event_identity")
                        ),
                        "limit_price": float(pending["limit_price"]),
                        "bid": float(quote.bid),
                        "ask": float(quote.ask),
                        "price": float(quote.ask if int(pending["direction"]) > 0 else quote.bid),
                        "time": pd.Timestamp(quote.tick_time),
                        "order_submission_time": pd.Timestamp(quote.order_time),
                    }
                else:
                    limit_fill_event = None
                self._try_enter_position(
                    int(pending["direction"]),
                    float(pending["risk_frac"]),
                    float(pending["rr_ratio"]),
                    bar,
                    pending["feat_row"],
                    pending["decision_bar_time"],
                    session_id,
                    entry_fill_bid,
                    entry_fill_ask,
                    entry_fill_time,
                    entry_candidate=pending["entry_candidate"],
                    fill_bar_idx=market_fill_idx,
                    order_submission_time=pending["order_submission_time"],
                    decision_bar_idx=int(pending["decision_bar_idx"]),
                    signal_bar_idx=int(pending["signal_bar_idx"]),
                    order_id=(
                        str(pending["order_id"]) if pending.get("order_id") is not None else None
                    ),
                )
                if not self._opened_this_step and pending.get("order_id") is not None:
                    selected = pending.get("selected", {})
                    selected_setup = selected.get("_selected_trade_setup")
                    self.trade_log.append(
                        {
                            "type": "order_cancel",
                            "order_id": pending["order_id"],
                            "decision_id": pending_decision_id,
                            "order_type": pending.get("order_type", "market"),
                            "reason": (
                                "entry_rejected_at_limit_fill"
                                if is_limit_order
                                else "entry_rejected_at_market_fill"
                            ),
                            "trade_setup_candidate_id": (
                                None if selected_setup is None else int(selected_setup.candidate_id)
                            ),
                            **trade_setup_event_identity_record(
                                selected.get("_selected_trade_setup_event_identity")
                            ),
                            "decision_bar_time": pending["decision_bar_time"],
                            "order_submission_time": pending["order_submission_time"],
                            **(
                                {
                                    "expiry_time": pending["expiry_time"],
                                    "limit_price": pending["limit_price"],
                                }
                                if is_limit_order
                                else {}
                            ),
                            "trigger_quote_time": (
                                pd.Timestamp(quote.tick_time)
                                if quote is not None
                                else pd.Timestamp(entry_fill_time)
                            ),
                            "trigger_quote_bid": float(
                                quote.bid if quote is not None else entry_fill_bid
                            ),
                            "trigger_quote_ask": float(
                                quote.ask if quote is not None else entry_fill_ask
                            ),
                            "trigger_quote_price": float(
                                (quote.ask if int(pending["direction"]) > 0 else quote.bid)
                                if quote is not None
                                else (
                                    entry_fill_ask
                                    if int(pending["direction"]) > 0
                                    else entry_fill_bid
                                )
                            ),
                            "time": pd.Timestamp(quote.tick_time)
                            if quote is not None
                            else pd.Timestamp(entry_fill_time),
                        }
                    )
                elif pending.get("order_id") is not None:
                    open_index = next(
                        (
                            index
                            for index, event in enumerate(self.trade_log)
                            if event.get("type") == "open"
                            and event.get("order_id") == pending["order_id"]
                        ),
                        None,
                    )
                    if open_index is None:
                        raise RuntimeError("pending order opened without a matching position event")
                    if is_limit_order:
                        if limit_fill_event is None:
                            raise RuntimeError(
                                "limit fill opened without executable quote evidence"
                            )
                        fill_event = limit_fill_event
                    else:
                        opened = self.trade_log[open_index]
                        actual_fill_time = opened.get(
                            "fill_time", opened.get("time", entry_fill_time)
                        )
                        fill_event = {
                            "type": "order_fill",
                            "order_id": pending["order_id"],
                            "decision_id": pending_decision_id,
                            "order_type": "market",
                            "direction": int(pending["direction"]),
                            "price": float(opened["price"]),
                            "bid": float(entry_fill_bid),
                            "ask": float(entry_fill_ask),
                            "time": pd.Timestamp(actual_fill_time),
                            "trade_setup_candidate_id": (
                                None if selected_setup is None else int(selected_setup.candidate_id)
                            ),
                            **trade_setup_event_identity_record(
                                pending.get("selected", {}).get(
                                    "_selected_trade_setup_event_identity"
                                )
                            ),
                        }
                    self.trade_log.insert(open_index, fill_event)
                self._decision_action = current_decision
                self._current_decision_id = current_decision_id
                for name, value in current_selected.items():
                    setattr(self, name, value)
            elif pending is not None and pending.get("order_id") is not None:
                selected = pending.get("selected", {})
                selected_setup = selected.get("_selected_trade_setup")
                self.trade_log.append(
                    {
                        "type": "order_cancel",
                        "order_id": pending["order_id"],
                        "decision_id": pending.get("decision_id"),
                        "order_type": pending.get("order_type", "market"),
                        "reason": "entry_blocked_before_fill",
                        "trade_setup_candidate_id": (
                            None if selected_setup is None else int(selected_setup.candidate_id)
                        ),
                        **trade_setup_event_identity_record(
                            selected.get("_selected_trade_setup_event_identity")
                        ),
                        "decision_bar_time": pending["decision_bar_time"],
                        "order_submission_time": pending["order_submission_time"],
                        "time": pd.Timestamp(entry_fill_time),
                    }
                )
            elif pending is not None:
                selected = pending.get("selected", {})
                selected_setup = selected.get("_selected_trade_setup")
                self.trade_log.append(
                    {
                        "type": "order_cancel",
                        "decision_id": str(pending.get("decision_id", self._current_decision_id)),
                        "order_id": pending.get("order_id"),
                        "order_type": pending.get("order_type", "market"),
                        "trade_setup_candidate_id": (
                            None if selected_setup is None else int(selected_setup.candidate_id)
                        ),
                        **trade_setup_event_identity_record(
                            selected.get("_selected_trade_setup_event_identity")
                        ),
                        "reason": "execution_blocked_before_scheduled_fill",
                        "decision_time": pending["decision_time"],
                        "decision_bar_time": pending["decision_bar_time"],
                        "order_submission_time": pending["order_submission_time"],
                        "time": fill_time,
                        "fill_time": None,
                        "bar": self.step_idx,
                    }
                )

        return done, truncated, session_blocked, peak_dd_block


__all__ = ["StepConstraintsRuntimeMixin"]
