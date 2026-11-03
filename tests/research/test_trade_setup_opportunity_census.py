from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scripts.research.analysis.features.entry_idea_opportunity_census import (
    FVG_EVENT_COLUMNS,
    _candidate_identity_frame,
    _cross_timeframe_alignment_metrics,
    _distinct_event_count,
    _fvg_collision_tables,
    _identity_lifecycle_metrics,
    _source_time_tuple_clusters,
    _validate_fvg_scalar_projection,
    _volatility_regime,
)
from scripts.research.analysis.features.training_context import (
    candidate_supported,
    training_slice,
)

from configuration.configuration_loader import load_config
from decisioning.trade_setup import TRADE_SETUP_CANDIDATES, trade_setup_candidate_id
from features.po3.fvg import build_fvg_zone_features_with_event_ledger


def test_fvg_scalar_projection_reconciles_zone_order_not_event_append_order() -> None:
    scalar = pd.DataFrame(
        {
            "fvg_retest_bull": [0.0, 1.0, 0.0, 1.0],
            "fvg_bull_retest_origin_time_ns": [np.nan, 101.0, np.nan, 303.0],
            "fvg_retest_bear": [0.0, 0.0, 0.0, 0.0],
            "fvg_bear_retest_origin_time_ns": [np.nan, np.nan, np.nan, np.nan],
        }
    )
    events = pd.DataFrame(
        [
            {
                "confirmation_bar": 3,
                "confirmation_time_ns": 400,
                "side": "bullish",
                "zone_start_time_ns": 303,
                "source_origin_bar": 1,
                "source_origin_time_ns": 200,
                "zone_low": 100.0,
                "zone_high": 101.0,
                "selected_by_scalar": True,
            },
            {
                "confirmation_bar": 1,
                "confirmation_time_ns": 200,
                "side": "bullish",
                "zone_start_time_ns": 101,
                "source_origin_bar": 0,
                "source_origin_time_ns": 100,
                "zone_low": 99.0,
                "zone_high": 100.0,
                "selected_by_scalar": True,
            },
        ],
        columns=FVG_EVENT_COLUMNS,
    )

    _validate_fvg_scalar_projection(events, scalar)


def test_registered_trade_setup_overlay_marks_only_configured_sources_supported() -> None:
    cfg = load_config(config_path="config/research/trade_setup_mtf_reasoning_2m.yaml")
    assert candidate_supported(cfg, "standard_deviation", "M1")
    assert candidate_supported(cfg, "standard_deviation", "D1")
    assert candidate_supported(cfg, "po3", "M1")
    assert candidate_supported(cfg, "ifvg_retest", "M1")
    assert not candidate_supported(cfg, "po3", "D1")
    assert not candidate_supported(cfg, "order_block", "M1")
    assert not candidate_supported(cfg, "fvg_retest", "M5")
    assert (
        sum(
            candidate.candidate_id != 0
            and candidate.idea is not None
            and candidate.setup_timeframe is not None
            and candidate_supported(cfg, candidate.idea, candidate.setup_timeframe)
            for candidate in TRADE_SETUP_CANDIDATES
        )
        == 24
    )


def test_shared_training_slice_keeps_the_entire_inclusive_timezone_aware_day() -> None:
    index = pd.DatetimeIndex(
        [
            "2025-01-01T00:00:00Z",
            "2025-01-01T23:59:59.999999999Z",
            "2025-01-02T00:00:00Z",
        ]
    )
    source = pd.DataFrame({"close": [1.0, 2.0, 3.0]}, index=index)

    result = training_slice({"M1": source}, "2025-01-01", "2025-01-01")

    assert result["M1"].index.equals(index[:2])


def test_training_volatility_terciles_are_fit_in_sample_and_label_warmup() -> None:
    index = pd.date_range("2025-01-01", periods=90, freq="min")
    close = np.linspace(100.0, 101.0, len(index))
    width = np.linspace(0.1, 1.0, len(index))
    bars = pd.DataFrame({"high": close + width, "low": close - width, "close": close}, index=index)

    regimes, thresholds = _volatility_regime(bars)

    assert regimes.iloc[:19].eq("warmup_unknown").all()
    assert regimes.iloc[19:].isin({"low", "middle", "high"}).all()
    assert thresholds["lower_tercile"] < thresholds["upper_tercile"]


