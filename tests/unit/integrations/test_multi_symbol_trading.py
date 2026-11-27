"""Behavior contracts for the multi-symbol MT5 application, without a terminal."""

from __future__ import annotations

import importlib
import sys
from io import StringIO
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest

if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        sys.modules["MetaTrader5"] = ModuleType("MetaTrader5")

mt5 = cast(Any, sys.modules["MetaTrader5"])
for _name, _value in {
    "TIMEFRAME_M1": 1,
    "TIMEFRAME_M5": 5,
    "TIMEFRAME_M15": 15,
    "TIMEFRAME_M30": 30,
    "TIMEFRAME_H1": 60,
    "TIMEFRAME_H4": 240,
    "TIMEFRAME_D1": 1440,
}.items():
    if not hasattr(mt5, _name):
        setattr(mt5, _name, _value)

from integrations.mt5.cli import multi_symbol_trading as app  # noqa: E402


def test_multi_symbol_manager_registers_selected_sources_and_skips_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager_module = importlib.import_module("integrations.mt5.domain.multi_symbol_manager")
    sources: dict[str, object] = {}
    selected = {"US100": True, "US500": False}
    monkeypatch.setattr(manager_module, "ensure_mt5_logged_in", lambda **_kwargs: None)
    monkeypatch.setattr(mt5, "symbol_select", lambda symbol, _enable: selected[symbol])
    monkeypatch.setattr(mt5, "shutdown", lambda: None, raising=False)

    class DataSource:
        def __init__(self, symbol: str, timeframe: int) -> None:
            sources[symbol] = (symbol, timeframe)

    monkeypatch.setattr(manager_module, "MT5Data", DataSource)
    manager = manager_module.MultiSymbolManager(
        login="login",
        server="server",
        password="password",
        terminal_path="terminal",
        symbols=["US100", "US500"],
        timeframe=mt5.TIMEFRAME_M5,
    )

    assert manager.get_active_symbols() == ["US100"]
    assert sources == {"US100": ("US100", mt5.TIMEFRAME_M5)}
    assert manager.get_data_source("US500") is None


def test_multi_symbol_manager_adds_and_removes_symbol_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager_module = importlib.import_module("integrations.mt5.domain.multi_symbol_manager")
    monkeypatch.setattr(manager_module, "ensure_mt5_logged_in", lambda **_kwargs: None)
    monkeypatch.setattr(mt5, "symbol_select", lambda _symbol, _enable: True)
    monkeypatch.setattr(mt5, "shutdown", lambda: None, raising=False)

    class DataSource:
        def __init__(self, symbol: str, timeframe: int) -> None:
            self.symbol = symbol
            self.timeframe = timeframe

    monkeypatch.setattr(manager_module, "MT5Data", DataSource)
    manager = manager_module.MultiSymbolManager(
        login="login",
        server="server",
        password="password",
        terminal_path="terminal",
        symbols=[],
        timeframe=mt5.TIMEFRAME_M1,
    )

    assert manager.add_symbol("US100") is True
    assert manager.add_symbol("US100") is True
    assert manager.symbols == ["US100"]
    assert manager.get_data_source("US100").timeframe == mt5.TIMEFRAME_M1
    manager.volatility_metrics["US100"] = {"atr": 3.0}
    assert manager.remove_symbol("US100") is True
    assert manager.get_active_symbols() == []
    assert manager.get_volatility_metrics("US100") is None
    assert manager.remove_symbol("US100") is False


def test_multi_symbol_manager_updates_only_available_volatility_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager_module = importlib.import_module("integrations.mt5.domain.multi_symbol_manager")
    monkeypatch.setattr(manager_module, "ensure_mt5_logged_in", lambda **_kwargs: None)
    monkeypatch.setattr(mt5, "symbol_select", lambda _symbol, _enable: True)
    monkeypatch.setattr(mt5, "shutdown", lambda: None, raising=False)
    monkeypatch.setattr(manager_module, "MT5Data", lambda *_args: object())
    manager = manager_module.MultiSymbolManager(
        login="login",
        server="server",
        password="password",
        terminal_path="terminal",
        symbols=["US100", "US500", "EURUSD"],
    )

    class Analyzer:
        def calculate_volatility_metrics(self, symbol: str, _timeframe: int) -> Any:
            if symbol == "US100":
                return {"atr": 2.0}
            if symbol == "EURUSD":
                raise RuntimeError("market data unavailable")
            return {}

    manager.update_volatility_metrics(Analyzer())

    assert manager.get_volatility_metrics("US100") == {"atr": 2.0}
    assert manager.get_volatility_metrics("US500") is None
    assert manager.get_volatility_metrics("EURUSD") is None


