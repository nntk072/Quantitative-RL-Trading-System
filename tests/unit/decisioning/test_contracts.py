from __future__ import annotations

import numpy as np
import pytest

from decisioning.contracts import (
    ActionSchemaRef,
    ContinuousAction,
    Decision,
    DiscreteAction,
    StructuredAction,
    to_policy_action,
)


def test_discrete_action_contract_rejects_invalid_schema_and_index() -> None:
    action = DiscreteAction(index=0, name="hold")
    with pytest.raises(ValueError, match="must have a version"):
        to_policy_action(Decision(action, ActionSchemaRef("", "actions", ("hold",), "discrete")))
    with pytest.raises(ValueError, match="coordinates must be unique"):
        to_policy_action(
            Decision(action, ActionSchemaRef("v1", "actions", ("hold", "hold"), "discrete"))
        )
    with pytest.raises(ValueError, match="requires a discrete"):
        to_policy_action(
            Decision(action, ActionSchemaRef("v1", "actions", ("hold",), "continuous"))
        )
    with pytest.raises(ValueError, match="must be an integer"):
        to_policy_action(
            Decision(
                DiscreteAction(index=True, name="hold"),
                ActionSchemaRef("v1", "actions", ("hold",), "discrete"),
            )
        )
    with pytest.raises(ValueError, match="outside its action schema"):
        to_policy_action(
            Decision(
                DiscreteAction(index=2, name="hold"),
                ActionSchemaRef("v1", "actions", ("hold",), "discrete"),
            )
        )


def test_continuous_and_structured_actions_enforce_schema_shape_and_finiteness() -> None:
    scalar = ActionSchemaRef("v1", "position", ("position",), "continuous")
    with pytest.raises(ValueError, match="one-coordinate"):
        to_policy_action(
            Decision(ContinuousAction(0.5), ActionSchemaRef("v1", "pair", ("x", "y"), "continuous"))
        )
    with pytest.raises(ValueError, match="finite"):
        to_policy_action(Decision(ContinuousAction(float("inf")), scalar))
    with pytest.raises(ValueError, match="requires a continuous"):
        to_policy_action(
            Decision(
                StructuredAction({"direction": 1.0}),
                ActionSchemaRef("v1", "pair", ("direction",), "discrete"),
            )
        )
    with pytest.raises(ValueError, match="disagree"):
        to_policy_action(
            Decision(
                StructuredAction({"x": 1.0}), ActionSchemaRef("v1", "pair", ("y",), "continuous")
            )
        )
    values = to_policy_action(Decision(StructuredAction({"position": 0.25}), scalar))
    np.testing.assert_array_equal(values, np.asarray([0.25], dtype=np.float32))
