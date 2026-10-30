from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class _ActiveFVG:
    start: int
    low: float
    high: float
    pass_extreme: float | None = None
    pass_bar: int = -1


@dataclass
class IFVGConfig:
    """Configuration for IFVG confirmation.

    Attributes
    ----------
    close_through_threshold : float
        How far price must close beyond the FVG zone to confirm IFVG
        (as a fraction of FVG size; 0.1 means 10% beyond the zone).
    inverse_opposing_fvg : bool
        When true, a bullish IFVG is a close above an existing bearish FVG;
        a bearish IFVG is a close below an existing bullish FVG. False keeps
        the historical same-orientation confirmation behavior.
    close_through_buffer_enabled : bool
        Whether confirmation also requires ``close_through_threshold`` beyond
        the far edge. A later close beyond the passing wick is always required.
    """

    close_through_threshold: float = 0.1
    inverse_opposing_fvg: bool = False
    close_through_buffer_enabled: bool = True

    def __post_init__(self) -> None:
        if self.close_through_threshold < 0.0:
            raise ValueError("close_through_threshold must be nonnegative")
        if not np.isfinite(self.close_through_threshold):
            raise ValueError("close_through_threshold must be finite")


def detect_ifvg_confirmation(
    bars: pd.DataFrame,
    fvg_df: pd.DataFrame,
    config: IFVGConfig | None = None,
) -> pd.DataFrame:
    """Detect IFVG (Imbalanced FVG) confirmation.

    An FVG becomes an IFVG after price passes through the zone and a later
    candle closes beyond the most extreme passing wick. An optional fractional
    buffer can require additional distance beyond the far boundary.

    Bullish IFVG confirmation: Price closes above the FVG zone (above bar1_high)
    Bearish IFVG confirmation: Price closes below the FVG zone (below bar1_low)

    Parameters
    ----------
    bars : pd.DataFrame
        OHLC DataFrame with 'high', 'low', 'close' columns.
    fvg_df : pd.DataFrame
        FVG detection output from detect_fvg().
    config : IFVGConfig, optional
        Configuration for IFVG confirmation. Uses defaults if None.

    Returns
    -------
    pd.DataFrame
        DataFrame with same index, containing:
        - ifvg_bullish_confirmed: 1 if bullish IFVG confirmed at this bar
        - ifvg_bearish_confirmed: 1 if bearish IFVG confirmed at this bar
        - ifvg_bullish_low: Low price of the IFVG zone (for bullish)
        - ifvg_bullish_high: High price of the IFVG zone (for bullish)
        - ifvg_bearish_low: Low price of the IFVG zone (for bearish)
        - ifvg_bearish_high: High price of the IFVG zone (for bearish)
    """
    if config is None:
        config = IFVGConfig()

    df = bars.copy()
    n = len(df)

    # Track active FVG zones
    active_fvg_bullish: list[_ActiveFVG] = []
    active_fvg_bearish: list[_ActiveFVG] = []

    # Pre-extract numpy arrays once: scalar access inside the loop via
    # pandas .iloc is ~10x slower than ndarray indexing over 100k+ bars.
    high_arr = df["high"].to_numpy(dtype=float)
    low_arr = df["low"].to_numpy(dtype=float)
    close_arr = df["close"].to_numpy(dtype=float)
    bull_flag = fvg_df["fvg_bullish"].to_numpy(dtype=int)
    bear_flag = fvg_df["fvg_bearish"].to_numpy(dtype=int)
    bull_low_arr = fvg_df["fvg_bullish_low"].to_numpy(dtype=float)
    bull_high_arr = fvg_df["fvg_bullish_high"].to_numpy(dtype=float)
    bear_low_arr = fvg_df["fvg_bearish_low"].to_numpy(dtype=float)
    bear_high_arr = fvg_df["fvg_bearish_high"].to_numpy(dtype=float)

    confirm_out_bull = np.zeros(n, dtype=int)
    confirm_out_bear = np.zeros(n, dtype=int)
    out_bull_low = np.full(n, np.nan)
    out_bull_high = np.full(n, np.nan)
    out_bear_low = np.full(n, np.nan)
    out_bear_high = np.full(n, np.nan)
    origin_bull = np.full(n, np.nan)
    origin_bear = np.full(n, np.nan)

    threshold = config.close_through_threshold if config.close_through_buffer_enabled else 0.0
    max_age = 50  # bars; zones older than this are dropped

    for i in range(n):
        # Check for new FVGs
        if i < len(fvg_df):
            if bull_flag[i] == 1 and i >= 2:
                active_fvg_bullish.append(_ActiveFVG(i, bull_low_arr[i], bull_high_arr[i]))
            if bear_flag[i] == 1 and i >= 2:
                active_fvg_bearish.append(_ActiveFVG(i, bear_low_arr[i], bear_high_arr[i]))

                # Check for IFVG confirmation (close-through)
        close_price = close_arr[i]

        # Revised mode inverts an opposing-direction gap. The false branch
        # retains the pre-Idea same-orientation behavior for reproduction.
        bullish_sources = active_fvg_bearish if config.inverse_opposing_fvg else active_fvg_bullish
        bearish_sources = active_fvg_bullish if config.inverse_opposing_fvg else active_fvg_bearish
        for gap in bullish_sources[:]:
            fvg_size = gap.high - gap.low
            if fvg_size > 0:
                close_through_pct = (close_price - gap.high) / fvg_size
                if (
                    gap.pass_bar >= 0
                    and i > gap.pass_bar
                    and close_price > gap.high + fvg_size * threshold
                    and gap.pass_extreme is not None
                    and close_price > gap.pass_extreme
                    and close_through_pct >= threshold
                ):
                    confirm_out_bull[i] = 1
                    out_bull_low[i] = gap.low
                    out_bull_high[i] = gap.high
                    origin_bull[i] = float(gap.start)
                    bullish_sources.remove(gap)
                    continue
                passed_zone = high_arr[i] >= gap.low and low_arr[i] <= gap.high
                if passed_zone:
                    gap.pass_extreme = (
                        high_arr[i]
                        if gap.pass_extreme is None
                        else max(gap.pass_extreme, high_arr[i])
                    )
                    gap.pass_bar = i

        for gap in bearish_sources[:]:
            fvg_size = gap.high - gap.low
            if fvg_size > 0:
                close_through_pct = (gap.low - close_price) / fvg_size
                if (
                    gap.pass_bar >= 0
                    and i > gap.pass_bar
                    and close_price < gap.low - fvg_size * threshold
                    and gap.pass_extreme is not None
                    and close_price < gap.pass_extreme
                    and close_through_pct >= threshold
                ):
                    confirm_out_bear[i] = 1
                    out_bear_low[i] = gap.low
                    out_bear_high[i] = gap.high
                    origin_bear[i] = float(gap.start)
                    bearish_sources.remove(gap)
                    continue
                passed_zone = high_arr[i] >= gap.low and low_arr[i] <= gap.high
                if passed_zone:
                    gap.pass_extreme = (
                        low_arr[i]
                        if gap.pass_extreme is None
                        else min(gap.pass_extreme, low_arr[i])
                    )
                    gap.pass_bar = i

                    # Remove old FVGs (older than lookback period)
        active_fvg_bullish = [gap for gap in active_fvg_bullish if i - gap.start < max_age]
        active_fvg_bearish = [gap for gap in active_fvg_bearish if i - gap.start < max_age]

    result = pd.DataFrame(
        {
            "ifvg_bullish_confirmed": confirm_out_bull,
            "ifvg_bearish_confirmed": confirm_out_bear,
            "ifvg_bullish_low": out_bull_low,
            "ifvg_bullish_high": out_bull_high,
            "ifvg_bearish_low": out_bear_low,
            "ifvg_bearish_high": out_bear_high,
            "ifvg_bullish_origin_bar": origin_bull,
            "ifvg_bearish_origin_bar": origin_bear,
        },
        index=df.index,
    )

    return result