def test_multi_symbol_manager_returns_independent_snapshots_and_contains_add_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager_module = importlib.import_module("integrations.mt5.domain.multi_symbol_manager")
    monkeypatch.setattr(manager_module, "ensure_mt5_logged_in", lambda **_kwargs: None)
    monkeypatch.setattr(mt5, "symbol_select", lambda _symbol, _enable: True)
    monkeypatch.setattr(mt5, "shutdown", lambda: None, raising=False)
    monkeypatch.setattr(manager_module, "MT5Data", lambda *_args: object())
    manager = manager_module.MultiSymbolManager(
        login="login",
        server="server",
        password="password",
        terminal_path="terminal",
        symbols=["US100"],
    )
    manager.volatility_metrics["US100"] = {"score": 1.2}

    data_sources = manager.get_all_data_sources()
    metrics = manager.get_all_volatility_metrics()
    data_sources.clear()
    metrics.clear()
    manager.refresh_data()

    assert manager.get_active_symbols() == ["US100"]
    assert manager.get_all_volatility_metrics() == {"US100": {"score": 1.2}}

    class BrokenDataSource:
        def __init__(self, *_args: Any) -> None:
            raise RuntimeError("data source unavailable")

    monkeypatch.setattr(manager_module, "MT5Data", BrokenDataSource)
    assert manager.add_symbol("US500") is False
    assert manager.get_active_symbols() == ["US100"]


@pytest.mark.parametrize(
    ("strategy_type", "factory_name"),
    [
        ("crossover", "CrossOverStrategy"),
        ("smc", "SMCStrategy"),
        ("trend_breakout", "TrendBreakoutStrategy"),
        ("combined", "CombinedStrategy"),
        ("unknown", "CombinedStrategy"),
    ],
)
def test_create_strategy_selects_configured_factory_and_falls_back_to_combined(
    monkeypatch: pytest.MonkeyPatch, strategy_type: str, factory_name: str
) -> None:
    source = object()
    strategy = object()
    calls: list[Any] = []

    for name in ("CrossOverStrategy", "SMCStrategy", "TrendBreakoutStrategy", "CombinedStrategy"):

        def build(received_source: Any, *, _name: str = name) -> object:
            calls.append((_name, received_source))
            return strategy

        monkeypatch.setattr(app, name, build)

    result = app.create_strategy(cast(Any, source), strategy_type)

    assert result is strategy
    assert calls == [(factory_name, source)]


def test_select_volatile_symbols_uses_configured_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    selected = ["US100"]
    calls: list[dict[str, Any]] = []

    class Analyzer:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def select_top_volatile_symbols(self, **kwargs: Any) -> list[str]:
            calls.append(kwargs)
            return selected

    monkeypatch.setattr(app, "VolatilityAnalyzer", Analyzer)
    monkeypatch.setattr(
        app, "load_config", lambda: {"volatility_config": {"min_volatility_threshold": 1.25}}
    )

    assert app.select_volatile_symbols(["US100", "US500"], max_symbols=1) == selected
    assert calls == [
        {"symbols": ["US100", "US500"], "max_symbols": 1, "min_volatility_threshold": 1.25}
    ]


def test_select_volatile_symbols_falls_back_to_input_order_after_analyzer_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Analyzer:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def select_top_volatile_symbols(self, **_kwargs: Any) -> list[str]:
            raise RuntimeError("terminal unavailable")

    monkeypatch.setattr(app, "VolatilityAnalyzer", Analyzer)
    monkeypatch.setattr(app, "load_config", lambda: {})

    assert app.select_volatile_symbols(["US100", "US500", "EURUSD"], max_symbols=2) == [
        "US100",
        "US500",
    ]


@pytest.mark.parametrize(
    ("config", "selection", "error"),
    [
        ({}, ["US100"], "No symbols configured"),
        ({"symbol_categories": {"major": ["US100"]}}, [], "Failed to select symbols"),
    ],
)
def test_initialize_trading_system_fails_closed_without_candidates_or_selection(
    monkeypatch: pytest.MonkeyPatch, config: dict[str, Any], selection: list[str], error: str
) -> None:
    monkeypatch.setattr(app, "PAPER_TRADING", True)
    monkeypatch.setattr(app, "load_config", lambda: config)
    monkeypatch.setattr(app, "select_volatile_symbols", lambda *_args: selection)

    with pytest.raises(ValueError, match=error):
        app.initialize_trading_system()


