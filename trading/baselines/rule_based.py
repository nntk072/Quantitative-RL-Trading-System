"""Rule-based baselines: EMA crossover, MACD, RSI + ATR stops.

Each strategy returns a Series of signals: +1 long, -1 short, 0 flat.
"""

from __future__ import annotations

import pandas as pd

from features.technical.indicators import ema
from features.technical.indicators import macd as _macd
from features.technical.indicators import rsi as _rsi


def _sma(series: pd.Series, period: int) -> pd.Series:
    """Simple moving average.

    Args:
        series: Tabular data used for the series.
        period: Numeric value used for the period.

    Returns:
        Result of simple moving average.
    """
    return series.rolling(window=period).mean()


def ema_crossover(
    bars: pd.DataFrame,
    fast: int = 9,
    slow: int = 21,
    atr_period: int = 14,
    atr_stop_mult: float = 2.0,
) -> pd.Series:
    """Return the directional EMA trend signal aligned to ``bars.index``.

    The ATR arguments remain for call compatibility; they do not change this
    signal. Stop and risk exits are owned by the selected execution engine.

    Args:
        bars: Market bars to process.
        fast: Numeric value used for the fast.
        slow: Numeric value used for the slow.
        atr_period: Legacy compatibility argument; unused by the signal.
        atr_stop_mult: Legacy compatibility argument; unused by the signal.

    Returns:
        ``+1`` for a bullish EMA trend, ``-1`` for a bearish trend, or ``0``
        when the averages are equal.
    """
    close = bars["close"]
    fast_e = ema(close, fast)
    slow_e = ema(close, slow)
    signal = pd.Series(0, index=bars.index, dtype=int)
    signal[fast_e > slow_e] = 1
    signal[fast_e < slow_e] = -1
    return signal


def macd_baseline(bars: pd.DataFrame) -> pd.Series:
    """MACD histogram sign → signal.

    Args:
        bars: Market bars to process.

    Returns:
        Result of mACD histogram sign → signal.
    """
    m = _macd(bars["close"])
    signal = pd.Series(0, index=bars.index, dtype=int)
    signal[m["macd_hist"] > 0] = 1
    signal[m["macd_hist"] < 0] = -1
    return signal


def macd_ema50_baseline(
    bars: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
    ema50_period: int = 50,
    cooldown_bars: int = 5,
) -> pd.Series:
    """MACD+EMA50 baseline with cross-only entry/exit and 5-bar cooldown.

    Rules:
    - Long entry: close > EMA50 AND bullish MACD cross
    - Long exit: bearish MACD cross (go flat)
    - Short entry: close < EMA50 AND bearish MACD cross
    - Short exit: bullish MACD cross (go flat)
    - Cooldown: wait >= 5 bars after any exit before next entry
    - No auto-flip (exit first, then wait for opposite condition to re-enter)

    Action stream is event-based (not per-bar state), so it can be fed
    directly to an engine with ``hold_on_zero=True`` without desyncing:
    - +1: long entry event (bar the position is opened)
    - -1: short entry event (bar the position is opened)
    - 0: hold current position, or flat with no signal
    - 2: explicit exit event (bar the position is closed, go flat)

    Args:
        bars: Market bars to process.
        fast: Numeric value used for the fast.
        slow: Numeric value used for the slow.
        signal_period: Numeric value used for the signal period.
        ema50_period: Numeric value used for the ema50 period.
        cooldown_bars: Market bar or price data used for mACD+EMA50 baseline with cross-only entry/exit and 5-bar cooldown.

    Returns:
        Result of mACD+EMA50 baseline with cross-only entry/exit and 5-bar cooldown.
    """
    close = bars["close"]

    # Compute MACD with SMA(9) signal line (not EMA)
    fast_ema = ema(close, fast)
    slow_ema = ema(close, slow)
    macd_line = fast_ema - slow_ema
    signal_line = _sma(macd_line, signal_period)
    ema50 = ema(close, ema50_period)

    # Detect crosses (causal: t-1 vs t)
    bullish_cross = (macd_line.shift(1) <= signal_line.shift(1)) & (macd_line > signal_line)
    bearish_cross = (macd_line.shift(1) >= signal_line.shift(1)) & (macd_line < signal_line)

    # Initialize action series
    actions = pd.Series(0, index=bars.index, dtype=int)
    position = 0  # 0=flat, 1=long, -1=short
    cooldown_counter = 0

    for i in range(len(bars)):
        # Decrement cooldown
        if cooldown_counter > 0:
            cooldown_counter -= 1

        current_action = 0  # default: hold

        if position == 0:
            # Flat: check for entry
            if cooldown_counter == 0:
                if close.iloc[i] > ema50.iloc[i] and bullish_cross.iloc[i]:
                    # Long entry
                    current_action = 1
                    position = 1
                elif close.iloc[i] < ema50.iloc[i] and bearish_cross.iloc[i]:
                    # Short entry
                    current_action = -1
                    position = -1

        elif position == 1:
            # In long: check for exit
            if bearish_cross.iloc[i]:
                # Exit signal
                current_action = 2
                position = 0
                cooldown_counter = cooldown_bars
            else:
                # Hold long (event-based: no repeated entry action)
                current_action = 0

        elif position == -1:
            # In short: check for exit
            if bullish_cross.iloc[i]:
                # Exit signal
                current_action = 2
                position = 0
                cooldown_counter = cooldown_bars
            else:
                # Hold short (event-based: no repeated entry action)
                current_action = 0

        actions.iloc[i] = current_action

    return actions


def rsi_mean_reversion(
    bars: pd.DataFrame,
    period: int = 14,
    oversold: float = 30.0,
    overbought: float = 70.0,
    atr_period: int = 14,
) -> pd.Series:
    """Return an RSI mean-reversion signal with a neutral-zone exit.

    The ATR argument remains for call compatibility; it does not change this
    signal. Stop and risk exits are owned by the selected execution engine.

    Args:
        bars: Market bars to process.
        period: Numeric value used for the period.
        oversold: Numeric value used for the oversold.
        overbought: Numeric value used for the overbought.
        atr_period: Legacy compatibility argument; unused by the signal.

    Returns:
        A stateful position signal: enter long below ``oversold`` or short
        above ``overbought``; hold that side until RSI enters the 45–55 neutral
        zone, then return to flat. Opposite entries require first becoming flat.
    """
    rsi_s = _rsi(bars["close"], period)
    signals: list[int] = []
    position = 0
    for value in rsi_s:
        if pd.notna(value):
            current_rsi = float(value)
            if position == 0:
                if current_rsi < oversold:
                    position = 1
                elif current_rsi > overbought:
                    position = -1
            elif 45.0 <= current_rsi <= 55.0:
                position = 0
        signals.append(position)
    return pd.Series(signals, index=bars.index, dtype=int)
