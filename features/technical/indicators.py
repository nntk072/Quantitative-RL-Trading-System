"""Causal technical indicators computed on bar DataFrames.

All indicators are strictly causal: at index t only rows ≤ t are used.
No pandas-ta / ta-lib dependency – pure pandas/numpy for portability.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def ema(s: pd.Series, span: int) -> pd.Series:
    """Compute a causal exponentially weighted moving average.

    Args:
        s: Input price or indicator series.
        span: Exponential weighting span in bars.

    Returns:
        The moving average aligned to the input index.
    """
    return s.ewm(span=span, adjust=False).mean()


def _true_range(df: pd.DataFrame) -> pd.Series:
    """Calculate each bar's true range against the previous close.

    Args:
        df: Bars containing ``high``, ``low``, and ``close`` columns.

    Returns:
        True-range values aligned to the input index.
    """
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Compute relative strength from exponentially smoothed gains and losses.

    Args:
        close: Closing prices in chronological order.
        period: Number of bars used to smooth gains and losses.

    Returns:
        RSI values aligned to the closing-price index.
    """
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """Compute the MACD line, signal line, and histogram.

    Args:
        close: Closing prices in chronological order.
        fast: Span for the fast exponential average.
        slow: Span for the slow exponential average.
        signal: Span for smoothing the MACD line.

    Returns:
        A frame containing ``macd``, ``macd_signal``, and ``macd_hist``.
    """
    fast_ema = ema(close, fast)
    slow_ema = ema(close, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return pd.DataFrame(
        {"macd": macd_line, "macd_signal": signal_line, "macd_hist": histogram},
        index=close.index,
    )


def ema_features(close: pd.Series, periods: list[int]) -> pd.DataFrame:
    """Build EMA, one-bar slope, and normalized-distance features.

    Args:
        close: Closing prices in chronological order.
        periods: EMA spans to calculate; each span becomes three columns.

    Returns:
        Frame with ``ema_{period}``, ``ema_{period}_slope``, and
        ``ema_{period}_dist`` columns for each requested span.
    """
    out: dict[str, pd.Series] = {}
    for p in periods:
        e = ema(close, p)
        out[f"ema_{p}"] = e
        out[f"ema_{p}_slope"] = e.diff()
        out[f"ema_{p}_dist"] = (close - e) / e.replace(0, np.nan)
    return pd.DataFrame(out, index=close.index)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate the exponentially smoothed average true range.

    Args:
        df: OHLC data with high, low, and close columns.
        period: Smoothing period used for the true range.

    Returns:
        A series named atr aligned to the input index.
    """
    tr = _true_range(df)
    return tr.ewm(alpha=1 / period, adjust=False).mean().rename("atr")


def volume_spike(volume: pd.Series, window: int = 20) -> pd.Series:
    """Compute volume spike as ratio to rolling median.

    Args:
        volume: Volume observations in chronological order.
        window: Number of observations in the rolling median.

    Returns:
        Volume divided by its rolling median, aligned to the input index.
        Positions with a zero median are ``NaN``.
    """
    median_vol = volume.rolling(window, min_periods=1).median()
    return volume / median_vol.replace(0, np.nan)


def adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Compute Wilder ADX and directional indicators with causal warmup.

    Args:
        df: OHLC bars with high, low, and close columns.
        period: Wilder smoothing period for directional movement.

    Returns:
        A frame containing ``adx``, ``plus_di``, and ``minus_di``.
    """
    if period < 1:
        raise ValueError("period must be positive")

    length = len(df)
    tr = _true_range(df).copy()
    tr.iloc[0:1] = np.nan
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)

    def smooth(values: pd.Series) -> pd.Series:
        """Apply Wilder smoothing after a period-length seed.

        Args:
            values: Input directional-movement or true-range series.

        Returns:
            Wilder-smoothed values aligned to the input index.
        """
        result = values.astype(float).copy()
        result.iloc[:period] = np.nan
        if length > period:
            seed = values.iloc[1:period].sum()
            result.iloc[period] = (seed - seed / period + values.iloc[period]) / period
        return result.ewm(alpha=1 / period, adjust=False, ignore_na=True).mean()

    smooth_tr = smooth(tr)
    smooth_plus = smooth(plus_dm)
    smooth_minus = smooth(minus_dm)
    plus_di = (100 * smooth_plus / smooth_tr).where(smooth_tr != 0, 0.0)
    minus_di = (100 * smooth_minus / smooth_tr).where(smooth_tr != 0, 0.0)
    directional_sum = plus_di + minus_di
    dx = (100 * (plus_di - minus_di).abs() / directional_sum).where(directional_sum != 0, 0.0)
    first_adx = 2 * period - 1
    adx_seed = dx.copy()
    adx_seed.iloc[:first_adx] = np.nan
    if length > first_adx:
        adx_seed.iloc[first_adx] = dx.iloc[period : first_adx + 1].mean()
    adx_values = adx_seed.ewm(alpha=1 / period, adjust=False, ignore_na=True).mean()

    return pd.DataFrame(
        {
            "adx": adx_values,
            "plus_di": plus_di,
            "minus_di": minus_di,
        },
        index=df.index,
    )