def test_initialize_trading_system_builds_paper_robot_from_available_symbol_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = {
        "symbol_categories": {"major": ["US100", "US500"]},
        "volatility_config": {"timeframe": "M5"},
        "trading_config": {"risk_per_symbol": 0.01, "max_total_risk": 0.03},
    }
    manager_calls: dict[str, Any] = {}
    data_sources = {"US100": object(), "US500": None}
    analyzer = object()
    trader = object()
    risk_manager = object()
    robot = object()

    class Manager:
        def __init__(self, **kwargs: Any) -> None:
            manager_calls["init"] = kwargs
            manager_calls["instance"] = self

        def update_volatility_metrics(self, received: Any) -> None:
            manager_calls["analyzer"] = received

        def get_data_source(self, symbol: str) -> Any:
            return data_sources[symbol]

    monkeypatch.setattr(app, "PAPER_TRADING", True)
    monkeypatch.setattr(app, "load_config", lambda: config)
    monkeypatch.setattr(app, "select_volatile_symbols", lambda *_args: ["US100", "US500"])
    monkeypatch.setattr(app, "MultiSymbolManager", Manager)
    monkeypatch.setattr(app, "VolatilityAnalyzer", lambda **_kwargs: analyzer)
    monkeypatch.setattr(app, "create_strategy", lambda source, _kind: ("strategy", source))

    def build_risk_manager(**kwargs: Any) -> object:
        manager_calls["risk"] = kwargs
        return risk_manager

    monkeypatch.setattr(app, "RiskManager", build_risk_manager)
    monkeypatch.setattr(app, "MT5Trader", lambda: trader)

    def build_robot(**kwargs: Any) -> object:
        manager_calls["robot"] = kwargs
        return robot

    monkeypatch.setattr(app, "MultiSymbolRobot", build_robot)

    result = app.initialize_trading_system()

    assert result is robot
    assert manager_calls["init"]["symbols"] == ["US100", "US500"]
    assert manager_calls["init"]["timeframe"] == mt5.TIMEFRAME_M5
    assert manager_calls["analyzer"] is analyzer
    assert manager_calls["risk"] == {"risk_per_symbol": 0.01, "max_total_risk": 0.03}
    assert manager_calls["robot"] == {
        "symbol_manager": manager_calls["instance"],
        "trader": trader,
        "strategies": {"US100": ("strategy", data_sources["US100"])},
        "risk_manager": risk_manager,
        "paper_trading": True,
    }


def test_initialize_trading_system_uses_default_timeframe_for_unknown_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager_calls: list[dict[str, Any]] = []
    robot = object()

    class Manager:
        def __init__(self, **kwargs: Any) -> None:
            manager_calls.append(kwargs)

        def update_volatility_metrics(self, _analyzer: Any) -> None:
            pass

        def get_data_source(self, _symbol: str) -> None:
            return None

    monkeypatch.setattr(app, "PAPER_TRADING", True)
    monkeypatch.setattr(
        app,
        "load_config",
        lambda: {
            "symbol_categories": {"major": ["US100"]},
            "volatility_config": {"timeframe": "W1"},
        },
    )
    monkeypatch.setattr(app, "select_volatile_symbols", lambda *_args: ["US100"])
    monkeypatch.setattr(app, "MultiSymbolManager", Manager)
    monkeypatch.setattr(app, "VolatilityAnalyzer", lambda **_kwargs: object())
    monkeypatch.setattr(app, "RiskManager", lambda **_kwargs: object())
    monkeypatch.setattr(app, "MT5Trader", lambda: object())
    monkeypatch.setattr(app, "MultiSymbolRobot", lambda **_kwargs: robot)

    assert app.initialize_trading_system() is robot
    assert manager_calls[0]["timeframe"] == mt5.TIMEFRAME_H1


def test_trading_cycle_is_noop_without_robot_and_trades_then_reports_status() -> None:
    system = app.TradingSystem()
    system.run_trading_cycle()

    calls: list[str] = []
    cast(Any, system).robot_instance = SimpleNamespace(
        trade=lambda: calls.append("trade"),
        get_status=lambda: {"total_positions": 2, "total_profit": 12.5},
    )
    system.run_trading_cycle()

    assert calls == ["trade"]


def test_trading_cycle_logs_robot_failures_without_escaping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    errors: list[str] = []
    monkeypatch.setattr(
        app,
        "logger",
        SimpleNamespace(
            info=lambda *_args: None,
            error=lambda *_args: None,
            exception=lambda message: errors.append(message),
        ),
    )
    system = app.TradingSystem()
    cast(Any, system).robot_instance = SimpleNamespace(
        trade=lambda: (_ for _ in ()).throw(RuntimeError("trade failed"))
    )

    system.run_trading_cycle()

    assert errors and "trade failed" in errors[0]


