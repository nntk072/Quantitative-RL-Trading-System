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


def test_smt_forward_fills_missing_secondary_bars_without_future_influence() -> None:
    primary = _bars([5, 7, 10, 7, 6, 8, 12, 8, 6, 8, 11, 7, 5])
    secondary = _bars([10, 15, 20, 15, 12, 14, 19, 14, 12, 15, 21, 14, 11])
    secondary = secondary.drop(index=secondary.index[[0, 4, 5, 9]])

    full = smt_divergence(primary, secondary, swing_period=1)
    aligned_close = secondary["close"].reindex(primary.index, method="ffill")
    expected_spread = (primary["close"] - aligned_close) / primary["close"]
    pd.testing.assert_series_equal(full["smt_spread"], expected_spread.rename("smt_spread"))
    assert pd.isna(full["smt_spread"].iloc[0])

    prefix_count = 8
    cutoff = primary.index[prefix_count - 1]
    prefix_primary = primary.iloc[:prefix_count]
    prefix_secondary = secondary.loc[secondary.index <= cutoff]
    prefix = smt_divergence(prefix_primary, prefix_secondary, swing_period=1)
    pd.testing.assert_frame_equal(full.iloc[:prefix_count], prefix)


def test_missing_secondary_confirmation_row_does_not_become_a_duplicate_bar() -> None:
    primary = _bars([5, 7, 10, 7, 6, 8, 12, 8, 6])
    secondary = _bars([10, 15, 20, 15, 12, 14, 19, 14, 12])
    missing_confirmation_row = secondary.drop(index=secondary.index[3])

    complete = smt_divergence(primary, secondary, swing_period=1)
    with_missing = smt_divergence(primary, missing_confirmation_row, swing_period=1)

    assert complete["smt_bearish"].iloc[7] == 1.0
    assert with_missing["smt_bearish"].iloc[7] == 1.0
    pd.testing.assert_series_equal(
        complete["smt_bearish"], with_missing["smt_bearish"], check_names=False
    )


def test_secondary_pivot_confirmation_is_not_backdated_to_primary_row() -> None:
    primary = _bars([5, 7, 10, 7, 6, 8, 12, 8, 6])
    secondary = _bars([10, 15, 20, 15, 12, 14, 19, 14, 12])
    secondary.index += pd.Timedelta(seconds=30)

    result = smt_divergence(primary, secondary, swing_period=1)

    assert result["smt_bearish"].iloc[7] == 0.0
    assert result["smt_bearish"].iloc[8] == 1.0
