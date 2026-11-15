"""Tests for learning-quality comparison families."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from omegaconf import OmegaConf

from configuration import load_config
from training.configuration.quality import (
    apply_quality_variant,
    get_quality_variant,
    load_quality_registry,
    quality_variant_metadata,
    quality_variant_resource_contract,
    validate_quality_resource_shape,
)
from training.setup.policy_diagnostics import _log_effective_ppo


def test_quality_registry_groups_variants_by_comparison() -> None:
    registry = load_quality_registry()
    assert registry.development_control == "ladder_a3_multi_tp"
    assert [str(family.id) for family in registry.families] == [
        "account_state",
        "rollout_geometry",
        "reward_objective",
        "action_distribution",
        "risk_constraints",
        "entry_lifecycle",
        "encoder_architecture",
    ]
    baseline = registry.families[0].variants[0]
    assert baseline.id == "account_state_baseline"
    assert baseline.status == "control"
    family, overrides = get_quality_variant("account_state_context")
    assert family == "account_state"
    assert overrides["env.observation_schema_version"] == "account-state-v2"


def test_quality_registry_rejects_unknown_override_path(tmp_path) -> None:
    registry_path = tmp_path / "quality.yaml"
    registry_path.write_text(
        """registry_version: 1
development_control: control
families:
  - id: control_comparison
    domain: environment
    control: control
    variants:
      - id: control
        parent: null
        status: control
        overrides: {env.typo_that_would_be_ignored: true}
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="does not exist in config/base/default.yaml"):
        load_quality_registry(registry_path)


def test_apply_quality_variant_clones_config_and_applies_only_declared_keys() -> None:
    base = load_config()
    base.env.n_envs = 8
    base.env.observation_schema_version = "v1"
    resolved = apply_quality_variant(base, "account_state_context")
    assert base.env.observation_schema_version == "v1"
    assert resolved.env.observation_schema_version == "account-state-v2"
    assert resolved.env.n_envs == 8
    assert resolved.env.strategy_actions is True
    assert resolved.env.allow_multi_tp is True
    assert resolved.agent.arch == "tcn"
    assert resolved.quality_diagnostics.enabled is True
    assert resolved.quality_variant_id == "account_state_context"


def test_dependent_comparison_refuses_to_run_before_winner_selection() -> None:
    with pytest.raises(ValueError, match="select the prior comparison winner"):
        apply_quality_variant(OmegaConf.create({}), "reward_risk_500")


def test_rollout_geometry_candidates_are_registered_but_fail_closed() -> None:
    for n_envs in (16, 32, 64):
        variant_id = f"rollout_{n_envs}_envs"
        family, overrides = get_quality_variant(variant_id)
        assert family == "rollout_geometry"
        assert overrides["env.n_envs"] == n_envs
        assert overrides["ppo.n_steps"] == 8192 // n_envs
        assert overrides["env.n_envs"] * overrides["ppo.n_steps"] == 8192
        assert quality_variant_resource_contract(variant_id) == {
            "exact_n_envs": True,
            "expected_n_envs": n_envs,
            "aggregate_rollout_steps": 8192,
        }
        with pytest.raises(ValueError, match="not implemented and selectable"):
            apply_quality_variant(OmegaConf.create({}), variant_id)


@pytest.mark.parametrize("n_envs", (16, 32, 64))
def test_rollout_geometry_requires_its_registered_environment_shape(n_envs: int) -> None:
    variant_id = f"rollout_{n_envs}_envs"
    validate_quality_resource_shape(
        variant_id,
        requested_n_envs=n_envs,
        effective_n_envs=n_envs,
        aggregate_rollout_steps=8192,
    )
    with pytest.raises(ValueError, match=f"requires exactly {n_envs} environments"):
        validate_quality_resource_shape(
            variant_id,
            requested_n_envs=n_envs,
            effective_n_envs=n_envs // 2,
            aggregate_rollout_steps=8192,
        )
    with pytest.raises(ValueError, match="requires requested_n_envs"):
        validate_quality_resource_shape(
            variant_id,
            requested_n_envs=n_envs // 2,
            effective_n_envs=n_envs // 2,
            aggregate_rollout_steps=8192,
        )
    with pytest.raises(ValueError, match="requires aggregate_rollout_steps=8192"):
        validate_quality_resource_shape(
            variant_id,
            requested_n_envs=n_envs,
            effective_n_envs=n_envs,
            aggregate_rollout_steps=4096,
        )


