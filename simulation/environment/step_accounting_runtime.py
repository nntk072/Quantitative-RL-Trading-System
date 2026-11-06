"""Focused simulation transition service."""

from __future__ import annotations

from typing import Any

import pandas as pd

from trading.execution import Position

from .market_view import BarView, FeatureRow
from .mixin_base import RuntimeMixinBase
from .timebase import BAR_TIME_TZ


class StepAccountingRuntimeMixin(RuntimeMixinBase):
    """Record realized step outcomes for account and evaluation bookkeeping."""

    position: Position | None

    def _liquidate_position_at_episode_end(
        self, bar: BarView, bar_time: Any, *, reason: str = "data_end"
    ) -> None:
        """Realize an open position at the final policy bar's close.

        Args:
            bar: Final market bar used when no tick fill is required.
            bar_time: Timestamp of the final policy bar.
            reason: Terminal close reason recorded in the trade ledger.
        """
        position = self.position
        if position is None:
            return

        terminal_time = pd.Timestamp(bar_time) + pd.Timedelta(minutes=self._minutes_per_step)
        execution_meta: dict[str, Any] = {}
        tick_fill = bool(self.tick_execution_required or self.randomized_fill_latency_ms > 0.0)
        if tick_fill:
            quote, execution_meta = self._resolve_randomized_tick_quote(
                terminal_time,
                event_key=f"bar_fill:{terminal_time.value}",
            )
            fill_quote = (float(quote.bid), float(quote.ask))
            fill_time = pd.Timestamp(quote.tick_time)
            quote_source = "tick"
        else:
            fill_quote = self._bar_quote(bar)
            fill_time = terminal_time
            quote_source = "terminal_bar_close"

        pnl, fill_price = self._close_at_quote(position, fill_quote, tick_fill=True)
        record = {
            "type": "eod_close",
            "pnl": pnl,
            "price": fill_price,
            "reason": reason,
            "bar": self.step_idx,
            "time": fill_time,
            "decision_time": bar_time,
            "order_submission_time": terminal_time,
            "fill_time": fill_time,
            "fill_quote_source": quote_source,
            "equity": self.account.equity,
            **execution_meta,
        }
        self._stamp_exit(record, fill_price)
        self.trade_log.append(record)
        self.position = None
        self.sessions_with_trades.add(self._current_session_id())
        self._note_close(pnl)

    def _record_step_accounting(
        self,
        bar: BarView,
        feat_row: FeatureRow | pd.Series,
        bar_time: Any,
        step_trade_log_start: int,
        done: bool,
        truncated: bool,
    ) -> tuple[bool, Any, float, float, dict[str, float]]:
        """Record step accounting.

        Args:
            bar: Bar used by the operation described above.
            feat_row: Feature values for the current market bar.
            bar_time: Bar time used by the operation described above.
            step_trade_log_start: Numeric value used for the step trade log start.
            done: Whether to enable or require the done.
            truncated: Whether to enable or require the truncated.

        Returns:
            Whether record step accounting meets the requested condition.
        """
        data_end = self._ny_pos + 1 >= len(self._ny_indices)
        step_limit = (
            self.max_episode_steps is not None
            and self.episode_step_count + 1 >= self.max_episode_steps
        )
        if data_end or (step_limit and not done):
            self._liquidate_position_at_episode_end(
                bar,
                bar_time,
                reason="data_end" if data_end else "max_episode_steps",
            )

        payout_terminal = self._handle_repeated_payout(bar_time)
        if payout_terminal:
            done = True

        valuation_time = bar_time + pd.Timedelta(minutes=self._minutes_per_step)
        for event in self.trade_log[step_trade_log_start:]:
            event_time = event.get("fill_time")
            if event_time is None and event.get("time_precision") == "bar_interval":
                event_time = event.get("event_time_end")
            if event_time is not None:
                event_timestamp = pd.Timestamp(event_time)
                if event_timestamp.tzinfo is None:
                    event_timestamp = event_timestamp.tz_localize("UTC")
                event_timestamp = event_timestamp.tz_convert(BAR_TIME_TZ)
                if event_timestamp > valuation_time:
                    valuation_time = event_timestamp
        self.equity_curve.append(self.account.equity)
        self.equity_times.append(valuation_time)
        pnl_step = (
            self.account.equity + float(self._payout_withdrawn_this_step) - self.equity_curve[-2]
        )
        self.pnl_history.append(pnl_step)

        reward = self._calculate_reward(pnl_step, bar, feat_row, done, truncated)
        reward_parts = {
            key: float(value) for key, value in getattr(self.reward_fn, "last_parts", {}).items()
        }
        if (
            self.peak_trailing_dd_limit > 0.0 or self._peak_eod_trailing_dd_limit_usd > 0.0
        ) and self._peak_dd_fired:
            # Penalize the percentage guard each active bar and the EOD guard
            # at its trigger boundary.
            reward -= 1.0
            part = "peak_eod_dd" if self._peak_eod_dd_locked else "peak_dd"
            reward_parts[part] = float(reward_parts.get(part, 0.0)) - 1.0
        return done, valuation_time, pnl_step, float(reward), reward_parts


__all__ = ["StepAccountingRuntimeMixin"]
