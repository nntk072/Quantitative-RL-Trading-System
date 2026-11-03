"""Tests for descriptive trade exit-reason cohort summaries."""

from __future__ import annotations

import pandas as pd
import pytest
from scripts.research.analysis.evaluation.summarize_trade_exit_cohorts import build_report


def _ledger(path) -> None:
    pd.DataFrame(
        {
            "position_id": ["p1", "p2", "p3"],
            "exit_reason": ["structure_sl", "structure_sl", "session_end"],
            "position_net_pnl_usd": [-10.0, -20.0, 5.0],
            "realized_r": [-1.0, -2.0, 0.5],
            "mfe_r_lower": [0.4, 0.8, 1.2],
            "mae_r_lower": [1.0, 2.0, 0.3],
            "mfe_lower_r_reaches_one": [False, False, True],
            "holding_seconds": [60.0, 180.0, 7200.0],
            "entry_timestamp_tie_rows": [1, 2, 1],
            "exit_timestamp_tie_rows": [1, 1, 3],
        }
    ).to_csv(path, index=False)


def test_build_report_summarizes_distinct_exit_reason_cohorts(tmp_path) -> None:
    source = tmp_path / "positions.csv"
    _ledger(source)

    report, cohorts = build_report([("a4a", source)])

    stops = cohorts.set_index("exit_reason").loc["structure_sl"]
    assert stops["position_count"] == 2
    assert stops["position_net_pnl_mean"] == -15.0
    assert stops["realized_r_median"] == -1.5
    assert stops["one_r_mfe_share"] == 0.0
    assert stops["entry_timestamp_tie_positions"] == 1
    assert report["arms"]["a4a"]["position_count"] == 3
    assert report["cohorts_are_paired"] is False
    assert report["cost_r_available"] is False


def test_build_report_rejects_duplicate_position_ids(tmp_path) -> None:
    source = tmp_path / "positions.csv"
    _ledger(source)
    frame = pd.read_csv(source)
    frame.loc[1, "position_id"] = "p1"
    frame.to_csv(source, index=False)

    with pytest.raises(ValueError, match="one row per non-null position_id"):
        build_report([("a4a", source)])
