"""Compatibility conversions for historical trading-policy mappings."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from trading.policy.config import TradingPolicyConfig, resolve_trading_policy


def test_historical_dollar_limits_and_aliases_resolve_to_canonical_policy_fields() -> None:
    policy = resolve_trading_policy(
        {
            "account": {"initial_balance": 80_000.0},
            "trading_policy": {
                "mode": "repeated_payout",
                "repeated_payout": {
                    "operating_balance": 80_000.0,
                    "payout_target_balance": 88_000.0,
                    "daily_loss_limit": 4_000.0,
                    "account_floor_equity": 72_000.0,
                    "agent_risk_min_frac": 0.0,
                    "agent_risk_max_frac": 0.008,
                    "reserve_cost_buffer_usd": 125.0,
                },
            },
        }
    )

    assert policy.daily_loss_limit_pct == pytest.approx(0.05)
    assert policy.daily_loss_limit == pytest.approx(4_000.0)
    assert policy.max_loss_limit_initial_pct == pytest.approx(0.10)
    assert policy.account_floor == pytest.approx(72_000.0)
    assert policy.profit_target_balance == pytest.approx(88_000.0)
    assert policy.min_agent_risk_frac == 0.0
    assert policy.max_agent_risk_frac == pytest.approx(0.008)
    assert policy.execution_reserve_usd == pytest.approx(125.0)


def test_canonical_values_take_precedence_over_historical_aliases() -> None:
    policy = resolve_trading_policy(
        {
            "trading_policy": {
                "repeated_payout": {
                    "daily_loss_limit_pct": 0.04,
                    "daily_loss_limit": 9_000.0,
                    "max_agent_risk_frac": 0.007,
                    "agent_risk_max_frac": 0.003,
                    "execution_reserve_usd": 50.0,
                    "reserve_cost_buffer_usd": 500.0,
                }
            }
        }
    )

    assert policy.daily_loss_limit_pct == pytest.approx(0.04)
    assert policy.max_agent_risk_frac == pytest.approx(0.007)
    assert policy.execution_reserve_usd == pytest.approx(50.0)


@pytest.mark.parametrize("legacy_field", ["daily_loss_limit", "account_floor"])
def test_historical_dollar_conversion_requires_a_positive_operating_balance(
    legacy_field: str,
) -> None:
    values: dict[str, object] = {"operating_balance": 0.0}
    values[legacy_field] = 1.0

    with pytest.raises(ValueError, match="operating balance must be positive"):
        TradingPolicyConfig.from_mapping(values)


def test_missing_policy_blocks_resolve_to_the_same_valid_legacy_defaults() -> None:
    absent = resolve_trading_policy(None)
    empty = resolve_trading_policy({"trading_policy": None})

    assert absent == empty
    assert absent.mode == "legacy"
    assert absent.daily_pnl_basis == "session_net_equity"
    assert absent.daily_loss_includes_open_pnl is True
    assert absent.daily_loss_limit == pytest.approx(5_000.0)


def test_from_mapping_normalizes_historical_limits_and_round_trips_canonical_state() -> None:
    policy = TradingPolicyConfig.from_mapping(
        {
            "mode": "legacy",
            "operating_balance": 80_000.0,
            "account_floor": 68_000.0,
            "daily_loss_limit": 4_000.0,
        }
    ).validate()

    assert policy.max_loss_limit_initial_pct == pytest.approx(0.15)
    assert policy.daily_loss_limit_pct == pytest.approx(0.05)
    assert TradingPolicyConfig.from_mapping(policy.to_dict()).validate() == policy


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"mode": "unknown"}, "unknown trading_policy.mode"),
        ({"risk_state_schema_version": "risk-state-v2"}, "unsupported trading policy risk-state"),
        ({"daily_loss_limit_pct": 1.01}, r"daily-loss percentage must be in \[0, 1\]"),
        ({"daily_pnl_basis": "unsupported"}, "unsupported daily PnL basis"),
        ({"profit_target_balance": 100_000.0}, "target must exceed operating balance"),
        ({"min_agent_risk_frac": 0.001}, "minimum agent risk must be zero"),
        ({"max_agent_risk_frac": 0.01}, r"max agent risk must be in \[0, 0\.01\)"),
        ({"execution_reserve_usd": -1.0}, "execution reserve cannot be negative"),
        ({"payout_trigger": "unrealized_equity"}, "trigger must be realized_balance_flat"),
        ({"continue_after_payout": False}, "evaluation must continue after payout"),
        ({"trailing_dd_limit": 0.01}, "trailing drawdown must be disabled"),
        ({"enforce_remaining_daily_capacity": False}, "must enforce remaining daily capacity"),
        (
            {"enforce_remaining_account_capacity": False},
            "must enforce remaining account capacity",
        ),
    ],
)
def test_repeated_payout_validation_rejects_unsafe_account_policy_overrides(
    overrides: dict[str, Any], message: str
) -> None:
    policy = TradingPolicyConfig(mode="repeated_payout")

    with pytest.raises(ValueError, match=message):
        replace(policy, **overrides).validate()


def test_repeated_payout_rejects_account_floor_at_or_above_zero_operating_balance() -> None:
    policy = TradingPolicyConfig(mode="repeated_payout", operating_balance=0.0)

    with pytest.raises(ValueError, match="account floor must be below operating balance"):
        policy.validate()
