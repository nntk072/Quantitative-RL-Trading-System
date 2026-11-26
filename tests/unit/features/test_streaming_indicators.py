"""Batch vs streaming and incremental vs full-build equivalence for EMA and ATR (CAUSAL-FEATURE-GRAPH).

Tolerances are frozen before comparison: the recursions are the same formula, so any difference is
float rounding from evaluation order. RTOL and ATOL are relative and absolute bounds on a price-scale
series (about 2e4), not fitted to the outcome.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from numpy.typing import NDArray

from features.technical.indicators import atr, ema
from features.technical.streaming import RecursiveMeanState, StreamingAtr, StreamingEma

REPO = Path(__file__).resolve().parents[3]
EXAMPLE = REPO / "data" / "examples" / "US100.cash_M1_202412300105_202501020334.csv"
RTOL = 1e-12
ATOL = 1e-9


@pytest.fixture(scope="module")
def bars() -> pd.DataFrame:
    raw = pd.read_csv(EXAMPLE, sep="\t", dtype=str).rename(columns=lambda name: name.strip("<>"))
    frame = pd.DataFrame(
        {
            "high": raw["HIGH"].astype(float).to_numpy(),
            "low": raw["LOW"].astype(float).to_numpy(),
            "close": raw["CLOSE"].astype(float).to_numpy(),
        }
    )
    assert len(frame) == 2880
    return frame


def _stream_ema(close: pd.Series, span: int) -> NDArray[np.float64]:
    state = StreamingEma.start(span)
    out = []
    for value in close.to_numpy():
        state = state.update(float(value))
        out.append(state.value)
    return np.asarray(out, dtype=float)


def _stream_atr(frame: pd.DataFrame, period: int) -> NDArray[np.float64]:
    state = StreamingAtr.start(period)
    out = []
    for high, low, close in zip(
        frame["high"].to_numpy(), frame["low"].to_numpy(), frame["close"].to_numpy(), strict=True
    ):
        state = state.update(float(high), float(low), float(close))
        out.append(state.value)
    return np.asarray(out, dtype=float)


def test_streaming_ema_matches_batch_ewm_on_the_example(bars: pd.DataFrame) -> None:
    batch = ema(bars["close"], 20).to_numpy()
    streamed = _stream_ema(bars["close"], 20)
    np.testing.assert_allclose(streamed, batch, rtol=RTOL, atol=ATOL)


def test_streaming_atr_matches_batch_ewm_on_the_example(bars: pd.DataFrame) -> None:
    batch = atr(bars, 14).to_numpy()
    streamed = _stream_atr(bars, 14)
    np.testing.assert_allclose(streamed, batch, rtol=RTOL, atol=ATOL)


def test_first_atr_value_is_the_first_bar_range(bars: pd.DataFrame) -> None:
    streamed = _stream_atr(bars, 14)
    assert streamed[0] == pytest.approx(bars["high"].iloc[0] - bars["low"].iloc[0], abs=0.0)


@pytest.mark.parametrize("k", [1, 2, 15, 500, 2879])
def test_incremental_state_at_each_prefix_equals_the_batch_on_that_prefix(
    bars: pd.DataFrame, k: int
) -> None:
    # Causality: the full-build value at row k-1 equals the value computed from the prefix alone.
    prefix = bars.iloc[:k].reset_index(drop=True)
    streamed_ema = _stream_ema(prefix["close"], 20)
    streamed_atr = _stream_atr(prefix, 14)
    np.testing.assert_allclose(
        streamed_ema[-1], ema(prefix["close"], 20).iloc[-1], rtol=RTOL, atol=ATOL
    )
    np.testing.assert_allclose(streamed_atr[-1], atr(prefix, 14).iloc[-1], rtol=RTOL, atol=ATOL)


def test_resuming_from_a_snapshot_reproduces_the_continuous_run(bars: pd.DataFrame) -> None:
    continuous = _stream_atr(bars, 14)
    split = 1000
    state = StreamingAtr.start(14)
    for high, low, close in zip(
        bars["high"].iloc[:split], bars["low"].iloc[:split], bars["close"].iloc[:split], strict=True
    ):
        state = state.update(float(high), float(low), float(close))
    snapshot = state  # immutable: resuming from it must not depend on any hidden mutable buffer
    resumed = []
    for high, low, close in zip(
        bars["high"].iloc[split:], bars["low"].iloc[split:], bars["close"].iloc[split:], strict=True
    ):
        snapshot = snapshot.update(float(high), float(low), float(close))
        resumed.append(snapshot.value)
    assert resumed == list(continuous[split:])


def test_updates_return_new_snapshots_and_leave_the_previous_one_unchanged() -> None:
    before = RecursiveMeanState(alpha=0.5)
    after = before.update(10.0)
    assert before.value is None and before.count == 0
    assert after.value == 10.0 and after.count == 1


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_observation_is_refused_not_carried_forward(bad: float) -> None:
    state = StreamingEma.start(5).update(100.0)
    with pytest.raises(ValueError, match="must be finite"):
        state.update(bad)
    with pytest.raises(ValueError, match="must be finite"):
        StreamingAtr.start(3).update(bad, 99.0, 100.0)


def test_inverted_bar_is_refused() -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        StreamingAtr.start(3).update(99.0, 100.0, 99.5)


@pytest.mark.parametrize("period", [0, -3])
def test_non_positive_periods_are_refused(period: int) -> None:
    with pytest.raises(ValueError):
        StreamingEma.start(period)
    with pytest.raises(ValueError):
        StreamingAtr.start(period)


def test_mean_state_rejects_an_alpha_outside_the_unit_interval() -> None:
    with pytest.raises(ValueError, match="alpha must be in"):
        RecursiveMeanState(alpha=0.0)