def bollinger(close: pd.Series, period: int = 20, std_mult: float = 2.0) -> pd.DataFrame:
    """Compute Bollinger percent-B, normalized band width, and midpoint.

    Args:
        close: Closing prices in chronological order.
        period: Rolling window used for the midpoint and standard deviation.
        std_mult: Number of standard deviations on each side of the midpoint.

    Returns:
        A frame containing ``bb_pct_b``, ``bb_width``, and ``bb_mid``.
    """
    mid = close.rolling(period).mean()
    std = close.rolling(period).std(ddof=0)
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    pct_b = (close - lower) / (upper - lower).replace(0, np.nan)
    width = (upper - lower) / mid.replace(0, np.nan)
    return pd.DataFrame(
        {"bb_pct_b": pct_b, "bb_width": width, "bb_mid": mid},
        index=close.index,
    )


def stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
    """Compute the rolling stochastic K and smoothed D lines.

    Args:
        df: OHLC bars with high, low, and close columns.
        k_period: Window used to find the rolling high and low.
        d_period: Window used to smooth the K line.

    Returns:
        A frame containing ``stoch_k`` and ``stoch_d``.
    """
    low_k = df["low"].rolling(k_period).min()
    high_k = df["high"].rolling(k_period).max()
    stoch_k = 100 * (df["close"] - low_k) / (high_k - low_k).replace(0, np.nan)
    stoch_d = stoch_k.rolling(d_period).mean()
    return pd.DataFrame({"stoch_k": stoch_k, "stoch_d": stoch_d}, index=df.index)


def vwap_level(df: pd.DataFrame) -> pd.Series:
    """Tick-count session VWAP (resets per ``session_id``).

    Weights typical price by :func:`~market_data.transforms.activity.activity_series`
    (MT5 tick count). This is not exchange volume; CFD ``<VOL>`` is unused.

    Args:
        df: Input DataFrame supplying the rows used by this calculation.

    Returns:
        Result of tick-count session VWAP (resets per ``session_id``).
    """
    from market_data.transforms.activity import activity_series

    if "session_id" not in df.columns:
        raise ValueError("DataFrame must have 'session_id' column (see data.session)")
    act = activity_series(df)
    if act is None:
        raise ValueError("DataFrame needs tickvol/tick_count activity for VWAP")
    typical = (df["high"] + df["low"] + df["close"]) / 3
    vol = act.reindex(df.index).replace(0, np.nan)
    tp_vol = typical * vol
    cum_tp_vol = tp_vol.groupby(df["session_id"]).cumsum()
    cum_vol = vol.groupby(df["session_id"]).cumsum()
    vwap = cum_tp_vol / cum_vol
    vwap.name = "vwap"
    return vwap


