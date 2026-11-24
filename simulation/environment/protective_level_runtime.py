"""Focused simulation execution service."""

from __future__ import annotations

import math
from collections.abc import Iterator
from typing import Any, cast

import numpy as np
import pandas as pd

from market_data.loading.ticks import (
    TickExecutionUnavailable,
    nearest_exit_tick_quote,
    tick_price_reaches_level,
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

    def _tick_fill_mode(self) -> bool:
        """Whether protective exits fill from executable ticks instead of OHLC levels.

        Returns:
            True when tick execution or randomized fill latency is configured.
        """
        return bool(
            getattr(self, "tick_execution_required", False)
            or getattr(self, "randomized_fill_latency_ms", 0.0) > 0
        )

    def _untriggered_level_quote(
        self, bar_time: pd.Timestamp, direction: int, level: float
    ) -> tuple[float, float] | None:
        """Executable quote for a stop or target that OHLC reached with no crossing tick.

        The fill is the bar window's tick closest to the level, so the distance
        from the level is the slippage. A bar with no ticks fills at the tick
        nearest in time, if it is within max_tick_quote_wait_ms; otherwise at the
        level. Tick tolerance is not applied to fills.
        Returns ``None`` outside tick mode, where the level-based quote applies.

        shortcut: fills at that tick's own quote without sampling execution
        latency; upgrade if latency must also apply to these fills.

        Args:
            bar_time: Start of the bar whose OHLC reached the level.
            direction: Signed position direction.
            level: Stop or target price that OHLC reached.

        Returns:
            ``(bid, ask)`` of the nearest executable tick, or ``None`` outside tick mode
            or when the book has no usable tick.

        Raises:
            TickExecutionUnavailable: In tick mode without a TickBook.
        """
        if not self._tick_fill_mode():
            return None
        if self._tickbook is None:
            raise TickExecutionUnavailable("tick fill mode requires a TickBook")
        pos = self.position
        entry = (
            None
            if pos is None or pos.entry_timestamp is None
            else pd.Timestamp(cast(Any, pos.entry_timestamp))
        )
        quote = nearest_exit_tick_quote(
            self._tickbook,
            pd.Timestamp(bar_time),
            direction,
            level,
            bar_minutes=max(1, int(round(self._minutes_per_step))),
            earliest_time=entry,
            max_gap_ns=int(self.max_tick_quote_wait_ms) * 1_000_000,
        )
        if quote is None:
            # No eligible tick within the wait cap, so the level-based quote applies.
            return None
        bid, ask = quote
        exit_price = bid if direction == 1 else ask
        tick_is_worse = exit_price <= level if direction == 1 else exit_price >= level
        if not tick_is_worse:
            # The nearest tick is better than the level (a stop the tape never
            # crossed), so pricing at it would turn a stop into a gain. Use the level.
            return cast(tuple[float, float], self._sl_tp_fill_quote(direction, level))
        return quote

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
        target can pay more than $100. A bar-range touch with no crossing tick
        fills at the nearest in-window tick, or at the level when that tick
        would be better for the position. Slippage, when configured, moves
        that level fill only against the position. If both levels sit inside
        one bar and there is no tick, the stop wins.

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
                # A tick exit ended the position, or a stop moved mid-bar. Such a stop
                # cannot be ordered against the bar's earlier OHLC range, so stop here.
                if self.position is None or self.position.sl_price != before_replay[1]:
                    return
                # A partial exit left a runner whose stop no tick crossed. The bar's
                # OHLC touches still apply to it below, priced at the nearest tick.

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
                self._untriggered_level_quote(
                    log_time, int(self.position.direction), float(self.position.sl_price)
                )
                or self._stop_fill_quote(
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

                    quote = self._untriggered_level_quote(
                        log_time, int(pos.direction), float(slot_px)
                    ) or self._sl_tp_fill_quote(int(pos.direction), float(slot_px))
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
                    self._untriggered_level_quote(
                        log_time, int(self.position.direction), float(self.position.tp_price)
                    )
                    or self._sl_tp_fill_quote(
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
        # Entry time is fixed for this position, so convert it once, not per tick.
        entry_ts = (
            None if pos.entry_timestamp is None else pd.Timestamp(cast(Any, pos.entry_timestamp))
        )
        for tick_ns, bid, ask in _pending_tp_sl_quotes(pos, book, bar_time, bar_minutes):
            if self.position is not pos or pos.size <= 0:
                break
            if tick_ns < last_fill_ns:
                continue
            if entry_ts is not None and tick_ns < entry_ts.value:
                continue
            # Timestamps are built only on a hit; the tick itself is raw nanoseconds.
            tick_time: pd.Timestamp | None = None
            exit_side = bid if pos.direction == 1 else ask
            sl = pos.sl_price
            stop_hit = sl is not None and (
                tick_price_reaches_level(exit_side, sl, direction=-int(pos.direction))
            )
            if stop_hit:
                tick_time = pd.Timestamp(tick_ns, unit="ns", tz="UTC")
                execution_meta: dict[str, Any] = {}
                if getattr(self, "server_side_protective_orders", False):
                    execution_time = tick_time
                    execution_meta = {
                        "order_submission_time": tick_time,
                        "execution_order_time": tick_time,
                        "execution_arrival_time": tick_time,
                        "execution_latency_ns": 0,
                        "actual_tick_time": tick_time,
                        "fill_quote_source": "tick",
                    }
                elif (
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
                target_hit = tick_price_reaches_level(
                    exit_side, slot_px, direction=int(pos.direction)
                )
                if not target_hit:
                    continue
                if tick_time is None:
                    tick_time = pd.Timestamp(tick_ns, unit="ns", tz="UTC")
                execution_meta = {}
                if getattr(self, "server_side_protective_orders", False):
                    execution_time = tick_time
                    execution_meta = {
                        "order_submission_time": tick_time,
                        "execution_order_time": tick_time,
                        "execution_arrival_time": tick_time,
                        "execution_latency_ns": 0,
                        "actual_tick_time": tick_time,
                        "fill_quote_source": "tick",
                    }
                elif (
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


def _pending_tp_sl_quotes(
    pos: Any, book: Any, bar_time: pd.Timestamp, bar_minutes: int
) -> Iterator[tuple[int, float, float]]:
    """Yield only the bar quotes that could stop out or fill a target for the open position.

    A quote that reaches neither the stop nor an open target does nothing in the replay loop,
    so skipping it changes no state. The candidate is re-evaluated from the position's current
    levels after every yielded quote, so a fill that moves a level is respected. Entry and
    last-fill filters stay in the replay loop.

    Args:
        pos: Open position whose levels decide which quotes can act.
        book: TickBook for the instrument.
        bar_time: Bar start time.
        bar_minutes: Bar length in minutes.

    Yields:
        Quote nanoseconds (UTC), bid and ask, in timestamp order.
    """
    ts, bid_arr, ask_arr = book.bar_arrays(bar_time, bar_minutes=bar_minutes)
    count = int(ts.shape[0])
    cursor = 0
    while cursor < count:
        exit_side = bid_arr if pos.direction == 1 else ask_arr
        hit = np.zeros(count - cursor, dtype=bool)
        if pos.sl_price is not None:
            hit |= _level_reached(exit_side[cursor:], pos.sl_price, -int(pos.direction))
        for slot_num in (1, 2, 3):
            slot_px = getattr(pos, f"tp{slot_num}_price")
            if slot_px is None or pos.tp_hit_mask & (1 << (slot_num - 1)):
                continue
            hit |= _level_reached(exit_side[cursor:], slot_px, int(pos.direction))
        found = np.flatnonzero(hit)
        if found.size == 0:
            return
        index = cursor + int(found[0])
        yield (int(ts[index]), float(bid_arr[index]), float(ask_arr[index]))
        cursor = index + 1


def _level_reached(prices: Any, level: float, direction: int) -> Any:
    """Vector form of ``tick_price_reaches_level`` over a slice of exit prices.

    Args:
        prices: Executable exit prices, one per tick.
        level: Protective price level.
        direction: +1 for an upward crossing, -1 for a downward crossing.

    Returns:
        Boolean array, True where the tick reaches or crosses the level.
    """
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or +1")
    boundary = math.nextafter(float(level), -math.inf if direction == 1 else math.inf)
    return prices >= boundary if direction == 1 else prices <= boundary
