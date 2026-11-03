"""Tests for the deterministic signal-series adapter."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trading.baselines import SignalSeriesStrategy


def test_signal_series_strategy_returns_aligned_values_without_state_drift() -> None:
    strategy = SignalSeriesStrategy(pd.Series([0.0, 1.0, -0.5, 0.0]))

    assert [strategy.act_at(i) for i in range(4)] == [0.0, 1.0, -0.5, 0.0]
    assert strategy.act_at(1) == 1.0
    assert all(-1.0 <= strategy.act_at(i) <= 1.0 for i in range(4))


@pytest.mark.parametrize(
    "signals",
    [
        pd.Series([], dtype=float),
        pd.Series([0.0, np.nan]),
        pd.Series([0.0, np.inf]),
        pd.Series([-1.1]),
        pd.Series([1.1]),
        pd.Series(["long"]),
    ],
)
def test_signal_series_strategy_rejects_invalid_targets(signals: pd.Series) -> None:
    with pytest.raises(ValueError):
        SignalSeriesStrategy(signals)


def test_signal_series_strategy_requires_a_series() -> None:
    with pytest.raises(TypeError, match="pandas Series"):
        SignalSeriesStrategy([0.0, 1.0])  # type: ignore[arg-type]
