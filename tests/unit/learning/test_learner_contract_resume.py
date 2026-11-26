"""Exact resume for SB3 PPO and SAC through ``learning.rl.resume``.

A continued run and a run resumed from a captured state must produce the same
parameters, counters and replay contents. The synthetic environment exposes its
own snapshot, which the caller supplies, because the environment is outside the
learner's ownership. CPU only; no market data.
"""

from __future__ import annotations

import random
from typing import Any

import numpy as np
import pytest
import torch

from learning.rl.resume import RESUME_STATE_SCHEMA, capture_resume_state, restore_resume_state
from tests.unit.learning.learner_contract_support import (
    ContractEnv,
    ppo_model,
    sac_model,
    state_dict_equal,
)


def _set_global_rng(rng: dict[str, Any]) -> None:
    """Put the process-wide RNG streams back where a captured run left them.

    The two models share the process-wide torch and NumPy streams, so the first
    run must not advance the stream the second run starts from.
    """
    random.setstate(rng["python"])
    np.random.set_state(rng["numpy"])
    torch.set_rng_state(rng["torch"])


def _env_snapshot(model: Any, env: ContractEnv) -> dict[str, Any]:
    """Capture the environment internals plus the SB3 Monitor flag that gates stepping."""
    return {"env": env.get_state(), "needs_reset": model.env.envs[0].needs_reset}


def _apply_env_snapshot(model: Any, env: ContractEnv, snapshot: dict[str, Any]) -> None:
    env.set_state(snapshot["env"])
    model.env.envs[0].needs_reset = snapshot["needs_reset"]


def test_sac_resume_from_captured_state_reproduces_the_continued_run() -> None:
    env_a = ContractEnv()
    continued = sac_model(seed=11, env=env_a)
    continued.learn(total_timesteps=40)
    state = capture_resume_state(continued, env_state=_env_snapshot(continued, env_a))

    env_b = ContractEnv()
    resumed = sac_model(seed=999, env=env_b)  # different seed and fresh env on purpose
    _apply_env_snapshot(resumed, env_b, restore_resume_state(resumed, state))

    continued.learn(total_timesteps=20, reset_num_timesteps=False)
    _set_global_rng(state["rng"])
    resumed.learn(total_timesteps=20, reset_num_timesteps=False)

    assert state_dict_equal(continued.policy.state_dict(), resumed.policy.state_dict())
    assert resumed.num_timesteps == continued.num_timesteps
    assert resumed._n_updates == continued._n_updates
    assert continued.log_ent_coef is not None and resumed.log_ent_coef is not None
    assert torch.equal(continued.log_ent_coef, resumed.log_ent_coef)
    assert resumed.replay_buffer is not None and continued.replay_buffer is not None
    assert resumed.replay_buffer.size() == continued.replay_buffer.size()


def test_ppo_resume_from_captured_state_reproduces_the_continued_run() -> None:
    env_a = ContractEnv()
    continued = ppo_model(seed=21, env=env_a)
    continued.learn(total_timesteps=32)
    state = capture_resume_state(continued, env_state=_env_snapshot(continued, env_a))

    env_b = ContractEnv()
    resumed = ppo_model(seed=5, env=env_b)
    _apply_env_snapshot(resumed, env_b, restore_resume_state(resumed, state))

    continued.learn(total_timesteps=32, reset_num_timesteps=False)
    _set_global_rng(state["rng"])
    resumed.learn(total_timesteps=32, reset_num_timesteps=False)

    assert state_dict_equal(continued.policy.state_dict(), resumed.policy.state_dict())
    assert resumed.num_timesteps == continued.num_timesteps


def test_resume_state_carries_the_schema_and_each_learner_role() -> None:
    sac = sac_model(seed=3)
    sac.learn(total_timesteps=40)
    sac_state = capture_resume_state(sac)
    assert sac_state["schema"] == RESUME_STATE_SCHEMA
    assert sac_state["algorithm"] == "SAC"
    assert set(sac_state["optimizers"]) == {"actor", "critic", "ent_coef"}
    assert sac_state["replay_buffer"] is not None

    ppo = ppo_model(seed=3)
    ppo.learn(total_timesteps=32)
    ppo_state = capture_resume_state(ppo)
    assert ppo_state["algorithm"] == "PPO"
    assert set(ppo_state["optimizers"]) == {"policy"}
    assert ppo_state["replay_buffer"] is None


def test_restore_rejects_a_state_from_another_algorithm() -> None:
    ppo = ppo_model(seed=4)
    ppo.learn(total_timesteps=32)
    state = capture_resume_state(ppo)
    with pytest.raises(ValueError, match="captured from 'PPO'"):
        restore_resume_state(sac_model(seed=4), state)


def test_restore_rejects_an_unknown_schema() -> None:
    ppo = ppo_model(seed=4)
    ppo.learn(total_timesteps=32)
    state = capture_resume_state(ppo)
    state["schema"] = "learner-exact-resume-v0"
    with pytest.raises(ValueError, match="unsupported resume state schema"):
        restore_resume_state(ppo_model(seed=4), state)


def test_captured_state_is_a_copy_that_later_training_cannot_mutate() -> None:
    model = ppo_model(seed=6)
    model.learn(total_timesteps=32)
    state = capture_resume_state(model)
    frozen = {key: value.clone() for key, value in state["policy"].items()}
    model.learn(total_timesteps=32, reset_num_timesteps=False)
    assert state_dict_equal(frozen, state["policy"])
