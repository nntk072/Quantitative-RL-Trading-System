from __future__ import annotations

from dataclasses import replace
from typing import NoReturn

import numpy as np
import pandas as pd
import pytest

from simulation.backtest.accounting import stamp_exit
from simulation.backtest.protective_events import (
    _advance_management_modes,
    _apply_tp_management,
    process_protective_and_account_events,
)
from simulation.backtest.runtime import BacktestSettings, BacktestState
from trading import AccountState
from trading.execution import Broker, CostModel, Position
from trading.risk import FTMOGuardrails


def _settings() -> BacktestSettings:
    return BacktestSettings(
        cost_model=CostModel(spread_points=0.0, commission_per_lot=0.0, point_size=0.01),
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
        tp_breakeven_alpha=0.5,
    )


def _position(*, tp_mode: str = "fixed") -> Position:
    return Position(
        direction=1,
        size=1.0,
        entry_price=100.0,
        margin_used=2.0,
        position_id="test-position",
        initial_size=1.0,
        sl_price=99.0,
        sl_initial_price=99.0,
        tp_price=103.0,
        tp1_price=103.0,
        tp2_price=105.0,
        tp_lot_fractions=(0.5, 0.5),
        tp_initial_size=1.0,
        tp_mode=tp_mode,
    )


def test_backtest_exit_records_account_currency_point_value() -> None:
    settings = replace(
        _settings(),
        cost_model=CostModel(point_value=2.5),
        contract_size=3.0,
    )
    position = Position(
        direction=1,
        size=0.0,
        entry_price=100.0,
        margin_used=0.0,
        initial_size=0.5,
    )
    state = BacktestState(account=AccountState(initial_balance=1000.0))
    record: dict[str, object] = {"type": "close", "pnl": 15.0}

    stamp_exit(state, settings, position, record, fill_price=104.0)

    assert record["gross_price_pnl"] == pytest.approx(15.0)
    assert record["point_value"] == 2.5


def test_explicit_tp_breakeven_pulls_nearest_target_without_retroactive_fill() -> None:
    position = _position(tp_mode="breakeven")
    state = BacktestState(account=AccountState(initial_balance=100_000.0), position=position)
    time = pd.Timestamp("2026-01-05T10:00:00Z")

    _apply_tp_management(
        position,
        _settings(),
        state,
        None,
        bar_index=0,
        bar_time=time,
        next_bar_time=time + pd.Timedelta(minutes=1),
        current_price=100.2,
    )

    assert position.tp1_price == pytest.approx(100.5)
    assert position.tp2_price == pytest.approx(105.0)
    assert state.trade_log[0]["effective_time"] == time + pd.Timedelta(minutes=1)

    behind_market = _position(tp_mode="breakeven")
    behind_state = BacktestState(
        account=AccountState(initial_balance=100_000.0), position=behind_market
    )
    _apply_tp_management(
        behind_market,
        _settings(),
        behind_state,
        None,
        bar_index=0,
        bar_time=time,
        next_bar_time=None,
        current_price=101.0,
    )
    assert behind_market.tp1_price == pytest.approx(103.0)
    assert not behind_state.trade_log


def test_explicit_tp_trailing_extends_nearest_target_and_preserves_order() -> None:
    position = _position(tp_mode="trailing")
    state = BacktestState(account=AccountState(initial_balance=100_000.0), position=position)
    time = pd.Timestamp("2026-01-05T10:00:00Z")

    _apply_tp_management(
        position,
        _settings(),
        state,
        pd.Series({"last_swing_high": 104.0}),
        bar_index=0,
        bar_time=time,
        next_bar_time=time + pd.Timedelta(minutes=1),
        current_price=102.0,
    )

    assert position.tp1_price == pytest.approx(104.0)
    assert position.tp2_price == pytest.approx(105.0)
    assert position.tp_price == pytest.approx(104.0)
    assert state.trade_log[0]["reason"] == "new_confirmed_favorable_swing"


def test_deferred_modes_advance_from_excursion_and_new_confirmed_swing() -> None:
    position = _position()
    position.sl_mode_overridden = False
    position.tp_mode_overridden = False
    position.entry_last_swing_high = 102.0
    position.best_favorable = 0.5

    _advance_management_modes(position, pd.Series({"last_swing_high": 103.0}))

    assert position.sl_mode == "trailing"
    assert position.tp_mode == "trailing"


def test_eod_progress_threshold_resets_stale_counter_when_favorable_progress_advances() -> None:
    settings = replace(
        _settings(),
        eod_risk={
            "progress_threshold_atr": 0.25,
            "max_loss_usd": 1_000_000.0,
            "breakeven_trigger_r": 100.0,
        },
    )
    position = Position(
        direction=1,
        size=1.0,
        entry_price=100.0,
        margin_used=2.0,
        position_id="stale-progress",
        entry_atr=2.0,
        last_progress_favorable=0.0,
        stale_counter=4,
        sl_price=98.0,
        sl_initial_price=98.0,
    )
    state = BacktestState(
        account=AccountState(initial_balance=100_000.0),
        position=position,
    )
    time = pd.Timestamp("2026-01-05T10:00:00Z")

    def unexpected_fill(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("unexpected execution fill")

    should_stop = process_protective_and_account_events(
        state,
        settings,
        Broker(cost_model=settings.cost_model),
        FTMOGuardrails(),
        pd.DataFrame(index=[time, time + pd.Timedelta(minutes=1)]),
        pd.Series({"open": 100.0, "high": 101.0, "low": 99.9, "close": 100.5}),
        feature_row=None,
        i=0,
        bar_time=time,
        bar_duration=pd.Timedelta(minutes=1),
        session=0,
        is_ny=False,
        bar_quote=(100.5, 100.5),
        entry_time=time - pd.Timedelta(minutes=1),
        position_active_in_bar=True,
        full_bar_available_after_entry=True,
        execution_rng=np.random.default_rng(0),
        resolve_bar_execution=unexpected_fill,
        fill_quote_event=unexpected_fill,
        sl_tp_fill_quote=unexpected_fill,
        bar_spread_price_units=lambda *_args: None,
        is_last_ny_bar=lambda *_args: False,
        eod_guard_due=False,
    )

    assert should_stop is False
    assert state.position is position
    assert position.last_progress_favorable == 1.0
    assert position.stale_counter == 0
