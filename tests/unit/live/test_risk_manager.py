"""Headless tests for stop-based live position and aggregate-risk limits."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        sys.modules["MetaTrader5"] = ModuleType("MetaTrader5")

_mt5_stub = sys.modules["MetaTrader5"]
if not hasattr(_mt5_stub, "TIMEFRAME_H1"):
    setattr(_mt5_stub, "TIMEFRAME_H1", 60)
if not hasattr(_mt5_stub, "ORDER_TYPE_BUY"):
    setattr(_mt5_stub, "ORDER_TYPE_BUY", 0)
if not hasattr(_mt5_stub, "ORDER_TYPE_SELL"):
    setattr(_mt5_stub, "ORDER_TYPE_SELL", 1)

import MetaTrader5 as mt5  # noqa: E402

from integrations.mt5.domain.risk_manager import RiskManager  # noqa: E402


@pytest.fixture
def mt5_risk_api(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    info = SimpleNamespace(
        trade_tick_size=0.01,
        trade_tick_value=1.0,
        digits=2,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )
    tick = SimpleNamespace(bid=100.0, ask=100.01)
    positions: list[Any] | None = []
    monkeypatch.setattr(mt5, "symbol_select", lambda *_args, **_kwargs: True, raising=False)
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: info, raising=False)
    monkeypatch.setattr(mt5, "symbol_info_tick", lambda _symbol: tick, raising=False)
    monkeypatch.setattr(
        mt5,
        "account_info",
        lambda: SimpleNamespace(balance=100_000.0, equity=100_000.0),
        raising=False,
    )
    monkeypatch.setattr(mt5, "positions_get", lambda: positions, raising=False)
    return {"info": info, "tick": tick, "positions": positions}


def test_sizing_rounds_down_and_stop_price_uses_same_distance(
    mt5_risk_api: dict[str, Any],
) -> None:
    manager = RiskManager(risk_per_symbol=0.01, max_total_risk=0.02)

    size = manager.calculate_position_size("US100.cash", stop_loss_pips=50.0)
    buy_stop = manager.calculate_stop_loss_price("US100.cash", mt5.ORDER_TYPE_BUY, 50.0)
    sell_stop = manager.calculate_stop_loss_price("US100.cash", mt5.ORDER_TYPE_SELL, 50.0)

    assert size == pytest.approx(20.0)
    assert buy_stop == pytest.approx(99.51)
    assert sell_stop == pytest.approx(100.5)
    allowed, message = manager.check_risk_limits("US100.cash", size, 50.0)
    assert allowed is True
    assert "total stop risk plus reserve: 1.00%" in message


def test_risk_manager_constructor_defaults_remain_backward_compatible() -> None:
    manager = RiskManager()

    assert manager.risk_per_symbol == pytest.approx(0.01)
    assert manager.max_total_risk == pytest.approx(0.02)
    assert manager.risk_per_symbol_usd_cap is None
    assert manager.execution_slippage_points == pytest.approx(0.0)
    assert manager.commission_per_lot == pytest.approx(0.0)


def test_absolute_per_symbol_cap_limits_sizing_and_risk_acceptance(
    mt5_risk_api: dict[str, Any],
) -> None:
    manager = RiskManager(
        risk_per_symbol=0.01,
        max_total_risk=0.02,
        risk_per_symbol_usd_cap=900.0,
    )

    size = manager.calculate_position_size("US100.cash", stop_loss_pips=50.0)
    allowed, message = manager.check_risk_limits("US100.cash", 18.01, 50.0)

    assert size == pytest.approx(18.0)
    assert allowed is False
    assert "per-symbol limit ($900.00" in message


def test_absolute_per_symbol_cap_applies_after_volatility_scaling(
    mt5_risk_api: dict[str, Any],
) -> None:
    manager = RiskManager(
        risk_per_symbol=0.01,
        max_total_risk=0.02,
        risk_per_symbol_usd_cap=900.0,
    )

    size = manager.calculate_position_size(
        "US100.cash", stop_loss_pips=50.0, volatility_multiplier=0.5
    )

    assert size == pytest.approx(18.0)


def test_new_order_reserves_entry_and_stop_slippage_plus_round_trip_commission(
    mt5_risk_api: dict[str, Any],
) -> None:
    manager = RiskManager(
        risk_per_symbol=0.01,
        max_total_risk=0.02,
        risk_per_symbol_usd_cap=900.0,
        execution_slippage_points=5.0,
        commission_per_lot=2.5,
    )

    size = manager.calculate_position_size("US100.cash", stop_loss_pips=50.0)
    allowed, message = manager.check_risk_limits("US100.cash", 0.86, 50.0)

    assert size == pytest.approx(0.85)
    assert allowed is False
    assert "including execution reserve ($907.30)" in message


def test_aggregate_limit_reserves_only_remaining_costs_for_existing_positions(
    mt5_risk_api: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    position = SimpleNamespace(
        symbol="US500.cash",
        volume=10.0,
        price_open=100.0,
        sl=99.5,
        profit=0.0,
    )
    monkeypatch.setattr(mt5, "positions_get", lambda: [position], raising=False)
    manager = RiskManager(
        risk_per_symbol=0.10,
        max_total_risk=0.06,
        execution_slippage_points=5.0,
        commission_per_lot=2.5,
    )

    exposure = manager.get_total_exposure()
    allowed, message = manager.check_risk_limits("US100.cash", 1.0, 50.0)

    assert exposure["total_open_risk"] == pytest.approx(500.0)
    assert exposure["total_open_execution_reserve"] == pytest.approx(5025.0)
    assert exposure["total_open_risk_with_reserve"] == pytest.approx(5525.0)
    assert allowed is False
    assert "Total stop risk plus execution reserve" in message


def test_volume_step_rounding_never_exceeds_cash_risk_budget(
    mt5_risk_api: dict[str, Any],
) -> None:
    manager = RiskManager(risk_per_symbol=0.01, max_total_risk=0.02)

    size = manager.calculate_position_size("US100.cash", stop_loss_pips=50.0, risk_amount=999.9)
    distance = 50.0 * mt5_risk_api["info"].trade_tick_size
    planned_risk = (
        distance
        / mt5_risk_api["info"].trade_tick_size
        * mt5_risk_api["info"].trade_tick_value
        * size
    )

    assert size == pytest.approx(19.99)
    assert planned_risk <= 999.9


def test_aggregate_limit_uses_open_stop_risk_not_floating_profit(
    mt5_risk_api: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    position = SimpleNamespace(
        symbol="US500.cash",
        volume=30.0,
        price_open=100.0,
        sl=99.5,
        profit=0.0,
    )
    monkeypatch.setattr(mt5, "positions_get", lambda: [position], raising=False)
    manager = RiskManager(risk_per_symbol=0.01, max_total_risk=0.02)

    exposure = manager.get_total_exposure()
    allowed, message = manager.check_risk_limits("US100.cash", 20.0, 50.0)

    assert exposure["total_open_risk"] == pytest.approx(1500.0)
    assert exposure["risk_unknown_positions"] == 0
    assert allowed is False
    assert "2.50%" in message


@pytest.mark.parametrize(
    "position",
    [
        SimpleNamespace(symbol="US500.cash", volume=1.0, price_open=100.0, sl=0.0, profit=0.0),
        SimpleNamespace(symbol="US500.cash", volume=1.0, price_open=100.0, profit=0.0),
    ],
)
def test_unknown_existing_stop_risk_blocks_new_trade(
    mt5_risk_api: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    position: Any,
) -> None:
    monkeypatch.setattr(mt5, "positions_get", lambda: [position], raising=False)
    manager = RiskManager(risk_per_symbol=0.01, max_total_risk=0.02)

    allowed, message = manager.check_risk_limits("US100.cash", 1.0, 50.0)

    assert allowed is False
    assert "risk is unknown" in message


def test_position_query_failure_blocks_new_trade(
    mt5_risk_api: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mt5, "positions_get", lambda: None, raising=False)
    manager = RiskManager(risk_per_symbol=0.01, max_total_risk=0.02)

    allowed, message = manager.check_risk_limits("US100.cash", 1.0, 50.0)

    assert allowed is False
    assert "risk is unknown" in message


def test_minimum_volume_is_not_forced_above_risk_budget(
    mt5_risk_api: dict[str, Any],
) -> None:
    manager = RiskManager(risk_per_symbol=0.000001, max_total_risk=0.02)

    assert manager.calculate_position_size("US100.cash", stop_loss_pips=50.0) == 0.0


@pytest.mark.parametrize(
    ("manager_kwargs", "size_kwargs"),
    [
        ({}, {"risk_amount": True}),
        ({}, {"volatility_multiplier": True}),
        ({}, {"stop_loss_pips": True}),
        ({"risk_per_symbol": True}, {}),
        ({"max_total_risk": True}, {}),
        ({"risk_per_symbol_usd_cap": True}, {}),
        ({"execution_slippage_points": True}, {}),
        ({"commission_per_lot": True}, {}),
    ],
)
def test_boolean_sizing_inputs_fail_closed(
    mt5_risk_api: dict[str, Any],
    manager_kwargs: dict[str, Any],
    size_kwargs: dict[str, Any],
) -> None:
    manager = RiskManager(**manager_kwargs)
    input_kwargs = dict(size_kwargs)
    stop_loss_pips = input_kwargs.pop("stop_loss_pips", 50.0)
    sizing_kwargs = {"risk_amount": 900.0, **input_kwargs}
    size = manager.calculate_position_size(
        "US100.cash", stop_loss_pips=stop_loss_pips, **sizing_kwargs
    )

    assert size == 0.0


@pytest.mark.parametrize(
    ("manager_kwargs", "proposed_position_size", "stop_loss_pips"),
    [
        ({}, True, 50.0),
        ({}, 1.0, True),
        ({"risk_per_symbol": True}, 1.0, 50.0),
        ({"max_total_risk": True}, 1.0, 50.0),
        ({"risk_per_symbol_usd_cap": True}, 1.0, 50.0),
    ],
)
def test_boolean_risk_limit_inputs_fail_closed(
    mt5_risk_api: dict[str, Any],
    manager_kwargs: dict[str, Any],
    proposed_position_size: float,
    stop_loss_pips: float,
) -> None:
    manager = RiskManager(**manager_kwargs)

    allowed, message = manager.check_risk_limits(
        "US100.cash", proposed_position_size, stop_loss_pips
    )

    assert allowed is False
    assert message


def test_boolean_account_balance_blocks_new_risk(
    mt5_risk_api: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        mt5,
        "account_info",
        lambda: SimpleNamespace(balance=True, equity=100_000.0),
        raising=False,
    )
    manager = RiskManager()

    allowed, message = manager.check_risk_limits("US100.cash", 1.0, 50.0)

    assert allowed is False
    assert "balance is unavailable" in message


def test_boolean_position_volume_makes_existing_risk_unknown(
    mt5_risk_api: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    position = SimpleNamespace(
        symbol="US500.cash", volume=True, price_open=100.0, sl=99.5, profit=0.0
    )
    monkeypatch.setattr(mt5, "positions_get", lambda: [position], raising=False)
    manager = RiskManager()

    exposure = manager.get_total_exposure()
    allowed, message = manager.check_risk_limits("US100.cash", 1.0, 50.0)

    assert exposure["query_failed"] is True
    assert allowed is False
    assert "risk is unknown" in message


def test_boolean_quote_cannot_create_a_stop_price(
    mt5_risk_api: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        mt5,
        "symbol_info_tick",
        lambda _symbol: SimpleNamespace(bid=100.0, ask=True),
        raising=False,
    )
    manager = RiskManager()

    with pytest.raises(ValueError, match="Invalid ask quote"):
        manager.calculate_stop_loss_price("US100.cash", mt5.ORDER_TYPE_BUY, 50.0)


@pytest.mark.parametrize(
    ("atr_percentage", "base_atr"),
    [
        (True, 1.0),
        (1.0, True),
        (float("nan"), 1.0),
        (float("inf"), 1.0),
        (-0.1, 1.0),
        (1.0, -0.1),
    ],
)
def test_invalid_atr_cannot_increase_or_preserve_position_size(
    mt5_risk_api: dict[str, Any], atr_percentage: float, base_atr: float
) -> None:
    manager = RiskManager()

    multiplier = manager.get_volatility_multiplier(atr_percentage, base_atr)

    assert multiplier == 0.0
    assert (
        manager.calculate_position_size(
            "US100.cash", stop_loss_pips=50.0, volatility_multiplier=multiplier
        )
        == 0.0
    )
