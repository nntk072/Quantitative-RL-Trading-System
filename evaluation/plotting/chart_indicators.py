"""Compatibility facade for chart indicator helpers."""

from .shared.indicators import (
    _LINE_KEYS,
    _break_series_gaps,
    _sma,
    _with_rsi_vwap,
    break_overlay_gaps,
    compute_chart_overlays,
    compute_chart_overlays_full,
    compute_ema50,
    compute_macd_sma,
    compute_mtf_ema_overlays,
    select_ema_overlays,
    slice_overlays,
)

__all__ = [
    "_LINE_KEYS",
    "_break_series_gaps",
    "_sma",
    "_with_rsi_vwap",
    "break_overlay_gaps",
    "compute_chart_overlays",
    "compute_chart_overlays_full",
    "compute_ema50",
    "compute_macd_sma",
    "compute_mtf_ema_overlays",
    "select_ema_overlays",
    "slice_overlays",
]
