from __future__ import annotations

from typing import Any

import pandas as pd

from features.context.trade_setup_candidates import active_trade_setup_candidates

from .entry_diagnostics import _previous_session_audit
from .entry_state import EntryCandidate
from .market_view import BarView, FeatureRow
from .mixin_base import RuntimeMixinBase


class TradeEntryRecordRuntimeMixin(RuntimeMixinBase):
    def _append_open_trade(
        self,
        *,
        discrete_action: int,
        risk_frac: float,
        bar: BarView,
        feat_row: FeatureRow | pd.Series,
        bar_time: Any,
        session_id: int,
        fill_time: Any,
        sl_price: float | None,
        tp_price: float | None,
        placed: Any,
        entry_price: float,
        entry_equity: float,
        execution_meta: dict[str, Any],
        entry_candidate: EntryCandidate | None,
        fill_bar_idx: int | None,
        order_submission_time: Any | None,
        decision_bar_idx: int | None,
        signal_bar: int,
        signal_time: pd.Timestamp,
        entry_level: str | None,
        sweep_delay: float,
    ) -> None:
        assert self.position is not None
        thesis = self._selected_trade_setup if self.trade_setup_actions else None
        primary_id = int(thesis.candidate_id) if thesis is not None else None
        supporting = [
            f"{candidate.idea}@{candidate.setup_timeframe}:{'long' if candidate.direction == 1 else 'short'}"
            for candidate in active_trade_setup_candidates(feat_row)
            if thesis is None or candidate.candidate_id != primary_id
        ]
        from decisioning.trade_setup import LEGACY_THESIS_ACTION_VERSION, TRADE_SETUP_ACTION_VERSION

        if thesis is not None and self.legacy_thesis_contract:
            setup_identity = {
                "thesis_candidate_id": primary_id,
                "thesis_schema_version": LEGACY_THESIS_ACTION_VERSION,
                "thesis_decision_time": self.position.thesis_decision_time,
            }
        elif thesis is not None:
            setup_identity = {
                "trade_setup_candidate_id": primary_id,
                "trade_setup_schema_version": TRADE_SETUP_ACTION_VERSION,
                "trade_setup_decision_time": self.position.trade_setup_decision_time,
            }
        else:
            setup_identity = {}

        self.trade_log.append(
            {
                "type": "open",
                "position_id": self.position.position_id,
                "requested_risk_usd": float(self._last_requested_risk_usd),
                "approved_risk_usd": float(self._last_approved_risk_usd),
                "execution_reserve_usd": float(self._last_execution_reserve_usd),
                "modeled_stop_risk_usd": float(self.position.planned_risk_usd or 0.0),
                "strategy": self.strategy.name,
                "variant_id": str(getattr(self.strategy, "variant_id", self.strategy.name)),
                "direction": discrete_action,
                **setup_identity,
                "primary_idea": thesis.idea if thesis is not None else "",
                "primary_setup_timeframe": thesis.setup_timeframe if thesis is not None else "",
                "primary_direction": thesis.direction if thesis is not None else 0,
                "supporting_idea_timeframes": supporting,
                "price": self.position.entry_price,
                "bar": self.step_idx if decision_bar_idx is None else decision_bar_idx,
                "signal_bar": signal_bar,
                "signal_time": signal_time,
                "order_submission_bar": signal_bar,
                "fill_bar": self.step_idx if fill_bar_idx is None else fill_bar_idx,
                "fill_phase": "tick" if execution_meta else "bar_open",
                "fill_quote_source": "tick" if execution_meta else "bar_open",
                "entry_mode": str(getattr(self.strategy, "entry_mode", "legacy")),
                "time": fill_time,
                "decision_time": bar_time,
                "order_submission_time": (
                    signal_time if order_submission_time is None else order_submission_time
                ),
                "fill_time": fill_time,
                "lots": self.position.size,
                "sl_price": sl_price,
                "tp_price": tp_price,
                **_previous_session_audit(self.strategy, feat_row, float(bar.close)),
                "executed_target_prices": [
                    float(price)
                    for price in (
                        self.position.tp1_price,
                        self.position.tp2_price,
                        self.position.tp3_price,
                    )
                    if price is not None
                ]
                or ([float(tp_price)] if tp_price is not None else []),
                "tp_anchor_ref_price": self.position.entry_tp_ref_price,
                "risk_frac": risk_frac,
                "rr_ratio": self.position.rr_ratio,
                "planned_rr": (
                    float("nan")
                    if self.position.planned_rr is None
                    else float(self.position.planned_rr)
                ),
                "sl_ref": self.position.sl_ref,
                "tp_ref": self.position.tp_ref,
                "sl_buffer": self.position.sl_buffer,
                "exit_mode": self.position.exit_mode,
                "manipulation": self.position.manipulation,
                "n_sl": self.position.n_sl,
                "n_tp": self.position.n_tp,
                "sl_menu": ([] if placed is None else [list(pair) for pair in placed.sl_menu]),
                "sl_candidate_audit": (
                    []
                    if placed is None
                    else [dict(candidate) for candidate in placed.sl_candidate_audit]
                ),
                "tp_menu": ([] if placed is None else [list(pair) for pair in placed.tp_menu]),
                **(
                    self._decision_fields(
                        placed,
                        entry_price=entry_price,
                        risk_frac=risk_frac,
                        entry_equity=entry_equity,
                        feat_row=feat_row,
                        bar_time=bar_time,
                    )
                    if placed is not None
                    else {}
                ),
                "equity": self.account.equity,
                **execution_meta,
                **(
                    {
                        "entry_setup_types": list(entry_candidate.setup_types),
                        "entry_origin_bar": entry_candidate.origin_bar,
                        "entry_origin_time": (
                            self.bars.index[entry_candidate.origin_bar]
                            if self.bars is not None
                            and 0 <= entry_candidate.origin_bar < len(self.bars)
                            else None
                        ),
                        "entry_setup_levels": dict(entry_candidate.setup_levels_snapshot),
                        "entry_state": "ARMED",
                    }
                    if entry_candidate is not None
                    else {}
                ),
                # Always recorded, on the strategy path and the baseline
                # path alike, so the logged risk can never disagree with
                # the filled lots. Baseline rows used to omit these,
                # leaving no record of what a trade actually risked.
                "stop_distance": (
                    abs(float(self.position.entry_price) - float(sl_price))
                    if sl_price is not None
                    else float("nan")
                ),
                "risk_cash": self._actual_risk_usd(
                    abs(float(self.position.entry_price) - float(sl_price))
                    if sl_price is not None
                    else float("nan")
                ),
                "level_type": entry_level,
                "sweep_delay_s": sweep_delay,
                "action_tp_mode": getattr(self, "_selected_tp_mode", "rr"),
                "asian_high": float(feat_row.get("asian_high", float("nan"))),
                "asian_low": float(feat_row.get("asian_low", float("nan"))),
                "sweep_high": float(feat_row.get("sweep_high", float("nan"))),
                "sweep_low": float(feat_row.get("sweep_low", float("nan"))),
                "manipulation_high": float(feat_row.get("po3_manipulation_high", float("nan"))),
                "manipulation_low": float(feat_row.get("po3_manipulation_low", float("nan"))),
                "manipulation_end": float(feat_row.get("po3_manipulation_end", float("nan"))),
                "distribution_phase": float(feat_row.get("po3_distribution", float("nan"))),
                "entry_rejection_reason": "",
                "ifvg_zone_low": float(
                    feat_row.get(
                        "ifvg_bull_low",
                        feat_row.get("ifvg_bear_low", float("nan")),
                    )
                ),
                "ifvg_zone_high": float(
                    feat_row.get(
                        "ifvg_bull_high",
                        feat_row.get("ifvg_bear_high", float("nan")),
                    )
                ),
            }
        )
        self.sessions_with_trades.add(session_id)
