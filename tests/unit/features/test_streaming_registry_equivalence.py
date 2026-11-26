"""Batch vs streaming equivalence on the registry's declared EMA and ATR outputs.

The batch values are the unnormalized ``build_indicators`` columns that the registry nodes
declare. Only EMA and ATR have streaming state; the other families are not covered here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from omegaconf import DictConfig

from configuration.configuration_loader import load_config
from features.technical import indicators as ind
from features.technical.streaming import StreamingAtr, StreamingEma


@pytest.fixture(scope="module")
def cfg() -> DictConfig:
    return load_config()


@pytest.fixture(scope="module")
def bars() -> pd.DataFrame:
    rng = np.random.default_rng(11)
    n = 2000
    index = pd.date_range("2025-01-06 00:00", periods=n, freq="min", tz="UTC")
    close = 100 + np.cumsum(rng.normal(0.0, 0.1, n))
    open_ = np.concatenate([[close[0]], close[:-1]])
    spread = np.abs(rng.normal(0.0, 0.05, n))
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + spread,
            "low": np.minimum(open_, close) - spread,
            "close": close,
            "volume": rng.integers(1, 6, n).astype(float),
        },
        index=index,
    )


def test_streaming_ema_equals_the_declared_ema_outputs(bars, cfg) -> None:
    batch = ind.build_indicators(bars, cfg.features)
    for span in (int(p) for p in cfg.features.ema_periods):
        state = StreamingEma.start(span)
        streamed = []
        for close in bars["close"].to_numpy(dtype=float):
            state = state.update(float(close))
            streamed.append(state.value)
        np.testing.assert_allclose(
            np.asarray(streamed), batch[f"ema_{span}"].to_numpy(dtype=float), rtol=1e-12, atol=0.0
        )


def test_streaming_atr_equals_the_declared_atr_output(bars, cfg) -> None:
    batch = ind.build_indicators(bars, cfg.features)
    state = StreamingAtr.start(int(cfg.features.atr_period))
    streamed = []
    for high, low, close in bars[["high", "low", "close"]].to_numpy(dtype=float):
        state = state.update(float(high), float(low), float(close))
        streamed.append(state.value)
    np.testing.assert_allclose(
        np.asarray(streamed), batch["atr"].to_numpy(dtype=float), rtol=1e-12, atol=0.0
    )
