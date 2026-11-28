"""Step-local reuse for immutable entry-idea context."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from features.context.entry_ideas import entry_idea_context

_EntryIdeaContextCache = tuple[
    tuple[int, int], dict[tuple[int, int, bool], tuple[Any, dict[str, Any]]]
]


def cached_entry_idea_context(
    env: Any,
    row: Any,
    direction: int,
    *,
    include_zones: bool = False,
) -> dict[str, Any]:
    """Reuse entry context for repeated queries of one row within one step.

    Args:
        env: Environment holding the current episode and decision step.
        row: Immutable feature row for the current market bar.
        direction: Signed direction: 1 for long, -1 for short, or 0.
        include_zones: Whether live source-zone details are requested.

    Returns:
        Entry ideas, their source timeframes, and optional zone details.
    """
    step_key = (
        int(getattr(env, "_episode_identity", 0)),
        int(getattr(env, "step_idx", 0)),
    )
    cache: _EntryIdeaContextCache | None = getattr(env, "_entry_idea_context_cache", None)
    if cache is None or cache[0] != step_key:
        cache = (step_key, {})
        env._entry_idea_context_cache = cache

    key = (id(row), int(direction), bool(include_zones))
    cached = cache[1].get(key)
    if cached is not None and cached[0] is row:
        return cached[1]

    full_context = entry_idea_context(row, direction, include_zones=True)
    no_zones_context = deepcopy(full_context)
    no_zones_context["zones"] = []
    full_key = (id(row), int(direction), True)
    no_zones_key = (id(row), int(direction), False)
    cache[1][full_key] = (row, full_context)
    cache[1][no_zones_key] = (row, no_zones_context)
    return cache[1][key][1]


__all__ = ["cached_entry_idea_context"]
