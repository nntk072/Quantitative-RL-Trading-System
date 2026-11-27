"""Contract tests for the legacy Backtrader cross-validation adapters."""

from __future__ import annotations

import runpy
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

import backtrader as bt
import pandas as pd
import pytest

from simulation.backtest.cross_validation import backtrader_runner
from simulation.backtest.cross_validation.strategies import cross_over, signal_following
from simulation.backtest.cross_validation.utils import data_loader


class _Line:
    def __init__(self, values: dict[int, float] | float = 0.0) -> None:
        self.values = values if isinstance(values, dict) else {0: values}

    def __getitem__(self, index: int) -> float:
        return self.values[index]


def _cross_over_instance(*, signal: float, position: bool = False, pending: Any = None) -> Any:
    return SimpleNamespace(
        datas=[
            SimpleNamespace(datetime=SimpleNamespace(date=lambda _offset: datetime(2026, 1, 2)))
        ],
        dataclose=_Line(101.5),
        crossover=signal,
        position=position,
        order=pending,
        params=SimpleNamespace(printlog=False, ma_short_period=8, ma_long_period=21),
        p=SimpleNamespace(ma_short_period=8, ma_long_period=21),
        broker=SimpleNamespace(getvalue=lambda: 1050.0),
        log=Mock(),
        buy=Mock(return_value="buy-order"),
        sell=Mock(return_value="sell-order"),
    )


@pytest.mark.parametrize("signal,position,expected", [(1, False, "buy"), (-1, True, "sell")])
def test_cross_over_strategy_trades_on_directional_cross(
    signal: float, position: bool, expected: str
) -> None:
    instance = _cross_over_instance(signal=signal, position=position)

    cross_over.CrossOverStrategy.next(instance)

    if expected == "buy":
        instance.buy.assert_called_once_with()
        assert instance.order == "buy-order"
    else:
        instance.sell.assert_called_once_with()
        assert instance.order == "sell-order"


def test_cross_over_strategy_holds_for_no_cross_or_pending_order() -> None:
    for instance in (
        _cross_over_instance(signal=0),
        _cross_over_instance(signal=1, pending="working-order"),
    ):
        cross_over.CrossOverStrategy.next(instance)
        instance.buy.assert_not_called()
        instance.sell.assert_not_called()


def test_cross_over_strategy_does_not_exit_long_on_bullish_cross() -> None:
    instance = _cross_over_instance(signal=1, position=True)

    cross_over.CrossOverStrategy.next(instance)

    instance.buy.assert_not_called()
    instance.sell.assert_not_called()


def test_cross_over_logging_respects_print_override(capsys: pytest.CaptureFixture[str]) -> None:
    instance = _cross_over_instance(signal=0)

    cross_over.CrossOverStrategy.log(instance, "quiet")
    assert capsys.readouterr().out == ""

    cross_over.CrossOverStrategy.log(instance, "forced", doprint=True)
    assert capsys.readouterr().out == "2026-01-02T00:00:00 forced\n"


def test_cross_over_initialization_constructs_indicators(monkeypatch: pytest.MonkeyPatch) -> None:
    sma = Mock(side_effect=["short", "long"])
    macd = Mock(return_value="macd")
    crossover = Mock(return_value="cross")
    monkeypatch.setattr(cast(Any, cross_over).bt.indicators, "SimpleMovingAverage", sma)
    monkeypatch.setattr(cast(Any, cross_over).bt.indicators, "MACD", macd)
    monkeypatch.setattr(cast(Any, cross_over).bt.indicators, "CrossOver", crossover)
    instance = SimpleNamespace(
        datas=[SimpleNamespace(close="close-series")],
        p=SimpleNamespace(ma_short_period=8, ma_long_period=21),
    )

    cast(Any, cross_over.CrossOverStrategy).__init__(instance)

    assert instance.dataclose == "close-series"
    assert (instance.ma_short, instance.ma_long, instance.macd, instance.crossover) == (
        "short",
        "long",
        "macd",
        "cross",
    )
    assert instance.order is None
    assert instance.buyprice is None
    assert instance.buycomm is None
    assert sma.call_args_list[0].kwargs == {"period": 8}
    assert sma.call_args_list[1].kwargs == {"period": 21}


@pytest.mark.parametrize("status", [1, 2])
def test_cross_over_pending_order_notifications_do_not_clear_order(status: int) -> None:
    instance = _cross_over_instance(signal=0, pending="working-order")
    order = SimpleNamespace(status=status, Submitted=1, Accepted=2, Completed=3)

    cross_over.CrossOverStrategy.notify_order(instance, order)

    assert instance.order == "working-order"


