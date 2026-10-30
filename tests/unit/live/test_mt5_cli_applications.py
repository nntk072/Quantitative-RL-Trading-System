"""Contract tests for the canonical MT5 application entrypoints."""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# MT5's binary package is not available on Linux; imports are safe with a stub
# because these contract tests never initialize the terminal or place orders.
if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        sys.modules["MetaTrader5"] = ModuleType("MetaTrader5")
if not hasattr(sys.modules["MetaTrader5"], "ORDER_TYPE_BUY"):
    sys.modules["MetaTrader5"] = MagicMock()

import demo_trading  # noqa: E402
import live_trading  # noqa: E402

from integrations.mt5.cli import multi_symbol_trading, single_symbol_demo  # noqa: E402


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
