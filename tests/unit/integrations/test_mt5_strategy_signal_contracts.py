"""End-to-end signal confirmation contracts for MT5 trend and SMC strategies."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest

if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        sys.modules["MetaTrader5"] = ModuleType("MetaTrader5")

mt5 = cast(Any, sys.modules["MetaTrader5"])
if not hasattr(mt5, "TIMEFRAME_H1"):
    mt5.TIMEFRAME_H1 = 16385

from integrations.mt5.adapters import TradingData  # noqa: E402
from integrations.mt5.domain.signal import Signal  # noqa: E402
from integrations.mt5.domain.strategies.smc_strategy import SMCStrategy  # noqa: E402
from integrations.mt5.domain.strategies.trend_breakout_strategy import (  # noqa: E402
    TrendBreakoutStrategy,
)


class FrameData(TradingData):
    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame

    def get_data(self) -> pd.DataFrame:
        return self.frame.copy()

    def get_symbol(self) -> str:
        return "US100"


def _bars(close: np.ndarray[Any, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "tick_volume": np.ones(close.size),
        }
    )


@pytest.mark.parametrize(
    ("close", "direction", "expected"),
    [
        (np.linspace(80.0, 100.0, 30), "bullish", Signal.BUY),
        (np.linspace(100.0, 80.0, 30), "bearish", Signal.SELL),
    ],
)
def test_trend_breakout_signal_requires_breakout_trend_and_moving_average_alignment(
    monkeypatch: pytest.MonkeyPatch,
    close: np.ndarray[Any, Any],
    direction: str,
    expected: Signal,
) -> None:
    frame = _bars(close)
    strategy = TrendBreakoutStrategy(FrameData(frame), lookback_period=20)
    if direction == "bullish":
        levels = (70.0, float(frame["high"].iloc[-1]) - 0.5)
    else:
        levels = (float(frame["low"].iloc[-1]) + 0.5, 110.0)
    monkeypatch.setattr(strategy, "identify_support_resistance", lambda _frame: levels)
    monkeypatch.setattr(strategy, "calculate_trend_strength", lambda _frame: 30.0)

    assert strategy.signal() == ("US100", expected)


def test_trend_continuation_signal_requires_nearby_support_and_volume_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _bars(np.linspace(90.0, 100.0, 30))
    strategy = TrendBreakoutStrategy(FrameData(frame), lookback_period=20)
    monkeypatch.setattr(strategy, "identify_support_resistance", lambda _frame: (99.8, 120.0))
    monkeypatch.setattr(strategy, "calculate_trend_strength", lambda _frame: 35.0)

    assert strategy.signal() == ("US100", Signal.BUY)


def test_smc_signal_requires_structure_setup_and_ema_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _bars(np.linspace(10.0, 20.0, 30))
    strategy = SMCStrategy(FrameData(frame), order_block_periods=10)
    monkeypatch.setattr(strategy, "identify_market_structure", lambda _frame: "bullish")
    monkeypatch.setattr(
        strategy,
        "identify_order_blocks",
        lambda _frame: (pd.Series([True] * len(frame)), pd.Series([False] * len(frame))),
    )

    assert strategy.signal() == ("US100", Signal.BUY)


def test_smc_signal_rejects_setup_when_price_lacks_ema_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _bars(np.linspace(20.0, 10.0, 30))
    strategy = SMCStrategy(FrameData(frame), order_block_periods=10)
    monkeypatch.setattr(strategy, "identify_market_structure", lambda _frame: "bullish")
    monkeypatch.setattr(
        strategy,
        "identify_order_blocks",
        lambda _frame: (pd.Series([True] * len(frame)), pd.Series([False] * len(frame))),
    )

    assert strategy.signal() == ("US100", Signal.NONE)


def test_smc_detects_bearish_order_block_followed_by_consolidation() -> None:
    strategy = SMCStrategy(FrameData(pd.DataFrame()), order_block_periods=1)
    frame = pd.DataFrame(
        {
            "open": [20.0, 20.0, 10.0],
            "high": [21.0, 20.5, 10.5],
            "low": [19.0, 9.5, 9.5],
            "close": [20.0, 10.0, 10.0],
        }
    )

    bullish, bearish = strategy.identify_order_blocks(frame)

    assert bearish.iloc[1]
    assert not bullish.any()


def test_smc_signal_emits_sell_for_bearish_setup_below_fast_ema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _bars(np.linspace(20.0, 10.0, 30))
    strategy = SMCStrategy(FrameData(frame), order_block_periods=10)
    monkeypatch.setattr(strategy, "identify_market_structure", lambda _frame: "bearish")
    monkeypatch.setattr(
        strategy,
        "identify_order_blocks",
        lambda _frame: (pd.Series([False] * len(frame)), pd.Series([True] * len(frame))),
    )

    assert strategy.signal() == ("US100", Signal.SELL)
