from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
import torch
from gymnasium import spaces
from omegaconf import OmegaConf

from decisioning.trade_setup import TRADE_SETUP_CATEGORY_COUNT
from learning.rl.agent import (
    LegacyFourToFiveActionAdapter,
    _finalize_cuda_policy,
    _ppo_policy_and_ent_coef,
    validate_model_architecture,
)
from learning.rl.hybrid import (
    HybridActorHeads,
    HybridBoxDistribution,
    HybridClampedStdMultiInputPolicy,
    TradeSetupConditionedActorHeads,
    TradeSetupConditionedClampedStdMultiInputPolicy,
    TradeSetupConditionedHybridBoxDistribution,
    _trade_setup_logits_width,
)


def test_trade_setup_mask_width_supports_both_hybrid_head_layouts() -> None:
    flat_actor = HybridActorHeads(4, ("trade_setup", "risk"), {})
    conditioned_actor = TradeSetupConditionedActorHeads(4, ("trade_setup", "risk"), {})

    assert _trade_setup_logits_width(flat_actor) == TRADE_SETUP_CATEGORY_COUNT
    assert _trade_setup_logits_width(conditioned_actor) == TRADE_SETUP_CATEGORY_COUNT
    with pytest.raises(ValueError, match="requires a trade-setup logits layer"):
        _trade_setup_logits_width(SimpleNamespace())


def test_hybrid_distribution_rejects_sampling_before_probability_binding() -> None:
    actor = HybridActorHeads(4, ("trade_setup", "risk"), {})
    distribution = HybridBoxDistribution(actor, action_width=2)
    actions = torch.zeros((1, 2))

    with pytest.raises(RuntimeError, match="call proba_distribution before sampling"):
        distribution.sample()
    with pytest.raises(RuntimeError, match="call proba_distribution before choosing actions"):
        distribution.mode()
    with pytest.raises(RuntimeError, match="call proba_distribution before evaluating actions"):
        distribution.log_prob(actions)
    with pytest.raises(RuntimeError, match="call proba_distribution before evaluating entropy"):
        distribution.entropy()
    with pytest.raises(RuntimeError, match="no trade-setup categorical head"):
        distribution.trade_setup_entropy()
    with pytest.raises(RuntimeError, match="no trade-setup categorical head"):
        distribution.trade_setup_probabilities()


def test_hybrid_policy_graph_features_fail_closed_on_cpu() -> None:
    policy = HybridClampedStdMultiInputPolicy(
        observation_space=spaces.Dict(
            {
                "state": spaces.Box(-1.0, 1.0, shape=(4,)),
                "account": spaces.Box(-1.0, 1.0, shape=(3,)),
            }
        ),
        action_space=spaces.Box(-1.0, 1.0, shape=(2,)),
        lr_schedule=lambda _progress: 1e-3,
        hybrid_action_coordinates=("exit", "risk"),
    )

    with pytest.raises(ValueError, match="feature graph requires the policy on a CUDA device"):
        policy.enable_feature_graph()
    with pytest.raises(ValueError, match="policy graph requires the policy on a CUDA device"):
        policy.enable_rollout_policy_graph()


def test_hybrid_graph_helpers_restore_feature_cache_and_route_inference_calls() -> None:
    graph_calls: list[tuple[object, object]] = []
    extractor = object()

    def graph(observation: object, selected: object) -> torch.Tensor:
        graph_calls.append((observation, selected))
        return torch.ones(1)

    graph_policy = SimpleNamespace(_feature_graph=graph, features_extractor=extractor)
    observation = {"state": torch.zeros((1, 2))}

    with torch.no_grad():
        features = HybridClampedStdMultiInputPolicy.extract_features(
            cast(Any, graph_policy), observation
        )

    assert isinstance(features, torch.Tensor)
    assert torch.equal(features, torch.ones(1))
    assert graph_calls == [(observation, extractor)]

    sentinel = object()
    capture_policy = SimpleNamespace(_feature_graph=sentinel)
    with (
        pytest.raises(RuntimeError, match="capture abort"),
        HybridClampedStdMultiInputPolicy._capture_context(cast(Any, capture_policy)),
    ):
        assert capture_policy._feature_graph is None
        raise RuntimeError("capture abort")
    assert capture_policy._feature_graph is sentinel