def vwap_from_session(df: pd.DataFrame) -> pd.Series:
    """Normalized (close - vwap) / vwap distance using ``session_id``.

    Args:
        df: Input DataFrame supplying the rows used by this calculation.

    Returns:
        Result of normalized (close - vwap) / vwap distance using ``session_id``.
    """
    vwap = vwap_level(df)
    dist = (df["close"] - vwap) / vwap.replace(0, np.nan)
    return dist.rename("vwap_dist")


def returns(close: pd.Series, horizons: list[int]) -> pd.DataFrame:
    """Log returns at multiple horizons.

    Args:
        close: Tabular data used for the close.
        horizons: Items supplied for the horizons, in input order.

    Returns:
        DataFrame returned by ``returns``.
    """
    log_c = np.log(close.replace(0, np.nan))
    out = {}
    for h in horizons:
        out[f"ret_{h}"] = log_c.diff(h)
    return pd.DataFrame(out, index=close.index)


def realized_vol(close: pd.Series, period: int = 20) -> pd.Series:
    """Compute rolling population volatility of log returns.

    Args:
        close: Closing prices in chronological order.
        period: Rolling window used to estimate return volatility.

    Returns:
        Realized volatility values aligned to the closing-price index.
    """
    lr = np.log(close.replace(0, np.nan)).diff()
    vol = lr.rolling(period).std(ddof=0)
    vol.name = "realized_vol"
    return pd.Series(vol, index=close.index, name="realized_vol")


def ny_session_clock(
    index: pd.DatetimeIndex,
    start: str = "16:30",
    end: str = "23:00",
) -> pd.DataFrame:
    """NY-session sin/cos and minutes-to-close, clipped to the session.

    ``session_duration`` is ``end - start`` in minutes. Bars outside the
    session clip onto the endpoints, so the sin/cos stay in ``[-1, 1]`` and
    minutes-to-close stays in ``[0, 1]``. These columns are concatenated
    after the z-score and must not be rescaled.

    Args:
        index: Position or label identifying the requested item.
        start: Text or path value identifying the start.
        end: Text or path value identifying the end.

    Returns:
        DataFrame returned by ``ny_session_clock``.
    """
    start_h, start_m = (int(part) for part in start.split(":"))
    end_h, end_m = (int(part) for part in end.split(":"))
    start_min = start_h * 60 + start_m
    end_min = end_h * 60 + end_m
    duration = end_min - start_min
    if duration <= 0:
        duration += 24 * 60
    minute_of_day = np.asarray(index.hour * 60 + index.minute, dtype=float)
    minute_idx = minute_of_day - start_min
    if end_min <= start_min:
        minute_idx = np.where(minute_of_day < start_min, minute_idx + 24 * 60, minute_idx)
    minute_idx = np.clip(minute_idx, 0.0, float(duration))
    angle = 2.0 * np.pi * minute_idx / float(duration)
    return pd.DataFrame(
        {
            "ny_session_sin": np.sin(angle),
            "ny_session_cos": np.cos(angle),
            "ny_minutes_to_close": (float(duration) - minute_idx) / float(duration),
        },
        index=index,
    )


