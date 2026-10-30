"""MetaTrader-specific adapters, loaded only when an adapter is requested."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_PUBLIC_EXPORTS = {
    "MT5Data": ("integrations.mt5.domain.data_sources.mt5_data", "MT5Data"),
    "MT5Trader": ("integrations.mt5.domain.trader", "MT5Trader"),
    "RiskManager": ("integrations.mt5.domain.risk_manager", "RiskManager"),
    "ensure_mt5_logged_in": (
        "integrations.mt5.domain.mt5_connection",
        "ensure_mt5_logged_in",
    ),
}

__all__ = list(_PUBLIC_EXPORTS)


def __getattr__(name: str) -> Any:
    """Import platform-dependent implementations on explicit use only."""
    target = _PUBLIC_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, symbol_name = target
    value = getattr(import_module(module_name), symbol_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted((*globals(), *__all__))
