from __future__ import annotations

import pytest

from decisioning.actions import build_action_schema_from_config
from decisioning.trade_setup import build_trade_setup_action_schema


def test_configured_trade_setup_schema_includes_selected_entry_execution() -> None:
    schema = build_action_schema_from_config(
        {
            "trade_setup_actions": True,
            "agent_entry_execution": True,
            "allow_agent_sl_mode": True,
            "allow_agent_tp_mode": True,
            "allow_multi_tp": False,
        }
    )

    assert schema == build_trade_setup_action_schema(
        has_sl_mode=True,
        has_tp_mode=True,
        has_multi_tp=False,
        has_entry_execution=True,
    )


def test_configured_market_only_trade_setup_omits_execution_controls() -> None:
    schema = build_action_schema_from_config(
        {"trade_setup_actions": True, "agent_entry_execution": False}
    )

    assert schema == build_trade_setup_action_schema(
        has_entry_execution=False,
        has_sl_mode=True,
    )
    assert "entry_execution" not in schema.indices


def test_config_rejects_entry_execution_without_setup_actions() -> None:
    with pytest.raises(ValueError, match="agent_entry_execution requires trade_setup_actions"):
        build_action_schema_from_config({"agent_entry_execution": True})
