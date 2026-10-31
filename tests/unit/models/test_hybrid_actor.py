"""Contracts for the hybrid categorical-continuous PPO action distribution."""

from __future__ import annotations

import gymnasium as gym
import numpy as np
import numpy.typing as npt
import pandas as pd
import pytest
import torch
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.torch_layers import CombinedExtractor

from decisioning.actions import build_action_schema
from decisioning.trade_setup import TRADE_SETUP_CATEGORY_COUNT, trade_setup_id_from_box
from learning.rl.callbacks import LearningDiagnosticsCallback
from learning.rl.hybrid import (
    HybridActorHeads,
    HybridBoxDistribution,
    HybridClampedStdMultiInputPolicy,
    ThesisConditionedActorHeads,
    ThesisConditionedClampedStdMultiInputPolicy,
    ThesisConditionedHybridBoxDistribution,
    TradeSetupConditionedClampedStdMultiInputPolicy,
    _encoded_centers,
)
from models.encoders import TCNEncoder
from trading.orders.selection import decode_tp_mode


def test_hybrid_mode_centers_match_existing_box_decoders() -> None:
    sl_tp = _encoded_centers("sl_mode", 0.1)
    units = tuple((value + 1.0) / 2.0 for value in sl_tp)
    assert int(units[0] * 3) == 0
    assert int(units[1] * 3) == 1
    assert abs(units[2] - 0.5) < 0.1
    assert int(units[3] * 3) == 2
    assert _encoded_centers("exit", 0.0) == (-0.5, 0.5)

    tp_centers = _encoded_centers("tp_mode", 0.1)
    decoded = [
        decode_tp_mode((center + 1.0) / 2.0, "fixed", 0.1, is_unit=True) for center in tp_centers
    ]
    assert decoded == [
        ("fixed", True),
        ("breakeven", True),
        ("fixed", False),
        ("trailing", True),
    ]


def test_hybrid_distribution_samples_box_actions_and_has_finite_gradients() -> None:
    coordinates = ("intensity", "risk", "sl_mode", "tp_mode", "exit")
    actor = HybridActorHeads(8, coordinates, {"sl_mode": 0.1, "tp_mode": 0.1})
    distribution = HybridBoxDistribution(actor, len(coordinates))
    latent = torch.randn(16, 8)
    means, logits = actor(latent)
    log_std = torch.zeros(len(actor.continuous_indices), requires_grad=True)
    distribution.proba_distribution(means, log_std, logits)

    actions = distribution.sample()
    assert actions.shape == (16, len(coordinates))
    for name, index in actor.categorical_indices.items():
        allowed = actions.new_tensor(actor.centers[name])
        assert torch.isfinite(actions[:, index]).all()
        assert torch.allclose(
            (actions[:, index : index + 1] - allowed[None, :]).abs().min(dim=1).values,
            torch.zeros(16),
        )
    assert torch.isfinite(actions[:, actor.continuous_indices]).all()
    assert torch.isfinite(distribution.log_prob(actions)).all()
    assert torch.isfinite(distribution.entropy()).all()

    objective = -distribution.log_prob(actions).mean() - distribution.entropy().mean()
    torch.autograd.backward(objective)
    assert actor.continuous_mean.weight.grad is not None
    assert actor.categorical_logits["sl_mode"].weight.grad is not None
    assert actor.categorical_logits["tp_mode"].weight.grad is not None
    assert actor.categorical_logits["exit"].weight.grad is not None
    assert torch.isfinite(actor.continuous_mean.weight.grad).all()


def test_hybrid_distribution_deterministic_mode_uses_valid_category_codes() -> None:
    coordinates = ("intensity", "sl_mode", "exit")
    actor = HybridActorHeads(4, coordinates, {"sl_mode": 0.1})
    distribution = HybridBoxDistribution(actor, len(coordinates))
    means, logits = actor(torch.randn(3, 4))
    distribution.proba_distribution(means, torch.zeros(1), logits)

    actions = distribution.mode()
    assert actions.shape == (3, len(coordinates))
    assert torch.isfinite(distribution.log_prob(actions)).all()


