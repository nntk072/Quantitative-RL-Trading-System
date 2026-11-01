from __future__ import annotations

import pytest

from decisioning.trade_setup import (
    NO_TRADE_ID,
    TRADE_SETUP_CANDIDATES,
    TRADE_SETUP_CATEGORY_COUNT,
    build_trade_setup_action_schema,
    trade_setup_candidate,
    trade_setup_candidate_id,
    trade_setup_center,
    trade_setup_id_from_box,
    trade_setup_observation_schema,
)


def test_candidate_ids_and_semantics_round_trip_for_the_full_catalog() -> None:
    assert TRADE_SETUP_CATEGORY_COUNT == len(TRADE_SETUP_CANDIDATES) == 109
    assert trade_setup_candidate(NO_TRADE_ID).is_no_trade

    for candidate_id, candidate in enumerate(TRADE_SETUP_CANDIDATES):
        assert candidate.candidate_id == candidate_id
        assert trade_setup_id_from_box(trade_setup_center(candidate_id)) == candidate_id
        if candidate.is_no_trade:
            continue
        assert candidate.idea is not None
        assert candidate.setup_timeframe is not None
        assert (
            trade_setup_candidate_id(candidate.idea, candidate.setup_timeframe, candidate.direction)
            == candidate_id
        )


@pytest.mark.parametrize("value", [-1.0001, 1.0001, float("nan"), float("inf")])
def test_box_decoder_rejects_values_outside_its_finite_normalized_domain(value: float) -> None:
    with pytest.raises(ValueError):
        trade_setup_id_from_box(value)


def test_action_and_observation_schemas_use_canonical_coordinates() -> None:
    action_schema = build_trade_setup_action_schema(
        has_sl_mode=True, has_tp_mode=True, has_multi_tp=True, has_simplex=True
    )
    assert action_schema.names == (
        "trade_setup",
        "stop",
        "risk",
        "tp1_sel",
        "tp2_sel",
        "tp3_sel",
        "sl_mode",
        "tp_mode",
        "z1",
        "z2",
        "exit",
    )
    assert action_schema.indices["trade_setup"] == 0
    assert action_schema.to_dict()["kind"] == "trade_setup_overlay"
    assert action_schema.to_dict()["has_trade_setup"] is True
    assert trade_setup_observation_schema()["mask_key"] == "trade_setup_mask"


def test_simplex_action_requires_multi_target_layout() -> None:
    with pytest.raises(ValueError, match="simplex fractions require multi-TP"):
        build_trade_setup_action_schema(has_simplex=True)
