from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest
import torch
from gymnasium import spaces
from omegaconf import OmegaConf

from decisioning.actions import build_action_schema, build_discrete_trading_action_schema
from decisioning.trade_setup import (
    CANDIDATE_GEOMETRY_FEATURE_NAMES,
    TRADE_SETUP_CATEGORY_COUNT,
    build_trade_setup_action_schema,
    candidate_geometry_slot_count,
)
from learning.rl.agent import (
    LegacyFourToFiveActionAdapter,
    _finalize_cuda_policy,
    _ppo_policy_and_ent_coef,
    persist_action_schema,
    validate_model_architecture,
)
from learning.rl.callbacks import (
    EpisodeEquityCallback,
    LearningDiagnosticsCallback,
    ProgressLoggerCallback,
)
from learning.rl.hybrid import (
    HybridActorHeads,
    HybridBoxDistribution,
    HybridClampedStdMultiInputPolicy,
    TradeSetupConditionedClampedStdMultiInputPolicy,
    _encoded_centers,
    distribution_validation_off,
    masks_prevalidated,
)


def test_hybrid_encoded_centers_reject_unsupported_or_unsafe_modes() -> None:
    with pytest.raises(ValueError, match="defer threshold"):
        _encoded_centers("sl_mode", 1.0 / 6.0)
    with pytest.raises(ValueError, match="unsupported categorical"):
        _encoded_centers("risk", 0.0)


def test_legacy_four_action_adapter_preserves_state_and_adds_structural_exit() -> None:
    state = object()
    actions = np.asarray([[0.2, -0.1, 0.4, 0.7]], dtype=np.float32)
    calls: list[bool] = []

    def predict(observation: object, *, deterministic: bool) -> tuple[np.ndarray[Any, Any], object]:
        del observation
        calls.append(deterministic)
        return actions, state

    model = SimpleNamespace(
        predict=predict,
        marker="delegated",
    )
    adapter = LegacyFourToFiveActionAdapter(model)

    adapted, returned_state = adapter.predict(np.zeros((1, 3)), deterministic=False)

    np.testing.assert_allclose(adapted, [[0.2, -0.1, 0.4, 0.7, -1.0]])
    assert adapted.dtype == actions.dtype
    assert returned_state is state
    assert calls == [False]
    assert adapter.marker == "delegated"
    with pytest.raises(ValueError, match="unexpected action shape"):
        LegacyFourToFiveActionAdapter(
            SimpleNamespace(predict=lambda *_args, **_kwargs: (np.zeros((2, 5)), None))
        ).predict(None)


def test_model_architecture_validation_allows_vae_and_fails_closed_without_extractor() -> None:
    model = SimpleNamespace(policy=SimpleNamespace(features_extractor=None))

    validate_model_architecture(model, "tcn", use_vae=True)
    with pytest.raises(ValueError, match="does not expose a feature extractor"):
        validate_model_architecture(model, "tcn")


def test_policy_factory_selects_semantic_gaussian_and_rejects_unknown_options() -> None:
    action_space = spaces.Box(-1.0, 1.0, (2,), dtype=np.float32)
    kwargs = {"net_arch": {"pi": [16]}}
    semantic_cfg = OmegaConf.create(
        {
            "ppo": {
                "actor_arch": "semantic_heads",
                "policy_distribution": "clamped_diagonal_gaussian",
                "ent_coef": 0.02,
                "ent_coef_continuous": 0.005,
                "log_std_min": -0.9,
            }
        }
    )

    policy, resolved_kwargs, entropy = _ppo_policy_and_ent_coef(semantic_cfg, kwargs, action_space)

    assert policy.__name__ == "SemanticClampedStdMultiInputPolicy"
    assert resolved_kwargs is not kwargs
    assert resolved_kwargs["net_arch"] == kwargs["net_arch"]
    assert resolved_kwargs["log_std_min"] == pytest.approx(-0.9)
    assert entropy == pytest.approx(0.005)

    bad_arch = OmegaConf.create(
        {
            "ppo": {
                "actor_arch": "custom",
                "policy_distribution": "clamped_diagonal_gaussian",
                "ent_coef": 0.0,
            }
        }
    )
    with pytest.raises(ValueError, match="unknown PPO actor_arch"):
        _ppo_policy_and_ent_coef(bad_arch, {}, action_space)
    bad_distribution = OmegaConf.create(
        {
            "ppo": {
                "actor_arch": "shared",
                "policy_distribution": "categorical_box",
                "ent_coef": 0.0,
            }
        }
    )
    with pytest.raises(ValueError, match="unknown PPO policy_distribution"):
        _ppo_policy_and_ent_coef(bad_distribution, {}, action_space)


