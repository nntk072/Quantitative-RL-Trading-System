"""Contract tests for the canonical MT5 application entrypoints."""

import runpy
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest

# MT5's binary package is not available on Linux; imports are safe with a stub
# because these contract tests never initialize the terminal or place orders.
if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        mt5_stub = ModuleType("MetaTrader5")
        cast(Any, mt5_stub).TIMEFRAME_H1 = 16385
        sys.modules["MetaTrader5"] = mt5_stub
if not hasattr(sys.modules["MetaTrader5"], "TIMEFRAME_H1"):
    cast(Any, sys.modules["MetaTrader5"]).TIMEFRAME_H1 = 16385
import demo_trading  # noqa: E402
import live_trading  # noqa: E402

from integrations.mt5.cli import multi_symbol_trading, single_symbol_demo  # noqa: E402


def test_multi_symbol_module_entrypoint_dispatches_main_without_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dotenv
    import loguru

    from integrations.mt5 import logging_config

    errors: list[str] = []
    fake_logger = SimpleNamespace(info=lambda *_args: None, exception=errors.append)
    monkeypatch.setattr(dotenv, "load_dotenv", lambda: None)
    monkeypatch.setattr(logging_config, "configure_logging", lambda: None)
    monkeypatch.setattr(loguru, "logger", fake_logger)
    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setattr(sys, "argv", ["multi_symbol_trading.py", "--once"])
    script = Path(__file__).resolve().parents[3] / "integrations/mt5/cli/multi_symbol_trading.py"

    with pytest.raises(RuntimeError, match="paper-only"):
        runpy.run_path(str(script), run_name="__main__")

    assert errors and "paper-only" in errors[0]


def test_single_symbol_module_entrypoint_dispatches_main_without_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dotenv
    import loguru

    from integrations.mt5 import logging_config
    from integrations.mt5.domain import mt5_connection

    errors: list[str] = []
    fake_logger = SimpleNamespace(info=lambda *_args: None, exception=errors.append)
    monkeypatch.setattr(dotenv, "load_dotenv", lambda: None)
    monkeypatch.setattr(logging_config, "configure_logging", lambda: None)
    monkeypatch.setattr(loguru, "logger", fake_logger)
    monkeypatch.setattr(
        mt5_connection,
        "ensure_mt5_logged_in",
        lambda **_kwargs: pytest.fail("entrypoint must reject real mode before MT5 login"),
    )
    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setattr(sys, "argv", ["single_symbol_demo.py", "--once"])
    script = Path(__file__).resolve().parents[3] / "integrations/mt5/cli/single_symbol_demo.py"

    runpy.run_path(str(script), run_name="__main__")

    assert errors and "paper-only" in errors[0]


def test_legacy_demo_entrypoint_forwards_to_application() -> None:
    assert demo_trading.get_robot is single_symbol_demo.get_robot
    assert demo_trading.run_job is single_symbol_demo.run_job
    assert demo_trading.main.__module__ == "demo_trading"


def test_legacy_multi_symbol_entrypoint_forwards_to_application() -> None:
    assert live_trading.load_config.__module__ == multi_symbol_trading.__name__
    assert live_trading.initialize_trading_system.__module__ == multi_symbol_trading.__name__
    assert live_trading.TradingSystem.__module__ == multi_symbol_trading.__name__
    assert live_trading.PAPER_TRADING is multi_symbol_trading.PAPER_TRADING


def test_multi_symbol_config_path_is_repository_relative() -> None:
    config = multi_symbol_trading.load_config()

    assert config
    assert Path("config/symbols_config.yaml").is_file()
    assert "symbol_categories" in config


def test_symbol_candidates_keep_configured_order_and_remove_duplicates() -> None:
    config = {"symbol_categories": {"major": ["US100", "US500"], "other": ["US100"]}}

    assert multi_symbol_trading.get_symbol_candidates(config) == ["US100", "US500"]


def test_demo_once_option_runs_one_cycle_without_starting_scheduler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(single_symbol_demo, "run_job", lambda: calls.append("cycle"))
    monkeypatch.setattr(
        single_symbol_demo,
        "start_scheduler",
        lambda: (_ for _ in ()).throw(AssertionError("scheduler must not start")),
    )
    monkeypatch.setattr(sys, "argv", ["demo_trading.py", "--once"])

    single_symbol_demo.main()

    assert calls == ["cycle"]


