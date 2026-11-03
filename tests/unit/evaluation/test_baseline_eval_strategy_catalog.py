"""Tests for opt-in deterministic strategy arms in the baseline evaluator."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import scripts.research.analysis.evaluation.run_baseline_eval as baseline_eval
from scripts.research.analysis.evaluation.run_baseline_eval import build_strategies


def test_baseline_catalog_exposes_reusable_macd_and_rsi_arms() -> None:
    rng = np.random.default_rng(4)
    index = pd.date_range("2025-01-02 16:30", periods=120, freq="1min", tz="Etc/GMT-3")
    close = 20_000.0 + np.cumsum(rng.normal(0.0, 1.0, len(index)))
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 2.0,
            "low": close - 2.0,
            "close": close,
            "volume": rng.uniform(900.0, 1_100.0, len(index)),
        },
        index=index,
    )

    strategies = build_strategies(bars)

    assert {"macd_histogram", "rsi_mean_reversion"} <= strategies.keys()
    for name in ("macd_histogram", "rsi_mean_reversion"):
        signal = strategies[name]
        actions = [signal.act_at(index) for index in range(len(bars))]
        assert all(np.isfinite(action) and -1.0 <= action <= 1.0 for action in actions)


def test_signal_baseline_evaluator_builds_exit_actions_after_warmup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = pd.date_range("2025-01-02 16:30", periods=6, freq="1min", tz="Etc/GMT-3")
    bars = pd.DataFrame({"close": 20_000.0}, index=index)
    targets = pd.Series([0, 0, 1, 1, 0, 0], index=index)
    monkeypatch.setattr(baseline_eval, "rsi_mean_reversion", lambda _bars: targets)

    actions = baseline_eval._discrete_signal_actions("rsi_mean_reversion", bars, start_index=2)

    assert actions is not None
    assert actions.tolist() == [0, 0, 7, 0, 19, 0]