def test_thesis_hybrid_distribution_samples_only_each_rows_valid_candidates() -> None:
    coordinates = ("thesis", "risk", "exit")
    actor = HybridActorHeads(4, coordinates, {})
    distribution = HybridBoxDistribution(actor, len(coordinates))
    latent = torch.randn(3, 4)
    means, logits = actor(latent)
    masks = torch.zeros((3, TRADE_SETUP_CATEGORY_COUNT), dtype=torch.float32)
    masks[0, 0] = 1.0
    masks[1, 0] = 1.0
    masks[1, 5] = 1.0
    masks[1, 37] = 1.0
    masks[2, 2] = 1.0
    distribution.proba_distribution(
        means, torch.zeros(len(actor.continuous_indices)), logits, masks={"thesis": masks}
    )

    for deterministic in (False, True):
        actions = distribution.get_actions(deterministic=deterministic)
        assert torch.isfinite(actions).all()
        selected = [trade_setup_id_from_box(float(value.detach())) for value in actions[:, 0]]
        assert selected[0] == 0
        assert selected[1] in {0, 5, 37}
        assert selected[2] == 2
    assert torch.isfinite(distribution.log_prob(actions)).all()
    assert torch.isfinite(distribution.entropy()).all()


def test_thesis_conditioned_distribution_masks_and_conditions_execution() -> None:
    torch.manual_seed(91)
    coordinates = ("thesis", "risk", "sl_mode", "exit")
    actor = ThesisConditionedActorHeads(8, coordinates, {"sl_mode": 0.1})
    distribution = ThesisConditionedHybridBoxDistribution(actor, len(coordinates))
    latent = torch.randn(2, 8)
    thesis_logits = actor.thesis(latent)
    masks = torch.zeros((2, TRADE_SETUP_CATEGORY_COUNT), dtype=torch.float32)
    masks[0, [0, 5, 31]] = 1.0
    masks[1, [0, 12]] = 1.0
    distribution.proba_distribution(
        latent,
        torch.zeros(len(actor.continuous_indices), requires_grad=True),
        thesis_logits,
        masks={"thesis": masks},
    )

    assert distribution.thesis is not None
    assert torch.all(distribution.thesis.probs[~masks.bool()] == 0.0)
    first, _ = actor.execution(latent[:1], torch.tensor([5]))
    second, _ = actor.execution(latent[:1], torch.tensor([31]))
    assert not torch.allclose(first, second)
    # The selector receives only market latent; changing a proposed execution
    # thesis cannot feed back into primary-thesis logits.
    assert torch.equal(actor.thesis(latent), thesis_logits)

    for deterministic in (False, True):
        actions = distribution.get_actions(deterministic=deterministic)
        selected = [trade_setup_id_from_box(float(value.detach())) for value in actions[:, 0]]
        assert selected[0] in {0, 5, 31}
        assert selected[1] in {0, 12}
        assert torch.isfinite(distribution.log_prob(actions)).all()
        assert torch.isfinite(distribution.entropy()).all()
        assert torch.isfinite(distribution.thesis_entropy()).all()
    objective = -distribution.log_prob(actions).mean() - distribution.entropy().mean()
    torch.autograd.backward(objective)
    assert actor.thesis_logits.weight.grad is not None
    assert actor.thesis_embedding.weight.grad is not None
    assert actor.execution_body[0].weight.grad is not None
    assert actor.continuous_mean.weight.grad is not None
    assert actor.execution_categorical_logits["sl_mode"].weight.grad is not None
    assert actor.execution_categorical_logits["exit"].weight.grad is not None
    assert torch.isfinite(actor.thesis_embedding.weight.grad).all()


