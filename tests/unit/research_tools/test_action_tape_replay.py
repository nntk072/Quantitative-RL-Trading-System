"""Tests for normalized parity comparisons of simulator action-tape events."""

from __future__ import annotations

import numpy as np
import pytest
from research_tools.simulation.evaluation.replay_simulator_action_tape import (
    _compare_lifecycle_events,
)


@pytest.mark.parametrize("missing_rr", [None, float("nan"), np.float64("nan")])
def test_structural_open_rr_missing_values_compare_as_the_same(
    missing_rr: float | None,
) -> None:
    environment = [
        {
            "type": "open",
            "direction": -1,
            "decision_bar_time": "2025-11-28T15:21:00+00:00",
            "fill_time": "2025-11-28T15:22:00.024000+00:00",
            "price": 25322.35,
            "size": 1.0,
            "sl_price": 25336.25,
            "tp_price": 25292.15,
            "modeled_stop_risk_usd": 13.9,
            "risk_budget_usd": 50.0,
            "risk_frac": 0.001,
            "rr_ratio": None,
        }
    ]
    backtest = [{**environment[0], "rr_ratio": missing_rr}]

    matches, mismatches = _compare_lifecycle_events(environment, backtest)

    assert matches
    assert mismatches == []


def test_structural_open_comparison_still_checks_finite_rr_values() -> None:
    environment = [
        {
            "type": "open",
            "direction": 1,
            "decision_bar_time": "2025-11-28T15:21:00+00:00",
            "fill_time": "2025-11-28T15:22:00+00:00",
            "price": 100.0,
            "size": 1.0,
            "sl_price": 99.0,
            "tp_price": 102.0,
            "modeled_stop_risk_usd": 1.0,
            "risk_budget_usd": 50.0,
            "risk_frac": 0.001,
            "rr_ratio": 2.0,
        }
    ]
    backtest = [{**environment[0], "rr_ratio": 3.0}]

    matches, mismatches = _compare_lifecycle_events(environment, backtest)

    assert not matches
    assert mismatches == ["open[0].rr_ratio"]
