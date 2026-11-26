"""Exact-resume state for Stable-Baselines3 PPO and SAC learners.

A default ``model.save`` keeps weights and optimizer state but not the RNG
streams, the SAC replay buffer, the collector's last observation, or the
environment's internal state. Exact resume needs all of them. This module
captures and restores the learner-owned part. The environment state is opaque
to the learner: the caller passes it in and receives it back.

Weights-only load (``PPO.load`` / ``SAC.load``) is a different operation. It
restores inference behaviour and counters but does not reproduce a continued run.
"""

from __future__ import annotations

import copy
import pickle
import random
from typing import Any

import numpy as np
import torch

RESUME_STATE_SCHEMA = "learner-exact-resume-v1"
_SUPPORTED_ALGORITHMS = frozenset({"PPO", "SAC"})


def _clone_nested(value: Any) -> Any:
    """Return a detached copy of nested tensors, arrays and containers.

    Args:
        value: Value to copy.

    Returns:
        A copy that shares no storage with ``value``.
    """
    return copy.deepcopy(value)


def _optimizers(model: Any) -> dict[str, Any]:
    """Return the learner's optimizers keyed by role.

    Args:
        model: A Stable-Baselines3 PPO or SAC model.

    Returns:
        Mapping from role name to optimizer, in a fixed order.

    Raises:
        ValueError: If the model is not a supported algorithm.
    """
    name = type(model).__name__
    if name == "PPO":
        return {"policy": model.policy.optimizer}
    if name == "SAC":
        optimizers = {
            "actor": model.policy.actor.optimizer,
            "critic": model.policy.critic.optimizer,
        }
        if model.ent_coef_optimizer is not None:
            optimizers["ent_coef"] = model.ent_coef_optimizer
        return optimizers
    raise ValueError(f"exact resume is defined only for PPO and SAC, not {name}")


def capture_resume_state(model: Any, *, env_state: Any = None) -> dict[str, Any]:
    """Capture everything a continued run depends on, except the environment internals.

    Args:
        model: A Stable-Baselines3 PPO or SAC model.
        env_state: Opaque environment snapshot supplied by the caller. It is
            stored and returned unchanged.

    Returns:
        A dictionary holding policy, optimizer, counter, RNG, collector and
        replay state under :data:`RESUME_STATE_SCHEMA`.
    """
    algorithm = type(model).__name__
    if algorithm not in _SUPPORTED_ALGORITHMS:
        raise ValueError(f"exact resume is defined only for PPO and SAC, not {algorithm}")
    state: dict[str, Any] = {
        "schema": RESUME_STATE_SCHEMA,
        "algorithm": algorithm,
        "policy": _clone_nested(model.policy.state_dict()),
        "optimizers": {
            role: _clone_nested(optimizer.state_dict())
            for role, optimizer in _optimizers(model).items()
        },
        "num_timesteps": int(model.num_timesteps),
        "total_timesteps": int(model._total_timesteps),
        "current_progress_remaining": float(model._current_progress_remaining),
        "episode_num": int(model._episode_num),
        "n_updates": int(model._n_updates),
        "last_obs": _clone_nested(model._last_obs),
        "last_original_obs": _clone_nested(model._last_original_obs),
        "last_episode_starts": _clone_nested(model._last_episode_starts),
        "rng": {
            "python": random.getstate(),
            "numpy": np.random.get_state(),
            "torch": torch.get_rng_state(),
        },
        "replay_buffer": None,
        "log_ent_coef": None,
        "env_state": _clone_nested(env_state),
    }
    if algorithm == "SAC":
        state["log_ent_coef"] = (
            None if model.log_ent_coef is None else model.log_ent_coef.detach().clone()
        )
        state["replay_buffer"] = pickle.dumps(model.replay_buffer)
    return state


def restore_resume_state(model: Any, state: dict[str, Any]) -> Any:
    """Restore a captured state into a freshly built model with the same architecture.

    Args:
        model: A new PPO or SAC model with the same policy and optimizer shapes.
        state: A dictionary returned by :func:`capture_resume_state`.

    Returns:
        The opaque environment snapshot the caller must apply to its environment.

    Raises:
        ValueError: If the schema or algorithm does not match the model.
    """
    algorithm = type(model).__name__
    if state.get("schema") != RESUME_STATE_SCHEMA:
        raise ValueError(f"unsupported resume state schema: {state.get('schema')!r}")
    if state.get("algorithm") != algorithm:
        raise ValueError(
            f"resume state was captured from {state.get('algorithm')!r}, not {algorithm!r}"
        )
    model.policy.load_state_dict(_clone_nested(state["policy"]))
    optimizers = _optimizers(model)
    if set(optimizers) != set(state["optimizers"]):
        raise ValueError("resume state optimizer roles do not match the model")
    for role, optimizer in optimizers.items():
        optimizer.load_state_dict(_clone_nested(state["optimizers"][role]))
    if algorithm == "SAC" and state["log_ent_coef"] is not None:
        model.log_ent_coef.data.copy_(state["log_ent_coef"].to(model.log_ent_coef.device))
        model.replay_buffer = pickle.loads(state["replay_buffer"])
    model.num_timesteps = int(state["num_timesteps"])
    model._total_timesteps = int(state["total_timesteps"])
    model._current_progress_remaining = float(state["current_progress_remaining"])
    model._episode_num = int(state["episode_num"])
    model._n_updates = int(state["n_updates"])
    model._last_obs = _clone_nested(state["last_obs"])
    model._last_original_obs = _clone_nested(state["last_original_obs"])
    model._last_episode_starts = _clone_nested(state["last_episode_starts"])
    random.setstate(state["rng"]["python"])
    np.random.set_state(state["rng"]["numpy"])
    torch.set_rng_state(state["rng"]["torch"])
    return _clone_nested(state["env_state"])


__all__ = [
    "RESUME_STATE_SCHEMA",
    "capture_resume_state",
    "restore_resume_state",
]
