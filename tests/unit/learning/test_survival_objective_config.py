"""Undiscounted learning requirements for the survival objective."""

from __future__ import annotations

import pytest
from omegaconf import OmegaConf

from learning.rl.agent import _validate_survival_objective_config


@pytest.mark.unit
def test_survival_objective_accepts_undiscounted_ppo_and_sac() -> None:
    ppo = OmegaConf.create(
        {"env": {"reward_mode": "survival"}, "ppo": {"gamma": 1.0, "gae_lambda": 1.0}}
    )
    sac = OmegaConf.create({"env": {"reward_mode": "survival"}, "sac": {"gamma": 1.0}})

    _validate_survival_objective_config(ppo, "ppo")
    _validate_survival_objective_config(sac, "sac")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("algo", "cfg", "message"),
    [
        (
            "ppo",
            {"env": {"reward_mode": "survival"}, "ppo": {"gamma": 0.99, "gae_lambda": 1.0}},
            "PPO gamma=1 and gae_lambda=1",
        ),
        (
            "ppo",
            {"env": {"reward_mode": "survival"}, "ppo": {"gamma": 1.0, "gae_lambda": 0.95}},
            "PPO gamma=1 and gae_lambda=1",
        ),
        (
            "sac",
            {"env": {"reward_mode": "survival"}, "sac": {"gamma": 0.99}},
            "SAC gamma=1",
        ),
    ],
)
def test_survival_objective_rejects_discounted_returns(
    algo: str, cfg: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _validate_survival_objective_config(OmegaConf.create(cfg), algo)


@pytest.mark.unit
def test_other_reward_modes_keep_existing_discount_configuration() -> None:
    cfg = OmegaConf.create({"env": {"reward_mode": "dsr"}, "ppo": {"gamma": 0.99}})

    _validate_survival_objective_config(cfg, "ppo")
