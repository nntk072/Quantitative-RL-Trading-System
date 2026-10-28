from __future__ import annotations

from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
import numpy.typing as npt
import pytest
import torch
from gymnasium import spaces
from omegaconf import OmegaConf
from stable_baselines3 import PPO

from decisioning.thesis import (
    THESIS_CATEGORY_COUNT,
    build_thesis_action_schema,
    thesis_id_from_box,
    thesis_observation_schema,
)
from learning.rl.agent import build_agent, encoder_for, validate_model_architecture
from models.encoders import (
    M1TCNHTFLiteReasoningEncoder,
    M1TCNHTFSnapshotReasoningEncoder,
    SharedTCNMTFReasoningEncoder,
)
from training.setup.models import _training_architecture_provenance

_STREAMS = (
    ("seq", "seq_mask", 60, 282),
    ("seq_m3", "mask_m3", 20, 60),
    ("seq_m5", "mask_m5", 24, 60),
    ("seq_m10", "mask_m10", 12, 60),
    ("seq_m15", "mask_m15", 16, 60),
    ("seq_m30", "mask_m30", 8, 60),
    ("seq_h1", "mask_h1", 12, 60),
    ("seq_h4", "mask_h4", 6, 60),
    ("seq_d1", "mask_d1", 5, 60),
)

_VARIANTS: tuple[tuple[str, type[torch.nn.Module]], ...] = (
    ("mtf_shared_tcn_reasoning", SharedTCNMTFReasoningEncoder),
    ("mtf_m1_tcn_htf_lite_reasoning", M1TCNHTFLiteReasoningEncoder),
    ("mtf_m1_tcn_htf_snapshot_reasoning", M1TCNHTFSnapshotReasoningEncoder),
)


class _ThesisMTFEnv(gym.Env[dict[str, npt.NDArray[np.float32]], npt.NDArray[np.float32]]):
    def __init__(self) -> None:
        schema: dict[str, spaces.Space[Any]] = {
            "account": spaces.Box(-10.0, 10.0, (6,), dtype=np.float32),
            "thesis_mask": spaces.Box(0.0, 1.0, (THESIS_CATEGORY_COUNT,), dtype=np.float32),
        }
        for seq_key, mask_key, length, width in _STREAMS:
            schema[seq_key] = spaces.Box(-1.0, 1.0, (length, width), dtype=np.float32)
            schema[mask_key] = spaces.Box(0.0, 1.0, (length,), dtype=np.float32)
        self.observation_space = spaces.Dict(schema)
        self.action_space = spaces.Box(-1.0, 1.0, (5,), dtype=np.float32)
        self.action_schema = build_thesis_action_schema()
        self.thesis_actions = True
        self.strategy_actions = True
        self.thesis_observation_schema = thesis_observation_schema()

    def _observation(self) -> dict[str, npt.NDArray[np.float32]]:
        observation: dict[str, npt.NDArray[np.float32]] = {
            "account": np.zeros(6, dtype=np.float32),
            "thesis_mask": np.zeros(THESIS_CATEGORY_COUNT, dtype=np.float32),
        }
        observation["thesis_mask"][[0, 12, 51]] = 1.0
        for seq_key, mask_key, length, width in _STREAMS:
            observation[seq_key] = np.zeros((length, width), dtype=np.float32)
            observation[mask_key] = np.ones(length, dtype=np.float32)
        return observation

    def reset(
        self, *, seed: int | None = None, options: dict[str, object] | None = None
    ) -> tuple[dict[str, npt.NDArray[np.float32]], dict[str, object]]:
        super().reset(seed=seed)
        return self._observation(), {}

    def step(
        self, action: npt.NDArray[np.float32]
    ) -> tuple[dict[str, npt.NDArray[np.float32]], float, bool, bool, dict[str, object]]:
        del action
        return self._observation(), 0.0, False, False, {}


