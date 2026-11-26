"""Rust retained-level kernel must match the Python reference exactly, and fail closed."""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from features.technical import native_kernels
from features.technical.structure import structure_levels
from features.technical.swings import detect_pivots, detect_swings, retained_swing_levels

qrl_native = pytest.importorskip("qrl_native")


def _random_frames(seed: int, n: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    index = pd.RangeIndex(n)
    ev_h = rng.random(n) < 0.3
    ev_l = rng.random(n) < 0.3
    px_h = np.round(rng.normal(100.0, 3.0, n), 1)
    px_l = np.round(rng.normal(100.0, 3.0, n), 1)
    px_h[rng.random(n) < 0.2] = np.nan
    px_l[rng.random(n) < 0.2] = np.nan
    loc_h = rng.integers(0, max(n, 1), n).astype(float)
    loc_l = rng.integers(0, max(n, 1), n).astype(float)
    loc_h[rng.random(n) < 0.2] = np.nan
    loc_l[rng.random(n) < 0.2] = np.nan
    high = np.round(rng.normal(100.0, 3.0, n), 1)
    low = high - np.abs(rng.normal(0.0, 2.0, n))
    close = np.round(rng.normal(100.0, 3.0, n), 1)
    close[rng.random(n) < 0.1] = np.nan
    swings = pd.DataFrame(
        {
            "swing_high_event": ev_h,
            "swing_low_event": ev_l,
            "swing_high_extreme": px_h,
            "swing_low_extreme": px_l,
            "swing_high_location": loc_h,
            "swing_low_location": loc_l,
            "swing_high_price": px_h,
            "swing_low_price": px_l,
        },
        index=index,
    )
    bars = pd.DataFrame({"open": close, "high": high, "low": low, "close": close}, index=index)
    return swings, bars


@pytest.mark.parametrize("seed", range(20))
@pytest.mark.parametrize("max_levels", [1, 2, 8])
def test_native_retained_levels_match_reference_with_missing_values(
    seed: int, max_levels: int
) -> None:
    swings, bars = _random_frames(seed, n=int(np.random.default_rng(seed).integers(1, 90)))
    expected = retained_swing_levels(swings, bars, max_levels=max_levels)
    actual = retained_swing_levels(swings, bars, max_levels=max_levels, backend="native")
    pd.testing.assert_frame_equal(actual, expected, check_exact=True)


def test_native_retained_levels_match_reference_on_detected_swings() -> None:
    rng = np.random.default_rng(3)
    n = 2500
    close = 18000.0 + np.cumsum(rng.normal(0.0, 0.8, n))
    open_ = np.concatenate([[close[0]], close[:-1]])
    wick = np.abs(rng.normal(0.0, 1.2, n))
    index = pd.date_range("2025-01-02", periods=n, freq="1min", tz="UTC")
    bars = pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + wick,
            "low": np.minimum(open_, close) - wick,
            "close": close,
        },
        index=index,
    )
    for period, mult in ((2, 0.0), (3, 0.8), (5, 0.5)):
        pivots = detect_pivots(bars, left=period, right=period)
        swings = detect_swings(bars, pivots, atr_mult=mult)
        expected = retained_swing_levels(swings, bars, max_levels=8)
        actual = retained_swing_levels(swings, bars, max_levels=8, backend="native")
        pd.testing.assert_frame_equal(actual, expected, check_exact=True)
        pd.testing.assert_frame_equal(
            structure_levels(bars, swing_period=period, atr_mult=mult, retained_backend="native"),
            structure_levels(bars, swing_period=period, atr_mult=mult),
            check_exact=True,
        )


@given(seed=st.integers(min_value=0, max_value=10_000), n=st.integers(min_value=0, max_value=60))
@settings(max_examples=80, derandomize=True, database=None)
def test_native_retained_levels_match_reference_on_generated_frames(seed: int, n: int) -> None:
    swings, bars = _random_frames(seed, n)
    expected = retained_swing_levels(swings, bars, max_levels=3)
    actual = retained_swing_levels(swings, bars, max_levels=3, backend="native")
    pd.testing.assert_frame_equal(actual, expected, check_exact=True)


def test_native_kernel_refuses_non_boolean_event_bytes() -> None:
    swings, bars = _random_frames(1, n=5)
    with pytest.raises(ValueError, match="only 0 or 1"):
        qrl_native.retained_swing_levels(
            bytes([0, 2, 0, 0, 0]),
            bytes(5),
            bytes(40),
            bytes(40),
            bytes(40),
            bytes(40),
            bytes(40),
            bytes(40),
            bytes(40),
            1,
        )


def test_native_kernel_refuses_partial_float_elements() -> None:
    with pytest.raises(ValueError, match="whole number of float64"):
        qrl_native.retained_swing_levels(
            bytes(3),
            bytes(3),
            bytes(3),
            bytes(3),
            bytes(3),
            bytes(3),
            bytes(3),
            bytes(3),
            bytes(3),
            1,
        )


def test_native_kernel_refuses_zero_width() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        qrl_native.retained_swing_levels(
            bytes(4),
            bytes(4),
            bytes(32),
            bytes(32),
            bytes(32),
            bytes(32),
            bytes(32),
            bytes(32),
            bytes(32),
            0,
        )


def test_loader_returns_the_extension_that_exposes_the_kernel() -> None:
    assert native_kernels.load_qrl_native() is qrl_native


def test_native_backend_raises_import_error_when_extension_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    swings, bars = _random_frames(4, n=10)
    monkeypatch.setitem(sys.modules, "qrl_native", None)
    with pytest.raises(ImportError, match="not importable"):
        retained_swing_levels(swings, bars, max_levels=2, backend="native")
