from __future__ import annotations

import json

import pandas as pd

from decisioning.thesis import thesis_candidate_id
from evaluation import calculate_metrics
from evaluation.metrics.thesis_policy import summarize_thesis_decisions
from evaluation.reporting.export import save_run


def test_thesis_policy_report_counts_abstention_diversity_and_invalid_choices() -> None:
    decisions = pd.DataFrame(
        [
            {
                "thesis_candidate_id": 0,
                "idea": "",
                "setup_timeframe": "",
                "selection_valid": True,
                "eligible_candidate_ids": [0, thesis_candidate_id("fvg_retest", "M5", 1)],
                "thesis_entropy_nats": 2.0,
                "time": "2025-01-01T00:00:00Z",
            },
            {
                "thesis_candidate_id": thesis_candidate_id("fvg_retest", "M5", 1),
                "idea": "fvg_retest",
                "setup_timeframe": "M5",
                "selection_valid": True,
                "eligible_candidate_ids": [
                    0,
                    thesis_candidate_id("fvg_retest", "M5", 1),
                    thesis_candidate_id("fvg_retest", "M5", -1),
                ],
                "thesis_entropy_nats": 1.0,
                "time": "2025-01-02T00:00:00Z",
            },
            {
                "thesis_candidate_id": thesis_candidate_id("po3", "M15", -1),
                "idea": "po3",
                "setup_timeframe": "M15",
                "selection_valid": False,
                "eligible_candidate_ids": [0, thesis_candidate_id("po3", "M15", -1)],
                "thesis_entropy_nats": 0.5,
                "time": "2025-02-01T00:00:00Z",
            },
        ]
    )
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "primary_idea": "fvg_retest",
                "primary_setup_timeframe": "M5",
                "primary_direction": 1,
                "thesis_candidate_id": thesis_candidate_id("fvg_retest", "M5", 1),
                "thesis_schema_version": "thesis-overlay-action-v1",
                "price": 100.0,
                "sl_price": 98.0,
                "tp_price": 104.0,
                "sl_timeframe": "M5",
                "sl_ref": "M5_swing_low",
                "tp_timeframe": "M5",
                "tp_ref": "M5_swing_high",
                "position_net_pnl": 120.0,
                "position_realized_r": 0.6,
            }
        ]
    )

    report = summarize_thesis_decisions(decisions, trades)

    assert report["decision_steps"] == 3
    assert report["no_trade_count"] == 1
    assert report["no_trade_rate"] == 1 / 3
    assert report["invalid_selection_count"] == 1
    assert report["selected_idea_count"] == 2
    assert report["selected_timeframe_count"] == 2
    assert report["trade_thesis_eligible_steps"] == 3
    assert report["no_trade_rate_when_trade_thesis_eligible"] == 1 / 3
    assert report["eligible_trade_thesis_count_max"] == 2
    assert len(report["selection_by_idea"]) == 6
    assert len(report["selection_by_timeframe"]) == 9
    assert len(report["selection_matrix"]) == 54
    fvg_idea = next(row for row in report["selection_by_idea"] if row["idea"] == "fvg_retest")
    assert fvg_idea["eligible_candidate_occurrences"] == 3
    assert fvg_idea["eligible_steps"] == 2
    assert fvg_idea["selection_rate_given_eligible_step"] == 0.5
    fvg_cell = next(
        row
        for row in report["selection_matrix"]
        if row["idea"] == "fvg_retest" and row["timeframe"] == "M5"
    )
    assert fvg_cell["eligible_candidate_occurrences"] == 3
    assert fvg_cell["eligible_steps"] == 2
    fvg_performance = next(
        row for row in report["performance_by_idea_timeframe"] if row["idea"] == "fvg_retest"
    )
    assert fvg_performance["trade_count"] == 1
    assert fvg_performance["net_pnl"] == 120.0
    assert fvg_performance["mean_realized_r"] == 0.6
    assert len(report["thesis_entropy_by_month"]) == 2
    assert report["structural_violations"]["total"] == 0


