"""Translate position-target baselines into explicit discrete actions."""

from __future__ import annotations

import numpy as np
import pandas as pd

from decisioning.actions import build_discrete_trading_action_schema


def discrete_actions_for_position_targets(targets: pd.Series) -> pd.Series:
    """Convert ``-1/0/+1`` targets to the discrete trading action contract.

    A direction change first emits an exit action; an opposite entry can occur
    on the following bar. Entries use the high-risk/low-target action
    coordinates; the evaluator sets its risk range so this matches the
    continuous baselines' absolute risk.

    Args:
        targets: Causal position targets aligned to the evaluated bars.

    Returns:
        Discrete actions aligned to ``targets.index``.

    Raises:
        TypeError: If ``targets`` is not a pandas Series.
        ValueError: If values are empty, non-finite, or outside ``{-1, 0, 1}``.
    """
    if not isinstance(targets, pd.Series):
        raise TypeError("targets must be a pandas Series")
    if targets.empty:
        raise ValueError("targets must not be empty")
    try:
        values = targets.to_numpy(dtype=float, copy=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("targets must be numeric") from exc
    if not np.isfinite(values).all():
        raise ValueError("targets must be finite")
    if not np.isin(values, (-1.0, 0.0, 1.0)).all():
        raise ValueError("targets must contain only -1, 0, or 1")

    schema = build_discrete_trading_action_schema()
    long_action = schema.names.index("enter_long_risk_high_rr_low")
    short_action = schema.names.index("enter_short_risk_high_rr_low")
    exit_action = schema.names.index("exit")

    actions: list[int] = []
    position = 0
    for raw_target in values:
        target = int(raw_target)
        if position != 0 and target != position:
            actions.append(exit_action)
            position = 0
        elif position == 0 and target != 0:
            actions.append(long_action if target > 0 else short_action)
            position = target
        else:
            actions.append(0)
    return pd.Series(actions, index=targets.index, dtype=int, name=targets.name)
