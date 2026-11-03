from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from simulation.backtest import run_backtest
from simulation.environment.env import TradingEnv
from trading.execution import CostModel
from trading.policy.config import TradingPolicyConfig


@pytest.mark.parametrize("policy_input", ["instance", "resolved_mapping", "full_config"])
def test_repeated_payout_backtest_withdraws_realized_overshoot_and_reports_economic_value(
    policy_input: str,
) -> None:
    prices = np.asarray([100.0, 100.0, 100.0, 102.0, 102.0, 102.0, 102.0])
    index = pd.date_range("2025-01-06 16:30", periods=len(prices), freq="1min", tz="Etc/GMT-3")
    bars = pd.DataFrame(
        {
            "open": prices,
            "high": prices + 0.1,
            "low": prices - 0.1,
            "close": prices,
            "spread": 0.0,
            "session_id": 0,
            "session": "ny",
        },
        index=index,
    )
    features = pd.DataFrame(
        {
            "last_swing_low": np.full(len(index), 99.0),
            "last_swing_high": np.full(len(index), 103.0),
        },
        index=index,
    )
    actions = iter([1, 2, 2, 2, 2, 2])
    policy = TradingPolicyConfig(
        mode="repeated_payout",
        operating_balance=100.0,
        profit_target_balance=101.5,
        account_floor=90.0,
        daily_loss_limit=20.0,
        max_agent_risk_frac=0.009,
    ).validate()
    if policy_input == "instance":
        policy_config: TradingPolicyConfig | dict[str, object] = policy
    elif policy_input == "resolved_mapping":
        policy_config = policy.to_dict()
    else:
        policy_config = {
            "account": {"initial_balance": 100.0},
            "trading_policy": {
                "mode": "repeated_payout",
                "repeated_payout": {
                    "operating_balance": 100.0,
                    "profit_target_balance": 101.5,
                    "account_floor": 90.0,
                    "daily_loss_limit": 20.0,
                    "max_agent_risk_frac": 0.009,
                },
            },
        }

    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions),
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0),
        initial_balance=100.0,
        trading_policy=policy_config,
        use_structure_sl_tp=True,
        risk_frac=0.009,
        rr_ratio=2.0,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=10.0,
        contract_size=1.0,
        exit_action=0,
        block_overnight=False,
    )

    payouts = result["trades"].loc[result["trades"]["type"] == "payout_reset"]
    closes = result["trades"].loc[result["trades"]["type"] == "tp_close"]
    assert len(closes) == 1
    assert len(payouts) == 1
    payout = float(payouts.iloc[0]["payout"])
    assert np.isclose(payout, float(closes.iloc[0]["net_pnl"]))
    assert payout > 0.0
    assert result["cumulative_payouts"] == payout
    assert result["cycle_count"] == 2
    assert result["cycle_successes"] == 1
    assert result["cycle_failures"] == 0
    assert result["account"].balance == 100.0
    assert result["account"].session_start_equity == 100.0
    assert result["ending_total_economic_value"] == 100.0 + payout
    assert result["total_economic_value_curve"].iloc[-1] == 100.0 + payout
    open_event = result["trades"].loc[result["trades"]["type"] == "open"].iloc[0]
    assert open_event["modeled_stop_risk_usd"] <= open_event["approved_risk_usd"]


def test_repeated_payout_backtest_continues_through_multiple_cycles() -> None:
    prices = np.asarray([100.0, 100.0, 100.0, 102.0, 102.0, 102.0, 104.0, 104.0, 104.0])
    index = pd.date_range("2025-01-06 16:30", periods=len(prices), freq="1min", tz="Etc/GMT-3")
    bars = pd.DataFrame(
        {
            "open": prices,
            "high": prices + 0.1,
            "low": prices - 0.1,
            "close": prices,
            "spread": 0.0,
            "session_id": 0,
            "session": "ny",
        },
        index=index,
    )
    features = pd.DataFrame(
        {
            "last_swing_low": [99.0, 99.0, 99.0, 101.0, 101.0, 101.0, 101.0, 101.0, 101.0],
            "last_swing_high": np.full(len(index), 105.0),
        },
        index=index,
    )
    actions = iter([1, 2, 1, 2, 2, 2, 2])
    policy = TradingPolicyConfig(
        mode="repeated_payout",
        operating_balance=100.0,
        profit_target_balance=101.5,
        account_floor=90.0,
        daily_loss_limit=20.0,
        max_agent_risk_frac=0.009,
    ).validate()

    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions),
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0),
        initial_balance=100.0,
        trading_policy=policy,
        use_structure_sl_tp=True,
        risk_frac=0.009,
        rr_ratio=2.0,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=10.0,
        contract_size=1.0,
        exit_action=0,
        block_overnight=False,
    )

    assert len(result["payout_events"]) == 2
    assert result["cycle_count"] == 3
    assert result["cycle_successes"] == 2
    assert result["cycle_failures"] == 0
    assert result["account"].balance == 100.0
    assert result["cumulative_payouts"] > 3.0
    assert result["ending_total_economic_value"] == 100.0 + result["cumulative_payouts"]


