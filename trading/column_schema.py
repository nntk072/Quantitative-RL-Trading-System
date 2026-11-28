"""Process-local indexes over immutable feature-column schemas."""

from __future__ import annotations

from typing import Any

_COLUMN_MATCH_CACHE: dict[tuple[int, tuple[str, ...]], tuple[Any, tuple[str, ...]]] = {}
_COLUMN_MATCH_CACHE_LIMIT = 64


def suffix_columns(columns: Any, suffixes: tuple[str, ...]) -> tuple[str, ...]:
    """Return schema columns equal to or ending in one of ``suffixes``.

    Feature-frame column indexes are immutable and shared across their rows.
    This bounded process-local cache stores only matching column names; row
    values and every eligibility check remain transition-local.

    Args:
        columns: Immutable feature-column index.
        suffixes: Exact names or suffixes to match, in any order.

    Returns:
        Matching string column names in their original schema order.
    """
    normalized_suffixes = tuple(str(suffix) for suffix in suffixes)
    if not normalized_suffixes:
        return ()

    key = (id(columns), normalized_suffixes)
    cached = _COLUMN_MATCH_CACHE.get(key)
    if cached is not None and cached[0] is columns:
        return cached[1]

    matches = tuple(
        name
        for raw_name in columns
        if any(
            (name := str(raw_name)) == suffix or name.endswith(f"_{suffix}")
            for suffix in normalized_suffixes
        )
    )
    if len(_COLUMN_MATCH_CACHE) >= _COLUMN_MATCH_CACHE_LIMIT:
        _COLUMN_MATCH_CACHE.clear()
    _COLUMN_MATCH_CACHE[key] = (columns, matches)
    return matches


__all__ = ["suffix_columns"]
