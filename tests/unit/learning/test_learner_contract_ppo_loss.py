"""PPO fixed-batch loss, gradient, inference, and normalization checks.

The frozen loss tape fixes the network weights, the minibatch, the old
log-probs and the targets. Expected values come from a float64 NumPy forward
pass in ``generate_tapes.py``. These tests load the same weights into a real
SB3 PPO model and compare its ``evaluate_actions`` outputs, the clipped
objective, the value loss, the gradient, and deterministic inference against
the tape. CPU only, float32 tolerance 1e-5.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.preprocessing import preprocess_obs
from torch.nn import functional as F

from tests.unit.learning.learner_contract_support import ContractEnv

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "learner_contract"
TOL = 1e-5
ARCH = {"net_arch": {"pi": [8], "vf": [8]}}


@pytest.fixture(scope="module")
def tape() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        (FIXTURE_DIR / "ppo_loss_tape.json").read_text(encoding="utf-8")
    )
    return payload


def _model(tape: dict[str, Any]) -> PPO:
    model = PPO(
        "MlpPolicy",
        ContractEnv(),
        policy_kwargs=ARCH,
        n_steps=16,
        batch_size=8,
        seed=0,
        device="cpu",
        verbose=0,
    )
    loaded = {
        name: torch.tensor(values, dtype=torch.float32) for name, values in tape["weights"].items()
    }
    model.policy.load_state_dict(loaded, strict=True)
    return model


def _batch(tape: dict[str, Any]) -> tuple[torch.Tensor, ...]:
    obs = torch.tensor(tape["obs"], dtype=torch.float32)
    actions = torch.tensor(tape["actions"], dtype=torch.float32)
    old_log_prob = torch.tensor(tape["old_log_prob"], dtype=torch.float32)
    advantages = torch.tensor(tape["advantages"], dtype=torch.float32)
    returns = torch.tensor(tape["returns"], dtype=torch.float32)
    return obs, actions, old_log_prob, advantages, returns


def _losses(
    log_prob: torch.Tensor,
    entropy: torch.Tensor,
    values: torch.Tensor,
    old_log_prob: torch.Tensor,
    advantages: torch.Tensor,
    returns: torch.Tensor,
    clip: float,
    ent_coef: float,
    vf_coef: float,
) -> tuple[torch.Tensor, ...]:
    """SB3's PPO objective, written out from per-row outputs."""
    ratio = torch.exp(log_prob - old_log_prob)
    surrogate = torch.min(ratio * advantages, torch.clamp(ratio, 1 - clip, 1 + clip) * advantages)
    policy_loss = -surrogate.mean()
    value_loss = F.mse_loss(returns, values)
    entropy_loss = -entropy.mean()
    total = policy_loss + ent_coef * entropy_loss + vf_coef * value_loss
    return policy_loss, value_loss, entropy_loss, total


def test_loaded_weights_match_the_frozen_architecture(tape: dict[str, Any]) -> None:
    model = _model(tape)
    state = model.policy.state_dict()
    assert set(state) == set(tape["weights"])
    for name, values in tape["weights"].items():
        assert tuple(state[name].shape) == tuple(np.asarray(values).shape), name


def test_evaluate_actions_matches_the_frozen_tape(tape: dict[str, Any]) -> None:
    model = _model(tape)
    obs, actions, _, _, _ = _batch(tape)
    with torch.no_grad():
        values, log_prob, entropy = model.policy.evaluate_actions(obs, actions)
    np.testing.assert_allclose(values.flatten().numpy(), tape["expected_value"], rtol=TOL, atol=TOL)
    np.testing.assert_allclose(log_prob.numpy(), tape["expected_log_prob"], rtol=TOL, atol=TOL)
    assert entropy is not None
    np.testing.assert_allclose(entropy.numpy(), tape["expected_entropy"], rtol=TOL, atol=TOL)


def test_clipped_objective_components_match_the_frozen_tape(tape: dict[str, Any]) -> None:
    model = _model(tape)
    obs, actions, old_log_prob, advantages, returns = _batch(tape)
    with torch.no_grad():
        values, log_prob, entropy = model.policy.evaluate_actions(obs, actions)
        assert entropy is not None
        policy_loss, value_loss, entropy_loss, total = _losses(
            log_prob,
            entropy,
            values.flatten(),
            old_log_prob,
            advantages,
            returns,
            tape["clip_range"],
            tape["ent_coef"],
            tape["vf_coef"],
        )
    assert policy_loss.item() == pytest.approx(tape["expected_policy_loss"], rel=TOL, abs=TOL)
    assert value_loss.item() == pytest.approx(tape["expected_value_loss"], rel=TOL, abs=TOL)
    assert entropy_loss.item() == pytest.approx(tape["expected_entropy_loss"], rel=TOL, abs=TOL)
    assert total.item() == pytest.approx(tape["expected_total_loss"], rel=TOL, abs=TOL)
    ratio = torch.exp(log_prob - old_log_prob).numpy()
    np.testing.assert_allclose(ratio, tape["expected_ratio"], rtol=TOL, atol=TOL)


