"""Compatibility facade for shared plotting time-series helpers."""

from .shared.series import (
    _date_key,
    apply_mpl_date_axis,
    daily_drawdown_pct,
    daily_drawdown_usd,
    daily_loss_limit_series,
    daily_pnl,
    drawdown_ylim,
    max_drawdown_pct,
    session_start_equity,
)

__all__ = [
    "_date_key",
    "apply_mpl_date_axis",
    "daily_drawdown_pct",
    "daily_drawdown_usd",
    "daily_loss_limit_series",
    "daily_pnl",
    "drawdown_ylim",
    "max_drawdown_pct",
    "session_start_equity",
]
