"""Compatibility facade for static PO3 / IFVG signal charts."""

from .data.po3 import (
    ENTRY_LONG_COLOR,
    ENTRY_SHORT_COLOR,
    HTF_FVG_BEAR_COLOR,
    HTF_FVG_BULL_COLOR,
    LTF_IFVG_BEAR_COLOR,
    LTF_IFVG_BULL_COLOR,
    _candle_half_width,
    _draw_candles,
    _draw_entries,
    _draw_zones,
    _resample_ohlc,
    _snap_ts_to_candle_x,
    _zone_color,
    plot_annotated_ny_session,
    plot_fvg_signals,
)

__all__ = [
    "ENTRY_LONG_COLOR",
    "ENTRY_SHORT_COLOR",
    "HTF_FVG_BEAR_COLOR",
    "HTF_FVG_BULL_COLOR",
    "LTF_IFVG_BEAR_COLOR",
    "LTF_IFVG_BULL_COLOR",
    "_candle_half_width",
    "_draw_candles",
    "_draw_entries",
    "_draw_zones",
    "_resample_ohlc",
    "_snap_ts_to_candle_x",
    "_zone_color",
    "plot_annotated_ny_session",
    "plot_fvg_signals",
]
