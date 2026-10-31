from __future__ import annotations

import decisioning.thesis as legacy
import decisioning.trade_setup as current


def test_canonical_and_legacy_catalogs_preserve_ids_and_meaning() -> None:
    assert current.TRADE_SETUP_CATEGORY_COUNT == 109
    assert current.TRADE_SETUP_CANDIDATES[0].is_no_trade
    assert current.TRADE_SETUP_CANDIDATES == legacy.THESIS_CANDIDATES
    for candidate_id, candidate in enumerate(current.TRADE_SETUP_CANDIDATES):
        assert candidate.candidate_id == candidate_id
        assert legacy.thesis_candidate(candidate_id) == candidate
        assert legacy.ThesisCandidate is current.TradeSetupCandidate


def test_action_and_observation_wire_schemas_remain_compatible() -> None:
    current_action = current.build_trade_setup_action_schema(
        has_sl_mode=True, has_tp_mode=True, has_multi_tp=True, has_simplex=True
    )
    legacy_action = legacy.build_thesis_action_schema(
        has_sl_mode=True, has_tp_mode=True, has_multi_tp=True, has_simplex=True
    )
    assert current_action.width == legacy_action.width
    assert current_action.names != legacy_action.names
    assert current_action.to_dict()["kind"] == "trade_setup_overlay"
    assert current_action.to_dict()["trade_setup_candidate_schema_version"] == (
        "trade-setup-candidate-v1"
    )
    assert legacy_action.to_dict()["kind"] == "thesis_overlay"
    assert legacy_action.to_dict()["thesis_candidate_schema_version"] == "thesis-candidate-v1"
    assert current.trade_setup_observation_schema()["mask_key"] == "trade_setup_mask"
    assert legacy.thesis_observation_schema()["mask_key"] == "thesis_mask"
    assert (
        current.translate_legacy_thesis_observation_schema(legacy.thesis_observation_schema())
        == current.trade_setup_observation_schema()
    )


def test_candidate_box_encoding_matches_legacy_api() -> None:
    for candidate_id in (0, 1, 17, 54, 108):
        box_value = current.trade_setup_center(candidate_id)
        assert box_value == legacy.thesis_center(candidate_id)
        assert current.trade_setup_id_from_box(box_value) == candidate_id
        assert legacy.thesis_id_from_box(box_value) == candidate_id
