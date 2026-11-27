"""Compatibility facade for shared Matplotlib style and save helpers."""

from .shared.rendering import (
    _CLOSE_TYPES,
    _NOTE_FONT_PT,
    BREACH_COLOR,
    CLOSE_COLOR,
    EQUITY_COLOR,
    LONG_COLOR,
    PEAK_COLOR,
    SHORT_COLOR,
    STYLE,
    _apply_style,
    _save,
)

__all__ = [
    "BREACH_COLOR",
    "CLOSE_COLOR",
    "EQUITY_COLOR",
    "LONG_COLOR",
    "PEAK_COLOR",
    "SHORT_COLOR",
    "STYLE",
    "_CLOSE_TYPES",
    "_NOTE_FONT_PT",
    "_apply_style",
    "_save",
]
