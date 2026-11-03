"""Source-characterization tests for current risk-event ordering boundaries."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import numpy as np
import pandas as pd
import pytest

from market_data.loading.ticks import TickBook
from simulation.backtest import run_backtest
from simulation.environment.env import TradingEnv
from trading.execution import CostModel
from trading.strategies.feature_row_contract import FeatureRow
from trading.strategies.strategy_contract import TradingStrategy


class _AlwaysLongStructuralStrategy(TradingStrategy):
    name = "always_long_structural_test"
    required_features: tuple[str, ...] = ()
    raw_columns: tuple[str, ...] = ()

    def validate_entry(self, *, direction: int, row: pd.Series) -> bool:
        return direction == 1

    def sl_reference(self, *, direction: int, row: FeatureRow | pd.Series) -> float | None:
        return float(row["last_swing_low"]) if direction == 1 else None

    def target_candidates(self, *, direction: int, row: pd.Series) -> dict[str, float]:
        return {"far_target": float(row["last_swing_high"])} if direction == 1 else {}

    def context_direction(self, row: pd.Series) -> int:
        return 1


class _AlwaysShortStructuralStrategy(TradingStrategy):
    name = "always_short_structural_test"
    required_features: tuple[str, ...] = ()
    raw_columns: tuple[str, ...] = ()

    def validate_entry(self, *, direction: int, row: pd.Series) -> bool:
        return direction == -1

    def sl_reference(self, *, direction: int, row: FeatureRow | pd.Series) -> float | None:
        return float(row["last_swing_high"]) if direction == -1 else None

    def target_candidates(self, *, direction: int, row: pd.Series) -> dict[str, float]:
        return {"far_target": float(row["last_swing_low"])} if direction == -1 else {}

    def context_direction(self, row: pd.Series) -> int:
        return -1


def _bars(
    close: tuple[float, ...],
    high: tuple[float, ...],
    low: tuple[float, ...],
    session_ids: tuple[int, ...] | None = None,
) -> pd.DataFrame:
    """Build an M1 trace with explicit OHLC and session IDs."""
    index = pd.date_range("2025-01-06 16:30", periods=len(close), freq="1min", tz="Etc/GMT-3")
    close_values = np.asarray(close, dtype=float)
    return pd.DataFrame(
        {
            "open": np.full(len(close), 100.0),
            "high": np.asarray(high, dtype=float),
            "low": np.asarray(low, dtype=float),
            "close": close_values,
            "spread": 0.0,
            "session_id": session_ids or (0,) * len(close),
            "session": "ny",
        },
        index=index,
    )


def _features(index: pd.Index, *, stop: float, target: float) -> pd.DataFrame:
    """Build structural stop/target references for the controlled trace."""
    return pd.DataFrame(
        {
            "last_swing_low": np.full(len(index), stop),
            "last_swing_high": np.full(len(index), target),
        },
        index=index,
    )


def _guardrails(
    max_loss_limit: float,
    *,
    daily_loss_limit: float = 50_000.0,
    trailing_dd_limit: float = 0.0,
) -> dict[str, float]:
    """Keep guardrails inactive except for the explicitly chosen thresholds."""
    return {
        "daily_loss_limit": daily_loss_limit,
        "max_loss_limit": max_loss_limit,
        "risk_per_trade_limit": 10_000.0,
        "soft_daily_loss_limit": 0.0,
        "soft_max_loss_limit": 0.0,
        "trailing_dd_limit": trailing_dd_limit,
    }


def _cost_model() -> CostModel:
    return CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0)


@pytest.mark.parametrize(
    (
        "protective_event",
        "close",
        "high",
        "low",
        "max_loss_limit",
        "expected_exit_type",
        "expected_env_reason",
        "expected_reason",
        "expected_pnl",
    ),
    [
        pytest.param(
            "stop",
            (100.0, 100.0, 100.0, 99.0, 99.0, 99.0),
            (100.1, 100.1, 100.1, 100.1, 99.1, 99.1),
            (99.9, 99.9, 99.9, 98.0, 98.9, 98.9),
            0.75,
            "stop_close",
            "structure_sl",
            "structure_sl",
            -0.5,
            id="same-bar-stop-and-max-loss",
        ),
        pytest.param(
            "target",
            (100.0, 100.0, 100.0, 99.9, 99.9, 99.9),
            (100.1, 100.1, 100.1, 101.0, 100.1, 100.1),
            (99.9, 99.9, 99.9, 99.8, 99.8, 99.8),
            0.05,
            "tp_close",
            "structure_tp3",
            "structure_tp",
            0.5,
            id="same-bar-target-and-marked-loss",
        ),
    ],
)
def test_environment_and_backtest_apply_same_bar_protection_before_account_guardrails(
    protective_event: str,
    close: tuple[float, ...],
    high: tuple[float, ...],
    low: tuple[float, ...],
    max_loss_limit: float,
    expected_exit_type: str,
    expected_env_reason: str,
    expected_reason: str,
    expected_pnl: float,
) -> None:
    """Reconcile protective-exit precedence without claiming OHLC chronology.

    Both engines process a touched SL/TP before account-level guardrails. A
    bar can show that both levels were reached, but does not reveal their
    within-bar order; this deterministic policy is not tick chronology.
    """
    bars = _bars(close, high, low)
    features = _features(bars.index, stop=99.5, target=100.5)
    cost_model = _cost_model()
    guardrails = _guardrails(max_loss_limit)
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        initial_balance=100_000.0,
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
    for action in (1, 0, 0):
        env.step(action)

    actions: Iterator[int] = iter((1, 0, 0))
    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions, 0),
        obs_window=1,
        cost_model=cost_model,
        initial_balance=100_000.0,
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
    )

    env_exits = [
        event
        for event in env.trade_log
        if event["type"] in {"forced_close", "stop_close", "tp_close"}
    ]
    assert len(env_exits) == 1
    assert env_exits[0]["type"] == expected_exit_type
    assert env_exits[0]["reason"] == expected_env_reason
    assert env_exits[0]["pnl"] == pytest.approx(expected_pnl)
    assert env.breach_events == []

    backtest_exits = result["trades"].loc[
        result["trades"]["type"].isin(["forced_close", "stop_close", "tp_close"])
    ]
    assert len(backtest_exits) == 1
    assert backtest_exits.iloc[0]["type"] == expected_exit_type
    assert backtest_exits.iloc[0]["reason"] == expected_reason
    assert backtest_exits.iloc[0]["pnl"] == pytest.approx(expected_pnl)
    assert result["breach_events"] == []


def test_environment_and_backtest_share_planned_risk_aware_adverse_close() -> None:
    close = (100.0, 100.0, 100.0, 100.0, 100.0)
    high = (100.1, 100.1, 100.1, 100.1, 100.1)
    low = (99.9, 99.9, 99.9, 95.9, 99.9)
    bars = _bars(close, high, low)
    features = _features(bars.index, stop=90.0, target=120.0)
    eod_risk = {
        "max_loss_usd": 3.0,
        "respect_planned_risk": False,
        "planned_risk_mult": 1.1,
    }
    guardrails = _guardrails(50_000.0)
    cost_model = _cost_model()

    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        initial_balance=50_000.0,
        cost_model=cost_model,
        guardrail_kwargs=guardrails,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        eod_risk=eod_risk,
        block_overnight=False,
    )
    env.reset(seed=7)
    for action in (1, 0, 0, 0):
        env.step(action)

    actions: Iterator[int] = iter((1, 0, 0, 0))
    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions, 0),
        obs_window=1,
        cost_model=cost_model,
        initial_balance=50_000.0,
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
        eod_risk=eod_risk,
    )

    env_guard = next(event for event in env.trade_log if event["type"] == "eod_close")
    backtest_guard = result["trades"].loc[result["trades"]["type"] == "eod_close"]
    assert env_guard["reason"] == "eod_max_loss"
    assert len(backtest_guard) == 1
    assert backtest_guard.iloc[0].get("reason") == "eod_max_loss", backtest_guard.iloc[0].to_dict()
    assert float(env_guard["pnl"]) == pytest.approx(float(backtest_guard.iloc[0]["pnl"]))
    assert env.account.equity == pytest.approx(result["account"].equity)


def test_environment_and_backtest_apply_breakeven_stop_on_following_bar() -> None:
    bars = _bars(
        close=(100.0, 100.0, 100.0, 100.5, 100.05, 100.05),
        high=(100.1, 100.1, 100.1, 100.6, 100.2, 100.1),
        low=(99.9, 99.9, 99.9, 99.9, 100.0, 100.0),
    )
    features = _features(bars.index, stop=99.5, target=110.0)
    eod_risk = {
        "max_loss_usd": 1_000.0,
        "respect_planned_risk": True,
        "planned_risk_mult": 1.1,
        "breakeven_trigger_r": 1.0,
        "breakeven_buffer_pts": 0.1,
    }
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        initial_balance=100_000.0,
        cost_model=_cost_model(),
        guardrail_kwargs=_guardrails(50_000.0),
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(10.0, 10.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=1_000.0,
        strategy_actions=True,
        strategy=_AlwaysLongStructuralStrategy(),
        entry_intensity_threshold=0.6,
        open_manipulation_bars=0,
        allow_ema_exit=False,
        allow_agent_sl_mode=True,
        eod_risk=eod_risk,
        block_overnight=False,
    )
    env.reset(seed=7)
    enter_with_breakeven = np.asarray([0.9, 0.0, 0.0, 0.0, -0.3, -1.0], dtype=np.float32)
    hold_with_breakeven = np.asarray([0.0, 0.0, 0.0, 0.0, -0.3, -1.0], dtype=np.float32)
    for action in (
        enter_with_breakeven,
        hold_with_breakeven,
        hold_with_breakeven,
        hold_with_breakeven,
    ):
        env.step(action)

    actions: Iterator[int] = iter((1, 0, 0, 0))
    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions, 0),
        obs_window=1,
        cost_model=_cost_model(),
        initial_balance=100_000.0,
        guardrail_kwargs=_guardrails(50_000.0),
        risk_frac=0.001,
        rr_ratio=10.0,
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=1_000.0,
        eod_risk=eod_risk,
        sl_mode="breakeven",
        hold_on_zero=True,
        block_overnight=False,
    )

    env_update = next(
        event
        for event in env.trade_log
        if event.get("type") == "sl_update" and event.get("reason") == "breakeven_trigger"
    )
    backtest_update = next(
        event
        for event in result["trades"].to_dict("records")
        if event.get("type") == "sl_update" and event.get("reason") == "breakeven_trigger"
    )
    env_exit = next(event for event in env.trade_log if event.get("type") == "stop_close")
    backtest_exit = result["trades"].loc[result["trades"]["type"] == "stop_close"].iloc[0]

    assert env_update["price"] == pytest.approx(100.1)
    assert env_update["effective_time"] == backtest_update["effective_time"]
    assert backtest_update["price"] == pytest.approx(env_update["price"])
    assert env_update["buffer_points"] == pytest.approx(backtest_update["buffer_points"])
    assert env_exit["reason"] == backtest_exit["reason"] == "structure_sl"
    assert env_exit["pnl"] == pytest.approx(float(backtest_exit["pnl"])), (
        env.trade_log,
        result["trades"].to_dict(orient="records"),
    )
    assert env.account.equity == pytest.approx(result["account"].equity)


@pytest.mark.parametrize("direction", [1, -1])
def test_environment_and_backtest_apply_confirmed_swing_trailing_stop_next_bar(
    direction: int,
) -> None:
    if direction == 1:
        bars = _bars(
            close=(100.0, 100.0, 100.0, 100.5, 100.1, 100.1),
            high=(100.1, 100.1, 100.1, 100.6, 100.2, 100.2),
            low=(99.9, 99.9, 99.9, 100.3, 100.0, 100.0),
        )
        features = _features(bars.index, stop=99.5, target=110.0)
        features["last_swing_low"] = (99.5, 99.5, 99.5, 100.3, 100.3, 100.3)
        strategy: TradingStrategy = _AlwaysLongStructuralStrategy()
        expected_reference = "last_swing_low"
        expected_stop = 100.2
    else:
        bars = _bars(
            close=(100.0, 100.0, 100.0, 99.5, 99.9, 99.9),
            high=(100.1, 100.1, 100.1, 99.7, 100.0, 100.0),
            low=(99.9, 99.9, 99.9, 99.4, 99.8, 99.8),
        )
        features = _features(bars.index, stop=90.0, target=100.5)
        features["last_swing_high"] = (100.5, 100.5, 100.5, 99.7, 99.7, 99.7)
        strategy = _AlwaysShortStructuralStrategy()
        expected_reference = "last_swing_high"
        expected_stop = 99.8
    gap_index = bars.index.to_list()
    gap_index[4] = gap_index[3] + pd.Timedelta(minutes=10)
    gap_index[5] = gap_index[4] + pd.Timedelta(minutes=1)
    bars.index = pd.DatetimeIndex(gap_index)
    features.index = bars.index
    eod_risk = {
        "max_loss_usd": 1_000.0,
        "respect_planned_risk": True,
        "planned_risk_mult": 1.1,
        "breakeven_trigger_r": 0.0,
        "breakeven_buffer_pts": 0.1,
    }
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        initial_balance=100_000.0,
        cost_model=_cost_model(),
        guardrail_kwargs=_guardrails(50_000.0),
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(10.0, 10.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=1_000.0,
        strategy_actions=True,
        strategy=strategy,
        entry_intensity_threshold=0.6,
        open_manipulation_bars=0,
        allow_ema_exit=False,
        allow_agent_sl_mode=True,
        sl_buffer_pts=0.1,
        eod_risk=eod_risk,
        block_overnight=False,
    )
    env.reset(seed=7)
    enter_trailing = np.asarray([0.9, 0.0, 0.0, 0.0, 1.0, -1.0], dtype=np.float32)
    hold_trailing = np.asarray([0.0, 0.0, 0.0, 0.0, 1.0, -1.0], dtype=np.float32)
    for action in (enter_trailing, hold_trailing, hold_trailing, hold_trailing):
        env.step(action)

    actions: Iterator[int] = iter((direction, 0, 0, 0))
    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions, 0),
        obs_window=1,
        cost_model=_cost_model(),
        initial_balance=100_000.0,
        guardrail_kwargs=_guardrails(50_000.0),
        risk_frac=0.001,
        rr_ratio=10.0,
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        sl_buffer_pts=0.1,
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=1_000.0,
        eod_risk=eod_risk,
        sl_mode="trailing",
        hold_on_zero=True,
        block_overnight=False,
    )

    env_update = next(
        event
        for event in env.trade_log
        if event.get("type") == "sl_update" and event.get("reason") == "confirmed_swing"
    )
    backtest_update = next(
        event
        for event in result["trades"].to_dict("records")
        if event.get("type") == "sl_update" and event.get("reason") == "confirmed_swing"
    )
    env_exit = next(event for event in env.trade_log if event.get("type") == "stop_close")
    backtest_exit = result["trades"].loc[result["trades"]["type"] == "stop_close"].iloc[0]

    assert env_update["reference"] == backtest_update["reference"] == expected_reference
    assert env_update["price"] == pytest.approx(expected_stop)
    assert backtest_update["price"] == pytest.approx(env_update["price"])
    assert env_update["effective_time"] == backtest_update["effective_time"]
    assert env_update["buffer_points"] == pytest.approx(backtest_update["buffer_points"])
    assert env_exit["reason"] == backtest_exit["reason"] == "structure_sl"
    assert env_exit["pnl"] == pytest.approx(float(backtest_exit["pnl"]))
    assert env.account.equity == pytest.approx(result["account"].equity)


def test_breakeven_update_precedes_same_bar_eod_adverse_cutoff_in_both_engines() -> None:
    bars = _bars(
        close=(100.0, 100.0, 100.0, 100.1, 100.1),
        high=(100.1, 100.1, 100.1, 100.6, 100.1),
        low=(99.9, 99.9, 99.9, 99.6, 100.0),
    )
    features = _features(bars.index, stop=99.5, target=110.0)
    eod_risk = {
        "max_loss_usd": 0.1,
        "respect_planned_risk": False,
        "planned_risk_mult": 1.1,
        "breakeven_trigger_r": 1.0,
        "breakeven_buffer_pts": 0.1,
    }
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        initial_balance=100_000.0,
        cost_model=_cost_model(),
        guardrail_kwargs=_guardrails(50_000.0),
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(10.0, 10.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=1_000.0,
        strategy_actions=True,
        strategy=_AlwaysLongStructuralStrategy(),
        entry_intensity_threshold=0.6,
        open_manipulation_bars=0,
        allow_ema_exit=False,
        allow_agent_sl_mode=True,
        eod_risk=eod_risk,
        block_overnight=False,
    )
    env.reset(seed=7)
    enter = np.asarray([0.9, 0.0, 0.0, 0.0, -0.3, -1.0], dtype=np.float32)
    hold = np.asarray([0.0, 0.0, 0.0, 0.0, -0.3, -1.0], dtype=np.float32)
    for action in (enter, hold, hold):
        env.step(action)

    actions: Iterator[int] = iter((1, 0, 0))
    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions, 0),
        obs_window=1,
        cost_model=_cost_model(),
        initial_balance=100_000.0,
        guardrail_kwargs=_guardrails(50_000.0),
        risk_frac=0.001,
        rr_ratio=10.0,
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=1_000.0,
        eod_risk=eod_risk,
        sl_mode="breakeven",
        hold_on_zero=True,
        block_overnight=False,
    )

    env_update_index = next(
        i
        for i, event in enumerate(env.trade_log)
        if event.get("type") == "sl_update" and event.get("reason") == "breakeven_trigger"
    )
    env_cutoff_index = next(
        i for i, event in enumerate(env.trade_log) if event.get("reason") == "eod_max_loss"
    )
    backtest_events = result["trades"].to_dict("records")
    backtest_update_index = next(
        i
        for i, event in enumerate(backtest_events)
        if event.get("type") == "sl_update" and event.get("reason") == "breakeven_trigger"
    )
    backtest_cutoff_index = next(
        i for i, event in enumerate(backtest_events) if event.get("reason") == "eod_max_loss"
    )

    assert env_update_index < env_cutoff_index
    assert backtest_update_index < backtest_cutoff_index
    assert env.trade_log[env_update_index]["price"] == pytest.approx(100.1)
    assert backtest_events[backtest_update_index]["price"] == pytest.approx(100.1)
    env_cutoff = env.trade_log[env_cutoff_index]
    backtest_cutoff = backtest_events[backtest_cutoff_index]
    assert env_cutoff["pnl"] == pytest.approx(backtest_cutoff["pnl"])
    assert env.account.equity == pytest.approx(result["account"].equity)


def test_environment_and_backtest_share_max_age_close() -> None:
    bars = _bars(
        close=(100.0, 100.0, 100.0, 100.1, 100.2, 100.3),
        high=(100.1, 100.1, 100.1, 100.2, 100.3, 100.4),
        low=(99.9, 99.9, 99.9, 100.0, 100.1, 100.2),
    )
    features = _features(bars.index, stop=90.0, target=120.0)
    tickbook = TickBook(
        pd.DatetimeIndex(bars.index).to_numpy(dtype=np.int64),
        bars["close"].to_numpy(dtype=float),
        bars["close"].to_numpy(dtype=float),
    )
    eod_risk = {
        "max_loss_usd": 1e9,
        "respect_planned_risk": False,
        "max_age_hours": 0.01,
        "stale_bars": 10_000,
        "breakeven_trigger_r": 0.0,
    }
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        initial_balance=50_000.0,
        cost_model=_cost_model(),
        tickbook=tickbook,
        tick_execution_required=True,
        guardrail_kwargs=_guardrails(50_000.0),
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=1_000.0,
        eod_risk=eod_risk,
        block_overnight=False,
    )
    env.reset(seed=7)
    for action in (1, 0, 0, 0):
        env.step(action)

    actions: Iterator[int] = iter((1, 0, 0, 0))
    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions, 0),
        obs_window=1,
        cost_model=_cost_model(),
        tickbook=tickbook,
        tick_execution_required=True,
        initial_balance=50_000.0,
        guardrail_kwargs=_guardrails(50_000.0),
        risk_frac=0.001,
        rr_ratio=1.0,
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=1_000.0,
        eod_risk=eod_risk,
        hold_on_zero=True,
        block_overnight=False,
    )

    env_exit = next(event for event in env.trade_log if event.get("reason") == "max_age")
    backtest_exit = result["trades"].loc[result["trades"]["reason"] == "max_age"].iloc[0]
    assert env_exit["type"] == backtest_exit["type"] == "eod_close"
    assert env_exit["reason"] == backtest_exit["reason"] == "max_age"
    assert pd.Timestamp(env_exit["fill_time"]) == pd.Timestamp(backtest_exit["fill_time"])
    assert env_exit["pnl"] == pytest.approx(float(backtest_exit["pnl"]))
    assert env.account.equity == pytest.approx(result["account"].equity)


def test_environment_and_backtest_share_stale_close_at_session_gap() -> None:
    bars = _bars(
        close=(100.0, 100.0, 100.0, 100.0, 100.0, 100.0),
        high=(100.1, 100.1, 100.1, 100.1, 100.1, 100.1),
        low=(99.9, 99.9, 99.9, 99.9, 99.9, 99.9),
    )
    bars["session"] = ("ny", "ny", "ny", "asia", "asia", "ny")
    features = _features(bars.index, stop=90.0, target=120.0)
    tickbook = TickBook(
        pd.DatetimeIndex(bars.index).to_numpy(dtype=np.int64),
        bars["close"].to_numpy(dtype=float),
        bars["close"].to_numpy(dtype=float),
    )
    eod_risk = {
        "max_loss_usd": 1e9,
        "respect_planned_risk": False,
        "max_age_hours": 8.0,
        "stale_bars": 2,
        "progress_threshold_atr": 1000.0,
        "breakeven_trigger_r": 0.0,
    }
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        initial_balance=50_000.0,
        cost_model=_cost_model(),
        tickbook=tickbook,
        tick_execution_required=True,
        guardrail_kwargs=_guardrails(50_000.0),
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=1_000.0,
        eod_risk=eod_risk,
        block_overnight=False,
    )
    env.reset(seed=7)
    for action in (1, 0):
        env.step(action)

    actions: Iterator[int] = iter((1, 0))
    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions, 0),
        obs_window=1,
        cost_model=_cost_model(),
        tickbook=tickbook,
        tick_execution_required=True,
        initial_balance=50_000.0,
        guardrail_kwargs=_guardrails(50_000.0),
        risk_frac=0.001,
        rr_ratio=1.0,
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=1_000.0,
        eod_risk=eod_risk,
        hold_on_zero=True,
        block_overnight=False,
    )

    env_exit = next(event for event in env.trade_log if event.get("reason") == "stale")
    backtest_exit = result["trades"].loc[result["trades"]["reason"] == "stale"].iloc[0]
    assert env_exit["type"] == backtest_exit["type"] == "eod_close"
    assert pd.Timestamp(env_exit["fill_time"]) == pd.Timestamp(backtest_exit["fill_time"])
    assert env_exit["pnl"] == pytest.approx(float(backtest_exit["pnl"]))
    assert env.account.equity == pytest.approx(result["account"].equity)


def test_environment_and_backtest_resolve_target_before_adverse_cutoff() -> None:
    """A touched target wins over the adverse excursion cutoff in both engines.

    OHLC does not expose within-bar ordering; this verifies the declared
    simulator event precedence, not a claim about intrabar chronology.
    """
    close = (100.0, 100.0, 100.0, 110.0, 110.0)
    high = (100.1, 100.1, 100.1, 111.0, 110.1)
    low = (99.9, 99.9, 99.9, 96.0, 100.4)
    bars = _bars(close, high, low)
    features = _features(bars.index, stop=90.0, target=110.0)
    cost_model = _cost_model()
    guardrails = _guardrails(50_000.0)
    eod_risk = {
        "max_loss_usd": 3.0,
        "respect_planned_risk": False,
        "planned_risk_mult": 1.1,
    }

    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        initial_balance=50_000.0,
        cost_model=cost_model,
        guardrail_kwargs=guardrails,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        eod_risk=eod_risk,
        block_overnight=False,
    )
    env.reset(seed=7)
    for action in (1, 0, 0):
        env.step(action)

    actions: Iterator[int] = iter((1, 0, 0))
    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions, 0),
        obs_window=1,
        cost_model=cost_model,
        initial_balance=50_000.0,
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
        eod_risk=eod_risk,
    )

    env_exit = next(event for event in env.trade_log if event["type"] == "tp_close")
    backtest_exit = result["trades"].loc[result["trades"]["type"] == "tp_close"]
    assert env_exit["reason"] == "structure_tp3"
    assert len(backtest_exit) == 1
    assert backtest_exit.iloc[0]["reason"] == "structure_tp"
    assert float(env_exit["pnl"]) == pytest.approx(float(backtest_exit.iloc[0]["pnl"]))
    assert env.breach_events == []
    assert result["breach_events"] == []
    assert not any(event.get("reason") == "eod_max_loss" for event in env.trade_log)
    assert not (result["trades"]["reason"] == "eod_max_loss").any()
    assert env.account.equity == pytest.approx(result["account"].equity)


@pytest.mark.parametrize(
    ("max_loss_limit", "trailing_dd_limit", "expected_reason"),
    [
        (1.0, 0.0, "max_drawdown"),
        (50_000.0, 0.00001, "trailing_dd"),
    ],
    ids=["max-loss", "trailing-drawdown"],
)
def test_recovered_annual_loss_breach_blocks_environment_and_backtest_for_rollout(
    max_loss_limit: float,
    trailing_dd_limit: float,
    expected_reason: str,
) -> None:
    """A recovered max-loss or trailing-DD breach remains latched across sessions."""
    close = (100.0, 100.0, 100.0, 100.0, 98.0, 100.0, 100.0)
    high = (100.1, 100.1, 100.1, 100.1, 98.1, 100.1, 100.1)
    low = (99.9, 99.9, 99.9, 99.9, 97.9, 99.9, 99.9)
    bars = _bars(close, high, low, session_ids=(0, 0, 0, 0, 0, 1, 1))
    features = _features(bars.index, stop=90.0, target=110.0)
    cost_model = _cost_model()
    guardrails = _guardrails(
        max_loss_limit=max_loss_limit,
        trailing_dd_limit=trailing_dd_limit,
    )

    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        initial_balance=100_000.0,
        cost_model=cost_model,
        guardrail_kwargs=guardrails,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        block_overnight=False,
        episodic=False,
    )
    env.reset(seed=7)
    for action in (1, 0, 0, 0, 1):
        env.step(action)

    actions: Iterator[int] = iter((1, 0, 0, 1))
    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions, 0),
        obs_window=1,
        cost_model=cost_model,
        initial_balance=100_000.0,
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
    )

    env_opens = [event for event in env.trade_log if event["type"] == "open"]
    backtest_opens = result["trades"].loc[result["trades"]["type"] == "open"]
    assert len(env.breach_events) == 1
    assert env.breach_events[0]["reason"] == expected_reason
    assert len(env_opens) == 1
    assert len(backtest_opens) == 1
    assert int(backtest_opens.iloc[0]["bar"]) == 1
    assert len(result["breach_events"]) == 1
    assert result["breach_events"][0]["reason"] == expected_reason
    backtest_breach = result["breach_events"][0]
    assert backtest_breach["time"] == bars.index[4]
    assert backtest_breach["session_id"] == 0
    assert backtest_breach["reason"] == expected_reason
    assert backtest_breach["equity"] == pytest.approx(99_998.0)


def test_daily_loss_breach_blocks_only_its_supplied_session() -> None:
    """A daily-loss breach blocks its supplied session, then permits the next one."""
    close = (100.0, 100.0, 100.0, 100.0, 98.0, 100.0, 100.0)
    high = (100.1, 100.1, 100.1, 100.1, 98.1, 100.1, 100.1)
    low = (99.9, 99.9, 99.9, 99.9, 97.9, 99.9, 99.9)
    bars = _bars(close, high, low, session_ids=(0, 0, 0, 0, 0, 1, 1))
    features = _features(bars.index, stop=99.0, target=110.0)
    actions: Iterator[int] = iter((1, 0, 0, 1))

    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions, 0),
        obs_window=1,
        cost_model=_cost_model(),
        initial_balance=100_000.0,
        guardrail_kwargs=_guardrails(max_loss_limit=50_000.0, daily_loss_limit=0.5),
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
    )

    assert len(result["breach_events"]) == 1
    assert result["breach_events"][0]["session_id"] == 0
    assert result["breach_events"][0]["reason"] == "daily_loss"
    opens = result["trades"].loc[result["trades"]["type"] == "open"]
    assert len(opens) == 2
    assert int(opens.iloc[-1]["bar"]) == 5


@pytest.mark.parametrize("randomized_fill_latency_ms", [0.0, 30.0])
def test_environment_and_backtest_share_tick_scheduled_session_close(
    randomized_fill_latency_ms: float,
) -> None:
    """Both engines submit the scheduled close during the final NY bar."""
    bars = _bars(
        close=(100.0,) * 8,
        high=(100.1,) * 8,
        low=(99.9,) * 8,
    )
    bars["session"] = ("ny", "ny", "ny", "ny", "ny", "ny", "asia", "asia")
    features = _features(bars.index, stop=90.0, target=120.0)
    minute_times = pd.DatetimeIndex([*bars.index, bars.index[-1] + pd.Timedelta(minutes=1)])
    minute_bids = (100.0, 100.0, 100.0, 100.0, 100.0, 101.0, 102.0, 103.0, 104.0)
    quote_rows = []
    for timestamp, bid in zip(minute_times, minute_bids, strict=True):
        quote_rows.append((timestamp, bid, bid + 0.2))
        if timestamp == bars.index[5]:
            quote_rows.extend(
                (timestamp + pd.Timedelta(milliseconds=offset), price, price + 0.2)
                for offset, price in (
                    (5, 101.1),
                    (10, 101.2),
                    (20, 101.3),
                    (25, 101.4),
                )
            )
    quote_rows.sort(key=lambda quote: quote[0])
    tick_times = pd.DatetimeIndex([quote[0] for quote in quote_rows])
    tickbook = TickBook(
        tick_times.to_numpy(dtype="datetime64[ns]").astype(np.int64),
        np.asarray([quote[1] for quote in quote_rows]),
        np.asarray([quote[2] for quote in quote_rows]),
    )
    eod_risk = {
        "max_loss_usd": 1e9,
        "respect_planned_risk": False,
        "max_age_hours": 1e9,
        "stale_bars": 1_000,
        "progress_threshold_atr": 1_000.0,
        "breakeven_trigger_r": 0.0,
    }
    common: dict[str, Any] = {
        "obs_window": 1,
        "initial_balance": 50_000.0,
        "cost_model": _cost_model(),
        "tickbook": tickbook,
        "tick_execution_required": True,
        "randomized_fill_latency_ms": randomized_fill_latency_ms,
        "guardrail_kwargs": _guardrails(50_000.0),
        "min_lot": 0.01,
        "max_lot": 1.0,
        "contract_size": 1.0,
        "max_loss_per_trade_usd": 1_000.0,
        "eod_risk": eod_risk,
        "block_overnight": True,
    }
    env = TradingEnv(
        bars=bars,
        features=features,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        **common,
    )
    env.reset(seed=11)
    for action in (1, 0, 0, 0, 0):
        env.step(action)

    actions: Iterator[int] = iter((1, 0, 0, 0, 0))
    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions, 0),
        execution_seed=11,
        risk_frac=0.001,
        rr_ratio=1.0,
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        hold_on_zero=True,
        **common,
    )

    env_open = next(event for event in env.trade_log if event["type"] == "open")
    backtest_open = result["trades"].loc[result["trades"]["type"] == "open"].iloc[0]
    env_close = next(event for event in env.trade_log if event.get("reason") == "session_end")
    backtest_close = result["trades"].loc[result["trades"]["reason"] == "session_end"].iloc[0]

    assert pd.Timestamp(env_open["fill_time"]) == pd.Timestamp(backtest_open["fill_time"])
    assert env_open["price"] == pytest.approx(float(backtest_open["price"]))
    assert pd.Timestamp(env_close["order_submission_time"]) == pd.Timestamp(
        backtest_close["order_submission_time"]
    )
    assert pd.Timestamp(env_close["time"]) == pd.Timestamp(backtest_close["time"])
    assert pd.Timestamp(env_close["fill_time"]) == pd.Timestamp(backtest_close["fill_time"])
    for close_event in (env_close, backtest_close):
        submitted = pd.Timestamp(close_event["order_submission_time"])
        arrival = pd.Timestamp(close_event["execution_arrival_time"])
        actual_tick = pd.Timestamp(close_event["actual_tick_time"])
        latency_ns = int(close_event["execution_latency_ns"])
        assert arrival - submitted == pd.Timedelta(latency_ns, unit="ns")
        assert 0 <= latency_ns < int(randomized_fill_latency_ms * 1_000_000) or (
            randomized_fill_latency_ms == 0.0 and latency_ns == 0
        )
        assert actual_tick >= arrival
        assert actual_tick <= submitted + pd.Timedelta(minutes=1)
    assert pd.Timestamp(env_close["actual_tick_time"]) == pd.Timestamp(
        backtest_close["actual_tick_time"]
    )
    assert pd.Timestamp(env_close["execution_arrival_time"]) == pd.Timestamp(
        backtest_close["execution_arrival_time"]
    )
    assert env_close["execution_latency_ns"] == backtest_close["execution_latency_ns"]
    assert env_close["price"] == pytest.approx(float(backtest_close["price"]))
    assert env_close["pnl"] == pytest.approx(float(backtest_close["pnl"]))
    assert env.account.equity == pytest.approx(result["account"].equity)


def test_randomized_execution_latency_is_independent_of_prior_no_action_steps() -> None:
    """Entry and protective latency are stable despite environment prefetches."""
    index = pd.date_range("2025-01-06 14:30:00Z", periods=8, freq="1min")
    prices = np.full(len(index), 100.0)
    bars = pd.DataFrame(
        {
            "open": prices,
            "high": prices + 1.0,
            "low": np.where(np.arange(len(index)) == 5, 89.0, prices - 1.0),
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
    quote_starts = index.append(pd.DatetimeIndex([index[-1] + pd.Timedelta(minutes=1)]))
    quote_times = pd.DatetimeIndex(
        [
            timestamp + pd.Timedelta(milliseconds=offset)
            for timestamp in quote_starts
            for offset in (0, 5, 10, 20, 25)
        ]
    )
    quote_bids = np.full(len(quote_times), 100.0)
    stop_trigger = quote_times == index[5]
    post_trigger_quotes = (quote_times > index[5]) & (
        quote_times <= index[5] + pd.Timedelta(milliseconds=25)
    )
    quote_bids[stop_trigger | post_trigger_quotes] = 89.0
    tickbook = TickBook(
        quote_times.to_numpy(dtype="datetime64[ns]").astype(np.int64),
        quote_bids,
        quote_bids + 0.2,
    )
    common: dict[str, Any] = {
        "obs_window": 1,
        "initial_balance": 50_000.0,
        "cost_model": _cost_model(),
        "tickbook": tickbook,
        "tick_execution_required": True,
        "randomized_fill_latency_ms": 30.0,
        "guardrail_kwargs": _guardrails(50_000.0),
        "min_lot": 0.01,
        "max_lot": 1.0,
        "contract_size": 1.0,
        "max_loss_per_trade_usd": 1_000.0,
        "block_overnight": False,
    }
    env = TradingEnv(
        bars,
        features,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        **common,
    )
    env.reset(seed=31)
    for action in (0, 0, 1, 0, 0):
        env.step(action)

    actions: Iterator[int] = iter((0, 0, 1, 0, 0))
    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions, 0),
        execution_seed=31,
        risk_frac=0.001,
        rr_ratio=1.0,
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        hold_on_zero=True,
        **common,
    )
    env_open = next(event for event in env.trade_log if event["type"] == "open")
    backtest_open = result["trades"].loc[result["trades"]["type"] == "open"].iloc[0]
    env_stop = next(event for event in env.trade_log if event.get("reason") == "structure_sl")
    backtest_stop = result["trades"].loc[result["trades"]["reason"] == "structure_sl"].iloc[0]

    assert env_open["execution_latency_ns"] == int(backtest_open["execution_latency_ns"])
    assert pd.Timestamp(env_open["execution_arrival_time"]) == pd.Timestamp(
        backtest_open["execution_arrival_time"]
    )
    assert pd.Timestamp(env_open["fill_time"]) == pd.Timestamp(backtest_open["fill_time"])
    assert pd.Timestamp(env_stop["order_submission_time"]) == pd.Timestamp(
        backtest_stop["order_submission_time"]
    )
    assert env_stop["execution_latency_ns"] == int(backtest_stop["execution_latency_ns"])
    assert pd.Timestamp(env_stop["execution_arrival_time"]) == pd.Timestamp(
        backtest_stop["execution_arrival_time"]
    )
    assert pd.Timestamp(env_stop["actual_tick_time"]) == pd.Timestamp(
        backtest_stop["actual_tick_time"]
    )
    assert env_stop["price"] == pytest.approx(float(backtest_stop["price"]))
    assert env_stop["pnl"] == pytest.approx(float(backtest_stop["pnl"]))
