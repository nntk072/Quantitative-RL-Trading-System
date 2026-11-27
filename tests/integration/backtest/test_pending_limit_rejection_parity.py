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
from market_data.loading.ticks import TickBook
from simulation.backtest import policy_actions
from simulation.environment.entries import orders as entry_orders
from trading.execution import CostModel
from trading.strategies.baseline import BaselineStrategy


def test_rejected_pending_limit_has_matching_cancel_reject_and_account_context(
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

    schema = build_trade_setup_action_schema(
        has_sl_mode=True,
        has_entry_execution=True,
    )
    limit_action = np.zeros(schema.width, dtype=np.float32)
    limit_action[schema.indices["trade_setup"]] = trade_setup_center(candidate_id)
    limit_action[schema.indices["stop"]] = -0.4
    limit_action[schema.indices["target"]] = 0.8
    limit_action[schema.indices["sl_mode"]] = -1.0
    limit_action[schema.indices["entry_execution"]] = 1.0
    limit_action[schema.indices["limit_offset_atr"]] = -1.0
    limit_action[schema.indices["limit_ttl_bars"]] = 1.0
    no_trade_action = np.zeros(schema.width, dtype=np.float32)
    no_trade_action[schema.indices["trade_setup"]] = trade_setup_center(NO_TRADE_ID)
    actions = [
        {
            "decision_time_utc": index[i].isoformat(),
            "action": (limit_action if i == 1 else no_trade_action).tolist(),
        }
        for i in range(1, len(index) - 1)
    ]
    tape_path = tmp_path / "pending_limit_rejection_tape.json"
    tape_path.write_text(
        json.dumps({"schema_version": "qrl.task13.action_tape.v1", "actions": actions}),
        encoding="utf-8",
    )
    tick_time = index[2] + pd.Timedelta(seconds=30)
    tickbook = TickBook(
        np.asarray([tick_time.value, (index[-1] + pd.Timedelta(minutes=1)).value]),
        np.asarray([19_999.5, 19_999.5]),
        np.asarray([19_999.75, 19_999.75]),
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
        "agent_entry_execution": True,
        "tickbook": tickbook,
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
        "tickbook": tickbook,
        "execution_seed": 7,
        "strategy": BaselineStrategy(),
        "open_manipulation_bars": 0,
    }

    report = replay_simulator_action_tape(
        bars,
        features,
        tape_path,
        environment_kwargs=environment_kwargs,
        backtest_kwargs=backtest_kwargs,
        run_provenance={
            "window_id": "pending-limit-rejection-unit-window",
            "split": "train",
            "bars_sha256": "1" * 64,
            "features_sha256": "2" * 64,
            "ticks_sha256": "6" * 64,
            "window_manifest_sha256": "3" * 64,
            "resolved_config_sha256": "4" * 64,
            "source_fingerprint": "5" * 64,
            "source_timezone": "UTC",
            "source_clock_model": "synthetic_fixture",
            "session_timezone": "America/New_York",
        },
        seed=7,
    )

    assert report["checks"]["order_events_match"] is True, (
        report["order_event_field_mismatches"],
        [
            (event.get("direction"), event.get("type"))
            for event in report["environment_events"]
            if event.get("type") == "order_cancel"
        ],
        [
            (event.get("direction"), event.get("type"))
            for event in report["backtest_events"]
            if event.get("type") == "order_cancel"
        ],
    )
    assert report["trace_passed"] is True
    assert report["checks"]["account_state_trace_matches"] is True
    for engine_key in ("environment_events", "backtest_events"):
        events = report[engine_key]
        terminal = [
            event
            for event in events
            if event.get("type") in {"order_submit", "order_cancel", "reject"}
        ]
        assert [event["type"] for event in terminal] == [
            "order_submit",
            "order_cancel",
            "reject",
        ]
        assert terminal[1]["order_id"] == terminal[0]["order_id"] == terminal[2]["order_id"]
        assert (
            terminal[1]["decision_id"] == terminal[0]["decision_id"] == terminal[2]["decision_id"]
        )
        assert terminal[1]["reason"] == "entry_rejected_at_limit_fill"
        assert terminal[2].get("reason", terminal[2].get("entry_rejection_reason")) == "no_valid_tp"
        assert pd.Timestamp(terminal[1]["trigger_quote_time"]).tz_convert("UTC") == tick_time
