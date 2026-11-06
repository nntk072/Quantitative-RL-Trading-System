"""Causal FVG zone feature construction."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

from features.po3.fvg_detection import FVGConfig, detect_fvg
from features.po3.zones import build_fvg_zones
from features.technical.indicators import atr

_FVG_DIST_CAP = 5.0
_FVG_EVENT_COLUMNS = (
    "confirmation_bar",
    "confirmation_time_ns",
    "side",
    "zone_start_time_ns",
    "source_origin_bar",
    "source_origin_time_ns",
    "zone_low",
    "zone_high",
    "selected_by_scalar",
)


def build_fvg_zone_features(
    bars: pd.DataFrame,
    fvg_config: FVGConfig | None = None,
    max_zone_bars: int = 50,
) -> pd.DataFrame:
    """Build causal scalar FVG zone features for one timeframe's own bars.

    Features include active-zone proximity, retest flags, current bounds, and
    the candle-one origin. When overlapping same-side retests confirm on one
    row, the newest zone in source-time order supplies the scalar event time
    and origin. Use :func:`build_fvg_zone_features_with_event_ledger` to inspect
    all same-row confirmations without changing this model-facing output.

    Args:
        bars: OHLC bars indexed by their decision timestamps.
        fvg_config: Optional gap and retest configuration.
        max_zone_bars: Maximum active lifetime of each FVG zone.

    Returns:
        One row per input bar with scalar FVG-zone features.
    """
    features, _ = _build_fvg_zone_features(bars, fvg_config, max_zone_bars)
    return features


def build_fvg_zone_features_with_event_ledger(
    bars: pd.DataFrame,
    fvg_config: FVGConfig | None = None,
    max_zone_bars: int = 50,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return scalar FVG features and every per-zone retest confirmation.

    The scalar feature projection is identical to
    :func:`build_fvg_zone_features`. The ledger preserves same-row overlapping
    zone confirmations and marks the zone whose source time the scalar feature
    selected. It is diagnostic data, not additional policy actions.

    Args:
        bars: OHLC bars indexed by their decision timestamps.
        fvg_config: Optional FVG detection and retest configuration.
        max_zone_bars: Maximum active lifetime of each FVG zone.

    Returns:
        A pair of the unchanged scalar feature frame and a per-zone event ledger.
    """
    return _build_fvg_zone_features(bars, fvg_config, max_zone_bars, collect_events=True)


