from __future__ import annotations

import numpy as np
import pandas as pd
from scripts.research.analysis.features.candidate_geometry_support import (
    _candidate_geometry_summary,
)

from decisioning.trade_setup import NO_TRADE_ID, TRADE_SETUP_CANDIDATES
from features.context.trade_setup_candidates import trade_setup_candidate_feature_columns


def _candidate(idea: str, timeframe: str, direction: int):
    return next(
        candidate
        for candidate in TRADE_SETUP_CANDIDATES
        if candidate.idea == idea
        and candidate.setup_timeframe == timeframe
        and candidate.direction == direction
    )


def test_candidate_geometry_coverage_counts_only_valid_active_source_bounds() -> None:
    candidate = _candidate("order_block", "M5", 1)
    candidate_feature = dict(trade_setup_candidate_feature_columns())[candidate.candidate_id]
    features = pd.DataFrame(
        {
            candidate_feature: [1.0, 1.0, 1.0, 0.0, np.nan],
            "M5_ob_bull_active": [1.0, 1.0, 1.0, 1.0, 1.0],
            "M5_ob_bull_low": [100.0, np.nan, 103.0, 90.0, 100.0],
            "M5_ob_bull_high": [101.0, 99.0, 102.0, 91.0, 101.0],
        }
    )

    report = _candidate_geometry_summary(features, candidate, configured_support=True)

    assert report["active_training_rows"] == 3
    assert report["geometry_kind"] == "source_zone"
    assert report["geometry_contract"] == "source_zone_bounds_available"
    assert report["rows_with_valid_geometry"] == 1
    assert report["rows_with_invalid_geometry_bounds"] == 2
    assert report["geometry_coverage_fraction"] == 1.0 / 3.0
    assert report["median_geometry_width"] == 1.0
    assert report["rows_with_atr_normalized_geometry"] is None
    assert report["median_geometry_width_atr"] is None


def test_candidate_geometry_reports_close_and_atr_scaled_width_and_distance() -> None:
    candidate = _candidate("order_block", "M5", 1)
    candidate_feature = dict(trade_setup_candidate_feature_columns())[candidate.candidate_id]
    features = pd.DataFrame(
        {
            candidate_feature: [1.0, 1.0, 0.0],
            "M5_ob_bull_active": [1.0, 1.0, 1.0],
            "M5_ob_bull_low": [100.0, 103.0, 100.0],
            "M5_ob_bull_high": [102.0, 104.0, 102.0],
            "close": [101.0, 100.0, 101.0],
            "atr": [2.0, 1.0, 1.0],
        }
    )

    report = _candidate_geometry_summary(features, candidate, configured_support=True)

    assert report["rows_with_atr_normalized_geometry"] == 2
    assert report["atr_normalized_geometry_coverage_fraction"] == 1.0
    assert report["median_geometry_width_atr"] == 1.0
    assert report["p95_geometry_width_atr"] == 1.0
    assert report["fraction_price_inside_geometry"] == 0.5
    assert report["median_distance_to_geometry_atr"] == 1.5
    assert np.isclose(report["p95_distance_to_geometry_atr"], 2.85)


def test_candidate_without_exposed_geometry_fields_is_reported_as_missing() -> None:
    candidate = _candidate("order_block", "M1", -1)
    candidate_feature = dict(trade_setup_candidate_feature_columns())[candidate.candidate_id]
    features = pd.DataFrame({candidate_feature: [1.0, 0.0]})

    report = _candidate_geometry_summary(features, candidate, configured_support=False)

    assert report["active_training_rows"] == 1
    assert report["geometry_contract"] == "expected_source_zone_bounds_missing"
    assert report["rows_with_valid_geometry"] is None
    assert report["geometry_coverage_fraction"] is None


