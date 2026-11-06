"""Strict parsing helpers for persisted training gate evidence."""

from __future__ import annotations

from typing import Any


def strict_nonnegative_int(value: Any) -> int | None:
    """Return a nonnegative integer only when the source value is exactly typed.

    Args:
        value: Persisted count value to validate.

    Returns:
        Nonnegative integer, or ``None`` for booleans and other types.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value
