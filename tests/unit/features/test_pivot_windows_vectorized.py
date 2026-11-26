"""Vectorized fractal pivots must match the sequential loop reference exactly."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from features.technical.swings import detect_pivots, detect_pivots_reference
from market_data.arrow_schemas import mt5_export_to_bars

REPO = Path(__file__).resolve().parents[3]
EXAMPLE = REPO / "data" / "examples" / "US100.cash_M1_202412300105_202501020334.csv"


def _bars(high: np.ndarray[Any, Any], low: np.ndarray[Any, Any]) -> pd.DataFrame:
    index = pd.RangeIndex(len(high))
    return pd.DataFrame({"open": low, "high": high, "low": low, "close": high}, index=index)


def _example_bars() -> pd.DataFrame:
    frame = pd.read_csv(EXAMPLE, sep="\t", dtype=str).rename(columns=lambda n: n.strip("<>"))
    table, problems = mt5_export_to_bars(frame, instrument_id="US100.cash", timeframe="M1")
    assert problems == []
    df: pd.DataFrame = table.select(["event_time", "open", "high", "low", "close"]).to_pandas()
    df.index = pd.DatetimeIndex(df.pop("event_time"))
    return df


@pytest.mark.parametrize("left,right", [(0, 0), (0, 3), (3, 0), (1, 1), (2, 2), (3, 3), (5, 4)])
def test_vectorized_pivots_match_loop_reference_on_tracked_example(left: int, right: int) -> None:
    bars = _example_bars()
    pd.testing.assert_frame_equal(
        detect_pivots(bars, left=left, right=right),
        detect_pivots_reference(bars, left=left, right=right),
        check_exact=True,
    )


@pytest.mark.parametrize("seed", range(12))
def test_vectorized_pivots_match_loop_reference_with_ties_and_missing_values(seed: int) -> None:
    rng = np.random.default_rng(seed)
    n = int(rng.integers(1, 120))
    high = np.round(rng.normal(100.0, 2.0, n), 1)
    low = high - np.abs(rng.normal(0.0, 1.0, n))
    high[rng.random(n) < 0.1] = np.nan
    low[rng.random(n) < 0.1] = np.nan
    bars = _bars(high, low)
    for left in range(0, 5):
        for right in range(0, 5):
            pd.testing.assert_frame_equal(
                detect_pivots(bars, left=left, right=right),
                detect_pivots_reference(bars, left=left, right=right),
                check_exact=True,
            )


def test_short_series_without_a_full_window_has_no_pivots() -> None:
    bars = _bars(np.array([1.0, 3.0, 2.0]), np.array([0.5, 2.5, 1.5]))
    result = detect_pivots(bars, left=2, right=2)
    assert not result["pivot_high_event"].any()
    assert not result["pivot_low_event"].any()
    assert result["pivot_high_price"].isna().all()


def test_negative_pivot_window_is_refused() -> None:
    bars = _bars(np.array([1.0, 2.0, 1.0]), np.array([0.5, 1.5, 0.5]))
    with pytest.raises(ValueError, match="non-negative"):
        detect_pivots(bars, left=-1, right=1)


@given(
    values=st.lists(
        st.tuples(
            st.integers(min_value=-40, max_value=40),
            st.integers(min_value=0, max_value=8),
            st.booleans(),
        ),
        min_size=1,
        max_size=60,
    ),
    left=st.integers(min_value=1, max_value=4),
    right=st.integers(min_value=1, max_value=4),
    cut=st.integers(min_value=0, max_value=60),
)
@settings(max_examples=120, derandomize=True, database=None)
def test_pivot_confirmation_is_causal_under_prefix_truncation(
    values: list[tuple[int, int, bool]], left: int, right: int, cut: int
) -> None:
    high = np.array([float(v) / 2.0 for v, _, _ in values])
    low = np.array([float(v) / 2.0 - float(w) for v, w, _ in values])
    high[[i for i, (_, _, nan) in enumerate(values) if nan]] = np.nan
    bars = _bars(high, low)
    full = detect_pivots(bars, left=left, right=right)
    keep = min(cut, len(bars))
    prefix = detect_pivots(bars.iloc[:keep], left=left, right=right)
    pd.testing.assert_frame_equal(prefix, full.iloc[:keep], check_exact=True)
