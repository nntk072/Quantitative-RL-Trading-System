"""Prefix-causality checks for reusable rule-based baseline signals."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
import pytest

import trading.baselines.rule_based as rule_based
from trading.baselines.rule_based import (
    ema_crossover,
    macd_baseline,
    macd_ema50_baseline,
    rsi_mean_reversion,
)


def _bars() -> pd.DataFrame:
    rng = np.random.default_rng(20261102)
    close = 20_000.0 + np.cumsum(rng.normal(0.0, 3.0, 240))
    return pd.DataFrame(
        {
            "open": close,
            "high": close + rng.uniform(0.1, 3.0, len(close)),
            "low": close - rng.uniform(0.1, 3.0, len(close)),
            "close": close,
            "volume": rng.uniform(100.0, 1_000.0, len(close)),
        },
        index=pd.date_range("2025-01-02", periods=len(close), freq="1min"),
    )


@pytest.mark.parametrize(
    "signal_builder",
    [ema_crossover, macd_baseline, macd_ema50_baseline, rsi_mean_reversion],
    ids=["ema", "macd-histogram", "macd-ema50", "rsi"],
)
def test_rule_signal_prefix_matches_full_build(
    signal_builder: Callable[[pd.DataFrame], pd.Series],
) -> None:
    bars = _bars()
    cutoff = 173

    full = signal_builder(bars)
    prefix = signal_builder(bars.iloc[:cutoff])

    pd.testing.assert_series_equal(full.iloc[:cutoff], prefix)


def test_legacy_atr_arguments_do_not_claim_or_change_signal_exit_semantics() -> None:
    bars = _bars()

    pd.testing.assert_series_equal(
        ema_crossover(bars, atr_period=3, atr_stop_mult=0.5),
        ema_crossover(bars, atr_period=40, atr_stop_mult=5.0),
    )
    pd.testing.assert_series_equal(
        rsi_mean_reversion(bars, atr_period=3),
        rsi_mean_reversion(bars, atr_period=40),
    )


def test_rsi_mean_reversion_holds_until_neutral_then_rearms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars = _bars().iloc[:9]
    rsi_values = pd.Series([60.0, 25.0, 35.0, 44.9, 45.0, 75.0, 60.0, 55.0, 25.0])
    monkeypatch.setattr(rule_based, "_rsi", lambda _close, _period: rsi_values)

    signals = rsi_mean_reversion(bars)

    assert signals.tolist() == [0, 1, 1, 1, 0, -1, -1, 0, 1]
