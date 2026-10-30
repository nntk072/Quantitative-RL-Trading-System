"""Shared ablation utilities for train_rl.py and ablation_runner.py.

Extracts the variant config merge logic and Tier 1 entry-state funnel
metrics so both entrypoints stay in sync without circular imports.
"""

from __future__ import annotations

from typing import Any, cast

from omegaconf import DictConfig, OmegaConf

from configuration import load_config_overlay, merge_config_overlay
from configuration.paths import repository_root
from training.configuration.strategy_overlays import merge_strategy_config
from training.configuration.variant_risk_policy import load_variant_ftmo_config

_PROJECT_ROOT = repository_root(__file__)
_PD_CONTEXT_CONFIG = _PROJECT_ROOT / "config" / "features" / "pd_context.yaml"

_LADDER_FLAGS: tuple[str, ...] = (
    "entry_state_machine",
    "entry_state_observation",
    "allow_agent_sl_mode",
    "allow_agent_tp_mode",
    "allow_multi_tp",
    "agent_direction_control",
    "strategy_actions",
    "arm_requires_retest",
    "candidate_max_age_bars",
    "peak_trailing_dd_limit",
)


def merge_variant_cfg(
    base: DictConfig,
    *,
    strategy: str,
    include_pd_context: bool,
    variant: dict[str, Any] | None = None,
) -> DictConfig:
    """Merge strategy / PD-context overlays onto a base config.

    This is extracted from ablation_runner.merge_variant_cfg so train_rl.py
    can apply the same variant semantics without importing from scripts/.
    """
    cfg = cast(DictConfig, OmegaConf.create(OmegaConf.to_container(base, resolve=True)))
    if include_pd_context:
        pd_path = _PD_CONTEXT_CONFIG
        if pd_path.is_file():
            cfg = merge_config_overlay(cfg, load_config_overlay(pd_path))
    if strategy != "baseline":
        cfg = merge_strategy_config(cfg, strategy)
    for key in _LADDER_FLAGS:
        if variant is not None and key in variant:
            cfg.env[key] = variant[key]
    if variant is not None and bool(variant.get("strategy_actions", False)):
        cfg.features.include_strategy_state = True
    # A baseline rung must not inherit default.yaml's po3_ifvg strategy block, which
    # strategy_actions would otherwise activate (plan A1). Mirrors variant_resolver.
    if strategy == "baseline" and "strategy" in cfg:
        cfg.strategy.name = "baseline"
    if variant is not None and variant.get("name"):
        ftmo = load_variant_ftmo_config(str(variant["name"]))
        cfg = merge_config_overlay(cfg, {"ftmo": ftmo})
    return cfg


def compute_tier1_funnel(
    entry_diag: dict[str, Any] | None,
    entry_state_diag: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compute Tier 1 entry-state funnel metrics from diagnostic dicts.

    Combines the lower-granularity ``entry_diag`` (from evaluate_model's
    ``_entry_diag``) with the FSM lifecycle counters from
    ``entry_state_diagnostics()``.

    Returns a flat dict suitable for inclusion in training_log.json.
    """
    entry_diag = entry_diag or {}
    entry_state_diag = entry_state_diag or {}

    opened = int(entry_diag.get("opened", 0))
    attempts = opened + sum(v for k, v in entry_diag.items() if k.startswith("rejected_"))

    funnel: dict[str, Any] = {
        "entry_opened": opened,
        "entry_attempts": attempts,
        "entry_rejection_rate": round(1.0 - opened / attempts, 6) if attempts else 0.0,
    }

    for key, value in entry_diag.items():
        if key.startswith("rejected_"):
            funnel[key] = int(value)

    for key in (
        "candidate_created",
        "candidate_expired",
        "candidate_invalidated",
        "trigger_requested",
        "trigger_refused",
        "entered",
        "closed",
        "armed_bars",
        "arm_to_trigger_rate",
        "trigger_refusal_rate",
    ):
        if key in entry_state_diag:
            funnel[key] = entry_state_diag[key]

    return funnel