def test_quality_registry_rejects_unknown_resource_contract_field(tmp_path) -> None:
    registry_path = tmp_path / "quality.yaml"
    registry_path.write_text(
        """registry_version: 1
development_control: control
families:
  - id: control_comparison
    domain: environment
    control: control
    variants:
      - id: control
        parent: null
        status: control
        overrides: {}
        resource_contract: {invented_limit: 1}
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown resource contract keys"):
        load_quality_registry(registry_path)


def test_training_log_records_effective_rollout_and_update_geometry(caplog) -> None:
    cfg = load_config(["env.n_envs=16", "ppo.batch_size=64", "ppo.n_epochs=3", "ppo.n_steps=128"])
    model = SimpleNamespace(n_steps=8, n_envs=16, ent_coef=0.01)
    caplog.set_level(logging.INFO, logger="training.setup.policy_diagnostics")

    _log_effective_ppo(model, cfg)

    assert (
        "logical_n_envs=16 sb3_n_steps_per_env=8 aggregate_rollout_steps=128 "
        "batch_size=64 n_epochs=3 minibatches_per_epoch=2 updates_per_rollout=6"
    ) in caplog.text


def test_training_log_rejects_effective_environment_count_mismatch() -> None:
    cfg = load_config(["env.n_envs=16"])
    model = SimpleNamespace(n_steps=8, n_envs=8, ent_coef=0.01)
    with pytest.raises(RuntimeError, match="effective PPO n_envs=8"):
        _log_effective_ppo(model, cfg)


def test_sac_effective_log_does_not_require_ppo_rollout_fields(caplog) -> None:
    cfg = load_config(["env.n_envs=1", "sac.batch_size=8", "sac.buffer_size=64"])
    model = SimpleNamespace(n_envs=1)
    caplog.set_level(logging.INFO, logger="training.setup.policy_diagnostics")

    _log_effective_ppo(model, cfg, algo="sac")

    assert "SAC effective: logical_n_envs=1" in caplog.text
    assert "buffer_size=64" in caplog.text


def test_entry_lifecycle_has_three_explicit_arms_with_only_visibility_changed() -> None:
    registry = load_quality_registry()
    family = next(family for family in registry.families if family.id == "entry_lifecycle")
    arms = {str(variant.id): variant for variant in family.variants}
    assert set(arms) == {
        "visible_entry_lifecycle",
        "hidden_entry_lifecycle",
        "entry_lifecycle_disabled",
    }
    assert arms["visible_entry_lifecycle"].overrides["env.entry_state_machine"] is True
    assert arms["visible_entry_lifecycle"].overrides["env.entry_state_observation"] is True
    assert arms["hidden_entry_lifecycle"].overrides["env.entry_state_machine"] is True
    assert arms["hidden_entry_lifecycle"].overrides["env.entry_state_observation"] is False
    assert arms["entry_lifecycle_disabled"].overrides["env.entry_state_machine"] is False
    assert all(str(variant.status) == "implementation_unverified" for variant in arms.values())
    for variant_id in arms:
        with pytest.raises(
            ValueError, match="not implemented and selectable|select the prior comparison winner"
        ):
            apply_quality_variant(OmegaConf.create({}), variant_id)


def test_unverified_hybrid_policy_remains_fail_closed() -> None:
    with pytest.raises(
        ValueError, match="not implemented and selectable|select the prior comparison winner"
    ):
        apply_quality_variant(OmegaConf.create({}), "hybrid_action_distribution")


def test_unverified_registry_arms_are_all_fail_closed() -> None:
    registry = load_quality_registry()
    unverified = [
        str(variant.id)
        for family in registry.families
        for variant in family.variants
        if str(variant.get("status", "")) == "implementation_unverified"
    ]
    assert unverified
    for variant_id in unverified:
        with pytest.raises(
            ValueError, match="not implemented and selectable|select the prior comparison winner"
        ):
            apply_quality_variant(OmegaConf.create({}), variant_id)


def test_lagrangian_remains_blocked_until_parent_comparison_is_selected() -> None:
    base = OmegaConf.create({"ppo": {"n_steps": 8}})
    family, overrides = get_quality_variant("lagrangian_risk_constraints")
    assert family == "risk_constraints"
    assert overrides["constrained_rl.enabled"] is True
    registry = load_quality_registry()
    lagrangian = next(
        variant
        for family_config in registry.families
        for variant in family_config.variants
        if variant.id == "lagrangian_risk_constraints"
    )
    assert lagrangian.status == "implemented_unit_tested"
    with pytest.raises(ValueError, match="select the prior comparison winner"):
        apply_quality_variant(base, "lagrangian_risk_constraints")
    assert "constrained_rl" not in base


def test_quality_variant_provenance_names_its_comparison_family() -> None:
    metadata = quality_variant_metadata("lagrangian_risk_constraints")
    assert metadata["family"] == "risk_constraints"
    assert metadata["domain"] == "trading"
    assert "stage" not in metadata


def test_registry_declares_hidden_entry_lifecycle_arm() -> None:
    registry = load_quality_registry()
    entry_lifecycle = next(family for family in registry.families if family.id == "entry_lifecycle")
    hidden = next(
        variant for variant in entry_lifecycle.variants if variant.id == "hidden_entry_lifecycle"
    )
    assert hidden.overrides["env.entry_state_machine"] is True
    assert hidden.overrides["env.entry_state_observation"] is False