def _agent_config(arch: str) -> Any:
    return OmegaConf.create(
        {
            "env": {"n_envs": 1, "thesis_actions": True, "strategy_actions": True},
            "agent": {
                "arch": arch,
                "head_arch": {arch: [32]},
                arch: {
                    "latent_dim": 16,
                    "channels": [8, 8],
                    "kernel_size": 3,
                    "dropout": 0.0,
                    "adapter_dim": 5 if arch == "mtf_shared_tcn_reasoning" else 4,
                    "attention_heads": 4,
                    "feedforward_dim": 32,
                },
            },
            "ppo": {
                "policy_distribution": "thesis_conditioned_v1",
                "actor_arch": "shared",
                "thesis_conditioned": {"embedding_dim": 8, "execution_hidden_dim": 16},
                "n_steps": 2,
                "batch_size": 2,
                "n_epochs": 1,
                "learning_rate": 3.0e-4,
                "gamma": 0.99,
                "gae_lambda": 0.95,
                "clip_range": 0.2,
                "ent_coef": 0.01,
                "ent_coef_continuous": 0.001,
                "rollout_buffer_on_device": False,
            },
        }
    )


def test_encoder_registry_maps_new_ids_and_rejects_unknown() -> None:
    for arch, encoder in _VARIANTS:
        assert encoder_for(arch) is encoder
    with pytest.raises(ValueError, match="unknown encoder architecture"):
        encoder_for("mtf_reasoning_typo")


@pytest.mark.parametrize("arch,encoder_class", _VARIANTS)
def test_thesis_conditioned_ppo_checkpoint_roundtrip_preserves_encoder(
    arch: str,
    encoder_class: type[torch.nn.Module],
    tmp_path: Path,
) -> None:
    env = _ThesisMTFEnv()
    config = _agent_config(arch)
    model = build_agent(env, config, arch=arch, device="cpu", seed=17)
    assert type(model.policy.features_extractor) is encoder_class
    assert type(model.policy).__name__ == "ThesisConditionedClampedStdMultiInputPolicy"
    run_provenance = _training_architecture_provenance(model, config, arch)
    encoder_details = run_provenance["encoder_specific"]
    assert isinstance(encoder_details, dict)
    assert encoder_details["encoder_id"] == arch
    assert run_provenance["encoder_parameter_count"] == sum(
        parameter.numel() for parameter in model.policy.features_extractor.parameters()
    )
    model.learn(total_timesteps=4)

    observation, _ = env.reset()
    predicted, _ = model.predict(observation, deterministic=True)
    assert thesis_id_from_box(float(predicted[0])) in {0, 12, 51}
    observation_tensor, _ = model.policy.obs_to_tensor(observation)
    action_tensor = torch.as_tensor(predicted, device=model.device).reshape(1, -1)
    _, log_prob, entropy = model.policy.evaluate_actions(observation_tensor, action_tensor)
    expected_log_prob = model.policy.get_distribution(observation_tensor).log_prob(action_tensor)
    assert torch.isfinite(log_prob).all()
    assert entropy is not None and torch.isfinite(entropy).all()
    assert torch.allclose(log_prob, expected_log_prob)

    model.policy.zero_grad(set_to_none=True)
    values, differentiable_log_prob, differentiable_entropy = model.policy.evaluate_actions(
        observation_tensor, action_tensor
    )
    assert differentiable_entropy is not None
    (-differentiable_log_prob.mean() + values.mean() - differentiable_entropy.mean()).backward()
    for name, module in (
        ("encoder", model.policy.features_extractor),
        ("thesis-conditioned actor", model.policy.action_net),
    ):
        gradients = [
            parameter.grad
            for parameter in module.parameters()
            if parameter.requires_grad and parameter.grad is not None
        ]
        assert gradients, f"{name} received no gradients"
        assert all(torch.isfinite(gradient).all() for gradient in gradients), name
        assert sum(float(gradient.abs().sum()) for gradient in gradients) > 0.0, name

    checkpoint = tmp_path / f"{arch}.zip"
    model.save(checkpoint)
    loaded = PPO.load(checkpoint, device="cpu")
    validate_model_architecture(loaded, arch)
    assert type(loaded.policy.features_extractor) is encoder_class
    loaded_action, _ = loaded.predict(observation, deterministic=True)
    assert np.allclose(loaded_action, predicted)

    other_arch = next(name for name, _ in _VARIANTS if name != arch)
    with pytest.raises(ValueError, match="does not match requested architecture"):
        validate_model_architecture(loaded, other_arch)
