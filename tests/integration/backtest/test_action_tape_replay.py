"""Integration contract for replaying a frozen tape through both simulators."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from research_tools.simulation.evaluation.replay_simulator_action_tape import (
    _action_for_backtest,
    _compare_account_state_rows,
    _compare_lifecycle_events,
    _compare_order_events,
    _load_tapes,
    replay_simulator_action_tape,
)

from trading.execution import CostModel

action_tape_replay = importlib.import_module(
    "research_tools.simulation.evaluation.replay_simulator_action_tape"
)
event_backtest = importlib.import_module("simulation.backtest.event_driven_backtest")


def test_decision_valuation_time_uses_current_action_fill_timestamp() -> None:
    resolve_valuation_time = getattr(event_backtest, "_decision_valuation_time", None)
    assert callable(resolve_valuation_time)

    boundary = pd.Timestamp("2025-01-02T15:29:00Z")
    fill_time = pd.Timestamp("2025-01-02T15:29:00.082Z")
    events = [
        {"type": "open", "bar": 7, "decision_id": "bt:d1", "fill_time": fill_time},
        {"type": "open", "bar": 6, "decision_id": "bt:d0", "fill_time": boundary},
        {
            "type": "stop_close",
            "bar": 8,
            "decision_id": "bt:d2",
            "fill_time": boundary + pd.Timedelta(seconds=5),
        },
        {
            "type": "eod_close",
            "bar": 9,
            "decision_id": "bt:d3",
            "fill_time": boundary + pd.Timedelta(seconds=9),
        },
    ]

    assert resolve_valuation_time(boundary, events, 7) == fill_time
    assert resolve_valuation_time(boundary, events, 8) == boundary + pd.Timedelta(seconds=5)
    assert resolve_valuation_time(boundary, events, 9) == boundary + pd.Timedelta(seconds=9)


def test_environment_short_actions_are_adapted_to_backtest_direction() -> None:
    environment_kwargs = {
        "risk_frac_range": (0.001, 0.003),
        "rr_ratio_range": (1.0, 3.0),
    }
    backtest_kwargs = {"risk_frac": 0.001, "rr_ratio": 1.0}

    assert _action_for_backtest(10, environment_kwargs, backtest_kwargs) == -1
    assert _action_for_backtest(1, environment_kwargs, backtest_kwargs) == 1
    with pytest.raises(ValueError, match="risk variant"):
        _action_for_backtest(
            10,
            environment_kwargs,
            {**backtest_kwargs, "risk_frac": 0.002},
        )


def test_environment_and_backtest_can_replay_separate_decision_clocks(
    tmp_path: Path,
) -> None:
    index = pd.date_range("2026-01-08T14:30:00Z", periods=7, freq="1min")
    bars = pd.DataFrame({"session": "ny"}, index=index)
    features = pd.DataFrame(index=index)
    environment_tape = tmp_path / "environment_actions.json"
    backtest_tape = tmp_path / "backtest_actions.json"
    environment_tape.write_text(
        json.dumps(
            {
                "schema_version": "qrl.task13.action_tape.v1",
                "actions": [
                    {"decision_time_utc": index[i].isoformat(), "action": 0}
                    for i in (1, 2, 3, 4, 5, 6)
                ],
            }
        ),
        encoding="utf-8",
    )
    backtest_tape.write_text(
        json.dumps(
            {
                "schema_version": "qrl.task13.action_tape.v1",
                "actions": [
                    {"decision_time_utc": index[i].isoformat(), "action": 0} for i in (2, 4, 5)
                ],
            }
        ),
        encoding="utf-8",
    )

    environment, backtest, _ = _load_tapes(
        environment_tape,
        bars,
        features,
        {"obs_window": 1},
        {"obs_window": 1},
        backtest_tape_path=backtest_tape,
    )

    assert len(environment.actions) == 6
    assert len(backtest.actions) == 3
    assert [stamp for stamp, _ in backtest.actions] == [index[i] for i in (2, 4, 5)]


def test_frozen_tape_binds_environment_and_backtest_decisions_to_same_bars(
    tmp_path: Path,
) -> None:
    index = pd.date_range("2026-01-08T14:30:00Z", periods=7, freq="1min")
    prices = np.asarray([100.0, 100.0, 101.0, 102.0, 102.0, 102.0, 102.0])
    bars = pd.DataFrame(
        {
            "open": prices,
            "high": prices + 0.1,
            "low": prices - 0.1,
            "close": prices,
            "spread": 0.0,
            "session_id": 7,
            "session": "ny",
        },
        index=index,
    )
    features = pd.DataFrame(
        {
            "last_swing_low": np.full(len(index), 90.0),
            "last_swing_high": np.full(len(index), 110.0),
        },
        index=index,
    )
    tape_path = tmp_path / "action_tape.json"
    tape_path.write_text(
        json.dumps(
            {
                "schema_version": "qrl.task13.action_tape.v1",
                "actions": [
                    {"decision_time_utc": index[i].isoformat(), "action": action}
                    for i, action in zip((1, 2, 3, 4, 5), (1, 0, 19, 0, 0), strict=True)
                ],
            }
        ),
        encoding="utf-8",
    )
    cost_model = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0)
    guardrails: dict[str, Any] = {
        "daily_loss_limit": 5_000.0,
        "max_loss_limit": 10_000.0,
        "risk_per_trade_limit": 1_000.0,
        "soft_daily_loss_limit": 0.0,
        "soft_max_loss_limit": 0.0,
    }
    environment_kwargs: dict[str, Any] = {
        "obs_window": 1,
        "initial_balance": 100_000.0,
        "cost_model": cost_model,
        "guardrail_kwargs": guardrails,
        "risk_frac_range": (0.001, 0.001),
        "rr_ratio_range": (1.0, 1.0),
        "min_lot": 0.01,
        "max_lot": 1.0,
        "contract_size": 1.0,
        "max_loss_per_trade_usd": 100.0,
        "block_overnight": False,
    }
    backtest_kwargs: dict[str, Any] = {
        "obs_window": 1,
        "initial_balance": 100_000.0,
        "cost_model": cost_model,
        "guardrail_kwargs": guardrails,
        "risk_frac": 0.001,
        "rr_ratio": 1.0,
        "min_lot": 0.01,
        "max_lot": 1.0,
        "contract_size": 1.0,
        "max_loss_per_trade_usd": 100.0,
        "hold_on_zero": True,
        "block_overnight": False,
        "exit_action": 19,
        "execution_seed": 7,
        "use_structure_sl_tp": True,
    }

    report = replay_simulator_action_tape(
        bars,
        features,
        tape_path,
        environment_kwargs=environment_kwargs,
        backtest_kwargs=backtest_kwargs,
        run_provenance={
            "window_id": "synthetic-train-only-test",
            "split": "train",
            "bars_sha256": "1" * 64,
            "features_sha256": "2" * 64,
            "window_manifest_sha256": "5" * 64,
            "resolved_config_sha256": "3" * 64,
            "source_fingerprint": "4" * 64,
            "source_timezone": "UTC",
            "source_clock_model": "synthetic_fixture",
            "session_timezone": "America/New_York",
        },
        seed=7,
    )

    assert report["environment_decision_times_utc"] == report["tape_decision_times_utc"]
    assert report["backtest_decision_bar_times_utc"] == report["tape_decision_times_utc"]
    assert report["environment_lifecycle"] == report["backtest_lifecycle"]
    assert report["environment_lifecycle"] == ["open", "close"]
    assert report["checks"]["lifecycle_event_fields_match"] is True, report[
        "lifecycle_event_field_mismatches"
    ]
    assert report["checks"]["order_events_match"] is True, (
        report["order_event_field_mismatches"],
        [event.get("type") for event in report["environment_events"]],
        [event.get("type") for event in report["backtest_events"]],
    )
    assert report["checks"] == {
        "environment_consumed_tape_at_exact_times": True,
        "backtest_decisions_match_tape_times": True,
        "lifecycle_events_match": True,
        "lifecycle_event_fields_match": True,
        "order_events_match": True,
        "account_state_trace_matches": True,
        "final_balance_matches": True,
    }
    assert report["account_state_parity"]["matched_decision_count"] == len(
        report["tape_decision_times_utc"]
    )
    assert all(
        row["environment_state_phase"] == row["backtest_state_phase"] == "post_action_valuation"
        for row in report["account_state_parity"]["rows"]
    )
    assert all(row["mismatches"] == [] for row in report["account_state_parity"]["rows"])
    assert report["trace_passed"] is True
    json.dumps(report, allow_nan=False)

    environment_events = [
        {
            "type": "open",
            "direction": 1,
            "decision_bar_time": "2026-01-08T09:31:00-05:00",
            "fill_time": "2026-01-08T14:32:00Z",
            "price": 100.0,
            "lots": 1.0,
            "sl_price": 98.0,
            "tp_price": 102.0,
            "modeled_stop_risk_usd": 2.0,
        }
    ]
    backtest_events = [
        {
            "type": "open",
            "direction": 1,
            "decision_bar_time": "2026-01-08T14:31:00Z",
            "fill_time": "2026-01-08T14:32:00+00:00",
            "price": 100.0,
            "lots": 1.0,
            "sl_price": 98.0,
            "tp_price": 102.0,
            "modeled_stop_risk_usd": 2.0,
        }
    ]
    assert _compare_lifecycle_events(environment_events, backtest_events) == (True, [])
    backtest_events[0]["sl_price"] = 97.0
    same, mismatches = _compare_lifecycle_events(environment_events, backtest_events)
    assert same is False
    assert mismatches == ["open[0].sl_price"]

    with pytest.raises(ValueError, match="initial_balance settings must match"):
        replay_simulator_action_tape(
            bars,
            features,
            tape_path,
            environment_kwargs=environment_kwargs,
            backtest_kwargs={**backtest_kwargs, "initial_balance": 99_999.0},
            run_provenance={
                "window_id": "synthetic-train-only-test",
                "split": "train",
                "bars_sha256": "1" * 64,
                "features_sha256": "2" * 64,
                "window_manifest_sha256": "5" * 64,
                "resolved_config_sha256": "3" * 64,
                "source_fingerprint": "4" * 64,
                "source_timezone": "UTC",
                "source_clock_model": "synthetic_fixture",
                "session_timezone": "America/New_York",
            },
            seed=7,
        )


def test_lifecycle_comparison_ignores_rr_without_a_take_profit() -> None:
    environment_events = [{"type": "open", "direction": 1, "tp_price": np.nan, "rr_ratio": np.nan}]
    backtest_events = [{"type": "open", "direction": 1, "tp_price": None, "rr_ratio": 1.0}]

    assert _compare_lifecycle_events(environment_events, backtest_events) == (True, [])


def test_account_comparison_normalizes_engine_order_ids_and_utc_timestamps() -> None:
    environment_rows = [
        {
            "decision_bar_time_utc": "2026-01-08T14:30:00+00:00",
            "account_state": {
                "decision_time": pd.Timestamp("2026-01-08T17:31:00+03:00"),
                "valuation_time": pd.Timestamp("2026-01-08T17:31:00+03:00"),
                "state_phase": "post_action_valuation",
                "pending_order_id": "e2:d59:limit",
                "pending_order_decision_id": "e2:d247",
                "pending_order_submission_time": pd.Timestamp("2026-01-08T17:31:00+03:00"),
                "pending_order_expiry_time": pd.Timestamp("2026-01-08T18:31:00+03:00"),
            },
            "reward": 0.0,
            "reward_parts": {},
        }
    ]
    backtest_trace = pd.DataFrame(
        [
            {
                "decision_time": pd.Timestamp("2026-01-08T14:31:00Z"),
                "valuation_time": pd.Timestamp("2026-01-08T14:31:00Z"),
                "state_phase": "pre_action_valuation",
                "pending_order_id": "bt:o1",
                "pending_order_decision_id": "bt:d242",
                "pending_order_submission_time": pd.Timestamp("2026-01-08T14:31:00Z"),
                "pending_order_expiry_time": pd.Timestamp("2026-01-08T15:31:00Z"),
            }
        ]
    )

    same, rows = _compare_account_state_rows(
        environment_rows,
        backtest_trace,
        backtest_policy_decision_times_utc={"2026-01-08T14:30:00+00:00"},
    )

    assert same is True
    assert rows[0]["mismatches"] == []


def test_order_comparison_matches_cross_engine_ids_and_checks_fill_quote() -> None:
    environment_events = [
        {
            "type": "order_fill",
            "decision_id": "e2:d71",
            "order_id": "e2:d59:limit",
            "fill_time": None,
            "order_type": "limit",
            "time": pd.Timestamp("2026-01-08T17:31:00.082+03:00"),
            "direction": 1,
            "trade_setup_candidate_id": 28,
            "limit_price": 100.0,
            "bid": 99.75,
            "ask": 100.0,
            "price": 100.0,
        }
    ]
    backtest_events = [
        {
            "type": "order_fill",
            "decision_id": "bt:d83",
            "order_id": "bt:o1",
            "fill_time": pd.NaT,
            "order_type": "limit",
            "reason": np.nan,
            "time": pd.Timestamp("2026-01-08T14:31:00.082Z"),
            "direction": 1,
            "trade_setup_candidate_id": 28,
            "limit_price": 100.0,
            "bid": 99.75,
            "ask": 100.0,
            "price": 100.0,
        }
    ]

    assert _compare_order_events(environment_events, backtest_events) == (True, [])
    backtest_events[0]["ask"] = 100.25
    same, mismatches = _compare_order_events(environment_events, backtest_events)
    assert same is False
    assert mismatches == ["order_fill[0].ask"]


def test_order_comparison_reports_different_event_shapes_without_raising() -> None:
    environment_events = [
        {
            "type": "order_cancel",
            "decision_time": pd.Timestamp("2026-01-08T14:31:00Z"),
            "order_submission_time": pd.Timestamp("2026-01-08T14:30:00Z"),
            "expiry_time": pd.Timestamp("2026-01-08T15:30:00Z"),
            "order_type": "limit",
            "limit_price": 100.0,
        }
    ]
    backtest_events = [
        {
            "type": "reject",
            "decision_bar_time": pd.Timestamp("2026-01-08T14:30:00Z"),
            "decision_time": pd.Timestamp("2026-01-08T14:31:00Z"),
        }
    ]

    same, mismatches = _compare_order_events(environment_events, backtest_events)

    assert same is False
    assert "event_type[0]" in mismatches
