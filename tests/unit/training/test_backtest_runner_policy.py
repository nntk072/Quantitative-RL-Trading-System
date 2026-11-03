from __future__ import annotations

from configuration import load_config
from training.runner.backtest import _configured_backtest_policy


def test_configured_backtest_runner_resolves_legacy_daily_pnl_basis() -> None:
    cfg = load_config()

    policy = _configured_backtest_policy(cfg)
    assert policy.daily_pnl_basis == "legacy_gross_closed_losses"
    assert not policy.repeated_payout


def test_configured_backtest_runner_resolves_repeated_payout_lifecycle() -> None:
    cfg = load_config(["trading_policy.mode=repeated_payout"])

    policy = _configured_backtest_policy(cfg)
    assert policy.repeated_payout
    assert policy.daily_pnl_basis == "session_net_equity"
    assert policy.operating_balance == cfg.account.initial_balance
    assert policy.max_agent_risk_frac < 0.01
