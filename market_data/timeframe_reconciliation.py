"""Higher-timeframe MT5 exports reconciled against M1 bars resampled to the same buckets (DATA-SCHEMAS).

The MT5 export labels bars with Helsinki wall-clock open times. Resampling is done on that local
wall-clock index, so a bucket is the local interval ``[open, open + timeframe)``. A native export bar
is matched to the resampled bucket with the same local open. Every export bar and every resampled
bucket is accounted for as matched, export-only or resampled-only. Field mismatches are counted, not
hidden. Tick volume is compared as recorded; it is not assumed to equal the sum of M1 tick volumes.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from market_data.arrow_schemas import SOURCE_CLOCK

TIMEFRAME_FREQ: dict[str, str] = {
    "M3": "3min",
    "M5": "5min",
    "M10": "10min",
    "M15": "15min",
    "M30": "30min",
    "H1": "1h",
    "H4": "4h",
    "D1": "1D",
}
PRICE_FIELDS = ("open", "high", "low", "close")


def m1_frame(
    event_time_utc: pd.DatetimeIndex, bars: dict[str, np.ndarray[Any, Any]]
) -> pd.DataFrame:
    """Index M1 bars by their local (Helsinki) wall-clock open.

    Args:
        event_time_utc: Bar open times in UTC, tz-aware.
        bars: Arrays named open, high, low, close and volume, aligned with the index.

    Returns:
        A frame indexed by tz-aware local open time with the same columns.
    """
    index = event_time_utc.tz_convert(SOURCE_CLOCK)
    return pd.DataFrame(
        {name: np.asarray(values, dtype=np.float64) for name, values in bars.items()}, index=index
    )


def resample_m1(m1: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Aggregate M1 bars into buckets on the local wall-clock grid.

    Args:
        m1: Frame from :func:`m1_frame`.
        timeframe: MT5 timeframe label in TIMEFRAME_FREQ.

    Returns:
        One row per non-empty bucket with open, high, low, close, volume and m1_count.

    Raises:
        ValueError: If the timeframe is not supported.
    """
    freq = TIMEFRAME_FREQ.get(timeframe)
    if freq is None:
        raise ValueError(f"unsupported timeframe {timeframe!r}")
    grouped = m1.groupby(pd.DatetimeIndex(m1.index).floor(freq))
    return pd.DataFrame(
        {
            "open": grouped["open"].first(),
            "high": grouped["high"].max(),
            "low": grouped["low"].min(),
            "close": grouped["close"].last(),
            "volume": grouped["volume"].sum(),
            "m1_count": grouped.size(),
        }
    )


def export_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Index a parsed export by its local wall-clock open.

    Rows whose local label does not exist or repeats (DST) are dropped and counted by the caller.

    Args:
        frame: Export frame with DATE, OPEN, HIGH, LOW, CLOSE and TICKVOL columns, and TIME unless the
            export is daily (strings).

    Returns:
        Frame indexed by tz-aware local open, with float columns open, high, low, close, volume.
    """
    # Daily exports carry no TIME column: a daily bar opens at local midnight.
    times = (
        frame["TIME"].astype(str)
        if "TIME" in frame.columns
        else pd.Series("00:00:00", index=frame.index)
    )
    local = pd.to_datetime(frame["DATE"].astype(str) + " " + times, format="%Y.%m.%d %H:%M:%S")
    index = local.dt.tz_localize(SOURCE_CLOCK, ambiguous="NaT", nonexistent="NaT")
    keep = index.notna().to_numpy()
    values = pd.DataFrame(
        {
            "open": frame["OPEN"].astype(float).to_numpy(),
            "high": frame["HIGH"].astype(float).to_numpy(),
            "low": frame["LOW"].astype(float).to_numpy(),
            "close": frame["CLOSE"].astype(float).to_numpy(),
            "volume": frame["TICKVOL"].astype(float).to_numpy(),
        },
        index=index,
    )
    return values.loc[keep]


def compare_export_to_resampled(
    export: pd.DataFrame, resampled: pd.DataFrame, m1_first: pd.Timestamp
) -> dict[str, Any]:
    """Count matched, export-only and resampled-only buckets and per-field mismatches.

    Args:
        export: Frame from :func:`export_frame`.
        resampled: Frame from :func:`resample_m1`.
        m1_first: Local open of the first M1 bar in the window. A bucket that starts before it is
            partial at the window edge and is reported separately.

    Returns:
        Counts, per-field mismatch counts, the largest absolute price difference, and the labels of
        the first mismatches (labels only, no values).
    """
    joined = export.join(resampled, how="outer", lsuffix="_export", rsuffix="_resampled")
    export_only = joined["m1_count"].isna()
    resampled_only = joined["open_export"].isna()
    both = ~export_only & ~resampled_only
    matched = joined.loc[both]

    mismatch_counts: dict[str, int] = {}
    any_field = np.zeros(len(matched), dtype=bool)
    max_abs_price_delta = 0.0
    for name in PRICE_FIELDS:
        differs = matched[f"{name}_export"].to_numpy() != matched[f"{name}_resampled"].to_numpy()
        mismatch_counts[name] = int(differs.sum())
        any_field |= differs
        if differs.any():
            delta = np.abs(
                matched[f"{name}_export"].to_numpy() - matched[f"{name}_resampled"].to_numpy()
            )
            max_abs_price_delta = max(max_abs_price_delta, float(delta[differs].max()))
    volume_differs = matched["volume_export"].to_numpy() != matched["volume_resampled"].to_numpy()
    mismatch_counts["volume"] = int(volume_differs.sum())
    any_field |= volume_differs

    edge = matched.index < m1_first
    labels = [ts.strftime("%Y-%m-%d %H:%M") for ts in matched.index[any_field][:10]]
    return {
        "export_bars": int(len(export)),
        "resampled_buckets": int(len(resampled)),
        "matched_buckets": int(both.sum()),
        "export_only_buckets": int(export_only.sum()),
        "resampled_only_buckets": int(resampled_only.sum()),
        "matched_with_all_fields_equal": int((~any_field).sum()),
        "matched_with_any_field_mismatch": int(any_field.sum()),
        "field_mismatch_counts": mismatch_counts,
        "max_abs_price_delta": max_abs_price_delta,
        "window_edge_partial_matched": int(edge.sum()),
        "first_mismatch_local_opens": labels,
    }