def test_fixed_batch_exercises_the_clip_branch(tape: dict[str, Any]) -> None:
    # The objective is only meaningful if some rows are clipped and both signs of
    # the advantage occur, so the frozen batch must cover those cases.
    ratio = np.asarray(tape["expected_ratio"])
    clip = tape["clip_range"]
    assert tape["expected_clip_fraction"] > 0.0
    assert np.any(ratio > 1 + clip) and np.any(ratio < 1 - clip)
    advantages = np.asarray(tape["advantages"])
    assert np.any(advantages > 0) and np.any(advantages < 0)


def test_policy_gradient_matches_an_independent_autograd_path(tape: dict[str, Any]) -> None:
    obs, actions, old_log_prob, advantages, returns = _batch(tape)

    learner = _model(tape)
    values, log_prob, entropy = learner.policy.evaluate_actions(obs, actions)
    assert entropy is not None
    learner_loss = _losses(
        log_prob,
        entropy,
        values.flatten(),
        old_log_prob,
        advantages,
        returns,
        tape["clip_range"],
        tape["ent_coef"],
        tape["vf_coef"],
    )[-1]
    learner_loss.backward()  # type: ignore[no-untyped-call]
    learner_grads = {
        name: param.grad.detach().clone()
        for name, param in learner.policy.named_parameters()
        if param.grad is not None
    }

    weights = {
        name: torch.tensor(values_, dtype=torch.float32, requires_grad=True)
        for name, values_ in tape["weights"].items()
    }
    hidden = torch.tanh(
        obs @ weights["mlp_extractor.policy_net.0.weight"].T
        + weights["mlp_extractor.policy_net.0.bias"]
    )
    mean = hidden @ weights["action_net.weight"].T + weights["action_net.bias"]
    value_hidden = torch.tanh(
        obs @ weights["mlp_extractor.value_net.0.weight"].T
        + weights["mlp_extractor.value_net.0.bias"]
    )
    value = (value_hidden @ weights["value_net.weight"].T + weights["value_net.bias"]).flatten()
    std = torch.exp(weights["log_std"])
    log_prob_ref = torch.sum(
        -0.5 * ((actions - mean) / std) ** 2
        - weights["log_std"]
        - 0.5 * torch.log(torch.tensor(2.0 * torch.pi)),
        dim=1,
    )
    entropy_ref = torch.sum(
        0.5 + 0.5 * torch.log(torch.tensor(2.0 * torch.pi)) + weights["log_std"]
    ) * torch.ones_like(log_prob_ref)
    reference_loss = _losses(
        log_prob_ref,
        entropy_ref,
        value,
        old_log_prob,
        advantages,
        returns,
        tape["clip_range"],
        tape["ent_coef"],
        tape["vf_coef"],
    )[-1]
    reference_loss.backward()  # type: ignore[no-untyped-call]

    assert reference_loss.item() == pytest.approx(learner_loss.item(), rel=TOL, abs=TOL)
    for name, grad in learner_grads.items():
        reference = weights[name].grad
        assert reference is not None, name
        torch.testing.assert_close(grad, reference, rtol=TOL, atol=TOL, msg=name)


def test_deterministic_inference_returns_the_clipped_gaussian_mean(tape: dict[str, Any]) -> None:
    model = _model(tape)
    obs = np.asarray(tape["obs"], dtype=np.float32)
    expected = np.asarray(tape["expected_deterministic_actions"], dtype=np.float32)
    first, _ = model.predict(obs, deterministic=True)
    np.testing.assert_allclose(first, expected, rtol=TOL, atol=TOL)
    # Inference is stateless: an unrelated call in between must not change the result.
    model.predict(obs[:1] * 0.0, deterministic=True)
    second, _ = model.predict(obs, deterministic=True)
    np.testing.assert_array_equal(first, second)


def test_policy_takes_no_learner_side_observation_normalization(tape: dict[str, Any]) -> None:
    model = _model(tape)
    obs = np.asarray(tape["obs"], dtype=np.float32)
    processed = preprocess_obs(
        torch.as_tensor(obs), model.observation_space, normalize_images=False
    )
    assert isinstance(processed, torch.Tensor)
    np.testing.assert_array_equal(processed.numpy(), obs)
    assert not [key for key in model.policy.state_dict() if "rms" in key or "running" in key]
