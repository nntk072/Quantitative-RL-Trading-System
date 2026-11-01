"""Action-coordinate conversion used for environment telemetry."""

from __future__ import annotations

from typing import Any

import numpy as np

from decisioning.actions import ActionSchema
from decisioning.trade_setup import TradeSetupActionSchema

_DECISION_KEYS: tuple[str, ...] = (
    "action_direction",
    "action_intensity",
    "action_stop",
    "action_risk",
    "action_target",
    "action_sl_mode",
    "action_exit",
    "intensity_u",
    "stop_u",
    "risk_u",
    "target_u",
    "sl_mode_u",
    "exit_u",
)


def _empty_decision() -> dict[str, float]:
    """Process decision.

    Returns:
        Mapping from ``str`` keys to ``float`` values.
    """
    return {key: float("nan") for key in _DECISION_KEYS}


def _at(values: np.ndarray[Any, Any], index: int) -> float:
    """Process the requested value.

    Args:
        values: Values to process, in input order.
        index: Position or label identifying the requested item.

    Returns:
        Numeric result returned by ``_at``.
    """
    if values.size <= index:
        return float("nan")
    return float(values[index])


def _decision_from_action(
    raw: np.ndarray[Any, Any],
    unit: np.ndarray[Any, Any],
    schema: ActionSchema | TradeSetupActionSchema,
) -> dict[str, float]:
    """Record raw/unit action coordinates using the versioned layout.

    Args:
        raw: Raw used by the operation described above.
        unit: Unit used by the operation described above.
        schema: Schema used by the operation described above.

    Returns:
        Mapping from ``str`` keys to ``float`` values.
    """
    result = _empty_decision()
    for name, idx in schema.indices.items():
        result[f"action_{name}"] = _at(raw, idx)
        result[f"{name}_u"] = _at(unit, idx)
    return result


__all__ = ["_DECISION_KEYS", "_at", "_decision_from_action", "_empty_decision"]
