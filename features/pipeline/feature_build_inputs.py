"""Resolve source bars and configuration inputs for feature assembly."""

from __future__ import annotations

from typing import Any, cast

import pandas as pd

from market_data.transforms.align import timeframe_close_times
from market_data.transforms.resample import TF, resample

DEFAULT_MTF_CONTEXT_TIMEFRAMES = ("M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
RAW_FVG_FEATURE_SUFFIXES = (
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
)


def split_raw_fvg_features(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separate raw FVG prices and active/retest flags from normalized features."""
    columns = [
        column
        for column in features.columns
        if any(
            str(column) == suffix or str(column).endswith("_" + suffix)
            for suffix in RAW_FVG_FEATURE_SUFFIXES
        )
    ]
    if not columns:
        return features, pd.DataFrame(index=features.index)
    return features.drop(columns=columns), features.loc[:, columns].copy()


def configured_feature_timeframes(
    feature_config: object, block_name: str, default: tuple[str, ...]
) -> list[str]:
    """Read timeframe configuration from a nested feature block or flat key."""
    raw: object = None
    if feature_config is not None:
        block = getattr(feature_config, block_name, None)
        if block is not None and hasattr(block, "timeframes"):
            raw = getattr(block, "timeframes")
        else:
            raw = getattr(feature_config, f"{block_name}_timeframes", None)
    if raw is None:
        return list(default)
    timeframes = [str(value) for value in list(cast(Any, raw))]
    return timeframes or list(default)


def resample_market_pair(
    primary_m1: pd.DataFrame,
    secondary_m1: pd.DataFrame | None,
    timeframe: str,
    primary_timeframes: dict[str, pd.DataFrame] | None = None,
    secondary_timeframes: dict[str, pd.DataFrame] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Select native source bars or resample each instrument's own M1 bars."""
    primary = (primary_timeframes or {}).get(timeframe)
    if primary is None:
        primary = primary_m1 if timeframe == "M1" else resample(primary_m1, cast(TF, timeframe))
    secondary: pd.DataFrame | None = None
    if secondary_m1 is not None:
        secondary = (secondary_timeframes or {}).get(timeframe)
        if secondary is None:
            secondary = (
                secondary_m1 if timeframe == "M1" else resample(secondary_m1, cast(TF, timeframe))
            )
    return primary, secondary


def feature_block_enabled(feature_config: object, block_name: str, default: bool) -> bool:
    """Read the enabled flag from a nested feature block or its flat config key."""
    if feature_config is None:
        return default
    block = getattr(feature_config, block_name, None)
    if block is not None and hasattr(block, "enabled"):
        return bool(getattr(block, "enabled"))
    flat = getattr(feature_config, f"{block_name}_enabled", None)
    return default if flat is None else bool(flat)


def source_timeframe_training_mask(
    source_bars: pd.DataFrame,
    primary_m1: pd.DataFrame,
    train_mask: pd.Series | None,
    timeframe: str,
    scheduled_closes: dict[str, str],
    session_start: str,
) -> pd.Series | None:
    """Map the M1 training cutoff only to completed source-timeframe candles."""
    if train_mask is None:
        return None
    aligned_mask = train_mask.reindex(primary_m1.index).fillna(False).astype(bool)
    train_rows = primary_m1.index[aligned_mask.to_numpy()]
    if len(train_rows) == 0:
        return pd.Series(False, index=source_bars.index, dtype=bool)
    training_end = train_rows.max()
    available_at = timeframe_close_times(source_bars, timeframe, scheduled_closes, session_start)
    return pd.Series(
        pd.DatetimeIndex(available_at).tz_convert(training_end.tz) <= training_end,
        index=source_bars.index,
        dtype=bool,
    )
