from __future__ import annotations

from types import SimpleNamespace

from decisioning.trade_setup import build_trade_setup_action_schema
from evaluation.reporting.run_artifact_writer import (
    _BREACH_EVENT_COLUMNS,
    _extract_ftmo_limits,
    action_schema_manifest,
)


def test_breach_export_preserves_versioned_daily_loss_semantics() -> None:
    assert "daily_loss" in _BREACH_EVENT_COLUMNS
    assert "daily_pnl_basis" in _BREACH_EVENT_COLUMNS


def test_artifact_limits_use_percentages_in_fixed_other_limits_mode() -> None:
    cfg = SimpleNamespace(
        account={"initial_balance": 100_000.0},
        ftmo={
            "limit_value_mode": "fixed_usd",
            "daily_loss_limit": 1.0,
            "daily_loss_limit_pct": 0.05,
            "max_loss_limit": 2.0,
            "max_loss_limit_initial_pct": 0.10,
            "profit_target": 10_000.0,
        },
    )

    assert _extract_ftmo_limits(cfg) == (5_000.0, 10_000.0, 10_000.0)


def test_artifact_action_schema_records_policy_selected_market_limit_coordinates() -> None:
    cfg = SimpleNamespace(
        env={
            "strategy_actions": True,
            "trade_setup_actions": True,
            "agent_entry_execution": True,
        }
    )

    schema = action_schema_manifest(cfg)

    assert (
        schema
        == build_trade_setup_action_schema(
            has_entry_execution=True,
            has_sl_mode=True,
        ).to_dict()
    )
    assert schema is not None
    assert schema["version"] == "trade-setup-entry-execution-action-v2"
    assert schema["has_entry_execution"] is True
    assert "limit_offset_atr" in schema["coordinates"]
    assert "limit_ttl_bars" in schema["coordinates"]


def test_artifact_market_only_schema_remains_the_original_trade_setup_contract() -> None:
    cfg = SimpleNamespace(
        env={
            "strategy_actions": True,
            "trade_setup_actions": True,
            "agent_entry_execution": False,
        }
    )

    schema = action_schema_manifest(cfg)

    assert schema == build_trade_setup_action_schema(has_sl_mode=True).to_dict()
