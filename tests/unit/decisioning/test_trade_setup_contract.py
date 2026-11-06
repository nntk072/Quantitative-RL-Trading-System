from __future__ import annotations

import pytest

from decisioning.trade_setup import (
    NO_TRADE_ID,
    TRADE_SETUP_CANDIDATES,
    TRADE_SETUP_CATEGORY_COUNT,
    TRADE_SETUP_EXECUTION_ACTION_VERSION,
    build_trade_setup_action_schema,
    decode_trade_setup_execution_choice,
    decode_trade_setup_geometry_choice,
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


def test_market_or_limit_entry_uses_a_distinct_named_action_schema() -> None:
    schema = build_trade_setup_action_schema(has_entry_execution=True)

    assert schema.version == TRADE_SETUP_EXECUTION_ACTION_VERSION
    assert schema.names == (
        "trade_setup",
        "stop",
        "risk",
        "target",
        "entry_execution",
        "limit_offset_atr",
        "limit_ttl_bars",
        "exit",
    )
    description = schema.to_dict()
    assert description["has_entry_execution"] is True
    assert description["conditional_coordinates"] == ["limit_offset_atr", "limit_ttl_bars"]


def test_legacy_setup_action_schema_retains_its_original_version_and_width() -> None:
    schema = build_trade_setup_action_schema()

    assert schema.version == "trade-setup-overlay-action-v1"
    assert schema.names == ("trade_setup", "stop", "risk", "target", "exit")


def test_entry_execution_action_decodes_market_and_conditional_limit_controls() -> None:
    schema = build_trade_setup_action_schema(has_entry_execution=True)
    action = [0.0] * schema.width
    indices = schema.indices
    action[indices["entry_execution"]] = -0.01
    action[indices["limit_offset_atr"]] = 1.0
    action[indices["limit_ttl_bars"]] = -1.0

    market = decode_trade_setup_execution_choice(
        action,
        schema,
        max_limit_offset_atr=1.5,
        max_limit_ttl_bars=60,
    )

    assert market.order_type == "market"
    assert market.limit_offset_atr == pytest.approx(1.5)
    assert market.ttl_bars == 1

    action[indices["entry_execution"]] = 0.0
    action[indices["limit_offset_atr"]] = 0.0
    action[indices["limit_ttl_bars"]] = 1.0
    limit = decode_trade_setup_execution_choice(
        action,
        schema,
        max_limit_offset_atr=1.5,
        max_limit_ttl_bars=60,
    )

    assert limit.order_type == "limit"
    assert limit.limit_offset_atr == pytest.approx(0.75)
    assert limit.ttl_bars == 60


@pytest.mark.parametrize(
    ("offset", "ttl"),
    [(0.0, 0), (-1.0, 0), (1.0, -1)],
)
def test_entry_execution_decoder_rejects_invalid_bounds(offset: float, ttl: int) -> None:
    schema = build_trade_setup_action_schema(has_entry_execution=True)
    with pytest.raises(ValueError):
        decode_trade_setup_execution_choice(
            [0.0] * schema.width,
            schema,
            max_limit_offset_atr=offset,
            max_limit_ttl_bars=ttl,
        )


def test_setup_geometry_decoder_maps_stop_target_and_exit_coordinates() -> None:
    schema = build_trade_setup_action_schema()
    action = [0.0] * schema.width
    action[schema.indices["stop"]] = -0.5
    action[schema.indices["target"]] = 0.6
    action[schema.indices["exit"]] = -0.6

    choice = decode_trade_setup_geometry_choice(action, schema)

    assert choice.stop_anchor_fraction == pytest.approx(0.5)
    assert choice.target_fraction == pytest.approx(0.8)
    assert choice.target_selections is None
    assert choice.simplex_logits is None
    assert choice.exit_mode == "structural"

    action[schema.indices["exit"]] = 1.0
    assert decode_trade_setup_geometry_choice(action, schema).exit_mode == "ema_21"
    assert (
        decode_trade_setup_geometry_choice(action, schema, allow_ema_exit=False).exit_mode
        == "structural"
    )


def test_setup_geometry_decoder_preserves_multi_target_slots_and_simplex_inputs() -> None:
    schema = build_trade_setup_action_schema(has_multi_tp=True, has_simplex=True)
    action = [0.0] * schema.width
    for name, value in {
        "stop": -1.0,
        "tp1_sel": -0.5,
        "tp2_sel": 0.0,
        "tp3_sel": 0.75,
        "z1": -0.25,
        "z2": 0.5,
    }.items():
        action[schema.indices[name]] = value

    choice = decode_trade_setup_geometry_choice(action, schema)

    assert choice.stop_anchor_fraction == pytest.approx(0.0)
    assert choice.target_fraction == pytest.approx(0.875)
    assert choice.target_selections == pytest.approx((0.25, 0.5, 0.875))
    assert choice.simplex_logits == pytest.approx((0.375, 0.75))


def test_setup_management_decoder_selects_or_defers_sl_and_tp_modes() -> None:
    schema = build_trade_setup_action_schema(has_sl_mode=True, has_tp_mode=True)
    action = [0.0] * schema.width
    action[schema.indices["sl_mode"]] = 1.0
    action[schema.indices["tp_mode"]] = -1.0

    choice = decode_trade_setup_geometry_choice(
        action,
        schema,
        default_sl_mode="fixed",
        default_tp_mode="trailing",
    )

    assert choice.sl_mode == "trailing"
    assert choice.sl_mode_explicit is True
    assert choice.tp_mode == "fixed"
    assert choice.tp_mode_explicit is True
    assert choice.has_sl_mode is True
    assert choice.has_tp_mode is True

    action[schema.indices["sl_mode"]] = 0.0
    action[schema.indices["tp_mode"]] = 0.0
    deferred = decode_trade_setup_geometry_choice(
        action,
        schema,
        default_sl_mode="breakeven",
        default_tp_mode="trailing",
    )
    assert (deferred.sl_mode, deferred.sl_mode_explicit) == ("breakeven", False)
    assert (deferred.tp_mode, deferred.tp_mode_explicit) == ("trailing", False)


@pytest.mark.parametrize("value", [-1.0001, 1.0001, float("nan"), float("inf")])
def test_setup_geometry_decoder_rejects_non_normalized_actions(value: float) -> None:
    schema = build_trade_setup_action_schema()
    action = [0.0] * schema.width
    action[schema.indices["stop"]] = value

    with pytest.raises(ValueError, match=r"finite and in \[-1, 1\]"):
        decode_trade_setup_geometry_choice(action, schema)