def test_thesis_conditioned_entropy_matches_full_category_reference() -> None:
    torch.manual_seed(17)
    coordinates = ("thesis", "risk", "sl_mode", "exit")
    actor = ThesisConditionedActorHeads(8, coordinates, {"sl_mode": 0.1})
    distribution = ThesisConditionedHybridBoxDistribution(actor, len(coordinates))
    latent = torch.randn(3, 8)
    thesis_logits = actor.thesis(latent)
    masks = torch.zeros((3, TRADE_SETUP_CATEGORY_COUNT), dtype=torch.float32)
    masks[0, 0] = 1.0
    masks[1, [0, 5]] = 1.0
    masks[2, [0, 12, 31, 84]] = 1.0
    log_std = torch.zeros(len(actor.continuous_indices))
    distribution.proba_distribution(
        latent,
        log_std,
        thesis_logits,
        masks={"thesis": masks},
    )

    actual = distribution.entropy()
    with torch.no_grad():
        all_ids = torch.arange(TRADE_SETUP_CATEGORY_COUNT).repeat(len(latent))
        all_latent = latent.repeat_interleave(TRADE_SETUP_CATEGORY_COUNT, dim=0)
        means, logits = actor.execution(all_latent, all_ids)
        normal = torch.distributions.Normal(means, log_std.exp().expand_as(means))
        normal_entropy = normal.entropy()  # type: ignore[no-untyped-call]
        conditional = normal_entropy.sum(dim=1)
        for values in logits.values():
            categorical = torch.distributions.Categorical(logits=values)
            conditional += categorical.entropy()  # type: ignore[no-untyped-call]
        conditional = conditional.reshape(len(latent), TRADE_SETUP_CATEGORY_COUNT)
        assert distribution.thesis is not None
        probs = distribution.thesis.probs
        reference = distribution.thesis_entropy() + (probs * conditional).sum(dim=1)

    assert torch.allclose(actual, reference, atol=1e-6, rtol=1e-6)
    assert torch.isfinite(actual).all()


def test_thesis_conditioned_ppo_update_and_checkpoint_roundtrip(tmp_path) -> None:
    env = _ThesisOverlayEnv()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    diagnostics_path = tmp_path / "learning_diagnostics.csv"
    model = PPO(
        ThesisConditionedClampedStdMultiInputPolicy,
        env,
        policy_kwargs={
            "hybrid_action_coordinates": ("thesis", "risk", "exit"),
            "thesis_mask_key": "thesis_mask",
            "thesis_embedding_dim": 16,
            "thesis_execution_hidden_dim": 32,
            "net_arch": {"pi": [32], "vf": [32]},
            "features_extractor_class": TCNEncoder,
            "features_extractor_kwargs": {
                "seq_len": 8,
                "n_features": 3,
                "account_dim": 6,
            },
        },
        n_steps=2,
        batch_size=2,
        n_epochs=1,
        device=device,
    )
    model.learn(
        total_timesteps=4,
        callback=LearningDiagnosticsCallback(diagnostics_path),
    )
    training_diagnostics = pd.read_csv(diagnostics_path)
    assert len(training_diagnostics) == 2
    assert training_diagnostics["thesis/entropy_mean_nats"].notna().all()
    assert (training_diagnostics["thesis/invalid_selection_count"] == 0).all()
    observation, _ = env.reset()
    predicted, _ = model.predict(observation, deterministic=True)
    assert trade_setup_id_from_box(float(predicted[0])) in {0, 12, 51}
    observation_tensor, _ = model.policy.obs_to_tensor(observation)
    _, log_prob, entropy = model.policy.evaluate_actions(
        observation_tensor, torch.as_tensor(predicted, device=model.device).reshape(1, -1)
    )
    stored_action_distribution = model.policy.get_distribution(observation_tensor)
    expected_log_prob = stored_action_distribution.log_prob(
        torch.as_tensor(predicted, device=model.device).reshape(1, -1)
    )
    assert torch.isfinite(log_prob).all()
    assert entropy is not None
    assert torch.isfinite(entropy).all()
    assert torch.allclose(log_prob, expected_log_prob)

    checkpoint = tmp_path / "thesis_conditioned_policy.zip"
    model.save(checkpoint)
    loaded = PPO.load(checkpoint, device=device)
    assert loaded.policy.thesis_embedding_dim == 16
    assert loaded.policy.thesis_execution_hidden_dim == 32
    loaded_action, _ = loaded.predict(observation, deterministic=True)
    assert np.allclose(loaded_action, predicted)


