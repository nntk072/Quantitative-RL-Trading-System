"""Public RL agent guards for unsupported dependency and action metadata."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from gymnasium import spaces
from omegaconf import OmegaConf

import learning.rl.agent as agent
from decisioning.actions import build_discrete_trading_action_schema


def test_build_agent_fails_clearly_when_stable_baselines_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(agent, "_SB3_AVAILABLE", False)

    with pytest.raises(ImportError, match="stable-baselines3 is required"):
        agent.build_agent(None, OmegaConf.create({}))


def test_build_agent_requires_a_prebuilt_vae_before_inspecting_environment() -> None:
    cfg = OmegaConf.create({"env": {"reward_mode": "dsr"}})

    with pytest.raises(ValueError, match="use_vae=True requires a constructed VAE"):
        agent.build_agent(None, cfg, use_vae=True, vae=None)


def test_discrete_schema_binding_rejects_action_space_width_mismatch() -> None:
    schema = build_discrete_trading_action_schema()
    model = SimpleNamespace(action_space=spaces.Discrete(schema.width + 1), policy=None)

    with pytest.raises(ValueError, match="width differs from the model action space"):
        agent.bind_discrete_action_schema(model, schema)

    assert not hasattr(model, "_action_schema")
