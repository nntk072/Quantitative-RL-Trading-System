"""Normalize raw bar timestamps and flag gaps between bars."""

from __future__ import annotations

from typing import cast

import pandas as pd


def clean(df: pd.DataFrame, tz: str = "Etc/GMT-3") -> pd.DataFrame:
    """Deduplicate, sort, localise timezone, and add a ``gap_flag`` column.

    Args:
        df: Raw bar DataFrame from :func:`market_data.loading.bars.load_bars`.
        tz: Timezone used to carry naive source wall-clock labels in the index.
            It is not an absolute-timezone claim when the source clock observes DST.

    Returns:
        A sorted copy with duplicate timestamps removed (keeping the last),
        a ``gap_flag`` column, and a timezone-aware index when the input index
        was naive. A gap is larger than twice the modal bar interval.
    """
    df = df.copy()
    df = df[~df.index.duplicated(keep="last")]
    df = df.sort_index()
    index = cast(pd.DatetimeIndex, df.index)
    if index.tz is None:
        df.index = index.tz_localize(tz, ambiguous="infer", nonexistent="shift_forward")
    # A gap is larger than twice the modal interval between bars.
    delta = cast(pd.DatetimeIndex, df.index).to_series().diff()
    modal = delta.mode().iloc[0]
    df["gap_flag"] = delta > (2 * modal)
    df["gap_flag"] = df["gap_flag"].fillna(False)
    return df