def test_legacy_hybrid_factory_requires_typed_strategy_schema_and_returns_policy_contract() -> None:
    schema = build_action_schema(has_direction=True)
    config = OmegaConf.create(
        {
            "env": {"allow_ema_exit": True},
            "ppo": {
                "actor_arch": "shared",
                "policy_distribution": "hybrid_v1",
                "ent_coef": 0.03,
                "ent_coef_continuous": 0.007,
            },
        }
    )
    action_space = spaces.Box(-1.0, 1.0, (schema.width,), dtype=np.float32)

    policy, kwargs, entropy = _ppo_policy_and_ent_coef(config, {}, action_space, schema)

    assert policy is HybridClampedStdMultiInputPolicy
    assert kwargs["hybrid_action_coordinates"] == schema.names
    assert kwargs["trade_setup_mask_key"] is None
    assert entropy == pytest.approx(0.007)

    with pytest.raises(ValueError, match="declared legacy strategy ActionSchema"):
        _ppo_policy_and_ent_coef(config, {}, action_space)


def test_hybrid_setup_mask_is_required_and_contexts_restore_after_exception() -> None:
    actor = HybridActorHeads(4, ("trade_setup", "risk"), {})
    distribution = HybridBoxDistribution(actor, action_width=2)
    means, logits = actor(torch.zeros((1, 4)))

    with pytest.raises(ValueError, match="requires its eligibility mask"):
        distribution.proba_distribution(means, torch.zeros(1), logits)

    mask = torch.ones((1, logits["trade_setup"].shape[-1]))
    with masks_prevalidated():
        assert (
            distribution.proba_distribution(
                means, torch.zeros(1), logits, masks={"trade_setup": mask}
            )
            is distribution
        )
        with pytest.raises(RuntimeError), distribution_validation_off():
            raise RuntimeError("capture failed")
        # Nested context use restores the prevalidated state for its caller.
        assert (
            distribution.proba_distribution(
                means, torch.zeros(1), logits, masks={"trade_setup": mask}
            )
            is distribution
        )

    malformed = torch.ones_like(mask)
    malformed[0, 0] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        distribution.proba_distribution(
            means, torch.zeros(1), logits, masks={"trade_setup": malformed}
        )


def test_persist_action_schema_handles_continuous_and_discrete_contracts() -> None:
    policy = SimpleNamespace()
    continuous_env = SimpleNamespace(
        action_space=spaces.Box(-1.0, 1.0, shape=(1,), dtype=np.float32),
        strategy_actions=False,
    )
    continuous_model = SimpleNamespace(policy=policy)

    persist_action_schema(continuous_model, continuous_env)

    assert continuous_model._action_layout_key == "1"
    assert continuous_model._action_schema_version
    assert policy._action_layout_key == "1"
    assert not hasattr(continuous_model, "_action_schema")

    schema = build_discrete_trading_action_schema()
    discrete_policy = SimpleNamespace()
    discrete_model = SimpleNamespace(
        policy=discrete_policy, action_space=spaces.Discrete(schema.width)
    )
    discrete_env = SimpleNamespace(action_space=discrete_model.action_space, action_schema=schema)

    persist_action_schema(discrete_model, discrete_env)

    assert discrete_model._action_schema == schema.to_dict()
    assert discrete_policy._action_schema == schema.to_dict()


