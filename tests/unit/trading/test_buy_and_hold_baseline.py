"""Contracts for the simple close-to-close buy-and-hold return curve."""

import numpy as np
import pandas as pd

from trading.baselines.buy_and_hold import buy_and_hold_returns


def test_buy_and_hold_returns_compound_close_returns_on_source_index() -> None:
    index = pd.date_range("2026-01-01", periods=3, freq="D")
    bars = pd.DataFrame({"close": [100.0, 110.0, 99.0]}, index=index)

    equity = buy_and_hold_returns(bars)

    assert equity.index.equals(index)
    np.testing.assert_allclose(equity.to_numpy(), [1.0, 1.1, 0.99])
    assert bars["close"].tolist() == [100.0, 110.0, 99.0]
