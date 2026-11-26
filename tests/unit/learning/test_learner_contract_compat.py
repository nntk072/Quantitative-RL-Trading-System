"""Compatibility matrix for registered PPO/SAC model and action families.

Each family is built through the production ``build_agent`` path on a
synthetic CPU environment. Checks per family: the encoder lineage is accepted,
a weights-only save/load reproduces the deterministic action, the log-prob of
an action sampled from the policy equals the log-prob that ``evaluate_actions``
reports for the same action, and all outputs are finite. The hybrid
trade-setup family also checks that sampled setup categories are always
eligible under the stored mask.

Families covered here: SAC and PPO with the tcn, gru and transformer encoders,
PPO's clamped diagonal Gaussian, trade-setup hybrid, trade-setup conditioned,
and trade-setup candidate-geometry distributions. Not covered by this matrix:
``tcn_regime``, ``mtf*``, ``lite_tcn``, ``semantic_heads`` actor heads and
``hybrid_v1``, which need their own observation schemas. Their existing unit
tests cover construction.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
import torch
from gymnasium import spaces
from omegaconf import OmegaConf

from learning.rl.agent import build_agent, validate_model_architecture
from models.factory import encoder_for
from tests.unit.learning.test_candidate_geometry_agent import (
    _CandidateGeometryEnv,
    _config,
)
from tests.unit.models.test_sac_agent import make_env

CANDIDATE_KEYS = frozenset({"candidate_ids", "candidate_features", "candidate_mask"})


class _SetupOnlyEnv(_CandidateGeometryEnv):
    """Trade-setup observation without candidate geometry, for the hybrid heads."""

    def __init__(self) -> None:
        super().__init__()
        self.observation_space = spaces.Dict(
            {
                key: space
                for key, space in cast(spaces.Dict, self.observation_space).spaces.items()
                if key not in CANDIDATE_KEYS
            }
        )
        self.candidate_geometry_actions = False
        # The builder treats a missing candidate schema as "no candidate heads".
        self.candidate_geometry_observation_schema = None  # type: ignore[assignment]

    def _observation(self) -> dict[str, Any]:
        return {
            key: value for key, value in super()._observation().items() if key not in CANDIDATE_KEYS
        }


def _ppo_cfg(distribution: str) -> Any:
    cfg = copy.deepcopy(_config())
    cfg.ppo.policy_distribution = distribution
    cfg.env.candidate_geometry_actions = distribution == "trade_setup_candidate_geometry_v1"
    return cfg


def _sac_cfg() -> Any:
    return OmegaConf.create(
        {
            "env": {"obs_window": 10},
            "ppo": {"batch_size": 16},
            "sac": {
                "learning_rate": 3e-4,
                "buffer_size": 512,
                "batch_size": 16,
                "tau": 0.005,
                "gamma": 0.99,
                "train_freq": 1,
                "gradient_steps": 1,
                "ent_coef": 0.01,
                "learning_starts": 16,
            },
        }
    )


def _ppo_tcn_cfg(arch: str) -> Any:
    cfg = OmegaConf.create(
        {
            "env": {"obs_window": 10},
            "ppo": {
                "n_steps": 32,
                "batch_size": 16,
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
    cfg.arch = arch
    return cfg


def _stack(observations: list[dict[str, Any]]) -> dict[str, torch.Tensor]:
    return {
        key: torch.as_tensor(np.stack([obs[key] for obs in observations]))
        for key in observations[0]
    }


def _real_observations(env: Any, count: int) -> list[dict[str, Any]]:
    rng = np.random.default_rng(0)
    observation, _ = env.reset(seed=0)
    collected = [observation]
    while len(collected) < count:
        observation, _, terminated, truncated, _ = env.step(
            rng.uniform(-1.0, 1.0, size=env.action_space.shape).astype(np.float32)
        )
        collected.append(observation)
        if terminated or truncated:
            observation, _ = env.reset()
    return collected[:count]


def _env_and_cfg(family: str, arch: str) -> tuple[Any, Any, str, str]:
    """Return (env, cfg, algo, arch) for one matrix row."""
    if family == "sac":
        return make_env(continuous=True), _sac_cfg(), "sac", arch
    if family == "ppo_gaussian":
        return make_env(continuous=True), _ppo_tcn_cfg(arch), "ppo", arch
    if family == "ppo_trade_setup_hybrid":
        return _SetupOnlyEnv(), _ppo_cfg("trade_setup_hybrid_v1"), "ppo", "tcn"
    if family == "ppo_trade_setup_conditioned":
        return _SetupOnlyEnv(), _ppo_cfg("trade_setup_conditioned_v1"), "ppo", "tcn"
    if family == "ppo_candidate_geometry":
        return _CandidateGeometryEnv(), _ppo_cfg("trade_setup_candidate_geometry_v1"), "ppo", "tcn"
    raise AssertionError(family)


MATRIX: list[tuple[str, str]] = [
    ("sac", "tcn"),
    ("sac", "gru"),
    ("sac", "transformer"),
    ("ppo_gaussian", "tcn"),
    ("ppo_gaussian", "gru"),
    ("ppo_gaussian", "transformer"),
    ("ppo_trade_setup_hybrid", "tcn"),
    ("ppo_trade_setup_conditioned", "tcn"),
    ("ppo_candidate_geometry", "tcn"),
]


def _build(family: str, arch: str, seed: int) -> tuple[Any, Any, str]:
    env, cfg, algo, arch_name = _env_and_cfg(family, arch)
    model = build_agent(env, cfg, arch=arch_name, algo=algo, device="cpu", seed=seed)
    return env, model, algo


@pytest.mark.parametrize(("family", "arch"), MATRIX)
def test_family_builds_and_weights_only_round_trip_is_exact(
    family: str, arch: str, tmp_path: Path
) -> None:
    env, model, algo = _build(family, arch, seed=0)
    if algo == "ppo" and family == "ppo_gaussian":
        validate_model_architecture(model, arch)
    elif algo == "sac":
        expected = encoder_for(arch)
        for extractor in (
            model.policy.actor.features_extractor,
            model.policy.critic.features_extractor,
        ):
            assert isinstance(extractor, expected), type(extractor).__name__

    observation, _ = env.reset(seed=0)
    expected_action, _ = model.predict(observation, deterministic=True)
    assert np.all(np.isfinite(expected_action))
    assert np.all(expected_action >= env.action_space.low - 1e-6)
    assert np.all(expected_action <= env.action_space.high + 1e-6)

    path = tmp_path / f"{family}_{arch}"
    model.save(path)
    restored = type(model).load(path, device="cpu")
    actual_action, _ = restored.predict(observation, deterministic=True)
    np.testing.assert_array_equal(actual_action, expected_action)


@pytest.mark.parametrize(("family", "arch"), MATRIX)
def test_sampled_action_log_prob_matches_evaluate_actions(family: str, arch: str) -> None:
    env, model, algo = _build(family, arch, seed=1)
    batch = _stack(_real_observations(env, count=4))
    # Rollouts sample with the policy in eval mode (dropout off). Compare in the
    # same mode; the train-mode mismatch is characterized separately below.
    model.policy.set_training_mode(False)
    with torch.no_grad():
        if algo == "ppo":
            sampled, values, sampled_log_prob = model.policy(batch)
            _, evaluated_log_prob, entropy = model.policy.evaluate_actions(batch, sampled)
            assert entropy is not None
            assert torch.isfinite(entropy).all()
            assert torch.isfinite(values).all()
            torch.testing.assert_close(
                evaluated_log_prob, sampled_log_prob.flatten(), rtol=1e-5, atol=1e-5
            )
            assert torch.isfinite(sampled).all()
            evaluated = evaluated_log_prob
        else:
            evaluated = model.policy.actor.action_log_prob(batch)[0]
        assert torch.isfinite(evaluated).all()


def test_trade_setup_hybrid_samples_only_eligible_setup_categories() -> None:
    env, model, _ = _build("ppo_trade_setup_hybrid", "tcn", seed=2)
    observation, _ = env.reset(seed=0)
    mask = observation["trade_setup_mask"] > 0
    assert mask.sum() == 2  # the fixture makes exactly categories 0 and 1 eligible
    batch = _stack([observation] * 64)
    heads = model.policy.action_net
    setup_index = heads.categorical_indices["trade_setup"]
    centers = torch.tensor(heads.centers["trade_setup"], dtype=torch.float32)
    torch.manual_seed(0)
    with torch.no_grad():
        distribution = model.policy.get_distribution(batch)
        actions = distribution.get_actions(deterministic=False)
    classes = (actions[:, setup_index : setup_index + 1] - centers[None, :]).abs().argmin(dim=1)
    assert set(classes.tolist()) <= set(np.flatnonzero(mask).tolist())


def test_train_mode_dropout_changes_the_stored_action_log_prob() -> None:
    """Characterize a known PPO mismatch: rollouts use eval mode, updates use train mode.

    Old log-probs come from ``collect_rollouts`` with dropout off. The update
    recomputes log-probs with dropout on, so at unchanged weights the importance
    ratio is not exactly one. Changing this alters the default algorithm and is
    recorded for an owner decision. If a fix makes the two modes agree, this test
    must be updated together with that decision.
    """
    env, model, _ = _build("ppo_gaussian", "tcn", seed=3)
    batch = _stack(_real_observations(env, count=32))
    model.policy.set_training_mode(False)
    with torch.no_grad():
        sampled, _, eval_log_prob = model.policy(batch)
    model.policy.set_training_mode(True)
    torch.manual_seed(0)
    with torch.no_grad():
        _, train_log_prob, _ = model.policy.evaluate_actions(batch, sampled)
    model.policy.set_training_mode(False)
    difference = (train_log_prob - eval_log_prob.flatten()).abs()
    assert float(difference.max()) > 1e-6
