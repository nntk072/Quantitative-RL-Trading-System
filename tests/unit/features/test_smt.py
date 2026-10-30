from __future__ import annotations

import numpy as np
import pandas as pd

from features.context.smt import smt_divergence


def _bars(closes: list[float], scale: float = 1.0) -> pd.DataFrame:
    close = np.asarray(closes, dtype=float) * scale
    return pd.DataFrame(
        {"open": close, "high": close + 0.1, "low": close - 0.1, "close": close},
        index=pd.date_range("2025-01-01", periods=len(close), freq="min", tz="UTC"),
    )


def test_smt_requires_paired_successive_swings_and_marks_divergence_on_confirmation() -> None:
    primary = _bars([5, 7, 10, 7, 6, 8, 12, 8, 6, 8, 11, 7, 5])
    secondary = _bars([10, 15, 20, 15, 12, 14, 19, 14, 12, 15, 21, 14, 11], 2.0)

    result = smt_divergence(primary, secondary, swing_period=1)

    expected = np.zeros(len(primary), dtype=float)
    expected[[7, 11]] = 1.0
    assert result["smt_bearish"].to_numpy().tolist() == expected.tolist()
    assert result["smt_bullish"].sum() == 0.0


def test_unmatched_primary_pivot_does_not_create_smt() -> None:
    primary = _bars([5, 7, 10, 7, 6, 8, 12, 8, 6])
    secondary = _bars([10, 11, 12, 13, 14, 15, 16, 17, 18])

    result = smt_divergence(primary, secondary, swing_period=1)

    assert result["smt_bearish"].sum() == 0.0
    assert result["smt_bullish"].sum() == 0.0
