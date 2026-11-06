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

    Attributes:
        close_through_threshold (float): How far price must close beyond the FVG zone to confirm IFVG
            (as a fraction of FVG size; 0.1 means 10% beyond the zone).
        inverse_opposing_fvg (bool): When true, a bullish IFVG is a close above an existing bearish FVG;
            a bearish IFVG is a close below an existing bullish FVG. False keeps
            the historical same-orientation confirmation behavior.
        close_through_buffer_enabled (bool): Whether confirmation also requires ``close_through_threshold`` beyond
            the far edge. A later close beyond the passing wick is always required.
    """

    close_through_threshold: float = 0.1
    inverse_opposing_fvg: bool = False
    close_through_buffer_enabled: bool = True

    def __post_init__(self) -> None:
        """Validate and initialize IFVGConfig after construction."""
        if self.close_through_threshold < 0.0:
            raise ValueError("close_through_threshold must be nonnegative")
        if not np.isfinite(self.close_through_threshold):
            raise ValueError("close_through_threshold must be finite")


def _detect_ifvg_confirmation_outputs(
    bars: pd.DataFrame,
    fvg_df: pd.DataFrame,
    config: IFVGConfig | None = None,
    *,
    collect_events: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Detect IFVG (Imbalanced FVG) confirmation.

    An FVG becomes an IFVG after price passes through the zone and a later
    candle closes beyond the most extreme passing wick. An optional fractional
    buffer can require additional distance beyond the far boundary.

    Bullish IFVG confirmation: Price closes above the FVG zone (above bar1_high)
    Bearish IFVG confirmation: Price closes below the FVG zone (below bar1_low)

    Args:
        bars (pd.DataFrame): OHLC DataFrame with 'high', 'low', 'close' columns.
        fvg_df (pd.DataFrame): FVG detection output from detect_fvg().
        config (IFVGConfig, optional): Configuration for IFVG confirmation. Uses defaults if None.
        collect_events: Whether to retain every per-zone confirmation for diagnostics.

    Returns:
        Tuple containing scalar features plus the optional per-zone event ledger.
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
    event_records: list[dict[str, object]] = []

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
                    # Active gaps are kept in source-time order. If several
                    # confirm on one row, the newest matching gap deterministically
                    # supplies the scalar geometry and origin below.
                    confirm_out_bull[i] = 1
                    out_bull_low[i] = gap.low
                    out_bull_high[i] = gap.high
                    origin_bull[i] = float(gap.start)
                    if collect_events:
                        event_records.append(
                            {
                                "confirmation_bar": i,
                                "confirmation_time_ns": pd.Timestamp(df.index[i]).value,
                                "side": "bullish",
                                "source_origin_bar": gap.start,
                                "source_origin_time_ns": pd.Timestamp(df.index[gap.start]).value,
                                "zone_low": gap.low,
                                "zone_high": gap.high,
                                "pass_bar": gap.pass_bar,
                                "pass_time_ns": pd.Timestamp(df.index[gap.pass_bar]).value,
                                "pass_extreme": gap.pass_extreme,
                            }
                        )
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
                    # Preserve the same newest-match selection for bearish gaps.
                    confirm_out_bear[i] = 1
                    out_bear_low[i] = gap.low
                    out_bear_high[i] = gap.high
                    origin_bear[i] = float(gap.start)
                    if collect_events:
                        event_records.append(
                            {
                                "confirmation_bar": i,
                                "confirmation_time_ns": pd.Timestamp(df.index[i]).value,
                                "side": "bearish",
                                "source_origin_bar": gap.start,
                                "source_origin_time_ns": pd.Timestamp(df.index[gap.start]).value,
                                "zone_low": gap.low,
                                "zone_high": gap.high,
                                "pass_bar": gap.pass_bar,
                                "pass_time_ns": pd.Timestamp(df.index[gap.pass_bar]).value,
                                "pass_extreme": gap.pass_extreme,
                            }
                        )
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

    event_columns = [
        "confirmation_bar",
        "confirmation_time_ns",
        "side",
        "source_origin_bar",
        "source_origin_time_ns",
        "zone_low",
        "zone_high",
        "pass_bar",
        "pass_time_ns",
        "pass_extreme",
        "selected_by_scalar",
    ]
    events = pd.DataFrame(event_records)
    if events.empty:
        events = pd.DataFrame(columns=event_columns)
    else:
        events["selected_by_scalar"] = False
        selected_rows = (
            events.groupby(["confirmation_bar", "side"], sort=False, as_index=False).tail(1).index
        )
        events.loc[selected_rows, "selected_by_scalar"] = True
        events = events.loc[:, event_columns]
    return result, events


def detect_ifvg_confirmation(
    bars: pd.DataFrame,
    fvg_df: pd.DataFrame,
    config: IFVGConfig | None = None,
) -> pd.DataFrame:
    """Return the existing scalar newest-confirmation-per-side feature view.

    Args:
        bars: Chronological OHLC bars used to confirm inversion events.
        fvg_df: Fair-value-gap features aligned with ``bars``.
        config: Optional IFVG detection settings.

    Returns:
        Scalar feature frame containing the newest confirmed inversion by side.
    """
    result, _ = _detect_ifvg_confirmation_outputs(
        bars,
        fvg_df,
        config,
        collect_events=False,
    )
    return result


def detect_ifvg_confirmation_events(
    bars: pd.DataFrame,
    fvg_df: pd.DataFrame,
    config: IFVGConfig | None = None,
) -> pd.DataFrame:
    """Return one record per confirmed source gap, including scalar selection.

    The returned ledger is diagnostic. It exposes same-row source zones that
    the model-facing scalar output resolves to the newest matching gap; it
    does not change feature or action semantics.

    Args:
        bars: Chronological OHLC bars used to confirm inversion events.
        fvg_df: Fair-value-gap features aligned with ``bars``.
        config: Optional IFVG detection settings.

    Returns:
        Event ledger with each confirmed source gap and scalar-selection marker.
    """
    if not isinstance(bars.index, pd.DatetimeIndex):
        raise TypeError("IFVG event ledger requires a DatetimeIndex")
    return _detect_ifvg_confirmation_outputs(
        bars,
        fvg_df,
        config,
        collect_events=True,
    )[1]