def test_persist_action_schema_requires_declared_strategy_coordinates() -> None:
    env = SimpleNamespace(
        action_space=spaces.Box(-1.0, 1.0, shape=(2,), dtype=np.float32),
        strategy_actions=True,
    )
    with pytest.raises(ValueError, match="declarative ActionSchema"):
        persist_action_schema(SimpleNamespace(policy=None), env)

    schema = build_action_schema(has_direction=True)
    mismatched_env = SimpleNamespace(
        action_space=spaces.Box(-1.0, 1.0, shape=(schema.width + 1,), dtype=np.float32),
        action_schema=schema,
    )
    with pytest.raises(ValueError, match="disagrees with declared schema width"):
        persist_action_schema(SimpleNamespace(policy=None), mismatched_env)


def test_cuda_policy_finalization_enables_each_shared_extractor_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shared = object()
    critic = object()
    policy = SimpleNamespace(
        features_extractor=shared,
        actor=SimpleNamespace(features_extractor=shared),
        critic=SimpleNamespace(features_extractor=critic),
        critic_target=SimpleNamespace(features_extractor=critic),
    )
    model = SimpleNamespace(policy=policy)
    dtype = object()
    enabled: list[tuple[object, object]] = []
    monkeypatch.setattr("learning.rl.agent.get_autocast_dtype", lambda *_args: dtype)
    monkeypatch.setattr(
        "learning.rl.agent.enable_extractor_autocast",
        lambda extractor, requested_dtype: enabled.append((extractor, requested_dtype)),
    )

    assert _finalize_cuda_policy(model, torch.device("cuda"), "bf16") is model

    assert enabled == [(shared, dtype), (critic, dtype)]


class _Logger:
    def __init__(self) -> None:
        self.values: dict[str, float] = {}

    def record(self, key: str, value: float) -> None:
        self.values[key] = float(value)


def test_diagnostics_callback_handles_discrete_actions_and_fallback_coordinate_names(
    tmp_path: Any,
) -> None:
    model = SimpleNamespace(
        num_timesteps=1,
        action_space=spaces.Discrete(3),
        logger=_Logger(),
        rollout_buffer=SimpleNamespace(
            actions=np.asarray([[0], [2]]),
            rewards=np.asarray([1.0, -1.0]),
            advantages=np.asarray([0.5, -0.5]),
            observations={},
        ),
        policy=SimpleNamespace(last_trade_setup_entropy=None),
    )
    callback = LearningDiagnosticsCallback(tmp_path / "discrete.csv")
    callback.init_callback(model)  # type: ignore[arg-type]
    callback.locals = {"infos": [None, {"constraints": {"metric": 0.25, "label": "skip"}}]}

    assert callback._on_step()
    callback._on_rollout_end()
    callback._on_training_end()

    row = callback._rows[0]
    assert row["action/coordinate_0_mean"] == 1.0
    assert row["constraints/mean_metric"] == 0.25
    assert "trade_setup/entropy_mean_nats" not in row
    assert callback._window_steps == 0


def test_progress_logger_skips_non_numeric_values_and_writes_rollout_rows(tmp_path: Any) -> None:
    model = SimpleNamespace(
        num_timesteps=12,
        logger=SimpleNamespace(name_to_value={"train/loss": 0.25, "train/ignored": object()}),
    )
    callback = ProgressLoggerCallback(tmp_path / "nested" / "progress.csv")
    callback.init_callback(model)  # type: ignore[arg-type]
    callback.num_timesteps = model.num_timesteps

    callback._on_rollout_end()
    callback._on_training_end()

    assert callback._rows == [{"timestep": 12, "train/loss": 0.25}]