def test_thesis_policy_report_flags_stop_floor_and_wrong_side_targets() -> None:
    decisions = pd.DataFrame(
        columns=[
            "thesis_candidate_id",
            "idea",
            "setup_timeframe",
            "selection_valid",
            "thesis_entropy_nats",
            "time",
        ]
    )
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "primary_idea": "standard_deviation",
                "primary_setup_timeframe": "M15",
                "primary_direction": 1,
                "thesis_candidate_id": thesis_candidate_id("standard_deviation", "M15", 1),
                "thesis_schema_version": "thesis-overlay-action-v1",
                "price": 100.0,
                "sl_price": 101.0,
                "tp_price": 99.0,
                "sl_timeframe": "M5",
                "sl_ref": "M5_standard_deviation_level_1_price",
            }
        ]
    )

    report = summarize_thesis_decisions(decisions, trades)

    violations = report["structural_violations"]
    assert violations["sl_wrong_side"] == 1
    assert violations["sl_below_primary_timeframe"] == 1
    assert violations["standard_deviation_sl_not_level_1_on_setup_timeframe"] == 1
    assert violations["tp_wrong_side"] == 1
    assert violations["total"] == 1


def test_m1_standard_deviation_stop_uses_unprefixed_level_one_name() -> None:
    decisions = pd.DataFrame()
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "primary_idea": "standard_deviation",
                "primary_setup_timeframe": "M1",
                "primary_direction": 1,
                "thesis_candidate_id": thesis_candidate_id("standard_deviation", "M1", 1),
                "thesis_schema_version": "thesis-overlay-action-v1",
                "price": 100.0,
                "sl_price": 98.0,
                "sl_timeframe": "M1",
                "sl_ref": "standard_deviation_level_1_price",
            }
        ]
    )

    report = summarize_thesis_decisions(decisions, trades)

    assert (
        report["structural_violations"]["standard_deviation_sl_not_level_1_on_setup_timeframe"] == 0
    )


def test_thesis_decision_diagnostics_export_to_split_artifacts(tmp_path) -> None:
    selected_id = thesis_candidate_id("fvg_retest", "M5", 1)
    decisions = pd.DataFrame(
        [
            {
                "step": 1,
                "time": "2025-01-01T00:01:00Z",
                "thesis_candidate_id": 0,
                "idea": "",
                "setup_timeframe": "",
                "direction": 0,
                "is_no_trade": True,
                "selection_valid": True,
                "eligible_thesis_count": 2,
                "eligible_candidate_ids": [0, selected_id],
                "thesis_entropy_nats": 0.8,
                "action_risk": 0.1,
            },
            {
                "step": 2,
                "time": "2025-01-01T00:02:00Z",
                "thesis_candidate_id": selected_id,
                "idea": "fvg_retest",
                "setup_timeframe": "M5",
                "direction": 1,
                "is_no_trade": False,
                "selection_valid": True,
                "eligible_thesis_count": 2,
                "eligible_candidate_ids": [0, selected_id],
                "thesis_entropy_nats": 0.7,
                "action_risk": 0.3,
            },
        ]
    )
    equity = pd.Series(
        [100_000.0, 100_010.0], index=pd.date_range("2025-01-01", periods=2, freq="min")
    )
    trades = pd.DataFrame()
    result = {
        "equity": equity,
        "trades": trades,
        "initial_balance": 100_000.0,
        "thesis_decisions": decisions,
        "thesis_policy_metrics": summarize_thesis_decisions(decisions, trades),
    }
    run_dir = save_run(
        run_dir=tmp_path / "thesis-diagnostics",
        train_result=result,
        train_metrics=calculate_metrics(equity, trades=trades, initial_balance=100_000.0),
        save_plots=True,
        save_html=False,
        save_csv=True,
        report_profile="campaign_fast",
    )

    split = run_dir / "training"
    assert len(pd.read_csv(split / "thesis_decisions.csv")) == 2
    assert len(pd.read_csv(split / "thesis_selection_matrix.csv")) == 54
    assert len(pd.read_csv(split / "thesis_selection_by_idea.csv")) == 6
    assert (split / "thesis_selection_heatmap.png").is_file()
    assert (split / "thesis_performance_heatmap.png").is_file()
    diagnostics = json.loads((split / "thesis_policy_metrics.json").read_text())
    assert diagnostics["no_trade_count"] == 1
    assert diagnostics["invalid_selection_count"] == 0
    summary = (split / "summary.txt").read_text()
    assert "THESIS POLICY DIAGNOSTICS" in summary
    assert "Structural violations: 0 unique trades" in summary
