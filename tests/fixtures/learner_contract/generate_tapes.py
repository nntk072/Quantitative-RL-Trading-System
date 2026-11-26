"""Generate the frozen learner-contract tapes for PPO and SAC.

The tapes are synthetic: every number comes from a fixed NumPy seed or a
literal, never from broker or market data. Expected values are computed here
in float64 with closed-form NumPy formulas that do not call the learner code
under test, so the tests compare the implementation against an independent
oracle. Run ``python generate_tapes.py`` from this directory to rewrite the
JSON tapes and ``manifest.json``; ``tests/unit/learning/test_learner_contract_tapes.py``
fails if the committed files drift from this generator.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

GENERATOR_VERSION = "learner-contract-tapes-v1"
HERE = Path(__file__).resolve().parent
SEED = 20261126

PPO_GAE_TAPE = "ppo_gae_tape.json"
HYBRID_TAPE = "hybrid_distribution_tape.json"
MANIFEST = "manifest.json"

# Hybrid coordinate layout. ``trade_setup`` is the masked categorical head;
# ``entry_execution``, ``sl_mode``, ``tp_mode`` and ``exit`` are unmasked
# categorical heads; ``x0`` and ``x1`` are Gaussian coordinates.
HYBRID_COORDINATES = (
    "x0",
    "trade_setup",
    "x1",
    "entry_execution",
    "sl_mode",
    "tp_mode",
    "exit",
)
HYBRID_THRESHOLDS = {"sl_mode": 0.05, "tp_mode": 0.05}
HYBRID_LATENT_DIM = 4


def _as_list(values: np.ndarray[Any, Any]) -> Any:
    return np.asarray(values, dtype=np.float64).tolist()


def build_ppo_gae_tape() -> dict[str, Any]:
    """Build a PPO rollout tape with terminal, truncated and open-episode steps.

    Returns:
        JSON-serializable tape with raw inputs and float64 GAE expectations.
    """
    rng = np.random.default_rng(SEED)
    gamma = 0.99
    gae_lambda = 0.95
    n_steps, n_envs = 6, 3
    rewards = rng.normal(0.0, 1.0, size=(n_steps, n_envs))
    values = rng.normal(0.0, 0.5, size=(n_steps, n_envs))
    terminal_values = rng.normal(0.0, 0.5, size=(n_steps, n_envs))
    last_values = rng.normal(0.0, 0.5, size=(n_envs,))
    # Env 0: terminates at step 2. Env 1: truncates at step 1 (bootstrapped).
    # Env 2: terminates on the last collected step, so last_values is ignored.
    terminated = np.zeros((n_steps, n_envs), dtype=bool)
    truncated = np.zeros((n_steps, n_envs), dtype=bool)
    terminated[2, 0] = True
    truncated[1, 1] = True
    terminated[n_steps - 1, 2] = True
    episode_ends = terminated | truncated
    # SB3 stores a step's episode start on the step that follows the boundary.
    episode_starts = np.zeros((n_steps, n_envs), dtype=bool)
    episode_starts[1:] = episode_ends[:-1]
    dones_last = episode_ends[-1]
    # Truncated steps bootstrap the terminal observation value into the reward,
    # matching the rollout collector's contract.
    effective_rewards = rewards + gamma * terminal_values * truncated

    advantages = np.zeros((n_steps, n_envs), dtype=np.float64)
    last_gae = np.zeros(n_envs, dtype=np.float64)
    for step in reversed(range(n_steps)):
        if step == n_steps - 1:
            non_terminal = 1.0 - dones_last.astype(np.float64)
            next_values = last_values
        else:
            non_terminal = 1.0 - episode_starts[step + 1].astype(np.float64)
            next_values = values[step + 1]
        delta = effective_rewards[step] + gamma * next_values * non_terminal - values[step]
        last_gae = delta + gamma * gae_lambda * non_terminal * last_gae
        advantages[step] = last_gae
    returns = advantages + values

    return {
        "schema": "qrl.learner-contract.ppo-gae-tape.v1",
        "generator": GENERATOR_VERSION,
        "gamma": gamma,
        "gae_lambda": gae_lambda,
        "n_steps": n_steps,
        "n_envs": n_envs,
        "rewards": _as_list(rewards),
        "values": _as_list(values),
        "terminal_values": _as_list(terminal_values),
        "terminated": terminated.astype(int).tolist(),
        "truncated": truncated.astype(int).tolist(),
        "episode_starts": episode_starts.astype(int).tolist(),
        "last_values": _as_list(last_values),
        "dones_last": dones_last.astype(int).tolist(),
        "expected_effective_rewards": _as_list(effective_rewards),
        "expected_advantages": _as_list(advantages),
        "expected_returns": _as_list(returns),
    }


def _hybrid_centers() -> dict[str, list[float]]:
    """Return the frozen encoded centers for every categorical coordinate.

    The centers are part of the action-schema contract. They are read from the
    implementation once, when the tape is regenerated, and the test then pins
    the implementation to these stored values.
    """
    from learning.rl.hybrid import HybridActorHeads

    heads = HybridActorHeads(HYBRID_LATENT_DIM, HYBRID_COORDINATES, HYBRID_THRESHOLDS)
    return {name: [float(value) for value in values] for name, values in heads.centers.items()}


def _log_softmax_valid(
    logits: np.ndarray[Any, Any], valid: np.ndarray[Any, Any]
) -> np.ndarray[Any, Any]:
    masked = np.where(valid, logits, -np.inf)
    peak = np.max(masked, axis=-1, keepdims=True)
    shifted = masked - peak
    log_norm = np.log(np.sum(np.where(valid, np.exp(shifted), 0.0), axis=-1, keepdims=True))
    return np.where(valid, shifted - log_norm, -np.inf)


def build_hybrid_tape() -> dict[str, Any]:
    """Build a hybrid Box distribution tape with masked trade-setup rows.

    Returns:
        JSON-serializable tape with inputs, encoded actions and float64 expectations.
    """
    rng = np.random.default_rng(SEED + 1)
    centers = _hybrid_centers()
    n_rows = 4
    continuous = [name for name in HYBRID_COORDINATES if name not in centers]
    categorical = [name for name in HYBRID_COORDINATES if name in centers]
    width = {name: len(centers[name]) for name in categorical}

    means = rng.normal(0.0, 0.7, size=(n_rows, len(continuous)))
    log_std = rng.normal(-0.3, 0.2, size=(len(continuous),))
    logits = {name: rng.normal(0.0, 1.0, size=(n_rows, width[name])) for name in categorical}

    setup_width = width["trade_setup"]
    setup_valid = np.zeros((n_rows, setup_width), dtype=bool)
    setup_valid[0, :] = True  # every candidate eligible
    setup_valid[1, [3, 17]] = True  # two eligible candidates
    setup_valid[2, [setup_width - 1]] = True  # one eligible candidate
    setup_valid[3, [0, 1, 50, 108]] = True  # sparse, including both ends
    masks = {"trade_setup": setup_valid.astype(int)}

    # Sampled classes must be eligible; the executed action is these classes.
    classes = {name: rng.integers(0, width[name], size=n_rows) for name in categorical}
    classes["trade_setup"] = np.array([5, 17, setup_width - 1, 108])
    continuous_actions = means + rng.normal(0.0, 0.5, size=means.shape)

    encoded = np.zeros((n_rows, len(HYBRID_COORDINATES)))
    cont_positions = [HYBRID_COORDINATES.index(name) for name in continuous]
    encoded[:, cont_positions] = continuous_actions
    for name in categorical:
        position = HYBRID_COORDINATES.index(name)
        encoded[:, position] = np.asarray(centers[name])[classes[name]]

    sigma = np.exp(log_std)
    log_prob = np.zeros(n_rows)
    entropy = np.zeros(n_rows)
    probs: dict[str, Any] = {}
    grads_logits: dict[str, np.ndarray[Any, Any]] = {}
    normal_log_prob = (
        -0.5 * ((continuous_actions - means) / sigma) ** 2 - log_std - 0.5 * math.log(2.0 * math.pi)
    )
    normal_entropy = 0.5 + 0.5 * math.log(2.0 * math.pi) + log_std
    log_prob += normal_log_prob.sum(axis=1)
    entropy += np.broadcast_to(normal_entropy, means.shape).sum(axis=1)
    grads_means = (continuous_actions - means) / sigma**2

    for name in categorical:
        valid = setup_valid if name == "trade_setup" else np.ones_like(logits[name], dtype=bool)
        logp = _log_softmax_valid(logits[name], valid)
        p = np.where(valid, np.exp(logp), 0.0)
        probs[name] = p.tolist()
        rows = np.arange(n_rows)
        log_prob += logp[rows, classes[name]]
        safe_logp = np.where(valid, logp, 0.0)
        entropy += -np.sum(p * safe_logp, axis=1)
        onehot = np.zeros_like(p)
        onehot[rows, classes[name]] = 1.0
        grads_logits[name] = np.where(valid, onehot - p, 0.0)

    return {
        "schema": "qrl.learner-contract.hybrid-distribution-tape.v1",
        "generator": GENERATOR_VERSION,
        "coordinates": list(HYBRID_COORDINATES),
        "thresholds": HYBRID_THRESHOLDS,
        "latent_dim": HYBRID_LATENT_DIM,
        "continuous_coordinates": continuous,
        "categorical_coordinates": categorical,
        "centers": centers,
        "means": _as_list(means),
        "log_std": _as_list(log_std),
        "logits": {name: _as_list(values) for name, values in logits.items()},
        "trade_setup_mask": masks["trade_setup"].tolist(),
        "classes": {
            name: np.asarray(values).astype(int).tolist() for name, values in classes.items()
        },
        "encoded_actions": _as_list(encoded),
        "expected_log_prob": _as_list(log_prob),
        "expected_entropy": _as_list(entropy),
        "expected_probs": probs,
        "expected_grad_means": _as_list(grads_means),
        "expected_grad_logits": {name: _as_list(values) for name, values in grads_logits.items()},
    }


def _dump(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, sort_keys=True, indent=1) + "\n").encode("utf-8")


def build_all() -> dict[str, bytes]:
    """Return the serialized tape files keyed by file name.

    Returns:
        Mapping from tape file name to its canonical JSON bytes.
    """
    return {
        PPO_GAE_TAPE: _dump(build_ppo_gae_tape()),
        HYBRID_TAPE: _dump(build_hybrid_tape()),
    }


def build_manifest(files: dict[str, bytes]) -> bytes:
    """Return the manifest binding each tape to its SHA-256 digest.

    Args:
        files: Serialized tape bytes keyed by file name.

    Returns:
        Canonical JSON bytes for the manifest.
    """
    manifest = {
        "schema": "qrl.learner-contract.tape-manifest.v1",
        "generator": GENERATOR_VERSION,
        "seed": SEED,
        "files": {
            name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
            for name, data in sorted(files.items())
        },
    }
    return _dump(manifest)


def main() -> None:
    """Write every tape and the manifest into this directory."""
    files = build_all()
    for name, data in files.items():
        (HERE / name).write_bytes(data)
    (HERE / MANIFEST).write_bytes(build_manifest(files))


if __name__ == "__main__":
    main()