@pytest.mark.parametrize("is_buy,expected_price", [(True, 101.25), (False, None)])
def test_cross_over_completed_orders_log_execution_and_clear_pending(
    is_buy: bool, expected_price: float | None
) -> None:
    instance = _cross_over_instance(signal=0, pending="working-order")
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

    cross_over.CrossOverStrategy.notify_order(instance, order)

    assert instance.order is None
    if expected_price is not None:
        assert instance.buyprice == expected_price
        assert instance.buycomm == 0.1
    instance.log.assert_called_once()


@pytest.mark.parametrize("status", [4, 5, 6])
def test_cross_over_rejected_orders_clear_pending_marker(status: int) -> None:
    instance = _cross_over_instance(signal=0, pending="working-order")
    order = SimpleNamespace(
        status=status,
        Submitted=1,
        Accepted=2,
        Completed=3,
        Canceled=4,
        Margin=5,
        Rejected=6,
    )

    cross_over.CrossOverStrategy.notify_order(instance, order)

    assert instance.order is None
    instance.log.assert_called_once_with("Order Canceled/Margin/Rejected")


def test_cross_over_trade_and_stop_reporting() -> None:
    instance = _cross_over_instance(signal=0)
    cross_over.CrossOverStrategy.notify_trade(
        instance, SimpleNamespace(isclosed=False, pnl=1.0, pnlcomm=0.8)
    )
    instance.log.assert_not_called()
    cross_over.CrossOverStrategy.notify_trade(
        instance, SimpleNamespace(isclosed=True, pnl=1.0, pnlcomm=0.8)
    )
    assert instance.log.call_args.args[0] == "OPERATION PROFIT, GROSS: 1.00, NET: 0.80"

    instance.log.reset_mock()
    cross_over.CrossOverStrategy.stop(instance)
    assert [call.args[0] for call in instance.log.call_args_list] == [
        "MA Short Period: 8, MA Long Period: 21",
        "(MA Strategy) Ending Value: 1050.00",
    ]


@pytest.mark.parametrize(
    "action,method,order_value",
    [(1, "buy", "buy-order"), (-1, "sell", "sell-order"), (2, "close", "close-order")],
)
def test_signal_following_strategy_executes_entry_short_and_exit_actions(
    action: int, method: str, order_value: str
) -> None:
    instance = SimpleNamespace(
        order=None,
        bar_index=0,
        p=SimpleNamespace(actions=pd.Series([action])),
        buy=Mock(return_value="buy-order"),
        sell=Mock(return_value="sell-order"),
        close=Mock(return_value="close-order"),
    )

    cast(Any, signal_following.SignalFollowingStrategy).next(instance)

    getattr(instance, method).assert_called_once_with()
    assert instance.order == order_value
    assert instance.bar_index == 1


def test_signal_following_initialization_and_logging(capsys: pytest.CaptureFixture[str]) -> None:
    instance = SimpleNamespace(p=SimpleNamespace(printlog=False))
    cast(Any, signal_following.SignalFollowingStrategy).__init__(instance)

    assert instance.order is None
    assert instance.bar_index == 0
    cast(Any, signal_following.SignalFollowingStrategy).log(instance, "quiet")
    assert capsys.readouterr().out == ""

    instance.p.printlog = True
    instance.datas = [
        SimpleNamespace(datetime=SimpleNamespace(date=lambda _offset: datetime(2026, 1, 2)))
    ]
    cast(Any, signal_following.SignalFollowingStrategy).log(instance, "visible")
    assert capsys.readouterr().out == "2026-01-02T00:00:00 visible\n"


def test_signal_following_hold_action_advances_without_order() -> None:
    instance = SimpleNamespace(
        order=None,
        bar_index=0,
        p=SimpleNamespace(actions=pd.Series([0])),
        buy=Mock(),
        sell=Mock(),
        close=Mock(),
    )

    cast(Any, signal_following.SignalFollowingStrategy).next(instance)

    assert instance.order is None
    assert instance.bar_index == 1
    instance.buy.assert_not_called()
    instance.sell.assert_not_called()
    instance.close.assert_not_called()


@pytest.mark.parametrize("actions,index", [(None, 0), (pd.Series([1]), 1)])
def test_signal_following_strategy_advances_when_actions_are_absent_or_exhausted(
    actions: pd.Series | None, index: int
) -> None:
    instance = SimpleNamespace(order=None, bar_index=index, p=SimpleNamespace(actions=actions))

    cast(Any, signal_following.SignalFollowingStrategy).next(instance)

    assert instance.bar_index == index + 1
    assert instance.order is None


def test_signal_following_strategy_pending_order_advances_without_resubmitting() -> None:
    instance = SimpleNamespace(
        order="working-order", bar_index=0, p=SimpleNamespace(actions=pd.Series([1]))
    )

    cast(Any, signal_following.SignalFollowingStrategy).next(instance)

    assert instance.bar_index == 1
    assert instance.order == "working-order"


