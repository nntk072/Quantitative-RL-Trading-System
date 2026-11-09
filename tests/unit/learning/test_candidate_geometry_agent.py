from __future__ import annotations

from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
import numpy.typing as npt
from gymnasium import spaces
from omegaconf import OmegaConf
from stable_baselines3 import PPO

from decisioning.trade_setup import (
    CANDIDATE_GEOMETRY_FEATURE_NAMES,
    TRADE_SETUP_CATEGORY_COUNT,
    build_trade_setup_action_schema,
    candidate_geometry_observation_schema,
    candidate_geometry_slot,
    candidate_geometry_slot_count,
    candidate_geometry_slot_semantics,
    trade_setup_observation_schema,
)
from learning.rl.agent import (
    build_agent,
    validate_model_candidate_geometry_observation_schema,
)


class _CandidateGeometryEnv(gym.Env[dict[str, npt.NDArray[Any]], npt.NDArray[np.float32]]):
    def __init__(self) -> None:
        count = candidate_geometry_slot_count()
        self.observation_space = spaces.Dict(
            {
                "seq": spaces.Box(-1.0, 1.0, (10, 4), dtype=np.float32),
                "seq_mask": spaces.Box(0.0, 1.0, (10,), dtype=np.float32),
                "account": spaces.Box(-10.0, 10.0, (6,), dtype=np.float32),
                "trade_setup_mask": spaces.Box(
                    0.0, 1.0, (TRADE_SETUP_CATEGORY_COUNT,), dtype=np.float32
                ),
                "candidate_ids": spaces.Box(
                    0, TRADE_SETUP_CATEGORY_COUNT - 1, (count,), dtype=np.int64
                ),
                "candidate_features": spaces.Box(
                    -10.0,
                    10.0,
                    (count, len(CANDIDATE_GEOMETRY_FEATURE_NAMES)),
                    dtype=np.float32,
                ),
                "candidate_mask": spaces.Box(
                    np.zeros(count, dtype=np.bool_),
                    np.ones(count, dtype=np.bool_),
                    (count,),
                    dtype=np.bool_,  # type: ignore[arg-type]  # Gymnasium accepts bool Boxes.
                ),
            }
        )
        self.action_schema = build_trade_setup_action_schema(
            has_sl_mode=True,
            has_entry_execution=True,
        )
        self.action_space = spaces.Box(-1.0, 1.0, (self.action_schema.width,), dtype=np.float32)
        self.trade_setup_actions = True
        self.candidate_geometry_actions = True
        self.strategy_actions = True
        self.trade_setup_observation_schema = trade_setup_observation_schema()
        self.candidate_geometry_observation_schema = candidate_geometry_observation_schema()

    def _observation(self) -> dict[str, npt.NDArray[Any]]:
        count = candidate_geometry_slot_count()
        trade_mask = np.zeros(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
        trade_mask[[0, 1]] = 1.0
        candidate_mask = np.zeros(count, dtype=np.bool_)
        candidate_mask[0] = True
        candidate_mask[candidate_geometry_slot(1, "market")] = True
        candidate_mask[candidate_geometry_slot(1, "limit")] = True
        candidate_features = np.zeros(
            (count, len(CANDIDATE_GEOMETRY_FEATURE_NAMES)), dtype=np.float32
        )
        limit_slot = candidate_geometry_slot(1, "limit")
        candidate_features[
            limit_slot, CANDIDATE_GEOMETRY_FEATURE_NAMES.index("entry_price_offset_atr")
        ] = -0.5
        candidate_features[
            limit_slot, CANDIDATE_GEOMETRY_FEATURE_NAMES.index("limit_ttl_fraction")
        ] = 0.25
        return {
            "seq": np.zeros((10, 4), dtype=np.float32),
            "seq_mask": np.ones(10, dtype=np.float32),
            "account": np.zeros(6, dtype=np.float32),
            "trade_setup_mask": trade_mask,
            "candidate_ids": np.asarray(
                [candidate_geometry_slot_semantics(slot)[0] for slot in range(count)],
                dtype=np.int64,
            ),
            "candidate_features": candidate_features,
            "candidate_mask": candidate_mask,
        }

    def reset(
        self, *, seed: int | None = None, options: dict[str, object] | None = None
    ) -> tuple[dict[str, npt.NDArray[Any]], dict[str, object]]:
        super().reset(seed=seed)
        return self._observation(), {}

    def step(
        self, action: npt.NDArray[np.float32]
    ) -> tuple[dict[str, npt.NDArray[Any]], float, bool, bool, dict[str, object]]:
        del action
        return self._observation(), 0.0, False, False, {}


def _config() -> Any:
    return OmegaConf.create(
        {
            "env": {
                "n_envs": 1,
                "obs_window": 10,
                "strategy_actions": True,
                "trade_setup_actions": True,
                "candidate_geometry_actions": True,
            },
            "agent": {
                "arch": "tcn",
                "head_arch": {"tcn": [32]},
                "tcn": {
                    "latent_dim": 16,
                    "channels": [8, 8],
                    "kernel_size": 3,
                    "dropout": 0.0,
                },
            },
            "execution": {
                "limit_order_max_offset_atr": 1.0,
                "limit_order_max_ttl_bars": 60,
            },
            "ppo": {
                "policy_distribution": "trade_setup_candidate_geometry_v1",
                "actor_arch": "shared",
                "candidate_geometry": {"embedding_dim": 8, "execution_hidden_dim": 16},
                "n_steps": 2,
                "batch_size": 2,
                "n_epochs": 1,
                "learning_rate": 3.0e-4,
                "gamma": 0.99,
                "gae_lambda": 0.95,
                "clip_range": 0.2,
                "ent_coef": 0.01,
                "ent_coef_continuous": 0.001,
                "log_std_init": 0.0,
                "log_std_min": -0.7,
                "log_std_max": 0.0,
                "mode_prior_coef": 0.0,
                "rollout_buffer_on_device": False,
            },
        }
    )


def test_candidate_geometry_agent_build_learn_predict_and_checkpoint_roundtrip(
    tmp_path: Path,
) -> None:
    env = _CandidateGeometryEnv()
    model = build_agent(env, _config(), arch="tcn", device="cpu", seed=7)
    assert type(model.policy).__name__ == "CandidateGeometryClampedStdMultiInputPolicy"
    observation, _ = env.reset(seed=7)
    action, _ = model.predict(observation, deterministic=True)
    assert np.isfinite(action).all()
    model.learn(total_timesteps=4)

    checkpoint = tmp_path / "candidate_geometry.zip"
    model.save(checkpoint)
    loaded = PPO.load(checkpoint, device="cpu")
    validate_model_candidate_geometry_observation_schema(
        loaded, candidate_geometry_observation_schema()
    )
    loaded_action, _ = loaded.predict(observation, deterministic=True)
    assert np.allclose(loaded_action, model.predict(observation, deterministic=True)[0])
