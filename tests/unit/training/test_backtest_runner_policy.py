from __future__ import annotations

from configuration import load_config
from simulation.environment.trading_environment_factory import cost_model
from trading.policy.config import TradingPolicyConfig
from training.runner.backtest import _configured_backtest_policy


def test_configured_backtest_runner_resolves_static_daily_loss_semantics() -> None:
    cfg = load_config()

    policy = _configured_backtest_policy(cfg)
    assert policy.daily_pnl_basis == "session_net_equity"
    assert policy.daily_loss_includes_open_pnl
    assert policy.daily_loss_limit_pct == 0.05
    assert cost_model(cfg).slippage_points == float(cfg.costs.slippage_points) == 5.0
    assert not policy.repeated_payout


def test_configured_backtest_runner_resolves_repeated_payout_lifecycle() -> None:
    cfg = load_config(["trading_policy.mode=repeated_payout"])

    policy = _configured_backtest_policy(cfg)
    assert policy.repeated_payout
    assert policy.daily_pnl_basis == "session_net_equity"
    assert policy.operating_balance == cfg.account.initial_balance
    assert policy.max_agent_risk_frac < 0.01


def test_historical_dollar_daily_limit_is_normalized_to_initial_equity_fraction() -> None:
    policy = TradingPolicyConfig.from_mapping(
        {
            "operating_balance": 100_000.0,
            "daily_loss_limit": 5_000.0,
            "account_floor": 90_000.0,
        }
    )

    assert policy.daily_loss_limit_pct == 0.05
    assert policy.daily_loss_limit == 5_000.0
    assert policy.account_floor == 90_000.0


def test_account_lifecycle_mode_does_not_change_daily_loss_basis() -> None:
    policy = TradingPolicyConfig(mode="legacy").validate()

    assert policy.daily_pnl_basis == "session_net_equity"
    assert policy.daily_loss_includes_open_pnl
