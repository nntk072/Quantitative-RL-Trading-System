from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from gymnasium import spaces

from decisioning.adapters.sb3 import SB3DecisionProvider
from decisioning.contracts import (
    ActionSchemaRef,
    ContinuousAction,
    Decision,
    DecisionInput,
    DiscreteAction,
    StructuredAction,
    to_policy_action,
)


class _Policy:
    def __init__(
        self, action_space: spaces.Space[Any], schema: dict[str, Any], action: Any
    ) -> None:
        self.action_space = action_space
        self._action_schema = schema
        self._action = action
        self.calls: list[tuple[Any, bool]] = []

    def predict(
        self, observation: dict[str, np.ndarray[Any, Any]], *, deterministic: bool
    ) -> tuple[Any, None]:
        self.calls.append((observation, deterministic))
        return self._action, None


def _input(schema_version: str = "observation-v1") -> DecisionInput:
    return DecisionInput({"seq": np.zeros((2, 3), dtype=np.float32)}, schema_version)


def test_discrete_provider_names_action_and_preserves_determinism() -> None:
    names = ("hold", "enter_long", "exit")
    model = _Policy(
        spaces.Discrete(3),
        {"kind": "discrete", "version": "discrete-v1", "key": "d3", "coordinates": names},
        np.asarray([1]),
    )
    provider = SB3DecisionProvider(model, input_schema_version="observation-v1")

    decision = provider.predict(_input(), deterministic=False)

    assert decision.action == DiscreteAction(index=1, name="enter_long")
    assert to_policy_action(decision) == 1
    assert model.calls[0][1] is False
    assert provider.metadata.action_schema.coordinates == names


@pytest.mark.parametrize("action", [1.5, float("nan"), float("inf")])
def test_discrete_provider_rejects_fractional_or_nonfinite_action(action: float) -> None:
    model = _Policy(
        spaces.Discrete(3),
        {
            "kind": "discrete",
            "version": "discrete-v1",
            "key": "d3",
            "coordinates": ("hold", "long", "exit"),
        },
        np.asarray([action]),
    )
    provider = SB3DecisionProvider(model, input_schema_version="observation-v1")

    with pytest.raises(ValueError, match="finite integer"):
        provider.predict(_input())


def test_box_provider_returns_named_structured_coordinates_in_schema_order() -> None:
    coordinates = ("direction", "risk", "target")
    model = _Policy(
        spaces.Box(-1.0, 1.0, shape=(3,), dtype=np.float32),
        {"version": "overlay-v2", "key": "3", "coordinates": coordinates},
        np.asarray([0.25, -0.5, 1.0], dtype=np.float32),
    )
    provider = SB3DecisionProvider(model, input_schema_version="observation-v1")

    decision = provider.predict(_input())

    assert decision.action == StructuredAction({"direction": 0.25, "risk": -0.5, "target": 1.0})
    np.testing.assert_array_equal(to_policy_action(decision), [0.25, -0.5, 1.0])


@pytest.mark.parametrize("action", [[0.1, float("nan"), 0.3], [0.1, 0.2, float("inf")]])
def test_box_provider_rejects_nonfinite_actions(action: list[float]) -> None:
    model = _Policy(
        spaces.Box(-1.0, 1.0, shape=(3,), dtype=np.float32),
        {"version": "overlay-v2", "key": "3", "coordinates": ("direction", "risk", "target")},
        np.asarray(action, dtype=np.float32),
    )
    provider = SB3DecisionProvider(model, input_schema_version="observation-v1")

    with pytest.raises(ValueError, match="only finite values"):
        provider.predict(_input())


def test_scalar_box_provider_uses_continuous_action_contract() -> None:
    model = _Policy(
        spaces.Box(-1.0, 1.0, shape=(1,), dtype=np.float32),
        {"version": "continuous-v1", "key": "scalar", "coordinates": ("position",)},
        np.asarray([0.4], dtype=np.float32),
    )
    provider = SB3DecisionProvider(model, input_schema_version="observation-v1")

    decision = provider.predict(_input())

    assert isinstance(decision.action, ContinuousAction)
    assert decision.action.value == pytest.approx(0.4)
    np.testing.assert_allclose(to_policy_action(decision), [0.4])


def test_provider_rejects_observation_schema_mismatch() -> None:
    model = _Policy(
        spaces.Discrete(2),
        {
            "kind": "discrete",
            "version": "discrete-v1",
            "key": "d2",
            "coordinates": ("hold", "exit"),
        },
        0,
    )
    provider = SB3DecisionProvider(model, input_schema_version="observation-v1")

    with pytest.raises(ValueError, match="observation schema"):
        provider.predict(_input("observation-v2"))


def test_provider_rejects_missing_or_inconsistent_action_schema() -> None:
    with pytest.raises(ValueError, match="persisted action schema"):
        SB3DecisionProvider(
            _Policy(spaces.Discrete(2), {}, 0), input_schema_version="observation-v1"
        )
    with pytest.raises(ValueError, match="wrong width"):
        SB3DecisionProvider(
            _Policy(
                spaces.Discrete(2),
                {"kind": "discrete", "version": "v1", "key": "d2", "coordinates": ("hold",)},
                0,
            ),
            input_schema_version="observation-v1",
        )


def test_structured_conversion_requires_exact_coordinate_set() -> None:
    model = _Policy(
        spaces.Box(-1.0, 1.0, shape=(2,), dtype=np.float32),
        {"version": "overlay-v2", "key": "2", "coordinates": ("risk", "target")},
        np.asarray([0.1, 0.2], dtype=np.float32),
    )
    decision = SB3DecisionProvider(model, input_schema_version="observation-v1").predict(_input())
    assert isinstance(decision.action, StructuredAction)

    inconsistent = Decision(
        action=StructuredAction({"risk": 0.1}),
        action_schema=ActionSchemaRef(
            version="overlay-v2", key="2", coordinates=("risk", "target"), kind="continuous"
        ),
    )
    with pytest.raises(ValueError, match="coordinates disagree"):
        to_policy_action(inconsistent)


@pytest.mark.parametrize(
    "decision",
    [
        Decision(
            action=DiscreteAction(index=1, name="wrong"),
            action_schema=ActionSchemaRef(
                version="discrete-v1", key="d2", coordinates=("hold", "exit"), kind="discrete"
            ),
        ),
        Decision(
            action=ContinuousAction(value=float("nan")),
            action_schema=ActionSchemaRef(
                version="continuous-v1", key="scalar", coordinates=("position",), kind="continuous"
            ),
        ),
        Decision(
            action=StructuredAction({"risk": 0.1, "target": float("inf")}),
            action_schema=ActionSchemaRef(
                version="overlay-v2", key="2", coordinates=("risk", "target"), kind="continuous"
            ),
        ),
    ],
)
def test_policy_action_conversion_rejects_actions_that_disagree_with_schema(
    decision: Decision,
) -> None:
    with pytest.raises(ValueError):
        to_policy_action(decision)