def test_schedule_trading_runs_cycle_and_schedules_next_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = app.TradingSystem()
    scheduled: list[tuple[int, int, Any]] = []
    calls: list[str] = []
    monkeypatch.setattr(app, "TRADING_INTERVAL_MINUTES", 7)
    monkeypatch.setattr(system, "run_trading_cycle", lambda: calls.append("cycle"))
    cast(Any, system).scheduler = SimpleNamespace(
        enter=lambda delay, priority, action: scheduled.append((delay, priority, action))
    )

    system.schedule_trading()

    assert calls == ["cycle"]
    assert scheduled == [(420, 1, system.schedule_trading)]


def test_start_scheduler_starts_daemon_worker_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    system = app.TradingSystem()
    scheduler_calls: list[tuple[int, int, Any]] = []
    cast(Any, system).scheduler = SimpleNamespace(
        enter=lambda *args: scheduler_calls.append(args), run=lambda: None
    )
    thread_calls: dict[str, Any] = {}

    class Thread:
        def __init__(self, **kwargs: Any) -> None:
            thread_calls.update(kwargs)

        def start(self) -> None:
            thread_calls["started"] = True

    monkeypatch.setattr(cast(Any, app).threading, "Thread", Thread)

    thread = cast(Any, system.start_scheduler())

    assert thread_calls == {
        "target": system.scheduler.run,
        "daemon": True,
        "started": True,
    }
    assert scheduler_calls == [(0, 1, system.schedule_trading)]
    assert thread is not None


def test_start_once_runs_initial_cycle_without_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    system = app.TradingSystem()
    cycle_calls: list[str] = []
    monkeypatch.setattr(app, "initialize_trading_system", lambda: object())
    monkeypatch.setattr(system, "run_trading_cycle", lambda: cycle_calls.append("cycle"))
    monkeypatch.setattr(
        system, "start_scheduler", lambda: pytest.fail("once mode must not schedule")
    )

    system.start(once=True)

    assert cycle_calls == ["cycle"]


def test_start_scheduler_mode_stops_cleanly_on_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = app.TradingSystem()
    monkeypatch.setattr(app, "initialize_trading_system", lambda: object())
    monkeypatch.setattr(system, "run_trading_cycle", lambda: None)
    monkeypatch.setattr(system, "start_scheduler", lambda: None)
    monkeypatch.setattr(
        cast(Any, app).time, "sleep", lambda _seconds: (_ for _ in ()).throw(KeyboardInterrupt)
    )

    system.start()


def test_start_reraises_initialization_failure_after_logging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    errors: list[str] = []
    monkeypatch.setattr(
        app,
        "logger",
        SimpleNamespace(exception=lambda message: errors.append(message)),
    )
    monkeypatch.setattr(
        app,
        "initialize_trading_system",
        lambda: (_ for _ in ()).throw(RuntimeError("initialization failed")),
    )

    with pytest.raises(RuntimeError, match="initialization failed"):
        app.TradingSystem().start(once=True)

    assert errors and "initialization failed" in errors[0]


def test_load_config_returns_empty_mapping_when_repository_config_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MissingPath:
        def __init__(self, value: str) -> None:
            self.value = value

        def resolve(self) -> MissingPath:
            return self

        @property
        def parents(self) -> tuple[MissingPath, MissingPath, MissingPath, MissingPath]:
            return (self, self, self, self)

        def __truediv__(self, _other: str) -> MissingPath:
            return self

        def exists(self) -> bool:
            return False

        def __str__(self) -> str:
            return "/repo/config/symbols_config.yaml"

    monkeypatch.setattr(app, "Path", MissingPath)

    assert app.load_config() == {}


def test_load_config_reads_yaml_and_normalizes_empty_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[str] = []

    class ConfigPath:
        def __init__(self, value: str) -> None:
            self.value = value

        def resolve(self) -> ConfigPath:
            return self

        @property
        def parents(self) -> tuple[ConfigPath, ConfigPath, ConfigPath, ConfigPath]:
            return (self, self, self, self)

        def __truediv__(self, _other: str) -> ConfigPath:
            return self

        def exists(self) -> bool:
            return True

        def __str__(self) -> str:
            return "/repo/config/symbols_config.yaml"

    monkeypatch.setattr(app, "Path", ConfigPath)

    def open_config(path: Any) -> StringIO:
        opened.append(str(path))
        return StringIO("")

    monkeypatch.setattr(app, "open", open_config, raising=False)
    monkeypatch.setattr(cast(Any, app).yaml, "safe_load", lambda _handle: None)

    assert app.load_config() == {}
    assert opened == ["/repo/config/symbols_config.yaml"]
