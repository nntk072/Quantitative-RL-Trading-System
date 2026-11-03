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
    assert report["producer_function_count"] == 41
    assert len(report["rows"]) == 1291
    assert all(row["producer_missingness_contract"] for row in report["rows"])
    assert all(Path(row["source_path"]).is_file() for row in report["rows"])


def test_observation_validity_contracts_preserve_known_state_limits() -> None:
    daily_session = resolve_feature_contract("D1_pd_asia_mid_dist_atr")
    po3_phase = resolve_feature_contract("po3_phase")
    tick_quote = resolve_feature_contract("tick_quote_age_fraction")

    assert daily_session is not None
    assert "unsupported on daily bars" in daily_session["validity_signal"]
    assert po3_phase is not None
    assert "No explicit session-validity" in po3_phase["validity_signal"]
    assert tick_quote is not None
    assert "tick_quote_available" in tick_quote["validity_signal"]


def test_unknown_observation_feature_fails_closed() -> None:
    assert resolve_feature_contract("unregistered_feature") is None
