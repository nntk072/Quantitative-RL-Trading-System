from __future__ import annotations

from omegaconf import OmegaConf

from configuration.loader import load_config
from simulation.environment.factory import build_eval_common


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