def test_repeated_payout_backtest_records_one_failed_cycle_on_account_breach() -> None:
    prices = np.asarray([100.0, 100.0, 100.0, 98.0, 98.0, 98.0])
    index = pd.date_range("2025-01-06 16:30", periods=len(prices), freq="1min", tz="Etc/GMT-3")
    bars = pd.DataFrame(
        {
            "open": prices,
            "high": prices + 0.1,
            "low": prices - 0.1,
            "close": prices,
            "spread": 0.0,
            "session_id": 0,
            "session": "ny",
        },
        index=index,
    )
    features = pd.DataFrame(
        {
            "last_swing_low": np.full(len(index), 99.0),
            "last_swing_high": np.full(len(index), 103.0),
        },
        index=index,
    )
    actions = iter([1, 2, 2, 2, 2])
    policy = TradingPolicyConfig(
        mode="repeated_payout",
        operating_balance=100.0,
        profit_target_balance=101.5,
        account_floor=99.5,
        daily_loss_limit=20.0,
        max_agent_risk_frac=0.009,
    ).validate()

    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions),
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0),
        initial_balance=100.0,
        trading_policy=policy,
        use_structure_sl_tp=True,
        risk_frac=0.009,
        rr_ratio=2.0,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=10.0,
        contract_size=1.0,
        exit_action=0,
        block_overnight=False,
    )

    assert result["cycle_count"] == 1
    assert result["cycle_failures"] == 1
    assert result["cycle_successes"] == 0
    assert result["cycle_events"][0]["outcome"] == "failure"
    assert result["cumulative_payouts"] == 0.0
    assert result["trading_policy_mode"] == "repeated_payout"


def test_repeated_payout_environment_and_backtest_match_controlled_target_and_reset() -> None:
    prices = np.asarray([100.0, 100.0, 100.0, 102.0, 102.0, 102.0, 102.0])
    index = pd.date_range("2025-01-06 16:30", periods=len(prices), freq="1min", tz="Etc/GMT-3")
    bars = pd.DataFrame(
        {
            "open": prices,
            "high": prices + 0.1,
            "low": prices - 0.1,
            "close": prices,
            "spread": 0.0,
            "session_id": 0,
            "session": "ny",
        },
        index=index,
    )
    features = pd.DataFrame(
        {
            "last_swing_low": np.full(len(index), 99.0),
            "last_swing_high": np.full(len(index), 103.0),
        },
        index=index,
    )
    policy = TradingPolicyConfig(
        mode="repeated_payout",
        operating_balance=100.0,
        profit_target_balance=101.5,
        account_floor=90.0,
        daily_loss_limit=20.0,
        max_agent_risk_frac=0.009,
    ).validate()
    cost_model = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0)
    env = TradingEnv(
        bars,
        features,
        obs_window=1,
        initial_balance=100.0,
        cost_model=cost_model,
        guardrail_kwargs={
            "daily_loss_limit": 20.0,
            "max_loss_limit": 10.0,
            "risk_per_trade_limit": 0.9,
            "soft_daily_loss_limit": 0.0,
            "soft_max_loss_limit": 0.0,
            "limit_value_mode": "fixed_usd",
        },
        risk_frac_range=(0.0, 0.009),
        rr_ratio_range=(2.0, 2.0),
        min_lot=0.01,
        max_lot=10.0,
        contract_size=1.0,
        max_loss_per_trade_usd=0.9,
        block_overnight=False,
        episodic=False,
        continuous_actions=True,
        reward_mode="pnl",
        trading_policy=policy.to_dict(),
    )
    env.reset(seed=17)
    for action in (1.0, 0.0, 0.0, 0.0, 0.0):
        env.step(np.asarray([action], dtype=np.float32))

    actions = iter([1, 2, 2, 2, 2, 2])
    backtest = run_backtest(
        bars,
        features,
        lambda _observation: next(actions),
        obs_window=1,
        cost_model=cost_model,
        initial_balance=100.0,
        trading_policy=policy,
        use_structure_sl_tp=True,
        risk_frac=0.009,
        rr_ratio=2.0,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=10.0,
        contract_size=1.0,
        exit_action=0,
        block_overnight=False,
    )

    assert len(env.payout_events) == 1
    assert len(backtest["payout_events"]) == 1
    assert env.cycle_count == backtest["cycle_count"] == 2
    assert env.cumulative_payouts == pytest.approx(backtest["cumulative_payouts"])
    assert env.payout_events[0]["payout"] == pytest.approx(backtest["payout_events"][0]["payout"])
    assert env.account.balance == pytest.approx(backtest["account"].balance)
    assert env.account.equity == pytest.approx(backtest["account"].equity)
    assert env.account.canonical_daily_loss() == pytest.approx(
        backtest["account"].canonical_daily_loss()
    )
    assert env.account.equity + env.cumulative_payouts == pytest.approx(
        backtest["total_economic_value"]
    )
    env_open = next(event for event in env.trade_log if event["type"] == "open")
    backtest_open = backtest["trades"].loc[backtest["trades"]["type"] == "open"].iloc[0]
    assert env_open["lots"] == pytest.approx(backtest_open["lots"])
    env_close = next(event for event in env.trade_log if event["type"] == "tp_close")
    backtest_close = backtest["trades"].loc[backtest["trades"]["type"] == "tp_close"].iloc[0]
    assert env_close["net_pnl"] == pytest.approx(backtest_close["net_pnl"])