def _build_fvg_zone_features(
    bars: pd.DataFrame,
    fvg_config: FVGConfig | None = None,
    max_zone_bars: int = 50,
    *,
    collect_events: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build model-facing FVG features and optionally collect zone events.

    Args:
        bars: Chronological OHLC bars for the source timeframe.
        fvg_config: Gap detection and retest settings, when customized.
        max_zone_bars: Maximum age of a zone in source-timeframe bars.
        collect_events: Whether to return every per-zone confirmation.

    Returns:
        Scalar feature frame and event ledger; the ledger is empty when disabled.
    """
    if max_zone_bars < 0:
        raise ValueError("max_zone_bars must be nonnegative")
    n = len(bars)
    idx = bars.index
    out = pd.DataFrame(
        0.0,
        index=idx,
        columns=[
            "fvg_in_bull",
            "fvg_in_bear",
            "fvg_bull_dist",
            "fvg_bear_dist",
            "fvg_retest_bull",
            "fvg_retest_bear",
            "fvg_bull_active",
            "fvg_bear_active",
            "fvg_bull_low",
            "fvg_bull_high",
            "fvg_bear_low",
            "fvg_bear_high",
            "fvg_bull_origin",
            "fvg_bear_origin",
            "fvg_bull_retest_confirmed_at_time_ns",
            "fvg_bear_retest_confirmed_at_time_ns",
            "fvg_bull_retest_origin_time_ns",
            "fvg_bear_retest_origin_time_ns",
        ],
    )
    out["fvg_bull_dist"] = _FVG_DIST_CAP
    out["fvg_bear_dist"] = _FVG_DIST_CAP
    out["fvg_bull_retest_confirmed_at_time_ns"] = np.nan
    out["fvg_bear_retest_confirmed_at_time_ns"] = np.nan
    out["fvg_bull_retest_origin_time_ns"] = np.nan
    out["fvg_bear_retest_origin_time_ns"] = np.nan
    for col in (
        "fvg_bull_low",
        "fvg_bull_high",
        "fvg_bear_low",
        "fvg_bear_high",
        "fvg_bull_origin",
        "fvg_bear_origin",
    ):
        out[col] = np.nan

    if n == 0:
        return out, pd.DataFrame(columns=_FVG_EVENT_COLUMNS)

    if fvg_config is not None and (
        not np.isfinite(fvg_config.reaction_buffer_fraction)
        or fvg_config.reaction_buffer_fraction < 0.0
    ):
        raise ValueError("reaction_buffer_fraction must be finite and nonnegative")
    reaction_buffer_fraction = (
        0.1
        if fvg_config is None
        else fvg_config.reaction_buffer_fraction
        if fvg_config.reaction_buffer_enabled
        else 0.0
    )

    signals = detect_fvg(bars, fvg_config)
    # build_fvg_zones() matches on the htf_fvg_* column family; rename the
    # plain detect_fvg() output so the zone builder recognises it.
    signals = signals.rename(
        columns={
            "fvg_bullish": "htf_fvg_bullish",
            "fvg_bullish_low": "htf_fvg_bullish_low",
            "fvg_bullish_high": "htf_fvg_bullish_high",
            "fvg_bearish": "htf_fvg_bearish",
            "fvg_bearish_low": "htf_fvg_bearish_low",
            "fvg_bearish_high": "htf_fvg_bearish_high",
        }
    )
    zones = build_fvg_zones(bars, signals, max_zone_bars=max_zone_bars, signals_are_events=True)
    if not zones:
        return out, pd.DataFrame(columns=_FVG_EVENT_COLUMNS)

    atr_s = atr(bars, period=14).to_numpy()
    close = bars["close"].to_numpy()
    high = bars["high"].to_numpy()
    low = bars["low"].to_numpy()
    bull_in = cast(int, out.columns.get_loc("fvg_in_bull"))
    bear_in = cast(int, out.columns.get_loc("fvg_in_bear"))
    bull_dist = cast(int, out.columns.get_loc("fvg_bull_dist"))
    bear_dist = cast(int, out.columns.get_loc("fvg_bear_dist"))
    bull_retest = cast(int, out.columns.get_loc("fvg_retest_bull"))
    bear_retest = cast(int, out.columns.get_loc("fvg_retest_bear"))
    bull_active = cast(int, out.columns.get_loc("fvg_bull_active"))
    bear_active = cast(int, out.columns.get_loc("fvg_bear_active"))
    bull_lo = cast(int, out.columns.get_loc("fvg_bull_low"))
    bull_hi = cast(int, out.columns.get_loc("fvg_bull_high"))
    bear_lo = cast(int, out.columns.get_loc("fvg_bear_low"))
    bear_hi = cast(int, out.columns.get_loc("fvg_bear_high"))
    bull_origin = cast(int, out.columns.get_loc("fvg_bull_origin"))
    bear_origin = cast(int, out.columns.get_loc("fvg_bear_origin"))
    bull_retest_time = cast(int, out.columns.get_loc("fvg_bull_retest_confirmed_at_time_ns"))
    bear_retest_time = cast(int, out.columns.get_loc("fvg_bear_retest_confirmed_at_time_ns"))
    bull_retest_origin_time = cast(int, out.columns.get_loc("fvg_bull_retest_origin_time_ns"))
    bear_retest_origin_time = cast(int, out.columns.get_loc("fvg_bear_retest_origin_time_ns"))

    # The zone/bar loop can touch millions of cells on a full M1 history.
    # DataFrame.iat performs indexer and block-manager work for every scalar
    # access, so keep the same ordered updates in a local homogeneous array
    # and wrap it back into the original column schema once at the end.
    values = out.to_numpy(copy=True)
    event_records: list[dict[str, object]] = []

    # Zones are source-time sorted. If several same-side retests confirm on
    # one row, the newest zone deterministically supplies the scalar event key.
    for zone in zones:
        start_i = int(idx.searchsorted(zone.start_ts, side="left"))
        end_i = int(idx.searchsorted(zone.end_ts, side="left" if zone.invalidated else "right"))
        if start_i >= n:
            continue
        origin_i = start_i - 2
        mid = 0.5 * (zone.zone_low + zone.zone_high)
        left = False
        pending_retest: tuple[int, float] | None = None
        reaction_buffer = (zone.zone_high - zone.zone_low) * reaction_buffer_fraction
        bull = zone.side == "bullish"
        for i in range(start_i, min(end_i, n)):
            if bull:
                edge = zone.zone_high if close[i] >= mid else zone.zone_low
            else:
                edge = zone.zone_low if close[i] <= mid else zone.zone_high
            d = abs(close[i] - edge)
            a = atr_s[i]
            in_col, dist_col = (bull_in, bull_dist) if bull else (bear_in, bear_dist)
            if np.isfinite(a) and a > 0.0:
                dist = min(d / a, values[i, dist_col])
            else:
                # The cap is also the explicit missing/unavailable-distance
                # value; using 1 price unit as a fake ATR invents precision.
                dist = values[i, dist_col]
            values[i, dist_col] = dist
            if zone.zone_low <= close[i] <= zone.zone_high:
                values[i, in_col] = 1.0
            if bull:
                values[i, bull_active] = 1.0
                values[i, bull_lo] = zone.zone_low
                values[i, bull_hi] = zone.zone_high
                if origin_i >= 0:
                    values[i, bull_origin] = low[origin_i]
                if (
                    pending_retest is not None
                    and i > pending_retest[0]
                    and close[i] > max(pending_retest[1], zone.zone_high + reaction_buffer)
                ):
                    values[i, bull_retest] = 1.0
                    values[i, bull_retest_time] = pd.Timestamp(idx[i]).value
                    values[i, bull_retest_origin_time] = pd.Timestamp(zone.start_ts).value
                    if collect_events:
                        event_records.append(
                            {
                                "confirmation_bar": i,
                                "confirmation_time_ns": pd.Timestamp(idx[i]).value,
                                "side": "bullish",
                                "zone_start_time_ns": pd.Timestamp(zone.start_ts).value,
                                "source_origin_bar": origin_i,
                                "source_origin_time_ns": pd.Timestamp(idx[origin_i]).value
                                if origin_i >= 0
                                else None,
                                "zone_low": zone.zone_low,
                                "zone_high": zone.zone_high,
                            }
                        )
                    pending_retest = None
                if left and low[i] <= zone.zone_high and high[i] >= zone.zone_low:
                    pending_retest = (
                        i if pending_retest is None else pending_retest[0],
                        high[i] if pending_retest is None else max(pending_retest[1], high[i]),
                    )
                if low[i] > zone.zone_high:
                    left = True
            else:
                values[i, bear_active] = 1.0
                values[i, bear_lo] = zone.zone_low
                values[i, bear_hi] = zone.zone_high
                if origin_i >= 0:
                    values[i, bear_origin] = high[origin_i]
                if (
                    pending_retest is not None
                    and i > pending_retest[0]
                    and close[i] < min(pending_retest[1], zone.zone_low - reaction_buffer)
                ):
                    values[i, bear_retest] = 1.0
                    values[i, bear_retest_time] = pd.Timestamp(idx[i]).value
                    values[i, bear_retest_origin_time] = pd.Timestamp(zone.start_ts).value
                    if collect_events:
                        event_records.append(
                            {
                                "confirmation_bar": i,
                                "confirmation_time_ns": pd.Timestamp(idx[i]).value,
                                "side": "bearish",
                                "zone_start_time_ns": pd.Timestamp(zone.start_ts).value,
                                "source_origin_bar": origin_i,
                                "source_origin_time_ns": pd.Timestamp(idx[origin_i]).value
                                if origin_i >= 0
                                else None,
                                "zone_low": zone.zone_low,
                                "zone_high": zone.zone_high,
                            }
                        )
                    pending_retest = None
                if left and low[i] <= zone.zone_high and high[i] >= zone.zone_low:
                    pending_retest = (
                        i if pending_retest is None else pending_retest[0],
                        low[i] if pending_retest is None else min(pending_retest[1], low[i]),
                    )
                if high[i] < zone.zone_low:
                    left = True
    features = pd.DataFrame(values, index=idx, columns=out.columns)
    if not event_records:
        return features, pd.DataFrame(columns=_FVG_EVENT_COLUMNS)
    events = pd.DataFrame.from_records(event_records)
    selected_origin = {
        "bullish": "fvg_bull_retest_origin_time_ns",
        "bearish": "fvg_bear_retest_origin_time_ns",
    }
    selected_by_scalar: list[bool] = []
    for _, event in events.iterrows():
        bar = int(cast(int, event["confirmation_bar"]))
        side = str(event["side"])
        origin_time = int(cast(int, event["zone_start_time_ns"]))
        selected = features.iloc[bar][selected_origin[side]]
        selected_by_scalar.append(pd.notna(selected) and int(selected) == origin_time)
    events["selected_by_scalar"] = selected_by_scalar
    return features, events.reindex(columns=_FVG_EVENT_COLUMNS)
