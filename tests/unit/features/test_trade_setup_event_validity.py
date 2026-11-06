from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from decisioning.trade_setup import trade_setup_candidate_id
from features.context.trade_setup_candidates import (
    trade_setup_candidate_event_identities,
    trade_setup_candidate_event_time_fields,
    trade_setup_event_is_current,
)

_FAMILY_STATE = {
    "po3": ("po3_distribution_after_ifvg", "ifvg_{side}_active"),
    "order_block": ("ob_{side}_active",),
    "standard_deviation": ("standard_deviation_leg_valid",),
    "fvg_retest": ("fvg_{side}_active",),
    "ifvg_retest": ("ifvg_{side}_active",),
    "ifvg_unretested": ("ifvg_{side}_active",),
}


def _setup_row(idea: str, timeframe: str = "M5", direction: int = 1) -> tuple[int, dict[str, Any]]:
    candidate_id = trade_setup_candidate_id(idea, timeframe, direction)
    prefix = "" if timeframe == "M1" else f"{timeframe}_"
    side = "bull" if direction == 1 else "bear"
    row: dict[str, Any] = {
        f"entry_idea_{idea}_{timeframe}_{'long' if direction == 1 else 'short'}": 1.0,
        f"{prefix}fvg_{side}_active": 1.0,
        f"{prefix}ifvg_{side}_active": 1.0,
        f"{prefix}ob_{side}_active": 1.0,
        f"{prefix}standard_deviation_leg_valid": 1.0,
        f"{prefix}standard_deviation_leg_direction": float(direction),
        f"{prefix}po3_distribution_after_ifvg": 1.0,
        f"{prefix}po3_distribution_direction": float(direction),
    }
    for column, scale in trade_setup_candidate_event_time_fields(candidate_id):
        row[column] = 100.0 / scale
    return candidate_id, row


@pytest.mark.parametrize("idea", tuple(_FAMILY_STATE))
@pytest.mark.parametrize("direction", (1, -1))
@pytest.mark.parametrize("timeframe", ("M1", "M5"))
def test_pending_setup_remains_valid_while_its_source_event_is_active(
    idea: str, direction: int, timeframe: str
) -> None:
    candidate_id, row = _setup_row(idea, timeframe=timeframe, direction=direction)
    identity = trade_setup_candidate_event_identities(row, (candidate_id,))[0]

    assert identity.status == "identified"
    assert trade_setup_event_is_current(identity, row) == (True, "")

    prefix = "" if timeframe == "M1" else f"{timeframe}_"
    for state_column in _FAMILY_STATE[idea]:
        invalidated = dict(row)
        column = state_column.format(side="bull" if direction == 1 else "bear")
        invalidated[f"{prefix}{column}"] = 0.0
        assert trade_setup_event_is_current(identity, invalidated) == (
            False,
            "source_setup_invalidated",
        )


@pytest.mark.parametrize("idea", tuple(_FAMILY_STATE))
@pytest.mark.parametrize("direction", (1, -1))
@pytest.mark.parametrize("timeframe", ("M1", "M5"))
def test_pending_setup_cancels_when_its_source_event_is_replaced(
    idea: str, direction: int, timeframe: str
) -> None:
    candidate_id, row = _setup_row(idea, timeframe=timeframe, direction=direction)
    identity = trade_setup_candidate_event_identities(row, (candidate_id,))[0]
    replaced = dict(row)
    source_field, _ = trade_setup_candidate_event_time_fields(candidate_id)[-1]
    replaced[source_field] = float(replaced[source_field]) + 1.0

    assert trade_setup_event_is_current(identity, replaced) == (
        False,
        "source_setup_replaced",
    )


@pytest.mark.parametrize("idea", ("order_block", "fvg_retest", "ifvg_retest"))
@pytest.mark.parametrize("timeframe", ("M1", "M5"))
def test_pending_retest_setup_survives_absent_confirmation_pulse(idea: str, timeframe: str) -> None:
    candidate_id, row = _setup_row(idea, timeframe=timeframe)
    identity = trade_setup_candidate_event_identities(row, (candidate_id,))[0]
    pulse_field = next(
        field
        for field, _ in trade_setup_candidate_event_time_fields(candidate_id)
        if "retest_confirmed_at_time_ns" in field
    )
    later_row = dict(row)
    later_row[pulse_field] = float("nan")

    assert trade_setup_event_is_current(identity, later_row) == (True, "")

    expired_zone = dict(later_row)
    prefix = "" if timeframe == "M1" else f"{timeframe}_"
    side = "bull"  # _setup_row defaults to the long direction.
    active_column = _FAMILY_STATE[idea][0].format(side=side)
    expired_zone[f"{prefix}{active_column}"] = 0.0
    assert trade_setup_event_is_current(identity, expired_zone) == (
        False,
        "source_setup_invalidated",
    )


