"""Runtime diagnostics services for the trading environment.

This package preserves the diagnostic helpers exported by the former
``diagnostics.py`` module.
"""

from .errors import (
    DebugStepError,
    jsonable,
    new_debug_window,
    note_debug_step,
    summarize_window,
    wiring_from_env,
)

__all__ = [
    "DebugStepError",
    "jsonable",
    "new_debug_window",
    "note_debug_step",
    "summarize_window",
    "wiring_from_env",
]
