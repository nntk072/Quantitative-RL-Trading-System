from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import gymnasium as gym
import numpy as np
import numpy.typing as npt
import pytest
import torch
from gymnasium import spaces
from stable_baselines3 import PPO

from configuration import load_config
from decisioning.actions import build_discrete_trading_action_schema
from decisioning.observations import build_observation_schema
from decisioning.regime_observations import REGIME_FEATURES, regime_observation_schema
from learning.rl.agent import build_agent, validate_model_architecture
from models.encoders import TCNEncoder, TCNRegimeEncoder
from models.factory import encoder_for

FloatArray = npt.NDArray[np.float32]


def _observation_space() -> spaces.Dict:
    width = len(REGIME_FEATURES)
    return spaces.Dict(
        {
            "seq": spaces.Box(-np.inf, np.inf, shape=(12, 4), dtype=np.float32),
            "seq_mask": spaces.Box(0.0, 1.0, shape=(12,), dtype=np.float32),
            "account": spaces.Box(-np.inf, np.inf, shape=(6,), dtype=np.float32),
            "regime": spaces.Box(-np.inf, np.inf, shape=(width,), dtype=np.float32),
            "regime_mask": spaces.Box(0.0, 1.0, shape=(width,), dtype=np.float32),
        }
    )


def _inputs(batch: int = 2) -> dict[str, torch.Tensor]:
    width = len(REGIME_FEATURES)
    return {
        "seq": torch.randn(batch, 12, 4),
        "seq_mask": torch.ones(batch, 12),
        "account": torch.randn(batch, 6),
        "regime": torch.randn(batch, width),
        "regime_mask": torch.ones(batch, width),
    }


class _TinyRegimeEnv(gym.Env[dict[str, FloatArray], np.int64]):
    def __init__(self) -> None:
        width = len(REGIME_FEATURES)
        self.observation_space = spaces.Dict(
            {
                "seq": spaces.Box(-1.0, 1.0, shape=(12, 4), dtype=np.float32),
                "seq_mask": spaces.Box(0.0, 1.0, shape=(12,), dtype=np.float32),
                "account": spaces.Box(-1.0, 1.0, shape=(6,), dtype=np.float32),
                "regime": spaces.Box(-1.0, 1.0, shape=(width,), dtype=np.float32),
                "regime_mask": spaces.Box(0.0, 1.0, shape=(width,), dtype=np.float32),
            }
        )
        self.action_space = spaces.Discrete(20)
        self.action_schema = build_discrete_trading_action_schema()
        self.observation_schema = build_observation_schema()
        self.regime_observation_schema = regime_observation_schema()

    def _observation(self) -> dict[str, FloatArray]:
        return {
            "seq": np.zeros((12, 4), dtype=np.float32),
            "seq_mask": np.ones(12, dtype=np.float32),
            "account": np.zeros(6, dtype=np.float32),
            "regime": np.zeros(len(REGIME_FEATURES), dtype=np.float32),
            "regime_mask": np.ones(len(REGIME_FEATURES), dtype=np.float32),
        }

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[dict[str, FloatArray], dict[str, Any]]:
        super().reset(seed=seed)
        return self._observation(), {}

    def step(
        self, action: np.int64
    ) -> tuple[dict[str, FloatArray], float, bool, bool, dict[str, Any]]:
        return self._observation(), 0.0, False, False, {}


def test_tcn_regime_is_registered_and_has_gradients() -> None:
    encoder = TCNRegimeEncoder(
        _observation_space(),
        seq_len=12,
        n_features=4,
        latent_dim=8,
        channels=(8, 8),
        dropout=0.0,
    )
    observations = _inputs()
    output = encoder(observations)

    assert encoder_for("tcn_regime") is TCNRegimeEncoder
    assert output.shape == (2, encoder.features_dim) == (2, 56)
    output.sum().backward()
    first_layer = encoder.regime_mlp[0]
    assert isinstance(first_layer, torch.nn.Linear)
    gradient = first_layer.weight.grad
    assert gradient is not None
    assert torch.isfinite(gradient).all()


def test_masked_regime_branch_is_neutral_and_valid_regime_changes_output() -> None:
    encoder = TCNRegimeEncoder(
        _observation_space(),
        seq_len=12,
        n_features=4,
        latent_dim=8,
        channels=(8, 8),
        dropout=0.0,
    ).eval()
    observations = _inputs(batch=1)
    masked = dict(observations, regime_mask=torch.zeros_like(observations["regime_mask"]))
    different_masked = dict(masked, regime=observations["regime"] + 5.0)
    valid_changed = dict(observations, regime=observations["regime"] + 5.0)

    torch.testing.assert_close(encoder(masked), encoder(different_masked))
    assert not torch.allclose(encoder(observations), encoder(valid_changed))


def test_regime_encoder_requires_declared_coordinates_and_checkpoint_schema() -> None:
    with pytest.raises(ValueError, match="requires regime and regime_mask"):
        TCNRegimeEncoder(
            spaces.Dict(
                {
                    "seq": spaces.Box(-np.inf, np.inf, shape=(12, 4), dtype=np.float32),
                    "account": spaces.Box(-np.inf, np.inf, shape=(6,), dtype=np.float32),
                }
            )
        )

    model = SimpleNamespace(
        policy=SimpleNamespace(features_extractor=TCNRegimeEncoder(_observation_space())),
        _regime_observation_schema=regime_observation_schema(),
    )
    validate_model_architecture(model, "tcn_regime")
    with pytest.raises(ValueError, match="checkpoint encoder"):
        validate_model_architecture(model, "tcn")
    model._regime_observation_schema = {"version": "stale"}
    with pytest.raises(ValueError, match="regime observation schema"):
        validate_model_architecture(model, "tcn_regime")


def test_existing_tcn_architecture_mapping_is_unchanged() -> None:
    assert encoder_for("tcn") is TCNEncoder


def test_tcn_regime_builds_and_checkpoint_roundtrips(tmp_path: Path) -> None:
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    env = _TinyRegimeEnv()
    model: PPO | None = None
    try:
        cfg = load_config()
        cfg.env.n_envs = 8
        cfg.env.vector_backend = "serial"
        cfg.env.obs_window = 12
        cfg.ppo.n_steps = 8
        cfg.ppo.batch_size = 8
        cfg.ppo.n_epochs = 1

        model = build_agent(
            env,
            cfg,
            arch="tcn_regime",
            device="cpu",
            env_fn=_TinyRegimeEnv,
        )
        assert isinstance(model.policy.features_extractor, TCNRegimeEncoder)
        validate_model_architecture(model, "tcn_regime")
        observation = env._observation()
        expected_action, _ = model.predict(observation, deterministic=True)
        checkpoint = tmp_path / "tcn_regime_ppo"
        model.save(checkpoint)
        loaded = PPO.load(checkpoint, device="cpu")
        validate_model_architecture(loaded, "tcn_regime")
        actual_action, _ = loaded.predict(observation, deterministic=True)
        np.testing.assert_array_equal(expected_action, actual_action)
    finally:
        if model is not None:
            vector_env = model.get_env()
            if vector_env is not None:
                vector_env.close()
        env.close()
        torch.set_num_threads(previous_threads)
