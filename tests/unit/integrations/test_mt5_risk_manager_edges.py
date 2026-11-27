"""Fail-closed risk behavior with controlled broker metadata."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any, NamedTuple, cast

import pytest

if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        sys.modules["MetaTrader5"] = ModuleType("MetaTrader5")

mt5 = cast(Any, sys.modules["MetaTrader5"])
if not hasattr(mt5, "TIMEFRAME_H1"):
    mt5.TIMEFRAME_H1 = 16385
if not hasattr(mt5, "ORDER_TYPE_BUY"):
    mt5.ORDER_TYPE_BUY = 0
if not hasattr(mt5, "ORDER_TYPE_SELL"):
    mt5.ORDER_TYPE_SELL = 1

from integrations.mt5.domain.risk_manager import RiskManager  # noqa: E402


def _symbol_info() -> SimpleNamespace:
    return SimpleNamespace(
        trade_tick_size=0.01,
        trade_tick_value=1.0,
        digits=2,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )


def test_sizing_stops_when_symbol_selection_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(mt5, "symbol_select", lambda *_args: False, raising=False)
    monkeypatch.setattr(
        mt5,
        "symbol_info",
        lambda symbol: calls.append(symbol),
        raising=False,
    )

    size = RiskManager().calculate_position_size("US100", stop_loss_pips=10.0)

    assert size == 0.0
    assert calls == []


def test_account_balance_is_unavailable_when_terminal_has_no_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mt5, "account_info", lambda: None, raising=False)

    assert RiskManager().get_account_balance() == 0.0


@pytest.mark.parametrize(
    "account",
    [None, SimpleNamespace(equity=True), SimpleNamespace(equity="invalid")],
)
def test_account_equity_is_zero_when_terminal_value_is_missing_or_invalid(
    monkeypatch: pytest.MonkeyPatch, account: object | None
) -> None:
    monkeypatch.setattr(mt5, "account_info", lambda: account, raising=False)

    assert RiskManager().get_account_equity() == 0.0


def test_stop_price_requires_valid_tick_metadata_and_quote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _symbol_info()
    monkeypatch.setattr(mt5, "symbol_select", lambda *_args: True, raising=False)
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: info, raising=False)
    monkeypatch.setattr(
        mt5, "symbol_info_tick", lambda _symbol: SimpleNamespace(ask=100.0, bid=99.9), raising=False
    )
    manager = RiskManager()

    info.trade_tick_size = 0.0
    with pytest.raises(ValueError, match="invalid symbol tick data"):
        manager.calculate_stop_loss_price("US100", 0, 10.0)

    info.trade_tick_size = 0.01
    monkeypatch.setattr(mt5, "symbol_info_tick", lambda _symbol: None, raising=False)
    with pytest.raises(ValueError, match="Missing symbol or quote data"):
        manager.calculate_stop_loss_price("US100", 0, 10.0)


def test_missing_symbol_metadata_marks_open_execution_reserve_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    position = SimpleNamespace(
        symbol="US500",
        volume=1.0,
        price_open=100.0,
        sl=99.0,
        profit=50.0,
    )
    monkeypatch.setattr(mt5, "positions_get", lambda: [position], raising=False)
    monkeypatch.setattr(
        mt5,
        "symbol_info",
        lambda symbol: _symbol_info() if symbol == "US100" else None,
        raising=False,
    )
    monkeypatch.setattr(
        mt5, "account_info", lambda: SimpleNamespace(balance=100_000.0), raising=False
    )

    manager = RiskManager()
    exposure = manager.get_total_exposure()
    allowed, reason = manager.check_risk_limits("US100", 1.0, 10.0)

    assert exposure["risk_unknown_positions"] == 1
    assert exposure["total_open_execution_reserve"] == 0.0
    assert allowed is False
    assert "risk is unknown" in reason


def test_exposure_filter_limits_aggregation_to_requested_symbols(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    positions = [
        SimpleNamespace(
            symbol=symbol,
            volume=volume,
            price_open=100.0,
            sl=99.0,
            profit=profit,
        )
        for symbol, volume, profit in (("US100", 1.0, 10.0), ("US500", 2.0, -5.0))
    ]
    monkeypatch.setattr(mt5, "positions_get", lambda: positions, raising=False)
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: _symbol_info(), raising=False)

    exposure = RiskManager().get_total_exposure(symbols=["US500"])

    assert exposure["total_positions"] == 1
    assert exposure["total_volume"] == 2.0
    assert exposure["total_profit"] == -5.0
    assert list(exposure["symbols"]) == ["US500"]


def test_malformed_position_metadata_marks_aggregate_exposure_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    malformed = SimpleNamespace(
        symbol="US100",
        volume=True,
        price_open=100.0,
        sl=99.0,
        profit=0.0,
    )
    monkeypatch.setattr(mt5, "positions_get", lambda: [malformed], raising=False)

    exposure = RiskManager().get_total_exposure()

    assert exposure["query_failed"] is True
    assert exposure["risk_unknown_positions"] == 1
    assert exposure["symbols"] == {}


def test_positions_query_exception_marks_aggregate_result_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_query_error() -> None:
        raise RuntimeError("terminal disconnected")

    monkeypatch.setattr(mt5, "positions_get", raise_query_error, raising=False)

    exposure = RiskManager().get_total_exposure()

    assert exposure["query_failed"] is True
    assert exposure["risk_unknown_positions"] == 1
    assert exposure["symbols"] == {}


def test_malformed_existing_position_tick_data_keeps_only_that_risk_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    position = SimpleNamespace(
        symbol="US500",
        volume=1.0,
        price_open=100.0,
        sl=99.0,
        profit=0.0,
    )
    invalid_info = _symbol_info()
    invalid_info.trade_tick_size = 0.0
    monkeypatch.setattr(mt5, "positions_get", lambda: [position], raising=False)
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: invalid_info, raising=False)

    exposure = RiskManager().get_total_exposure()

    assert exposure["query_failed"] is False
    assert exposure["risk_unknown_positions"] == 1
    assert exposure["total_open_risk"] == 0.0
    assert exposure["symbols"]["US500"]["open_risk"] == 0.0


@pytest.mark.parametrize("invalid_metadata", [None, "boolean_volume_step"])
def test_sizing_rejects_missing_symbol_or_invalid_volume_metadata(
    monkeypatch: pytest.MonkeyPatch, invalid_metadata: object | None
) -> None:
    info = _symbol_info() if invalid_metadata == "boolean_volume_step" else invalid_metadata
    if info is not None and invalid_metadata == "boolean_volume_step":
        cast(Any, info).volume_step = True
    monkeypatch.setattr(mt5, "symbol_select", lambda *_args: True, raising=False)
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: info, raising=False)
    monkeypatch.setattr(
        mt5,
        "symbol_info_tick",
        lambda _symbol: SimpleNamespace(bid=99.9, ask=100.1),
        raising=False,
    )

    size = RiskManager().calculate_position_size("US100", stop_loss_pips=10.0, risk_amount=100.0)

    assert size == 0.0


def test_invalid_execution_cost_configuration_fails_closed_during_sizing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mt5, "symbol_select", lambda *_args: True, raising=False)
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: _symbol_info(), raising=False)
    monkeypatch.setattr(
        mt5,
        "symbol_info_tick",
        lambda _symbol: SimpleNamespace(bid=99.9, ask=100.1),
        raising=False,
    )
    monkeypatch.setattr(
        mt5, "account_info", lambda: SimpleNamespace(balance=100_000.0), raising=False
    )

    manager = RiskManager(commission_per_lot=-1.0)

    assert manager.calculate_position_size("US100", stop_loss_pips=10.0) == 0.0


def test_execution_reserve_rejects_unavailable_and_nonpositive_position_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: _symbol_info(), raising=False)
    manager = RiskManager(execution_slippage_points=0.2, commission_per_lot=1.0)

    assert manager._position_execution_reserve({"volume": 1.0}) is None
    assert manager._position_execution_reserve({"symbol": "US100", "volume": True}) is None
    assert manager._position_execution_reserve({"symbol": "US100", "volume": 0.0}) is None
    assert manager._position_execution_reserve({"symbol": "US100", "volume": 1.0}) == pytest.approx(
        21.0
    )


def test_account_balance_returns_zero_when_terminal_query_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_query() -> None:
        raise RuntimeError("terminal disconnected")

    monkeypatch.setattr(mt5, "account_info", fail_query, raising=False)

    assert RiskManager().get_account_balance() == 0.0


def test_position_stop_risk_rejects_boolean_and_invalid_broker_tick_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    position = {
        "symbol": "US100",
        "volume": 1.0,
        "price_open": 100.0,
        "sl": 99.0,
    }
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: _symbol_info(), raising=False)
    assert RiskManager._position_stop_risk({**position, "volume": True}) is None

    invalid = _symbol_info()
    invalid.trade_tick_value = 0.0
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: invalid, raising=False)
    assert RiskManager._position_stop_risk(position) is None


def test_position_reader_accepts_broker_namedtuple_fields() -> None:
    class Position(NamedTuple):
        symbol: str

    assert RiskManager._position_value(Position("US100"), "symbol") == "US100"
    assert RiskManager._position_value(Position("US100"), "missing", "fallback") == "fallback"


def test_sizing_and_risk_check_reject_invalid_config_and_proposals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = RiskManager(risk_per_symbol=0.0)
    assert manager.calculate_position_size("US100", stop_loss_pips=10.0) == 0.0

    monkeypatch.setattr(
        mt5, "account_info", lambda: SimpleNamespace(balance=100_000.0), raising=False
    )
    allowed, reason = manager.check_risk_limits(
        "US100", proposed_position_size=0.0, stop_loss_pips=10.0
    )
    assert not allowed
    assert "nonpositive" in reason
    allowed, reason = RiskManager(risk_per_symbol=0.0).check_risk_limits(
        "US100", proposed_position_size=1.0, stop_loss_pips=10.0
    )
    assert not allowed
    assert "risk limit is invalid" in reason


@pytest.mark.parametrize(
    ("position_type", "tick", "expected"),
    [
        (mt5.ORDER_TYPE_SELL, SimpleNamespace(ask=100.0, bid=99.9), 100.0),
        (mt5.ORDER_TYPE_BUY, SimpleNamespace(ask=100.0, bid=99.9), 99.9),
    ],
)
def test_stop_price_uses_directional_quote_and_precision(
    monkeypatch: pytest.MonkeyPatch, position_type: int, tick: object, expected: float
) -> None:
    monkeypatch.setattr(mt5, "symbol_select", lambda *_args: True, raising=False)
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: _symbol_info(), raising=False)
    monkeypatch.setattr(mt5, "symbol_info_tick", lambda _symbol: tick, raising=False)

    price = RiskManager().calculate_stop_loss_price("US100", position_type, 10.0)

    assert price == pytest.approx(expected)


def test_stop_price_rejects_unsupported_type_and_boolean_quote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mt5, "symbol_select", lambda *_args: True, raising=False)
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: _symbol_info(), raising=False)
    monkeypatch.setattr(
        mt5, "symbol_info_tick", lambda _symbol: SimpleNamespace(ask=True, bid=99.9), raising=False
    )
    with pytest.raises(ValueError, match="Invalid ask quote"):
        RiskManager().calculate_stop_loss_price("US100", mt5.ORDER_TYPE_BUY, 10.0)

    monkeypatch.setattr(
        mt5, "symbol_info_tick", lambda _symbol: SimpleNamespace(ask=100.0, bid=99.9), raising=False
    )
    with pytest.raises(ValueError, match="Unsupported order type"):
        RiskManager().calculate_stop_loss_price("US100", 99, 10.0)

    monkeypatch.setattr(
        mt5, "symbol_info_tick", lambda _symbol: SimpleNamespace(ask=100.0, bid=True), raising=False
    )
    with pytest.raises(ValueError, match="Invalid bid quote"):
        RiskManager().calculate_stop_loss_price("US100", mt5.ORDER_TYPE_SELL, 10.0)

    monkeypatch.setattr(
        mt5, "symbol_info_tick", lambda _symbol: SimpleNamespace(ask=0.0, bid=0.0), raising=False
    )
    with pytest.raises(ValueError, match="Invalid stop price"):
        RiskManager().calculate_stop_loss_price("US100", mt5.ORDER_TYPE_BUY, 10.0)


def test_sizing_rejects_invalid_absolute_cash_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mt5, "symbol_select", lambda *_args: True, raising=False)
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: _symbol_info(), raising=False)
    monkeypatch.setattr(
        mt5, "symbol_info_tick", lambda _symbol: SimpleNamespace(bid=99.9, ask=100.1), raising=False
    )
    monkeypatch.setattr(
        mt5, "account_info", lambda: SimpleNamespace(balance=100_000.0), raising=False
    )

    assert (
        RiskManager(risk_per_symbol_usd_cap=0.0).calculate_position_size(
            "US100", stop_loss_pips=10.0
        )
        == 0.0
    )


def test_risk_check_fails_closed_for_missing_symbol_and_bad_stop_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mt5, "account_info", lambda: SimpleNamespace(balance=100_000.0), raising=False
    )
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: None, raising=False)
    allowed, reason = RiskManager().check_risk_limits(
        "US100", proposed_position_size=1.0, stop_loss_pips=10.0
    )
    assert not allowed
    assert "not found" in reason

    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: _symbol_info(), raising=False)
    monkeypatch.setattr(mt5, "symbol_select", lambda *_args: False, raising=False)
    with pytest.raises(ValueError, match="not available"):
        RiskManager().calculate_stop_loss_price("MISSING", mt5.ORDER_TYPE_BUY, 10.0)

    invalid = _symbol_info()
    invalid.trade_tick_size = 0.0
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: invalid, raising=False)
    allowed, reason = RiskManager().check_risk_limits(
        "US100", proposed_position_size=1.0, stop_loss_pips=10.0
    )
    assert not allowed
    assert "Error checking risk limits" in reason


@pytest.mark.parametrize(
    ("atr", "base", "expected"),
    [("invalid", 1.0, 0.0), (1.0, 0.0, 1.0), (4.0, 1.0, 0.5), (0.01, 1.0, 2.0)],
)
def test_volatility_multiplier_handles_invalid_zero_and_clamped_values(
    atr: float | str, base: float, expected: float
) -> None:
    assert RiskManager().get_volatility_multiplier(cast(Any, atr), base) == pytest.approx(expected)
