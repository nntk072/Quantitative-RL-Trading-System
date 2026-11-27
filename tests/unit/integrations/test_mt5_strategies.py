"""Behavior contracts for broker-neutral MT5 strategy calculations."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest

from integrations.mt5.adapters.data import TradingData

if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        sys.modules["MetaTrader5"] = ModuleType("MetaTrader5")

mt5 = cast(Any, sys.modules["MetaTrader5"])
if not hasattr(mt5, "TIMEFRAME_H1"):
    mt5.TIMEFRAME_H1 = 60

from integrations.mt5.domain.signal import Signal  # noqa: E402
from integrations.mt5.domain.strategies import trend_breakout_strategy as trend_module  # noqa: E402
from integrations.mt5.domain.strategies.combined_strategy import CombinedStrategy  # noqa: E402
from integrations.mt5.domain.strategies.cross_over_strategy import CrossOverStrategy  # noqa: E402
from integrations.mt5.domain.strategies.smc_strategy import SMCStrategy  # noqa: E402
from integrations.mt5.domain.strategies.trend_breakout_strategy import (  # noqa: E402
    TrendBreakoutStrategy,
)


class PriceData(TradingData):
    def __init__(self, frame: pd.DataFrame, symbol: str = "US100") -> None:
        self.frame = frame
        self.symbol = symbol

    def get_data(self) -> pd.DataFrame:
        return self.frame.copy()

    def get_symbol(self) -> str:
        return self.symbol


def _bars(close: list[float]) -> pd.DataFrame:
    values = np.asarray(close, dtype=float)
    return pd.DataFrame(
        {
            "open": values,
            "high": values + 1.0,
            "low": values - 1.0,
            "close": values,
            "tick_volume": np.ones(values.size),
        }
    )


@pytest.mark.parametrize(
    ("prices", "expected"),
    [
        ([1.0] * 50 + [2.0] * 5, Signal.BUY),
        ([2.0] * 50 + [1.0] * 5, Signal.SELL),
    ],
)
def test_crossover_signal_tracks_latest_moving_average_order(
    prices: list[float], expected: Signal
) -> None:
    assert CrossOverStrategy(PriceData(_bars(prices))).signal() == ("US100", expected)


def test_crossover_signal_is_neutral_without_bars() -> None:
    assert CrossOverStrategy(PriceData(pd.DataFrame())).signal() == ("US100", Signal.NONE)


def test_crossover_signal_is_neutral_when_fast_and_slow_averages_match() -> None:
    assert CrossOverStrategy(PriceData(_bars([10.0] * 55))).signal() == ("US100", Signal.NONE)


def test_smc_order_blocks_require_a_strong_candle_followed_by_consolidation() -> None:
    strategy = SMCStrategy(PriceData(pd.DataFrame()), order_block_periods=1)
    frame = pd.DataFrame(
        {
            "open": [10.0, 10.0, 20.0],
            "high": [11.0, 20.0, 21.0],
            "low": [9.0, 10.0, 19.0],
            "close": [10.0, 19.0, 20.0],
        }
    )

    bullish, bearish = strategy.identify_order_blocks(frame)

    assert bullish.iloc[1]
    assert not bearish.any()


@pytest.mark.parametrize(
    ("frame", "bullish_at", "bearish_at"),
    [
        (
            pd.DataFrame({"high": [10.0, 11.0, 13.0], "low": [8.0, 11.0, 12.0]}),
            1,
            None,
        ),
        (
            pd.DataFrame({"high": [13.0, 9.0, 8.0], "low": [10.0, 7.0, 6.0]}),
            None,
            1,
        ),
    ],
)
def test_smc_fair_value_gaps_detect_bullish_and_bearish_separation(
    frame: pd.DataFrame, bullish_at: int | None, bearish_at: int | None
) -> None:
    bullish, bearish = SMCStrategy(PriceData(frame)).identify_fair_value_gaps(frame)

    assert (bullish_at is not None) is bool(bullish.any())
    assert (bearish_at is not None) is bool(bearish.any())
    if bullish_at is not None:
        assert bullish.iloc[bullish_at]
    if bearish_at is not None:
        assert bearish.iloc[bearish_at]


@pytest.mark.parametrize("direction", ["bullish", "bearish"])
def test_smc_market_structure_follows_ordered_highs_and_lows(direction: str) -> None:
    levels: np.ndarray[Any, Any] = np.arange(20, dtype=float)
    if direction == "bearish":
        levels = levels[::-1]
    frame = pd.DataFrame({"high": levels + 1.0, "low": levels})

    assert SMCStrategy(PriceData(frame)).identify_market_structure(frame) == direction


def test_smc_signal_is_neutral_before_its_minimum_history() -> None:
    strategy = SMCStrategy(PriceData(_bars([1.0] * 24)))

    assert strategy.signal() == ("US100", Signal.NONE)


def test_combined_strategy_handles_empty_and_failed_consensus() -> None:
    data = PriceData(_bars([1.0]))
    no_strategies = CombinedStrategy(data, strategies=[])
    assert no_strategies.signal() == ("US100", Signal.NONE)

    combined = CombinedStrategy(data, strategies=[])
    combined.strategies = cast(
        Any,
        {
            "buy_a": SimpleNamespace(signal=lambda: ("other", Signal.BUY)),
            "buy_b": SimpleNamespace(signal=lambda: ("other", Signal.BUY)),
            "sell": SimpleNamespace(signal=lambda: ("other", Signal.SELL)),
        },
    )
    assert combined.signal() == ("US100", Signal.BUY)

    combined.require_all = True
    assert combined.signal() == ("US100", Signal.NONE)


def test_combined_strategy_skips_failed_children() -> None:
    combined = CombinedStrategy(PriceData(_bars([1.0])), strategies=[])
    combined.strategies = cast(
        Any,
        {
            "failed": SimpleNamespace(signal=lambda: (_ for _ in ()).throw(RuntimeError("failed"))),
            "buy": SimpleNamespace(signal=lambda: ("US100", Signal.BUY)),
        },
    )

    assert combined.signal() == ("US100", Signal.BUY)


def test_combined_strategy_builds_defaults_and_resolves_sell_consensus() -> None:
    data = PriceData(_bars([1.0, 2.0]))
    defaults = CombinedStrategy(data)
    assert set(defaults.strategies) == {"crossover", "smc", "trend_breakout"}

    combined = CombinedStrategy(data, strategies=[])
    combined.strategies = cast(
        Any,
        {
            "sell_a": SimpleNamespace(signal=lambda: ("other", Signal.SELL)),
            "sell_b": SimpleNamespace(signal=lambda: ("other", Signal.SELL)),
            "buy": SimpleNamespace(signal=lambda: ("other", Signal.BUY)),
        },
    )
    assert combined.signal() == ("US100", Signal.SELL)
    combined.require_all = True
    assert combined.signal() == ("US100", Signal.NONE)


def test_trend_breakout_limits_short_history_and_confirms_breakouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    strategy = TrendBreakoutStrategy(PriceData(pd.DataFrame()), lookback_period=3)
    short = _bars([1.0, 1.0])
    assert strategy.identify_support_resistance(short) == (0.0, 0.0)
    assert not strategy.identify_consolidation(short)
    assert strategy.calculate_trend_strength(short) == 0.0

    frame = pd.DataFrame({"high": [10.0, 10.0], "low": [9.0, 8.8], "close": [9.5, 9.0]})
    assert strategy.detect_breakout(frame, support=8.5, resistance=10.0) == (False, "")
    frame.loc[1, "high"] = 10.1
    assert strategy.detect_breakout(frame, support=8.5, resistance=10.0) == (True, "bullish")
    frame.loc[1, "high"] = 10.0
    frame.loc[1, "low"] = 8.0
    assert strategy.detect_breakout(frame, support=8.5, resistance=10.0) == (True, "bearish")

    monkeypatch.setattr(
        trend_module,
        "calculate_adx",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad bars")),
    )
    assert strategy.calculate_trend_strength(_bars([float(i + 1) for i in range(27)])) == 0.0


def test_trend_breakout_volume_profile_uses_available_volume_or_price_proxy() -> None:
    strategy = TrendBreakoutStrategy(PriceData(pd.DataFrame()))
    frame = pd.DataFrame({"high": [12.0, 14.0], "low": [8.0, 10.0], "close": [10.0, 12.0]})
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3

    expected_proxy = (typical * typical).cumsum() / typical.cumsum()
    pd.testing.assert_series_equal(strategy.calculate_volume_profile(frame), expected_proxy)
    frame["real_volume"] = [2.0, 1.0]
    expected_real = (typical * frame["real_volume"]).cumsum() / frame["real_volume"].cumsum()
    pd.testing.assert_series_equal(strategy.calculate_volume_profile(frame), expected_real)


def test_trend_breakout_signal_is_neutral_before_minimum_history() -> None:
    strategy = TrendBreakoutStrategy(PriceData(_bars([1.0] * 24)), lookback_period=20)

    assert strategy.signal() == ("US100", Signal.NONE)


def test_trend_breakout_levels_consolidation_and_adx_result_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    strategy = TrendBreakoutStrategy(PriceData(pd.DataFrame()), lookback_period=3)
    frame = pd.DataFrame(
        {
            "high": [10.02, 10.03, 10.01],
            "low": [9.98, 9.99, 9.97],
            "close": [10.0, 10.01, 9.99],
        }
    )

    assert strategy.identify_support_resistance(frame) == (9.97, 10.03)
    assert strategy.identify_consolidation(frame)
    frame.loc[:, "high"] = [12.0, 13.0, 14.0]
    assert not strategy.identify_consolidation(frame)

    monkeypatch.setattr(
        trend_module, "calculate_adx", lambda *_args, **_kwargs: pd.DataFrame({"adx": [31.0]})
    )
    assert strategy.calculate_trend_strength(_bars([float(i + 1) for i in range(27)])) == 31.0
    monkeypatch.setattr(
        trend_module, "calculate_adx", lambda *_args, **_kwargs: pd.DataFrame({"adx": [np.nan]})
    )
    assert strategy.calculate_trend_strength(_bars([float(i + 1) for i in range(27)])) == 0.0


@pytest.mark.parametrize(
    ("close", "expected"),
    [
        ([float(value) for value in range(76, 101)], Signal.BUY),
        ([float(value) for value in range(124, 99, -1)], Signal.SELL),
    ],
)
def test_trend_breakout_signal_can_confirm_nearby_trend_continuation(
    monkeypatch: pytest.MonkeyPatch, close: list[float], expected: Signal
) -> None:
    values = np.asarray(close, dtype=float)
    if expected is Signal.BUY:
        low: np.ndarray[Any, Any] = np.full(values.size, values[-1] - 0.2)
        high: np.ndarray[Any, Any] = values + 0.1
    else:
        high = np.full(values.size, values[-1] + 0.2)
        low = values - 0.1
    frame = pd.DataFrame(
        {
            "open": values,
            "high": high,
            "low": low,
            "close": values,
            "tick_volume": np.ones(values.size),
        }
    )
    strategy = TrendBreakoutStrategy(PriceData(frame), lookback_period=20)
    monkeypatch.setattr(strategy, "detect_breakout", lambda *_args: (False, ""))
    monkeypatch.setattr(strategy, "calculate_trend_strength", lambda _frame: 40.0)

    assert strategy.signal() == ("US100", expected)
