"""Public hybrid-policy runtime and persistence contracts."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest
import torch
from gymnasium import spaces

from learning.rl.feature_graph import FeatureGraphCache, GraphedForwardCache
from learning.rl.hybrid import (
    HybridClampedStdMultiInputPolicy,
    TradeSetupConditionedClampedStdMultiInputPolicy,
)


def _observation_space(*, with_setup_mask: bool = False) -> spaces.Dict:
    observations: dict[str, spaces.Space[Any]] = {
        "state": spaces.Box(-1.0, 1.0, shape=(4,)),
        "account": spaces.Box(-1.0, 1.0, shape=(3,)),
    }
    if with_setup_mask:
        observations["eligible"] = spaces.Box(0.0, 1.0, shape=(9,))
    return spaces.Dict(observations)


def _flat_policy() -> HybridClampedStdMultiInputPolicy:
    return HybridClampedStdMultiInputPolicy(
        observation_space=_observation_space(),
        action_space=spaces.Box(-1.0, 1.0, shape=(2,)),
        lr_schedule=lambda _progress: 1e-3,
        hybrid_action_coordinates=("exit", "risk"),
    )


def test_hybrid_policy_uses_graph_only_for_no_grad_rollout_collection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = _flat_policy()
    observation = {"state": torch.zeros((1, 4)), "account": torch.zeros((1, 3))}
    graph_result = (torch.ones((1, 2)), torch.ones((1, 1)), torch.ones((1,)))
    eager_result = (torch.zeros((1, 2)), torch.zeros((1, 1)), torch.zeros((1,)))
    graph = Mock(return_value=graph_result)
    monkeypatch.setattr(policy, "_rollout_graph", graph)
    monkeypatch.setattr(
        policy,
        "_forward_eager",
        lambda _obs, deterministic=False: eager_result,
    )
    policy._collecting_rollout = True

    with torch.no_grad():
        actual_graph_result = policy.forward(observation, deterministic=True)

    assert actual_graph_result is graph_result
    graph.assert_called_once_with(observation, True)
    assert policy.forward(observation) is eager_result

    policy._collecting_rollout = False
    with torch.no_grad():
        assert policy.forward(observation) is eager_result
    graph.assert_called_once()


def test_graph_enablement_requires_shared_features_and_builds_only_python_wrappers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = _flat_policy()
    # Emulate the device capability check only. The graph wrappers do not allocate CUDA
    # buffers until called, so this test never captures or claims GPU replay behavior.
    monkeypatch.setattr(
        HybridClampedStdMultiInputPolicy,
        "device",
        property(lambda _self: torch.device("cuda")),
    )
    policy.share_features_extractor = False

    with pytest.raises(ValueError, match="requires a shared features extractor"):
        policy.enable_feature_graph()
    with pytest.raises(ValueError, match="requires a shared features extractor"):
        policy.enable_rollout_policy_graph()
    assert policy._feature_graph is None
    assert policy._rollout_graph is None

    policy.share_features_extractor = True
    policy.enable_feature_graph()
    policy.enable_rollout_policy_graph()

    assert isinstance(policy._feature_graph, FeatureGraphCache)
    assert isinstance(policy._rollout_graph, GraphedForwardCache)


def test_flat_hybrid_checkpoint_omits_setup_mask_and_rollout_mask_validation() -> None:
    policy = _flat_policy()

    parameters = policy._get_constructor_parameters()

    assert parameters["hybrid_action_coordinates"] == ("exit", "risk")
    assert "trade_setup_mask_key" not in parameters
    with pytest.raises(ValueError, match="requires a trade-setup policy"):
        _ = policy.rollout_mask_width


@pytest.mark.parametrize("conditioned", [False, True])
def test_hybrid_policy_rejects_action_coordinate_width_mismatch(conditioned: bool) -> None:
    policy_type: Any = (
        TradeSetupConditionedClampedStdMultiInputPolicy
        if conditioned
        else HybridClampedStdMultiInputPolicy
    )
    kwargs: dict[str, Any] = {
        "observation_space": _observation_space(with_setup_mask=conditioned),
        "action_space": spaces.Box(-1.0, 1.0, shape=(2,)),
        "lr_schedule": lambda _progress: 1e-3,
        "hybrid_action_coordinates": ("trade_setup",) if conditioned else ("exit",),
    }
    if conditioned:
        kwargs["trade_setup_mask_key"] = "eligible"

    with pytest.raises(ValueError, match="coordinate count differs from action-space width"):
        policy_type(**kwargs)
