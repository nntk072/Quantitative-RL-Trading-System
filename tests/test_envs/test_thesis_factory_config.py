from __future__ import annotations

import numpy as np
import pandas as pd
from gymnasium import spaces
from omegaconf import OmegaConf
from stable_baselines3 import PPO

from configuration.loader import load_config
from decisioning.thesis import THESIS_CATEGORY_COUNT, thesis_id_from_box
from features.context.thesis_candidates import thesis_candidate_feature_columns
from learning.rl.agent import build_agent
from learning.rl.hybrid import HybridClampedStdMultiInputPolicy
from models.encoders import MTFReasoningEncoder
from simulation.environment.factory import build_eval_common, make_env
from tests.test_envs.test_account_normalization import _make_bars, _make_features
from trading.strategies import PO3IFVGStrategy


def test_thesis_observation_mode_flows_into_train_and_eval_env_kwargs() -> None:
    config = OmegaConf.load("config/base/default.yaml")
    config.env.strategy_actions = True
    config.env.thesis_actions = True

    eval_common, *_ = build_eval_common(config, arch="tcn")

    assert eval_common["strategy_actions"] is True
    assert eval_common["thesis_actions"] is True


def test_thesis_observation_mode_defaults_off() -> None:
    config = OmegaConf.load("config/base/default.yaml")

    eval_common, *_ = build_eval_common(config, arch="tcn")

    assert eval_common["thesis_actions"] is False


def test_mtf_reasoning_research_overlay_is_opt_in_and_complete() -> None:
    config = load_config(config_path="config/research/thesis_mtf_reasoning.yaml")

    assert config.env.strategy_actions is True
    assert config.env.thesis_actions is True
    assert config.env.agent_direction_control is False
    assert config.features.entry_ideas.enabled is True
    assert config.agent.arch == "mtf_reasoning"
    assert config.ppo.policy_distribution == "thesis_hybrid_v1"
    assert config.ppo.actor_arch == "shared"


def test_mtf_reasoning_overlay_builds_real_env_and_agent(tmp_path) -> None:
    config = load_config(config_path="config/research/thesis_mtf_reasoning.yaml")
    config.costs.use_tick_execution = False
    config.execution.randomized_fill_latency_ms = 0.0
    config.ppo.n_steps = 2
    config.ppo.batch_size = 2
    config.ppo.n_epochs = 1
    config.agent.mtf_reasoning.latent_dim = 32
    config.agent.mtf_reasoning.feedforward_dim = 64
    config.agent.mtf_reasoning.dropout = 0.0

    bars = _make_bars(120)
    features = _make_features(bars)
    thesis_columns = [name for _, name in thesis_candidate_feature_columns()]
    strategy_columns = list(PO3IFVGStrategy.required_features)
    features = pd.concat(
        [
            features,
            pd.DataFrame(0.0, index=features.index, columns=strategy_columns, dtype=np.float32),
            pd.DataFrame(0.0, index=features.index, columns=thesis_columns, dtype=np.float32),
        ],
        axis=1,
    )
    eval_common, *_ = build_eval_common(config)
    assert eval_common["mtf"] is True

    env = make_env(
        bars,
        features,
        config,
        algo="ppo",
        reward="dsr",
    )
    observation, _ = env.reset(seed=41)
    assert isinstance(env.observation_space, spaces.Dict)
    assert {
        "seq_m3",
        "seq_m5",
        "seq_m10",
        "seq_m15",
        "seq_m30",
        "seq_h1",
        "seq_h4",
        "seq_d1",
        "mask_m3",
        "mask_m5",
        "mask_m10",
        "mask_m15",
        "mask_m30",
        "mask_h1",
        "mask_h4",
        "mask_d1",
        "thesis_mask",
    } <= set(env.observation_space.spaces)
    assert observation["thesis_mask"].shape == (THESIS_CATEGORY_COUNT,)

    model = build_agent(
        env,
        config,
        arch=str(config.agent.arch),
        algo="ppo",
        device="cpu",
        seed=41,
    )
    assert isinstance(model.policy.features_extractor, MTFReasoningEncoder)
    assert isinstance(model.policy, HybridClampedStdMultiInputPolicy)
    model.learn(total_timesteps=2)
    action, _ = model.predict(observation, deterministic=False)
    assert thesis_id_from_box(float(action[0])) == 0

    checkpoint = tmp_path / "mtf_thesis_factory_smoke.zip"
    model.save(checkpoint)
    loaded = PPO.load(checkpoint, env=env, device="cpu")
    assert isinstance(loaded.policy.features_extractor, MTFReasoningEncoder)
    assert isinstance(loaded.policy, HybridClampedStdMultiInputPolicy)
    assert getattr(loaded, "_thesis_observation_schema", None) == env.thesis_observation_schema
    loaded_action, _ = loaded.predict(observation, deterministic=True)
    assert thesis_id_from_box(float(loaded_action[0])) == 0
