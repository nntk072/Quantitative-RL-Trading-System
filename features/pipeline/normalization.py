"""Rolling train-only z-score normalisation (no data leakage).

The scaler is fit only on training bars (mask=True) and applied to all bars.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

ROLLING_ZSCORE_STATE_SCHEMA = "rolling-zscore-fit-v1"


def _aligned_training_mask(df: pd.DataFrame, train_mask: pd.Series[Any]) -> pd.Series[Any]:
    """Validate and align a boolean fit mask to the feature rows.

    Args:
        df: Feature rows whose index defines the required mask coverage.
        train_mask: Boolean selector identifying rows allowed to fit statistics.

    Returns:
        Boolean mask aligned exactly to the feature index.
    """
    if not df.index.is_unique or not train_mask.index.is_unique:
        raise ValueError("normalization fit requires unique row indexes")
    if not pd.api.types.is_bool_dtype(train_mask.dtype):
        raise ValueError("normalization fit mask must have boolean dtype")
    aligned = train_mask.reindex(df.index)
    if aligned.isna().any():
        raise ValueError("normalization fit mask must cover every feature row")
    aligned = aligned.astype(bool)
    if not bool(aligned.any()):
        raise ValueError("normalization fit requires nonempty training observations")
    return aligned


def fit_rolling_zscore_state(
    df: pd.DataFrame,
    *,
    train_mask: pd.Series,
    window: int = 252,
    mode: str = "legacy_masked_window",
) -> dict[str, Any]:
    """Capture the final train-only rolling statistics for inference.

    The returned state is the exact mean and standard deviation available at
    the last training row under ``rolling_zscore``. Validation and live inputs
    must apply these constants; they must not refit from their own bars.

    Args:
        df: Feature values used to fit the normalization statistics.
        train_mask: Boolean selector identifying training rows.
        window: Number of training observations in each rolling statistic.
        mode: Historical masked-window or frozen-fold fit semantics.

    Returns:
        Serializable schema-versioned fit state with final means and scales.
    """
    if mode not in {"legacy_masked_window", "frozen_fold"}:
        raise ValueError(f"Unknown normalization mode: {mode}")
    if isinstance(window, bool) or int(window) != window or int(window) <= 0:
        raise ValueError("normalization window must be a positive integer")
    if not df.columns.is_unique:
        raise ValueError("normalization fit requires unique feature columns")
    if len({str(column) for column in df.columns}) != len(df.columns):
        raise ValueError("normalization fit requires unique string feature names")
    mask = _aligned_training_mask(df, train_mask)
    if mode == "frozen_fold":
        train_df = df.loc[mask]
        means = train_df.rolling(int(window), min_periods=1).mean()
        scales = train_df.rolling(int(window), min_periods=2).std(ddof=0)
    else:
        train_df = df.where(mask)
        means = train_df.rolling(int(window), min_periods=1).mean().ffill()
        scales = train_df.rolling(int(window), min_periods=2).std(ddof=0).ffill()
    last_train_index = df.index[np.flatnonzero(mask.to_numpy())[-1]]
    mean_row = means.loc[last_train_index]
    scale_row = scales.loc[last_train_index].mask(scales.loc[last_train_index].eq(0.0), 1.0)

    def finite_or_none(value: Any) -> float | None:
        """Serialize a finite fitted statistic, using null otherwise.

        Args:
            value: Fitted statistic to convert.

        Returns:
            Finite float, or ``None`` for a non-finite statistic.
        """
        number = float(value)
        return number if math.isfinite(number) else None

    return {
        "schema": ROLLING_ZSCORE_STATE_SCHEMA,
        "mode": mode,
        "window": int(window),
        "columns": [str(column) for column in df.columns],
        "as_of": str(last_train_index),
        "mean": {str(column): finite_or_none(mean_row[column]) for column in df.columns},
        "scale": {str(column): finite_or_none(scale_row[column]) for column in df.columns},
    }


def apply_rolling_zscore_state(df: pd.DataFrame, state: dict[str, Any]) -> pd.DataFrame:
    """Apply a serialized train-only fit state without refitting on ``df``.

    Args:
        df: Feature rows to transform using the saved fit state.
        state: Serialized normalization state captured from training data.

    Returns:
        Normalized frame with the same rows and columns as ``df``.
    """
    if state.get("schema") != ROLLING_ZSCORE_STATE_SCHEMA:
        raise ValueError("unsupported feature normalization fit-state schema")
    if state.get("mode") not in {"legacy_masked_window", "frozen_fold"}:
        raise ValueError("feature normalization fit state has an unsupported mode")
    window = state.get("window")
    if isinstance(window, bool) or not isinstance(window, int) or window <= 0:
        raise ValueError("feature normalization fit state has an invalid window")
    columns = [str(column) for column in df.columns]
    if state.get("columns") != columns:
        raise ValueError("feature normalization columns differ from the fitted state")
    means = state.get("mean")
    scales = state.get("scale")
    if not isinstance(means, dict) or not isinstance(scales, dict):
        raise ValueError("feature normalization fit state requires mean and scale mappings")
    if set(means) != set(columns) or set(scales) != set(columns):
        raise ValueError("feature normalization fit-state statistics do not match its columns")
    mean_values: dict[str, float] = {}
    scale_values: dict[str, float] = {}
    for column in columns:
        mean = means.get(column)
        scale = scales.get(column)
        if (mean is None) != (scale is None):
            raise ValueError(f"incomplete feature normalization statistics for {column!r}")
        if mean is None or scale is None:
            mean_values[column] = float("nan")
            scale_values[column] = float("nan")
            continue
        mean_float = float(mean)
        scale_float = float(scale)
        if not math.isfinite(mean_float) or not math.isfinite(scale_float) or scale_float <= 0.0:
            raise ValueError(f"invalid feature normalization statistics for {column!r}")
        mean_values[column] = mean_float
        scale_values[column] = scale_float
    mean_series = pd.Series(
        [mean_values[str(column)] for column in df.columns], index=df.columns, dtype=np.float64
    )
    scale_series = pd.Series(
        [scale_values[str(column)] for column in df.columns], index=df.columns, dtype=np.float64
    )
    return (df - mean_series) / scale_series


def rolling_zscore(
    df: pd.DataFrame,
    window: int = 252,
    train_mask: pd.Series | None = None,
    mode: str = "legacy_masked_window",
) -> pd.DataFrame:
    """Apply a rolling z-score to each column.

    Args:
        df: Feature DataFrame.
        window: Look-back window for mean/std (bars).
        train_mask: Boolean Series; if provided, statistics are computed only from rows
            where mask=True (the training fold).  Test rows are normalised using
            the last known training statistics.
        mode: ``legacy_masked_window`` keeps calendar-row rolling statistics on
            training observations and carries the last fitted statistics through
            held-out rows. ``frozen_fold`` computes rolling statistics across
            training observations and forward-fills the final fitted mean/std
            throughout validation, without validation input.

    Returns:
        Normalised DataFrame (same shape as input).:
    """
    if mode not in {"legacy_masked_window", "frozen_fold"}:
        raise ValueError(f"Unknown normalization mode: {mode}")
    if mode == "frozen_fold":
        if train_mask is None:
            raise ValueError("frozen_fold normalization requires a training mask")
        mask = _aligned_training_mask(df, train_mask)
        train_df = df.loc[mask]
        # Statistics are computed on the training fold alone, then projected
        # causally onto the full index.  No validation sample can change the fit.
        mu = train_df.rolling(window, min_periods=1).mean().reindex(df.index).ffill()
        sigma = train_df.rolling(window, min_periods=2).std(ddof=0).reindex(df.index).ffill()
    elif train_mask is not None:
        # Forward-fill stats computed from training rows only. Validate the
        # mask here too so misaligned or non-boolean inputs cannot silently
        # change which rows fit the production scaler.
        mask = _aligned_training_mask(df, train_mask)
        train_df = df.where(mask)
        mu = train_df.rolling(window, min_periods=1).mean().where(mask).ffill()
        sigma = train_df.rolling(window, min_periods=2).std(ddof=0).where(mask).ffill()
    else:
        mu = df.rolling(window, min_periods=1).mean()
        sigma = df.rolling(window, min_periods=2).std(ddof=0)

    # A constant fitted window has a defined centered value: finite inputs map
    # to zero. Keep NaN standard deviations missing; they indicate unavailable
    # fit statistics rather than a zero-variance window.
    sigma = sigma.mask(sigma.eq(0.0), 1.0)
    return (df - mu) / sigma