def test_signal_following_order_notification_logs_and_clears_completed_order() -> None:
    instance = SimpleNamespace(order="working-order", p=SimpleNamespace(printlog=False), log=Mock())
    order = SimpleNamespace(
        status=3,
        Submitted=1,
        Accepted=2,
        Completed=3,
        Canceled=4,
        Margin=5,
        Rejected=6,
        executed=SimpleNamespace(price=101.25),
        isbuy=lambda: True,
    )

    cast(Any, signal_following.SignalFollowingStrategy).notify_order(instance, order)

    assert instance.order is None
    instance.log.assert_called_once_with("BUY EXECUTED, Price: 101.25")


def test_signal_following_sell_fill_is_logged() -> None:
    instance = SimpleNamespace(order="working-order", p=SimpleNamespace(printlog=False), log=Mock())
    order = SimpleNamespace(
        status=3,
        Submitted=1,
        Accepted=2,
        Completed=3,
        Canceled=4,
        Margin=5,
        Rejected=6,
        executed=SimpleNamespace(price=99.5),
        isbuy=lambda: False,
    )

    cast(Any, signal_following.SignalFollowingStrategy).notify_order(instance, order)

    assert instance.order is None
    instance.log.assert_called_once_with("SELL EXECUTED, Price: 99.50")


@pytest.mark.parametrize("status", [4, 5, 6])
def test_signal_following_rejected_orders_clear_pending_marker(status: int) -> None:
    instance = SimpleNamespace(order="working-order", p=SimpleNamespace(printlog=False), log=Mock())
    order = SimpleNamespace(
        status=status,
        Submitted=1,
        Accepted=2,
        Completed=3,
        Canceled=4,
        Margin=5,
        Rejected=6,
    )

    cast(Any, signal_following.SignalFollowingStrategy).notify_order(instance, order)

    assert instance.order is None
    instance.log.assert_called_once_with("Order Canceled/Margin/Rejected")


