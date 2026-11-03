"""Tests for diagnostic PO3 setup-sequence lifecycle projection."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal, assert_series_equal

from features.po3 import build_po3_setup_lifecycle_ledger
from features.po3.ifvg_state import build_po3_ifvg_state

_STATE_COLUMNS = (
    "po3_setup_id",
    "po3_manipulation_direction",
    "po3_manipulation_active",
    "po3_manipulation_end",
    "po3_waiting_ifvg",
    "po3_ifvg_confirmed",
    "po3_distribution",
    "po3_distribution_after_ifvg",
    "po3_sweep_reference",
    "po3_sweep_reference_tf_code",
    "po3_sweep_pivot_time_ns",
    "po3_sweep_confirmed_at_ns",
    "po3_sweep_time_ns",
    "po3_reclaim_time_ns",
    "po3_ifvg_time_ns",
    "po3_ifvg_fvg_origin_bar",
    "po3_ifvg_fvg_origin_time_ns",
    "po3_sweep_conflict",
)


def _state_frame() -> pd.DataFrame:
    index = pd.date_range("2025-01-06 16:30", periods=10, freq="1min", tz="UTC")
    state = pd.DataFrame(0.0, index=index, columns=_STATE_COLUMNS)
    state.loc[index[2:7], "po3_setup_id"] = 1.0
    state.loc[index[2:7], "po3_manipulation_direction"] = -1.0
    state.loc[index[2], "po3_manipulation_active"] = 1.0
    state.loc[index[3], "po3_manipulation_end"] = 1.0
    state.loc[index[3], "po3_waiting_ifvg"] = 1.0
    state.loc[index[4:7], "po3_distribution"] = 1.0
    state.loc[index[4], "po3_ifvg_confirmed"] = 1.0
    state.loc[index[4:7], "po3_distribution_after_ifvg"] = 1.0
    state.loc[index[2:7], "po3_sweep_reference"] = 98.5
    state.loc[index[2:7], "po3_sweep_reference_tf_code"] = 1.0
    state.loc[index[2:7], "po3_sweep_time_ns"] = index[2].value
    state.loc[index[3:7], "po3_reclaim_time_ns"] = index[3].value
    state.loc[index[4:7], "po3_ifvg_time_ns"] = index[4].value
    state.loc[index[4:7], "po3_ifvg_fvg_origin_bar"] = 2.0
    state.loc[index[4:7], "po3_ifvg_fvg_origin_time_ns"] = index[2].value
    state.loc[index[6], "po3_sweep_conflict"] = 1.0
    state.loc[index[7:10], "po3_setup_id"] = 2.0
    state.loc[index[7:10], "po3_manipulation_direction"] = 1.0
    state.loc[index[7:10], "po3_manipulation_active"] = 1.0
    state.loc[index[7:10], "po3_sweep_reference"] = 102.0
    state.loc[index[7:10], "po3_sweep_time_ns"] = index[7].value
    return state


def test_ledger_records_phase_transitions_rearm_and_conflict_separately() -> None:
    state = _state_frame()
    original = state.copy(deep=True)

    ledger = build_po3_setup_lifecycle_ledger(state)

    assert_frame_equal(state, original)
    setups = ledger.loc[ledger["event_kind"] == "po3_setup_sequence"].reset_index(drop=True)
    assert len(setups) == 2
    assert setups.loc[0, "producer_setup_id"] == 1
    assert setups.loc[0, "direction"] == 1
    assert setups.loc[0, "start_index"] == 2
    assert setups.loc[0, "reclaim_index"] == 3
    assert setups.loc[0, "ifvg_confirmation_index"] == 4
    assert setups.loc[0, "ifvg_fvg_origin_bar"] == 2.0
    assert setups.loc[0, "phase_at_end"] == "distribution_after_ifvg"
    assert setups.loc[0, "termination_reason"] == "replaced_by_next_sweep"
    assert setups.loc[0, "replacement_setup_id"] == 2
    assert setups.loc[0, "replacement_time"] == state.index[7]
    assert setups.loc[1, "direction"] == -1
    assert setups.loc[1, "phase_at_end"] == "manipulation"
    assert setups.loc[1, "termination_reason"] == "input_end"

    conflicts = ledger.loc[ledger["event_kind"] == "conflicting_same_bar_sweeps"]
    assert len(conflicts) == 1
    assert pd.isna(conflicts.iloc[0]["producer_setup_id"])
    assert conflicts.iloc[0]["start_index"] == 6
    assert conflicts.iloc[0]["termination_reason"] == "same_bar_direction_conflict"


def test_ledger_preserves_exact_bar_event_nanoseconds() -> None:
    state = _state_frame()
    state.index = state.index + pd.Timedelta(123, unit="ns")

    setups = build_po3_setup_lifecycle_ledger(state).query("event_kind == 'po3_setup_sequence'")
    first = setups.iloc[0]

    assert first["sweep_time_ns"] == int(state.index[2].value)
    assert first["reclaim_time_ns"] == int(state.index[3].value)
    assert first["ifvg_confirmation_time_ns"] == int(state.index[4].value)
    assert first["ifvg_fvg_origin_time_ns"] == int(state.index[2].value)
    assert "sweep_pivot_time_source_float_ns" in setups.columns
    assert "sweep_confirmed_at_source_float_ns" in setups.columns


def test_finalized_setup_lifecycle_is_prefix_invariant() -> None:
    full = build_po3_setup_lifecycle_ledger(_state_frame())
    truncated_state = _state_frame().iloc[:9]
    prefix = build_po3_setup_lifecycle_ledger(truncated_state)

    full_first = full.loc[full["producer_setup_id"] == 1].iloc[0]
    prefix_first = prefix.loc[prefix["producer_setup_id"] == 1].iloc[0]
    assert_series_equal(full_first, prefix_first, check_names=False)


def test_ledger_extracts_reclaim_and_conflict_from_producer_output() -> None:
    index = pd.date_range("2025-01-06 16:30", periods=5, freq="1min", tz="UTC")
    bars = pd.DataFrame(
        {
            "high": [100.0, 101.0, 100.5, 102.0, 103.0],
            "low": [99.0, 97.0, 98.0, 100.0, 101.0],
            "close": [99.5, 98.0, 99.0, 101.5, 102.0],
        },
        index=index,
    )
    sweeps = pd.DataFrame(
        0.0,
        index=index,
        columns=[
            "sweep_low",
            "sweep_high",
            "sweep_low_level",
            "sweep_high_level",
        ],
    )
    sweeps.loc[index[1], ["sweep_low", "sweep_low_level"]] = [1.0, 98.5]
    sweeps.loc[index[3], ["sweep_low", "sweep_high"]] = [1.0, 1.0]
    ifvg = pd.DataFrame(
        {
            "ifvg_bull_confirmed": np.zeros(len(index)),
            "ifvg_bear_confirmed": np.zeros(len(index)),
            "ifvg_bull_fvg_origin_bar": np.full(len(index), np.nan),
            "ifvg_bear_fvg_origin_bar": np.full(len(index), np.nan),
            "_ifvg_bull_confirmation_tf_code": np.ones(len(index)),
            "_ifvg_bear_confirmation_tf_code": np.ones(len(index)),
            "ifvg_bull_low": np.zeros(len(index)),
            "ifvg_bull_high": np.zeros(len(index)),
            "ifvg_bear_low": np.zeros(len(index)),
            "ifvg_bear_high": np.zeros(len(index)),
        },
        index=index,
    )

    producer_state = build_po3_ifvg_state(bars, sweeps, ifvg)
    ledger = build_po3_setup_lifecycle_ledger(producer_state)
    setup = ledger.loc[ledger["event_kind"] == "po3_setup_sequence"].iloc[0]
    conflict = ledger.loc[ledger["event_kind"] == "conflicting_same_bar_sweeps"].iloc[0]

    assert setup["producer_setup_id"] == 1
    assert setup["start_index"] == 1
    assert setup["reclaim_index"] == 2
    assert setup["phase_at_end"] == "waiting_for_ifvg"
    assert conflict["start_index"] == 3


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_index",
        "non_monotone_ids",
        "id_gap",
        "missing_column",
    ],
)
def test_ledger_rejects_ambiguous_state(mutation: str) -> None:
    state = _state_frame()
    if mutation == "duplicate_index":
        state.index = pd.DatetimeIndex([*state.index[:-1], state.index[-2]])
    elif mutation == "non_monotone_ids":
        state.loc[state.index[7], "po3_setup_id"] = 0.0
    elif mutation == "id_gap":
        state.loc[state.index[7:10], "po3_setup_id"] = 3.0
    else:
        state = state.drop(columns=["po3_ifvg_time_ns"])

    with pytest.raises(ValueError):
        build_po3_setup_lifecycle_ledger(state)
