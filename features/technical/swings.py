"""Confirmed fractal pivots and ATR-filtered zigzag swings."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from features.technical.indicators import atr as compute_atr

TIMEFRAME_CONFIG: dict[str, dict[str, float | int]] = {
    "M1": {"left": 3, "right": 3, "atr_mult": 0.8, "atr_period": 14},
    "M3": {"left": 3, "right": 3, "atr_mult": 0.75, "atr_period": 14},
    "M5": {"left": 3, "right": 3, "atr_mult": 0.7, "atr_period": 14},
    # M10 uses the midpoint ATR threshold of its adjacent M5/M15 profiles.
    "M10": {"left": 3, "right": 3, "atr_mult": 0.65, "atr_period": 14},
    "M15": {"left": 4, "right": 4, "atr_mult": 0.6, "atr_period": 14},
    "M30": {"left": 4, "right": 4, "atr_mult": 0.55, "atr_period": 14},
    "H1": {"left": 4, "right": 4, "atr_mult": 0.5, "atr_period": 14},
    "H4": {"left": 5, "right": 5, "atr_mult": 0.5, "atr_period": 14},
    "D1": {"left": 5, "right": 5, "atr_mult": 0.5, "atr_period": 14},
}


def detect_pivots(df: pd.DataFrame, left: int = 2, right: int = 2) -> pd.DataFrame:
    """Detect fractal pivots; features populate only from the confirmation bar.

    A pivot at bar ``i`` is known at bar ``i + right``. High pivots use the
    highest wick and low pivots use the lowest wick; both become visible only
    at the confirmation bar.

    Args:
        df: OHLC frame with a DatetimeIndex.
        left: Bars before the pivot that must be strictly lower/higher.
        right: Confirmation bars after the pivot.

    Returns:
        Frame with pivot high/low event, price, extreme, and location columns.
    """
    n = len(df)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)

    ev_h = np.zeros(n, dtype=bool)
    ev_l = np.zeros(n, dtype=bool)
    price_h = np.full(n, np.nan)
    price_l = np.full(n, np.nan)
    ext_h = np.full(n, np.nan)
    ext_l = np.full(n, np.nan)
    loc_h = np.full(n, np.nan)
    loc_l = np.full(n, np.nan)

    for i in range(left, n - right):
        conf = i + right
        left_h = high[i - left : i]
        right_h = high[i + 1 : i + right + 1]
        left_l = low[i - left : i]
        right_l = low[i + 1 : i + right + 1]
        if left_h.size and right_h.size and high[i] > left_h.max() and high[i] > right_h.max():
            ev_h[conf] = True
            price_h[conf] = high[i]
            ext_h[conf] = high[i]
            loc_h[conf] = i
        if left_l.size and right_l.size and low[i] < left_l.min() and low[i] < right_l.min():
            ev_l[conf] = True
            price_l[conf] = low[i]
            ext_l[conf] = low[i]
            loc_l[conf] = i

    return pd.DataFrame(
        {
            "pivot_high_event": ev_h,
            "pivot_high_price": price_h,
            "pivot_high_extreme": ext_h,
            "pivot_high_location": loc_h,
            "pivot_low_event": ev_l,
            "pivot_low_price": price_l,
            "pivot_low_extreme": ext_l,
            "pivot_low_location": loc_l,
        },
        index=df.index,
    )


def detect_swings(
    df: pd.DataFrame,
    pivots: pd.DataFrame,
    atr: pd.Series | None = None,
    atr_mult: float = 0.5,
) -> pd.DataFrame:
    """ATR-filtered zigzag on confirmed pivots.

    A candidate is created at fractal confirmation, replaced if a more extreme
    candidate appears before reversal, and accepted when close reverses by
    ``atr_mult * ATR`` frozen at candidate confirmation. When ATR is missing
    the candidate is accepted on its confirmation bar.

    Args:
        df: OHLC frame aligned with ``pivots``.
        pivots: Output of :func:`detect_pivots`.
        atr: ATR series; computed from ``df`` when None.
        atr_mult: Reversal threshold in ATR units.
    """
    n = len(df)
    close = df["close"].to_numpy(dtype=float)
    if atr is None:
        atr_arr = compute_atr(df, period=14).to_numpy(dtype=float)
    else:
        atr_arr = atr.reindex(df.index).to_numpy(dtype=float)

    ev_h = pivots["pivot_high_event"].to_numpy(dtype=bool)
    ev_l = pivots["pivot_low_event"].to_numpy(dtype=bool)
    ph = pivots["pivot_high_price"].to_numpy(dtype=float)
    pl = pivots["pivot_low_price"].to_numpy(dtype=float)
    eh = pivots["pivot_high_extreme"].to_numpy(dtype=float)
    el = pivots["pivot_low_extreme"].to_numpy(dtype=float)
    lh = pivots["pivot_high_location"].to_numpy(dtype=float)
    ll = pivots["pivot_low_location"].to_numpy(dtype=float)

    acc_h = np.zeros(n, dtype=bool)
    acc_l = np.zeros(n, dtype=bool)
    out_price_h = np.full(n, np.nan)
    out_price_l = np.full(n, np.nan)
    out_ext_h = np.full(n, np.nan)
    out_ext_l = np.full(n, np.nan)
    out_loc_h = np.full(n, np.nan)
    out_loc_l = np.full(n, np.nan)

    cand_h: dict[str, float] | None = None
    cand_l: dict[str, float] | None = None
    last_side = 0

    def _atr_at(i: int) -> float:
        a = atr_arr[i]
        return float(a) if np.isfinite(a) else 0.0

    for t in range(n):
        if ev_h[t] and last_side != 1:
            cand = {
                "price": float(ph[t]),
                "extreme": float(eh[t]),
                "loc": float(lh[t]),
                "atr": _atr_at(t),
            }
            if cand_h is None or cand["extreme"] >= cand_h["extreme"]:
                cand_h = cand
        if ev_l[t] and last_side != -1:
            cand = {
                "price": float(pl[t]),
                "extreme": float(el[t]),
                "loc": float(ll[t]),
                "atr": _atr_at(t),
            }
            if cand_l is None or cand["extreme"] <= cand_l["extreme"]:
                cand_l = cand

        if cand_h is not None and last_side != 1:
            thresh = atr_mult * cand_h["atr"]
            reversed_h = thresh <= 0.0 or close[t] <= cand_h["price"] - thresh
            if reversed_h:
                acc_h[t] = True
                out_price_h[t] = cand_h["price"]
                out_ext_h[t] = cand_h["extreme"]
                out_loc_h[t] = cand_h["loc"]
                last_side = 1
                cand_h = None
                continue
        if cand_l is not None and last_side != -1:
            thresh = atr_mult * cand_l["atr"]
            reversed_l = thresh <= 0.0 or close[t] >= cand_l["price"] + thresh
            if reversed_l:
                acc_l[t] = True
                out_price_l[t] = cand_l["price"]
                out_ext_l[t] = cand_l["extreme"]
                out_loc_l[t] = cand_l["loc"]
                last_side = -1
                cand_l = None

    cur_ph = cur_eh = cur_lh = np.nan
    cur_pl = cur_el = cur_ll = np.nan
    ffill_h = np.full(n, np.nan)
    ffill_l = np.full(n, np.nan)
    ffill_eh = np.full(n, np.nan)
    ffill_el = np.full(n, np.nan)
    ffill_lh = np.full(n, np.nan)
    ffill_ll = np.full(n, np.nan)
    for t in range(n):
        if acc_h[t]:
            cur_ph, cur_eh, cur_lh = out_price_h[t], out_ext_h[t], out_loc_h[t]
        if acc_l[t]:
            cur_pl, cur_el, cur_ll = out_price_l[t], out_ext_l[t], out_loc_l[t]
        ffill_h[t], ffill_eh[t], ffill_lh[t] = cur_ph, cur_eh, cur_lh
        ffill_l[t], ffill_el[t], ffill_ll[t] = cur_pl, cur_el, cur_ll

    return pd.DataFrame(
        {
            "swing_high_event": acc_h,
            "swing_high_price": ffill_h,
            "swing_high_extreme": ffill_eh,
            "swing_high_location": ffill_lh,
            "swing_low_event": acc_l,
            "swing_low_price": ffill_l,
            "swing_low_extreme": ffill_el,
            "swing_low_location": ffill_ll,
        },
        index=df.index,
    )


def classify_structure(swings: pd.DataFrame) -> pd.DataFrame:
    """Classify accepted swings as HH/HL/LH/LL.

    Args:
        swings: Output of :func:`detect_swings`.

    Returns:
        Frame with ``structure`` (string) plus one-hot HH/HL/LH/LL flags.
    """
    n = len(swings)
    ev_h = swings["swing_high_event"].to_numpy(dtype=bool)
    ev_l = swings["swing_low_event"].to_numpy(dtype=bool)
    px_h = swings["swing_high_price"].to_numpy(dtype=float)
    px_l = swings["swing_low_price"].to_numpy(dtype=float)
    labels = np.empty(n, dtype=object)
    labels[:] = ""
    hh = np.zeros(n)
    hl = np.zeros(n)
    lh = np.zeros(n)
    ll = np.zeros(n)
    prev_h = np.nan
    prev_l = np.nan
    for t in range(n):
        if ev_h[t]:
            if np.isfinite(prev_h):
                if px_h[t] > prev_h:
                    labels[t] = "HH"
                    hh[t] = 1.0
                elif px_h[t] < prev_h:
                    labels[t] = "LH"
                    lh[t] = 1.0
            prev_h = px_h[t]
        if ev_l[t]:
            if np.isfinite(prev_l):
                if px_l[t] > prev_l:
                    labels[t] = "HL"
                    hl[t] = 1.0
                elif px_l[t] < prev_l:
                    labels[t] = "LL"
                    ll[t] = 1.0
            prev_l = px_l[t]
    return pd.DataFrame(
        {
            "structure": labels,
            "hh": hh,
            "hl": hl,
            "lh": lh,
            "ll": ll,
        },
        index=swings.index,
    )


def swing_features(
    df: pd.DataFrame,
    swings: pd.DataFrame,
    structure: pd.DataFrame,
    atr: pd.Series | None = None,
    obs_window: int = 60,
) -> pd.DataFrame:
    """Causal continuous swing features for the agent.

    Last swing means last swing confirmed and observable at the current bar.

    Args:
        df: OHLC frame.
        swings: Output of :func:`detect_swings`.
        structure: Output of :func:`classify_structure`.
        atr: ATR series; computed when None.
    """
    if atr is None:
        atr_s = compute_atr(df, period=14)
    else:
        atr_s = atr.reindex(df.index)
    atr_safe = atr_s.where(atr_s > 0)
    close = df["close"]
    last_h = swings["swing_high_extreme"]
    last_l = swings["swing_low_extreme"]
    dist_h = (last_h - close) / atr_safe
    dist_l = (close - last_l) / atr_safe
    nearest = pd.concat([dist_h.abs(), dist_l.abs()], axis=1).min(axis=1)
    side = pd.Series(np.nan, index=df.index)
    side = side.where(~swings["swing_high_event"], 1.0)
    side = side.where(~swings["swing_low_event"], -1.0)
    side = side.ffill()
    size = (last_h - last_l).abs() / atr_safe
    since_h = _bars_since(swings["swing_high_event"].to_numpy(dtype=bool))
    since_l = _bars_since(swings["swing_low_event"].to_numpy(dtype=bool))
    since_raw = np.fmin(since_h, since_l)
    window = max(int(obs_window), 1)
    since = np.minimum(since_raw, float(window)) / float(window)
    return pd.DataFrame(
        {
            "dist_to_last_high_atr": dist_h,
            "dist_to_last_low_atr": dist_l,
            "dist_to_nearest_swing_atr": nearest,
            "last_swing_side": side,
            "last_swing_size_atr": size,
            "bars_since_last_swing": since,
            "hh": structure["hh"],
            "hl": structure["hl"],
            "lh": structure["lh"],
            "ll": structure["ll"],
            "swing_high_event": swings["swing_high_event"].astype(float),
            "swing_low_event": swings["swing_low_event"].astype(float),
        },
        index=df.index,
    )


MAX_RETAINED_LEVELS = 8


def retained_swing_levels(
    swings: pd.DataFrame,
    bars: pd.DataFrame,
    *,
    max_levels: int = MAX_RETAINED_LEVELS,
) -> pd.DataFrame:
    """Retain every currently-unswept confirmed swing level per side.

    Unlike :func:`swing_history`, which keeps the last N *accepted* swings
    regardless of whether they were swept, this removes a level as soon as
    price takes it out. So at any bar the retained set contains only levels
    that are still valid reference points.

    A high level is swept when ``high[t]`` exceeds it (a low level when
    ``low[t]`` falls below it). The sweep is recorded as an event on the bar
    it happens, and the level is dropped from the retained set on the same
    bar, so downstream components can distinguish "this level never existed"
    from "this level existed and was just swept" via the swept event columns.

    All levels are causally observable: a swing enters the set only on its
    confirmation bar, never before.

    Args:
        swings: Output of :func:`detect_swings`.
        bars: OHLC frame aligned with ``swings``; needs ``high``/``low``.
        max_levels: Cap on retained levels per side per bar (fixed-width).

    Returns:
        Frame indexed like ``swings`` with, per side:
        ``retained_highs`` / ``retained_lows`` (list of retained levels),
        ``retained_high_locs`` / ``retained_low_locs`` (their bar locations),
        ``n_retained_highs`` / ``n_retained_lows`` (counts),
        ``swept_high`` / ``swept_low`` (level swept this bar, else NaN),
        ``swept_high_loc`` / ``swept_low_loc`` (its bar location, else NaN).
    """
    n = len(swings)
    ev_h = swings["swing_high_event"].to_numpy(dtype=bool)
    ev_l = swings["swing_low_event"].to_numpy(dtype=bool)
    px_h = swings["swing_high_extreme"].to_numpy(dtype=float)
    px_l = swings["swing_low_extreme"].to_numpy(dtype=float)
    loc_h = swings["swing_high_location"].to_numpy(dtype=float)
    loc_l = swings["swing_low_location"].to_numpy(dtype=float)
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)

    k = max(int(max_levels), 1)
    out_h = np.full((n, k), np.nan)
    out_l = np.full((n, k), np.nan)
    loc_hh = np.full((n, k), np.nan)
    loc_ll = np.full((n, k), np.nan)
    n_h = np.zeros(n, dtype=int)
    n_l = np.zeros(n, dtype=int)
    swept_h = np.full(n, np.nan)
    swept_l = np.full(n, np.nan)
    swept_h_loc = np.full(n, np.nan)
    swept_l_loc = np.full(n, np.nan)

    # Each retained level is (price, pivot location, sweep already emitted).
    # A wick sweep is an event, but only a body close through the level
    # invalidates it. Keeping these states separate avoids repeating an event
    # while preserving a level that has not been invalidated by close.
    highs: list[tuple[float, float, bool]] = []
    lows: list[tuple[float, float, bool]] = []
    close = bars["close"].to_numpy(dtype=float)

    for t in range(n):
        # A swing enters the retained set only on its confirmation bar.
        if ev_h[t] and np.isfinite(px_h[t]) and np.isfinite(loc_h[t]):
            highs.append((float(px_h[t]), float(loc_h[t]), False))
        if ev_l[t] and np.isfinite(px_l[t]) and np.isfinite(loc_l[t]):
            lows.append((float(px_l[t]), float(loc_l[t]), False))

            # A body close through invalidates a level. A wick beyond it marks a
            # one-time sweep event while the level remains available until close
            # confirms invalidation.
        highs = [(lv, lc, close[t] > lv) for lv, lc, _ in highs]
        lows = [(lv, lc, close[t] < lv) for lv, lc, _ in lows]
        highs = [item for item in highs if not item[2]]
        lows = [item for item in lows if not item[2]]
        high_events = [i for i, (lv, _loc, swept) in enumerate(highs) if not swept and high[t] > lv]
        low_events = [i for i, (lv, _loc, swept) in enumerate(lows) if not swept and low[t] < lv]
        if high_events:
            swept_idx = high_events[0]
            lv, lc, _ = highs[swept_idx]
            swept_h[t], swept_h_loc[t] = lv, lc
            highs[swept_idx] = (lv, lc, True)
        if low_events:
            swept_idx = low_events[0]
            lv, lc, _ = lows[swept_idx]
            swept_l[t], swept_l_loc[t] = lv, lc
            lows[swept_idx] = (lv, lc, True)

            # Cap size so the output matrix stays fixed-width.
        if len(highs) > k:
            highs = highs[-k:]
        if len(lows) > k:
            lows = lows[-k:]

        n_h[t] = len(highs)
        n_l[t] = len(lows)
        for i, (lv, lc, _swept) in enumerate(highs):
            out_h[t, i] = lv
            loc_hh[t, i] = lc
        for i, (lv, lc, _swept) in enumerate(lows):
            out_l[t, i] = lv
            loc_ll[t, i] = lc

    cols: dict[str, np.ndarray[Any, Any]] = {
        "n_retained_highs": n_h,
        "n_retained_lows": n_l,
        "swept_high": swept_h,
        "swept_low": swept_l,
        "swept_high_loc": swept_h_loc,
        "swept_low_loc": swept_l_loc,
    }
    for i in range(k):
        cols[f"retained_high_{i + 1}"] = out_h[:, i]
        cols[f"retained_low_{i + 1}"] = out_l[:, i]
        cols[f"retained_high_{i + 1}_loc"] = loc_hh[:, i]
        cols[f"retained_low_{i + 1}_loc"] = loc_ll[:, i]
    return pd.DataFrame(cols, index=swings.index)


def recent_unswept_swing_candidates(
    swings: pd.DataFrame,
    bars: pd.DataFrame,
    *,
    count: int = 3,
    price_increment: float | None = None,
    confirmation_delay_ms: int = 0,
) -> pd.DataFrame:
    """Expose the most recent confirmed, unswept swing candidates per side.

    Slot 1 is the newest candidate. A level becomes available on its completed
    confirmation bar and is removed as soon as a later (or same confirmation)
    bar sweeps it. Older candidates fall out when the configured count is
    exceeded; this event-recency rule defines staleness, with no arbitrary
    wall-clock expiry. Pivot/confirmation times are epoch milliseconds so they
    remain exact in the numeric shared-bundle matrix for minute-based bars.
    """
    if not swings.index.equals(bars.index):
        raise ValueError("swings and bars must have identical indexes")
    if count < 1:
        raise ValueError("count must be at least one")
    if price_increment is not None and (not np.isfinite(price_increment) or price_increment <= 0):
        raise ValueError("price_increment must be finite and positive")
    if confirmation_delay_ms < 0:
        raise ValueError("confirmation_delay_ms must be nonnegative")

    n = len(bars)
    high_events = swings["swing_high_event"].to_numpy(dtype=bool)
    low_events = swings["swing_low_event"].to_numpy(dtype=bool)
    high_prices = swings["swing_high_extreme"].to_numpy(dtype=float)
    low_prices = swings["swing_low_extreme"].to_numpy(dtype=float)
    high_locations = swings["swing_high_location"].to_numpy(dtype=float)
    low_locations = swings["swing_low_location"].to_numpy(dtype=float)
    bar_close = bars["close"].to_numpy(dtype=float)
    times_ms = (
        pd.DatetimeIndex(bars.index).to_numpy(dtype="datetime64[ns]").view(np.int64) // 1_000_000
    )

    Candidate = tuple[float, int, int]
    highs: list[Candidate] = []
    lows: list[Candidate] = []

    def tick_key(price: float) -> int | float:
        if price_increment is None:
            return price
        return int(np.rint(price / price_increment))

    def add_distinct(candidates: list[Candidate], candidate: Candidate) -> list[Candidate]:
        key = tick_key(candidate[0])
        # Keep the most recently confirmed representative of a price level.
        candidates = [item for item in candidates if tick_key(item[0]) != key]
        candidates.append(candidate)
        return candidates

    values: dict[str, np.ndarray[Any, Any]] = {}
    for side in ("high", "low"):
        for slot in range(1, count + 1):
            stem = f"swing_{side}_candidate_{slot}"
            values[stem] = np.full(n, np.nan, dtype=np.float64)
            values[f"{stem}_pivot_time_ms"] = np.full(n, np.nan, dtype=np.float64)
            values[f"{stem}_confirmed_at_ms"] = np.full(n, np.nan, dtype=np.float64)
            values[f"{stem}_age_bars"] = np.full(n, np.nan, dtype=np.float64)

    for t in range(n):
        if high_events[t] and np.isfinite(high_prices[t]) and np.isfinite(high_locations[t]):
            highs = add_distinct(highs, (float(high_prices[t]), int(high_locations[t]), t))
        if low_events[t] and np.isfinite(low_prices[t]) and np.isfinite(low_locations[t]):
            lows = add_distinct(lows, (float(low_prices[t]), int(low_locations[t]), t))

            # A wick sweep is still useful context. Remove candidates only after a
            # completed candle body closes through the swing level.
        highs = [candidate for candidate in highs if bar_close[t] <= candidate[0]]
        lows = [candidate for candidate in lows if bar_close[t] >= candidate[0]]
        highs = highs[-count:]
        lows = lows[-count:]

        for side, candidates in (("high", highs), ("low", lows)):
            for slot, (price, pivot_idx, confirmed_idx) in enumerate(reversed(candidates), start=1):
                stem = f"swing_{side}_candidate_{slot}"
                values[stem][t] = price
                values[f"{stem}_pivot_time_ms"][t] = times_ms[pivot_idx]
                values[f"{stem}_confirmed_at_ms"][t] = (
                    times_ms[confirmed_idx] + confirmation_delay_ms
                )
                values[f"{stem}_age_bars"][t] = t - confirmed_idx

    return pd.DataFrame(values, index=bars.index)


def _bars_since(events: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    n = len(events)
    out = np.full(n, np.nan)
    last = -1
    for i in range(n):
        if events[i]:
            last = i
        if last >= 0:
            out[i] = i - last
    return out


def swing_history(swings: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """Last N accepted swing extremes, causally observable.

    ``swing_high_1`` is the most recent accepted swing high; ``swing_high_2``
    is the one before that, and so on. Same for ``swing_low_*``. Bars before
    the first accepted swing are NaN.
    """
    n = max(int(n), 1)
    ev_h = swings["swing_high_event"].to_numpy(dtype=bool)
    ev_l = swings["swing_low_event"].to_numpy(dtype=bool)
    px_h = swings["swing_high_extreme"].to_numpy(dtype=float)
    px_l = swings["swing_low_extreme"].to_numpy(dtype=float)
    m = len(swings)
    out: dict[str, np.ndarray[Any, Any]] = {}
    for i in range(1, n + 1):
        out[f"swing_high_{i}"] = np.full(m, np.nan)
        out[f"swing_low_{i}"] = np.full(m, np.nan)
    hist_h: list[float] = []
    hist_l: list[float] = []
    for t in range(m):
        if ev_h[t] and np.isfinite(px_h[t]):
            hist_h.append(float(px_h[t]))
            hist_h = hist_h[-n:]
        if ev_l[t] and np.isfinite(px_l[t]):
            hist_l.append(float(px_l[t]))
            hist_l = hist_l[-n:]
        for i in range(1, n + 1):
            idx = i - 1
            out[f"swing_high_{i}"][t] = hist_h[idx] if idx < len(hist_h) else np.nan
            out[f"swing_low_{i}"][t] = hist_l[idx] if idx < len(hist_l) else np.nan
    return pd.DataFrame(out, index=swings.index)