class _ThesisOverlayEnv(gym.Env[dict[str, npt.NDArray[np.float32]], npt.NDArray[np.float32]]):
    def __init__(self) -> None:
        self.observation_space = spaces.Dict(
            {
                "seq": spaces.Box(-1.0, 1.0, (8, 3), dtype=np.float32),
                "seq_mask": spaces.Box(0.0, 1.0, (8,), dtype=np.float32),
                "account": spaces.Box(-10.0, 10.0, (6,), dtype=np.float32),
                "thesis_mask": spaces.Box(
                    0.0, 1.0, (TRADE_SETUP_CATEGORY_COUNT,), dtype=np.float32
                ),
            }
        )
        self.action_space = spaces.Box(-1.0, 1.0, (3,), dtype=np.float32)

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, object] | None = None,
    ) -> tuple[dict[str, npt.NDArray[np.float32]], dict[str, object]]:
        super().reset(seed=seed)
        observation = {
            "seq": np.zeros((8, 3), dtype=np.float32),
            "seq_mask": np.ones(8, dtype=np.float32),
            "account": np.zeros(6, dtype=np.float32),
        }
        mask = np.zeros(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
        mask[[0, 12, 51]] = 1.0
        observation["thesis_mask"] = mask
        return observation, {}

    def step(
        self, action: npt.NDArray[np.float32]
    ) -> tuple[dict[str, npt.NDArray[np.float32]], float, bool, bool, dict[str, object]]:
        del action
        observation, _ = self.reset()
        return observation, 0.0, True, False, {}


class _TradeSetupOverlayEnv(_ThesisOverlayEnv):
    """Equivalent fake environment exposing the canonical observation key."""

    def __init__(self) -> None:
        super().__init__()
        assert isinstance(self.observation_space, spaces.Dict)
        mask_space = self.observation_space.spaces.pop("thesis_mask")
        self.observation_space.spaces["trade_setup_mask"] = mask_space

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, object] | None = None,
    ) -> tuple[dict[str, npt.NDArray[np.float32]], dict[str, object]]:
        observation, info = super().reset(seed=seed, options=options)
        observation["trade_setup_mask"] = observation.pop("thesis_mask")
        return observation, info


def test_thesis_hybrid_ppo_update_and_checkpoint_roundtrip(tmp_path) -> None:
    env = _ThesisOverlayEnv()
    model = PPO(
        HybridClampedStdMultiInputPolicy,
        env,
        policy_kwargs={
            "hybrid_action_coordinates": ("thesis", "risk", "exit"),
            "thesis_mask_key": "thesis_mask",
            "net_arch": {"pi": [32], "vf": [32]},
            "features_extractor_class": TCNEncoder,
            "features_extractor_kwargs": {
                "seq_len": 8,
                "n_features": 3,
                "account_dim": 6,
            },
        },
        n_steps=2,
        batch_size=2,
        n_epochs=1,
        device="cpu",
    )
    model.learn(total_timesteps=4)
    observation, _ = env.reset()
    for deterministic in (False, True):
        action, _ = model.predict(observation, deterministic=deterministic)
        assert trade_setup_id_from_box(float(action[0])) in {0, 12, 51}
    checkpoint = tmp_path / "thesis_hybrid_policy.zip"
    model.save(checkpoint)
    loaded = PPO.load(checkpoint, device="cpu")
    action, _ = loaded.predict(observation, deterministic=True)
    assert trade_setup_id_from_box(float(action[0])) in {0, 12, 51}


def test_trade_setup_conditioned_policy_checkpoint_roundtrip(tmp_path) -> None:
    env = _TradeSetupOverlayEnv()
    model = PPO(
        TradeSetupConditionedClampedStdMultiInputPolicy,
        env,
        policy_kwargs={
            "hybrid_action_coordinates": ("trade_setup", "risk", "exit"),
            "trade_setup_mask_key": "trade_setup_mask",
            "trade_setup_embedding_dim": 16,
            "trade_setup_execution_hidden_dim": 32,
            "net_arch": {"pi": [32], "vf": [32]},
            "features_extractor_class": CombinedExtractor,
        },
        n_steps=2,
        batch_size=2,
        n_epochs=1,
        device="cpu",
    )
    observation, _ = env.reset()
    prediction, _ = model.predict(observation, deterministic=True)
    assert trade_setup_id_from_box(float(prediction[0])) in {0, 12, 51}
    observation_tensor, _ = model.policy.obs_to_tensor(observation)
    _, log_prob, entropy = model.policy.evaluate_actions(
        observation_tensor, torch.as_tensor(prediction, device=model.device).reshape(1, -1)
    )
    assert torch.isfinite(log_prob).all()
    assert entropy is not None and torch.isfinite(entropy).all()
    checkpoint = tmp_path / "trade_setup_conditioned_policy.zip"
    model.save(checkpoint)
    loaded = PPO.load(checkpoint, device="cpu")
    loaded_prediction, _ = loaded.predict(observation, deterministic=True)
    assert np.allclose(loaded_prediction, prediction)


