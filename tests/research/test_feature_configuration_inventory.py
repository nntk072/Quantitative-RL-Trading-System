from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from omegaconf import OmegaConf
from scripts.research.analysis.features.build_feature_configuration_inventory import (
    build_inventory,
    load_profile_config,
)

from configuration.paths import repository_root

ROOT = repository_root(__file__)


@pytest.fixture(scope="module")
def inventory() -> dict[str, Any]:
    return build_inventory()


def test_feature_configuration_inventory_covers_runtime_profile_sources(
    inventory: dict[str, Any],
) -> None:
    profile_ids = {profile["profile_id"] for profile in inventory["profiles"]}

    assert inventory["generator"]["path"] == (
        "scripts/research/analysis/features/build_feature_configuration_inventory.py"
    )
    assert inventory["generator"]["sha256"]
    assert inventory["resolver_sources"]
    assert "base/default" in profile_ids
    assert {
        f"features/{path.stem}" for path in (ROOT / "config" / "features").glob("*.yaml")
    } <= profile_ids
    assert {
        f"research/{path.stem}" for path in (ROOT / "config" / "research").glob("*.yaml")
    } <= profile_ids
    assert {
        f"strategy_overlay/{path.stem}" for path in (ROOT / "config").glob("[123]_*.yaml")
    } <= profile_ids
    assert {
        f"experiment_run/{path.stem}"
        for path in (ROOT / "config" / "experiment_runs").glob("*.yaml")
    } <= profile_ids

    experiment_catalog = OmegaConf.load(ROOT / "config" / "experiments.yaml")
    assert {
        f"legacy_variant/{variant.name}" for variant in experiment_catalog.variants
    } <= profile_ids


def test_feature_configuration_inventory_resolves_list_valued_run_override(
    inventory: dict[str, Any],
) -> None:
    profile = next(
        profile
        for profile in inventory["profiles"]
        if profile["profile_id"]
        == "experiment_run/regime_tcn_context_r2_seed50_train2025_2m_normal_mtf_context_20261026"
    )

    assert profile["profile_kind"] == "experiment_run_spec"
    assert profile["features"]["ema_periods"] == [9, 21, 50, 200]


def test_legacy_distribution_profile_hash_includes_runtime_strategy_overlay(
    inventory: dict[str, Any],
) -> None:
    profile = next(
        item
        for item in inventory["profiles"]
        if item["profile_id"] == "legacy_variant/ablation_distribution"
    )
    cfg = load_profile_config(profile["profile_id"])
    feature_tree = OmegaConf.to_container(cfg.features, resolve=True)
    encoded = json.dumps(feature_tree, sort_keys=True, separators=(",", ":")).encode()

    assert hashlib.sha256(encoded).hexdigest() == profile["feature_config_sha256"]
    assert cfg.features.include_pd_context is True
    assert profile["source_paths"][-1]["path"] == "config/3_distribution.yaml"
