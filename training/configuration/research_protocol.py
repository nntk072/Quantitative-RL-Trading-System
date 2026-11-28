"""Prospective research-protocol validation and stable identity."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from omegaconf import DictConfig, OmegaConf

PROTOCOL_SCHEMA_VERSION = "research-execution-protocol-v2"
EXPECTED_DEVELOPMENT = ("2024-12-30", "2025-12-31")
EXPECTED_EXPOSED = ("2026-01-01", "2026-10-16")
EXPECTED_SEEDS = (42, 43, 44, 45, 46, 47)
EXPECTED_TIMEFRAMES = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    """Normalize a configuration node and reject scalar or list values.

    Args:
        value: Configuration value to validate as a mapping.
        name: Field name used in any validation error.

    Returns:
        Mapping view of the value.
    """
    if isinstance(value, DictConfig):
        value = OmegaConf.to_container(value, resolve=True)
    if isinstance(value, Mapping):
        return value
    raise ValueError(f"{name} must be a mapping")


def load_research_protocol(path: str | Path) -> dict[str, Any]:
    """Load and validate the frozen prospective protocol.

    Args:
        path: YAML path containing the protocol contract.

    Returns:
        Validated protocol mapping with resolved configuration values.
    """
    raw = OmegaConf.load(Path(path))
    value = OmegaConf.to_container(raw, resolve=True)
    if not isinstance(value, Mapping):
        raise ValueError("research protocol root must be a mapping")
    protocol = dict(value)
    validate_research_protocol(protocol)
    return protocol


def validate_research_protocol(protocol: Mapping[str, Any]) -> None:
    """Fail closed if a predeclared scientific choice changes.

    Args:
        protocol: Protocol mapping to validate against frozen study invariants.
    """
    if protocol.get("schema_version") != PROTOCOL_SCHEMA_VERSION:
        raise ValueError("unsupported research protocol schema version")

    questions = _mapping(protocol.get("questions"), "questions")
    if not str(questions.get("primary", "")).strip():
        raise ValueError("primary research question must be non-empty")
    if questions.get("primary_comparator") != "always_no_trade":
        raise ValueError("primary comparator must remain always_no_trade")

    periods = _mapping(protocol.get("periods"), "periods")
    development = _mapping(periods.get("development"), "periods.development")
    exposed = _mapping(periods.get("exposed_report_only"), "periods.exposed_report_only")
    if (development.get("start"), development.get("end_inclusive")) != EXPECTED_DEVELOPMENT:
        raise ValueError("development period differs from the frozen interval")
    if (exposed.get("start"), exposed.get("end_inclusive")) != EXPECTED_EXPOSED:
        raise ValueError("exposed report period differs from the frozen interval")
    if exposed.get("selectable") is not False:
        raise ValueError("exposed report period must not be selectable")

    survival = _mapping(protocol.get("survival_contract"), "survival_contract")
    expected_survival = {
        "initial_balance_usd": 100000.0,
        "daily_loss_limit_fraction": 0.05,
        "max_loss_limit_fraction": 0.10,
        "max_loss_mode": "static",
        "risk_fraction_ceiling": 0.01,
        "risk_sizing_ceiling_usd": 900.0,
        "compatibility_risk_per_trade_limit_usd": 1000.0,
        "payout_enabled": False,
        "daily_pnl_basis": "session_net_equity",
        "daily_loss_includes_open_pnl": True,
        "daily_loss_reset_source": "supplied_session_id_transition",
        "equality_at_floor_is_breach": False,
        "breach_below_floor_is_breach": True,
        "hard_breach_latches_full_evaluation": True,
        "reward_mode": "survival",
        "intermediate_reward": 0.0,
        "breach_terminal_reward": -1.0,
        "complete_breach_free_split_reward": 1.0,
        "ppo_gamma": 1.0,
        "ppo_gae_lambda": 1.0,
    }
    for key, expected in expected_survival.items():
        if survival.get(key) != expected:
            raise ValueError(f"survival contract field {key!r} differs from the frozen value")

    policy = _mapping(protocol.get("policy"), "policy")
    if int(policy.get("default_n_envs", 0)) != 8:
        raise ValueError("canonical survival policy must default to n_envs=8")
    if tuple(policy.get("all_setup_timeframes", ())) != EXPECTED_TIMEFRAMES:
        raise ValueError("canonical policy must retain all nine setup timeframes")
    for key in ("canonical_survival_config", "control_config", "price_geometry_config"):
        path = policy.get(key)
        if not isinstance(path, str) or not path.startswith("config/research/"):
            raise ValueError(f"policy.{key} must identify a repository research config")
    gate_ii = _mapping(policy.get("gate_ii_ablation_configs"), "policy.gate_ii_ablation_configs")
    expected_gate_ii = {
        "A": "config/research/m1_opportunity_reference.yaml",
        "B": "config/research/mtf_shared_opportunities_m1_history.yaml",
        "C": "config/research/mtf_shared_opportunities_with_history.yaml",
    }
    if dict(gate_ii) != expected_gate_ii:
        raise ValueError("Gate II A/B/C config identities differ from the registered ablation")

    replication = _mapping(protocol.get("replication"), "replication")
    seeds = tuple(replication.get("seeds", ()))
    if seeds != EXPECTED_SEEDS or len(set(seeds)) != len(seeds):
        raise ValueError("prospective seed set must be exactly 42..47")
    if int(replication.get("minimum_unique_seed_count", 0)) < 6:
        raise ValueError("at least six unique seeds are required")
    if replication.get("mvp_allowed") is not False:
        raise ValueError("MVP mode must remain disabled")
    if replication.get("locked_oos_selection_allowed") is not False:
        raise ValueError("locked OOS selection must remain disabled")
    walk_forward = _mapping(replication.get("walk_forward"), "replication.walk_forward")
    expected_wf = {
        "splits": 5,
        "purge_bars": 60,
        "embargo_bars": 20,
        "label_horizon_bars": 0,
        "test_size_fraction": 0.2,
    }
    for key, expected in expected_wf.items():
        if walk_forward.get(key) != expected:
            raise ValueError(f"walk-forward field {key!r} differs from the frozen protocol")

    stats = _mapping(protocol.get("primary_statistics"), "primary_statistics")
    if stats.get("unit") != "paired_independent_training_seed":
        raise ValueError("primary inference unit must remain the independent training seed")
    if stats.get("comparator") != "always_no_trade":
        raise ValueError("primary statistical comparator must remain always_no_trade")
    if stats.get("survival_lexicographically_first") is not True:
        raise ValueError("survival must remain lexicographically first")
    sign_flip = _mapping(stats.get("sign_flip"), "primary_statistics.sign_flip")
    expected_sign = {
        "alternative": "greater",
        "alpha": 0.05,
        "exact_max_pairs": 15,
        "monte_carlo_assignments": 100000,
        "rng_seed": 42,
    }
    for key, expected in expected_sign.items():
        if sign_flip.get(key) != expected:
            raise ValueError(f"sign-flip field {key!r} differs from the frozen protocol")
    bootstrap = _mapping(stats.get("paired_bootstrap"), "primary_statistics.paired_bootstrap")
    if bootstrap.get("samples") != 10000 or bootstrap.get("rng_seed") != 42:
        raise ValueError("paired bootstrap count or seed differs from the frozen protocol")
    if bootstrap.get("lower_confidence_bound_must_exceed") != 0.0:
        raise ValueError("paired bootstrap lower-bound criterion must remain zero")

    stopping = _mapping(protocol.get("stopping"), "stopping")
    fail_rule = _mapping(
        stopping.get("if_survival_qualification_fails"),
        "stopping.if_survival_qualification_fails",
    )
    if fail_rule.get("portfolio_optimization_allowed") is not False:
        raise ValueError("portfolio optimization must stop after failed qualification")
    if stopping.get("negative_result_is_valid_outcome") is not True:
        raise ValueError("negative-result disposition must remain explicitly allowed")

    compute = _mapping(protocol.get("compute"), "compute")
    if compute.get("comparison_unit") != "full_path_equivalents_per_environment":
        raise ValueError("compute comparisons must use full paths per environment")
    if float(compute.get("minimum_full_path_equivalents_per_environment", 0.0)) < 2.0:
        raise ValueError("compute budget must preserve at least two full paths per environment")
    if int(compute.get("default_n_envs", 0)) != 8:
        raise ValueError("canonical compute shape must remain n_envs=8")


def research_protocol_sha256(protocol: Mapping[str, Any]) -> str:
    """Return a stable semantic digest of a validated protocol.

    Args:
        protocol: Protocol mapping to hash after invariant validation.

    Returns:
        SHA-256 digest of its canonical semantic representation.
    """
    validate_research_protocol(protocol)
    payload = json.dumps(protocol, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "EXPECTED_DEVELOPMENT",
    "EXPECTED_EXPOSED",
    "EXPECTED_SEEDS",
    "EXPECTED_TIMEFRAMES",
    "PROTOCOL_SCHEMA_VERSION",
    "load_research_protocol",
    "research_protocol_sha256",
    "validate_research_protocol",
]
