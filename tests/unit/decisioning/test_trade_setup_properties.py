from __future__ import annotations

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from decisioning.actions import build_action_schema, build_discrete_trading_action_schema
from decisioning.trade_setup import (
    TRADE_SETUP_DIRECTIONS,
    TRADE_SETUP_IDEAS,
    TRADE_SETUP_TIMEFRAMES,
    build_trade_setup_action_schema,
    trade_setup_candidate,
    trade_setup_candidate_id,
    trade_setup_center,
    trade_setup_id_from_box,
)


def test_default_action_schema_keeps_the_legacy_coordinate_layout() -> None:
    schema = build_action_schema()

    assert schema.names == ("intensity", "stop", "risk", "target", "exit")
    assert schema.has_direction is False
    assert schema.has_sl_mode is False
    assert schema.has_tp_mode is False
    assert schema.has_multi_tp is False
    assert schema.has_simplex is False


def test_discrete_action_schema_is_the_fixed_twenty_choice_menu() -> None:
    schema = build_discrete_trading_action_schema()

    assert schema.width == 20
    assert schema.key == "discrete-20"
    assert schema.names[0] == "hold"
    assert schema.names[-1] == "exit"
    assert len(set(schema.names)) == 20
    with pytest.raises(ValueError, match="requires 20 choices"):
        build_discrete_trading_action_schema(n_actions=19)


@given(
    idea=st.sampled_from(TRADE_SETUP_IDEAS),
    timeframe=st.sampled_from(TRADE_SETUP_TIMEFRAMES),
    direction=st.sampled_from(TRADE_SETUP_DIRECTIONS),
)
@settings(max_examples=200, derandomize=True, database=None)
def test_semantic_trade_setup_round_trips_through_id_and_box(
    idea: str, timeframe: str, direction: int
) -> None:
    candidate_id = trade_setup_candidate_id(idea, timeframe, direction)
    candidate = trade_setup_candidate(candidate_id)

    assert (candidate.idea, candidate.setup_timeframe, candidate.direction) == (
        idea,
        timeframe,
        direction,
    )
    assert trade_setup_id_from_box(trade_setup_center(candidate_id)) == candidate_id


@given(
    has_sl=st.booleans(),
    has_tp=st.booleans(),
    has_multi_tp=st.booleans(),
    has_simplex=st.booleans(),
)
@settings(max_examples=32, derandomize=True, database=None)
def test_action_schema_flag_combinations_have_unique_coordinates(
    has_sl: bool, has_tp: bool, has_multi_tp: bool, has_simplex: bool
) -> None:
    if has_simplex and not has_multi_tp:
        return

    schema = build_trade_setup_action_schema(
        has_sl_mode=has_sl,
        has_tp_mode=has_tp,
        has_multi_tp=has_multi_tp,
        has_simplex=has_simplex,
    )

    assert len(schema.names) == schema.width == len(set(schema.names))
    assert schema.names[0] == "trade_setup"
    assert schema.indices["trade_setup"] == 0
    assert ("sl_mode" in schema.names) is has_sl
    assert ("tp_mode" in schema.names) is has_tp
    assert ("z1" in schema.names) is has_simplex


@given(
    has_direction=st.booleans(),
    has_sl_mode=st.booleans(),
    has_tp_mode=st.booleans(),
    has_multi_tp=st.booleans(),
    has_simplex=st.booleans(),
)
@settings(max_examples=64, derandomize=True, database=None)
def test_action_schema_flag_combinations_keep_order_and_json_contract(
    has_direction: bool,
    has_sl_mode: bool,
    has_tp_mode: bool,
    has_multi_tp: bool,
    has_simplex: bool,
) -> None:
    if has_simplex and not has_multi_tp:
        with pytest.raises(ValueError, match="simplex fractions require multi-TP"):
            build_action_schema(
                has_direction=has_direction,
                has_sl_mode=has_sl_mode,
                has_tp_mode=has_tp_mode,
                has_multi_tp=has_multi_tp,
                has_simplex=has_simplex,
            )
        return

    schema = build_action_schema(
        has_direction=has_direction,
        has_sl_mode=has_sl_mode,
        has_tp_mode=has_tp_mode,
        has_multi_tp=has_multi_tp,
        has_simplex=has_simplex,
    )
    expected_coordinates = ["direction"] if has_direction else []
    expected_coordinates.extend(("intensity", "stop", "risk"))
    expected_coordinates.extend(("tp1_sel", "tp2_sel", "tp3_sel") if has_multi_tp else ("target",))
    if has_sl_mode:
        expected_coordinates.append("sl_mode")
    if has_tp_mode:
        expected_coordinates.append("tp_mode")
    if has_simplex:
        expected_coordinates.extend(("z1", "z2"))
    expected_coordinates.append("exit")

    serialized = json.loads(json.dumps(schema.to_dict()))
    expected_contract = {
        "version": schema.version,
        "key": schema.key,
        "width": len(expected_coordinates),
        "coordinates": expected_coordinates,
        "has_direction": has_direction,
        "has_sl_mode": has_sl_mode,
        "has_tp_mode": has_tp_mode,
        "has_multi_tp": has_multi_tp,
        "has_simplex": has_simplex,
    }
    assert schema.names == tuple(expected_coordinates)
    assert schema.width == len(expected_coordinates)
    assert len(schema.names) == len(set(schema.names))
    assert serialized == expected_contract

    restored = build_action_schema(
        has_direction=serialized["has_direction"],
        has_sl_mode=serialized["has_sl_mode"],
        has_tp_mode=serialized["has_tp_mode"],
        has_multi_tp=serialized["has_multi_tp"],
        has_simplex=serialized["has_simplex"],
    )
    assert restored.to_dict() == serialized