def test_load_data_from_csv_parses_date_column(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "bars.csv"
    path.touch()
    frame = pd.DataFrame(
        {"date": ["2026-01-02"], "open": [1], "high": [2], "low": [0], "close": [1], "volume": [3]}
    )
    monkeypatch.setattr(cast(Any, data_loader).pd, "read_csv", lambda *_args, **_kwargs: frame)
    feed = Mock(return_value="feed")
    monkeypatch.setattr(cast(Any, data_loader).bt.feeds, "PandasData", feed)

    assert cast(Any, data_loader.load_data_from_csv)(path) == "feed"
    assert isinstance(frame.index, pd.DatetimeIndex)
    feed.assert_called_once()


def test_load_data_from_csv_parses_datetime_column_and_rejects_missing_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        cast(Any, data_loader.load_data_from_csv)(tmp_path / "missing.csv")

    path = tmp_path / "bars.csv"
    path.touch()
    frame = pd.DataFrame(
        {
            "datetime": ["2026-01-02"],
            "open": [1],
            "high": [2],
            "low": [0],
            "close": [1],
            "volume": [3],
        }
    )
    monkeypatch.setattr(cast(Any, data_loader).pd, "read_csv", lambda *_args, **_kwargs: frame)
    monkeypatch.setattr(
        cast(Any, data_loader).bt.feeds, "PandasData", lambda **kwargs: kwargs["dataname"]
    )

    assert isinstance(cast(Any, data_loader.load_data_from_csv)(path).index, pd.DatetimeIndex)


def test_download_data_from_yahoo_normalizes_dates_and_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    columns = pd.MultiIndex.from_tuples(
        [(name, "TEST") for name in ("Open", "High", "Low", "Close", "Volume")]
    )
    data = pd.DataFrame([[1, 2, 0, 1, 3]], columns=columns)
    download = Mock(return_value=data)
    feed = Mock(return_value="feed")
    monkeypatch.setattr(cast(Any, data_loader).yf, "download", download)
    monkeypatch.setattr(cast(Any, data_loader).bt.feeds, "PandasData", feed)

    result = cast(Any, data_loader.download_data_from_yahoo)("TEST", "2026-01-01", "2026-01-02")

    assert result == "feed"
    assert download.call_args.kwargs["start"] == datetime(2026, 1, 1)
    assert download.call_args.kwargs["end"] == datetime(2026, 1, 2)
    assert list(feed.call_args.kwargs["dataname"].columns) == [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]


def test_run_backtest_reports_analyzers_and_returns_cerebro(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    class Cerebro:
        def __init__(self) -> None:
            self.broker = SimpleNamespace(
                setcash=Mock(),
                setcommission=Mock(),
                getvalue=Mock(side_effect=[100_000.0, 101_000.0]),
            )
            self.adddata = Mock()
            self.addstrategy = Mock()
            self.addanalyzer = Mock()
            self.run = Mock(
                return_value=[
                    SimpleNamespace(
                        analyzers=SimpleNamespace(
                            sharpe=SimpleNamespace(get_analysis=lambda: {"sharperatio": 1.25}),
                            drawdown=SimpleNamespace(
                                get_analysis=lambda: {"max": {"drawdown": 2.0}}
                            ),
                            returns=SimpleNamespace(get_analysis=lambda: {"rtot": 0.01}),
                            trades=SimpleNamespace(
                                get_analysis=lambda: {
                                    "total": {"total": 4},
                                    "won": {"total": 3},
                                    "lost": {"total": 1},
                                }
                            ),
                        )
                    )
                ]
            )
            self.plot = Mock()

    cerebro = Cerebro()
    monkeypatch.setattr(cast(Any, backtrader_runner).bt, "Cerebro", lambda: cerebro)

    result = backtrader_runner.run_backtest("feed", strategy=bt.Strategy, stake=2)

    assert result is cerebro
    cerebro.adddata.assert_called_once_with("feed")
    cerebro.addstrategy.assert_called_once_with(bt.Strategy, stake=2)
    assert cerebro.addanalyzer.call_count == 4
    cerebro.plot.assert_called_once_with(style="candlestick")
    assert "Win Rate: 75.00%" in capsys.readouterr().out


@pytest.mark.parametrize("won,total", [(0, 0), (0, 3)])
def test_run_backtest_omits_win_rate_when_there_are_no_wins(
    monkeypatch: pytest.MonkeyPatch, capsys, won: int, total: int
) -> None:
    analyzer = SimpleNamespace(
        sharpe=SimpleNamespace(get_analysis=lambda: {}),
        drawdown=SimpleNamespace(get_analysis=lambda: {}),
        returns=SimpleNamespace(get_analysis=lambda: {}),
        trades=SimpleNamespace(
            get_analysis=lambda: {
                "total": {"total": total},
                "won": {"total": won},
                "lost": {"total": total},
            }
        ),
    )
    cerebro = SimpleNamespace(
        broker=SimpleNamespace(
            setcash=Mock(), setcommission=Mock(), getvalue=Mock(return_value=100_000.0)
        ),
        adddata=Mock(),
        addstrategy=Mock(),
        addanalyzer=Mock(),
        run=Mock(return_value=[SimpleNamespace(analyzers=analyzer)]),
        plot=Mock(),
    )
    monkeypatch.setattr(cast(Any, backtrader_runner).bt, "Cerebro", lambda: cerebro)

    backtrader_runner.run_backtest("feed")

    assert "Win Rate:" not in capsys.readouterr().out


@pytest.mark.parametrize("strategy", ["crossover", "macd", "ema_macd"])
def test_backtrader_cli_routes_strategy_and_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, strategy: str
) -> None:
    path = tmp_path / "bars.csv"
    path.touch()
    bars = pd.DataFrame(
        {"open": [1.0], "high": [2.0], "low": [0.0], "close": [1.0], "volume": [3]},
        index=pd.Index(["2026-01-02"]),
    )
    feed = SimpleNamespace(dataname=bars)
    load = Mock(return_value=feed)
    run = Mock()
    monkeypatch.setattr(backtrader_runner, "load_data_from_csv", load)
    monkeypatch.setattr(backtrader_runner, "run_backtest", run)
    baseline = Mock(return_value=pd.Series([0], index=bars.index))
    monkeypatch.setattr("trading.baselines.macd_ema50_baseline", baseline)

    assert backtrader_runner.main(["--data-path", str(path), "--strategy", strategy]) == 0

    load.assert_called_once_with(path)
    run.assert_called_once()
    if strategy == "crossover":
        assert run.call_args.kwargs["ma_short_period"] == 20
        assert run.call_args.kwargs["ma_long_period"] == 50
        baseline.assert_not_called()
    else:
        baseline.assert_called_once()
        assert run.call_args.kwargs["actions"].equals(pd.Series([0], index=bars.index))


def test_backtrader_cli_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="Data file not found"):
        backtrader_runner.main(["--data-path", str(tmp_path / "missing.csv")])


def test_legacy_cross_validation_module_entrypoint_delegates_to_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["simulation.backtest.cross_validation.main", "--data-path", str(tmp_path / "missing.csv")],
    )

    with pytest.raises(SystemExit, match="Data file not found"):
        runpy.run_module("simulation.backtest.cross_validation.main", run_name="__main__")