def test_episode_equity_callback_warns_on_positive_reward_with_falling_equity(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    warnings: list[tuple[str, tuple[object, ...]]] = []
    monkeypatch.setattr(
        "learning.rl.callbacks.log.warning",
        lambda message, *args: warnings.append((message, args)),
    )
    callback = EpisodeEquityCallback(tmp_path / "episode_equity.csv")
    callback.init_callback(SimpleNamespace(num_timesteps=21))  # type: ignore[arg-type]
    callback.locals = {
        "dones": np.asarray([False, True]),
        "infos": [
            {"episode_equity": {"end_equity": 1.0}},
            {
                "episode_equity": {
                    "end_equity": 95.0,
                    "start_equity": 100.0,
                    "reward_sum": 0.5,
                    "n_trades": 2,
                    "breach_reason": "max_loss",
                }
            },
        ],
    }

    assert callback._on_step()
    callback._on_training_end()

    assert len(warnings) == 1
    assert "episode reward %.4f is positive" in warnings[0][0]
    assert warnings[0][1][-1] == "max_loss"


def test_hybrid_policy_uses_configured_setup_mask_and_rejects_missing_mask() -> None:
    policy_state = SimpleNamespace(
        setup_coordinate="trade_setup",
        trade_setup_mask_key="eligible_setups",
        _distribution_masks=None,
    )
    mask = torch.ones((2, 4))

    HybridClampedStdMultiInputPolicy._set_distribution_mask(
        cast(Any, policy_state), {"eligible_setups": mask}
    )

    assert policy_state._distribution_masks == {"trade_setup": mask}
    with pytest.raises(ValueError, match="configured eligibility mask"):
        HybridClampedStdMultiInputPolicy._set_distribution_mask(cast(Any, policy_state), {})


def test_candidate_geometry_policy_factory_binds_observation_and_execution_contract() -> None:
    config = OmegaConf.create(
        {
            "env": {"allow_ema_exit": True},
            "execution": {
                "limit_order_max_offset_atr": 1.25,
                "limit_order_max_ttl_bars": 45,
            },
            "ppo": {
                "actor_arch": "shared",
                "policy_distribution": "trade_setup_candidate_geometry_v1",
                "candidate_geometry": {"embedding_dim": 12, "execution_hidden_dim": 24},
                "ent_coef": 0.01,
                "ent_coef_continuous": 0.004,
            },
        }
    )
    action_schema = build_trade_setup_action_schema(has_entry_execution=True)
    slots = candidate_geometry_slot_count()
    observation_space = spaces.Dict(
        {
            "trade_setup_mask": spaces.Box(
                0.0, 1.0, (TRADE_SETUP_CATEGORY_COUNT,), dtype=np.float32
            ),
            "candidate_ids": spaces.Box(
                0, TRADE_SETUP_CATEGORY_COUNT - 1, (slots,), dtype=np.int64
            ),
            "candidate_features": spaces.Box(
                -1.0, 1.0, (slots, len(CANDIDATE_GEOMETRY_FEATURE_NAMES)), dtype=np.float32
            ),
            "candidate_mask": spaces.Box(
                np.zeros((slots,), dtype=np.bool_),
                np.ones((slots,), dtype=np.bool_),
                (slots,),
                dtype=cast(Any, np.bool_),
            ),
        }
    )
    action_space = spaces.Box(-1.0, 1.0, (action_schema.width,), dtype=np.float32)

    policy, kwargs, entropy_coef = _ppo_policy_and_ent_coef(
        config, {"net_arch": {"pi": [32]}}, action_space, action_schema, observation_space
    )

    assert policy.__name__ == "CandidateGeometryClampedStdMultiInputPolicy"
    assert kwargs["candidate_ids_key"] == "candidate_ids"
    assert kwargs["candidate_features_key"] == "candidate_features"
    assert kwargs["candidate_mask_key"] == "candidate_mask"
    assert kwargs["candidate_embedding_dim"] == 12
    assert kwargs["candidate_execution_hidden_dim"] == 24
    assert kwargs["max_limit_offset_atr"] == 1.25
    assert kwargs["max_limit_ttl_bars"] == 45
    assert entropy_coef == pytest.approx(0.004)


def test_conditioned_policy_factory_binds_semantic_action_and_execution_dimensions() -> None:
    schema = build_trade_setup_action_schema(has_sl_mode=True)
    observation_space = spaces.Dict(
        {"trade_setup_mask": spaces.Box(0.0, 1.0, (TRADE_SETUP_CATEGORY_COUNT,), dtype=np.float32)}
    )
    config = OmegaConf.create(
        {
            "env": {
                "allow_ema_exit": True,
                "sl_mode_defer_threshold": 0.08,
                "tp_mode_defer_threshold": 0.12,
            },
            "ppo": {
                "actor_arch": "shared",
                "policy_distribution": "trade_setup_conditioned_v1",
                "trade_setup_conditioned": {"embedding_dim": 10, "execution_hidden_dim": 28},
                "log_std_init": -0.2,
                "log_std_min": -0.8,
                "log_std_max": 0.1,
                "mode_prior_coef": 0.003,
                "ent_coef": 0.02,
                "ent_coef_continuous": 0.006,
            },
        }
    )
    original_kwargs = {"net_arch": {"pi": [32]}}

    policy, kwargs, entropy_coef = _ppo_policy_and_ent_coef(
        config,
        original_kwargs,
        spaces.Box(-1.0, 1.0, (schema.width,), dtype=np.float32),
        schema,
        observation_space,
    )

    assert policy is TradeSetupConditionedClampedStdMultiInputPolicy
    assert kwargs is not original_kwargs
    assert kwargs["net_arch"] == original_kwargs["net_arch"]
    assert kwargs["hybrid_action_coordinates"] == schema.names
    assert kwargs["trade_setup_mask_key"] == "trade_setup_mask"
    assert kwargs["trade_setup_embedding_dim"] == 10
    assert kwargs["trade_setup_execution_hidden_dim"] == 28
    assert kwargs["sl_mode_defer_threshold"] == pytest.approx(0.08)
    assert kwargs["tp_mode_defer_threshold"] == pytest.approx(0.12)
    assert kwargs["log_std_init"] == pytest.approx(-0.2)
    assert kwargs["log_std_min"] == pytest.approx(-0.8)
    assert kwargs["log_std_max"] == pytest.approx(0.1)
    assert kwargs["mode_prior_coef"] == pytest.approx(0.003)
    assert entropy_coef == pytest.approx(0.006)


@pytest.mark.parametrize(
    ("actor_arch", "schema", "observation_space", "allow_ema_exit", "message"),
    [
        (
            "semantic_heads",
            "valid",
            "valid",
            True,
            "hybrid PPO distributions require ppo.actor_arch='shared'",
        ),
        (
            "shared",
            None,
            "valid",
            True,
            "requires its matching action schema",
        ),
        (
            "shared",
            "valid",
            spaces.Dict({"account": spaces.Box(-1.0, 1.0, (2,), dtype=np.float32)}),
            True,
            "requires the trade_setup_mask observation",
        ),
        (
            "shared",
            "valid",
            "valid",
            False,
            "exit coordinate to be active",
        ),
    ],
)
def test_conditioned_policy_factory_fails_closed_on_incompatible_contracts(
    actor_arch: str,
    schema: Any,
    observation_space: Any,
    allow_ema_exit: bool,
    message: str,
) -> None:
    valid_schema = build_trade_setup_action_schema(has_sl_mode=True)
    valid_observation_space = spaces.Dict(
        {"trade_setup_mask": spaces.Box(0.0, 1.0, (TRADE_SETUP_CATEGORY_COUNT,), dtype=np.float32)}
    )
    if schema == "valid":
        schema = valid_schema
    if observation_space == "valid":
        observation_space = valid_observation_space
    config = OmegaConf.create(
        {
            "env": {"allow_ema_exit": allow_ema_exit},
            "ppo": {
                "actor_arch": actor_arch,
                "policy_distribution": "trade_setup_conditioned_v1",
                "ent_coef": 0.01,
            },
        }
    )

    with pytest.raises(ValueError, match=message):
        _ppo_policy_and_ent_coef(
            config,
            {"net_arch": {"pi": [16]}},
            spaces.Box(-1.0, 1.0, (valid_schema.width,), dtype=np.float32),
            schema,
            observation_space,
        )