def test_conditioned_policy_validates_rollout_masks_and_persists_constructor_contract() -> None:
    policy = TradeSetupConditionedClampedStdMultiInputPolicy(
        observation_space=spaces.Dict(
            {
                "state": spaces.Box(-1.0, 1.0, shape=(4,)),
                "account": spaces.Box(-1.0, 1.0, shape=(3,)),
                "eligible": spaces.Box(0.0, 1.0, shape=(TRADE_SETUP_CATEGORY_COUNT,)),
            }
        ),
        action_space=spaces.Box(-1.0, 1.0, shape=(2,)),
        lr_schedule=lambda _progress: 1e-3,
        hybrid_action_coordinates=("trade_setup", "risk"),
        trade_setup_mask_key="eligible",
        trade_setup_embedding_dim=4,
        trade_setup_execution_hidden_dim=8,
    )
    mask = torch.zeros((2, TRADE_SETUP_CATEGORY_COUNT), dtype=torch.bool)
    mask[:, [1, 3]] = True

    policy.validate_rollout_masks({"eligible": mask})
    with pytest.raises(ValueError, match="only finite values"):
        invalid = mask.to(torch.float32)
        invalid[0, 0] = torch.nan
        policy.validate_rollout_masks({"eligible": invalid})

    policy._set_distribution_mask({"eligible": mask})
    distribution = policy._get_action_dist_from_latent(
        torch.zeros((2, policy.mlp_extractor.latent_dim_pi))
    )
    assert distribution.trade_setup_probabilities()[:, [0, 2]].count_nonzero() == 0
    assert policy.last_trade_setup_entropy is not None
    assert torch.isfinite(policy.last_trade_setup_entropy).all()
    parameters = policy._get_constructor_parameters()
    assert parameters["hybrid_action_coordinates"] == ("trade_setup", "risk")
    assert parameters["trade_setup_mask_key"] == "eligible"
    assert parameters["trade_setup_embedding_dim"] == 4
    assert parameters["trade_setup_execution_hidden_dim"] == 8


def test_hybrid_distribution_packs_masked_modes_and_scores_the_encoded_action() -> None:
    actor = HybridActorHeads(2, ("trade_setup", "sl_mode", "risk"), {"sl_mode": 0.1})
    distribution = HybridBoxDistribution(actor, action_width=3)
    means = torch.tensor([[0.25]])
    log_std = torch.zeros(1)
    setup_logits = torch.zeros((1, TRADE_SETUP_CATEGORY_COUNT))
    setup_logits[0, 1] = 2.0
    sl_mode_logits = torch.tensor([[0.0, 0.0, 3.0, 0.0]])
    setup_mask = torch.zeros_like(setup_logits, dtype=torch.bool)
    setup_mask[0, :2] = True

    distribution.proba_distribution(
        means,
        log_std,
        {"trade_setup": setup_logits, "sl_mode": sl_mode_logits},
        masks={"trade_setup": setup_mask},
    )
    action = distribution.mode()

    assert action.shape == (1, 3)
    assert float(action[0, actor.categorical_indices["trade_setup"]]) == pytest.approx(
        actor.centers["trade_setup"][1]
    )
    assert float(action[0, actor.categorical_indices["sl_mode"]]) == pytest.approx(0.0)
    assert float(action[0, actor.continuous_indices[0]]) == pytest.approx(0.25)
    probabilities = distribution.trade_setup_probabilities()
    assert probabilities[0, 2:].count_nonzero() == 0
    assert probabilities[0, 1] > probabilities[0, 0]
    assert torch.isfinite(distribution.log_prob(action)).all()
    assert torch.isfinite(distribution.entropy()).all()