def test_candidate_event_identity_census_counts_resolved_missing_and_distinct_events() -> None:
    index = pd.date_range("2025-01-01", periods=5, freq="min", tz="UTC")
    candidate_id = next(
        candidate.candidate_id
        for candidate in TRADE_SETUP_CANDIDATES
        if candidate.idea == "po3"
        and candidate.setup_timeframe == "M5"
        and candidate.direction == 1
    )
    active = pd.Series([True, True, True, False, True], index=index)
    features = pd.DataFrame(
        {
            "entry_idea_po3_M5_long": active.astype(float),
            "M5_po3_sweep_time_ns": [101.0, 101.0, np.nan, np.nan, 201.0],
            "M5_po3_reclaim_time_ns": [151.0, 151.0, 151.0, np.nan, 251.0],
            "M5_ifvg_bull_confirmed_at_time_ns": [176.0, 176.0, 176.0, np.nan, 276.0],
            "M5_po3_ifvg_fvg_origin_time_ns": [126.0, 126.0, 126.0, np.nan, 226.0],
        },
        index=index,
    )

    identities = _candidate_identity_frame(features, candidate_id, active)
    resolved = identities["status"].eq("identified").to_numpy()

    assert identities["status"].tolist() == [
        "identified",
        "identified",
        "missing_source_event_time",
        "inactive",
        "identified",
    ]
    assert _distinct_event_count(identities, resolved) == 2


def test_identity_lifecycle_metrics_distinguish_transitions_from_logical_events() -> None:
    index = pd.date_range("2025-01-01", periods=8, freq="min", tz="UTC")
    active = pd.Series([True, True, True, False, True, True, False, True], index=index)
    features = pd.DataFrame(
        {
            "entry_idea_po3_M5_long": active.astype(float),
            "M5_po3_sweep_time_ns": [1.0, 1.0, 2.0, np.nan, 2.0, 2.0, np.nan, 3.0],
            "M5_po3_reclaim_time_ns": [11.0, 11.0, 12.0, np.nan, 12.0, 12.0, np.nan, 13.0],
            "M5_ifvg_bull_confirmed_at_time_ns": [
                21.0,
                21.0,
                22.0,
                np.nan,
                22.0,
                22.0,
                np.nan,
                23.0,
            ],
            "M5_po3_ifvg_fvg_origin_time_ns": [
                16.0,
                16.0,
                17.0,
                np.nan,
                17.0,
                17.0,
                np.nan,
                18.0,
            ],
        },
        index=index,
    )
    candidate_id = next(
        candidate.candidate_id
        for candidate in TRADE_SETUP_CANDIDATES
        if candidate.idea == "po3"
        and candidate.setup_timeframe == "M5"
        and candidate.direction == 1
    )

    identities = _candidate_identity_frame(features, candidate_id, active)

    assert _identity_lifecycle_metrics(identities, active) == {
        "identified_identity_episode_starts": 4,
        "adjacent_active_identity_changes": 1,
        "distinct_ids_reused_across_active_episodes": 1,
    }


def test_cross_timeframe_alignment_counts_exact_joint_source_time_tuples_only() -> None:
    index = pd.date_range("2025-01-01", periods=5, freq="min", tz="UTC")
    left_active = pd.Series([True, True, True, False, True], index=index)
    right_active = pd.Series([True, True, False, True, True], index=index)
    left = pd.DataFrame(
        {
            "status": ["identified", "identified", "identified", "inactive", "identified"],
            "source_time_0_ns": [10, 10, 20, 0, 30],
            "source_time_1_ns": [11, 11, 21, 0, 31],
        },
        index=index,
    )
    right = pd.DataFrame(
        {
            "status": ["identified", "identified", "inactive", "identified", "identified"],
            "source_time_0_ns": [10, 10, 0, 40, 30],
            "source_time_1_ns": [11, 12, 0, 41, 31],
        },
        index=index,
    )

    metrics = _cross_timeframe_alignment_metrics(left, left_active, right, right_active)

    assert metrics == {
        "jointly_active_m1_rows": 3,
        "jointly_identified_m1_rows": 3,
        "exact_source_time_tuple_aligned_m1_rows": 2,
        "distinct_aligned_source_time_tuples": 2,
    }


def test_cross_timeframe_alignment_rejects_different_timestamp_tuple_shapes() -> None:
    index = pd.date_range("2025-01-01", periods=1, freq="min", tz="UTC")
    active = pd.Series([True], index=index)
    left = pd.DataFrame({"status": ["identified"], "source_time_0_ns": [1]}, index=index)
    right = pd.DataFrame(
        {"status": ["identified"], "source_time_0_ns": [1], "source_time_1_ns": [2]},
        index=index,
    )

    with pytest.raises(ValueError, match="matching source-time tuple shapes"):
        _cross_timeframe_alignment_metrics(left, active, right, active)


