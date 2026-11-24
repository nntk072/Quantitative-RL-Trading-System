"""The captured PPO update must fall back to SB3 wherever it cannot apply, including on CPU."""

from __future__ import annotations

from typing import Any

from omegaconf import OmegaConf

from learning.rl.agent import build_agent
from learning.rl.update_graph import _graph_supported, install_graphed_update
from simulation.environment.env import TradingEnv
from tests.unit.models.test_sac_agent import make_env


def _cfg() -> Any:
    return OmegaConf.create(
        {
            "env": {"obs_window": 10},
            "ppo": {
                "n_steps": 64,
                "batch_size": 32,
                "n_epochs": 1,
                "learning_rate": 3e-4,
                "gamma": 0.99,
                "gae_lambda": 0.95,
                "clip_range": 0.2,
                "ent_coef": 0.01,
                "ent_coef_continuous": 0.001,
                "log_std_init": 0.0,
                "log_std_min": -2.0,
                "log_std_max": 0.0,
            },
        }
    )


def _model() -> Any:
    source = make_env(continuous=True)
    env = TradingEnv(
        source.bars,
        source.features,
        strategy_actions=True,
        agent_direction_control=True,
        allow_agent_sl_mode=False,
        obs_window=10,
        episodic=True,
    )
    return build_agent(env, _cfg(), arch="tcn", algo="ppo")


def test_graph_update_is_refused_off_cuda() -> None:
    model = _model()
    assert _graph_supported(model) is False


def test_installed_update_falls_back_to_sb3_and_still_learns() -> None:
    model = _model()
    install_graphed_update(model)
    model.learn(total_timesteps=model.n_steps * model.n_envs)
    assert model._n_updates >= 1
