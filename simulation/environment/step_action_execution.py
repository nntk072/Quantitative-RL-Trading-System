"""Focused simulation transition service."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from features.context.trade_setup_candidates import trade_setup_event_is_current
from market_data.loading.ticks import (
    TickExecutionUnavailable,
    limit_entry_execution_rng,
    resolve_tick_limit_execution,
)
from simulation.entry_state import EntryCandidate
from trading.execution import Position
from trading.orders import limit_order_expiry, limit_price_from_atr_offset

from .market_view import BarView, FeatureRow
from .mixin_base import RuntimeMixinBase


class StepActionExecutionMixin(RuntimeMixinBase):
    """Apply decoded actions to exits, pending entries, and execution."""

    position: Position | None
    _pending_entry_order: dict[str, Any] | None

    def _submit_limit_entry_order(
        self,
        *,
        direction: int,
        risk_frac: float,
        rr_ratio: float,
        bar: BarView,
        feat_row: FeatureRow | pd.Series,
        bar_time: Any,
        session_id: int,
        entry_candidate: EntryCandidate | None,
    ) -> bool:
        """Submit a policy-priced limit and retain its first eligible tick fill.

        Args:
            direction: Trade direction, ``1`` for long or ``-1`` for short.
            risk_frac: Policy-selected risk fraction for the position.
            rr_ratio: Requested reward-to-risk ratio.
            bar: Current OHLC bar used as the causal limit-price reference.
            feat_row: Current feature row used for setup and volatility checks.
            bar_time: Timestamp of the current decision bar.
            session_id: Active trading session identifier.
            entry_candidate: Selected candidate whose source validity is checked.

        Returns:
            Whether a valid pending limit order was submitted.
        """
        if self._selected_trade_setup is not None:
            identity = self._selected_trade_setup_event_identity
            if identity is None or identity.status != "identified":
                self._reject("limit_entry_source_identity_unavailable")
                return False
            source_is_current, _ = trade_setup_event_is_current(identity, feat_row)
            if not source_is_current:
                self._reject("limit_entry_source_setup_unavailable")
                return False
        atr_value = feat_row.get("atr_5", feat_row.get("atr", np.nan))
        try:
            atr = float(atr_value)
        except (TypeError, ValueError):
            atr = float("nan")
        if not np.isfinite(atr) or atr <= 0.0:
            self._reject("limit_entry_missing_atr")
            return False
        submission_time = pd.Timestamp(bar_time) + pd.Timedelta(minutes=self._minutes_per_step)
        expiry_time = limit_order_expiry(
            submission_time,
            self._selected_limit_ttl_bars,
            pd.Timedelta(minutes=self._minutes_per_step),
        )
        limit_price = limit_price_from_atr_offset(
            direction=direction,
            reference_price=float(bar.close),
            atr=atr,
            offset_atr=float(self._selected_limit_offset_atr),
            point_size=float(self.cost_model.point_size),
        )
        if self._tickbook is None:
            raise TickExecutionUnavailable(
                "policy-selected limit entries require TickBook quote chronology"
            )
        order_id = f"{self._current_decision_id}:limit"
        max_latency_ns = int(float(self.randomized_fill_latency_ms) * 1_000_000)
        fill_quote = resolve_tick_limit_execution(
            self._tickbook,
            direction,
            limit_price,
            submission_time,
            expiry_time,
            limit_entry_execution_rng(
                int(self.np_random_seed),
                submission_time,
                direction,
                limit_price,
                (
                    None
                    if self._selected_trade_setup is None
                    else self._selected_trade_setup.candidate_id
                ),
            ),
            max_latency_ns_exclusive=max_latency_ns,
            require_trade_through=self.limit_order_require_trade_through,
        )
        stored_feat_row: FeatureRow | pd.Series = feat_row
        if isinstance(feat_row, pd.Series):
            stored_feat_row = feat_row.copy()
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
        self._pending_entry_order = {
            "order_id": order_id,
            "order_type": "limit",
            "decision_id": self._current_decision_id,
            "direction": direction,
            "risk_frac": risk_frac,
            "rr_ratio": rr_ratio,
            "feat_row": stored_feat_row,
            "decision_time": submission_time,
            "decision_bar_time": bar_time,
            "decision_bar_idx": self.step_idx,
            "signal_bar_idx": self.step_idx,
            "signal_time": submission_time,
            "order_submission_time": submission_time,
            "expiry_time": expiry_time,
            "limit_price": limit_price,
            "entry_candidate": entry_candidate,
            "decision_action": dict(self._decision_action),
            "selected": {name: getattr(self, name) for name in selected_names},
            "fill_quote": fill_quote,
            "session_id": session_id,
        }
        selected_setup = self._selected_trade_setup if self.trade_setup_actions else None
        setup_identity: dict[str, Any] = {}
        if selected_setup is not None:
            from features.context.trade_setup_candidates import trade_setup_event_identity_record

            setup_identity = {
                "trade_setup_candidate_id": int(selected_setup.candidate_id),
                "trade_setup_schema_version": self.action_schema.version,
                "primary_idea": str(selected_setup.idea or ""),
                "primary_setup_timeframe": str(selected_setup.setup_timeframe or ""),
                "primary_direction": int(selected_setup.direction),
                **trade_setup_event_identity_record(self._selected_trade_setup_event_identity),
            }
        self.trade_log.append(
            {
                "type": "order_submit",
                "order_id": order_id,
                "order_type": "limit",
                "direction": direction,
                "decision_id": self._current_decision_id,
                "decision_bar_time": bar_time,
                "decision_time": submission_time,
                "order_submission_time": submission_time,
                "limit_price": limit_price,
                "limit_offset_atr": float(self._selected_limit_offset_atr),
                "ttl_bars": int(self._selected_limit_ttl_bars),
                "expiry_time": expiry_time,
                "time": submission_time,
                "bar": self.step_idx,
                **setup_identity,
            }
        )
        return True

    def _execute_step_action(
        self,
        action: int | float | np.ndarray[Any, Any],
        discrete_action: int,
        risk_frac: float,
        rr_ratio: float,
        bar: BarView,
        feat_row: FeatureRow | pd.Series,
        bar_time: Any,
        session_id: int,
        fill_idx: int,
        action_fill_time: Any,
        fill_bid: float,
        fill_ask: float,
        fill_time: Any,
        entry_fill_bid: float,
        entry_fill_ask: float,
        entry_fill_time: Any,
        market_fill_idx: int,
        entry_candidate: EntryCandidate | None,
        done: bool,
        pending_due: bool,
        session_blocked: bool,
        peak_dd_block: bool,
    ) -> None:
        # Action handling
        """Execute step action.

        Args:
            action: Action to apply to the current state.
            discrete_action: Numeric value used for the discrete action.
            risk_frac: Numeric value used for the risk frac.
            rr_ratio: Numeric value used for the rr ratio.
            bar: Bar used by the operation described above.
            feat_row: Feature values for the current market bar.
            bar_time: Bar time used by the operation described above.
            session_id: Numeric value used for the session id.
            fill_idx: Numeric value used for the fill idx.
            action_fill_time: Action fill time used by the operation described above.
            fill_bid: Numeric value used for the fill bid.
            fill_ask: Numeric value used for the fill ask.
            fill_time: Fill time used by the operation described above.
            entry_fill_bid: Numeric value used for the entry fill bid.
            entry_fill_ask: Numeric value used for the entry fill ask.
            entry_fill_time: Entry fill time used by the operation described above.
            market_fill_idx: Numeric value used for the market fill idx.
            entry_candidate: Entry candidate used by the operation described above.
            done: Whether to enable or require the done.
            pending_due: Whether to enable or require the pending due.
            session_blocked: Whether to enable or require the session blocked.
            peak_dd_block: Whether to enable or require the peak dd block.
        """
        if not done and not pending_due:
            if not self.strategy_actions and action == 19:  # exit action
                if self.position is not None:
                    execution_meta = {}
                    # An action selected on this bar submits for the next
                    # market bar. ``fill_time`` is the following valuation
                    # boundary used by the step accounting path, one bar
                    # later than the executable action quote.
                    action_fill_bid, action_fill_ask = entry_fill_bid, entry_fill_ask
                    action_fill_time = entry_fill_time
                    active_execution = getattr(self, "_active_step_execution", None)
                    if active_execution is not None:
                        quote = active_execution["quote"]
                        execution_meta = dict(active_execution["metadata"])
                        action_fill_bid, action_fill_ask = quote.bid, quote.ask
                        action_fill_time = quote.tick_time
                    elif getattr(self, "tick_execution_required", False):
                        quote, execution_meta = self._resolve_randomized_tick_quote(
                            pd.Timestamp(entry_fill_time)
                        )
                        action_fill_bid, action_fill_ask = quote.bid, quote.ask
                        action_fill_time = quote.tick_time
                    pnl, fill_price = self._close_at_quote(
                        self.position,
                        (action_fill_bid, action_fill_ask),
                        tick_fill=True,
                    )
                    record = {
                        "type": "close",
                        "pnl": pnl,
                        "price": fill_price,
                        "fill_quote_source": "tick" if execution_meta else "bar_open",
                        "bar": self.step_idx,
                        "time": action_fill_time,
                        "decision_time": bar_time + pd.Timedelta(minutes=self._minutes_per_step),
                        "decision_bar_time": bar_time,
                        "order_submission_time": bar_time
                        + pd.Timedelta(minutes=self._minutes_per_step),
                        "fill_time": action_fill_time,
                        "equity": self.account.equity,
                        **execution_meta,
                    }
                    self._stamp_exit(record, fill_price)
                    self.trade_log.append(record)
                    self.position = None
                    self.sessions_with_trades.add(session_id)
                    self._note_close(pnl)
            elif discrete_action != 0 and fill_idx >= self._n_bars:
                self._reject("terminal_no_fill_bar")
            elif discrete_action != 0 and not session_blocked and not peak_dd_block:
                # A live resting limit owns the account's single pending-entry
                # slot. Ignore subsequent entry requests until it fills or
                # expires; replacing it implicitly could leave two executable
                # orders on the same policy decision stream.
                if (
                    self.agent_entry_execution
                    and self._pending_entry_order is not None
                    and self._pending_entry_order.get("order_type") == "limit"
                ):
                    self._reject("entry_pending")
                # Soft brick: stop new entries on daily-loss or trailing-DD
                # soft limits; hard breaches still use session_blocked.
                elif self.guardrails.check_soft_daily(
                    self.account
                ) or self.guardrails.check_soft_trailing_dd(self.account):
                    # Soft brick on daily loss or trailing DD. Renamed from
                    # ``soft_brick`` so it counts in the rejected_* funnel; the
                    # reason key below was never set before, so the rejection
                    # was invisible in both the buckets and the trade log.
                    self._reject("soft_brick")
                else:
                    if self.agent_entry_execution and self._selected_entry_execution == "limit":
                        if self.position is not None:
                            self._reject("limit_entry_requires_flat_account")
                            return
                        self._submit_limit_entry_order(
                            direction=discrete_action,
                            risk_frac=risk_frac,
                            rr_ratio=rr_ratio,
                            bar=bar,
                            feat_row=feat_row,
                            bar_time=bar_time,
                            session_id=session_id,
                            entry_candidate=entry_candidate,
                        )
                        return
                    if self.fill_latency_bars > 0:
                        order_id = f"{self._current_decision_id}:market"
                        stored_feat_row: FeatureRow | pd.Series = feat_row
                        if isinstance(feat_row, pd.Series):
                            stored_feat_row = feat_row.copy()
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
                        self._pending_entry_order = {
                            "order_id": order_id,
                            "order_type": "market",
                            "decision_id": self._current_decision_id,
                            "fill_idx": fill_idx,
                            "direction": discrete_action,
                            "risk_frac": risk_frac,
                            "rr_ratio": rr_ratio,
                            "feat_row": stored_feat_row,
                            "decision_time": bar_time
                            + pd.Timedelta(minutes=self._minutes_per_step),
                            "decision_bar_time": bar_time,
                            "decision_bar_idx": self.step_idx,
                            "signal_bar_idx": self.step_idx,
                            "signal_time": bar_time + pd.Timedelta(minutes=self._minutes_per_step),
                            "order_submission_time": bar_time
                            + pd.Timedelta(minutes=self._minutes_per_step),
                            "entry_candidate": entry_candidate,
                            "decision_action": dict(self._decision_action),
                            "selected": {name: getattr(self, name) for name in selected_names},
                        }
                        selected_setup = (
                            self._selected_trade_setup if self.trade_setup_actions else None
                        )
                        if selected_setup is not None:
                            setup_identity = {
                                "trade_setup_candidate_id": int(selected_setup.candidate_id),
                                "trade_setup_schema_version": self.action_schema.version,
                            }
                            from features.context.trade_setup_candidates import (
                                trade_setup_event_identity_record,
                            )

                            setup_identity.update(
                                trade_setup_event_identity_record(
                                    self._selected_trade_setup_event_identity
                                )
                            )
                        else:
                            setup_identity = {}
                        self.trade_log.append(
                            {
                                "type": "order_submit",
                                "order_id": order_id,
                                "order_type": "market",
                                "decision_id": self._current_decision_id,
                                "direction": discrete_action,
                                **setup_identity,
                                "primary_idea": (
                                    selected_setup.idea if selected_setup is not None else ""
                                ),
                                "primary_setup_timeframe": (
                                    selected_setup.setup_timeframe
                                    if selected_setup is not None
                                    else ""
                                ),
                                "primary_direction": (
                                    selected_setup.direction if selected_setup is not None else 0
                                ),
                                "time": bar_time,
                                "decision_time": bar_time
                                + pd.Timedelta(minutes=self._minutes_per_step),
                                "decision_bar_time": bar_time,
                                "signal_bar": self.step_idx,
                                "signal_time": bar_time
                                + pd.Timedelta(minutes=self._minutes_per_step),
                                "order_submission_bar": self.step_idx,
                                "order_submission_time": bar_time
                                + pd.Timedelta(minutes=self._minutes_per_step),
                                "expected_fill_time": action_fill_time,
                                "fill_time": None,
                                "bar": self.step_idx,
                            }
                        )
                    else:
                        order_id = f"{self._current_decision_id}:market"
                        order_submission_time = bar_time + pd.Timedelta(
                            minutes=self._minutes_per_step
                        )
                        selected_setup = (
                            self._selected_trade_setup if self.trade_setup_actions else None
                        )
                        market_setup_identity: dict[str, Any] = {}
                        if selected_setup is not None:
                            from features.context.trade_setup_candidates import (
                                trade_setup_event_identity_record,
                            )

                            market_setup_identity = {
                                "trade_setup_candidate_id": int(selected_setup.candidate_id),
                                "trade_setup_schema_version": self.action_schema.version,
                                **trade_setup_event_identity_record(
                                    self._selected_trade_setup_event_identity
                                ),
                            }
                        self.trade_log.append(
                            {
                                "type": "order_submit",
                                "order_id": order_id,
                                "order_type": "market",
                                "decision_id": self._current_decision_id,
                                "direction": discrete_action,
                                **market_setup_identity,
                                "time": bar_time,
                                "decision_time": bar_time,
                                "decision_bar_time": bar_time,
                                "order_submission_time": order_submission_time,
                                "expected_fill_time": entry_fill_time,
                                "bar": self.step_idx,
                            }
                        )
                        self._try_enter_position(
                            discrete_action,
                            risk_frac,
                            rr_ratio,
                            bar,
                            feat_row,
                            bar_time,
                            session_id,
                            entry_fill_bid,
                            entry_fill_ask,
                            entry_fill_time,
                            entry_candidate=entry_candidate,
                            fill_bar_idx=market_fill_idx,
                            order_submission_time=order_submission_time,
                            decision_bar_idx=self.step_idx,
                            signal_bar_idx=self.step_idx,
                            order_id=order_id,
                        )
                        open_index = next(
                            (
                                index
                                for index, event in enumerate(self.trade_log)
                                if event.get("type") == "open" and event.get("order_id") == order_id
                            ),
                            None,
                        )
                        if open_index is None:
                            self.trade_log.append(
                                {
                                    "type": "order_cancel",
                                    "order_id": order_id,
                                    "order_type": "market",
                                    "decision_id": self._current_decision_id,
                                    "reason": "entry_rejected_at_market_fill",
                                    **market_setup_identity,
                                    "order_submission_time": order_submission_time,
                                    "trigger_quote_time": pd.Timestamp(entry_fill_time),
                                    "trigger_quote_bid": float(entry_fill_bid),
                                    "trigger_quote_ask": float(entry_fill_ask),
                                    "trigger_quote_price": float(
                                        entry_fill_ask if discrete_action > 0 else entry_fill_bid
                                    ),
                                    "time": pd.Timestamp(entry_fill_time),
                                }
                            )
                        else:
                            opened = self.trade_log[open_index]
                            actual_fill_time = opened.get(
                                "fill_time", opened.get("time", entry_fill_time)
                            )
                            self.trade_log.insert(
                                open_index,
                                {
                                    "type": "order_fill",
                                    "order_id": order_id,
                                    "order_type": "market",
                                    "decision_id": self._current_decision_id,
                                    "direction": discrete_action,
                                    "price": float(opened["price"]),
                                    "bid": float(entry_fill_bid),
                                    "ask": float(entry_fill_ask),
                                    "time": pd.Timestamp(actual_fill_time),
                                    **market_setup_identity,
                                },
                            )


__all__ = ["StepActionExecutionMixin"]
