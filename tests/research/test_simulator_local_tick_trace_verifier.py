"""Contracts for independent local TickBook trace verification."""

from __future__ import annotations

from scripts.research.analysis.evaluation.verify_simulator_local_tick_trace_set import (
    _same_source_decision_bar,
)


def test_decision_bar_verification_preserves_engine_timestamp_phases() -> None:
    environment_event = {"decision_bar_time": "2025-01-14T22:13:00+03:00"}
    backtest_event = {
        "decision_bar_time": "2025-01-14T22:13:00+03:00",
        "decision_time": "2025-01-14T22:14:00+03:00",
    }

    assert _same_source_decision_bar(environment_event, backtest_event)


def test_decision_bar_verification_rejects_different_source_bars() -> None:
    environment_event = {"decision_bar_time": "2025-01-14T22:13:00+03:00"}
    backtest_event = {
        "decision_bar_time": "2025-01-14T22:14:00+03:00",
        "decision_time": "2025-01-14T22:14:00+03:00",
    }

    assert not _same_source_decision_bar(environment_event, backtest_event)
