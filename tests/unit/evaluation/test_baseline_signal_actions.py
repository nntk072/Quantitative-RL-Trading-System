"""Tests for position-target to discrete baseline action conversion."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from decisioning.actions import build_discrete_trading_action_schema
from evaluation.rollout.baseline_signal_actions import discrete_actions_for_position_targets


def test_position_targets_emit_explicit_holds_exits_and_delayed_reversals() -> None:
    index = pd.RangeIndex(9)
    targets = pd.Series([0, 1, 1, 0, -1, -1, 1, 1, 0], index=index)

    actions = discrete_actions_for_position_targets(targets)

    schema = build_discrete_trading_action_schema()
    long_action = schema.names.index("enter_long_risk_high_rr_low")
    short_action = schema.names.index("enter_short_risk_high_rr_low")
    exit_action = schema.names.index("exit")
    assert actions.tolist() == [
        0,
        long_action,
        0,
        exit_action,
        short_action,
        0,
        exit_action,
        long_action,
        exit_action,
    ]


@pytest.mark.parametrize(
    "targets",
    [
        pd.Series([], dtype=float),
        pd.Series([0.0, np.nan]),
        pd.Series([0.0, 0.5]),
        pd.Series(["long"]),
    ],
)
def test_position_target_converter_rejects_invalid_values(targets: pd.Series) -> None:
    with pytest.raises(ValueError):
        discrete_actions_for_position_targets(targets)


def test_position_target_converter_requires_a_series() -> None:
    with pytest.raises(TypeError, match="pandas Series"):
        discrete_actions_for_position_targets([0, 1])  # type: ignore[arg-type]
