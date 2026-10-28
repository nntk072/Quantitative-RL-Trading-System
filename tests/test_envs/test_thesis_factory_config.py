from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from gymnasium import spaces
from omegaconf import OmegaConf
from stable_baselines3 import PPO

from configuration.loader import load_config
from decisioning.thesis import (
    THESIS_CATEGORY_COUNT,
    build_thesis_action_schema,
    thesis_id_from_box,
)
from features.context.thesis_candidates import thesis_candidate_feature_columns
from learning.rl.agent import build_agent
from learning.rl.hybrid import (
    HybridClampedStdMultiInputPolicy,
    ThesisConditionedClampedStdMultiInputPolicy,
)
from models.encoders import MTFReasoningEncoder
from simulation.environment.factory import build_eval_common, make_env, mtf_settings
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


@pytest.mark.parametrize(
    "arch",
    [
        "mtf_shared_tcn_reasoning",
        "mtf_m1_tcn_htf_lite_reasoning",
        "mtf_m1_tcn_htf_snapshot_reasoning",
    ],
)
def test_e_f_g_architectures_enable_mtf_observations(arch: str) -> None:
    config = OmegaConf.create({"agent": {"arch": arch}})

    use_mtf, windows = mtf_settings(config, arch)

    assert use_mtf is True
    assert set(windows) == {"m3", "m5", "m10", "m15", "m30", "h1", "h4", "d1"}


def test_mtf_reasoning_research_overlay_is_opt_in_and_complete() -> None:
    config = load_config(config_path="config/research/thesis_mtf_reasoning.yaml")

    assert config.env.strategy_actions is True
    assert config.env.thesis_actions is True
    assert config.env.agent_direction_control is False
    assert config.features.include_strategy_state is True
    assert config.features.entry_ideas.enabled is True
    assert config.agent.arch == "mtf_reasoning"
    assert config.ppo.policy_distribution == "thesis_hybrid_v1"
    assert config.ppo.actor_arch == "shared"


def test_mtf_reasoning_conditioned_overlay_is_opt_in_and_complete() -> None:
    config = load_config(config_path="config/research/thesis_mtf_reasoning_conditioned.yaml")

    assert config.env.strategy_actions is True
    assert config.env.thesis_actions is True
    assert config.agent.arch == "mtf_reasoning"
    assert config.ppo.policy_distribution == "thesis_conditioned_v1"
    assert config.ppo.thesis_conditioned.embedding_dim == 32
    assert config.ppo.thesis_conditioned.execution_hidden_dim == 128


def test_mtf_reasoning_2m_configs_are_matched_except_for_execution_conditioning() -> None:
    control = load_config(config_path="config/research/thesis_mtf_reasoning_2m.yaml")
    treatment = load_config(config_path="config/research/thesis_mtf_reasoning_conditioned_2m.yaml")

    for config in (control, treatment):
        assert config.env.n_envs == 8
        assert config.env.strategy_actions is True
        assert config.env.thesis_actions is True
        assert config.features.include_strategy_state is True
        assert config.agent.arch == "mtf_reasoning"
        assert config.ppo.n_steps == 2048
        assert config.ppo.batch_size == 512
        assert config.ppo.n_epochs == 15
        assert config.ppo.total_timesteps == 2_000_000
        assert config.ppo.checkpoint_freq == 250_000
        assert config.quality_execution.requested_n_envs == 8
        assert config.quality_execution.exact_n_envs is True

    assert control.ppo.policy_distribution == "thesis_hybrid_v1"
    assert treatment.ppo.policy_distribution == "thesis_conditioned_v1"
    assert control.ppo.thesis_conditioned == treatment.ppo.thesis_conditioned
    control_resolved = OmegaConf.to_container(control, resolve=True)
    treatment_resolved = OmegaConf.to_container(treatment, resolve=True)
    assert isinstance(control_resolved, dict)
    assert isinstance(treatment_resolved, dict)
    control_resolved["ppo"].pop("policy_distribution")
    treatment_resolved["ppo"].pop("policy_distribution")
    assert control_resolved == treatment_resolved
    action_schemas = [
        build_thesis_action_schema(
            has_sl_mode=bool(config.env.get("allow_agent_sl_mode", False)),
            has_tp_mode=bool(config.env.get("allow_agent_tp_mode", False)),
            has_multi_tp=bool(config.env.get("allow_multi_tp", False)),
            has_simplex=bool(
                config.env.get("allow_multi_tp", False) and config.env.get("allow_simplex", False)
            ),
        ).to_dict()
        for config in (control, treatment)
    ]
    assert action_schemas[0] == action_schemas[1]


@pytest.mark.parametrize(
    ("overlay", "expected_policy"),
    [
        ("thesis_mtf_reasoning.yaml", HybridClampedStdMultiInputPolicy),
        ("thesis_mtf_reasoning_conditioned.yaml", ThesisConditionedClampedStdMultiInputPolicy),
    ],
)
def test_mtf_reasoning_overlay_builds_real_env_and_agent(
    tmp_path, overlay, expected_policy
) -> None:
    config = load_config(config_path=f"config/research/{overlay}")
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
    assert type(model.policy) is expected_policy
    model.learn(total_timesteps=2)
    action, _ = model.predict(observation, deterministic=False)
    assert thesis_id_from_box(float(action[0])) == 0

    checkpoint = tmp_path / "mtf_thesis_factory_smoke.zip"
    model.save(checkpoint)
    loaded = PPO.load(checkpoint, env=env, device="cpu")
    assert isinstance(loaded.policy.features_extractor, MTFReasoningEncoder)
    assert type(loaded.policy) is expected_policy
    assert getattr(loaded, "_thesis_observation_schema", None) == env.thesis_observation_schema
    loaded_action, _ = loaded.predict(observation, deterministic=True)
    assert thesis_id_from_box(float(loaded_action[0])) == 0
