"""Contract tests for the Backtrader MACD baseline strategies."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import backtrader as bt
import pytest

from simulation.backtest.cross_validation.strategies import macd_strategy


class _Line:
    def __init__(self, values: dict[int, float] | float = 0.0) -> None:
        self.values = values if isinstance(values, dict) else {0: values}

    def __getitem__(self, index: int) -> float:
        return self.values[index]

    def __sub__(self, other: _Line) -> _Line:
        return _Line({index: value - other[index] for index, value in self.values.items()})


def _macd_strategy(*, histogram: float, position: bool = False, pending: Any = None) -> Any:
    return SimpleNamespace(
        dataclose=_Line(101.5),
        macd=SimpleNamespace(macd=_Line(histogram), signal=_Line(0.0)),
        order=pending,
        position=position,
        log=Mock(),
        buy=Mock(return_value="buy-order"),
        sell=Mock(return_value="sell-order"),
    )


def _ema_strategy(
    *,
    previous_macd: float,
    current_macd: float,
    previous_signal: float = 0.0,
    current_signal: float = 0.0,
    price: float = 101.0,
    ema: float = 100.0,
    position: int = 0,
    cooldown: int = 0,
    pending: Any = None,
) -> Any:
    return SimpleNamespace(
        dataclose=_Line(price),
        macd_line=_Line({-1: previous_macd, 0: current_macd}),
        signal_line=_Line({-1: previous_signal, 0: current_signal}),
        ema50=_Line(ema),
        position=position,
        cooldown_counter=cooldown,
        cooldown_bars=5,
        order=pending,
        log=Mock(),
        buy=Mock(return_value="buy-order"),
        sell=Mock(return_value="sell-order"),
        close=Mock(return_value="close-order"),
    )


def test_macd_initialization_uses_configured_periods(monkeypatch: pytest.MonkeyPatch) -> None:
    macd = Mock(return_value="indicator")
    monkeypatch.setattr(bt.indicators, "MACD", macd)
    instance: Any = SimpleNamespace(
        datas=[SimpleNamespace(close="close-series")],
        p=SimpleNamespace(fast=8, slow=21, signal_period=5),
    )

    macd_strategy.MACDStrategy.__init__(instance)

    macd.assert_called_once_with("close-series", period_me1=8, period_me2=21, period_signal=5)
    assert instance.dataclose == "close-series"
    assert instance.macd == "indicator"
    assert (instance.fast, instance.slow, instance.signal_period) == (8, 21, 5)
    assert instance.order is None
    assert instance.buyprice is None
    assert instance.buycomm is None


@pytest.mark.parametrize("histogram,position,expected", [(0.5, False, "buy"), (-0.5, True, "sell")])
def test_macd_strategy_enters_and_exits_on_histogram_sign(
    histogram: float, position: bool, expected: str
) -> None:
    instance = _macd_strategy(histogram=histogram, position=position)

    macd_strategy.MACDStrategy.next(instance)

    if expected == "buy":
        instance.buy.assert_called_once_with()
        instance.sell.assert_not_called()
        assert instance.order == "buy-order"
    else:
        instance.sell.assert_called_once_with()
        instance.buy.assert_not_called()
        assert instance.order == "sell-order"


@pytest.mark.parametrize("position,histogram", [(False, -0.5), (True, 0.5), (False, 0.0)])
def test_macd_strategy_holds_when_signal_does_not_change_position(
    position: bool, histogram: float
) -> None:
    instance = _macd_strategy(histogram=histogram, position=position)

    macd_strategy.MACDStrategy.next(instance)

    instance.buy.assert_not_called()
    instance.sell.assert_not_called()


def test_macd_strategy_does_not_submit_while_order_is_pending() -> None:
    instance = _macd_strategy(histogram=1.0, pending="working-order")

    macd_strategy.MACDStrategy.next(instance)

    instance.buy.assert_not_called()
    instance.sell.assert_not_called()
    assert instance.order == "working-order"


def test_macd_logging_is_silent_by_default_and_uses_data_date_when_enabled(
    capsys: pytest.CaptureFixture[str],
) -> None:
    instance: Any = SimpleNamespace(
        p=SimpleNamespace(printlog=False),
        datas=[SimpleNamespace(datetime=SimpleNamespace(date=lambda _offset: date(2026, 1, 2)))],
    )

    macd_strategy.MACDStrategy.log(instance, "quiet")
    assert capsys.readouterr().out == ""

    instance.p.printlog = True
    macd_strategy.MACDStrategy.log(instance, "visible")

    assert capsys.readouterr().out == "2026-01-02 visible\n"


@pytest.mark.parametrize(
    "timestamp,expected",
    [(date(2026, 2, 3), "2026-02-03 event\n"), ("broker-time", "broker-time event\n")],
)
def test_macd_logging_formats_explicit_date_or_string(
    capsys: pytest.CaptureFixture[str], timestamp: object, expected: str
) -> None:
    instance: Any = SimpleNamespace(p=SimpleNamespace(printlog=False))

    macd_strategy.MACDStrategy.log(instance, "event", dt=timestamp, doprint=True)

    assert capsys.readouterr().out == expected


@pytest.mark.parametrize("status", [1, 2])
def test_macd_order_notifications_keep_submitted_and_accepted_orders(status: int) -> None:
    instance: Any = SimpleNamespace(order="working-order", p=SimpleNamespace(printlog=False))
    order = SimpleNamespace(status=status, Submitted=1, Accepted=2, Completed=3)

    macd_strategy.MACDStrategy.notify_order(instance, order)

    assert instance.order == "working-order"


def test_macd_completed_buy_records_fill_and_clears_pending_order() -> None:
    instance: Any = SimpleNamespace(
        order="working-order", p=SimpleNamespace(printlog=False), log=Mock()
    )
    order = SimpleNamespace(
        status=3,
        Submitted=1,
        Accepted=2,
        Completed=3,
        Canceled=4,
        Margin=5,
        Rejected=6,
        executed=SimpleNamespace(price=101.25, value=101.25, comm=0.1),
        isbuy=lambda: True,
    )

    macd_strategy.MACDStrategy.notify_order(instance, order)

    assert instance.buyprice == 101.25
    assert instance.buycomm == 0.1
    assert instance.order is None
    instance.log.assert_called_once()


def test_macd_completed_sell_logs_fill_and_clears_pending_order() -> None:
    instance: Any = SimpleNamespace(
        order="working-order", p=SimpleNamespace(printlog=False), log=Mock()
    )
    order = SimpleNamespace(
        status=3,
        Submitted=1,
        Accepted=2,
        Completed=3,
        executed=SimpleNamespace(price=99.5, value=99.5, comm=0.2),
        isbuy=lambda: False,
    )

    macd_strategy.MACDStrategy.notify_order(instance, order)

    assert instance.order is None
    instance.log.assert_called_once()


@pytest.mark.parametrize("status", [4, 5, 6])
def test_macd_failed_orders_are_cleared_and_reported(status: int) -> None:
    instance: Any = SimpleNamespace(
        order="working-order", p=SimpleNamespace(printlog=False), log=Mock()
    )
    order = SimpleNamespace(
        status=status,
        Submitted=1,
        Accepted=2,
        Completed=3,
        Canceled=4,
        Margin=5,
        Rejected=6,
    )

    macd_strategy.MACDStrategy.notify_order(instance, order)

    assert instance.order is None
    instance.log.assert_called_once_with("Order Canceled/Margin/Rejected")


def test_macd_closed_trade_is_logged_but_open_trade_is_ignored() -> None:
    instance: Any = SimpleNamespace(p=SimpleNamespace(printlog=False), log=Mock())

    macd_strategy.MACDStrategy.notify_trade(
        instance, SimpleNamespace(isclosed=False, pnl=1.0, pnlcomm=0.8)
    )
    instance.log.assert_not_called()

    macd_strategy.MACDStrategy.notify_trade(
        instance, SimpleNamespace(isclosed=True, pnl=1.0, pnlcomm=0.8)
    )
    instance.log.assert_called_once_with("OPERATION PROFIT, GROSS: 1.00, NET: 0.80")


def test_macd_stop_reports_parameters_and_broker_value() -> None:
    instance: Any = SimpleNamespace(
        p=SimpleNamespace(fast=8, slow=21, signal_period=5),
        broker=SimpleNamespace(getvalue=lambda: 1050.0),
        log=Mock(),
    )

    macd_strategy.MACDStrategy.stop(instance)

    assert [call.args[0] for call in instance.log.call_args_list] == [
        "MACD Fast: 8, Slow: 21, Signal: 5",
        "(MACD Strategy) Ending Value: 1050.00",
    ]


def test_ema_macd_initialization_builds_indicators_and_resets_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exponential = Mock(side_effect=lambda data, period: _Line(float(period)))
    simple = Mock(return_value=_Line())
    monkeypatch.setattr(bt.indicators, "ExponentialMovingAverage", exponential)
    monkeypatch.setattr(bt.indicators, "SimpleMovingAverage", simple)
    instance: Any = SimpleNamespace(
        datas=[SimpleNamespace(close="close-series")],
        p=SimpleNamespace(fast=8, slow=21, signal_period=5, ema50_period=34, cooldown_bars=3),
    )

    macd_strategy.EMAMACDStrategy.__init__(instance)

    assert exponential.call_args_list[0].args == ("close-series",)
    assert exponential.call_args_list[0].kwargs == {"period": 8}
    assert exponential.call_args_list[1].kwargs == {"period": 21}
    assert exponential.call_args_list[2].kwargs == {"period": 34}
    simple.assert_called_once()
    assert (instance.fast, instance.slow, instance.signal_period) == (8, 21, 5)
    assert instance.ema50_period == 34
    assert instance.cooldown_bars == 3
    assert instance.order is None
    assert instance.position == 0
    assert instance.cooldown_counter == 0


@pytest.mark.parametrize(
    "timestamp,expected",
    [(date(2026, 2, 3), "2026-02-03 event\n"), ("broker-time", "broker-time event\n")],
)
def test_ema_macd_logging_formats_explicit_date_or_string(
    capsys: pytest.CaptureFixture[str], timestamp: object, expected: str
) -> None:
    instance: Any = SimpleNamespace(p=SimpleNamespace(printlog=False))

    macd_strategy.EMAMACDStrategy.log(instance, "event", dt=timestamp, doprint=True)

    assert capsys.readouterr().out == expected


def test_ema_macd_opens_long_only_on_bullish_cross_above_ema() -> None:
    instance = _ema_strategy(previous_macd=-0.1, current_macd=0.1)

    macd_strategy.EMAMACDStrategy.next(instance)

    instance.buy.assert_called_once_with()
    assert instance.order == "buy-order"
    assert instance.position == 1


def test_ema_macd_opens_short_only_on_bearish_cross_below_ema() -> None:
    instance = _ema_strategy(
        previous_macd=0.1,
        current_macd=-0.1,
        price=99.0,
    )

    macd_strategy.EMAMACDStrategy.next(instance)

    instance.sell.assert_called_once_with()
    assert instance.order == "sell-order"
    assert instance.position == -1


@pytest.mark.parametrize("position,previous,current", [(1, 0.1, -0.1), (-1, -0.1, 0.1)])
def test_ema_macd_closes_position_on_opposite_cross_and_starts_cooldown(
    position: int, previous: float, current: float
) -> None:
    instance = _ema_strategy(
        previous_macd=previous,
        current_macd=current,
        position=position,
    )

    macd_strategy.EMAMACDStrategy.next(instance)

    instance.close.assert_called_once_with()
    assert instance.order == "close-order"
    assert instance.position == 0
    assert instance.cooldown_counter == 5


def test_ema_macd_cooldown_decrements_and_blocks_entry() -> None:
    instance = _ema_strategy(previous_macd=-0.1, current_macd=0.1, cooldown=2)

    macd_strategy.EMAMACDStrategy.next(instance)

    assert instance.cooldown_counter == 1
    instance.buy.assert_not_called()
    instance.sell.assert_not_called()


@pytest.mark.parametrize(
    "position,previous,current,price,ema",
    [
        (0, -0.1, -0.2, 101.0, 100.0),
        (0, 0.1, 0.2, 99.0, 100.0),
        (1, -0.1, 0.1, 101.0, 100.0),
        (-1, 0.1, -0.1, 99.0, 100.0),
    ],
)
def test_ema_macd_holds_when_price_or_cross_does_not_authorize_transition(
    position: int, previous: float, current: float, price: float, ema: float
) -> None:
    instance = _ema_strategy(
        previous_macd=previous,
        current_macd=current,
        price=price,
        ema=ema,
        position=position,
    )

    macd_strategy.EMAMACDStrategy.next(instance)

    assert instance.order is None
    instance.buy.assert_not_called()
    instance.sell.assert_not_called()
    instance.close.assert_not_called()


def test_ema_macd_pending_order_returns_after_cooldown_decrement() -> None:
    instance = _ema_strategy(
        previous_macd=-0.1,
        current_macd=0.1,
        cooldown=2,
        pending="working-order",
    )

    macd_strategy.EMAMACDStrategy.next(instance)

    assert instance.cooldown_counter == 1
    assert instance.order == "working-order"
    instance.buy.assert_not_called()


@pytest.mark.parametrize("status", [1, 2])
def test_ema_macd_order_notifications_keep_submitted_and_accepted_orders(status: int) -> None:
    instance: Any = SimpleNamespace(order="working-order", p=SimpleNamespace(printlog=False))
    order = SimpleNamespace(status=status, Submitted=1, Accepted=2, Completed=3)

    macd_strategy.EMAMACDStrategy.notify_order(instance, order)

    assert instance.order == "working-order"


@pytest.mark.parametrize("status", [4, 5, 6])
def test_ema_macd_failed_order_notification_clears_order(status: int) -> None:
    instance: Any = SimpleNamespace(
        order="working-order", p=SimpleNamespace(printlog=False), log=Mock()
    )
    order = SimpleNamespace(
        status=status,
        Submitted=1,
        Accepted=2,
        Completed=3,
        Canceled=4,
        Margin=5,
        Rejected=6,
    )

    macd_strategy.EMAMACDStrategy.notify_order(instance, order)

    assert instance.order is None
    instance.log.assert_called_once_with("Order Canceled/Margin/Rejected")


@pytest.mark.parametrize("is_buy,expected_position", [(True, 1), (False, 0)])
def test_ema_macd_completed_order_updates_position_and_clears_order(
    is_buy: bool, expected_position: int
) -> None:
    instance: Any = SimpleNamespace(
        order="working-order", position=0, p=SimpleNamespace(printlog=False), log=Mock()
    )
    order = SimpleNamespace(
        status=3,
        Submitted=1,
        Accepted=2,
        Completed=3,
        Canceled=4,
        Margin=5,
        Rejected=6,
        executed=SimpleNamespace(price=101.25, value=101.25, comm=0.1),
        isbuy=lambda: is_buy,
    )

    macd_strategy.EMAMACDStrategy.notify_order(instance, order)

    assert instance.position == expected_position
    assert instance.order is None
