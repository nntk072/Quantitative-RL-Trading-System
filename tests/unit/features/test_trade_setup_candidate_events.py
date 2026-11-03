"""Source-time identity for exact trade-setup candidate categories."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from decisioning.trade_setup import (
    NO_TRADE_ID,
    TRADE_SETUP_CANDIDATES,
    TRADE_SETUP_CATEGORY_COUNT,
    trade_setup_candidate_id,
)
from features.context.entry_ideas import build_entry_idea_features
from features.context.trade_setup_candidates import (
    TRADE_SETUP_EVENT_IDENTITY_VERSION,
    TradeSetupEventIdentity,
    trade_setup_candidate_event_identities,
    trade_setup_candidate_event_time_fields,
    trade_setup_candidate_mask,
    trade_setup_event_identity_record,
)
from features.pipeline.schema import select_obs_columns
from market_data.transforms.align import align_timeframes


def _po3_candidate(
    sweep_time_ns: int,
    reclaim_time_ns: int,
    ifvg_confirmation_time_ns: int = 1_735_000_120_000_000_000,
    ifvg_origin_time_ns: int = 1_735_000_060_000_000_000,
) -> dict[str, float]:
    return {
        "entry_idea_po3_M5_long": 1.0,
        "M5_po3_sweep_time_ns": float(sweep_time_ns),
        "M5_po3_reclaim_time_ns": float(reclaim_time_ns),
        "M5_ifvg_bull_confirmed_at_time_ns": float(ifvg_confirmation_time_ns),
        "M5_po3_ifvg_fvg_origin_time_ns": float(ifvg_origin_time_ns),
    }


def test_source_event_identity_is_stable_for_one_active_candidate() -> None:
    first = trade_setup_candidate_event_identities(
        _po3_candidate(1_735_000_000_000_000_000, 1_735_000_060_000_000_000)
    )
    repeated = trade_setup_candidate_event_identities(
        _po3_candidate(1_735_000_000_000_000_000, 1_735_000_060_000_000_000)
    )

    assert first == repeated
    assert first[0].candidate_id == trade_setup_candidate_id("po3", "M5", 1)
    assert first[0].status == "identified"
    assert first[0].source_event_id is not None
    assert first[0].source_event_id.startswith(f"{TRADE_SETUP_EVENT_IDENTITY_VERSION}:po3:M5:1:")


def test_event_identity_record_preserves_version_status_and_source_times() -> None:
    identity = TradeSetupEventIdentity(
        candidate_id=trade_setup_candidate_id("po3", "M5", 1),
        source_event_id="test-event-id",
        source_event_times_ns=(("M5_po3_sweep_time_ns", 100),),
        status="identified",
    )

    assert trade_setup_event_identity_record(None) == {}
    assert trade_setup_event_identity_record(identity) == {
        "trade_setup_event_identity_version": TRADE_SETUP_EVENT_IDENTITY_VERSION,
        "trade_setup_source_event_id": "test-event-id",
        "trade_setup_source_event_identity_status": "identified",
        "trade_setup_source_event_times_ns": [{"field": "M5_po3_sweep_time_ns", "time_ns": 100}],
    }


def test_selected_candidate_lookup_avoids_unselected_active_categories() -> None:
    row = _po3_candidate(1_735_000_000_000_000_000, 1_735_000_060_000_000_000)
    row.update(
        {
            "entry_idea_fvg_retest_M1_short": 1.0,
            "fvg_bear_retest_confirmed_at_time_ns": 1_735_000_120_000_000_000,
            "fvg_bear_retest_origin_time_ns": 1_735_000_060_000_000_000,
        }
    )
    selected_id = trade_setup_candidate_id("fvg_retest", "M1", -1)

    identities = trade_setup_candidate_event_identities(row, candidate_ids=(selected_id,))

    assert len(identities) == 1
    assert identities[0].candidate_id == selected_id
    assert identities[0].status == "identified"


def test_candidate_event_time_fields_preserve_source_units_and_order() -> None:
    fields = trade_setup_candidate_event_time_fields(
        trade_setup_candidate_id("order_block", "M5", 1)
    )

    assert fields == (
        ("M5_ob_bull_origin_time_ms", 1_000_000),
        ("M5_ob_bull_retest_confirmed_at_time_ns", 1),
    )


def test_po3_event_time_fields_include_matching_ifvg_confirmation() -> None:
    m1_long = trade_setup_candidate_event_time_fields(trade_setup_candidate_id("po3", "M1", 1))
    m5_short = trade_setup_candidate_event_time_fields(trade_setup_candidate_id("po3", "M5", -1))

    assert m1_long == (
        ("po3_sweep_time_ns", 1),
        ("po3_reclaim_time_ns", 1),
        ("ifvg_bull_confirmed_at_time_ns", 1),
        ("ifvg_bull_fvg_origin_time_ns", 1),
    )
    assert m5_short == (
        ("M5_po3_sweep_time_ns", 1),
        ("M5_po3_reclaim_time_ns", 1),
        ("M5_ifvg_bear_confirmed_at_time_ns", 1),
        ("M5_po3_ifvg_fvg_origin_time_ns", 1),
    )
    m1_row = {
        "entry_idea_po3_M1_long": 1.0,
        "po3_sweep_time_ns": 100.0,
        "po3_reclaim_time_ns": 200.0,
        "ifvg_bull_confirmed_at_time_ns": 300.0,
        "ifvg_bull_fvg_origin_time_ns": 250.0,
    }
    m1_identity = trade_setup_candidate_event_identities(m1_row)[0]
    assert m1_identity.status == "identified"
    assert m1_identity.source_event_times_ns[-2:] == (
        ("ifvg_bull_confirmed_at_time_ns", 300),
        ("ifvg_bull_fvg_origin_time_ns", 250),
    )


def test_mtf_po3_identity_uses_confirmed_ifvg_time_after_source_close() -> None:
    tz = "Etc/GMT-3"
    source_time = pd.Timestamp("2025-01-06 16:30", tz=tz)
    close_time = pd.Timestamp("2025-01-06 16:35", tz=tz)
    m1_index = pd.DatetimeIndex(
        [source_time + pd.Timedelta(minutes=4), close_time, close_time + pd.Timedelta(minutes=1)]
    )
    source = pd.DataFrame(
        {
            "po3_distribution": [1.0],
            "po3_distribution_direction": [1.0],
            "po3_distribution_after_ifvg": [1.0],
            "ifvg_bull_active": [1.0],
            "po3_sweep_time_ns": [1_735_000_000_000_000_000],
            "po3_reclaim_time_ns": [1_735_000_060_000_000_000],
            "ifvg_bull_confirmed_at_time_ns": [1_735_000_120_000_000_000],
            "po3_ifvg_fvg_origin_time_ns": [source_time.value],
        },
        index=pd.DatetimeIndex([source_time]),
    )
    aligned = align_timeframes(
        pd.DataFrame({"close": [100.0, 101.0, 102.0]}, index=m1_index),
        {"M5": source},
        availability_times={"M5": pd.Series([close_time], index=source.index)},
    )
    aligned = pd.concat([aligned, build_entry_idea_features(aligned)], axis=1)
    candidate_id = trade_setup_candidate_id("po3", "M5", 1)

    assert aligned.loc[m1_index[0], "entry_idea_po3_M5_long"] == 0.0
    assert aligned.loc[m1_index[1], "entry_idea_po3_M5_long"] == 1.0
    identity = trade_setup_candidate_event_identities(
        aligned.loc[m1_index[1]], candidate_ids=(candidate_id,)
    )[0]
    assert identity.status == "identified"
    assert identity.source_event_times_ns == (
        ("M5_po3_sweep_time_ns", 1_735_000_000_000_000_000),
        ("M5_po3_reclaim_time_ns", 1_735_000_060_000_000_000),
        ("M5_ifvg_bull_confirmed_at_time_ns", 1_735_000_120_000_000_000),
        ("M5_po3_ifvg_fvg_origin_time_ns", source_time.value),
    )


def test_mtf_swing_candidate_uses_its_own_prefixed_source_leg_times() -> None:
    candidate_id = trade_setup_candidate_id("standard_deviation", "M5", 1)
    row = {
        "entry_idea_standard_deviation_M5_long": 1.0,
        "standard_deviation_leg_start_time_ns": 100.0,
        "standard_deviation_leg_end_time_ns": 200.0,
        "M5_standard_deviation_leg_start_time_ns": 300.0,
        "M5_standard_deviation_leg_end_time_ns": 400.0,
    }

    identity = trade_setup_candidate_event_identities(row, candidate_ids=(candidate_id,))[0]

    assert trade_setup_candidate_event_time_fields(candidate_id) == (
        ("M5_standard_deviation_leg_start_time_ns", 1),
        ("M5_standard_deviation_leg_end_time_ns", 1),
    )
    assert identity.source_event_times_ns == (
        ("M5_standard_deviation_leg_start_time_ns", 300),
        ("M5_standard_deviation_leg_end_time_ns", 400),
    )


@pytest.mark.parametrize(
    ("timeframe", "duration_minutes"),
    [
        ("M3", 3),
        ("M5", 5),
        ("M10", 10),
        ("M15", 15),
        ("M30", 30),
        ("H1", 60),
        ("H4", 240),
        ("D1", 1440),
    ],
)
def test_mtf_candidate_event_identity_survives_causal_availability_alignment(
    timeframe: str, duration_minutes: int
) -> None:
    tz = "Etc/GMT-3"
    source_time = pd.Timestamp("2025-01-06 16:30", tz=tz)
    close_time = source_time + pd.Timedelta(minutes=duration_minutes)
    m1_index = pd.DatetimeIndex(
        [close_time - pd.Timedelta(minutes=1), close_time, close_time + pd.Timedelta(minutes=1)]
    )
    m1 = pd.DataFrame({"close": [100.0, 101.0, 102.0]}, index=m1_index)
    source = pd.DataFrame(
        {
            "standard_deviation_entry_long": [1.0],
            "standard_deviation_leg_start_time_ns": [source_time.value],
            "standard_deviation_leg_end_time_ns": [close_time.value],
        },
        index=pd.DatetimeIndex([source_time]),
    )
    close_times = pd.Series([close_time], index=source.index)

    aligned = align_timeframes(
        m1,
        {timeframe: source},
        availability_times={timeframe: close_times},
    )
    ideas = build_entry_idea_features(aligned)
    aligned = pd.concat([aligned, ideas], axis=1)
    candidate_id = trade_setup_candidate_id("standard_deviation", timeframe, 1)
    candidate_column = f"entry_idea_standard_deviation_{timeframe}_long"
    source_start = f"{timeframe}_standard_deviation_leg_start_time_ns"
    source_end = f"{timeframe}_standard_deviation_leg_end_time_ns"

    assert aligned[candidate_column].tolist() == [0.0, 1.0, 1.0]
    assert trade_setup_candidate_mask(aligned.loc[m1_index[0]])[candidate_id] == 0.0
    assert_frame_equal(
        ideas.iloc[:1],
        build_entry_idea_features(
            align_timeframes(
                m1.iloc[:1],
                {timeframe: source},
                availability_times={timeframe: close_times},
            )
        ),
    )
    identity = trade_setup_candidate_event_identities(
        aligned.loc[m1_index[1]], candidate_ids=(candidate_id,)
    )[0]
    assert identity.status == "identified"
    assert identity.source_event_times_ns == (
        (source_start, source_time.value),
        (source_end, close_time.value),
    )


def test_every_candidate_category_has_resolvable_source_time_fields() -> None:
    """Check catalog mapping coverage with scalar fixtures, not event cardinality."""
    for candidate in TRADE_SETUP_CANDIDATES[1:]:
        assert candidate.idea is not None
        assert candidate.setup_timeframe is not None
        side = "long" if candidate.direction == 1 else "short"
        row: dict[str, float] = {
            f"entry_idea_{candidate.idea}_{candidate.setup_timeframe}_{side}": 1.0
        }
        fields = trade_setup_candidate_event_time_fields(candidate.candidate_id)
        assert fields
        row.update({field: float(1000 * (index + 1)) for index, (field, _) in enumerate(fields)})

        identity = trade_setup_candidate_event_identities(
            row, candidate_ids=(candidate.candidate_id,)
        )[0]

        assert identity.candidate_id == candidate.candidate_id
        assert identity.status == "identified"
        assert identity.source_event_id is not None
        assert identity.source_event_id.startswith(
            f"{TRADE_SETUP_EVENT_IDENTITY_VERSION}:{candidate.idea}:"
            f"{candidate.setup_timeframe}:{candidate.direction}:"
        )


def test_repeated_boolean_category_can_identify_distinct_source_events() -> None:
    first = trade_setup_candidate_event_identities(
        _po3_candidate(1_735_000_000_000_000_000, 1_735_000_060_000_000_000)
    )[0]
    second = trade_setup_candidate_event_identities(
        _po3_candidate(1_735_000_120_000_000_000, 1_735_000_180_000_000_000)
    )[0]

    assert first.candidate_id == second.candidate_id
    assert first.source_event_id != second.source_event_id


def test_same_po3_leg_with_distinct_ifvg_confirmations_has_distinct_identity() -> None:
    first = trade_setup_candidate_event_identities(
        _po3_candidate(1_735_000_000_000_000_000, 1_735_000_060_000_000_000, 300)
    )[0]
    second = trade_setup_candidate_event_identities(
        _po3_candidate(1_735_000_000_000_000_000, 1_735_000_060_000_000_000, 400)
    )[0]

    assert first.source_event_times_ns[:2] == second.source_event_times_ns[:2]
    assert first.source_event_id != second.source_event_id
    assert first.source_event_times_ns[2] != second.source_event_times_ns[2]


def test_same_confirmation_bar_with_distinct_selected_fvg_origins_has_distinct_identity() -> None:
    first = trade_setup_candidate_event_identities(
        _po3_candidate(1_735_000_000_000_000_000, 1_735_000_060_000_000_000, 300, 100)
    )[0]
    second = trade_setup_candidate_event_identities(
        _po3_candidate(1_735_000_000_000_000_000, 1_735_000_060_000_000_000, 300, 200)
    )[0]

    assert first.source_event_times_ns[:3] == second.source_event_times_ns[:3]
    assert first.source_event_id != second.source_event_id
    assert first.source_event_times_ns[-1] != second.source_event_times_ns[-1]


def test_fvg_and_ifvg_candidate_ids_include_selected_source_zone_origins() -> None:
    fvg_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    ifvg_id = trade_setup_candidate_id("ifvg_unretested", "M1", 1)
    row = {
        "entry_idea_fvg_retest_M1_long": 1.0,
        "fvg_bull_retest_confirmed_at_time_ns": 300.0,
        "fvg_bull_retest_origin_time_ns": 100.0,
        "entry_idea_ifvg_unretested_M1_long": 1.0,
        "ifvg_bull_confirmed_at_time_ns": 400.0,
        "ifvg_bull_fvg_origin_time_ns": 200.0,
    }

    fvg_identity, ifvg_identity = trade_setup_candidate_event_identities(
        row, candidate_ids=(fvg_id, ifvg_id)
    )

    assert fvg_identity.status == ifvg_identity.status == "identified"
    assert fvg_identity.source_event_times_ns == (
        ("fvg_bull_retest_confirmed_at_time_ns", 300),
        ("fvg_bull_retest_origin_time_ns", 100),
    )
    assert ifvg_identity.source_event_times_ns == (
        ("ifvg_bull_confirmed_at_time_ns", 400),
        ("ifvg_bull_fvg_origin_time_ns", 200),
    )


def test_missing_or_conflicting_source_times_remain_explicitly_unresolved() -> None:
    missing = _po3_candidate(1_735_000_000_000_000_000, 1_735_000_060_000_000_000)
    del missing["M5_po3_reclaim_time_ns"]
    missing_identity = trade_setup_candidate_event_identities(missing)[0]

    missing_confirmation = _po3_candidate(1_735_000_000_000_000_000, 1_735_000_060_000_000_000)
    del missing_confirmation["M5_ifvg_bull_confirmed_at_time_ns"]
    missing_confirmation_identity = trade_setup_candidate_event_identities(missing_confirmation)[0]
    missing_origin = _po3_candidate(1_735_000_000_000_000_000, 1_735_000_060_000_000_000)
    del missing_origin["M5_po3_ifvg_fvg_origin_time_ns"]
    missing_origin_identity = trade_setup_candidate_event_identities(missing_origin)[0]

    conflicting = pd.Series(
        [
            1.0,
            1_735_000_000_000_000_000,
            1_735_000_060_000_000_000,
            1_735_000_120_000_000_000,
            1_735_000_121_000_000_000,
        ],
        index=[
            "entry_idea_po3_M5_long",
            "M5_po3_sweep_time_ns",
            "M5_po3_reclaim_time_ns",
            "M5_ifvg_bull_confirmed_at_time_ns",
            "M5_ifvg_bull_confirmed_at_time_ns",
        ],
    )
    conflicting_identity = trade_setup_candidate_event_identities(conflicting)[0]

    assert missing_identity.status == "missing_source_event_time"
    assert missing_identity.source_event_id is None
    assert missing_confirmation_identity.status == "missing_source_event_time"
    assert missing_confirmation_identity.source_event_id is None
    assert missing_origin_identity.status == "missing_source_event_time"
    assert missing_origin_identity.source_event_id is None
    assert conflicting_identity.status == "conflicting_source_event_times"
    assert conflicting_identity.source_event_id is None


def test_source_times_do_not_change_candidate_mask_or_model_observation() -> None:
    first = _po3_candidate(1_735_000_000_000_000_000, 1_735_000_060_000_000_000, 300)
    second = _po3_candidate(1_735_000_000_000_000_000, 1_735_000_060_000_000_000, 400)

    np.testing.assert_array_equal(
        trade_setup_candidate_mask(first), trade_setup_candidate_mask(second)
    )
    mask = trade_setup_candidate_mask(first)
    assert mask.shape == (TRADE_SETUP_CATEGORY_COUNT,)
    assert TRADE_SETUP_CATEGORY_COUNT == 109
    assert mask[NO_TRADE_ID] == 1.0
    assert mask[trade_setup_candidate_id("po3", "M5", 1)] == 1.0

    observed = select_obs_columns(pd.DataFrame([first, second]))
    assert "entry_idea_po3_M5_long" in observed
    assert "M5_po3_sweep_time_ns" not in observed
    assert "M5_po3_reclaim_time_ns" not in observed
    assert "M5_ifvg_bull_confirmed_at_time_ns" not in observed
    assert "M5_po3_ifvg_fvg_origin_time_ns" not in observed