def test_source_time_tuple_clusters_are_exact_and_direction_scoped() -> None:
    index = pd.date_range("2025-01-01", periods=3, freq="min", tz="UTC")
    m1_long = trade_setup_candidate_id("standard_deviation", "M1", 1)
    m3_long = trade_setup_candidate_id("standard_deviation", "M3", 1)
    m1_short = trade_setup_candidate_id("standard_deviation", "M1", -1)

    def identity_frame(statuses: list[str], first: list[int], second: list[int]) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "status": statuses,
                "source_time_0_ns": first,
                "source_time_1_ns": second,
            },
            index=index,
        )

    streams = {
        m1_long: (
            pd.Series([True, True, False], index=index),
            identity_frame(["identified", "identified", "inactive"], [10, 10, 0], [11, 11, 0]),
        ),
        m3_long: (
            pd.Series([True, False, True], index=index),
            identity_frame(["identified", "inactive", "identified"], [10, 0, 20], [11, 0, 21]),
        ),
        m1_short: (
            pd.Series([True, False, False], index=index),
            identity_frame(["identified", "inactive", "inactive"], [10, 0, 0], [11, 0, 0]),
        ),
    }

    clusters = _source_time_tuple_clusters(streams)

    shared = clusters.loc[
        clusters["idea"].eq("standard_deviation")
        & clusters["direction"].eq("long")
        & clusters["source_time_tuple_ns"].eq("[10,11]")
    ].iloc[0]
    assert shared["candidate_ids"] == f"[{m1_long}, {m3_long}]"
    assert shared["timeframes"] == '["M1", "M3"]'
    assert shared["candidate_count"] == shared["timeframe_count"] == 2
    assert shared["candidate_row_occurrences"] == 3
    assert shared["unique_active_m1_rows"] == 2
    assert shared["rows_with_multiple_timeframes"] == 1
    assert shared["max_concurrent_timeframes"] == 2
    assert not clusters.loc[
        clusters["direction"].eq("short") & clusters["source_time_tuple_ns"].eq("[10,11]")
    ].empty


def test_source_time_tuple_clusters_reject_family_width_mismatch() -> None:
    index = pd.date_range("2025-01-01", periods=1, freq="min", tz="UTC")
    m1 = trade_setup_candidate_id("standard_deviation", "M1", 1)
    m3 = trade_setup_candidate_id("standard_deviation", "M3", 1)
    streams = {
        m1: (
            pd.Series([True], index=index),
            pd.DataFrame(
                {"status": ["identified"], "source_time_0_ns": [1], "source_time_1_ns": [2]},
                index=index,
            ),
        ),
        m3: (
            pd.Series([True], index=index),
            pd.DataFrame({"status": ["identified"], "source_time_0_ns": [1]}, index=index),
        ),
    }
    with pytest.raises(ValueError, match="tuple widths differ"):
        _source_time_tuple_clusters(streams)


def test_fvg_training_ledger_reconciles_scalar_and_groups_overlap_by_regime() -> None:
    index = pd.date_range("2025-02-03 17:00", periods=7, freq="min", tz="Etc/GMT-3")
    bars = pd.DataFrame(
        {
            "open": [100.0, 100.5, 101.5, 102.5, 103.0, 101.0, 104.0],
            "high": [100.0, 101.0, 102.0, 103.0, 104.0, 104.0, 106.0],
            "low": [99.0, 100.0, 101.0, 102.0, 102.5, 99.9, 103.0],
            "close": [99.5, 100.5, 101.5, 102.5, 103.0, 101.1, 105.0],
        },
        index=index,
    )
    scalar, events = build_fvg_zone_features_with_event_ledger(bars)

    _validate_fvg_scalar_projection(events, scalar)
    collisions, monthly = _fvg_collision_tables(
        events,
        bars,
        pd.Series(["low", "low", "middle", "middle", "high", "high", "high"], index=index),
    )

    assert len(events.loc[events["confirmation_bar"].eq(6)]) == 2
    assert len(collisions) == 1
    assert collisions.loc[0, "confirmation_month"] == "2025-02"
    assert collisions.loc[0, "volatility_regime"] == "high"
    assert collisions.loc[0, "suppressed_per_zone_confirmations"] == 1
    assert monthly.loc[0, "per_zone_confirmations"] == 2
    assert monthly.loc[0, "scalar_confirmation_pulses"] == 1
    assert monthly.loc[0, "collision_rows"] == 1
