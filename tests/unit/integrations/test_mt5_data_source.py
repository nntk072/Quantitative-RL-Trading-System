"""MT5 rate data is exposed through the broker-neutral tabular contract."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any, cast

import pandas as pd

if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        sys.modules["MetaTrader5"] = ModuleType("MetaTrader5")

mt5 = cast(Any, sys.modules["MetaTrader5"])

from integrations.mt5.domain.data_sources.mt5_data import MT5Data  # noqa: E402


def test_get_data_requests_configured_symbol_and_converts_epoch_bar_times(monkeypatch) -> None:
    calls: list[tuple[str, int, int, int]] = []

    def copy_rates(symbol: str, timeframe: int, start: int, count: int) -> list[dict[str, int]]:
        calls.append((symbol, timeframe, start, count))
        return [{"time": 1_700_000_000, "open": 100}, {"time": 1_700_000_060, "open": 101}]

    monkeypatch.setattr(mt5, "copy_rates_from_pos", copy_rates, raising=False)
    source = MT5Data("US100.cash", 5)

    bars = source.get_data()

    assert calls == [("US100.cash", 5, 0, 1000)]
    assert source.get_symbol() == "US100.cash"
    assert list(bars.columns) == ["time", "open"]
    assert bars["time"].tolist() == list(pd.to_datetime([1_700_000_000, 1_700_000_060], unit="s"))


def test_get_data_preserves_empty_result_without_inventing_bar_columns(monkeypatch) -> None:
    monkeypatch.setattr(mt5, "copy_rates_from_pos", lambda *_args: None, raising=False)

    bars = MT5Data("US500", 60).get_data()

    assert bars.empty
    assert list(bars.columns) == []