def test_repeated_payout_environment_and_backtest_match_payout_then_cycle_breach() -> None:
    prices = np.asarray([100.0, 100.0, 100.0, 103.0, 103.0, 103.0, 100.0, 100.0, 98.0, 98.0, 98.0])
    index = pd.date_range("2025-01-06 16:30", periods=len(prices), freq="1min", tz="Etc/GMT-3")
    bars = pd.DataFrame(
        {
            "open": prices,
            "high": prices + 0.1,
            "low": prices - 0.1,
            "close": prices,
            "spread": 0.0,
            "session_id": 0,
            "session": "ny",
        },
        index=index,
    )
    features = pd.DataFrame(
        {
            "last_swing_low": np.full(len(index), 99.0),
            "last_swing_high": np.full(len(index), 103.0),
        },
        index=index,
    )
    policy = TradingPolicyConfig(
        mode="repeated_payout",
        operating_balance=100.0,
        profit_target_balance=101.4,
        account_floor=99.5,
        daily_loss_limit=20.0,
        max_agent_risk_frac=0.009,
    ).validate()
    cost_model = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0)
    env = TradingEnv(
        bars,
        features,
        obs_window=1,
        initial_balance=100.0,
        cost_model=cost_model,
        guardrail_kwargs={
            "daily_loss_limit": 20.0,
            "max_loss_limit": 0.5,
            "risk_per_trade_limit": 0.9,
            "soft_daily_loss_limit": 0.0,
            "soft_max_loss_limit": 0.0,
            "limit_value_mode": "fixed_usd",
        },
        risk_frac_range=(0.0, 0.009),
        rr_ratio_range=(3.0, 3.0),
        min_lot=0.01,
        max_lot=10.0,
        contract_size=1.0,
        max_loss_per_trade_usd=0.9,
        block_overnight=False,
        episodic=False,
        continuous_actions=True,
        reward_mode="pnl",
        trading_policy=policy.to_dict(),
    )
    env.reset(seed=17)
    env_done = False
    for risk_action in (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0):
        _, _, env_done, _, _ = env.step(np.asarray([risk_action], dtype=np.float32))
        if env_done:
            break

    actions = iter([1, 2, 2, 2, 1, 2, 2, 2, 2, 2])
    backtest = run_backtest(
        bars,
        features,
        lambda _observation: next(actions),
        obs_window=1,
        cost_model=cost_model,
        initial_balance=100.0,
        trading_policy=policy,
        use_structure_sl_tp=True,
        risk_frac=0.009,
        rr_ratio=3.0,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=10.0,
        contract_size=1.0,
        exit_action=0,
        block_overnight=False,
    )

    assert env_done
    assert len(env.payout_events) == len(backtest["payout_events"]) == 1
    assert env.cycle_count == backtest["cycle_count"] == 2
    assert env.cycle_successes == backtest["cycle_successes"] == 1
    assert env.cycle_failures == backtest["cycle_failures"] == 1
    assert env.cumulative_payouts == pytest.approx(backtest["cumulative_payouts"]) == 1.5
    env_failure = [event for event in env.cycle_events if event["outcome"] == "failure"]
    backtest_failure = [
        event for event in backtest["cycle_events"] if event["outcome"] == "failure"
    ]
    assert len(env_failure) == len(backtest_failure) == 1
    assert env_failure[0]["cycle"] == backtest_failure[0]["cycle"] == 2
    assert env_failure[0]["reason"] == backtest_failure[0]["reason"] == "max_drawdown"
    assert env_failure[0]["time"] == backtest_failure[0]["time"]
    assert env.account.balance == pytest.approx(backtest["account"].balance) == 99.0
    assert env.account.equity == pytest.approx(backtest["account"].equity)
    assert env.account.canonical_daily_loss() == pytest.approx(
        backtest["account"].canonical_daily_loss()
    )
    assert env.account.equity + env.cumulative_payouts == pytest.approx(100.5)
    assert env.account.equity + env.cumulative_payouts == pytest.approx(
        backtest["total_economic_value"]
    )
    assert backtest["total_economic_value_curve"].iloc[-1] == pytest.approx(100.5)
