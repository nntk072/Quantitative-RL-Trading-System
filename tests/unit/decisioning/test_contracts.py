from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from gymnasium import spaces

from decisioning.adapters.rule_based import RuleBasedDecisionProvider
from decisioning.adapters.sb3 import SB3DecisionProvider
from decisioning.contracts import (
    ActionSchemaRef,
    ContinuousAction,
    Decision,
    DecisionInput,
    DiscreteAction,
    PredictorMetadata,
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


def test_rule_based_provider_enforces_input_and_action_schema_metadata() -> None:
    action_schema = ActionSchemaRef("v1", "actions", ("hold",), "discrete")
    metadata = PredictorMetadata("rule", "rule", "rules", "obs-v1", action_schema)
    expected = Decision(DiscreteAction(0, "hold"), action_schema)

    def rule(_input: DecisionInput) -> Decision:
        return expected

    provider = RuleBasedDecisionProvider(rule, metadata)

    assert provider.metadata == metadata
    assert provider.predict(DecisionInput({}, "obs-v1"), deterministic=False) == expected
    with pytest.raises(ValueError, match="observation schema"):
        provider.predict(DecisionInput({}, "obs-v2"))

    wrong_action = Decision(
        DiscreteAction(0, "hold"), ActionSchemaRef("v1", "other", ("hold",), "discrete")
    )

    def mismatched_rule(_input: DecisionInput) -> Decision:
        return wrong_action

    mismatched_provider = RuleBasedDecisionProvider(mismatched_rule, metadata)
    with pytest.raises(ValueError, match="differs from provider metadata"):
        mismatched_provider.predict(DecisionInput({}, "obs-v1"))


def test_sb3_provider_decodes_named_discrete_and_structured_actions() -> None:
    class FakeModel:
        def __init__(self, action_space: Any, schema: dict[str, object], action: object) -> None:
            self.action_space = action_space
            self._action_schema = schema
            self._action = action
            self.deterministic: bool | None = None

        def predict(self, observation: object, *, deterministic: bool) -> tuple[object, None]:
            self.deterministic = deterministic
            return self._action, None

    discrete_model = FakeModel(
        spaces.Discrete(2),
        {
            "kind": "discrete",
            "version": "d1",
            "key": "d2",
            "coordinates": ["hold", "exit"],
        },
        np.asarray([1]),
    )
    discrete = SB3DecisionProvider(discrete_model, input_schema_version="obs-v1")
    result = discrete.predict(DecisionInput({"x": 1.0}, "obs-v1"), deterministic=False)
    assert result.action == DiscreteAction(1, "exit")
    assert result.action_schema == discrete.metadata.action_schema
    assert discrete_model.deterministic is False

    continuous_model = FakeModel(
        spaces.Box(-1.0, 1.0, shape=(2,)),
        {"version": "a1", "key": "pair", "coordinates": ["risk", "target"]},
        np.asarray([0.25, -0.5]),
    )
    continuous = SB3DecisionProvider(continuous_model, input_schema_version="obs-v1")
    structured = continuous.predict(DecisionInput({}, "obs-v1")).action
    assert structured == StructuredAction({"risk": 0.25, "target": -0.5})


def test_sb3_provider_rejects_incompatible_saved_schema_and_predictions() -> None:
    class FakeModel:
        def __init__(self, action_space: Any, schema: object, action: object) -> None:
            self.action_space = action_space
            self._action_schema = schema
            self.action = action

        def predict(self, observation: object, *, deterministic: bool) -> tuple[object, None]:
            del observation, deterministic
            return self.action, None

    with pytest.raises(ValueError, match="persisted action schema"):
        SB3DecisionProvider(
            FakeModel(spaces.Discrete(2), None, np.asarray([0])), input_schema_version="obs-v1"
        )
    with pytest.raises(TypeError, match="one-dimensional Box or Discrete"):
        SB3DecisionProvider(
            FakeModel(spaces.MultiDiscrete([2, 2]), {}, np.asarray([0, 1])),
            input_schema_version="obs-v1",
        )

    model = FakeModel(
        spaces.Discrete(2),
        {
            "kind": "discrete",
            "version": "d1",
            "key": "d2",
            "coordinates": ["hold", "exit"],
        },
        np.asarray([0.5]),
    )
    provider = SB3DecisionProvider(model, input_schema_version="obs-v1")
    with pytest.raises(ValueError, match="finite integer"):
        provider.predict(DecisionInput({}, "obs-v1"))
    model.action = np.asarray([2])
    with pytest.raises(ValueError, match="outside the action schema"):
        provider.predict(DecisionInput({}, "obs-v1"))

    model.action = np.asarray([0, 1])
    with pytest.raises(ValueError, match="exactly one category"):
        provider.predict(DecisionInput({}, "obs-v1"))
    model.action = np.asarray([object()])
    with pytest.raises(ValueError, match="finite integer"):
        provider.predict(DecisionInput({}, "obs-v1"))

    continuous_without_schema = FakeModel(spaces.Box(-1.0, 1.0, shape=(1,)), None, [0.0])
    with pytest.raises(ValueError, match="continuous model requires a persisted action schema"):
        SB3DecisionProvider(continuous_without_schema, input_schema_version="obs-v1")
    wrong_width_schema = {
        "version": "a1",
        "key": "pair",
        "coordinates": ["risk", "target"],
    }
    with pytest.raises(ValueError, match="continuous action schema is incomplete"):
        SB3DecisionProvider(
            FakeModel(spaces.Box(-1.0, 1.0, shape=(1,)), wrong_width_schema, [0.0]),
            input_schema_version="obs-v1",
        )
    continuous_model = FakeModel(
        spaces.Box(-1.0, 1.0, shape=(2,)),
        {"version": "a1", "key": "pair", "coordinates": ["risk", "target"]},
        [0.0],
    )
    continuous = SB3DecisionProvider(continuous_model, input_schema_version="obs-v1")
    with pytest.raises(ValueError, match="action width 1 differs from schema width 2"):
        continuous.predict(DecisionInput({}, "obs-v1"))
