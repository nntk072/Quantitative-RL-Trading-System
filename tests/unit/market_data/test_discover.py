"""Behavior tests for broker-neutral symbol discovery utilities."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
import yaml

# MT5 is a Windows-only runtime dependency. Keep this CLI importable on CPU CI;
# augment any test-provided stub and replace every MT5 call before use.
_mt5_stub = sys.modules.get("MetaTrader5")
if _mt5_stub is None:
    _mt5_stub = ModuleType("MetaTrader5")
    sys.modules["MetaTrader5"] = _mt5_stub
for _name in ("initialize", "login", "symbols_get", "shutdown", "last_error"):
    if not hasattr(_mt5_stub, _name):
        setattr(_mt5_stub, _name, lambda *args, **kwargs: None)

from market_data.commands import discover  # noqa: E402

mt5: Any = vars(discover)["mt5"]


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [
        ("BTCUSD", "crypto"),
        ("XAUUSD", "commodities"),
        ("BRENT", "commodities"),
        ("COPPER", "commodities"),
        ("EURUSD", "forex"),
        ("USDSGD", "forex"),
        ("SPY", "etf"),
        ("BRK.B", "stocks"),
        ("US100IDX", "other"),
    ],
)
def test_categorize_symbol_uses_symbol_name_rules(symbol: str, expected: str) -> None:
    assert discover.categorize_symbol(symbol, "ignored description") == expected


def _symbol(
    name: str,
    *,
    description: str | None = "description",
    visible: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        description=description,
        visible=visible,
        currency_base="USD",
        currency_profit="EUR",
        trade_mode=4,
        digits=2,
        point=0.01,
        volume_min=0.1,
        volume_max=10.0,
        volume_step=0.1,
    )


def test_discover_symbols_categorizes_visible_symbols_and_shuts_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    records = [
        _symbol("BTCUSD", description=None),
        _symbol("EURUSD"),
        _symbol("US100IDX", visible=False),
        _symbol("GBPUSD"),
    ]

    def initialize(**kwargs: Any) -> bool:
        del kwargs
        calls.append("initialize")
        return True

    def login(**kwargs: Any) -> bool:
        del kwargs
        calls.append("login")
        return True

    monkeypatch.setattr(mt5, "initialize", initialize)
    monkeypatch.setattr(mt5, "login", login)
    monkeypatch.setattr(mt5, "symbols_get", lambda: records)
    monkeypatch.setattr(mt5, "shutdown", lambda: calls.append("shutdown"))

    result = discover.discover_symbols()

    assert [item["symbol"] for item in result["forex"]] == ["EURUSD", "GBPUSD"]
    assert result["crypto"] == [
        {
            "symbol": "BTCUSD",
            "description": "",
            "currency_base": "USD",
            "currency_profit": "EUR",
            "trade_mode": 4,
            "digits": 2,
            "point": 0.01,
            "volume_min": 0.1,
            "volume_max": 10.0,
            "volume_step": 0.1,
        }
    ]
    assert result["other"] == []
    assert calls == ["initialize", "login", "shutdown"]


@pytest.mark.parametrize(
    ("initialize_ok", "login_ok", "symbols", "expected_calls"),
    [
        (False, True, [], ["initialize"]),
        (True, False, [], ["initialize", "login", "shutdown"]),
        (True, True, None, ["initialize", "login", "shutdown"]),
    ],
)
def test_discover_symbols_fails_closed_and_shuts_down_when_initialized(
    monkeypatch: pytest.MonkeyPatch,
    initialize_ok: bool,
    login_ok: bool,
    symbols: list[Any] | None,
    expected_calls: list[str],
) -> None:
    calls: list[str] = []

    def initialize(**kwargs: Any) -> bool:
        del kwargs
        calls.append("initialize")
        return initialize_ok

    def login(**kwargs: Any) -> bool:
        del kwargs
        calls.append("login")
        return login_ok

    monkeypatch.setattr(mt5, "initialize", initialize)
    monkeypatch.setattr(mt5, "login", login)
    monkeypatch.setattr(mt5, "symbols_get", lambda: symbols)
    monkeypatch.setattr(mt5, "last_error", lambda: (1, "test error"))
    monkeypatch.setattr(mt5, "shutdown", lambda: calls.append("shutdown"))

    assert discover.discover_symbols() == {}
    assert calls == expected_calls


def test_print_symbols_shows_first_twenty_and_omits_empty_categories(
    capsys: pytest.CaptureFixture[str],
) -> None:
    symbols = [{"symbol": f"S{index:02d}", "description": "example"} for index in range(21)]

    discover.print_symbols(
        {"crypto": symbols, "forex": [{"symbol": "EURUSD", "description": "FX"}], "other": []}
    )

    output = capsys.readouterr().out
    assert "CRYPTO (21 symbols)" in output
    assert "S19" in output
    assert "S20" not in output
    assert "... and 1 more" in output
    assert "FOREX (1 symbols)" in output
    assert "OTHER (" not in output


def test_save_symbols_to_config_merges_nonempty_categories_and_creates_parent(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "nested" / "symbols.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        "symbol_categories:\n  forex: [OLD]\n  crypto: [BTCUSD]\nsettings:\n  enabled: true\n",
        encoding="utf-8",
    )

    discover.save_symbols_to_config(
        {
            "forex": [{"symbol": "EURUSD"}],
            "crypto": [],
            "etf": [{"symbol": "SPY"}],
        },
        str(config_path),
    )

    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert saved == {
        "symbol_categories": {"forex": ["EURUSD"], "crypto": ["BTCUSD"], "etf": ["SPY"]},
        "settings": {"enabled": True},
    }


def test_save_symbols_to_config_handles_empty_yaml_file(tmp_path: Path) -> None:
    config_path = tmp_path / "symbols.yaml"
    config_path.write_text("", encoding="utf-8")

    discover.save_symbols_to_config(
        {"forex": [{"symbol": "EURUSD"}], "crypto": []}, str(config_path)
    )

    assert yaml.safe_load(config_path.read_text(encoding="utf-8")) == {
        "symbol_categories": {"forex": ["EURUSD"]}
    }


def test_main_returns_when_credentials_are_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(discover, "LOGIN", None)
    monkeypatch.setattr(discover, "PASSWORD", "password")
    monkeypatch.setattr(discover, "SERVER", "server")
    was_called = False

    def fail_connect() -> dict[str, list[dict[str, Any]]]:
        nonlocal was_called
        was_called = True
        return {}

    monkeypatch.setattr(discover, "discover_symbols", fail_connect)

    discover.main()

    assert not was_called


def test_main_returns_when_discovery_has_no_symbols(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(discover, "LOGIN", "login")
    monkeypatch.setattr(discover, "PASSWORD", "password")
    monkeypatch.setattr(discover, "SERVER", "server")
    monkeypatch.setattr(discover, "discover_symbols", lambda: {})
    monkeypatch.setattr(discover, "repository_root", lambda _file: tmp_path)

    discover.main()

    assert not (tmp_path / "config" / "symbols_config.yaml").exists()


def test_main_persists_discovery_and_reports_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    symbols = {
        "forex": [{"symbol": "EURUSD", "description": "Euro"}],
        "crypto": [{"symbol": "BTCUSD", "description": "Bitcoin"}],
        "commodities": [],
        "etf": [],
        "stocks": [],
        "other": [],
    }
    monkeypatch.setattr(discover, "LOGIN", "login")
    monkeypatch.setattr(discover, "PASSWORD", "password")
    monkeypatch.setattr(discover, "SERVER", "server")
    monkeypatch.setattr(discover, "discover_symbols", lambda: symbols)
    monkeypatch.setattr(discover, "repository_root", lambda _file: tmp_path)

    discover.main()

    output = capsys.readouterr().out
    assert "SUMMARY: Discovered 2 tradeable symbols" in output
    assert "forex: 1 symbols" in output
    assert "crypto: 1 symbols" in output
    config = yaml.safe_load(
        (tmp_path / "config" / "symbols_config.yaml").read_text(encoding="utf-8")
    )
    assert config["symbol_categories"] == {"forex": ["EURUSD"], "crypto": ["BTCUSD"]}


def test_module_entrypoint_returns_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LOGIN", "PASSWORD", "SERVER"):
        monkeypatch.setenv(name, "")
    monkeypatch.setitem(sys.modules, "MetaTrader5", mt5)
    module_path = discover.__file__
    assert module_path is not None

    namespace = runpy.run_path(module_path, run_name="__main__")

    assert namespace["__name__"] == "__main__"
