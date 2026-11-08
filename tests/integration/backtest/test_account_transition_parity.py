"""Controlled account-transition parity between the environment and backtest."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
import pytest

from evaluation.reporting.account_state_trace_reconciliation import (
    reconcile_account_state_trace,
)
from market_data.loading.ticks import TickBook, TickExecutionUnavailable
from simulation.backtest import run_backtest
from simulation.environment.env import TradingEnv
from trading.execution import CostModel
from trading.risk import RiskDailyPnlBasis
from trading.risk.ftmo_clock import FTMOMidnightSnapshotUnavailable


def _ftmo_midnight_fixture() -> tuple[
    pd.DataFrame, pd.DataFrame, CostModel, dict[str, object], dict[str, float]
]:
    index = pd.date_range("2026-01-08T22:55:00Z", periods=11, freq="1min")
    prices = np.asarray(
        [100.0, 100.0, 101.0, 102.0, 102.0, 102.0, 102.0, 102.0, 102.0, 102.0, 102.0]
    )
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
    cost_model = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0)
    policy = {
        "mode": "legacy",
        "daily_pnl_basis": "ftmo_midnight_balance",
        "daily_loss_includes_open_pnl": True,
        "daily_loss_reset_source": "prague_midnight",
    }
    guardrails = {
        "daily_loss_limit": 5_000.0,
        "max_loss_limit": 10_000.0,
        "risk_per_trade_limit": 1_000.0,
        "soft_daily_loss_limit": 0.0,
        "soft_max_loss_limit": 0.0,
    }
    return bars, features, cost_model, policy, guardrails


def test_prague_midnight_resets_flat_account_without_session_transition() -> None:
    bars, features, cost_model, policy, guardrails = _ftmo_midnight_fixture()
    actions = (1, 0, 19, 0, 0, 0, 0, 0, 0, 0)
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        cost_model=cost_model,
        trading_policy=policy,
        guardrail_kwargs=guardrails,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        block_overnight=False,
    )
    env.reset(seed=7)
    for action in actions:
        env.step(action)

    action_index = 0

    def backtest_policy(_observation: np.ndarray[Any, Any]) -> int:
        nonlocal action_index
        action = actions[action_index] if action_index < len(actions) else 0
        action_index += 1
        return action

    result = run_backtest(
        bars,
        features,
        backtest_policy,
        obs_window=1,
        cost_model=cost_model,
        trading_policy=policy,
        guardrail_kwargs=guardrails,
        risk_frac=0.001,
        rr_ratio=1.0,
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        hold_on_zero=True,
        block_overnight=False,
        exit_action=19,
    )

    assert bars["session_id"].nunique() == 1
    assert env.account.balance == pytest.approx(100_001.0)
    assert result["account"].balance == pytest.approx(100_001.0)
    assert env.account.session_start_balance == pytest.approx(100_001.0)
    assert result["account"].session_start_balance == pytest.approx(100_001.0)
    trace = result["account_state_trace"]
    post_midnight = trace.loc[
        pd.to_datetime(trace["decision_time"], utc=True) == pd.Timestamp("2026-01-08T23:00:00Z")
    ]
    assert len(post_midnight) == 1
    assert float(post_midnight.iloc[0]["session_start_balance"]) == pytest.approx(100_001.0)
    assert post_midnight.iloc[0]["daily_pnl_basis"] == "ftmo_midnight_balance"


def test_open_position_crossing_prague_midnight_fails_closed_in_both_engines() -> None:
    bars, features, cost_model, policy, guardrails = _ftmo_midnight_fixture()
    actions = (1, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        cost_model=cost_model,
        trading_policy=policy,
        guardrail_kwargs=guardrails,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        block_overnight=False,
    )
    env.reset(seed=7)
    with pytest.raises(
        FTMOMidnightSnapshotUnavailable, match="open position crossed FTMO midnight"
    ):
        for action in actions:
            env.step(action)

    action_index = 0

    def backtest_policy(_observation: np.ndarray[Any, Any]) -> int:
        nonlocal action_index
        action = actions[action_index] if action_index < len(actions) else 0
        action_index += 1
        return action

    with pytest.raises(
        FTMOMidnightSnapshotUnavailable,
        match="open position crossed FTMO midnight",
    ):
        run_backtest(
            bars,
            features,
            backtest_policy,
            obs_window=1,
            cost_model=cost_model,
            trading_policy=policy,
            guardrail_kwargs=guardrails,
            risk_frac=0.001,
            rr_ratio=1.0,
            min_lot=0.01,
            max_lot=1.0,
            contract_size=1.0,
            max_loss_per_trade_usd=100.0,
            hold_on_zero=True,
            block_overnight=False,
            exit_action=19,
        )


@pytest.mark.parametrize("initial_balance", [50_000.0, 100_000.0])
@pytest.mark.parametrize(
    "daily_pnl_basis",
    ["legacy_gross_closed_losses", "session_net_equity"],
)
def test_environment_and_backtest_reconcile_realized_and_open_account_transitions(
    initial_balance: float,
    daily_pnl_basis: RiskDailyPnlBasis,
) -> None:
    """Match a loss, a reset, an open mark, a win, and a second-session loss.

    The flat, synthetic quote trace makes the two APIs' declared fill path
    comparable without asserting real-feed timing or an external session clock.
    """
    prices = np.asarray(
        [100.0, 100.0, 101.0, 99.0, 99.0, 100.0, 101.0, 103.0, 103.0, 103.0, 100.0, 98.0, 98.0]
    )
    index = pd.date_range("2025-01-06 16:30", periods=len(prices), freq="1min", tz="Etc/GMT-3")
    bars = pd.DataFrame(
        {
            "open": prices,
            "high": prices + 0.1,
            "low": prices - 0.1,
            "close": prices,
            "spread": 0.0,
            "session_id": [0] * 5 + [1] * (len(prices) - 5),
            "session": "ny",
        },
        index=index,
    )
    features = pd.DataFrame(
        {
            "last_swing_low": np.full(len(prices), 90.0),
            "last_swing_high": np.full(len(prices), 110.0),
        },
        index=index,
    )
    cost_model = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0)
    guardrails = {
        "limit_value_mode": "fixed_usd",
        "daily_loss_limit_pct": 0.10,
        "max_loss_limit_initial_pct": 0.20,
        "risk_per_trade_limit": 10_000.0,
        "soft_daily_loss_limit_pct": 0.0,
        "soft_max_loss_limit_initial_pct": 0.0,
    }
    actions = [1, 0, 19, 0, 1, 0, 0, 19, 1, 0, 19]

    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        initial_balance=initial_balance,
        cost_model=cost_model,
        guardrail_kwargs=guardrails,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        block_overnight=False,
    )
    env.reset(seed=7)
    env_open_pnl_at_mark: float | None = None
    env_account_trace_rows: list[dict[str, Any]] = []
    for action_index, action in enumerate(actions):
        _, _, _, _, info = env.step(action)
        env_account_trace_rows.append(info["account_state_snapshot"])
        if action_index == 6:
            env_open_pnl_at_mark = float(env.account.open_pnl)

    env_opens = [event for event in env.trade_log if event["type"] == "open"]
    assert env_opens
    for event in env_opens:
        assert event["decision_time"] == event["signal_time"]
        assert event["decision_time"] == event["order_submission_time"]
        assert event["decision_bar_time"] < event["decision_time"]

    action_iter: Sequence[int] = tuple(actions)
    action_index = 0

    def policy(_observation: np.ndarray[Any, Any]) -> int:
        nonlocal action_index
        if action_index >= len(action_iter):
            return 0
        action = action_iter[action_index]
        action_index += 1
        return action

    result = run_backtest(
        bars,
        features,
        policy,
        obs_window=1,
        cost_model=cost_model,
        initial_balance=initial_balance,
        guardrail_kwargs=guardrails,
        risk_frac=0.001,
        rr_ratio=1.0,
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        hold_on_zero=True,
        block_overnight=False,
        exit_action=19,
        daily_pnl_basis=daily_pnl_basis,
    )
    account_trace = result["account_state_trace"]
    assert result["account_state_trace_complete"] is True
    assert len(account_trace) == len(result["equity"])
    assert account_trace["schema_version"].eq("account_state_trace.v2").all()
    assert account_trace["state_phase"].eq("pre_action_valuation").all()
    env_account_trace = pd.DataFrame.from_records(env_account_trace_rows)
    assert len(env_account_trace) == len(actions)
    assert env_account_trace["state_phase"].eq("post_action_valuation").all()
    env_reconciliation = reconcile_account_state_trace(
        env_account_trace,
        pd.DataFrame.from_records(env.trade_log),
        breach_events=[],
    )
    assert env_reconciliation["status"] == "matched", env_reconciliation["failures"]
    backtest_reconciliation = reconcile_account_state_trace(
        account_trace, result["trades"], breach_events=[]
    )
    assert backtest_reconciliation["status"] == "matched", backtest_reconciliation["failures"]
    backtest_shared_marks = account_trace.iloc[: len(actions)]
    np.testing.assert_allclose(
        env_account_trace["equity"].to_numpy(dtype=float),
        backtest_shared_marks["equity"].to_numpy(dtype=float),
        rtol=0.0,
        atol=1e-9,
        err_msg="cross-engine equity marks differ at the shared synthetic boundaries",
    )
    assert np.any(
        env_account_trace["balance"].to_numpy(dtype=float)
        != backtest_shared_marks["balance"].to_numpy(dtype=float)
    )
    for trace in (env_account_trace, backtest_shared_marks):
        np.testing.assert_allclose(
            trace["balance"].to_numpy(dtype=float) + trace["open_pnl"].to_numpy(dtype=float),
            trace["equity"].to_numpy(dtype=float),
            rtol=0.0,
            atol=1e-9,
        )
    np.testing.assert_allclose(
        account_trace["equity"].to_numpy(dtype=float),
        result["equity"].to_numpy(dtype=float),
        rtol=0.0,
        atol=1e-9,
    )
    np.testing.assert_allclose(
        account_trace["daily_floor_equity"].to_numpy(dtype=float),
        account_trace["session_start_equity"].to_numpy(dtype=float)
        - account_trace["daily_loss_limit_usd"].to_numpy(dtype=float),
        rtol=0.0,
        atol=1e-9,
    )

    env_closes = [event for event in env.trade_log if event["type"] == "close"]
    backtest_closes = result["trades"].loc[result["trades"]["type"] == "close"]
    env_close_pnl = np.asarray([float(event["pnl"]) for event in env_closes])
    backtest_close_pnl = backtest_closes["pnl"].to_numpy(dtype=float)
    np.testing.assert_allclose(env_close_pnl, backtest_close_pnl, rtol=0.0, atol=1e-9)
    env_close_times = [pd.Timestamp(event["fill_time"]) for event in env_closes]
    backtest_close_times = [pd.Timestamp(value) for value in backtest_closes["fill_time"]]
    assert env_close_times == backtest_close_times
    close_cash_by_time: dict[pd.Timestamp, float] = {}
    for event in env_closes:
        fill_time = pd.Timestamp(event["fill_time"])
        close_cash_by_time[fill_time] = close_cash_by_time.get(fill_time, 0.0) + float(event["pnl"])
    for row_index, env_row in env_account_trace.iterrows():
        balance_delta = float(env_row["balance"]) - float(
            backtest_shared_marks.iloc[row_index]["balance"]
        )
        if abs(balance_delta) <= 1e-9:
            continue
        boundary_time = pd.Timestamp(env_row["valuation_time"])
        assert boundary_time in close_cash_by_time
        assert balance_delta == pytest.approx(close_cash_by_time[boundary_time])
    assert env_close_pnl[0] < 0.0
    assert env_close_pnl[1] > 0.0
    assert env_close_pnl[2] < 0.0

    # Environment equity is recorded after each action; backtest equity is
    # recorded on the corresponding shared bar horizon. This synthetic trace
    # holds exit-bar quotes flat across adjacent rows so those values align.
    np.testing.assert_allclose(
        np.asarray(env.equity_curve[1:], dtype=float),
        result["equity"].iloc[: len(actions)].to_numpy(dtype=float),
        rtol=0.0,
        atol=1e-9,
    )

    first_session_close_balance = initial_balance + env_close_pnl[0]
    assert env_open_pnl_at_mark is not None and env_open_pnl_at_mark > 0.0
    backtest_open_pnl_at_mark = float(result["equity"].iloc[6]) - first_session_close_balance
    assert env_open_pnl_at_mark == pytest.approx(backtest_open_pnl_at_mark)
    assert env.account.session_start_balance == pytest.approx(first_session_close_balance)
    assert result["account"].session_start_balance == pytest.approx(first_session_close_balance)

    expected_final_balance = initial_balance + float(env_close_pnl.sum())
    assert env.account.balance == pytest.approx(expected_final_balance)
    assert result["account"].balance == pytest.approx(expected_final_balance)
    # The legacy counter resets at the supplied session boundary and counts
    # only the second-session loss; the earlier loss remains in total equity.
    expected_second_session_loss = -float(env_close_pnl[2])
    assert env.account.daily_loss == pytest.approx(expected_second_session_loss)
    assert result["account"].daily_loss == pytest.approx(expected_second_session_loss)
    assert result["account"].daily_pnl_basis == daily_pnl_basis
    expected_session_loss = max(0.0, -float(env_close_pnl[1:].sum()))
    expected_daily_loss = (
        expected_session_loss
        if daily_pnl_basis == "session_net_equity"
        else expected_second_session_loss
    )
    assert result["account"].canonical_daily_loss() == pytest.approx(expected_daily_loss)


@pytest.mark.parametrize(
    ("tick_execution_required", "randomized_fill_latency_ms", "tick_slippage"),
    [(True, 0.0, 0.0), (True, 0.0, 0.1), (True, 30.0, 0.1), (False, 30.0, 0.0)],
)
@pytest.mark.parametrize(("env_action", "direction"), [(1, 1), (10, -1)])
def test_environment_and_backtest_match_on_one_shared_tick_execution_trace(
    tick_execution_required: bool,
    randomized_fill_latency_ms: float,
    tick_slippage: float,
    env_action: int,
    direction: int,
) -> None:
    """Reconcile both execution paths against identical, unambiguous quotes."""
    index = pd.date_range("2025-01-06 14:30:00Z", periods=6, freq="1min")
    prices = np.full(len(index), 100.0)
    bars = pd.DataFrame(
        {
            "open": prices,
            "high": prices + 1.0,
            "low": prices - 1.0,
            "close": prices,
            "spread": 0.0,
            "session_id": 1,
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
    tick_times = np.asarray(
        [
            (index[2] + pd.Timedelta(milliseconds=100)).value,
            (index[3] + pd.Timedelta(milliseconds=100)).value,
        ],
        dtype=np.int64,
    )
    tickbook = TickBook(
        tick_times,
        np.asarray([100.0, 99.5]),
        np.asarray([100.2, 99.7]),
    )
    cost_model = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=2.0)
    env = TradingEnv(
        bars,
        features,
        obs_window=1,
        initial_balance=50_000.0,
        cost_model=cost_model,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        block_overnight=False,
        reward_mode="pnl",
        tickbook=tickbook,
        tick_execution_required=tick_execution_required,
        randomized_fill_latency_ms=randomized_fill_latency_ms,
        tick_fill_slippage_points=tick_slippage,
    )
    env.reset(seed=7)
    env.step(env_action)
    env.step(19)

    actions = iter((direction, 19))

    def policy(_observation: np.ndarray[Any, Any]) -> int:
        return next(actions, 0)

    result = run_backtest(
        bars,
        features,
        policy,
        obs_window=1,
        cost_model=cost_model,
        initial_balance=50_000.0,
        max_loss_per_trade_usd=100.0,
        tickbook=tickbook,
        tick_execution_required=tick_execution_required,
        randomized_fill_latency_ms=randomized_fill_latency_ms,
        tick_fill_slippage_points=tick_slippage,
        execution_seed=7,
        block_overnight=False,
        hold_on_zero=True,
        exit_action=19,
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        risk_frac=0.001,
        rr_ratio=1.0,
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
    )

    env_open = next(event for event in env.trade_log if event["type"] == "open")
    env_close = next(event for event in env.trade_log if event["type"] == "close")
    backtest_open = result["trades"].loc[result["trades"]["type"] == "open"].iloc[0]
    backtest_close = result["trades"].loc[result["trades"]["type"] == "close"].iloc[0]
    expected_open_price = 100.2 + tick_slippage if direction == 1 else 100.0 - tick_slippage
    expected_close_price = 99.5 - tick_slippage if direction == 1 else 99.7 + tick_slippage
    assert env_open["price"] == pytest.approx(expected_open_price)
    assert env_close["price"] == pytest.approx(expected_close_price)

    for env_event, backtest_event in (
        (env_open, backtest_open),
        (env_close, backtest_close),
    ):
        assert env_event["fill_quote_source"] == backtest_event["fill_quote_source"] == "tick"
        assert pd.Timestamp(env_event["fill_time"]).tz_convert("UTC") == pd.Timestamp(
            backtest_event["fill_time"]
        ).tz_convert("UTC")
        assert pd.Timestamp(env_event["order_submission_time"]).tz_convert("UTC") == pd.Timestamp(
            backtest_event["order_submission_time"]
        ).tz_convert("UTC")
        assert pd.Timestamp(env_event["decision_bar_time"]).tz_convert("UTC") == pd.Timestamp(
            backtest_event["decision_bar_time"]
        ).tz_convert("UTC")
        assert env_event["price"] == pytest.approx(backtest_event["price"])
        assert pd.Timestamp(env_event["actual_tick_time"]) == pd.Timestamp(
            backtest_event["actual_tick_time"]
        )

    exit_quote = tickbook.execution_quote_event_at(index[3])
    assert exit_quote is not None
    assert env_close["fill_time"] == exit_quote[0]
    assert env_close["pnl"] == pytest.approx(backtest_close["pnl"])
    assert env.account.balance == pytest.approx(result["account"].balance)
    lots = float(env_open["lots"])
    expected_balance = 50_000.0 + (
        (expected_close_price - expected_open_price) * direction * lots
        - 2.0 * cost_model.total_cost(lots)
    )
    assert env.account.balance == pytest.approx(expected_balance)


def test_environment_and_backtest_consume_actions_while_delayed_entry_is_pending() -> None:
    """Keep policy timing and exits aligned while a whole-bar entry is pending."""
    index = pd.date_range("2025-01-06 14:30:00Z", periods=12, freq="1min")
    prices = np.full(len(index), 100.0)
    bars = pd.DataFrame(
        {
            "open": prices,
            "high": prices + 1.0,
            "low": prices - 1.0,
            "close": prices,
            "spread": 0.0,
            "session_id": 1,
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
    tickbook = TickBook(
        np.asarray(
            [index[i].value for i in (5, 8, 9)] + [(index[-1] + pd.Timedelta(minutes=1)).value],
            dtype=np.int64,
        ),
        np.asarray([100.0, 99.5, 99.2, 99.0]),
        np.asarray([100.2, 99.7, 99.4, 99.2]),
    )
    cost_model = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0)
    # Environment action IDs 1 and 10 encode long and short; the backtest
    # adapter below receives their signed directions directly.
    actions = [1, 0, 0, 0, 10, 10, 19, 0, 0, 0, 0]
    env = TradingEnv(
        bars,
        features,
        obs_window=1,
        initial_balance=50_000.0,
        cost_model=cost_model,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        block_overnight=False,
        fill_latency_bars=3,
        reward_mode="pnl",
        tickbook=tickbook,
        tick_execution_required=True,
    )
    env.reset(seed=7)
    env_infos = []
    for action in actions:
        env_infos.append(env.step(action)[-1])

    action_index = 0

    def policy(_observation: np.ndarray[Any, Any]) -> int:
        nonlocal action_index
        action = actions[action_index]
        action_index += 1
        return -1 if action == 10 else action

    result = run_backtest(
        bars,
        features,
        policy,
        obs_window=1,
        cost_model=cost_model,
        initial_balance=50_000.0,
        risk_frac=0.001,
        rr_ratio=1.0,
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        hold_on_zero=True,
        block_overnight=False,
        exit_action=19,
        fill_latency_bars=3,
        tickbook=tickbook,
        tick_execution_required=True,
    )

    env_opens = [event for event in env.trade_log if event["type"] == "open"]
    bt_opens = [event for event in result["trades"].to_dict("records") if event["type"] == "open"]
    env_closes = [event for event in env.trade_log if event["type"] == "close"]
    bt_closes = [event for event in result["trades"].to_dict("records") if event["type"] == "close"]
    env_orders = [event for event in env.trade_log if event["type"] == "order_submit"]
    bt_orders = [
        event for event in result["trades"].to_dict("records") if event["type"] == "order_submit"
    ]
    assert len(env_opens) == len(bt_opens) == 2
    assert len(env_closes) == len(bt_closes) == 1
    assert len(env_orders) == len(bt_orders) == 2
    for env_order, bt_order in zip(env_orders, bt_orders, strict=True):
        assert pd.Timestamp(env_order["decision_bar_time"]).tz_convert("UTC") == pd.Timestamp(
            bt_order["decision_bar_time"]
        ).tz_convert("UTC")
        assert pd.Timestamp(env_order["order_submission_time"]).tz_convert("UTC") == pd.Timestamp(
            bt_order["order_submission_time"]
        ).tz_convert("UTC")
        assert pd.Timestamp(env_order["expected_fill_time"]).tz_convert("UTC") == pd.Timestamp(
            bt_order["scheduled_fill_time"]
        ).tz_convert("UTC")
    for env_event, bt_event in zip(env_opens + env_closes, bt_opens + bt_closes, strict=True):
        assert pd.Timestamp(env_event["time"]).tz_convert("UTC") == pd.Timestamp(
            bt_event["time"]
        ).tz_convert("UTC")
        assert float(env_event["price"]) == pytest.approx(float(bt_event["price"]))
    assert pd.Timestamp(env_closes[0]["decision_bar_time"]) == index[7]
    assert pd.Timestamp(bt_closes[0]["time"]) == index[8]
    env_pending_rejects = [
        info for info in env_infos if info.get("entry_rejection_reason") == "entry_pending"
    ]
    bt_pending_rejects = [
        event
        for event in result["trades"].to_dict("records")
        if event.get("reason") == "entry_pending"
    ]
    assert len(env_pending_rejects) == len(bt_pending_rejects) == 1
    assert env.account.balance == pytest.approx(result["account"].balance)
    assert action_index == len(actions) - 1  # the final bar has no next fill bar


def test_environment_and_backtest_both_fail_closed_on_quote_wait_gap() -> None:
    """A late first quote cannot become a candle-priced entry in either engine."""
    index = pd.date_range("2025-01-06T14:30:00Z", periods=6, freq="1min")
    prices = np.full(len(index), 100.0)
    bars = pd.DataFrame(
        {
            "open": prices,
            "high": prices + 1.0,
            "low": prices - 1.0,
            "close": prices,
            "spread": 0.0,
            "session_id": 1,
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
    # The first executable quote is 2 ms after the scheduled fill, beyond the
    # shared 1 ms wait bound. No bar fallback is permitted on this path.
    late_quote_time = index[2] + pd.Timedelta(milliseconds=2)
    tickbook = TickBook(
        np.asarray([late_quote_time.value], dtype=np.int64),
        np.asarray([100.0]),
        np.asarray([100.2]),
    )
    cost_model = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0)
    env = TradingEnv(
        bars,
        features,
        obs_window=1,
        initial_balance=50_000.0,
        cost_model=cost_model,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        block_overnight=False,
        tickbook=tickbook,
        tick_execution_required=True,
        max_tick_quote_wait_ms=1,
    )
    env.reset(seed=7)
    with pytest.raises(TickExecutionUnavailable, match="no executable quote within 1ms"):
        env.step(1)

    actions = iter([1, 0, 0, 0, 0])
    with pytest.raises(TickExecutionUnavailable, match="no executable tick within 1ms"):
        run_backtest(
            bars,
            features,
            lambda _observation: next(actions),
            obs_window=1,
            cost_model=cost_model,
            initial_balance=50_000.0,
            risk_frac=0.001,
            rr_ratio=1.0,
            use_structure_sl_tp=True,
            swing_buffer_pts=0.0,
            min_lot=0.01,
            max_lot=1.0,
            contract_size=1.0,
            max_loss_per_trade_usd=100.0,
            hold_on_zero=True,
            block_overnight=False,
            fill_latency_bars=1,
            tickbook=tickbook,
            tick_execution_required=True,
            max_tick_quote_wait_ms=1,
        )


def test_environment_and_backtest_use_first_source_order_for_tied_stop_target_ticks() -> None:
    """Equal millisecond timestamps use the same stable first-row trigger in both engines."""
    index = pd.date_range("2025-01-06T14:30:00Z", periods=6, freq="1min")
    prices = np.full(len(index), 100.0)
    bars = pd.DataFrame(
        {
            "open": prices,
            "high": prices + 0.5,
            "low": prices - 0.5,
            "close": prices,
            "spread": 0.0,
            "session_id": 1,
            "session": "ny",
        },
        index=index,
    )
    bars.loc[index[3], "high"] = 111.0
    bars.loc[index[3], "low"] = 89.0
    features = pd.DataFrame(
        {
            "last_swing_low": np.full(len(index), 99.0),
            "last_swing_high": np.full(len(index), 101.0),
        },
        index=index,
    )
    entry_time = index[2] + pd.Timedelta(milliseconds=100)
    tied_trigger_time = index[3] + pd.Timedelta(milliseconds=200)
    tickbook = TickBook(
        np.asarray([entry_time.value, tied_trigger_time.value, tied_trigger_time.value]),
        np.asarray([100.0, 95.0, 110.0]),
        np.asarray([100.2, 95.2, 110.2]),
    )
    cost_model = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0)
    env = TradingEnv(
        bars,
        features,
        obs_window=1,
        initial_balance=50_000.0,
        cost_model=cost_model,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        block_overnight=False,
        tickbook=tickbook,
        tick_execution_required=True,
    )
    env.reset(seed=7)
    env.step(1)
    env.step(0)
    env.step(0)

    actions = iter([1, 0, 0, 0, 0])
    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions),
        obs_window=1,
        cost_model=cost_model,
        initial_balance=50_000.0,
        max_loss_per_trade_usd=100.0,
        tickbook=tickbook,
        tick_execution_required=True,
        block_overnight=False,
        hold_on_zero=True,
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        risk_frac=0.001,
        rr_ratio=1.0,
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
    )

    env_stop = next(event for event in env.trade_log if event["type"] == "stop_close")
    backtest_stop = result["trades"].loc[result["trades"]["type"] == "stop_close"].iloc[0]
    assert env_stop["reason"] == backtest_stop["reason"] == "structure_sl"
    assert env_stop["price"] == pytest.approx(backtest_stop["price"])
    assert env_stop["price"] == pytest.approx(95.0)
    assert pd.Timestamp(env_stop["fill_time"]).tz_convert("UTC") == tied_trigger_time
    assert pd.Timestamp(backtest_stop["fill_time"]).tz_convert("UTC") == tied_trigger_time
    assert env.account.balance == pytest.approx(result["account"].balance)


@pytest.mark.parametrize(("block_overnight", "expected_opens"), [(False, 1), (True, 0)])
def test_environment_and_backtest_match_delayed_entry_session_boundary(
    block_overnight: bool,
    expected_opens: int,
) -> None:
    """A delayed entry crosses a supplied session only when overnight is allowed."""
    index = pd.date_range("2025-01-06 14:30:00Z", periods=8, freq="1min")
    prices = np.full(len(index), 100.0)
    bars = pd.DataFrame(
        {
            "open": prices,
            "high": prices + 1.0,
            "low": prices - 1.0,
            "close": prices,
            "spread": 0.0,
            "session_id": [0, 0, 0, 0, 1, 1, 1, 1],
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
    tickbook = TickBook(
        np.asarray([index[4].value, index[6].value], dtype=np.int64),
        np.asarray([100.0, 99.5]),
        np.asarray([100.2, 99.7]),
    )
    cost_model = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0)
    env = TradingEnv(
        bars,
        features,
        obs_window=1,
        initial_balance=50_000.0,
        cost_model=cost_model,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        block_overnight=block_overnight,
        fill_latency_bars=2,
        reward_mode="pnl",
        tickbook=tickbook,
        tick_execution_required=True,
    )
    env.reset(seed=7)
    actions = [1, 0, 0, 0, 19, 0]
    for action in actions:
        env.step(action)
    backtest_actions = iter(actions)

    def policy(_observation: np.ndarray[Any, Any]) -> int:
        return next(backtest_actions, 0)

    result = run_backtest(
        bars,
        features,
        policy,
        obs_window=1,
        cost_model=cost_model,
        initial_balance=50_000.0,
        risk_frac=0.001,
        rr_ratio=1.0,
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        block_overnight=block_overnight,
        exit_action=19,
        fill_latency_bars=2,
        tickbook=tickbook,
        tick_execution_required=True,
    )

    env_opens = [event for event in env.trade_log if event["type"] == "open"]
    bt_opens = [event for event in result["trades"].to_dict("records") if event["type"] == "open"]
    assert len(env_opens) == len(bt_opens) == expected_opens
    assert env.account.balance == pytest.approx(result["account"].balance)


@pytest.mark.parametrize(
    ("env_action", "direction", "risk_limit", "expected_lots"),
    [
        (1, 1, 5.0, 0.5),
        (10, -1, 5.0, 0.5),
        (1, 1, 0.05, None),
        (10, -1, 0.05, None),
    ],
)
def test_environment_and_backtest_size_to_the_same_trade_risk_cap(
    env_action: int,
    direction: int,
    risk_limit: float,
    expected_lots: float | None,
) -> None:
    """Both engines size to the hard cap and reject below-minimum risk sizes."""
    index = pd.date_range("2025-01-06 14:30:00Z", periods=7, freq="1min")
    prices = np.full(len(index), 100.0)
    bars = pd.DataFrame(
        {
            "open": prices,
            "high": prices + 0.1,
            "low": prices - 0.1,
            "close": prices,
            "spread": 0.0,
            "session_id": 1,
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
    guardrails = {
        "limit_value_mode": "fixed_usd",
        "daily_loss_limit_pct": 0.10,
        "max_loss_limit_initial_pct": 0.20,
        "risk_per_trade_limit": risk_limit,
        "soft_daily_loss_limit_pct": 0.0,
        "soft_max_loss_limit_initial_pct": 0.0,
    }
    cost_model = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0)
    env = TradingEnv(
        bars,
        features,
        obs_window=1,
        initial_balance=50_000.0,
        cost_model=cost_model,
        guardrail_kwargs=guardrails,
        risk_frac_range=(0.01, 0.01),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        block_overnight=False,
    )
    env.reset(seed=7)
    env.step(env_action)

    actions = iter((direction, 0, 0, 0, 0, 0))

    def policy(_observation: np.ndarray[Any, Any]) -> int:
        return next(actions, 0)

    result = run_backtest(
        bars,
        features,
        policy,
        obs_window=1,
        cost_model=cost_model,
        initial_balance=50_000.0,
        guardrail_kwargs=guardrails,
        risk_frac=0.01,
        rr_ratio=1.0,
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        block_overnight=False,
    )

    env_opens = [event for event in env.trade_log if event["type"] == "open"]
    bt_opens = [event for event in result["trades"].to_dict("records") if event["type"] == "open"]
    if expected_lots is None:
        assert not env_opens
        assert not bt_opens
    else:
        assert len(env_opens) == len(bt_opens) == 1
        assert env_opens[0]["lots"] == pytest.approx(expected_lots)
        assert bt_opens[0]["lots"] == pytest.approx(expected_lots)
        assert env_opens[0]["modeled_stop_risk_usd"] == pytest.approx(risk_limit)
        assert abs(bt_opens[0]["price"] - bt_opens[0]["sl_price"]) * bt_opens[0][
            "lots"
        ] == pytest.approx(risk_limit)


@pytest.mark.parametrize(("env_action", "direction"), [(1, 1), (10, -1)])
def test_environment_and_backtest_reject_insufficient_margin_without_account_mutation(
    env_action: int,
    direction: int,
) -> None:
    """Reject an unaffordable entry consistently in both simulation engines."""
    index = pd.date_range("2025-01-06 14:30:00Z", periods=7, freq="1min")
    prices = np.full(len(index), 100.0)
    bars = pd.DataFrame(
        {
            "open": prices,
            "high": prices + 0.1,
            "low": prices - 0.1,
            "close": prices,
            "spread": 0.0,
            "session_id": 1,
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
    initial_balance = 50_000.0
    cost_model = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0)
    broker_kwargs = {"margin_pct": 1_000.0}
    env = TradingEnv(
        bars,
        features,
        obs_window=1,
        initial_balance=initial_balance,
        cost_model=cost_model,
        broker_kwargs=broker_kwargs,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        block_overnight=False,
    )
    env.reset(seed=7)
    env.step(env_action)

    actions = iter((direction, 0, 0, 0, 0, 0))

    def policy(_observation: np.ndarray[Any, Any]) -> int:
        return next(actions, 0)

    result = run_backtest(
        bars,
        features,
        policy,
        obs_window=1,
        cost_model=cost_model,
        initial_balance=initial_balance,
        broker_kwargs=broker_kwargs,
        risk_frac=0.001,
        rr_ratio=1.0,
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        block_overnight=False,
    )

    env_opens = [event for event in env.trade_log if event["type"] == "open"]
    assert not env_opens
    backtest_events = result["trades"].to_dict("records")
    submit = next(event for event in backtest_events if event["type"] == "order_submit")
    rejection = next(event for event in backtest_events if event["type"] == "reject")
    assert submit["order_type"] == "market"
    assert submit["decision_id"] == rejection["decision_id"]
    assert submit["order_id"] == rejection["order_id"]
    assert rejection["reason"] == "insufficient_margin"
    assert not any(event["type"] in {"open", "close", "order_fill"} for event in backtest_events)
    assert not env.sessions_with_trades
    assert result["n_sessions_with_trades"] == 0
    for account in (env.account, result["account"]):
        assert account.balance == pytest.approx(initial_balance)
        assert account.equity == pytest.approx(initial_balance)
        assert account.open_pnl == pytest.approx(0.0)
        assert account.daily_loss == pytest.approx(0.0)
