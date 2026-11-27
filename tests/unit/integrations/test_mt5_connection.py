"""MT5 session setup is idempotent and fails closed on setup errors."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest

if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        sys.modules["MetaTrader5"] = ModuleType("MetaTrader5")

mt5 = cast(Any, sys.modules["MetaTrader5"])
if not hasattr(mt5, "TIMEFRAME_H1"):
    mt5.TIMEFRAME_H1 = 16385

from integrations.mt5.domain import mt5_connection  # noqa: E402


def test_existing_account_skips_reinitialization_and_login(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []
    monkeypatch.setattr(mt5, "terminal_info", lambda: object(), raising=False)
    monkeypatch.setattr(mt5, "initialize", lambda **kwargs: calls.append(kwargs), raising=False)
    monkeypatch.setattr(
        mt5,
        "account_info",
        lambda: SimpleNamespace(login=123),
        raising=False,
    )
    monkeypatch.setattr(mt5, "login", lambda **kwargs: calls.append(kwargs), raising=False)

    mt5_connection.ensure_mt5_logged_in(
        login="123",
        password="secret",  # pragma: allowlist secret
        server="demo",
        terminal_path="terminal",
    )

    assert calls == []


def test_uninitialized_terminal_is_initialized_before_requested_account_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(mt5, "terminal_info", lambda: None, raising=False)
    monkeypatch.setattr(
        mt5,
        "initialize",
        lambda **kwargs: _record_success(calls, "initialize", kwargs),
        raising=False,
    )
    monkeypatch.setattr(
        mt5,
        "account_info",
        lambda: SimpleNamespace(login=111),
        raising=False,
    )
    monkeypatch.setattr(
        mt5,
        "login",
        lambda **kwargs: _record_success(calls, "login", kwargs),
        raising=False,
    )

    mt5_connection.ensure_mt5_logged_in(
        login=222, password="secret", server="demo", terminal_path="terminal"
    )

    assert calls == [
        ("initialize", {"path": "terminal"}),
        ("login", {"login": 222, "password": "secret", "server": "demo"}),
    ]


def test_failed_terminal_initialization_stops_before_account_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(mt5, "terminal_info", lambda: None, raising=False)
    monkeypatch.setattr(mt5, "initialize", lambda **_kwargs: False, raising=False)
    monkeypatch.setattr(mt5, "last_error", lambda: "not found", raising=False)
    monkeypatch.setattr(mt5, "account_info", lambda: calls.append("account"), raising=False)

    with pytest.raises(RuntimeError, match="Failed to initialize MT5"):
        mt5_connection.ensure_mt5_logged_in(
            login=123, password="secret", server="demo", terminal_path="missing"
        )

    assert calls == []


def test_login_failure_reports_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(mt5, "terminal_info", lambda: object(), raising=False)
    monkeypatch.setattr(mt5, "account_info", lambda: None, raising=False)
    monkeypatch.setattr(
        mt5,
        "login",
        lambda **kwargs: _record_failure(calls, kwargs),
        raising=False,
    )
    monkeypatch.setattr(mt5, "last_error", lambda: "bad credentials", raising=False)

    with pytest.raises(RuntimeError, match="Failed to login to MT5"):
        mt5_connection.ensure_mt5_logged_in(
            login="456", password="secret", server="demo", terminal_path="terminal"
        )

    assert calls == [{"login": 456, "password": "secret", "server": "demo"}]


def test_non_numeric_login_is_rejected_before_account_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(mt5, "terminal_info", lambda: object(), raising=False)
    monkeypatch.setattr(mt5, "account_info", lambda: calls.append("account"), raising=False)

    with pytest.raises(ValueError, match="LOGIN must be an integer"):
        mt5_connection.ensure_mt5_logged_in(
            login="account-name", password="secret", server="demo", terminal_path="terminal"
        )

    assert calls == []


def _record_success(
    calls: list[tuple[str, dict[str, object]]], name: str, kwargs: dict[str, object]
) -> bool:
    calls.append((name, kwargs))
    return True


def _record_failure(calls: list[dict[str, object]], kwargs: dict[str, object]) -> bool:
    calls.append(kwargs)
    return False


def test_mt5_public_api_lazy_export_and_unknown_name_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import integrations.mt5 as mt5_package

    marker = object()
    previous = mt5_package.__dict__.pop("RiskManager", None)
    monkeypatch.setattr(
        mt5_package,
        "import_module",
        lambda module_name: (
            SimpleNamespace(RiskManager=marker)
            if module_name == "integrations.mt5.domain.risk_manager"
            else pytest.fail(f"unexpected module import: {module_name}")
        ),
    )
    try:
        assert mt5_package.__getattr__("RiskManager") is marker
        assert "RiskManager" in mt5_package.__dir__()
        assert mt5_package.__getattr__("RiskManager") is marker
        with pytest.raises(AttributeError, match="unknown"):
            mt5_package.__getattr__("unknown")
    finally:
        mt5_package.__dict__.pop("RiskManager", None)
        if previous is not None:
            mt5_package.__dict__["RiskManager"] = previous


def test_logging_configuration_falls_back_to_stdout_when_file_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from integrations.mt5 import logging_config

    calls: list[object] = []

    def add(target: object, **_kwargs: object) -> None:
        calls.append(target)
        if target != sys.stdout:
            raise PermissionError("read-only logs")

    warnings: list[str] = []

    def warning(message: str, *args: object) -> None:
        warnings.append(message.format(*args))

    monkeypatch.setattr(
        logging_config,
        "logger",
        SimpleNamespace(remove=lambda: calls.append("remove"), add=add, warning=warning),
    )
    log_path = tmp_path / "nested" / "application.log"

    logging_config.configure_logging(str(log_path))

    assert log_path.parent.is_dir()
    assert calls[0] == "remove"
    assert warnings == [f"Cannot write to {log_path}, falling back to stdout-only logging"]
