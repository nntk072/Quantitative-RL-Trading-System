"""Frozen PPO and hybrid-distribution tapes checked against the learner code.

The tapes live in ``tests/fixtures/learner_contract`` and are synthetic. Their
expected values come from float64 closed-form NumPy formulas in
``generate_tapes.py``, which does not call the code under test. These tests
pin the committed bytes to the generator, pin the action-schema centers, and
compare SB3's rollout GAE and the hybrid Box distribution against the tapes.
CPU only; float64 comparisons use 1e-9 and float32 production paths use 1e-5.

Tolerance rationale. The float32 CPU path rounds each operation to about 6e-8
relative error. The tapes have at most a few dozen operations per output, so the
accumulated error stays near 1e-6; 1e-5 leaves margin without hiding a real
change, because a logic defect moves values by orders of magnitude more. The
tolerances cover CPU float32 only. CUDA, TF32 and BF16 paths differ by more
than this and need their own measured tolerance (GPU timing is not run here).
Sampling streams are device-specific, so stochastic-sample equality is claimed
only for CPU seeds.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pytest
import torch
from gymnasium import spaces
from stable_baselines3.common.buffers import RolloutBuffer

from learning.rl.hybrid import HybridActorHeads, HybridBoxDistribution

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "learner_contract"
F64 = 1e-9
F32 = 1e-5


def _load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "learner_contract_generate_tapes", FIXTURE_DIR / "generate_tapes.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tape(name: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    return payload


@pytest.fixture(scope="module")
def ppo_tape() -> dict[str, Any]:
    return _tape("ppo_gae_tape.json")


@pytest.fixture(scope="module")
def hybrid_tape() -> dict[str, Any]:
    return _tape("hybrid_distribution_tape.json")


# --- fixture integrity ---------------------------------------------------------


def _assert_close(committed: Any, regenerated: Any, path: str) -> None:
    # Byte equality is not portable: libm rounding differs by platform, so values are compared at 1e-12.
    if isinstance(committed, dict):
        assert committed.keys() == regenerated.keys(), path
        for key in committed:
            _assert_close(committed[key], regenerated[key], f"{path}.{key}")
    elif isinstance(committed, list):
        assert len(committed) == len(regenerated), path
        for i, (a, b) in enumerate(zip(committed, regenerated, strict=True)):
            _assert_close(a, b, f"{path}[{i}]")
    elif isinstance(committed, float):
        assert math.isclose(committed, regenerated, rel_tol=1e-12, abs_tol=1e-12), path
    else:
        assert committed == regenerated, path


def test_committed_tapes_match_the_generator() -> None:
    generator = _load_generator()
    files = generator.build_all()
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"].keys() == files.keys()
    for name, regenerated in files.items():
        committed = (FIXTURE_DIR / name).read_bytes()
        assert hashlib.sha256(committed).hexdigest() == manifest["files"][name]["sha256"], name
        _assert_close(json.loads(committed), json.loads(regenerated), name)


def test_implementation_action_centers_match_the_frozen_schema(hybrid_tape: dict[str, Any]) -> None:
    heads = HybridActorHeads(
        hybrid_tape["latent_dim"], hybrid_tape["coordinates"], hybrid_tape["thresholds"]
    )
    assert set(heads.centers) == set(hybrid_tape["categorical_coordinates"])
    for name, centers in hybrid_tape["centers"].items():
        np.testing.assert_allclose(heads.centers[name], centers, rtol=F64, atol=F64)


# --- PPO rollout GAE and bootstrap rules --------------------------------------


def _rollout(
    tape: dict[str, Any], rewards: np.ndarray[Any, Any], last_values: list[float]
) -> RolloutBuffer:
    """Fill an SB3 rollout buffer from the tape and compute GAE with the given rewards."""
    n_steps, n_envs = tape["n_steps"], tape["n_envs"]
    buffer = RolloutBuffer(
        n_steps,
        spaces.Box(0.0, 1.0, (1,), dtype=np.float32),
        spaces.Box(-1.0, 1.0, (1,), dtype=np.float32),
        device="cpu",
        gamma=tape["gamma"],
        gae_lambda=tape["gae_lambda"],
        n_envs=n_envs,
    )
    values = np.asarray(tape["values"], dtype=np.float32)
    starts = np.asarray(tape["episode_starts"], dtype=np.float32)
    for step in range(n_steps):
        buffer.add(
            np.zeros((n_envs, 1), dtype=np.float32),
            np.zeros((n_envs, 1), dtype=np.float32),
            rewards[step].astype(np.float32),
            starts[step],
            torch.as_tensor(values[step]),
            torch.zeros(n_envs),
        )
    buffer.compute_returns_and_advantage(
        last_values=torch.as_tensor(np.asarray(last_values, dtype=np.float32)),
        dones=np.asarray(tape["dones_last"], dtype=np.float32),
    )
    return buffer


def _effective_rewards(tape: dict[str, Any]) -> np.ndarray[Any, Any]:
    """Return rewards with truncated steps bootstrapped by their terminal value."""
    return np.asarray(tape["expected_effective_rewards"], dtype=np.float64)


def test_collector_bootstrap_formula_matches_tape(ppo_tape: dict[str, Any]) -> None:
    rewards = np.asarray(ppo_tape["rewards"])
    terminal = np.asarray(ppo_tape["terminal_values"])
    truncated = np.asarray(ppo_tape["truncated"], dtype=float)
    effective = rewards + ppo_tape["gamma"] * terminal * truncated
    np.testing.assert_allclose(
        effective, ppo_tape["expected_effective_rewards"], rtol=F64, atol=F64
    )


def test_sb3_rollout_gae_and_returns_match_the_frozen_tape(ppo_tape: dict[str, Any]) -> None:
    buffer = _rollout(ppo_tape, _effective_rewards(ppo_tape), ppo_tape["last_values"])
    np.testing.assert_allclose(
        buffer.advantages, ppo_tape["expected_advantages"], rtol=F32, atol=F32
    )
    np.testing.assert_allclose(buffer.returns, ppo_tape["expected_returns"], rtol=F32, atol=F32)


def test_terminal_last_step_ignores_the_bootstrap_value(ppo_tape: dict[str, Any]) -> None:
    # Env 2 terminates on the final collected step, so its bootstrap value is masked out.
    rewards = _effective_rewards(ppo_tape)
    baseline = _rollout(ppo_tape, rewards, ppo_tape["last_values"])
    changed = list(ppo_tape["last_values"])
    changed[2] += 100.0
    shifted = _rollout(ppo_tape, rewards, changed)
    np.testing.assert_allclose(
        shifted.advantages[:, 2], baseline.advantages[:, 2], rtol=F32, atol=F32
    )
    # Env 1 is still open at the final step, so perturbing its bootstrap must move it.
    open_env = list(ppo_tape["last_values"])
    open_env[1] += 100.0
    moved = _rollout(ppo_tape, rewards, open_env)
    assert not np.allclose(moved.advantages[:, 1], baseline.advantages[:, 1])


def test_episode_boundary_stops_advantage_propagation(ppo_tape: dict[str, Any]) -> None:
    # Env 0 terminates at step 2, so steps 0-2 must not see rewards after the boundary.
    rewards = _effective_rewards(ppo_tape)
    baseline = _rollout(ppo_tape, rewards, ppo_tape["last_values"])
    perturbed = rewards.copy()
    perturbed[5, 0] += 50.0
    shifted = _rollout(ppo_tape, perturbed, ppo_tape["last_values"])
    np.testing.assert_allclose(
        shifted.advantages[:3, 0], baseline.advantages[:3, 0], rtol=F32, atol=F32
    )
    assert not np.allclose(shifted.advantages[3:, 0], baseline.advantages[3:, 0])


# --- hybrid Box distribution ---------------------------------------------------


def _build_distribution(
    tape: dict[str, Any], dtype: torch.dtype
) -> tuple[HybridBoxDistribution, dict[str, torch.Tensor], torch.Tensor, torch.Tensor]:
    heads = HybridActorHeads(tape["latent_dim"], tape["coordinates"], tape["thresholds"])
    heads = heads.to(dtype=dtype)
    means = torch.tensor(tape["means"], dtype=dtype, requires_grad=True)
    log_std = torch.tensor(tape["log_std"], dtype=dtype)
    logits = {
        name: torch.tensor(values, dtype=dtype, requires_grad=True)
        for name, values in tape["logits"].items()
    }
    mask = torch.tensor(tape["trade_setup_mask"], dtype=dtype)
    encoded = torch.tensor(tape["encoded_actions"], dtype=dtype)
    distribution = HybridBoxDistribution(heads, len(tape["coordinates"]))
    distribution.proba_distribution(
        means, log_std.expand(means.shape[0], means.shape[1]), logits, {"trade_setup": mask}
    )
    return distribution, {**logits, "means": means}, encoded, mask


def test_hybrid_log_prob_and_entropy_match_the_frozen_tape(hybrid_tape: dict[str, Any]) -> None:
    distribution, _, encoded, _ = _build_distribution(hybrid_tape, torch.float64)
    np.testing.assert_allclose(
        distribution.log_prob(encoded).detach().numpy(),
        hybrid_tape["expected_log_prob"],
        rtol=F64,
        atol=F64,
    )
    np.testing.assert_allclose(
        distribution.entropy().detach().numpy(), hybrid_tape["expected_entropy"], rtol=F64, atol=F64
    )


def test_hybrid_log_prob_and_entropy_match_tape_in_float32(hybrid_tape: dict[str, Any]) -> None:
    distribution, _, encoded, _ = _build_distribution(hybrid_tape, torch.float32)
    np.testing.assert_allclose(
        distribution.log_prob(encoded).detach().numpy(),
        hybrid_tape["expected_log_prob"],
        rtol=F32,
        atol=F32,
    )
    np.testing.assert_allclose(
        distribution.entropy().detach().numpy(), hybrid_tape["expected_entropy"], rtol=F32, atol=F32
    )


def test_hybrid_probabilities_match_tape_and_invalid_candidates_have_exact_zero(
    hybrid_tape: dict[str, Any],
) -> None:
    distribution, _, _, mask = _build_distribution(hybrid_tape, torch.float64)
    for name, expected in hybrid_tape["expected_probs"].items():
        probs = distribution.categorical[name].probs.detach().numpy()
        np.testing.assert_allclose(probs, expected, rtol=F64, atol=F64)
    probs = distribution.categorical["trade_setup"].probs.detach().numpy()
    assert np.all(probs[mask.numpy() == 0] == 0.0)


def test_hybrid_gradients_match_closed_form_and_leak_nothing_to_invalid_candidates(
    hybrid_tape: dict[str, Any],
) -> None:
    distribution, inputs, encoded, mask = _build_distribution(hybrid_tape, torch.float64)
    names = hybrid_tape["categorical_coordinates"]
    grads = torch.autograd.grad(
        distribution.log_prob(encoded).sum(),
        [inputs["means"], *(inputs[name] for name in names)],
    )
    np.testing.assert_allclose(
        grads[0].numpy(), hybrid_tape["expected_grad_means"], rtol=F64, atol=F64
    )
    for name, grad in zip(names, grads[1:], strict=True):
        np.testing.assert_allclose(
            grad.numpy(), hybrid_tape["expected_grad_logits"][name], rtol=F64, atol=F64
        )
    trade_setup_grad = grads[1 + names.index("trade_setup")].numpy()
    assert np.all(trade_setup_grad[mask.numpy() == 0] == 0.0)


def test_hybrid_sampled_actions_are_eligible_and_decode_to_the_sampled_class(
    hybrid_tape: dict[str, Any],
) -> None:
    torch.manual_seed(0)
    distribution, _, _, mask = _build_distribution(hybrid_tape, torch.float64)
    centers = torch.tensor(hybrid_tape["centers"]["trade_setup"], dtype=torch.float64)
    invalid = mask == 0
    row = torch.arange(mask.shape[0])
    for _ in range(200):
        actions = distribution.sample()
        assert torch.isfinite(actions).all()
        classes = (actions[:, 1:2] - centers[None, :]).abs().argmin(dim=1)
        assert not bool(invalid[row, classes].any()), "sampled a masked setup category"
        assert torch.isfinite(distribution.log_prob(actions)).all()


def test_hybrid_masked_rows_fail_closed_instead_of_producing_nan(
    hybrid_tape: dict[str, Any],
) -> None:
    heads = HybridActorHeads(
        hybrid_tape["latent_dim"], hybrid_tape["coordinates"], hybrid_tape["thresholds"]
    )
    means = torch.tensor(hybrid_tape["means"], dtype=torch.float64)
    log_std = torch.tensor(hybrid_tape["log_std"], dtype=torch.float64)
    logits = {
        name: torch.tensor(values, dtype=torch.float64)
        for name, values in hybrid_tape["logits"].items()
    }
    distribution = HybridBoxDistribution(heads, len(hybrid_tape["coordinates"]))

    all_masked = torch.tensor(hybrid_tape["trade_setup_mask"], dtype=torch.float64)
    all_masked[1] = 0.0
    with pytest.raises(ValueError, match="allow a category"):
        distribution.proba_distribution(
            means, log_std.expand_as(means), logits, {"trade_setup": all_masked}
        )

    nonfinite = torch.tensor(hybrid_tape["trade_setup_mask"], dtype=torch.float64)
    nonfinite[0, 0] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        distribution.proba_distribution(
            means, log_std.expand_as(means), logits, {"trade_setup": nonfinite}
        )

    with pytest.raises(ValueError, match="requires its eligibility mask"):
        distribution.proba_distribution(means, log_std.expand_as(means), logits, None)
