"""Shared, lazily loaded primitives used by plotting families."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "BREACH_COLOR": (".rendering", "BREACH_COLOR"),
    "CLOSE_COLOR": (".rendering", "CLOSE_COLOR"),
    "EQUITY_COLOR": (".rendering", "EQUITY_COLOR"),
    "LONG_COLOR": (".rendering", "LONG_COLOR"),
    "PEAK_COLOR": (".rendering", "PEAK_COLOR"),
    "SHORT_COLOR": (".rendering", "SHORT_COLOR"),
    "STYLE": (".rendering", "STYLE"),
    "_CLOSE_TYPES": (".rendering", "_CLOSE_TYPES"),
    "_NOTE_FONT_PT": (".rendering", "_NOTE_FONT_PT"),
    "_LINE_KEYS": (".indicators", "_LINE_KEYS"),
    "_apply_style": (".rendering", "_apply_style"),
    "_save": (".rendering", "_save"),
    "_break_series_gaps": (".indicators", "_break_series_gaps"),
    "_date_key": (".series", "_date_key"),
    "_sma": (".indicators", "_sma"),
    "_with_rsi_vwap": (".indicators", "_with_rsi_vwap"),
    "apply_mpl_date_axis": (".series", "apply_mpl_date_axis"),
    "at_sample_extreme": (".levels", "at_sample_extreme"),
    "break_overlay_gaps": (".indicators", "break_overlay_gaps"),
    "chart_ylim": (".levels", "chart_ylim"),
    "compute_chart_overlays": (".indicators", "compute_chart_overlays"),
    "compute_chart_overlays_full": (".indicators", "compute_chart_overlays_full"),
    "compute_ema50": (".indicators", "compute_ema50"),
    "compute_macd_sma": (".indicators", "compute_macd_sma"),
    "compute_mtf_ema_overlays": (".indicators", "compute_mtf_ema_overlays"),
    "daily_drawdown_pct": (".series", "daily_drawdown_pct"),
    "daily_drawdown_usd": (".series", "daily_drawdown_usd"),
    "daily_loss_limit_series": (".series", "daily_loss_limit_series"),
    "daily_pnl": (".series", "daily_pnl"),
    "deviation_levels": (".levels", "deviation_levels"),
    "drawdown_ylim": (".series", "drawdown_ylim"),
    "isolated_spike_mask": (".levels", "isolated_spike_mask"),
    "level_near_candles": (".levels", "level_near_candles"),
    "max_drawdown_pct": (".series", "max_drawdown_pct"),
    "ohlc_ok_mask": (".levels", "ohlc_ok_mask"),
    "select_ema_overlays": (".indicators", "select_ema_overlays"),
    "session_start_equity": (".series", "session_start_equity"),
    "slice_overlays": (".indicators", "slice_overlays"),
    "tradable_mask": (".levels", "tradable_mask"),
    "wick_time": (".levels", "wick_time"),
}

__all__ = [
    "BREACH_COLOR",
    "CLOSE_COLOR",
    "EQUITY_COLOR",
    "LONG_COLOR",
    "PEAK_COLOR",
    "SHORT_COLOR",
    "STYLE",
    "apply_mpl_date_axis",
    "at_sample_extreme",
    "break_overlay_gaps",
    "chart_ylim",
    "compute_chart_overlays",
    "compute_chart_overlays_full",
    "compute_ema50",
    "compute_macd_sma",
    "compute_mtf_ema_overlays",
    "daily_drawdown_pct",
    "daily_drawdown_usd",
    "daily_loss_limit_series",
    "daily_pnl",
    "deviation_levels",
    "drawdown_ylim",
    "isolated_spike_mask",
    "level_near_candles",
    "max_drawdown_pct",
    "ohlc_ok_mask",
    "select_ema_overlays",
    "session_start_equity",
    "slice_overlays",
    "tradable_mask",
    "wick_time",
]


def __getattr__(name: str) -> Any:
    """Resolve a lazily exported shared plotting symbol.

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
