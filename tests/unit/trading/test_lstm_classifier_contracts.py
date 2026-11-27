"""Fast contracts for sweep-label generation and LSTM signal replay."""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd
import pytest
import torch
from torch import nn

from trading.baselines.lstm_classifier import (
    LSTMStrategy,
    LSTMSweepClassifier,
    build_sweep_dataset,
)


def _bars(close: list[float]) -> pd.DataFrame:
    index = pd.date_range("2026-01-02 01:05", periods=len(close), freq="1min")
    return pd.DataFrame({"close": close}, index=index)


def test_sweep_dataset_uses_first_future_crossing_and_zero_fills_features(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars = _bars([8.0, 9.0, 12.0, -1.0, 12.0, -1.0])
    features = pd.DataFrame({"x": [1.0, np.nan, 3.0, 4.0, 5.0, 6.0]}, index=bars.index)
    levels = pd.DataFrame(
        {
            "asian_high": [10.0, 10.0, 10.0, 10.0, 10.0, 10.0],
            "london_high": [np.nan] * len(bars),
            "asian_low": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "london_low": [np.nan] * len(bars),
        },
        index=bars.index,
    )
    monkeypatch.setattr(
        "trading.baselines.lstm_classifier.detect_session_levels", lambda _bars: levels
    )

    x, y = build_sweep_dataset(bars, features, window=2, horizon=2)

    assert x.dtype == torch.float32
    assert y.dtype == torch.int64
    assert y.tolist() == [1, -1, 1]
    assert x[0, :, 0].tolist() == [1.0, 0.0]


def test_sweep_dataset_handles_missing_levels_and_rejects_unusable_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars = _bars([10.0, 10.0, 10.0, 10.0])
    features = pd.DataFrame({"x": np.zeros(len(bars))}, index=bars.index)
    no_levels = pd.DataFrame(
        {
            name: [np.nan] * len(bars)
            for name in ("asian_high", "london_high", "asian_low", "london_low")
        },
        index=bars.index,
    )
    monkeypatch.setattr(
        "trading.baselines.lstm_classifier.detect_session_levels", lambda _bars: no_levels
    )

    with pytest.raises(ValueError, match="No valid session levels"):
        build_sweep_dataset(bars, features, window=2, horizon=1)

    partial_levels = no_levels.copy()
    partial_levels.loc[bars.index[-1], "asian_high"] = 100.0
    monkeypatch.setattr(
        "trading.baselines.lstm_classifier.detect_session_levels", lambda _bars: partial_levels
    )
    x, y = build_sweep_dataset(bars, features, window=2, horizon=1)
    assert x.shape == (2, 2, 1)
    assert y.tolist() == [0, 0]

    with pytest.raises(ValueError, match="no labelled sweep samples"):
        build_sweep_dataset(bars, features, window=4, horizon=1)


def test_lstm_classifier_forward_returns_three_direction_logits() -> None:
    model = LSTMSweepClassifier(n_features=2, hidden_size=3, num_layers=2, dropout=0.25)

    logits = model(torch.zeros((4, 5, 2)))

    assert logits.shape == (4, 3)


class _DirectionModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.anchor = nn.Parameter(torch.zeros(()))
        self.seen_nan = False
        self.eval_called = False

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        self.seen_nan = self.seen_nan or bool(torch.isnan(values).any())
        feature = values[0, 0, 0]
        if feature < 0:
            logits = torch.tensor([[4.0, 0.0, 0.0]], device=values.device)
        elif feature > 0:
            logits = torch.tensor([[0.0, 0.0, 4.0]], device=values.device)
        else:
            logits = torch.tensor([[0.0, 4.0, 0.0]], device=values.device)
        return logits + self.anchor

    def eval(self) -> _DirectionModel:
        self.eval_called = True
        return self


def test_lstm_strategy_precomputes_thresholded_actions_and_replays_by_index() -> None:
    model = _DirectionModel()
    features = pd.DataFrame({"x": [-1.0, -1.0, 1.0, 0.0, np.nan]})

    strategy = LSTMStrategy(
        cast(Any, model), features, window=2, long_size=0.75, short_size=-0.5, threshold=0.8
    )

    assert model.eval_called
    assert not model.seen_nan
    assert [strategy.act_at(index) for index in range(len(features))] == [
        0.0,
        0.0,
        -0.5,
        -0.5,
        0.75,
    ]
    assert strategy.act({}) == 0.0
    strategy.fast_forward(2)
    assert strategy.act({}) == -0.5
    strategy.reset()
    assert strategy.act_at(2) == -0.5
    with pytest.raises(IndexError, match="outside"):
        strategy.act_at(len(features))


def test_lstm_strategy_neutral_probabilities_do_not_cross_action_threshold() -> None:
    model = _DirectionModel()
    features = pd.DataFrame({"x": [0.0, 0.0, 0.0]})

    strategy = LSTMStrategy(cast(Any, model), features, window=1, threshold=0.99)

    assert [strategy.act_at(index) for index in range(len(features))] == [0.0, 0.0, 0.0]
