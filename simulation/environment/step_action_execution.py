"""Focused simulation transition service."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from trading.execution import Position

from .entry_state import EntryCandidate
from .market_view import BarView, FeatureRow
from .mixin_base import RuntimeMixinBase


class StepActionExecutionMixin(RuntimeMixinBase):
    position: Position | None
    _pending_entry_order: dict[str, Any] | None

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
        entry_machine: Any,
        done: bool,
        pending_due: bool,
        session_blocked: bool,
        peak_dd_block: bool,
    ) -> None:
        # Action handling
        if not done and not pending_due:
            if not self.strategy_actions and action == 19:  # exit action
                if self.position is not None:
                    execution_meta = {}
                    action_fill_bid, action_fill_ask = fill_bid, fill_ask
                    action_fill_time = fill_time
                    if getattr(self, "tick_execution_required", False):
                        quote, execution_meta = self._resolve_randomized_tick_quote(
                            pd.Timestamp(fill_time)
                        )
                        action_fill_bid, action_fill_ask = quote.bid, quote.ask
                        action_fill_time = quote.tick_time
                    pnl, fill_price = self._close_at_quote(
                        self.position,
                        (action_fill_bid, action_fill_ask),
                        tick_fill=bool(execution_meta),
                    )
                    record = {
                        "type": "close",
                        "pnl": pnl,
                        "price": fill_price,
                        "fill_quote_source": "tick" if execution_meta else "bar_open",
                        "bar": self.step_idx,
                        "time": action_fill_time,
                        "decision_time": bar_time,
                        "order_submission_time": bar_time,
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
                # Soft brick: stop new entries on daily-loss or trailing-DD
                # soft limits; hard breaches still use session_blocked.
                if self.guardrails.check_soft_daily(
                    self.account
                ) or self.guardrails.check_soft_trailing_dd(self.account):
                    # Soft brick on daily loss or trailing DD. Renamed from
                    # ``soft_brick`` so it counts in the rejected_* funnel; the
                    # reason key below was never set before, so the rejection
                    # was invisible in both the buckets and the trade log.
                    self._reject("soft_brick")
                else:
                    if self.fill_latency_bars > 0:
                        stored_feat_row: FeatureRow | pd.Series = feat_row
                        if isinstance(feat_row, pd.Series):
                            stored_feat_row = feat_row.copy()
                        selected_names = (
                            "_selected_trade_setup",
                            "_selected_sl_anchor",
                            "_selected_tp_fraction",
                            "_selected_exit_mode",
                            "_selected_sl_mode",
                            "_sl_mode_explicit",
                            "_selected_tp_mode",
                            "_tp_mode_explicit",
                            "_selected_tp_selections",
                            "_selected_tp_z",
                        )
                        self._pending_entry_order = {
                            "fill_idx": fill_idx,
                            "direction": discrete_action,
                            "risk_frac": risk_frac,
                            "rr_ratio": rr_ratio,
                            "feat_row": stored_feat_row,
                            "decision_time": bar_time,
                            "decision_bar_idx": self.step_idx,
                            "signal_bar_idx": self.step_idx,
                            "signal_time": bar_time + pd.Timedelta(minutes=self._minutes_per_step),
                            "order_submission_time": bar_time
                            + pd.Timedelta(minutes=self._minutes_per_step),
                            "entry_candidate": entry_candidate,
                            "decision_action": dict(self._decision_action),
                            "selected": {name: getattr(self, name) for name in selected_names},
                        }
                        thesis = self._selected_trade_setup if self.trade_setup_actions else None
                        if thesis is not None and self.legacy_thesis_contract:
                            from decisioning.trade_setup import LEGACY_THESIS_ACTION_VERSION

                            setup_identity = {
                                "thesis_candidate_id": int(thesis.candidate_id),
                                "thesis_schema_version": LEGACY_THESIS_ACTION_VERSION,
                            }
                        elif thesis is not None:
                            from decisioning.trade_setup import TRADE_SETUP_ACTION_VERSION

                            setup_identity = {
                                "trade_setup_candidate_id": int(thesis.candidate_id),
                                "trade_setup_schema_version": TRADE_SETUP_ACTION_VERSION,
                            }
                        else:
                            setup_identity = {}
                        self.trade_log.append(
                            {
                                "type": "order_submit",
                                "direction": discrete_action,
                                **setup_identity,
                                "primary_idea": thesis.idea if thesis is not None else "",
                                "primary_setup_timeframe": (
                                    thesis.setup_timeframe if thesis is not None else ""
                                ),
                                "primary_direction": thesis.direction if thesis is not None else 0,
                                "time": bar_time,
                                "decision_time": bar_time,
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
                            order_submission_time=bar_time
                            + pd.Timedelta(minutes=self._minutes_per_step),
                            decision_bar_idx=self.step_idx,
                            signal_bar_idx=self.step_idx,
                        )
                        if entry_machine is not None and self._opened_this_step:
                            entry_machine.mark_entered()


__all__ = ["StepActionExecutionMixin"]
