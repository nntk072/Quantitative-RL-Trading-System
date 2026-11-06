from __future__ import annotations

import pandas as pd
import pytest

from simulation.backtest.protective_events import (
    _advance_management_modes,
    _apply_tp_management,
)
from simulation.backtest.runtime import BacktestSettings, BacktestState
from trading import AccountState
from trading.execution import CostModel, Position


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
