from __future__ import annotations

import json

import pandas as pd

from decisioning.trade_setup import trade_setup_candidate_id
from evaluation import calculate_metrics
from evaluation.metrics.trade_setup_policy import summarize_trade_setup_decisions
from evaluation.reporting.run_artifact_writer import save_run


def test_trade_setup_policy_report_counts_abstention_diversity_and_invalid_choices() -> None:
    decisions = pd.DataFrame(
        [
            {
                "trade_setup_candidate_id": 0,
                "trade_setup_event_identity_version": "trade-setup-event-identity-v3",
                "trade_setup_source_event_id": None,
                "trade_setup_source_event_identity_status": "not_applicable",
                "trade_setup_source_event_times_ns": [],
                "idea": "",
                "setup_timeframe": "",
                "selection_valid": True,
                "eligible_candidate_ids": [0, trade_setup_candidate_id("fvg_retest", "M5", 1)],
                "trade_setup_entropy_nats": 2.0,
                "time": "2025-01-01T00:00:00Z",
            },
            {
                "trade_setup_candidate_id": trade_setup_candidate_id("fvg_retest", "M5", 1),
                "idea": "fvg_retest",
                "setup_timeframe": "M5",
                "selection_valid": True,
                "eligible_candidate_ids": [
                    0,
                    trade_setup_candidate_id("fvg_retest", "M5", 1),
                    trade_setup_candidate_id("fvg_retest", "M5", -1),
                ],
                "trade_setup_entropy_nats": 1.0,
                "time": "2025-01-02T00:00:00Z",
            },
            {
                "trade_setup_candidate_id": trade_setup_candidate_id("po3", "M15", -1),
                "idea": "po3",
                "setup_timeframe": "M15",
                "selection_valid": False,
                "eligible_candidate_ids": [0, trade_setup_candidate_id("po3", "M15", -1)],
                "trade_setup_entropy_nats": 0.5,
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
                "trade_setup_candidate_id": trade_setup_candidate_id("fvg_retest", "M5", 1),
                "trade_setup_schema_version": "trade-setup-overlay-action-v1",
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

    report = summarize_trade_setup_decisions(decisions, trades)

    assert report["decision_steps"] == 3
    assert report["no_trade_count"] == 1
    assert report["no_trade_rate"] == 1 / 3
    assert report["invalid_selection_count"] == 1
    assert report["selected_idea_count"] == 2
    assert report["selected_timeframe_count"] == 2
    assert report["trade_setup_eligible_steps"] == 3
    assert report["no_trade_rate_when_trade_setup_eligible"] == 1 / 3
    assert report["eligible_trade_setup_count_max"] == 2
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
    assert fvg_performance["profit_factor"] is None
    assert fvg_performance["profit_factor_availability"] == (
        "unbounded_no_losses_with_positive_gains"
    )
    breakeven_trades = trades.copy()
    breakeven_trades["position_net_pnl"] = 0.0
    breakeven_report = summarize_trade_setup_decisions(decisions, breakeven_trades)
    breakeven_performance = next(
        row
        for row in breakeven_report["performance_by_idea_timeframe"]
        if row["idea"] == "fvg_retest"
    )
    assert breakeven_performance["profit_factor"] is None
    assert breakeven_performance["profit_factor_availability"] == ("undefined_no_gains_or_losses")
    assert len(report["trade_setup_entropy_by_month"]) == 2
    assert report["structural_violations"]["total"] == 0


def test_trade_setup_entropy_is_grouped_by_decision_month_not_valuation_month() -> None:
    decisions = pd.DataFrame(
        [
            {
                "trade_setup_candidate_id": 0,
                "idea": "",
                "setup_timeframe": "",
                "selection_valid": True,
                "eligible_candidate_ids": [0],
                "trade_setup_entropy_nats": 0.5,
                "decision_time": "2025-01-31T23:59:00+03:00",
                "valuation_time": "2025-02-01T00:00:00+03:00",
                "time": "2025-01-31T23:59:00+03:00",
            }
        ]
    )

    report = summarize_trade_setup_decisions(decisions, pd.DataFrame())

    assert report["trade_setup_entropy_by_month"] == [
        {"month": "2025-01", "count": 1, "mean": 0.5, "median": 0.5, "no_trade_rate": 1.0}
    ]


def test_decision_open_linkage_uses_ids_and_fails_closed_on_mismatches() -> None:
    candidate_id = trade_setup_candidate_id("fvg_retest", "M5", 1)
    decisions = pd.DataFrame(
        [
            {
                "decision_id": "episode:d1",
                "trade_setup_candidate_id": candidate_id,
                "idea": "fvg_retest",
                "setup_timeframe": "M5",
                "selection_valid": True,
                "eligible_candidate_ids": [0, candidate_id],
                "trade_setup_entropy_nats": 0.4,
                "decision_time": "2025-01-01T00:00:00Z",
            },
            {
                "decision_id": "episode:d2",
                "trade_setup_candidate_id": 0,
                "idea": "",
                "setup_timeframe": "",
                "selection_valid": True,
                "eligible_candidate_ids": [0],
                "trade_setup_entropy_nats": 0.0,
                "decision_time": "2025-01-01T00:01:00Z",
            },
        ]
    )
    opens = pd.DataFrame(
        [{"type": "open", "decision_id": "episode:d1", "trade_setup_candidate_id": candidate_id}]
    )

    report = summarize_trade_setup_decisions(decisions, opens)["decision_open_linkage"]

    assert report == {
        "status": "complete",
        "decision_count": 2,
        "open_count": 1,
        "decisions_without_decision_id": 0,
        "decisions_with_open": 1,
        "decisions_without_open": 1,
        "opens_without_decision_id": 0,
        "opens_with_unknown_decision_id": 0,
        "duplicate_decision_id_count": 0,
        "multiple_opens_per_decision_count": 0,
        "candidate_id_columns_available": True,
        "candidate_id_mismatch_count": 0,
    }

    broken_opens = pd.concat(
        [
            opens,
            pd.DataFrame(
                [
                    {
                        "type": "open",
                        "decision_id": "legacy:unknown",
                        "trade_setup_candidate_id": candidate_id,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    broken = summarize_trade_setup_decisions(decisions, broken_opens)["decision_open_linkage"]

    assert broken["status"] == "mismatch"
    assert broken["opens_with_unknown_decision_id"] == 1

    missing_candidate = summarize_trade_setup_decisions(
        decisions,
        opens.drop(columns="trade_setup_candidate_id"),
    )["decision_open_linkage"]
    assert missing_candidate["status"] == "incomplete_missing_candidate_id_column"
    assert missing_candidate["candidate_id_columns_available"] is False


def test_trade_setup_policy_report_flags_stop_floor_and_wrong_side_targets() -> None:
    decisions = pd.DataFrame(
        columns=[
            "trade_setup_candidate_id",
            "idea",
            "setup_timeframe",
            "selection_valid",
            "trade_setup_entropy_nats",
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
                "trade_setup_candidate_id": trade_setup_candidate_id(
                    "standard_deviation", "M15", 1
                ),
                "trade_setup_schema_version": "trade-setup-overlay-action-v1",
                "price": 100.0,
                "sl_price": 101.0,
                "tp_price": 99.0,
                "sl_timeframe": "M5",
                "sl_ref": "M5_standard_deviation_level_1_price",
            }
        ]
    )

    report = summarize_trade_setup_decisions(decisions, trades)

    violations = report["structural_violations"]
    assert violations["sl_wrong_side"] == 1
    assert violations["sl_below_primary_timeframe"] == 1
    assert violations["standard_deviation_sl_not_level_1_on_setup_timeframe"] == 1
    assert violations["tp_wrong_side"] == 1
    assert violations["total"] == 1


def test_session_composite_stops_and_lower_timeframe_targets_are_valid() -> None:
    decisions = pd.DataFrame()
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "primary_idea": "po3",
                "primary_setup_timeframe": "M1",
                "primary_direction": -1,
                "trade_setup_candidate_id": trade_setup_candidate_id("po3", "M1", -1),
                "trade_setup_schema_version": "trade-setup-overlay-action-v1",
                "price": 100.0,
                "sl_price": 101.0,
                "tp_price": 99.0,
                "sl_ref": "london_high|M5_last_swing_high|M10_last_swing_high",
                "sl_timeframe": "",
                "tp_ref": "M1_last_swing_low",
                "tp_timeframe": "M1",
            },
            {
                "type": "open",
                "primary_idea": "ifvg_unretested",
                "primary_setup_timeframe": "M1",
                "primary_direction": -1,
                "trade_setup_candidate_id": trade_setup_candidate_id("ifvg_unretested", "M1", -1),
                "trade_setup_schema_version": "trade-setup-overlay-action-v1",
                "price": 100.0,
                "sl_price": 101.0,
                "tp_price": 99.0,
                "sl_ref": "asian_high",
                "sl_timeframe": "",
                "tp_ref": "M1_last_swing_low",
                "tp_timeframe": "M1",
            },
            {
                "type": "open",
                "primary_idea": "fvg_retest",
                "primary_setup_timeframe": "M5",
                "primary_direction": 1,
                "trade_setup_candidate_id": trade_setup_candidate_id("fvg_retest", "M5", 1),
                "trade_setup_schema_version": "trade-setup-overlay-action-v1",
                "price": 100.0,
                "sl_price": 98.0,
                "tp_price": 102.0,
                "sl_ref": "M5_last_swing_low",
                "sl_timeframe": "M5",
                "tp_ref": "M1_last_swing_high",
                "tp_timeframe": "M1",
            },
        ]
    )

    report = summarize_trade_setup_decisions(decisions, trades)

    violations = report["structural_violations"]
    assert violations["sl_below_primary_timeframe"] == 0
    assert violations["tp_wrong_side"] == 0
    assert violations["tp_below_primary_timeframe"] == 1
    assert violations["total"] == 0
    assert report["semantic_violation_count"] == 0


def test_m1_standard_deviation_stop_uses_unprefixed_level_one_name() -> None:
    decisions = pd.DataFrame()
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "primary_idea": "standard_deviation",
                "primary_setup_timeframe": "M1",
                "primary_direction": 1,
                "trade_setup_candidate_id": trade_setup_candidate_id("standard_deviation", "M1", 1),
                "trade_setup_schema_version": "trade-setup-overlay-action-v1",
                "price": 100.0,
                "sl_price": 98.0,
                "sl_timeframe": "M1",
                "sl_ref": "standard_deviation_level_1_price",
            }
        ]
    )

    report = summarize_trade_setup_decisions(decisions, trades)

    assert (
        report["structural_violations"]["standard_deviation_sl_not_level_1_on_setup_timeframe"] == 0
    )


def test_trade_setup_decision_diagnostics_export_to_split_artifacts(tmp_path) -> None:
    selected_id = trade_setup_candidate_id("fvg_retest", "M5", 1)
    decisions = pd.DataFrame(
        [
            {
                "step": 1,
                "time": "2025-01-01T00:01:00Z",
                "trade_setup_candidate_id": 0,
                "trade_setup_event_identity_version": "trade-setup-event-identity-v3",
                "trade_setup_source_event_id": None,
                "trade_setup_source_event_identity_status": "not_applicable",
                "trade_setup_source_event_times_ns": [],
                "idea": "",
                "setup_timeframe": "",
                "direction": 0,
                "is_no_trade": True,
                "selection_valid": True,
                "eligible_trade_setup_count": 2,
                "eligible_candidate_ids": [0, selected_id],
                "trade_setup_entropy_nats": 0.8,
                "action_risk": 0.1,
                "entry_rejection_reason": "",
                "entry_state": "FLAT",
                "position_open_after_step": False,
                "trade_event_start_index": 0,
                "trade_event_end_index_exclusive": 0,
            },
            {
                "step": 2,
                "time": "2025-01-01T00:02:00Z",
                "trade_setup_candidate_id": selected_id,
                "trade_setup_event_identity_version": "trade-setup-event-identity-v3",
                "trade_setup_source_event_id": (
                    "trade-setup-event-identity-v3:fvg_retest:M5:1:"
                    "M5_fvg_bull_retest_confirmed_at_time_ns=1735689660000000000:"
                    "M5_fvg_bull_retest_origin_time_ns=1735689360000000000"
                ),
                "trade_setup_source_event_identity_status": "identified",
                "trade_setup_source_event_times_ns": [
                    {
                        "field": "M5_fvg_bull_retest_confirmed_at_time_ns",
                        "time_ns": 1735689660000000000,
                    },
                    {
                        "field": "M5_fvg_bull_retest_origin_time_ns",
                        "time_ns": 1735689360000000000,
                    },
                ],
                "idea": "fvg_retest",
                "setup_timeframe": "M5",
                "direction": 1,
                "is_no_trade": False,
                "selection_valid": True,
                "eligible_trade_setup_count": 2,
                "eligible_candidate_ids": [0, selected_id],
                "trade_setup_entropy_nats": 0.7,
                "action_risk": 0.3,
                "entry_rejection_reason": "",
                "entry_state": "FLAT",
                "position_open_after_step": False,
                "trade_event_start_index": 0,
                "trade_event_end_index_exclusive": 0,
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
        "account_state_trace": pd.DataFrame(
            [
                {
                    "schema_version": "account_state_trace.v1",
                    "state_phase": "post_action_valuation",
                    "rollout_step": 1,
                    "valuation_time": "2025-01-01T00:01:00Z",
                    "balance": 100_000.0,
                    "equity": 100_010.0,
                    "daily_loss": 0.0,
                    "daily_floor_equity": 95_000.0,
                    "max_loss_floor_equity": 90_000.0,
                    "pending_order_limit_price": None,
                    "breach_reason": "",
                }
            ]
        ),
        "account_state_trace_complete": True,
        "policy_decisions": pd.DataFrame(
            [
                {
                    "schema_version": "event_backtest_policy_decision.v2",
                    "decision_id": "bt:d1",
                    "decision_time": "2025-01-01T00:01:00Z",
                    "action": 0,
                    "trade_setup_candidate_id": 3,
                    "trade_setup_eligible": True,
                    "eligible_candidate_count": 2,
                    "eligible_trade_setup_ids": [0, 3],
                    "trade_setup_source_event_id": "source-event-3",
                    "trade_setup_source_event_identity_status": "identified",
                    "position_direction_at_decision": 0,
                    "position_id_at_decision": None,
                    "pending_order_id_at_decision": None,
                },
                {
                    "schema_version": "event_backtest_policy_decision.v1",
                    "decision_id": "bt:d0",
                    "action": 0,
                },
            ]
        ),
        "policy_decisions_complete": True,
        "trade_setup_decisions": decisions,
        "trade_setup_policy_metrics": summarize_trade_setup_decisions(decisions, trades),
        "policy_metadata": {
            "policy_id": "random_eligible_trade_setup_v1",
            "seed": 42,
            "trade_probability": 1.0,
        },
    }
    run_dir = save_run(
        run_dir=tmp_path / "trade_setup-diagnostics",
        train_result=result,
        train_metrics=calculate_metrics(equity, trades=trades, initial_balance=100_000.0),
        save_plots=True,
        save_html=False,
        save_csv=True,
        report_profile="experiment_run_fast",
    )

    split = run_dir / "training"
    saved_decisions = pd.read_csv(split / "trade_setup_decisions.csv")
    saved_policy_decisions = pd.read_csv(split / "policy_decisions.csv")
    saved_account_state = pd.read_csv(split / "account_state_trace.csv")
    assert saved_account_state.loc[0, "schema_version"] == "account_state_trace.v1"
    assert saved_account_state.loc[0, "daily_floor_equity"] == 95_000.0
    assert pd.isna(saved_account_state.loc[0, "pending_order_limit_price"])
    assert len(saved_decisions) == 2
    assert saved_policy_decisions.loc[0, "decision_id"] == "bt:d1"
    assert saved_policy_decisions.loc[0, "trade_setup_eligible"]
    assert saved_decisions["trade_event_start_index"].tolist() == [0, 0]
    assert saved_decisions["trade_event_end_index_exclusive"].tolist() == [0, 0]
    assert saved_decisions["trade_setup_source_event_identity_status"].tolist() == [
        "not_applicable",
        "identified",
    ]
    assert "fvg_retest:M5:1:" in saved_decisions["trade_setup_source_event_id"].iloc[1]
    assert "1735689660000000000" in saved_decisions["trade_setup_source_event_times_ns"].iloc[1]
    assert len(pd.read_csv(split / "trade_setup_selection_matrix.csv")) == 54
    assert len(pd.read_csv(split / "trade_setup_selection_by_idea.csv")) == 6
    assert (split / "trade_setup_selection_heatmap.png").is_file()
    assert (split / "trade_setup_performance_heatmap.png").is_file()
    diagnostics = json.loads((split / "trade_setup_policy_metrics.json").read_text())
    evaluation_diagnostics = json.loads((split / "evaluation_diagnostics.json").read_text())
    assert evaluation_diagnostics["account_state_trace_rows"] == 1
    assert evaluation_diagnostics["account_state_trace_complete"] is True
    assert evaluation_diagnostics["account_state_trace_phases"] == ["post_action_valuation"]
    assert evaluation_diagnostics["account_state_trace_schema"] == "account_state_trace.v1"
    assert evaluation_diagnostics["account_state_reconciliation_status"] == "incomplete"
    assert evaluation_diagnostics["breach_event_ledger_supplied"] is False
    assert evaluation_diagnostics["breach_event_rows"] == 0
    policy_reconciliation = json.loads((split / "policy_decision_reconciliation.json").read_text())
    assert "breach_event_ledger_not_supplied" in policy_reconciliation["incomplete_reasons"]
    reconciliation = json.loads((split / "account_state_reconciliation.json").read_text())
    assert reconciliation["status"] == "incomplete"
    assert "unsupported_or_mixed_trace_schema" in reconciliation["incomplete_reasons"]
    assert evaluation_diagnostics["policy_decisions_rows"] == 2
    assert evaluation_diagnostics["policy_decisions_complete"] is True
    assert evaluation_diagnostics["policy_decisions_schema"] == "mixed"
    assert evaluation_diagnostics["policy_decisions_schema_versions"] == [
        "event_backtest_policy_decision.v1",
        "event_backtest_policy_decision.v2",
    ]
    assert evaluation_diagnostics["policy_metadata"]["seed"] == 42
    assert diagnostics["no_trade_count"] == 1
    assert diagnostics["invalid_selection_count"] == 0
    assert diagnostics["trade_setup_entropy_mean_nats"] == 0.75
    summary = (split / "summary.txt").read_text()
    assert "TRADE SETUP POLICY DIAGNOSTICS" in summary
    assert "Structural violations: 0 unique trades" in summary
