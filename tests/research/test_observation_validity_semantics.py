"""Checks the measured observation-validity to producer-contract crosswalk."""

from __future__ import annotations

from pathlib import Path

from scripts.research.analysis.features.reconcile_observation_validity_semantics import (
    build_report,
    resolve_feature_contract,
)


def test_observation_feature_validity_contracts_cover_measured_profile_rows(
    tmp_path: Path,
) -> None:
    report = build_report(output_dir=tmp_path)

    assert report["feature_timeframe_rows"] == 1291
    assert report["producer_function_count"] == 43
    assert len(report["rows"]) == 1291
    assert all(row["producer_missingness_contract"] for row in report["rows"])
    assert all(Path(row["source_path"]).is_file() for row in report["rows"])
    assert all(
        "per-feature finite-value channel" in row["observation_conversion"]
        for row in report["rows"]
    )


def test_observation_validity_contracts_preserve_known_state_limits() -> None:
    daily_session = resolve_feature_contract("D1_pd_asia_mid_dist_atr")
    htf_bias_available = resolve_feature_contract("htf_day_bias_available")
    mtf_swing_distance = resolve_feature_contract("M5_dist_to_swing_high_atr")
    primary_swing_distance = resolve_feature_contract("dist_to_nearest_swing_atr")
    swing_level = resolve_feature_contract("H1_last_swing_high")
    swing_candidate = resolve_feature_contract("H1_swing_high_candidate_2")
    swing_age = resolve_feature_contract("bars_since_last_swing")
    retracement = resolve_feature_contract("M5_standard_deviation_level_0_5_distance")
    po3_phase = resolve_feature_contract("po3_phase")
    session_progress = resolve_feature_contract("session_progress")
    wick_ratio = resolve_feature_contract("wick_ratio")
    tick_quote = resolve_feature_contract("tick_quote_age_fraction")

    assert daily_session is not None
    assert "unsupported on daily bars" in daily_session["validity_signal"]
    assert htf_bias_available is not None
    assert htf_bias_available["producer_function"] == "build_pd_context_features"
    assert "valid neutral htf_day_bias" in htf_bias_available["validity_signal"]
    assert mtf_swing_distance is not None
    assert mtf_swing_distance["producer_function"] == "build_features"
    assert mtf_swing_distance["source_path"] == "features/pipeline/feature_matrix_builder.py"
    assert "per-feature validity channel" in mtf_swing_distance["validity_signal"]
    assert primary_swing_distance is not None
    assert primary_swing_distance["producer_function"] == "swing_features"
    assert swing_level is not None
    assert swing_level["producer_function"] == "append_structure_features"
    assert swing_candidate is not None
    assert swing_candidate["producer_function"] == "append_structure_features"
    assert swing_age is not None
    assert swing_age["producer_function"] == "swing_features"
    assert retracement is not None
    assert retracement["producer_function"] == "build_swing_retracement_features"
    assert po3_phase is not None
    assert "explicit -1 phase sentinel" in po3_phase["validity_signal"]
    assert "two-observation standard-deviation warmup" in po3_phase["validity_signal"]
    assert session_progress is not None
    assert "paired po3_phase sentinel" in session_progress["validity_signal"]
    assert "two-observation standard-deviation warmup" in session_progress["validity_signal"]
    assert wick_ratio is not None
    assert "defined zero upper-wick ratio" in wick_ratio["reviewed_missingness_semantics"]
    assert tick_quote is not None
    assert "tick_quote_available" in tick_quote["validity_signal"]


def test_unknown_observation_feature_fails_closed() -> None:
    assert resolve_feature_contract("unregistered_feature") is None
