"""Causal entry evidence preserves direction and setup provenance."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from simulation.entry_evidence import build_entry_evidence


def _strategy(direction: int = 0) -> SimpleNamespace:
    return SimpleNamespace(context_direction=lambda _row: direction, name="test")


def test_retest_infers_direction_and_captures_finite_setup_provenance() -> None:
    bars_index = pd.date_range("2026-01-05 14:30", periods=3, freq="min", tz="UTC")
    row = pd.Series(
        {
            "fvg_retest_bull": 1.0,
            "ifvg_retest_bull": 1.0,
            "sweep_low": 1.0,
            "sweep_low_level": 99.5,
            "sweep_low_wick": 99.2,
            "sweep_low_ref_tf_code": 1.0,
            "sweep_low_pivot_time_ns": float(bars_index[1].value),
            "ifvg_bull_low": 99.8,
            "ifvg_bull_high": 100.2,
            "sweep_high_level": float("nan"),
        }
    )

    evidence = build_entry_evidence(
        strategy=_strategy(),
        feature_row=row,
        bar=2,
        candidate=None,
        bars_index=bars_index,
        state_machine_enabled=True,
    )

    assert evidence.direction == 1
    assert evidence.retest_confirmed
    assert evidence.arm_condition
    assert evidence.setup_types == ("fvg_reaction", "ifvg", "ifvg_reaction", "sweep")
    assert evidence.setup_levels_snapshot == (
        ("ifvg_bull_high", 100.2),
        ("ifvg_bull_low", 99.8),
        ("sweep_low_level", 99.5),
        ("sweep_low_pivot_bar", 1.0),
        ("sweep_low_ref_tf_code", 1.0),
        ("sweep_low_wick", 99.2),
    )


def test_simultaneous_opposing_retests_are_invalid_and_do_not_infer_direction() -> None:
    row = pd.Series({"ifvg_retest_bull": 1.0, "fvg_retest_bear": 1.0})

    evidence = build_entry_evidence(
        strategy=_strategy(),
        feature_row=row,
        bar=4,
        candidate=None,
        bars_index=None,
        state_machine_enabled=True,
    )

    assert evidence.invalidated
    assert evidence.direction == 0
    assert not evidence.retest_confirmed
    assert not evidence.arm_condition


def test_explicit_strategy_direction_takes_precedence_over_opposing_retest() -> None:
    row = pd.Series({"fvg_retest_bull": 1.0, "sweep_high": 1.0})

    evidence = build_entry_evidence(
        strategy=_strategy(direction=-1),
        feature_row=row,
        bar=5,
        candidate=None,
        bars_index=None,
        state_machine_enabled=False,
    )

    assert evidence.direction == -1
    assert not evidence.retest_confirmed
    assert evidence.setup_types == ("sweep",)
    assert evidence.setup_levels_snapshot == ()


def test_sweep_pivot_falls_back_to_legacy_timestamp_and_aligns_timezone() -> None:
    bars_index = pd.date_range("2026-01-05 14:30", periods=3, freq="min", tz="UTC")
    row = pd.Series(
        {
            "sweep_low": 1.0,
            "sweep_low_level": 99.5,
            "sweep_low_pivot_time_ns": "invalid-nanoseconds",
            "last_swing_low_time": "2026-01-05 14:31",
        }
    )

    evidence = build_entry_evidence(
        strategy=_strategy(direction=1),
        feature_row=row,
        bar=2,
        candidate=None,
        bars_index=bars_index,
        state_machine_enabled=True,
    )

    assert evidence.setup_levels_snapshot == (
        ("sweep_low_level", 99.5),
        ("sweep_low_pivot_bar", 1.0),
    )