def test_standard_deviation_candidate_uses_its_retracement_band() -> None:
    candidate = _candidate("standard_deviation", "M1", -1)
    candidate_feature = dict(trade_setup_candidate_feature_columns())[candidate.candidate_id]
    features = pd.DataFrame(
        {
            candidate_feature: [1.0, 1.0, 0.0],
            "standard_deviation_band_low": [100.0, 102.0, 90.0],
            "standard_deviation_band_high": [101.0, 104.0, 91.0],
        }
    )

    report = _candidate_geometry_summary(features, candidate, configured_support=True)

    assert report["geometry_kind"] == "retracement_band"
    assert report["geometry_contract"] == "retracement_band_fields_available"
    assert report["active_training_rows"] == 2
    assert report["rows_with_valid_geometry"] == 2
    assert report["geometry_coverage_fraction"] == 1.0
    assert report["median_geometry_width"] == 1.5


def test_standard_deviation_retracement_band_uses_candidate_timeframe() -> None:
    candidate = _candidate("standard_deviation", "D1", 1)
    candidate_feature = dict(trade_setup_candidate_feature_columns())[candidate.candidate_id]
    features = pd.DataFrame(
        {
            candidate_feature: [1.0],
            "D1_standard_deviation_band_low": [20.0],
            "D1_standard_deviation_band_high": [24.0],
            "standard_deviation_band_low": [10.0],
            "standard_deviation_band_high": [12.0],
        }
    )

    report = _candidate_geometry_summary(features, candidate, configured_support=True)

    assert report["rows_with_valid_geometry"] == 1
    assert report["median_geometry_width"] == 4.0


def test_po3_geometry_uses_active_source_timeframe_fallback() -> None:
    candidate = _candidate("po3", "M1", 1)
    candidate_feature = dict(trade_setup_candidate_feature_columns())[candidate.candidate_id]
    features = pd.DataFrame(
        {
            candidate_feature: [1.0, 1.0, 1.0],
            "po3_distribution_direction": [1.0, 0.0, 0.0],
            "ifvg_bull_active": [0.0, 1.0, 0.0],
            "M1_fvg_bull_active": [1.0, 0.0, 1.0],
            "M1_fvg_bull_low": [100.0, np.nan, 100.0],
            "M1_fvg_bull_high": [101.0, np.nan, 101.0],
            "ifvg_bull_low": [np.nan, 98.0, np.nan],
            "ifvg_bull_high": [np.nan, 99.0, np.nan],
        }
    )

    report = _candidate_geometry_summary(features, candidate, configured_support=True)

    assert report["geometry_contract"] == "source_zone_bounds_available"
    assert report["active_training_rows"] == 3
    assert report["rows_with_valid_geometry"] == 2
    assert report["geometry_coverage_fraction"] == 2.0 / 3.0
    assert report["median_geometry_width"] == 1.0


def test_po3_geometry_uses_versioned_confirmation_code_projection() -> None:
    candidate = _candidate("po3", "M1", 1)
    candidate_feature = dict(trade_setup_candidate_feature_columns())[candidate.candidate_id]
    features = pd.DataFrame(
        {
            candidate_feature: [1.0, 1.0],
            "po3_ifvg_confirmation_tf_code": [5.0, 0.0],
            "po3_ifvg_low": [100.0, np.nan],
            "po3_ifvg_high": [102.0, np.nan],
        }
    )

    report = _candidate_geometry_summary(features, candidate, configured_support=True)

    assert report["geometry_contract"] == "source_zone_bounds_available"
    assert report["rows_with_valid_geometry"] == 1
    assert report["geometry_coverage_fraction"] == 0.5
    assert report["median_geometry_width"] == 2.0


def test_no_trade_is_not_misreported_as_a_geometry_gap() -> None:
    candidate = TRADE_SETUP_CANDIDATES[NO_TRADE_ID]
    report = _candidate_geometry_summary(
        pd.DataFrame(index=pd.RangeIndex(3)), candidate, configured_support=True
    )

    assert report["idea"] == "no_trade"
    assert report["geometry_contract"] == "not_applicable"
    assert report["rows_with_valid_geometry"] is None
