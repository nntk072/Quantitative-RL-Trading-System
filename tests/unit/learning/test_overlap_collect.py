"""Overlapped collection must consume the whole budget exactly and never leave a thread running."""

from __future__ import annotations

from typing import Any

from omegaconf import OmegaConf

from learning.rl.agent import build_agent
from simulation.environment.env import TradingEnv
from tests.unit.models.test_sac_agent import make_env


def _cfg(overlap: bool) -> Any:
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
                "overlap_collect": overlap,
            },
        }
    )


def _env() -> TradingEnv:
    source = make_env(continuous=True)
    return TradingEnv(
        source.bars,
        source.features,
        strategy_actions=True,
        agent_direction_control=True,
        allow_agent_sl_mode=False,
        obs_window=10,
        episodic=True,
    )


def test_overlap_consumes_exact_budget_and_drains() -> None:
    model = build_agent(_env(), _cfg(True), arch="tcn", algo="ppo")
    assert "collect_rollouts" in model.__dict__, "overlap collector not installed"
    model.learn(total_timesteps=64 * 4)
    assert model.num_timesteps == 64 * 4
    assert model._n_updates >= 4
    assert model.rollout_buffer is not None
    collector = model.__dict__.get("_overlap_collector")
    assert collector is None or collector._pending is None
