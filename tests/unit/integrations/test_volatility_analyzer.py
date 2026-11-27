"""ATR and volatility metrics of the MT5 volatility analyzer, with MT5 calls faked."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        sys.modules["MetaTrader5"] = ModuleType("MetaTrader5")
        sys.modules["MetaTrader5"].TIMEFRAME_H1 = 16385  # type: ignore[attr-defined]

from integrations.mt5.domain import volatility_analyzer as va  # noqa: E402

mt5: Any = sys.modules["MetaTrader5"]

for _name in ("symbol_select", "copy_rates_from_pos", "symbol_info_tick", "shutdown"):
    if not hasattr(mt5, _name):
        setattr(mt5, _name, lambda *_args, **_kwargs: None)


@pytest.fixture
def analyzer(monkeypatch: pytest.MonkeyPatch) -> va.VolatilityAnalyzer:
    monkeypatch.setattr(va, "ensure_mt5_logged_in", lambda **_kwargs: None)
    return va.VolatilityAnalyzer(
        login="1", server="s", password="p", terminal_path="t", atr_period=3, lookback_period=2
    )


def _bars(n: int, step: float = 1.0) -> pd.DataFrame:
    close = np.arange(n, dtype=float) * step + 100.0
    return pd.DataFrame({"high": close + 1.0, "low": close - 1.0, "close": close})


def test_atr_is_zero_when_history_is_too_short(analyzer: va.VolatilityAnalyzer) -> None:
    assert analyzer.calculate_atr(_bars(3)) == 0.0


def test_atr_of_constant_range_bars_is_that_range(analyzer: va.VolatilityAnalyzer) -> None:
    # Each bar spans 2.0 and the close moves by 1.0, so every true range is 2.0.
    assert analyzer.calculate_atr(_bars(10)) == pytest.approx(2.0)


def test_atr_uses_the_gap_to_previous_close_when_it_is_larger(
    analyzer: va.VolatilityAnalyzer,
) -> None:
    df = pd.DataFrame(
        {
            "high": [10.0, 30.0, 31.0, 32.0, 33.0],
            "low": [9.0, 29.0, 30.0, 31.0, 32.0],
            "close": [9.5, 29.5, 30.5, 31.5, 32.5],
        }
    )

    # The gap from the previous close to the next high sets the true range on the first bar.
    assert analyzer.calculate_atr(df) > 2.0


def test_atr_with_few_true_ranges_is_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(va, "ensure_mt5_logged_in", lambda **_kwargs: None)
    wide = va.VolatilityAnalyzer(
        login="1", server="s", password="p", terminal_path="t", atr_period=8
    )

    assert wide.calculate_atr(_bars(8)) == 0.0


def test_volatility_metrics_return_none_when_symbol_is_unavailable(
    analyzer: va.VolatilityAnalyzer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mt5, "symbol_select", lambda *_args: False)

    assert analyzer.calculate_volatility_metrics("EURUSD") is None


def test_volatility_metrics_return_none_without_rates(
    analyzer: va.VolatilityAnalyzer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mt5, "symbol_select", lambda *_args: True)
    monkeypatch.setattr(mt5, "copy_rates_from_pos", lambda *_args: None)

    assert analyzer.calculate_volatility_metrics("EURUSD") is None


def test_volatility_metrics_refuse_short_history(
    analyzer: va.VolatilityAnalyzer, monkeypatch: pytest.MonkeyPatch
) -> None:
    rates = _bars(4).assign(time=np.arange(4) * 3600)
    monkeypatch.setattr(mt5, "symbol_select", lambda *_args: True)
    monkeypatch.setattr(mt5, "copy_rates_from_pos", lambda *_args: rates.to_records(index=False))

    assert analyzer.calculate_volatility_metrics("EURUSD") is None


def _rates_and_tick(monkeypatch: pytest.MonkeyPatch, tick: Any) -> None:
    rates = _bars(12).assign(time=np.arange(12) * 3600)
    monkeypatch.setattr(mt5, "symbol_select", lambda *_args: True)
    monkeypatch.setattr(mt5, "copy_rates_from_pos", lambda *_args: rates.to_records(index=False))
    monkeypatch.setattr(mt5, "symbol_info_tick", lambda *_args: tick)


def test_volatility_metrics_use_the_tick_mid_price(
    analyzer: va.VolatilityAnalyzer, monkeypatch: pytest.MonkeyPatch
) -> None:
    _rates_and_tick(monkeypatch, SimpleNamespace(bid=110.0, ask=112.0))

    metrics = analyzer.calculate_volatility_metrics("EURUSD")

    assert metrics is not None
    assert metrics["symbol"] == "EURUSD"
    assert metrics["current_price"] == pytest.approx(111.0)
    assert metrics["atr"] == pytest.approx(2.0)
    assert metrics["atr_percentage"] == pytest.approx(2.0 / 111.0 * 100)
    assert metrics["score"] == pytest.approx(
        metrics["atr_percentage"] * 0.6 + metrics["volatility"] * 0.4
    )


def test_volatility_metrics_fall_back_to_last_close_without_a_tick(
    analyzer: va.VolatilityAnalyzer, monkeypatch: pytest.MonkeyPatch
) -> None:
    _rates_and_tick(monkeypatch, None)

    metrics = analyzer.calculate_volatility_metrics("EURUSD")

    assert metrics is not None
    assert metrics["current_price"] == pytest.approx(111.0)


def test_volatility_metrics_report_errors_as_none(
    analyzer: va.VolatilityAnalyzer, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_args: Any) -> bool:
        raise RuntimeError("terminal gone")

    monkeypatch.setattr(mt5, "symbol_select", boom)

    assert analyzer.calculate_volatility_metrics("EURUSD") is None


def test_destructor_shuts_the_terminal_down(
    analyzer: va.VolatilityAnalyzer, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(mt5, "shutdown", lambda: calls.append("shutdown"))

    analyzer.__del__()

    assert calls == ["shutdown"]


def test_ranking_sorts_by_score_and_skips_unavailable_symbols(
    analyzer: va.VolatilityAnalyzer, monkeypatch: pytest.MonkeyPatch
) -> None:
    metrics = {
        "EURUSD": {"symbol": "EURUSD", "score": 0.4},
        "GBPUSD": None,
        "US100": {"symbol": "US100", "score": 1.2},
    }
    monkeypatch.setattr(
        analyzer,
        "calculate_volatility_metrics",
        lambda symbol, _timeframe: metrics[symbol],
    )

    ranked = analyzer.rank_symbols_by_volatility(["EURUSD", "GBPUSD", "US100"])

    assert [item["symbol"] for item in ranked] == ["US100", "EURUSD"]


def test_selection_applies_score_floor_and_symbol_limit(
    analyzer: va.VolatilityAnalyzer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        analyzer,
        "rank_symbols_by_volatility",
        lambda *_args: [
            {"symbol": "US100", "score": 1.0, "atr_percentage": 0.8, "volatility": 0.4},
            {"symbol": "US500", "score": 0.7, "atr_percentage": 0.6, "volatility": 0.3},
            {"symbol": "EURUSD", "score": 0.2, "atr_percentage": 0.1, "volatility": 0.1},
        ],
    )

    selected = analyzer.select_top_volatile_symbols(
        ["US100", "US500", "EURUSD"], max_symbols=1, min_volatility_threshold=0.5
    )

    assert selected == ["US100"]


def test_symbol_info_maps_broker_fields_and_handles_missing_or_broken_metadata(
    analyzer: va.VolatilityAnalyzer, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = SimpleNamespace(
        name="EURUSD",
        description="Euro / US Dollar",
        currency_base="EUR",
        currency_profit="USD",
        trade_mode=4,
        visible=True,
        select=True,
    )
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: info)
    mapped = analyzer.get_symbol_info("EURUSD")

    assert mapped == {
        "symbol": "EURUSD",
        "name": "EURUSD",
        "description": "Euro / US Dollar",
        "currency_base": "EUR",
        "currency_profit": "USD",
        "trade_mode": 4,
        "visible": True,
        "select": True,
    }

    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: None)
    assert analyzer.get_symbol_info("MISSING") is None

    def fail_info(_symbol: str) -> None:
        raise RuntimeError("terminal disconnected")

    monkeypatch.setattr(mt5, "symbol_info", fail_info)
    assert analyzer.get_symbol_info("EURUSD") is None