class _HybridOverlayEnv(gym.Env[dict[str, npt.NDArray[np.float32]], npt.NDArray[np.float32]]):
    def __init__(self) -> None:
        self.observation_space = spaces.Dict(
            {
                "seq": spaces.Box(-1.0, 1.0, (8, 3), dtype=np.float32),
                "seq_mask": spaces.Box(0.0, 1.0, (8,), dtype=np.float32),
                "account": spaces.Box(-10.0, 10.0, (6,), dtype=np.float32),
            }
        )
        self.action_space = spaces.Box(-1.0, 1.0, (12,), dtype=np.float32)

    def reset(
        self, *, seed: int | None = None, options: dict[str, object] | None = None
    ) -> tuple[dict[str, npt.NDArray[np.float32]], dict[str, object]]:
        super().reset(seed=seed)
        return {
            "seq": np.zeros((8, 3), dtype=np.float32),
            "seq_mask": np.ones(8, dtype=np.float32),
            "account": np.zeros(6, dtype=np.float32),
        }, {}

    def step(
        self, action: npt.NDArray[np.float32]
    ) -> tuple[dict[str, npt.NDArray[np.float32]], float, bool, bool, dict[str, object]]:
        observation, _ = self.reset()
        return observation, 0.0, True, False, {}


def test_hybrid_ppo_learns_and_roundtrips_policy(tmp_path) -> None:
    coordinates = build_action_schema(
        has_direction=True,
        has_sl_mode=True,
        has_tp_mode=True,
        has_multi_tp=True,
        has_simplex=True,
    ).names
    model = PPO(
        HybridClampedStdMultiInputPolicy,
        _HybridOverlayEnv(),
        policy_kwargs={
            "hybrid_action_coordinates": coordinates,
            "sl_mode_defer_threshold": 0.1,
            "tp_mode_defer_threshold": 0.1,
            "net_arch": {"pi": [32], "vf": [32]},
            "features_extractor_class": TCNEncoder,
            "features_extractor_kwargs": {
                "seq_len": 8,
                "n_features": 3,
                "account_dim": 6,
            },
        },
        n_steps=2,
        batch_size=2,
        n_epochs=1,
        device="cpu",
    )
    model.learn(total_timesteps=4)
    checkpoint = tmp_path / "hybrid_policy.zip"
    model.save(checkpoint)
    loaded = PPO.load(checkpoint, device="cpu")
    observation, _ = _HybridOverlayEnv().reset()
    predicted, _ = loaded.predict(observation, deterministic=True)
    assert predicted.shape == (12,)
    assert torch.isfinite(torch.as_tensor(predicted)).all()


@pytest.mark.skipif(not torch.cuda.is_available(), reason="requires CUDA or ROCm accelerator")
@pytest.mark.gpu
def test_hybrid_ppo_accelerator_update_and_roundtrip(tmp_path) -> None:
    coordinates = build_action_schema(
        has_direction=True,
        has_sl_mode=True,
        has_tp_mode=True,
        has_multi_tp=True,
        has_simplex=True,
    ).names
    env = _HybridOverlayEnv()
    model = PPO(
        HybridClampedStdMultiInputPolicy,
        env,
        policy_kwargs={
            "hybrid_action_coordinates": coordinates,
            "sl_mode_defer_threshold": 0.1,
            "tp_mode_defer_threshold": 0.1,
            "net_arch": {"pi": [32], "vf": [32]},
            "features_extractor_class": TCNEncoder,
            "features_extractor_kwargs": {
                "seq_len": 8,
                "n_features": 3,
                "account_dim": 6,
            },
        },
        n_steps=2,
        batch_size=2,
        n_epochs=1,
        device="cuda",
    )
    model.learn(total_timesteps=4)
    torch.cuda.synchronize()
    checkpoint = tmp_path / "hybrid_policy_accelerator.zip"
    model.save(checkpoint)
    loaded = PPO.load(checkpoint, device="cuda")
    observation, _ = env.reset()
    predicted, _ = loaded.predict(observation, deterministic=True)
    assert predicted.shape == (12,)
    assert torch.isfinite(torch.as_tensor(predicted)).all()
