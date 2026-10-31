from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from features.context.entry_ideas import entry_idea_context
from trading.orders import place_strategy_order
from trading.risk import compute_sl_tp_long, compute_sl_tp_short

from .market_view import FeatureRow
from .mixin_base import RuntimeMixinBase


class EntryOrderRuntimeMixin(RuntimeMixinBase):
    def _build_entry_levels(
        self,
        discrete_action: int,
        risk_frac: float,
        rr_ratio: float,
        feat_row: FeatureRow | pd.Series,
        fill_bid: float,
        fill_ask: float,
    ) -> tuple[float, float | None, float | None, float, bool, Any]:
        sl_price = None
        tp_price = None

        last_swing_low = (
            float(feat_row["last_swing_low"])
            if "last_swing_low" in feat_row.index and np.isfinite(float(feat_row["last_swing_low"]))
            else np.nan
        )
        last_swing_high = (
            float(feat_row["last_swing_high"])
            if "last_swing_high" in feat_row.index
            and np.isfinite(float(feat_row["last_swing_high"]))
            else np.nan
        )

        entry_price = float(fill_ask if discrete_action == 1 else fill_bid)

        has_levels = False
        placed = None
        if self.strategy_actions:
            entry_context = entry_idea_context(feat_row, discrete_action)
            selected_trade_setup = self._selected_trade_setup if self.trade_setup_actions else None
            timeframe_floor = (
                str(selected_trade_setup.setup_timeframe)
                if selected_trade_setup is not None
                else str(entry_context["stop_timeframe_floor"])
            )
            sd_timeframes = (
                (str(selected_trade_setup.setup_timeframe),)
                if selected_trade_setup is not None
                and str(selected_trade_setup.idea) == "standard_deviation"
                else tuple(entry_context["standard_deviation_timeframes"])
            )

            placed = place_strategy_order(
                self.strategy,
                direction=discrete_action,
                entry_price=entry_price,
                feat_row=feat_row,
                min_dist=self._min_sl_distance(feat_row),
                sl_fraction=float(self._selected_sl_anchor),
                tp_fraction=float(self._selected_tp_fraction),
                exit_mode=str(self._selected_exit_mode),
                buffer_pts=self.sl_buffer_pts,
                max_tp_distance=self._max_tp_here(),
                rr_bounds=self.rr_ratio_range,
                htf=self._target_timeframes,
                entry_timeframe_floor=timeframe_floor,
                standard_deviation_timeframes=sd_timeframes,
                tp_selections=(self._selected_tp_selections if self.allow_multi_tp else None),
                tp_z=(
                    self._selected_tp_z if (self.allow_multi_tp and self.allow_simplex) else None
                ),
                allow_multi_tp=self.allow_multi_tp,
                allow_simplex=self.allow_simplex,
                ema_runner_fraction=(
                    self.ema_runner_fraction if self._selected_exit_mode == "ema_21" else 0.0
                ),
                price_increment=float(self.cost_model.point_size),
                thesis=selected_trade_setup,
            )
            sl_price = placed.sl_price
            tp_price = placed.tp_price
            # Size only after the chosen stop exists. An EMA exit has no target price.
            order_ok = sl_price is not None and (
                placed.exit_mode == "ema_21" or tp_price is not None
            )
            if order_ok:
                assert sl_price is not None
                lots = self._compute_lots_for(risk_frac, entry_price, sl_price)
                has_levels = True
            else:
                lots = 0.0
                if placed.reject_kind == "tp":
                    self._reject("no_valid_tp")
                elif placed.reject_kind == "ema":
                    # A missing EMA-21 level is an exit problem, not a stop
                    # problem. It used to increment rejected_sl while
                    # reporting no_valid_tp, so the counter and the reason
                    # disagreed and the EMA case was invisible in entry_sl.
                    self._reject("no_ema_exit")
                else:
                    self._reject("no_valid_sl")
        elif discrete_action == 1 and not np.isnan(last_swing_low) and last_swing_low < entry_price:
            sl_price, tp_price = compute_sl_tp_long(
                entry_price,
                last_swing_low,
                buffer_pts=self.swing_buffer_pts,
                rr_ratio=rr_ratio,
            )
            lots = self._compute_lots_for(risk_frac, entry_price, sl_price)
            has_levels = True
        elif (
            discrete_action == -1
            and not np.isnan(last_swing_high)
            and last_swing_high > entry_price
        ):
            sl_price, tp_price = compute_sl_tp_short(
                entry_price,
                last_swing_high,
                buffer_pts=self.swing_buffer_pts,
                rr_ratio=rr_ratio,
            )
            lots = self._compute_lots_for(risk_frac, entry_price, sl_price)
            has_levels = True
        else:
            lots = 0.0
        return entry_price, sl_price, tp_price, lots, has_levels, placed
