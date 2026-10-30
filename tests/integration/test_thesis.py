from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from decisioning.thesis import (
    NO_TRADE_ID,
    THESIS_CANDIDATES,
    THESIS_CATEGORY_COUNT,
    THESIS_DIRECTIONS,
    THESIS_IDEAS,
    THESIS_TIMEFRAMES,
    build_thesis_action_schema,
    thesis_candidate,
    thesis_candidate_id,
    thesis_center,
    thesis_id_from_box,
)
from features.context.thesis_candidates import active_thesis_candidates, thesis_candidate_mask


def test_thesis_catalog_has_stable_complete_semantic_mapping() -> None:
    assert THESIS_CATEGORY_COUNT == 109
    assert THESIS_CANDIDATES[NO_TRADE_ID].is_no_trade
    assert THESIS_CANDIDATES[NO_TRADE_ID].direction == 0
    assert len({candidate.candidate_id for candidate in THESIS_CANDIDATES}) == 109
    assert (
        len(
            {
                (candidate.idea, candidate.setup_timeframe, candidate.direction)
                for candidate in THESIS_CANDIDATES[1:]
            }
        )
        == 108
    )
    assert {candidate.idea for candidate in THESIS_CANDIDATES[1:]} == set(THESIS_IDEAS)
    assert {candidate.setup_timeframe for candidate in THESIS_CANDIDATES[1:]} == set(
        THESIS_TIMEFRAMES
    )
    assert {candidate.direction for candidate in THESIS_CANDIDATES[1:]} == set(THESIS_DIRECTIONS)


def test_thesis_ids_and_box_centers_round_trip_exactly() -> None:
    for candidate in THESIS_CANDIDATES:
        candidate_id = candidate.candidate_id
        assert thesis_candidate(candidate_id) == candidate
        assert thesis_id_from_box(thesis_center(candidate_id)) == candidate_id
        if not candidate.is_no_trade:
            assert candidate.idea is not None
            assert candidate.setup_timeframe is not None
            assert (
                thesis_candidate_id(candidate.idea, candidate.setup_timeframe, candidate.direction)
                == candidate_id
            )


def test_thesis_action_schema_is_separate_from_legacy_overlay() -> None:
    schema = build_thesis_action_schema(
        has_sl_mode=True,
        has_tp_mode=True,
        has_multi_tp=True,
        has_simplex=True,
    )
    assert schema.version == "thesis-overlay-action-v1"
    assert schema.names == (
        "thesis",
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
    assert schema.width == 11
    assert schema.to_dict()["thesis_category_count"] == THESIS_CATEGORY_COUNT


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.01, 1.01])
def test_thesis_box_decoder_rejects_invalid_values(value: float) -> None:
    with pytest.raises(ValueError):
        thesis_id_from_box(value)


def test_candidate_mask_keeps_exact_timeframe_and_direction() -> None:
    row = pd.Series(
        {
            "entry_idea_fvg_retest_M5_long": 1.0,
            "entry_idea_fvg_retest_long": 1.0,
            "entry_idea_ifvg_retest_M5_long": 1.0,
            "entry_idea_ifvg_unretested_M15_short": 1.0,
        }
    )

    mask = thesis_candidate_mask(row)
    fvg_m5_long = thesis_candidate_id("fvg_retest", "M5", 1)
    ifvg_m5_long = thesis_candidate_id("ifvg_retest", "M5", 1)
    ifvg_m15_short = thesis_candidate_id("ifvg_unretested", "M15", -1)

    assert mask.shape == (109,)
    assert mask.dtype == np.float32
    assert mask[NO_TRADE_ID] == 1.0
    assert mask[fvg_m5_long] == 1.0
    assert mask[ifvg_m5_long] == 1.0
    assert mask[ifvg_m15_short] == 1.0
    assert mask[thesis_candidate_id("fvg_retest", "M1", 1)] == 0.0
    assert mask[thesis_candidate_id("fvg_retest", "M5", -1)] == 0.0
    assert int(mask.sum()) == 4


@pytest.mark.parametrize(
    ("idea", "column"),
    [
        ("po3", "entry_idea_po3_M5_long"),
        ("order_block", "entry_idea_order_block_M5_long"),
        ("standard_deviation", "entry_idea_standard_deviation_M5_long"),
        ("fvg_retest", "entry_idea_fvg_retest_M5_long"),
        ("ifvg_retest", "entry_idea_ifvg_retest_M5_long"),
        ("ifvg_unretested", "entry_idea_ifvg_unretested_M5_long"),
    ],
)
def test_each_entry_idea_has_exact_timeframe_candidate(idea: str, column: str) -> None:
    active = active_thesis_candidates(pd.Series({column: 1.0}))
    assert [(item.idea, item.setup_timeframe, item.direction) for item in active] == [
        (idea, "M5", 1)
    ]


def test_candidate_mask_handles_m1_and_nonfinite_values() -> None:
    row = pd.Series(
        {
            "entry_idea_order_block_M1_long": 1.0,
            "entry_idea_order_block_M3_long": np.nan,
            "entry_idea_order_block_M5_short": float("inf"),
        }
    )
    mask = thesis_candidate_mask(row)
    assert mask[thesis_candidate_id("order_block", "M1", 1)] == 1.0
    assert mask[thesis_candidate_id("order_block", "M3", 1)] == 0.0
    assert mask[thesis_candidate_id("order_block", "M5", -1)] == 0.0
    assert mask[NO_TRADE_ID] == 1.0