@pytest.mark.parametrize(
    ("mask", "message"),
    [
        (torch.tensor([[float("nan"), 1.0]]), "only finite values"),
        (torch.zeros((1, 2)), "allow a category"),
    ],
)
def test_hybrid_setup_distribution_rejects_invalid_eligibility(
    mask: torch.Tensor, message: str
) -> None:
    actor = HybridActorHeads(2, ("trade_setup", "risk"), {})
    distribution = HybridBoxDistribution(actor, action_width=2)
    logits = torch.zeros((1, TRADE_SETUP_CATEGORY_COUNT))

    with pytest.raises(ValueError, match=message):
        distribution.proba_distribution(
            torch.zeros((1, 1)),
            torch.zeros(1),
            {"trade_setup": logits},
            masks={"trade_setup": mask},
        )


def test_conditioned_hybrid_distribution_requires_context_before_execution() -> None:
    actor = TradeSetupConditionedActorHeads(4, ("trade_setup", "risk"), {})
    distribution = TradeSetupConditionedHybridBoxDistribution(actor, action_width=2)

    with pytest.raises(RuntimeError, match="call proba_distribution before evaluating the policy"):
        distribution._selected_distributions(torch.zeros(1, dtype=torch.long))
    with pytest.raises(RuntimeError, match="call proba_distribution before sampling actions"):
        distribution.sample()
    with pytest.raises(RuntimeError, match="call proba_distribution before selecting an action"):
        distribution.mode()
    with pytest.raises(RuntimeError, match="call proba_distribution before evaluating actions"):
        distribution.log_prob(torch.zeros((1, 2)))
    with pytest.raises(RuntimeError, match="call proba_distribution before evaluating entropy"):
        distribution.entropy()


def test_conditioned_distribution_selects_masked_setup_and_scores_its_execution() -> None:
    actor = TradeSetupConditionedActorHeads(
        2, ("trade_setup", "sl_mode", "risk"), {"sl_mode": 0.1}, embedding_dim=2, hidden_dim=4
    )

    def execution(_market_latent: torch.Tensor, setup_ids: torch.Tensor):
        means = setup_ids.to(torch.float32).unsqueeze(1)
        sl_logits = torch.zeros((setup_ids.shape[0], 4))
        selected_sl = setup_ids.remainder(4)
        sl_logits.scatter_(1, selected_sl.unsqueeze(1), 3.0)
        return means, {"sl_mode": sl_logits}

    cast(Any, actor).execution = execution
    distribution = TradeSetupConditionedHybridBoxDistribution(actor, action_width=3)
    setup_logits = torch.zeros((2, TRADE_SETUP_CATEGORY_COUNT))
    setup_logits[0, 3] = 2.0
    setup_logits[1, 1] = 3.0
    setup_logits[1, 3] = 2.0
    mask = torch.zeros_like(setup_logits, dtype=torch.bool)
    mask[:, [1, 3]] = True
    latent = torch.zeros((2, 2))

    action = distribution.actions_from_params(
        latent,
        torch.zeros(1),
        setup_logits,
        masks={"trade_setup": mask},
        deterministic=True,
    )
    selected_ids = torch.tensor([3, 1])
    setup_centers = actor.center_tensor("trade_setup", action)
    sl_centers = actor.center_tensor("sl_mode", action)

    assert torch.allclose(action[:, 0], setup_centers[selected_ids])
    assert torch.allclose(action[:, 1], sl_centers[selected_ids.remainder(4)])
    assert torch.allclose(action[:, 2], selected_ids.float())

    expected_setup_log_prob = (
        torch.log_softmax(
            setup_logits.masked_fill(~mask, torch.finfo(setup_logits.dtype).min), dim=1
        )
        .gather(1, selected_ids.unsqueeze(1))
        .squeeze(1)
    )
    expected_conditional_log_prob = (
        torch.log_softmax(
            torch.nn.functional.one_hot(selected_ids.remainder(4), num_classes=4).float() * 3.0,
            dim=1,
        )
        .gather(1, selected_ids.remainder(4).unsqueeze(1))
        .squeeze(1)
    )
    expected_normal_log_prob = torch.ones(2) * (-0.5 * torch.log(torch.tensor(2.0 * torch.pi)))
    assert torch.allclose(
        distribution.log_prob(action),
        expected_setup_log_prob + expected_conditional_log_prob + expected_normal_log_prob,
        atol=1e-6,
    )