def test_single_symbol_demo_rejects_real_mode_before_mt5_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login_calls: list[bool] = []
    monkeypatch.setattr(single_symbol_demo, "_cross_over_robot", None)
    monkeypatch.setattr(single_symbol_demo, "paper_trading", False)
    monkeypatch.setattr(
        single_symbol_demo,
        "ensure_mt5_logged_in",
        lambda **_kwargs: login_calls.append(True),
    )

    with pytest.raises(RuntimeError, match="paper-only"):
        single_symbol_demo.get_robot()

    assert login_calls == []


def test_multi_symbol_app_rejects_real_mode_before_loading_or_mt5_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_calls: list[bool] = []
    monkeypatch.setattr(multi_symbol_trading, "PAPER_TRADING", False)
    monkeypatch.setattr(
        multi_symbol_trading,
        "load_config",
        lambda: config_calls.append(True),
    )

    with pytest.raises(RuntimeError, match="paper-only"):
        multi_symbol_trading.initialize_trading_system()

    assert config_calls == []


def test_multi_symbol_once_option_is_forwarded_to_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []
    monkeypatch.setattr(
        multi_symbol_trading.TradingSystem,
        "start",
        lambda _self, *, once: calls.append(once),
    )
    monkeypatch.setattr(sys, "argv", ["live_trading.py", "--once"])

    multi_symbol_trading.main()

    assert calls == [True]


def test_single_symbol_demo_builds_and_caches_paper_robot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    robots: list[object] = []

    class Data:
        def __init__(self, symbol: str, timeframe: int) -> None:
            calls.append(("data", symbol, timeframe))

    class Strategy:
        def __init__(self, data: object) -> None:
            calls.append(("strategy", data))

    class Trader:
        def __init__(self) -> None:
            calls.append("trader")

    class Robot:
        def __init__(self, *args: object, **kwargs: object) -> None:
            calls.append(("robot", args, kwargs))
            robots.append(self)

    monkeypatch.setattr(single_symbol_demo, "_cross_over_robot", None)
    monkeypatch.setattr(single_symbol_demo, "paper_trading", True)
    monkeypatch.setattr(
        single_symbol_demo, "ensure_mt5_logged_in", lambda **_kwargs: calls.append("login")
    )
    monkeypatch.setattr(single_symbol_demo, "MT5Data", Data)
    monkeypatch.setattr(single_symbol_demo, "CrossOverStrategy", Strategy)
    monkeypatch.setattr(single_symbol_demo, "MT5Trader", Trader)
    monkeypatch.setattr(single_symbol_demo, "CrossOverRobot", Robot)

    first = single_symbol_demo.get_robot()
    assert first is single_symbol_demo.get_robot()
    assert first is robots[0]
    assert calls[0] == "login"
    assert len(calls) == 5


def test_single_symbol_demo_run_job_trades_and_contains_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    traded: list[str] = []
    errors: list[str] = []
    monkeypatch.setattr(
        single_symbol_demo,
        "logger",
        SimpleNamespace(info=lambda *_args: None, exception=errors.append),
    )
    monkeypatch.setattr(
        single_symbol_demo,
        "get_robot",
        lambda: SimpleNamespace(trade=lambda: traded.append("trade")),
    )

    single_symbol_demo.run_job()
    assert traded == ["trade"]

    monkeypatch.setattr(
        single_symbol_demo,
        "get_robot",
        lambda: (_ for _ in ()).throw(RuntimeError("robot unavailable")),
    )
    single_symbol_demo.run_job()
    assert errors and "robot unavailable" in errors[0]


def test_single_symbol_demo_scheduler_mode_stops_on_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(sys, "argv", ["demo_trading.py"])
    monkeypatch.setattr(single_symbol_demo, "run_job", lambda: calls.append("run"))
    monkeypatch.setattr(single_symbol_demo, "start_scheduler", lambda: calls.append("schedule"))
    monkeypatch.setattr(
        cast(Any, single_symbol_demo).time,
        "sleep",
        lambda _seconds: (_ for _ in ()).throw(KeyboardInterrupt),
    )

    single_symbol_demo.main()

    assert calls == ["run", "schedule"]
