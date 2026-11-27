"""Boundary behavior for MT5 symbol management and paper-only entrypoints."""

from __future__ import annotations

import importlib
import sys
import threading as threading_module
from types import ModuleType
from typing import Any, cast

import pandas as pd
import pytest

if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        sys.modules["MetaTrader5"] = ModuleType("MetaTrader5")

mt5 = cast(Any, sys.modules["MetaTrader5"])
for _name, _value in {
    "TIMEFRAME_H1": 16385,
    "ORDER_TYPE_BUY": 0,
    "ORDER_TYPE_SELL": 1,
}.items():
    if not hasattr(mt5, _name):
        setattr(mt5, _name, _value)

manager_module = importlib.import_module("integrations.mt5.domain.multi_symbol_manager")
from integrations.mt5.cli import single_symbol_demo  # noqa: E402
from integrations.mt5.domain.signal import Signal  # noqa: E402
from integrations.mt5.robot.cross_over_robot import CrossOverRobot  # noqa: E402


def _manager(monkeypatch: pytest.MonkeyPatch, symbols: list[str] | None = None) -> Any:
    monkeypatch.setattr(manager_module, "ensure_mt5_logged_in", lambda **_kwargs: None)
    monkeypatch.setattr(mt5, "symbol_select", lambda _symbol, _enabled: True, raising=False)
    monkeypatch.setattr(mt5, "shutdown", lambda: None, raising=False)
    monkeypatch.setattr(manager_module, "MT5Data", lambda symbol, timeframe: (symbol, timeframe))
    return manager_module.MultiSymbolManager(
        login="login",
        server="server",
        password="password",
        terminal_path="terminal",
        symbols=symbols or [],
        timeframe=cast(Any, mt5.TIMEFRAME_H1),
    )


def test_symbol_manager_records_source_and_construction_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected: list[str] = []
    monkeypatch.setattr(manager_module, "ensure_mt5_logged_in", lambda **_kwargs: None)
    monkeypatch.setattr(mt5, "shutdown", lambda: None, raising=False)

    def select(symbol: str, _enabled: bool) -> bool:
        selected.append(symbol)
        if symbol == "US500":
            raise RuntimeError("terminal disconnected")
        return symbol != "EURUSD"

    def build_source(symbol: str, _timeframe: int) -> object:
        if symbol == "US100":
            raise ValueError("fixture source failed")
        return object()

    monkeypatch.setattr(mt5, "symbol_select", select, raising=False)
    monkeypatch.setattr(manager_module, "MT5Data", build_source)

    manager = manager_module.MultiSymbolManager(
        login="login",
        server="server",
        password="password",
        terminal_path="terminal",
        symbols=["US100", "US500", "EURUSD"],
    )

    assert selected == ["US100", "US500", "EURUSD"]
    assert manager.get_active_symbols() == []
    assert manager.get_all_data_sources() == {}


def test_symbol_manager_add_failure_preserves_symbol_list(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager(monkeypatch)
    monkeypatch.setattr(mt5, "symbol_select", lambda *_args: False, raising=False)

    assert manager.add_symbol("US100") is False
    assert manager.symbols == []
    assert manager.get_data_source("US100") is None


def test_symbol_manager_remove_failure_is_reported_without_losing_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _manager(monkeypatch, ["US100"])

    class BrokenSources(dict[str, object]):
        def __delitem__(self, key: str) -> None:
            raise RuntimeError(f"cannot remove {key}")

    manager.data_sources = cast(Any, BrokenSources(manager.data_sources))

    assert manager.remove_symbol("US100") is False
    assert manager.symbols == ["US100"]
    assert manager.get_active_symbols() == ["US100"]


@pytest.mark.parametrize(
    ("signal", "counts", "expected_queries"),
    [
        (Signal.SELL, {mt5.ORDER_TYPE_BUY: 1}, [mt5.ORDER_TYPE_SELL, mt5.ORDER_TYPE_BUY]),
        (Signal.SELL, {mt5.ORDER_TYPE_SELL: 1}, [mt5.ORDER_TYPE_SELL, mt5.ORDER_TYPE_BUY]),
        (Signal.NONE, {}, []),
    ],
)
def test_crossover_paper_cycle_handles_sell_existing_positions_and_no_signal(
    signal: Signal,
    counts: dict[int, int],
    expected_queries: list[int],
) -> None:
    queries: list[int] = []
    writes: list[str] = []

    class Trader:
        def get_opened_positions(
            self, _symbol: str, position_type: int
        ) -> tuple[int, pd.DataFrame]:
            queries.append(position_type)
            return counts.get(position_type, 0), pd.DataFrame()

        def open_position(self, *_args: object, **_kwargs: object) -> None:
            writes.append("open")

        def close_positions(self, *_args: object, **_kwargs: object) -> None:
            writes.append("close")

    class Strategy:
        def signal(self) -> tuple[str, Signal]:
            return "US100", signal

    CrossOverRobot(volume=0.1, trader=cast(Any, Trader()), strategy=cast(Any, Strategy())).trade()

    assert queries == expected_queries
    assert writes == []


def test_single_symbol_scheduler_logs_cycle_errors_and_schedules_next_cycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    demo = single_symbol_demo
    scheduled: list[tuple[float, int, object]] = []
    monkeypatch.setattr(
        demo,
        "get_robot",
        lambda: (_ for _ in ()).throw(RuntimeError("terminal unavailable")),
    )
    monkeypatch.setattr(
        demo.scheduler,
        "enter",
        lambda delay, priority, action: scheduled.append((delay, priority, action)),
    )

    demo.schedule_hourly()

    assert len(scheduled) == 1
    assert scheduled[0][0:2] == (60 * 60, 1)
    assert scheduled[0][2] is demo.schedule_hourly


def test_single_symbol_start_scheduler_uses_daemon_thread_without_running_scheduler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: dict[str, Any] = {}

    class Thread:
        def __init__(self, *, target: object, daemon: bool) -> None:
            created.update(target=target, daemon=daemon)

        def start(self) -> None:
            created["started"] = True

    monkeypatch.setattr(single_symbol_demo.scheduler, "enter", lambda *_args: None)
    monkeypatch.setattr(threading_module, "Thread", Thread)

    single_symbol_demo.start_scheduler()

    assert created == {
        "target": single_symbol_demo.scheduler.run,
        "daemon": True,
        "started": True,
    }
