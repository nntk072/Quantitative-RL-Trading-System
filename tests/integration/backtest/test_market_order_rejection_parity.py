from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest
from research_tools.simulation.evaluation.replay_simulator_action_tape import (
    replay_simulator_action_tape,
)

from decisioning.trade_setup import NO_TRADE_ID, build_trade_setup_action_schema, trade_setup_center
from features.context.trade_setup_candidates import trade_setup_candidate_feature_columns
from simulation.backtest import policy_actions
from simulation.environment.entries import orders as entry_orders
from trading.execution import CostModel
from trading.strategies.baseline import BaselineStrategy


def test_rejected_market_order_has_matching_terminal_event_and_fill_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = pd.date_range("2025-01-06T14:30:00Z", periods=7, freq="1min")
    prices = np.full(len(index), 20_000.0)
    bars = pd.DataFrame(
        {
            "open": prices,
            "high": prices + 2.0,
            "low": prices - 2.0,
            "close": prices,
            "spread": 0.0,
            "session_id": 7,
            "session": "ny",
        },
        index=index,
    )
    features = pd.DataFrame(
        0.0,
        index=index,
        columns=[name for _, name in trade_setup_candidate_feature_columns()],
    )
    features["atr_5"] = 1.0
    candidate_id = 28  # long M1 FVG retest
    features.loc[index[1:], "entry_idea_fvg_retest_M1_long"] = 1.0
    features.loc[index[1:], "fvg_bull_active"] = 1.0
    features.loc[index[1:], "fvg_bull_retest_confirmed_at_time_ns"] = index[1].value
    features.loc[index[1:], "fvg_bull_retest_origin_time_ns"] = index[0].value

    def reject_tp(*args: Any, **kwargs: Any) -> SimpleNamespace:  # noqa: ARG001
        return SimpleNamespace(
            sl_price=19_990.0,
            tp_price=None,
            reject_kind="tp",
            exit_mode="structural",
        )

    monkeypatch.setattr(entry_orders, "place_strategy_order", reject_tp)
    monkeypatch.setattr(policy_actions, "place_strategy_order", reject_tp)

    schema = build_trade_setup_action_schema(has_sl_mode=True)
    long_market_action = np.zeros(schema.width, dtype=np.float32)
    long_market_action[schema.indices["trade_setup"]] = trade_setup_center(candidate_id)
    long_market_action[schema.indices["stop"]] = -0.4
    long_market_action[schema.indices["target"]] = 0.8
    long_market_action[schema.indices["sl_mode"]] = -1.0
    long_market_action[schema.indices["exit"]] = -1.0
    no_trade_action = np.zeros(schema.width, dtype=np.float32)
    no_trade_action[schema.indices["trade_setup"]] = trade_setup_center(NO_TRADE_ID)
    actions = [
        {
            "decision_time_utc": index[i].isoformat(),
            "action": (long_market_action if i == 1 else no_trade_action).tolist(),
        }
        for i in range(1, len(index) - 1)
    ]
    tape_path = tmp_path / "market_rejection_tape.json"
    tape_path.write_text(
        json.dumps({"schema_version": "qrl.task13.action_tape.v1", "actions": actions}),
        encoding="utf-8",
    )
    costs = CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0)
    guardrails = {
        "daily_loss_limit": 5_000.0,
        "max_loss_limit": 10_000.0,
        "risk_per_trade_limit": 1_000.0,
        "soft_daily_loss_limit": 0.0,
        "soft_max_loss_limit": 0.0,
    }
    environment_kwargs = {
        "obs_window": 1,
        "initial_balance": 100_000.0,
        "cost_model": costs,
        "guardrail_kwargs": guardrails,
        "risk_frac_range": (0.001, 0.001),
        "rr_ratio_range": (1.0, 1.0),
        "min_lot": 0.01,
        "max_lot": 1.0,
        "contract_size": 1.0,
        "max_loss_per_trade_usd": 100.0,
        "block_overnight": False,
        "strategy_actions": True,
        "trade_setup_actions": True,
        "fill_latency_bars": 0,
        "strategy": BaselineStrategy(),
        "open_manipulation_bars": 0,
    }
    backtest_kwargs = {
        "obs_window": 1,
        "initial_balance": 100_000.0,
        "cost_model": costs,
        "guardrail_kwargs": guardrails,
        "risk_frac": 0.001,
        "rr_ratio": 1.0,
        "policy_risk_frac_range": (0.001, 0.001),
        "policy_rr_ratio_range": (1.0, 1.0),
        "min_lot": 0.01,
        "max_lot": 1.0,
        "contract_size": 1.0,
        "max_loss_per_trade_usd": 100.0,
        "hold_on_zero": True,
        "block_overnight": False,
        "trade_setup_actions": True,
        "trade_setup_action_schema": schema,
        "trade_setup_geometry": True,
        "strategy": BaselineStrategy(),
        "open_manipulation_bars": 0,
        "execution_seed": 7,
    }

    report = replay_simulator_action_tape(
        bars,
        features,
        tape_path,
        environment_kwargs=environment_kwargs,
        backtest_kwargs=backtest_kwargs,
        run_provenance={
            "window_id": "market-rejection-unit-window",
            "split": "train",
            "bars_sha256": "1" * 64,
            "features_sha256": "2" * 64,
            "window_manifest_sha256": "3" * 64,
            "resolved_config_sha256": "4" * 64,
            "source_fingerprint": "5" * 64,
            "source_timezone": "UTC",
            "source_clock_model": "synthetic_fixture",
            "session_timezone": "America/New_York",
        },
        seed=7,
    )

    assert report["checks"]["order_events_match"] is True, report["order_event_field_mismatches"]
    assert report["trace_passed"] is True
    assert report["checks"]["lifecycle_events_match"] is True
    assert report["checks"]["lifecycle_event_fields_match"] is True
    terminal_events = []
    for engine_key in ("environment_events", "backtest_events"):
        events = report[engine_key]
        rejected = next(
            event
            for event in events
            if event.get("type") == "reject"
            and event.get("reason", event.get("entry_rejection_reason")) == "no_valid_tp"
        )
        canceled = next(
            event
            for event in events
            if event.get("type") == "order_cancel"
            and event.get("reason") == "entry_rejected_at_market_fill"
        )
        submitted = next(event for event in events if event.get("type") == "order_submit")
        assert [
            event["type"]
            for event in events
            if event.get("type") in {"order_submit", "order_cancel", "reject"}
        ] == ["order_submit", "order_cancel", "reject"]
        assert canceled["order_id"] == submitted["order_id"]
        assert rejected["order_id"] == submitted["order_id"]
        assert canceled["decision_id"] == submitted["decision_id"] == rejected["decision_id"]
        assert canceled["decision_bar_time"] == submitted["decision_bar_time"]
        assert canceled["decision_time"] == submitted["decision_time"]
        assert canceled["order_submission_time"] == submitted["order_submission_time"]
        assert pd.Timestamp(rejected["decision_bar_time"]).tz_convert("UTC") == index[1]
        assert pd.Timestamp(rejected["decision_time"]).tz_convert("UTC") == index[2]
        assert pd.Timestamp(canceled["trigger_quote_time"]).tz_convert("UTC") == index[2]
        assert canceled["trigger_quote_bid"] == pytest.approx(20_000.0)
        assert canceled["trigger_quote_ask"] == pytest.approx(20_000.0)
        terminal_events.append((canceled, rejected))

    assert report["environment_final_balance"] == report["backtest_final_balance"]
    assert terminal_events[0][1]["entry_rejection_reason"] == terminal_events[1][1]["reason"]
