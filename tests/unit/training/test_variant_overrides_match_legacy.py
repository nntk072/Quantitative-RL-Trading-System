"""The resolver's overrides must reproduce the legacy merge_variant_cfg config."""

from __future__ import annotations

import pytest

omegaconf = pytest.importorskip("omegaconf")
from omegaconf import DictConfig, OmegaConf  # noqa: E402

from configuration import apply_overrides, load_config  # noqa: E402
from training.configuration.variant_resolution import (  # noqa: E402
    DEFAULT_BASE,
    FULL_PO3_BASE,
    PREBUILT_FEATURE_CACHES,
    PROJECT_ROOT,
    load_experiments,
    resolve_variant,
)
from training.configuration.variants import merge_variant_cfg  # noqa: E402

STEPS = 100_000
# Launcher overrides the old script applied for full-PO3 variants. The shared
# policy now disables peak drawdown for every variant.
LEGACY_FULL_PO3 = [
    "features.include_session_ohlc=true",
    "features.liquidity.enabled=true",
    "features.po3_state_mtf.enabled=true",
    "features.ifvg_mtf.enabled=true",
    "features.include_strategy_state=true",
    "env.open_manipulation_bars=0",
    "ftmo.trailing_dd_limit=0.0",
]
STRAT_YAML = {
    "po3_ifvg": "config/2_po3_ifvg.yaml",
    "distribution": "config/3_distribution.yaml",
}
# Deliberate changes from the former YAML merge path. Keep these explicit so
# every other effective-config difference remains a test failure.
RISK_BAND_DIFFS = {
    "env.risk_band_hold_below_usd",
    "env.risk_band_max_usd",
    "env.risk_floor",
    "env.risk_mode",
}
LOGGING_DIFFS = {"training.progress_log_every"}
GROWTH_DIFFS = {"env.reward_mode"}
CONSTRAINT_DIFFS = {
    "constrained_rl.enabled",
    "constrained_rl.episode_cost_budget",
}
EXPECTED_DIFFS_BY_VARIANT = {
    "ladder_a4a_dollar_band_q5_off": RISK_BAND_DIFFS
    | {"data.cache_dir", "data.price_discretization.enabled"},
    "ladder_a4a_dollar_band_q5_on": RISK_BAND_DIFFS
    | CONSTRAINT_DIFFS
    | {"data.cache_dir", "data.price_discretization.enabled"},
    "rq_mtf_control_tcn": RISK_BAND_DIFFS,
    "rq_mtf_treatment_mtf": RISK_BAND_DIFFS,
    "rq_mtf_treatment_reasoning": RISK_BAND_DIFFS
    | {
        "env.trade_setup_actions",
        "features.entry_ideas.enabled",
        "ppo.policy_distribution",
    },
    "sustainable_growth_ppo_dsr": RISK_BAND_DIFFS | LOGGING_DIFFS,
    "regime_d1_norm_tcn_control": RISK_BAND_DIFFS
    | LOGGING_DIFFS
    | {"features.normalize_d1_technical_on_source"},
    "regime_d1_norm_tcn_regime": RISK_BAND_DIFFS
    | LOGGING_DIFFS
    | {"features.normalize_d1_technical_on_source", "env.regime_observation"},
    "sustainable_growth_ppo_log": RISK_BAND_DIFFS | LOGGING_DIFFS | GROWTH_DIFFS,
    "sustainable_growth_ppo_log_eod_dd10k": RISK_BAND_DIFFS
    | LOGGING_DIFFS
    | GROWTH_DIFFS
    | {"env.eod_risk.peak_trailing_dd_limit_usd"},
    "sustainable_growth_ppo_log_q5": RISK_BAND_DIFFS
    | LOGGING_DIFFS
    | GROWTH_DIFFS
    | CONSTRAINT_DIFFS
    | {"constrained_rl.cost_discount_gamma"},
    "sustainable_growth_sac_log": RISK_BAND_DIFFS | LOGGING_DIFFS | GROWTH_DIFFS,
}


def _flatten(cfg) -> dict[str, object]:
    container = OmegaConf.to_container(cfg, resolve=True)
    out: dict[str, object] = {}

    def walk(node: object, prefix: str = "") -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{prefix}{k}.")
        else:
            out[prefix[:-1]] = node

    walk(container)
    return out


def _legacy(name: str):
    experiments = load_experiments()
    variants = experiments["variants"]
    matches = [row for row in variants if str(row.get("name")) == name]
    assert len(matches) == 1
    variant = {**dict(experiments.get("defaults") or {}), **matches[0]}
    strategy = str(variant.get("strategy", "baseline"))
    sa = bool(variant.get("strategy_actions", False))
    base = FULL_PO3_BASE if (strategy != "baseline" or sa) else DEFAULT_BASE
    cfg = load_config(None, config_path=PROJECT_ROOT / base)
    cfg = merge_variant_cfg(
        cfg,
        strategy=strategy,
        include_pd_context=bool(variant.get("include_pd_context", False)),
        variant=variant,
    )
    overrides = (LEGACY_FULL_PO3 if (strategy != "baseline" or sa) else []) + [
        f"ppo.total_timesteps={STEPS}"
    ]
    return apply_overrides(cfg, overrides)


def _new(name: str):
    resolved = resolve_variant(name, steps=STEPS, vae_path="placeholder.pth")
    cfg: DictConfig = load_config(None, config_path=PROJECT_ROOT / resolved["base_config"])
    if resolved["strategy"] in STRAT_YAML:
        cfg = OmegaConf.merge(cfg, OmegaConf.load(PROJECT_ROOT / STRAT_YAML[resolved["strategy"]]))  # type: ignore[assignment]
    return apply_overrides(cfg, resolved["overrides"])


@pytest.mark.parametrize("name", [str(v["name"]) for v in load_experiments()["variants"]])
def test_resolver_matches_legacy_config(name: str) -> None:
    legacy = _flatten(_legacy(name))
    new = _flatten(_new(name))
    diff = {k for k in set(legacy) | set(new) if legacy.get(k) != new.get(k)}
    expected_diff = set(EXPECTED_DIFFS_BY_VARIANT.get(name, set()))
    resolved = resolve_variant(name, vae_path="placeholder.pth")
    if "data.price_discretization.enabled=true" in resolved["overrides"]:
        expected_diff.update({"data.cache_dir", "data.price_discretization.enabled"})
        assert str(new["data.cache_dir"]).endswith("train_test_2025_2026_qgrid025_v1")
        assert new["data.price_discretization.enabled"] is True
    if resolved["strategy"] == "baseline":
        assert new["strategy.name"] == "baseline"
        if legacy.get("strategy.name") != new.get("strategy.name"):
            expected_diff.add("strategy.name")
    expected_cache = PREBUILT_FEATURE_CACHES.get(name)
    if expected_cache is not None:
        expected_diff.add("data.prebuilt_feature_cache")
        assert new["data.prebuilt_feature_cache"] == expected_cache
    unexpected = diff - expected_diff
    assert not unexpected, f"{name}: unexpected config drift: " + ", ".join(
        f"{k} legacy={legacy.get(k)!r} new={new.get(k)!r}" for k in sorted(unexpected)
    )
    if diff:
        # The baseline strategy-name override is intentional.
        assert diff == expected_diff
    assert resolved["strategy"] == new["strategy.name"]
