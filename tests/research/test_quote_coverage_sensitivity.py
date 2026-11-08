"""Regression tests for distinct raw-source and reconstructed-TickBook assumptions."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scripts.research.analysis.evaluation.compare_quote_coverage_sensitivity import (
    compare_frames,
    load_packet,
    sha256,
    validate_paired_manifests,
)
from scripts.research.analysis.market_data.build_reconstructed_quote_coverage import (
    book_minute_counts,
    classify_coverage,
)

from market_data.loading.ticks import TickBook


def _book(rows: list[tuple[str, float, float]]) -> TickBook:
    times = pd.DatetimeIndex([row[0] for row in rows], tz="UTC")
    if times.tz is None:
        raise ValueError("test ticks must be timezone-aware")
    return TickBook(
        np.asarray(times.as_unit("ns").astype("int64"), dtype=np.int64),
        np.array([row[1] for row in rows], dtype=np.float64),
        np.array([row[2] for row in rows], dtype=np.float64),
    )


def _raw_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source_tick_rows": [2, 3, 1, 0],
            "m1_tickvol": [2, 2, 1, 0],
            "valid_two_sided_quotes": [1, 3, 1, 0],
            "quote_complete": [False, False, True, False],
        }
    )


def test_profiles_separate_one_side_carry_from_m1_count_mismatch() -> None:
    result = classify_coverage(_raw_frame(), np.array([2, 3, 0, 0]), np.zeros(4, dtype=np.int64))
    assert result["strict_raw_quote_complete"].tolist() == [False, False, True, False]
    assert result["production_tickbook_complete"].tolist() == [True, True, False, False]
    assert result["production_tickbook_count_checked"].tolist() == [True, False, False, False]


def test_reconstructed_count_cannot_exceed_raw_count() -> None:
    with pytest.raises(ValueError, match="more rows"):
        classify_coverage(_raw_frame(), np.array([3, 3, 1, 0]), np.zeros(4, dtype=int))


def test_inconsistent_original_strict_coverage_fails_closed() -> None:
    source = _raw_frame()
    source.loc[0, "quote_complete"] = True
    with pytest.raises(ValueError, match="strict raw labels"):
        classify_coverage(source, np.array([2, 3, 1, 0]), np.zeros(4, dtype=int))


def test_quote_counts_use_mt5_fixed_offset_and_minute_boundaries() -> None:
    minutes = pd.date_range("2025-01-02 16:00", periods=3, freq="min")
    book = _book(
        [
            ("2025-01-02T12:59:59.999Z", 100.0, 100.2),
            ("2025-01-02T13:00:00.000Z", 100.1, 100.2),
            ("2025-01-02T13:00:59.999Z", 100.1, 100.3),
            ("2025-01-02T13:01:00.000Z", 100.4, 100.6),
        ]
    )
    count, invalid = book_minute_counts(book, minutes, timezone="Etc/GMT-3", chunk_rows=2)
    assert count.tolist() == [2, 1, 0]
    assert invalid.tolist() == [0, 0, 0]


def test_quote_count_validation_refuses_nonfixed_timezone() -> None:
    minutes = pd.DatetimeIndex(["2025-03-29 16:00", "2025-03-31 16:00"])
    with pytest.raises(ValueError, match="changing source timezone"):
        book_minute_counts(_book([]), minutes, timezone="Europe/Helsinki")


def _outcomes(statuses: list[str], reasons: list[str | None]) -> pd.DataFrame:
    rows = []
    for idx, (status, reason) in enumerate(zip(statuses, reasons, strict=True)):
        resolved = status == "filled_resolved"
        rows.append(
            {
                "outcome_id": f"co2-{idx}",
                "status": status,
                "unresolved_reason": reason,
                "fill_time": "2025-01-01T12:00:00Z" if resolved else None,
                "fill_price": 100.0 if resolved else None,
                "exit_time": "2025-01-01T12:01:00Z" if resolved else None,
                "exit_price": 101.0 if resolved else None,
                "exit_reason": "tp" if resolved else None,
                "net_r": 1.0 if resolved else None,
            }
        )
    return pd.DataFrame.from_records(rows)


def test_status_comparison_counts_only_newly_classified_outcomes() -> None:
    strict = _outcomes(
        ["filled_resolved", "unresolved_data", "unresolved_data"],
        [None, "local two-sided quote coverage is incomplete before exit resolution", "gap"],
    )
    alternative = _outcomes(
        ["filled_resolved", "filled_resolved", "unresolved_data"],
        [None, None, "gap"],
    )
    summary = compare_frames(strict, alternative)
    assert summary["unresolved_that_became_filled_resolved"] == 1
    assert summary["alternative_unresolved"] == 1
    assert summary["original_completed_outcomes_stable"] is True


def test_existing_completed_trade_cannot_change_economics() -> None:
    strict = _outcomes(["filled_resolved"], [None])
    alternative = strict.copy()
    alternative.loc[0, "net_r"] = 0.2
    with pytest.raises(ValueError, match="already-completed outcome changed net_r"):
        compare_frames(strict, alternative)


def _paired_manifest() -> dict[str, object]:
    from scripts.research.analysis.evaluation.compare_quote_coverage_sensitivity import (
        IDENTICAL_INPUTS,
    )

    manifest: dict[str, object] = {key: f"value:{key}" for key in IDENTICAL_INPUTS}
    manifest["source_sha256"] = {"evaluation/candidate_execution.py": "abc123"}
    return manifest


def test_paired_manifest_rejects_noncoverage_input_mismatch() -> None:
    strict = _paired_manifest()
    alternative = _paired_manifest()
    alternative["tickbook_sha256"] = "different"

    with pytest.raises(ValueError, match="unmatched replay input tickbook_sha256"):
        validate_paired_manifests(strict, alternative, packet_label="alternate")


def test_paired_manifest_rejects_execution_source_mismatch() -> None:
    strict = _paired_manifest()
    alternative = _paired_manifest()
    alternative["source_sha256"] = {"evaluation/candidate_execution.py": "different"}

    with pytest.raises(ValueError, match="execution source changed"):
        validate_paired_manifests(strict, alternative, packet_label="alternate")


def test_status_comparison_rejects_changed_outcome_population() -> None:
    strict = _outcomes(["filled_resolved", "unresolved_data"], [None, "gap"])
    alternative = _outcomes(["filled_resolved", "unresolved_data"], [None, "gap"])
    alternative.loc[1, "outcome_id"] = "different-id"

    with pytest.raises(ValueError, match="proposal/bracket population"):
        compare_frames(strict, alternative)


def test_load_packet_retains_proposal_identity_for_audit(tmp_path: Path) -> None:
    frame = _outcomes(["filled_resolved"], [None]).assign(proposal_id=["proposal-1"])
    packet = tmp_path / "packet"
    packet.mkdir()
    data_path = packet / "conditional_outcomes.parquet"
    frame.to_parquet(data_path, index=False)
    manifest = {
        "status": "training_conditional_outcomes_with_coverage_dispositions",
        "conditional_outcome_rows": 1,
        "outcome_status_counts": {"filled_resolved": 1},
        "output_sha256": {data_path.name: sha256(data_path)},
    }
    (packet / "outcome_manifest.json").write_text(json.dumps(manifest))

    loaded, _ = load_packet(packet)

    assert loaded["proposal_id"].tolist() == ["proposal-1"]