def time_features(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Cyclical sin/cos encoding of time-of-day and day-of-week.

    Args:
        index: Position or label identifying the requested item.

    Returns:
        DataFrame returned by ``time_features``.
    """
    hour_min = index.hour + index.minute / 60.0
    tod_sin = np.sin(2 * np.pi * hour_min / 24.0)
    tod_cos = np.cos(2 * np.pi * hour_min / 24.0)
    dow_sin = np.sin(2 * np.pi * index.dayofweek / 7.0)
    dow_cos = np.cos(2 * np.pi * index.dayofweek / 7.0)
    return pd.DataFrame(
        {"tod_sin": tod_sin, "tod_cos": tod_cos, "dow_sin": dow_sin, "dow_cos": dow_cos},
        index=index,
    )


def atr_normalized_price(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Close distance from previous close, normalised by ATR.

    Args:
        df: Input DataFrame supplying the rows used by this calculation.
        period: Numeric value used for the period.

    Returns:
        Result of close distance from previous close, normalised by ATR.
    """
    atr_s = atr(df, period)
    return df["close"].diff() / atr_s.replace(0, np.nan)


def sweep_velocity(
    df: pd.DataFrame,
    london_high: pd.Series | None = None,
    london_low: pd.Series | None = None,
    asian_high: pd.Series | None = None,
    asian_low: pd.Series | None = None,
    atr_period: int = 5,
) -> pd.DataFrame:
    """Compute bullish and bearish sweep velocity.

    Bullish Sweep Velocity: (Close - LondonHigh) / ATR_5
    Bearish Sweep Velocity: (LondonLow - Close) / ATR_5

    Args:
        df (pd.DataFrame): OHLCV DataFrame
        london_high (pd.Series or None): London session high (will be computed from df if None)
        london_low (pd.Series or None): London session low (will be computed from df if None)
        asian_high (pd.Series or None): Asian session high (will be computed from df if None)
        asian_low (pd.Series or None): Asian session low (will be computed from df if None)
        atr_period (int): ATR period for normalization (default: 5)

    Returns:
        pd.DataFrame: DataFrame with columns: sweep_velocity_bullish, sweep_velocity_bearish
    """
    close = df["close"]
    atr_val = atr(df, atr_period)

    if london_high is None:
        london_high = df.get("london_high", pd.Series(dtype=float))
    if london_low is None:
        london_low = df.get("london_low", pd.Series(dtype=float))

    bullish_velocity = (close - london_high) / atr_val.replace(0, np.nan)
    bearish_velocity = (london_low - close) / atr_val.replace(0, np.nan)

    return pd.DataFrame(
        {
            "sweep_velocity_bullish": bullish_velocity,
            "sweep_velocity_bearish": bearish_velocity,
        },
        index=df.index,
    )


def wick_ratio(df: pd.DataFrame) -> pd.Series:
    """Compute wick ratio as ``abs(High - max(Open, Close)) / (High - Low)``.

    High values indicate rejection (false sweep).
    A zero-range candle has no upper wick and maps to a finite ratio of zero;
    other invalid OHLC inputs remain non-finite.

    Args:
        df (pd.DataFrame): OHLCV DataFrame

    Returns:
        pd.Series: Wick ratio values
    """
    high = df["high"]
    low = df["low"]
    open_ = df["open"]
    close = df["close"]

    max_oc = pd.concat([open_, close], axis=1).max(axis=1)

    wick = (high - max_oc).abs()

    range_ = high - low

    wick_ratio = wick / range_.where(range_ != 0)
    wick_ratio = wick_ratio.mask(range_ == 0, 0.0)
    wick_ratio.name = "wick_ratio"

    return wick_ratio


def build_indicators(df: pd.DataFrame, cfg: Any) -> pd.DataFrame:
    """Compute all indicators and return a wide feature DataFrame.

    Args:
        df: Cleaned, session-filtered M1 bars with a timezone-aware index.
        cfg: OmegaConf ``features`` sub-config.

    Returns:
        A DataFrame containing the configured causal technical features.
    """
    close = df["close"]
    parts: list[pd.DataFrame | pd.Series] = []

    parts.append(ema_features(close, list(cfg.ema_periods)))
    parts.append(macd(close, cfg.macd_fast, cfg.macd_slow, cfg.macd_signal))
    parts.append(rsi(close, cfg.rsi_period).rename("rsi"))
    parts.append(atr(df, cfg.atr_period))
    parts.append(adx(df, cfg.adx_period))
    parts.append(bollinger(close, cfg.bb_period, cfg.bb_std))
    parts.append(stochastic(df, cfg.stoch_k, cfg.stoch_d))
    # Session VWAP weights typical price by tick-count activity.
    if bool(getattr(cfg, "vwap_session", False)) and "session_id" in df.columns:
        parts.append(vwap_from_session(df))
    parts.append(returns(close, list(cfg.return_horizons)))
    parts.append(realized_vol(close, cfg.realized_vol_period))
    parts.append(time_features(pd.DatetimeIndex(df.index)))
    parts.append(atr_normalized_price(df, cfg.atr_period).rename("atr_norm_price"))

    feat = pd.concat([p for p in parts], axis=1)
    return feat
