"""Static order chart APIs, loaded only when an exported name is requested."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "plot_price_with_orders": (".charts", "plot_price_with_orders"),
    "plot_per_trade_orders": (".charts", "plot_per_trade_orders"),
    "_plot_price_line_fallback": (".charts", "_plot_price_line_fallback"),
    "_per_trade_equity": (".charts", "_per_trade_equity"),
    "_candle_body_days": (".charts", "_candle_body_days"),
    "_axis_date_format": (".charts", "_axis_date_format"),
    "_close_time_label": (".charts", "_close_time_label"),
    "_trade_filename": (".charts", "_trade_filename"),
    "_position_events": (".charts", "_position_events"),
    "_position_pnl_from_fills": (".charts", "_position_pnl_from_fills"),
    "_clock_label": (".charts", "_clock_label"),
    "_draw_position_fills": (".charts", "_draw_position_fills"),
    "_draw_target_updates": (".charts", "_draw_target_updates"),
    "_extend_trade_window": (".window", "_extend_trade_window"),
    "_extract_window": (".window", "_extract_window"),
    "_structure_anchors": (".window", "_structure_anchors"),
}

__all__ = ["plot_per_trade_orders", "plot_price_with_orders"]


def __getattr__(name: str) -> Any:
    """Resolve a lazily exported order plotting symbol.

    Args:
        name: Public symbol requested by the caller.

    Returns:
        The symbol from its owning module.
    """
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """List public exports and already loaded attributes.

    Returns:
        Sorted names available from the package.
    """
    return sorted(set(globals()) | set(_EXPORTS))