def test_conditioned_distribution_entropy_weights_only_eligible_setup_policies() -> None:
    actor = TradeSetupConditionedActorHeads(
        2, ("trade_setup", "sl_mode", "risk"), {"sl_mode": 0.1}, embedding_dim=2, hidden_dim=4
    )

    def execution(_market_latent: torch.Tensor, setup_ids: torch.Tensor):
        means = (0.1 * setup_ids.to(torch.float32)).unsqueeze(1)
        sl_logits = torch.zeros((setup_ids.shape[0], 4))
        sl_logits[:, 0] = 2.0
        sl_logits[:, 1] = setup_ids.to(torch.float32)
        return means, {"sl_mode": sl_logits}

    cast(Any, actor).execution = execution
    distribution = TradeSetupConditionedHybridBoxDistribution(actor, action_width=3)
    setup_logits = torch.zeros((1, TRADE_SETUP_CATEGORY_COUNT))
    mask = torch.zeros_like(setup_logits, dtype=torch.bool)
    mask[0, :2] = True
    distribution.proba_distribution(
        torch.zeros((1, 2)),
        torch.zeros(1),
        setup_logits,
        masks={"trade_setup": mask},
    )

    setup_entropy = torch.log(torch.tensor(2.0))
    normal_entropy = torch.tensor(0.5 * (1.0 + torch.log(torch.tensor(2.0 * torch.pi))))
    conditional_entropies = torch.stack(
        [
            cast(
                Any,
                torch.distributions.Categorical(
                    logits=torch.tensor([2.0, float(setup_id), 0.0, 0.0])
                ),
            ).entropy()
            for setup_id in (0, 1)
        ]
    )
    expected_entropy = setup_entropy + normal_entropy + conditional_entropies.mean()

    assert torch.allclose(distribution.trade_setup_probabilities()[0, :2], torch.tensor([0.5, 0.5]))
    assert distribution.trade_setup_probabilities()[0, 2:].count_nonzero() == 0
    assert torch.allclose(distribution.entropy(), expected_entropy.reshape(1), atol=1e-6)


def test_legacy_four_to_five_adapter_rejects_unexpected_policy_output_shape() -> None:
    class _LegacyModel:
        def predict(self, _observation: Any, *, deterministic: bool) -> tuple[Any, None]:
            assert deterministic is True
            return torch.zeros(5).numpy(), None

    adapter = LegacyFourToFiveActionAdapter(_LegacyModel())

    with pytest.raises(ValueError, match="unexpected action shape"):
        adapter.predict(None)


def test_vae_architecture_validation_defers_to_vae_checkpoint_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "learning.rl.agent.encoder_for",
        lambda _arch: pytest.fail("VAE feature architecture is validated by its own contract"),
    )

    validate_model_architecture(SimpleNamespace(), "not-a-sequence-encoder", use_vae=True)


def test_policy_configuration_keeps_discrete_actions_categorical() -> None:
    kwargs = {"net_arch": {"pi": [16]}}
    standard = OmegaConf.create(
        {"ppo": {"ent_coef": 0.03, "policy_distribution": "clamped_diagonal_gaussian"}}
    )

    policy, returned_kwargs, entropy_coefficient = _ppo_policy_and_ent_coef(
        standard, kwargs, spaces.Discrete(20)
    )

    assert policy == "MultiInputPolicy"
    assert returned_kwargs is kwargs
    assert entropy_coefficient == pytest.approx(0.03)

    hybrid = OmegaConf.create(
        {"ppo": {"ent_coef": 0.03, "policy_distribution": "trade_setup_hybrid_v1"}}
    )
    with pytest.raises(ValueError, match="requires a Box action space"):
        _ppo_policy_and_ent_coef(hybrid, kwargs, spaces.Discrete(20))


def test_cuda_policy_finalization_returns_early_without_cuda_policy() -> None:
    cpu_model = SimpleNamespace(policy=SimpleNamespace(features_extractor=object()))
    no_policy_model = SimpleNamespace()

    assert _finalize_cuda_policy(cpu_model, "cpu") is cpu_model
    assert _finalize_cuda_policy(no_policy_model, torch.device("cuda")) is no_policy_model
