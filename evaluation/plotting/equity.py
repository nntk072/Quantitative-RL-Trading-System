"""Compatibility facade for equity and drawdown charts."""

from .performance.equity import _draw_dd_panel, plot_drawdown, plot_equity_curve

__all__ = ["_draw_dd_panel", "plot_drawdown", "plot_equity_curve"]