@pytest.mark.parametrize("idea", ("order_block", "fvg_retest", "ifvg_retest"))
def test_pending_retest_setup_cancels_on_new_confirmation_event(idea: str) -> None:
    candidate_id, row = _setup_row(idea)
    identity = trade_setup_candidate_event_identities(row, (candidate_id,))[0]
    pulse_field = next(
        field
        for field, _ in trade_setup_candidate_event_time_fields(candidate_id)
        if "retest_confirmed_at_time_ns" in field
    )
    replaced = dict(row)
    replaced[pulse_field] = float(replaced[pulse_field]) + 1.0

    assert trade_setup_event_is_current(identity, replaced) == (
        False,
        "source_setup_replaced",
    )


def test_pending_retest_setup_fails_closed_on_malformed_or_missing_pulse_state() -> None:
    candidate_id, row = _setup_row("ifvg_retest")
    identity = trade_setup_candidate_event_identities(row, (candidate_id,))[0]
    pulse_field = next(
        field
        for field, _ in trade_setup_candidate_event_time_fields(candidate_id)
        if "retest_confirmed_at_time_ns" in field
    )

    malformed = dict(row)
    malformed[pulse_field] = "not-a-timestamp"
    assert trade_setup_event_is_current(identity, malformed) == (
        False,
        "source_setup_invalidated",
    )

    missing = dict(row)
    del missing[pulse_field]
    assert trade_setup_event_is_current(identity, missing) == (
        False,
        "source_setup_state_unavailable",
    )


def test_pending_retest_setup_fails_closed_on_partially_missing_duplicate_timestamp() -> None:
    candidate_id, row = _setup_row("ifvg_retest")
    pulse_field = next(
        field
        for field, _ in trade_setup_candidate_event_time_fields(candidate_id)
        if "retest_confirmed_at_time_ns" in field
    )
    duplicated = pd.Series(
        [*row.values(), float("nan")],
        index=[*row.keys(), pulse_field],
    )
    identity = trade_setup_candidate_event_identities(row, (candidate_id,))[0]

    assert trade_setup_event_is_current(identity, duplicated) == (
        False,
        "source_setup_invalidated",
    )
    ambiguous_identity = trade_setup_candidate_event_identities(duplicated, (candidate_id,))[0]
    assert ambiguous_identity.status == "conflicting_source_event_times"


def test_pending_setup_fails_closed_when_identity_is_unavailable() -> None:
    _, row = _setup_row("ifvg_unretested")

    assert trade_setup_event_is_current(None, row) == (
        False,
        "source_setup_identity_unavailable",
    )


def test_pending_setup_fails_closed_when_active_state_is_missing() -> None:
    candidate_id, row = _setup_row("fvg_retest")
    identity = trade_setup_candidate_event_identities(row, (candidate_id,))[0]
    del row["M5_fvg_bull_active"]

    assert trade_setup_event_is_current(identity, row) == (
        False,
        "source_setup_state_unavailable",
    )


def test_pending_setup_fails_closed_on_conflicting_duplicate_active_state() -> None:
    candidate_id, row = _setup_row("fvg_retest")
    identity = trade_setup_candidate_event_identities(row, (candidate_id,))[0]
    active_column = "M5_fvg_bull_active"
    ambiguous_row = pd.Series(
        [*row.values(), 0.0],
        index=[*row.keys(), active_column],
    )

    assert trade_setup_event_is_current(identity, ambiguous_row) == (
        False,
        "source_setup_invalidated",
    )


@pytest.mark.parametrize("direction", (1, -1))
@pytest.mark.parametrize("timeframe", ("M1", "M5"))
def test_po3_pending_setup_cancels_when_distribution_direction_changes(
    direction: int, timeframe: str
) -> None:
    candidate_id, row = _setup_row("po3", timeframe=timeframe, direction=direction)
    identity = trade_setup_candidate_event_identities(row, (candidate_id,))[0]
    prefix = "" if timeframe == "M1" else f"{timeframe}_"
    row[f"{prefix}po3_distribution_direction"] = float(-direction)

    assert trade_setup_event_is_current(identity, row) == (
        False,
        "source_setup_invalidated",
    )


def test_po3_pending_setup_cancels_when_a_new_sweep_replaces_its_source() -> None:
    candidate_id, row = _setup_row("po3")
    identity = trade_setup_candidate_event_identities(row, (candidate_id,))[0]
    replaced = dict(row)
    sweep_time_field = trade_setup_candidate_event_time_fields(candidate_id)[0][0]
    replaced[sweep_time_field] = float(replaced[sweep_time_field]) + 1.0

    assert trade_setup_event_is_current(identity, replaced) == (
        False,
        "source_setup_replaced",
    )


@pytest.mark.parametrize("direction", (1, -1))
@pytest.mark.parametrize("timeframe", ("M1", "M5"))
def test_standard_deviation_setup_cancels_when_leg_direction_changes(
    direction: int, timeframe: str
) -> None:
    candidate_id, row = _setup_row("standard_deviation", timeframe=timeframe, direction=direction)
    identity = trade_setup_candidate_event_identities(row, (candidate_id,))[0]
    prefix = "" if timeframe == "M1" else f"{timeframe}_"
    row[f"{prefix}standard_deviation_leg_direction"] = float(-direction)

    assert trade_setup_event_is_current(identity, row) == (
        False,
        "source_setup_invalidated",
    )
