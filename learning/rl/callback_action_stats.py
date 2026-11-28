"""Shared action-coordinate summary helpers for RL callbacks."""

from __future__ import annotations

from typing import Any

import numpy as np


def _action_coordinate_names(env: Any, width: int) -> list[str]:
    """Process coordinate names.

    Args:
        env: Environment whose state is read or updated.
        width: Numeric value used for the width.

    Returns:
        Values returned by ``_action_coordinate_names``, in the declared order.
    """
    schema = getattr(env, "action_schema", None)
    to_dict = getattr(schema, "to_dict", None)
    if callable(to_dict):
        schema = to_dict()
    raw_names = schema.get("coordinates", ()) if isinstance(schema, dict) else ()
    names = [str(name) for name in raw_names] if isinstance(raw_names, (list, tuple)) else []
    return names if len(names) == width else [f"coordinate_{index}" for index in range(width)]


def _record_action_coordinates(
    totals: dict[str, dict[str, float]], action: Any, names: list[str]
) -> None:
    """Record action coordinates.

    Args:
        totals: Key-value data used for the totals.
        action: Action to apply to the current state.
        names: Items supplied for the names, in input order.
    """
    values = np.asarray(action, dtype=np.float64).reshape(-1)
    if values.size != len(names):
        return
    for name, value in zip(names, values, strict=True):
        item = totals.setdefault(
            name,
            {
                "count": 0.0,
                "nonfinite_count": 0.0,
                "sum": 0.0,
                "sum_squares": 0.0,
                "min": float("inf"),
                "max": float("-inf"),
            },
        )
        if not np.isfinite(value):
            item["nonfinite_count"] += 1.0
            continue
        item["count"] += 1.0
        item["sum"] += float(value)
        item["sum_squares"] += float(value * value)
        item["min"] = min(item["min"], float(value))
        item["max"] = max(item["max"], float(value))


def _summarize_action_coordinates(
    totals: dict[str, dict[str, float]],
) -> dict[str, dict[str, float | int]]:
    """Summarize action coordinates.

    Args:
        totals: Key-value data used for the totals.

    Returns:
        Mapping from ``str`` keys to ``dict[str, float | int]`` values.
    """
    summary: dict[str, dict[str, float | int]] = {}
    for name, item in totals.items():
        count = int(item["count"])
        mean = item["sum"] / count if count else float("nan")
        variance = max(item["sum_squares"] / count - mean * mean, 0.0) if count else float("nan")
        summary[name] = {
            "n": count,
            "nonfinite_n": int(item["nonfinite_count"]),
            "mean": mean,
            "std": float(np.sqrt(variance)),
            "min": item["min"] if count else float("nan"),
            "max": item["max"] if count else float("nan"),
        }
    return summary
