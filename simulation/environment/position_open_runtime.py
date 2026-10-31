from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd

from trading.orders import target_menu
from trading.risk import stop_loss_risk_usd

from .entry_state import EntryCandidate
from .market_view import FeatureRow
from .mixin_base import RuntimeMixinBase


class PositionOpenRuntimeMixin(RuntimeMixinBase):
    _position_sequence: int

    def _initialize_open_position(
        self,
        discrete_action: int,
        risk_frac: float,
        rr_ratio: float,
        entry_price: float,
        sl_price: float | None,
        tp_price: float | None,
        placed: Any,
        feat_row: FeatureRow | pd.Series,
        fill_time: Any,
        session_id: int,
        entry_candidate: EntryCandidate | None,
        bar_time: Any,
        signal_bar_idx: int | None,
    ) -> tuple[str | None, float, int, pd.Timestamp]:
        assert self.position is not None
        self._entry_diag["opened"] += 1
        self._position_sequence += 1
        self.position.position_id = f"e{self._episode_identity}:p{self._position_sequence}"
        self.position.initial_size = float(self.position.size)
        thesis = self._selected_trade_setup if self.trade_setup_actions else None
        if thesis is not None:
            from decisioning.trade_setup import (
                LEGACY_THESIS_ACTION_VERSION,
                TRADE_SETUP_ACTION_VERSION,
            )

            schema_version = (
                LEGACY_THESIS_ACTION_VERSION
                if self.legacy_thesis_contract
                else TRADE_SETUP_ACTION_VERSION
            )
            if self.legacy_thesis_contract:
                self.position.thesis_candidate_id = int(thesis.candidate_id)
                self.position.thesis_schema_version = schema_version
                self.position.thesis_decision_time = bar_time
            else:
                self.position.trade_setup_candidate_id = int(thesis.candidate_id)
                self.position.trade_setup_schema_version = schema_version
                self.position.trade_setup_decision_time = bar_time
            self.position.primary_idea = str(thesis.idea or "")
            self.position.primary_setup_timeframe = str(thesis.setup_timeframe or "")
        self.position.sl_price = sl_price
        self.position.sl_initial_price = sl_price
        self.position.breakeven_done = False
        if sl_price is not None:
            # Loss in account currency if the structural stop fills.
            # The intraday adverse guard uses this as its floor so
            # sizing and the guard cannot disagree.
            self.position.planned_risk_usd = stop_loss_risk_usd(
                entry_price - float(sl_price),
                float(self.position.size),
                self.contract_size,
            )
        self.position.tp_price = tp_price
        self.position.risk_frac = risk_frac
        if placed is not None:
            self.position.sl_ref = placed.sl_ref
            self.position.tp_ref = placed.tp_ref
            self.position.planned_rr = placed.planned_rr
            self.position.exit_mode = placed.exit_mode
            self.position.sl_buffer = placed.sl_buffer
            self.position.manipulation = placed.manipulation
            self.position.n_sl = placed.n_sl
            self.position.n_tp = placed.n_tp
            assert placed.sl_price is not None
            self.position.stop_distance = abs(entry_price - float(placed.sl_price))
            # planned_rr is the structural ratio. rr_ratio stays empty.
            self.position.rr_ratio = None
            self.position.tp1_price = placed.tp1_price
            self.position.tp2_price = placed.tp2_price
            self.position.tp3_price = placed.tp3_price
            self.position.tp1_ref = placed.tp1_ref
            self.position.tp2_ref = placed.tp2_ref
            self.position.tp3_ref = placed.tp3_ref
            self.position.tp_lot_fractions = placed.tp_lot_fractions
            self.position.ema_runner_fraction = placed.ema_runner_fraction
            self.position.tp_initial_price = (
                placed.tp3_price if placed.tp3_price is not None else placed.tp_price
            )
        else:
            self.position.rr_ratio = rr_ratio
            self.position.tp3_price = tp_price
            self.position.tp_initial_price = tp_price
            self.position.tp_lot_fractions = (1.0,)
            if feat_row is not None and tp_price is not None:
                try:
                    sl_d = abs(entry_price - float(sl_price)) if sl_price is not None else 0.0
                    targets = target_menu(
                        direction=discrete_action,
                        entry_price=entry_price,
                        row=feat_row,
                        stop_dist=sl_d,
                        max_tp_distance=float("inf"),
                        rr_bounds=None,
                        htf=self._target_timeframes,
                    )
                    if targets:
                        self.position.entry_tp_ref_price = float(targets[0][1])
                        self.position.tp_ref = str(targets[0][0])
                        self.position.tp3_ref = str(targets[0][0])
                except Exception:
                    pass
        self.position.tp_initial_size = float(self.position.size)
        self.position.tp_mode = self._selected_tp_mode
        self.position.tp_mode_overridden = self._tp_mode_explicit
        self.position.tp_breakeven_done = False
        self.position.tp_hit_mask = 0
        self.position.entry_timestamp = fill_time
        atr_val = feat_row.get("atr_5", feat_row.get("atr", np.nan))
        self.position.entry_atr = (
            float(atr_val) if pd.notna(atr_val) and float(atr_val) > 0 else 1.0
        )
        if placed is not None and placed.sl_ref == "sl_reference":
            ref = None
            if hasattr(self.strategy, "sl_reference"):
                ref = self.strategy.sl_reference(direction=discrete_action, row=feat_row)
            self.position.entry_sl_ref_price = (
                float(ref) if ref is not None and np.isfinite(float(ref)) else None
            )
        try:
            self.position.entry_last_swing_high = float(feat_row["last_swing_high"])
        except (KeyError, TypeError, ValueError):
            self.position.entry_last_swing_high = None
        try:
            self.position.entry_last_swing_low = float(feat_row["last_swing_low"])
        except (KeyError, TypeError, ValueError):
            self.position.entry_last_swing_low = None
        self.position.sl_mode = self._selected_sl_mode
        self.position.sl_mode_overridden = self._sl_mode_explicit
        self.position.best_favorable = 0.0
        self.position.last_progress_favorable = 0.0
        self.position.stale_counter = 0
        self.position.mfe = 0.0
        self.position.mae = 0.0
        if self.strategy_actions:
            self._session_entry_counts[session_id] = (
                self._session_entry_counts.get(session_id, 0) + 1
            )
        if entry_candidate is not None:
            self.position.entry_setup_types = entry_candidate.setup_types
            self.position.entry_origin_bar = entry_candidate.origin_bar
        entry_level, cross_time = self._matched_entry_level(session_id, discrete_action)
        sweep_delay = (
            float("nan")
            if cross_time is None
            else float(
                (
                    pd.Timestamp(cast(Any, bar_time)) - pd.Timestamp(cast(Any, cross_time))
                ).total_seconds()
            )
        )
        self._opened_this_step = True
        signal_bar = self.step_idx if signal_bar_idx is None else int(signal_bar_idx)
        signal_time = pd.Timestamp(cast(Any, bar_time)) + pd.Timedelta(
            minutes=self._minutes_per_step
        )
        return entry_level, sweep_delay, signal_bar, signal_time
