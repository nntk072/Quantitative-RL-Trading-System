"""Observable contracts for protective exits in the event backtest."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from market_data.loading.ticks import TickBook, TickExecutionUnavailable
from simulation.backtest.protective_events import process_protective_and_account_events
from simulation.backtest.runtime import BacktestSettings, BacktestState
from trading import AccountState
from trading.execution import Broker, CostModel, Position
from trading.risk import FTMOGuardrails


def test_legacy_per_trade_loss_cap_closes_and_realizes_the_position_loss() -> None:
    time = pd.Timestamp("2026-02-02 14:31", tz="UTC")
    costs = CostModel(spread_points=0.0, point_size=0.01, point_value=1.0)
    settings = BacktestSettings(
        cost_model=costs,
        lots=1.0,
        max_loss_per_trade_usd=1.0,
        take_profit_per_trade_usd=None,
        tickbook=None,
        fill_delay_ms=0,
        randomized_fill_latency_ms=0.0,
        max_tick_quote_wait_ms=1_000,
        tick_execution_required=False,
        use_structure_sl_tp=False,
        risk_frac=0.01,
        policy_risk_frac_range=(0.01, 0.01),
        rr_ratio=2.0,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
        contract_size=1.0,
        hold_on_zero=False,
        exit_action=None,
        block_overnight=False,
        eod_risk=None,
    )
    position = Position(
        direction=1,
        size=1.0,
        entry_price=100.0,
        margin_used=0.0,
        position_id="legacy-loss-cap",
        sl_price=None,
        tp_price=None,
    )
    account = AccountState(initial_balance=10_000.0)
    account.update_equity(-2.0)
    state = BacktestState(account=account, position=position)

    def resolve_fill(
        *_args: object, **_kwargs: object
    ) -> tuple[tuple[float, float], pd.Timestamp, str, dict[str, Any]]:
        return (98.0, 98.0), time, "bar_open", {}

    stopped = process_protective_and_account_events(
        state,
        settings,
        Broker(cost_model=costs),
        FTMOGuardrails(),
        pd.DataFrame(index=[time, time + pd.Timedelta(minutes=1)]),
        pd.Series({"open": 100.0, "high": 100.1, "low": 99.9, "close": 100.0}),
        i=0,
        bar_time=time,
        bar_duration=pd.Timedelta(minutes=1),
        session=0,
        is_ny=False,
        bar_quote=(100.0, 100.0),
        entry_time=time - pd.Timedelta(minutes=1),
        position_active_in_bar=True,
        full_bar_available_after_entry=True,
        execution_rng=np.random.default_rng(0),
        resolve_bar_execution=resolve_fill,
        fill_quote_event=lambda *_args, **_kwargs: resolve_fill(),
        sl_tp_fill_quote=lambda *_args: (98.0, 98.0),
        bar_spread_price_units=lambda *_args: 0.0,
        is_last_ny_bar=lambda *_args: False,
        eod_guard_due=False,
    )

    assert stopped is False
    assert state.position is None
    close = next(event for event in state.trade_log if event["type"] == "stop_close")
    assert close["reason"] == "max_loss_cap"
    assert close["position_id"] == position.position_id
    assert close["pnl"] == pytest.approx(-2.0)
    assert state.account.balance == pytest.approx(9_998.0)
    assert state.breach_events == []


def test_eod_risk_loss_cap_closes_without_a_structural_stop() -> None:
    time = pd.Timestamp("2026-02-02 14:31", tz="UTC")
    costs = CostModel(spread_points=0.0, point_size=0.01, point_value=1.0)
    settings = BacktestSettings(
        cost_model=costs,
        lots=1.0,
        max_loss_per_trade_usd=None,
        take_profit_per_trade_usd=None,
        tickbook=None,
        fill_delay_ms=0,
        randomized_fill_latency_ms=0.0,
        max_tick_quote_wait_ms=1_000,
        tick_execution_required=False,
        use_structure_sl_tp=True,
        risk_frac=0.01,
        policy_risk_frac_range=(0.01, 0.01),
        rr_ratio=2.0,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
        contract_size=1.0,
        hold_on_zero=False,
        exit_action=None,
        block_overnight=False,
        eod_risk={"max_loss_usd": 0.5, "respect_planned_risk": False},
    )
    position = Position(
        direction=1,
        size=1.0,
        entry_price=100.0,
        margin_used=0.0,
        position_id="eod-risk-cap",
        sl_price=None,
        tp_price=None,
    )
    state = BacktestState(account=AccountState(initial_balance=10_000.0), position=position)

    def resolve_fill(
        *_args: object, **_kwargs: object
    ) -> tuple[tuple[float, float], pd.Timestamp, str, dict[str, Any]]:
        return (99.0, 99.0), time, "bar_open", {}

    stop = process_protective_and_account_events(
        state,
        settings,
        Broker(cost_model=costs),
        FTMOGuardrails(),
        pd.DataFrame(index=[time, time + pd.Timedelta(minutes=1)]),
        pd.Series({"open": 100.0, "high": 100.1, "low": 99.0, "close": 99.5}),
        i=0,
        bar_time=time,
        bar_duration=pd.Timedelta(minutes=1),
        session=0,
        is_ny=False,
        bar_quote=(99.5, 99.5),
        entry_time=time - pd.Timedelta(minutes=1),
        position_active_in_bar=True,
        full_bar_available_after_entry=True,
        execution_rng=np.random.default_rng(0),
        resolve_bar_execution=resolve_fill,
        fill_quote_event=lambda *_args, **_kwargs: resolve_fill(),
        sl_tp_fill_quote=lambda *_args: (99.0, 99.0),
        bar_spread_price_units=lambda *_args: 0.0,
        is_last_ny_bar=lambda *_args: False,
        eod_guard_due=False,
    )

    assert stop is False
    assert state.position is None
    close = next(event for event in state.trade_log if event["type"] == "eod_close")
    assert close["reason"] == "eod_max_loss"


def test_eod_max_age_closes_at_the_resolved_execution_quote_and_realizes_pnl() -> None:
    time = pd.Timestamp("2026-02-02 14:31", tz="UTC")
    fill_time = time + pd.Timedelta(seconds=5)
    costs = CostModel(spread_points=0.0, point_size=0.01, point_value=1.0)
    settings = BacktestSettings(
        cost_model=costs,
        lots=1.0,
        max_loss_per_trade_usd=None,
        take_profit_per_trade_usd=None,
        tickbook=None,
        fill_delay_ms=0,
        randomized_fill_latency_ms=0.0,
        max_tick_quote_wait_ms=1_000,
        tick_execution_required=False,
        use_structure_sl_tp=True,
        risk_frac=0.01,
        policy_risk_frac_range=(0.01, 0.01),
        rr_ratio=2.0,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
        contract_size=1.0,
        hold_on_zero=False,
        exit_action=None,
        block_overnight=False,
        eod_risk={"max_age_hours": 8.0},
    )
    position = Position(
        direction=1,
        size=1.0,
        entry_price=100.0,
        margin_used=0.0,
        position_id="max-age-close",
        sl_price=None,
        tp_price=None,
    )
    state = BacktestState(account=AccountState(initial_balance=10_000.0), position=position)

    def resolve_fill(
        *_args: object, **_kwargs: object
    ) -> tuple[tuple[float, float], pd.Timestamp, str, dict[str, Any]]:
        return (98.0, 98.0), fill_time, "bar_open", {}

    stopped = process_protective_and_account_events(
        state,
        settings,
        Broker(cost_model=costs),
        FTMOGuardrails(),
        pd.DataFrame(index=[time, time + pd.Timedelta(minutes=1)]),
        pd.Series({"open": 100.0, "high": 100.1, "low": 99.9, "close": 100.0}),
        i=0,
        bar_time=time,
        bar_duration=pd.Timedelta(minutes=1),
        session=0,
        is_ny=False,
        bar_quote=(100.0, 100.0),
        entry_time=time - pd.Timedelta(hours=9),
        position_active_in_bar=True,
        full_bar_available_after_entry=True,
        execution_rng=np.random.default_rng(0),
        resolve_bar_execution=resolve_fill,
        fill_quote_event=lambda *_args, **_kwargs: resolve_fill(),
        sl_tp_fill_quote=lambda *_args: (100.0, 100.0),
        bar_spread_price_units=lambda *_args: 0.0,
        is_last_ny_bar=lambda *_args: False,
        eod_guard_due=False,
    )

    assert stopped is False
    assert state.position is None
    close = next(event for event in state.trade_log if event["type"] == "eod_close")
    assert close["reason"] == "max_age"
    assert close["time"] == time
    assert close["fill_time"] == fill_time
    assert close["fill_quote_source"] == "bar_open"
    assert close["pnl"] == pytest.approx(-2.0)
    assert state.account.balance == pytest.approx(9_998.0)


def test_tick_only_session_close_refuses_to_invent_a_fill_when_no_deadline_quote_exists() -> None:
    time = pd.Timestamp("2026-02-02 20:59", tz="UTC")
    costs = CostModel(spread_points=0.0, point_size=0.01)
    settings = BacktestSettings(
        cost_model=costs,
        lots=1.0,
        max_loss_per_trade_usd=None,
        take_profit_per_trade_usd=None,
        tickbook=TickBook(np.asarray([], dtype=np.int64), np.asarray([]), np.asarray([])),
        fill_delay_ms=0,
        randomized_fill_latency_ms=0.0,
        max_tick_quote_wait_ms=1_000,
        tick_execution_required=True,
        use_structure_sl_tp=False,
        risk_frac=0.01,
        policy_risk_frac_range=(0.01, 0.01),
        rr_ratio=2.0,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
        contract_size=1.0,
        hold_on_zero=False,
        exit_action=None,
        block_overnight=True,
        eod_risk=None,
    )
    position = Position(
        direction=1,
        size=1.0,
        entry_price=100.0,
        margin_used=0.0,
        position_id="deadline-tick-required",
        sl_price=None,
        tp_price=None,
    )
    state = BacktestState(account=AccountState(initial_balance=10_000.0), position=position)

    with pytest.raises(
        TickExecutionUnavailable, match="no executable tick between order submission"
    ):
        process_protective_and_account_events(
            state,
            settings,
            Broker(cost_model=costs),
            FTMOGuardrails(),
            pd.DataFrame(index=[time, time + pd.Timedelta(minutes=1)]),
            pd.Series({"open": 100.0, "high": 100.1, "low": 99.9, "close": 100.0}),
            i=0,
            bar_time=time,
            bar_duration=pd.Timedelta(minutes=1),
            session=0,
            is_ny=True,
            bar_quote=(100.0, 100.0),
            entry_time=time - pd.Timedelta(minutes=1),
            position_active_in_bar=True,
            full_bar_available_after_entry=True,
            execution_rng=np.random.default_rng(0),
            resolve_bar_execution=lambda *_args, **_kwargs: ((100.0, 100.0), time, "tick", {}),
            fill_quote_event=lambda *_args, **_kwargs: ((100.0, 100.0), time, "tick", {}),
            sl_tp_fill_quote=lambda *_args: (100.0, 100.0),
            bar_spread_price_units=lambda *_args: 0.0,
            is_last_ny_bar=lambda *_args: True,
            eod_guard_due=False,
        )

    assert state.position is position
    assert not state.trade_log


def test_tick_replay_closes_multi_target_position_in_quote_order() -> None:
    time = pd.Timestamp("2026-02-02 14:31", tz="UTC")
    target_times = [time + pd.Timedelta(seconds=10), time + pd.Timedelta(seconds=20)]
    tickbook = TickBook(
        np.asarray([timestamp.value for timestamp in target_times], dtype=np.int64),
        np.asarray([101.1, 102.1]),
        np.asarray([101.2, 102.2]),
    )
    costs = CostModel(spread_points=0.0, point_size=0.01, point_value=1.0)
    settings = BacktestSettings(
        cost_model=costs,
        lots=1.0,
        max_loss_per_trade_usd=None,
        take_profit_per_trade_usd=None,
        tickbook=tickbook,
        fill_delay_ms=0,
        randomized_fill_latency_ms=0.0,
        max_tick_quote_wait_ms=1_000,
        tick_execution_required=False,
        use_structure_sl_tp=True,
        risk_frac=0.01,
        policy_risk_frac_range=(0.01, 0.01),
        rr_ratio=2.0,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
        contract_size=1.0,
        hold_on_zero=False,
        exit_action=None,
        block_overnight=False,
        eod_risk=None,
    )
    position = Position(
        direction=1,
        size=1.0,
        initial_size=1.0,
        tp_initial_size=1.0,
        tp_lot_fractions=(0.5, 0.5),
        entry_price=100.0,
        margin_used=0.0,
        position_id="ordered-tick-targets",
        sl_price=95.0,
        tp_price=101.0,
        tp1_price=101.0,
        tp2_price=102.0,
    )
    state = BacktestState(account=AccountState(initial_balance=10_000.0), position=position)

    stopped = process_protective_and_account_events(
        state,
        settings,
        Broker(cost_model=costs),
        FTMOGuardrails(),
        pd.DataFrame(index=[time, time + pd.Timedelta(minutes=1)]),
        pd.Series({"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0}),
        i=0,
        bar_time=time,
        bar_duration=pd.Timedelta(minutes=1),
        session=0,
        is_ny=False,
        bar_quote=(100.0, 100.0),
        entry_time=time - pd.Timedelta(minutes=1),
        position_active_in_bar=True,
        full_bar_available_after_entry=True,
        execution_rng=np.random.default_rng(0),
        resolve_bar_execution=lambda *_args, **_kwargs: ((100.0, 100.0), time, "bar_open", {}),
        fill_quote_event=lambda *_args, **_kwargs: ((100.0, 100.0), time, "bar_open", {}),
        sl_tp_fill_quote=lambda *_args: (100.0, 100.0),
        bar_spread_price_units=lambda *_args: 0.0,
        is_last_ny_bar=lambda *_args: False,
        eod_guard_due=False,
    )

    closes = [
        event for event in state.trade_log if event["type"] in {"tp_partial_close", "tp_close"}
    ]
    assert stopped is False
    assert [event["tp_slot"] for event in closes] == [1, 2]
    assert [event["time"] for event in closes] == target_times
    assert [event["reason"] for event in closes] == ["structure_tp1", "structure_tp2"]
    assert state.position is None
    # The replay fills at the first executable quote past each target, not at
    # the target level: 0.5 * 1.1 plus 0.5 * 2.1 points of realized PnL.
    assert state.account.balance == pytest.approx(10_001.6)
