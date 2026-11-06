from __future__ import annotations

import pandas as pd
import pytest
from scripts.research.analysis.evaluation.compare_candidate_outcome_replays import (
    compare_parquet_values,
)


def test_full_replay_comparison_reports_exact_arrow_equality(tmp_path) -> None:
    reference = tmp_path / "reference.parquet"
    replay = tmp_path / "replay.parquet"
    frame = pd.DataFrame({"outcome_id": ["a", "b"], "net_r": [0.5, -1.0]})
    frame.to_parquet(reference)
    frame.to_parquet(replay)

    report = compare_parquet_values(reference, replay, batch_size=1)

    assert report["status"] == "all_rows_exactly_equal"
    assert report["rows_compared"] == 2
    assert report["reference_sha256"] == report["replay_sha256"]
    assert "not an independent execution implementation" in report["method"]


def test_full_replay_comparison_identifies_first_changed_field(tmp_path) -> None:
    reference = tmp_path / "reference.parquet"
    replay = tmp_path / "replay.parquet"
    pd.DataFrame({"outcome_id": ["a", "b"], "net_r": [0.5, -1.0]}).to_parquet(reference)
    pd.DataFrame({"outcome_id": ["a", "b"], "net_r": [0.5, -0.9]}).to_parquet(replay)

    report = compare_parquet_values(reference, replay, batch_size=1)

    assert report["status"] == "mismatch"
    assert report["first_mismatch"]["first_different_field"] == "net_r"
    assert report["rows_compared"] == 1


def test_full_replay_comparison_rejects_nonpositive_batch_size(tmp_path) -> None:
    path = tmp_path / "outcomes.parquet"
    pd.DataFrame({"outcome_id": ["a"]}).to_parquet(path)

    with pytest.raises(ValueError, match="batch_size must be positive"):
        compare_parquet_values(path, path, batch_size=0)
