"""Build higher-timeframe bars from one-minute market data."""

from __future__ import annotations

from typing import Any, Literal, cast

import pandas as pd

TF = Literal["M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1"]

_TF_TO_RULE: dict[TF, str] = {
    "M1": "1min",
    "M3": "3min",
    "M5": "5min",
    "M10": "10min",
    "M15": "15min",
    "M30": "30min",
    "H1": "1h",
    "H4": "4h",
    "D1": "1D",
}

_OHLCV_AGG = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "tickvol": "sum",
    "vol": "sum",
    "volume": "sum",  # alias used by VAE pre-NY builder after tickvol→volume
    "spread": "mean",
}


def resample(m1: pd.DataFrame, tf: TF) -> pd.DataFrame:
    """Return *tf* bars built from *m1* (1-minute) bars.

    D1 uses pandas ``1D`` with left labels / left closes, so daily bars align
    to broker midnight of ``m1``'s timezone (typically ``Etc/GMT-3``), not
    UTC midnight and not NY close.

    Args:
        m1: DataFrame produced by :func:`market_data.loading.bars.load_bars`
            with a DatetimeIndex.
        tf: Target timeframe string.

    Returns:
        Bars aggregated to ``tf``. Requesting ``M1`` returns a copy of the
        input data.
    """
    if tf == "M1":
        return m1.copy()
    rule = _TF_TO_RULE[tf]
    agg_spec = {k: v for k, v in _OHLCV_AGG.items() if k in m1.columns}
    resampled = m1.resample(rule, label="left", closed="left").agg(cast(Any, agg_spec))
    resampled = resampled.dropna(subset=["open"])
    return resampled


def build_all_timeframes(m1: pd.DataFrame) -> dict[TF, pd.DataFrame]:
    """Build all standard timeframes from M1 data.

    Args:
        m1: One-minute bars with a :class:`~pandas.DatetimeIndex`.

    Returns:
        Mapping from each supported timeframe to its resampled bars. The
        ``M1`` entry is a copy of the input data.
    """
    return {tf: resample(m1, tf) for tf in _TF_TO_RULE}
