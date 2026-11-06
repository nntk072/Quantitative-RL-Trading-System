"""Focused simulation execution service."""

from __future__ import annotations

from typing import Any, cast

import pandas as pd

from market_data.loading.ticks import (
    TickExecutionUnavailable,
)
from trading.execution import Position, exit_side_bar_range, raw_spread_to_price
from trading.positions import target_close_size
from trading.risk import tightened_breakeven_stop_price

from .market_view import BarView
from .mixin_base import RuntimeMixinBase


class ProtectiveLevelRuntimeMixin(RuntimeMixinBase):
    """Resolve protective levels and partial exits while preserving runners."""

    position: Position | None

    def _exit_side_bar_range(self, bar: BarView, direction: int) -> tuple[float, float]:
        """Return the executable low/high range for the exiting position side.

        Args:
            bar: Current market bar with high, low, and spread values.
            direction: Position direction, ``1`` for long or ``-1`` for short.

        Returns:
            Low and high executable price bounds after spread handling.
        """
        spread = raw_spread_to_price(float(bar.spread), self.cost_model.point_size)
        return exit_side_bar_range(
            direction, float(bar.low), float(bar.high), spread, self.cost_model
        )

    def _assert_tick_protective_events_observed(
        self,
        bar: BarView,
        bar_idx: int | None = None,
        *,
        protective_levels: tuple[float | None, tuple[float | None, ...]] | None = None,
    ) -> None:
        """Reject OHLC protective crossings that have no matching executable tick.

        Args:
            bar: Market bar whose stop and target crossings are checked.
            bar_idx: Optional bar index; defaults to the current environment step.
            protective_levels: Optional stop and target levels to validate.
        """
        position = self.position
        if position is None:
            return
        idx = self.step_idx if bar_idx is None else bar_idx
        bar_time = self._bar_time(idx)
        entry_time = (
            None
            if position.entry_timestamp is None
            else pd.Timestamp(cast(Any, position.entry_timestamp))
        )
        if entry_time is not None and entry_time > bar_time:
            return
        exit_low, exit_high = self._exit_side_bar_range(bar, int(position.direction))
        sl_price, target_levels = protective_levels or (
            position.sl_price,
            tuple(getattr(position, f"tp{slot}_price") for slot in (1, 2, 3)),
        )
        if protective_levels is None and not any(target is not None for target in target_levels):
            target_levels = (position.tp_price,)
        stop_touched = sl_price is not None and (
            exit_low <= sl_price if position.direction == 1 else exit_high >= sl_price
        )
        target_touched = any(
            target is not None
            and (
                (position.direction == 1 and exit_high >= target)
                or (position.direction == -1 and exit_low <= target)
            )
            for target in target_levels
        )
        if stop_touched or target_touched:
            tick_window = "unavailable"
            if self._tickbook is not None:
                window_end = bar_time + pd.Timedelta(
                    minutes=max(1, int(round(self._minutes_per_step)))
                )
                tick_start = int(self._tickbook._ts.searchsorted(bar_time.value, side="left"))
                tick_end = int(self._tickbook._ts.searchsorted(window_end.value, side="left"))
                executable_side = (
                    self._tickbook._bid if position.direction == 1 else self._tickbook._ask
                )
                window_prices = executable_side[tick_start:tick_end]
                tick_window = (
                    f"count={tick_end - tick_start}, "
                    f"side_min={float(window_prices.min()) if len(window_prices) else None}, "
                    f"side_max={float(window_prices.max()) if len(window_prices) else None}, "
                    f"start={pd.Timestamp(int(self._tickbook._ts[tick_start]), unit='ns', tz='UTC') if tick_start < len(self._tickbook) else None}"
                )
            target_text = ", ".join(
                f"tp{slot}={getattr(position, f'tp{slot}_price')}" for slot in (1, 2, 3)
            )
            raise TickExecutionUnavailable(
                "OHLC indicates a protective level was reached, but no matching "
                "tick trigger was found; candle fallback is disabled "
                f"(bar_idx={idx}, bar_time={bar_time.isoformat()}, "
                f"entry_time={entry_time}, "
                f"direction={position.direction}, open={bar.open}, high={bar.high}, "
                f"low={bar.low}, close={bar.close}, exit_low={exit_low}, "
                f"exit_high={exit_high}, sl={sl_price}, "
                f"tick_window=({tick_window}), "
                f"multi_target_replay={getattr(self, '_last_multi_target_replay', None)}, "
                f"{target_text})"
            )

    def _check_sl_tp(
        self,
        bar: BarView,
        fill_bid: float,
        fill_ask: float,
        bar_idx: int | None = None,
    ) -> None:
        """Check whether the open position hit its SL or TP on this bar.

        With a tick book, the first bid (long) or ask (short) beyond the
        level is the fill. ``fill_delay_ms`` is 0, so a later tick is not
        used: a stop cannot bounce back to a better price. That crossing
        tick is already through the level, so a loss can exceed $100 and a
        target can pay more than $100. With no crossing tick, the fill stays
        at the level. Slippage, when configured, moves that level fill only
        against the position. If both levels sit inside one bar and there is
        no tick, the stop wins.

        Args:
            bar: Bar used by the operation described above.
            fill_bid: Numeric value used for the fill bid.
            fill_ask: Numeric value used for the fill ask.
            bar_idx: Bar idx used by the operation described above.
        """
        if self.position is None:
            return
        record: dict[str, Any]
        idx = self.step_idx if bar_idx is None else bar_idx
        exit_low, exit_high = self._exit_side_bar_range(bar, int(self.position.direction))
        log_time = (
            self._bar_time(idx)
            if 0 <= idx < len(self._bar_times)
            else self._bar_time(self.step_idx)
        )
        # Touch detection uses the bar range. The next quote must not be the fill.
        _ = (fill_bid, fill_ask)

        # Multi-level positions require a chronological tick replay. A single
        # SL/TP lookup loses the slot identities and can liquidate the entire
        # position at TP1 (or ignore TP1 when only tp1_price is populated).
        has_tick_slots = any(
            getattr(self.position, f"tp{slot}_price") is not None for slot in (1, 2, 3)
        )
        if has_tick_slots and self._tickbook is not None:
            before_replay = (
                int(self.position.direction),
                self.position.sl_price,
                tuple(getattr(self.position, f"tp{slot}_price") for slot in (1, 2, 3)),
                float(self.position.size),
                int(self.position.tp_hit_mask),
            )
            if self._check_multi_tp_ticks(log_time, idx):
                self._last_multi_target_replay = {
                    "before": before_replay,
                    "after": (
                        None
                        if self.position is None
                        else (
                            int(self.position.direction),
                            self.position.sl_price,
                            tuple(getattr(self.position, f"tp{slot}_price") for slot in (1, 2, 3)),
                            float(self.position.size),
                            int(self.position.tp_hit_mask),
                        )
                    ),
                }
                # Replay may leave a runner with updated protective levels.
                # Check only that live position after replay; a fully closed
                # position has no remaining event to validate.
                if self.position is not None and (
                    getattr(self, "tick_execution_required", False)
                    or getattr(self, "randomized_fill_latency_ms", 0.0) > 0
                ):
                    replayed_targets = before_replay[2]
                    remaining_targets = tuple(
                        current if current is not None and current == previous else None
                        for current, previous in zip(
                            (getattr(self.position, f"tp{slot}_price") for slot in (1, 2, 3)),
                            replayed_targets,
                            strict=True,
                        )
                    )
                    unchanged_stop = (
                        self.position.sl_price
                        if self.position.sl_price == before_replay[1]
                        else None
                    )
                    self._assert_tick_protective_events_observed(
                        bar,
                        idx,
                        protective_levels=(unchanged_stop, remaining_targets),
                    )
                return

        tick_hit = None if has_tick_slots else self._tick_exit_quote(log_time)
        if tick_hit is not None:
            kind, quote, fill_time, execution_meta = tick_hit
            pnl, fill_price = self._close_at_quote(self.position, quote, tick_fill=True)
            record = {
                "type": "stop_close" if kind == "sl" else "tp_close",
                "pnl": pnl,
                "price": fill_price,
                "reason": "structure_sl" if kind == "sl" else "structure_tp",
                "fill_quote_source": "tick",
                "bar": idx,
                "time": fill_time,
                "equity": self.account.equity,
                **execution_meta,
            }
            self._stamp_exit(record, fill_price)
            self.trade_log.append(record)
            self.position = None
            self.sessions_with_trades.add(self._current_session_id())
            self._note_close(pnl)
            return

        if (
            getattr(self, "tick_execution_required", False)
            or getattr(self, "randomized_fill_latency_ms", 0.0) > 0
        ):
            self._assert_tick_protective_events_observed(bar, idx)
            # Intrabar OHLC extrema are not executable bid/ask evidence. Keep
            # the position open when no matching executable tick was observed.
            self._maybe_ema_exit(bar, idx, log_time)
            return

        sl_hit = False
        if self.position.sl_price is not None:
            if self.position.direction == 1 and exit_low <= self.position.sl_price:
                sl_hit = True
            elif self.position.direction == -1 and exit_high >= self.position.sl_price:
                sl_hit = True

        if sl_hit:
            assert self.position.sl_price is not None
            pnl, fill_price = self.broker.close_position(
                self.account,
                self.position,
                self._stop_fill_quote(
                    bar, int(self.position.direction), float(self.position.sl_price)
                ),
            )
            record = {
                "type": "stop_close",
                "pnl": pnl,
                "price": fill_price,
                "reason": "structure_sl",
                "bar": idx,
                "time": log_time,
                "fill_time": None,
                "event_time_start": log_time,
                "event_time_end": log_time
                + pd.Timedelta(minutes=getattr(self, "_minutes_per_step", 1)),
                "time_precision": "bar_interval",
                "equity": self.account.equity,
            }
            self._stamp_exit(record, fill_price)
            self.trade_log.append(record)
            self.position = None
            self.sessions_with_trades.add(self._current_session_id())
            self._note_close(pnl)
            return

        has_multi_levels = self.position is not None and (
            self.position.tp1_price is not None
            or self.position.tp2_price is not None
            or self.position.tp3_price is not None
        )
        if has_multi_levels and self.position is not None:
            pos = self.position
            for slot_num in (1, 2, 3):
                if self.position is None or pos.size <= 0:
                    break
                slot_px = getattr(pos, f"tp{slot_num}_price")
                if slot_px is None:
                    continue
                hit_mask_bit = 1 << (slot_num - 1)
                if pos.tp_hit_mask & hit_mask_bit:
                    continue

                slot_hit = False
                if pos.direction == 1 and exit_high >= float(slot_px):
                    slot_hit = True
                elif pos.direction == -1 and exit_low <= float(slot_px):
                    slot_hit = True

                if slot_hit:
                    # Check remaining active slots after this one
                    remaining_slots = [
                        s
                        for s in (1, 2, 3)
                        if s > slot_num and getattr(pos, f"tp{s}_price") is not None
                    ]
                    is_final = len(remaining_slots) == 0
                    close_size = target_close_size(pos, slot_num, is_final=is_final)

                    quote = self._sl_tp_fill_quote(int(pos.direction), float(slot_px))
                    pnl, fill_price = self._close_at_quote(pos, quote, size=close_size)
                    pos.tp_hit_mask |= hit_mask_bit
                    setattr(pos, f"tp{slot_num}_price", None)
                    record = {
                        "type": "tp_close" if pos.size <= 0 else "tp_partial_close",
                        "pnl": pnl,
                        "price": fill_price,
                        "reason": f"structure_tp{slot_num}",
                        "bar": idx,
                        "time": log_time,
                        "fill_time": None,
                        "event_time_start": log_time,
                        "event_time_end": log_time
                        + pd.Timedelta(minutes=getattr(self, "_minutes_per_step", 1)),
                        "time_precision": "bar_interval",
                        "equity": self.account.equity,
                        "tp_slot": slot_num,
                        "size": close_size,
                    }
                    self._stamp_exit(record, fill_price)
                    self.trade_log.append(record)
                    self.sessions_with_trades.add(self._current_session_id())

                    if pos.size <= 0:
                        self.position = None
                        self._note_close(pnl)
                        return
                    else:
                        pos.tp_price = (
                            pos.tp1_price
                            if pos.tp1_price is not None
                            else (pos.tp2_price if pos.tp2_price is not None else pos.tp3_price)
                        )
                        if self._breakeven_trigger_r > 0.0:
                            buffer = self._breakeven_buffer_pts
                            new_sl = tightened_breakeven_stop_price(
                                direction=pos.direction,
                                entry_price=pos.entry_price,
                                current_stop_price=pos.sl_price,
                                buffer_points=buffer,
                            )
                            if new_sl is not None:
                                previous_sl = pos.sl_price
                                pos.sl_price = new_sl
                                pos.breakeven_done = True
                                self._record_stop_update(
                                    pos,
                                    previous_sl,
                                    reference="entry",
                                    reference_price=pos.entry_price,
                                    reason="post_partial_breakeven",
                                    buffer_points=buffer,
                                    event_time=log_time,
                                    bar_idx=idx,
                                )
            if self.position is None:
                return
        elif self.position.tp_price is not None:
            tp_hit = False
            if self.position.direction == 1 and exit_high >= self.position.tp_price:
                tp_hit = True
            elif self.position.direction == -1 and exit_low <= self.position.tp_price:
                tp_hit = True

            if tp_hit:
                assert self.position.tp_price is not None
                pnl, fill_price = self._close_at_quote(
                    self.position,
                    self._sl_tp_fill_quote(
                        int(self.position.direction), float(self.position.tp_price)
                    ),
                )
                record = {
                    "type": "tp_close",
                    "pnl": pnl,
                    "price": fill_price,
                    "reason": "structure_tp",
                    "bar": idx,
                    "time": log_time,
                    "fill_time": None,
                    "event_time_start": log_time,
                    "event_time_end": log_time
                    + pd.Timedelta(minutes=getattr(self, "_minutes_per_step", 1)),
                    "time_precision": "bar_interval",
                    "equity": self.account.equity,
                }
                self._stamp_exit(record, fill_price)
                self.trade_log.append(record)
                self.position = None
                self.sessions_with_trades.add(self._current_session_id())
                self._note_close(pnl)
                return

        self._maybe_ema_exit(bar, idx, log_time)

    def _check_multi_tp_ticks(self, bar_time: pd.Timestamp, idx: int) -> bool:
        """Replay observed bid/ask crossings in order, respecting remaining TP lots.

        Return True when a tick produced any exit. The caller must then avoid
        applying the bar's ambiguous OHLC crossings to the same position.

        Args:
            bar_time: Bar time used by the operation described above.
            idx: Numeric value used for the idx.

        Returns:
            Whether check multi tp ticks meets the requested condition.
        """
        book = self._tickbook
        pos = self.position
        if book is None or pos is None:
            return False
        had_fill = False
        last_fill_ns = -1
        randomized_by_trigger: dict[int, tuple[Any, dict[str, Any]]] = {}
        bar_minutes = max(1, int(round(getattr(self, "_minutes_per_step", 1.0))))
        for tick_time, bid, ask in book.bar_quotes(bar_time, bar_minutes=bar_minutes):
            if self.position is not pos or pos.size <= 0:
                break
            if tick_time.value < last_fill_ns:
                continue
            if pos.entry_timestamp is not None and tick_time < pd.Timestamp(
                cast(Any, pos.entry_timestamp)
            ):
                continue
            exit_side = bid if pos.direction == 1 else ask
            sl = pos.sl_price
            stop_hit = sl is not None and (
                (pos.direction == 1 and exit_side <= sl)
                or (pos.direction == -1 and exit_side >= sl)
            )
            if stop_hit:
                execution_meta: dict[str, Any] = {}
                if (
                    getattr(self, "tick_execution_required", False)
                    or getattr(self, "randomized_fill_latency_ms", 0.0) > 0
                ):
                    cached = randomized_by_trigger.get(tick_time.value)
                    if cached is None:
                        quote, execution_meta = self._resolve_randomized_tick_quote(
                            tick_time,
                            event_key=(f"protective_exit:{pos.direction}:sl:{tick_time.value}"),
                        )
                        execution_meta["order_submission_time"] = tick_time
                        cached = (quote, execution_meta)
                        randomized_by_trigger[tick_time.value] = cached
                    quote, execution_meta = cached
                    bid, ask = quote.bid, quote.ask
                    execution_time = quote.tick_time
                else:
                    fill_time = tick_time + pd.Timedelta(milliseconds=self.fill_delay_ms)
                    quote_event = book.quote_event_at(fill_time)
                    if quote_event is None:
                        continue
                    quote_time, bid, ask = quote_event
                    execution_time = max(fill_time, quote_time)
                    execution_meta = {
                        "order_submission_time": tick_time,
                        "execution_order_time": tick_time,
                        "execution_arrival_time": fill_time,
                        "execution_latency_ns": int(
                            pd.Timedelta(milliseconds=self.fill_delay_ms).value
                        ),
                        "actual_tick_time": quote_time,
                        "fill_quote_source": "tick",
                    }
                remaining = pos.size
                pnl, fill_price = self._close_at_quote(pos, (bid, ask), tick_fill=True)
                record = {
                    "type": "stop_close",
                    "pnl": pnl,
                    "price": fill_price,
                    "reason": "structure_sl",
                    "fill_quote_source": "tick",
                    "bar": idx,
                    "time": execution_time,
                    "equity": self.account.equity,
                    "size": remaining,
                    **execution_meta,
                }
                self._stamp_exit(record, fill_price)
                self.trade_log.append(record)
                self.position = None
                self.sessions_with_trades.add(self._current_session_id())
                self._note_close(pnl)
                return True

            for slot_num in (1, 2, 3):
                if self.position is None or pos.size <= 0:
                    return True
                bit = 1 << (slot_num - 1)
                slot_px = getattr(pos, f"tp{slot_num}_price")
                if slot_px is None or pos.tp_hit_mask & bit:
                    continue
                target_hit = (pos.direction == 1 and exit_side >= slot_px) or (
                    pos.direction == -1 and exit_side <= slot_px
                )
                if not target_hit:
                    continue
                execution_meta = {}
                if (
                    getattr(self, "tick_execution_required", False)
                    or getattr(self, "randomized_fill_latency_ms", 0.0) > 0
                ):
                    cached = randomized_by_trigger.get(tick_time.value)
                    if cached is None:
                        quote, execution_meta = self._resolve_randomized_tick_quote(
                            tick_time,
                            event_key=(f"protective_exit:{pos.direction}:tp:{tick_time.value}"),
                        )
                        execution_meta["order_submission_time"] = tick_time
                        cached = (quote, execution_meta)
                        randomized_by_trigger[tick_time.value] = cached
                    quote, execution_meta = cached
                    bid, ask = quote.bid, quote.ask
                    execution_time = quote.tick_time
                else:
                    fill_time = tick_time + pd.Timedelta(milliseconds=self.fill_delay_ms)
                    quote_event = book.quote_event_at(fill_time)
                    if quote_event is None:
                        continue
                    quote_time, bid, ask = quote_event
                    execution_time = max(fill_time, quote_time)
                    execution_meta = {
                        "order_submission_time": tick_time,
                        "execution_order_time": tick_time,
                        "execution_arrival_time": fill_time,
                        "execution_latency_ns": int(
                            pd.Timedelta(milliseconds=self.fill_delay_ms).value
                        ),
                        "actual_tick_time": quote_time,
                        "fill_quote_source": "tick",
                    }
                last_fill_ns = max(last_fill_ns, execution_time.value)
                remaining_slots = [
                    slot
                    for slot in (1, 2, 3)
                    if slot > slot_num
                    and getattr(pos, f"tp{slot}_price") is not None
                    and not (pos.tp_hit_mask & (1 << (slot - 1)))
                ]
                close_size = target_close_size(pos, slot_num, is_final=not remaining_slots)

                pnl, fill_price = self._close_at_quote(
                    pos, (bid, ask), size=close_size, tick_fill=True
                )
                pos.tp_hit_mask |= bit
                setattr(pos, f"tp{slot_num}_price", None)
                record = {
                    "type": "tp_close" if pos.size <= 0 else "tp_partial_close",
                    "pnl": pnl,
                    "price": fill_price,
                    "reason": f"structure_tp{slot_num}",
                    "fill_quote_source": "tick",
                    "bar": idx,
                    "time": execution_time,
                    "equity": self.account.equity,
                    "tp_slot": slot_num,
                    "size": close_size,
                    **execution_meta,
                }
                self._stamp_exit(record, fill_price)
                self.trade_log.append(record)
                self.sessions_with_trades.add(self._current_session_id())
                had_fill = True
                if pos.size <= 0:
                    self.position = None
                    self._note_close(pnl)
                    return True

                pos.tp_price = next(
                    (
                        getattr(pos, f"tp{slot}_price")
                        for slot in (1, 2, 3)
                        if getattr(pos, f"tp{slot}_price") is not None
                    ),
                    None,
                )
                if self._breakeven_trigger_r > 0.0:
                    buffer = self._breakeven_buffer_pts
                    new_sl = tightened_breakeven_stop_price(
                        direction=pos.direction,
                        entry_price=pos.entry_price,
                        current_stop_price=pos.sl_price,
                        buffer_points=buffer,
                    )
                    if new_sl is not None:
                        previous_sl = pos.sl_price
                        pos.sl_price = new_sl
                        pos.breakeven_done = True
                        self._record_stop_update(
                            pos,
                            previous_sl,
                            reference="entry",
                            reference_price=pos.entry_price,
                            reason="post_partial_breakeven",
                            buffer_points=buffer,
                            event_time=tick_time,
                            bar_idx=idx,
                        )
        return had_fill
