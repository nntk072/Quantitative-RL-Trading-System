"""Matched setup controls, deterministic rules, and policies on one evaluation path."""

from __future__ import annotations

import hashlib
import inspect
import json
import random
import re
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import import_module
from math import isfinite
from typing import Any, cast

import numpy as np
import pandas as pd

from decisioning.trade_setup import TradeSetupActionSchema
from evaluation.metrics import (
    account_path_metric_inputs,
    calculate_metrics,
    evaluation_periods_per_year,
)
from evaluation.metrics.bootstrap import metrics_with_ci
from evaluation.metrics.trade_pairs import pair_trades
from evaluation.reporting.run_manifest import dataframe_sha256
from evaluation.rollout.random_eligible_setup import (
    AlwaysNoTradePolicy,
    AlwaysNoTradeRolloutModel,
    RandomEligibleSetupPolicy,
    RandomEligibleSetupRolloutModel,
)
from evaluation.rollout.trained_policy_rollout import evaluate_model
from simulation.environment.env import TradingEnv
from simulation.environment.trading_environment_factory import build_eval_common, cost_model

BASELINE_NAMES = ("always_no_trade", "random_eligible_setup")


@dataclass(frozen=True, slots=True)
class ExistingPolicyArm:
    """An already-trained model and the identity needed for a matched rollout."""

    model: Any
    metadata: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class RuleSetupBaselineArm:
    """A deterministic rule model whose identity is emitted by its policy."""

    model: Any


def _valid_sha256(value: Any) -> bool:
    """Return whether a value is a lowercase SHA-256 hexadecimal digest.

    Args:
        value: Candidate digest value to validate.

    Returns:
        Whether ``value`` has 64 lowercase hexadecimal characters.
    """
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _validate_existing_policy(name: str, arm: ExistingPolicyArm) -> dict[str, Any]:
    """Validate checkpoint metadata required for a reproducible policy arm.

    Args:
        name: Stable identifier assigned to the additional policy arm.
        arm: Trained model and saved checkpoint metadata.

    Returns:
        Validated metadata with checkpoint and action-protocol fields.
    """
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or name in BASELINE_NAMES:
        raise ValueError("additional policy names must be unique lowercase identifiers")
    metadata = dict(arm.metadata)
    for key in (
        "policy_id",
        "checkpoint_sha256",
        "checkpoint_source_key",
        "training_seed",
        "training_total_steps",
        "policy_action_mode",
        "action_schema",
    ):
        if key not in metadata:
            raise ValueError(f"existing policy metadata is missing {key!r}")
    if not isinstance(metadata["policy_id"], str) or not metadata["policy_id"].strip():
        raise ValueError("existing policy policy_id must be a non-empty string")
    if not _valid_sha256(metadata["checkpoint_sha256"]):
        raise ValueError("existing policy checkpoint_sha256 must be a lowercase SHA-256")
    if (
        not isinstance(metadata["checkpoint_source_key"], str)
        or not metadata["checkpoint_source_key"].strip()
    ):
        raise ValueError("existing policy checkpoint_source_key must be a non-empty string")
    for key in ("training_seed", "training_total_steps"):
        value = metadata[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"existing policy {key} must be a non-negative integer")
    if metadata["policy_action_mode"] not in {"deterministic", "stochastic"}:
        raise ValueError("policy_action_mode must be deterministic or stochastic")
    if metadata["policy_action_mode"] == "stochastic":
        seed = metadata.get("policy_action_seed")
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**32 - 1:
            raise ValueError("stochastic policies require policy_action_seed in [0, 2**32-1]")
    if not callable(getattr(arm.model, "predict", None)):
        raise TypeError("existing policy model must expose predict(observation, deterministic=...)")
    return metadata


def _validate_rule_setup_baseline(name: str, arm: RuleSetupBaselineArm) -> dict[str, Any]:
    """Validate the provenance contract for a deterministic setup rule.

    Args:
        name: Stable identifier assigned to the additional baseline arm.
        arm: Deterministic rule model exposing policy metadata.

    Returns:
        Validated rule metadata labeled as a deterministic policy source.
    """
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or name in BASELINE_NAMES:
        raise ValueError("additional policy names must be unique lowercase identifiers")
    if not callable(getattr(arm.model, "predict", None)):
        raise TypeError("rule baseline model must expose predict(observation, deterministic=...)")
    emitted = getattr(arm.model, "policy_metadata", None)
    if not isinstance(emitted, Mapping):
        raise ValueError("rule baseline must expose policy_metadata from its policy implementation")
    metadata = dict(emitted)
    for key in (
        "policy_id",
        "baseline_tier",
        "policy_action_mode",
        "action_schema",
        "permitted_information",
        "training_performed",
        "selection_or_tuning_performed",
    ):
        if key not in metadata:
            raise ValueError(f"rule baseline metadata is missing {key!r}")
    if not isinstance(metadata["policy_id"], str) or not metadata["policy_id"].strip():
        raise ValueError("rule baseline policy_id must be a non-empty string")
    if not str(metadata["baseline_tier"]).startswith("tier_1_"):
        raise ValueError("rule baseline must identify a Tier 1 baseline_tier")
    if metadata["policy_action_mode"] != "deterministic":
        raise ValueError("rule baselines must use deterministic action mode")
    if metadata["training_performed"] is not False:
        raise ValueError("rule baselines must declare training_performed=false")
    if metadata["selection_or_tuning_performed"] is not False:
        raise ValueError("rule baselines must declare selection_or_tuning_performed=false")
    if not isinstance(metadata["permitted_information"], list):
        raise ValueError("rule baseline permitted_information must be a list")
    metadata["policy_source"] = "deterministic_rule"
    return metadata


def _validate_additional_policy(
    name: str, arm: ExistingPolicyArm | RuleSetupBaselineArm
) -> dict[str, Any]:
    """Validate an additional trained or deterministic policy arm.

    Args:
        name: Stable identifier assigned to the policy arm.
        arm: Existing trained checkpoint or deterministic setup-rule model.

    Returns:
        Validated policy provenance metadata.
    """
    if isinstance(arm, RuleSetupBaselineArm):
        return _validate_rule_setup_baseline(name, arm)
    if isinstance(arm, ExistingPolicyArm):
        metadata = _validate_existing_policy(name, arm)
        metadata["policy_source"] = "trained_checkpoint"
        return metadata
    raise TypeError("additional policies must be ExistingPolicyArm or RuleSetupBaselineArm")


@contextmanager
def _seeded_action_rng(seed: int) -> Iterator[None]:
    """Isolate common global RNGs for a seeded stochastic model rollout.

    Args:
        seed: Common action seed applied to NumPy, Python, and Torch RNGs.

    Yields:
        Control while the seeded RNG state is active; prior states are restored
        when the context exits.
    """
    numpy_state = np.random.get_state()
    python_state = random.getstate()
    torch_module: Any = None
    try:
        torch_module = import_module("torch")
    except ImportError:
        pass
    np.random.seed(seed)
    random.seed(seed)
    try:
        if torch_module is None:
            yield
        else:
            devices = (
                list(range(torch_module.cuda.device_count()))
                if torch_module.cuda.is_available()
                else []
            )
            with torch_module.random.fork_rng(devices=devices):
                torch_module.manual_seed(seed)
                yield
    finally:
        np.random.set_state(numpy_state)
        random.setstate(python_state)


def _config_flag(cfg: Any, key: str) -> bool:
    """Read one environment flag from a mapping or attribute-based config.

    Args:
        cfg: Resolved run configuration.
        key: Environment flag name to read.

    Returns:
        The configured flag value as a boolean.
    """
    env_cfg = cfg.get("env", {}) if isinstance(cfg, Mapping) else getattr(cfg, "env", {})
    value = (
        env_cfg.get(key, False) if isinstance(env_cfg, Mapping) else getattr(env_cfg, key, False)
    )
    return bool(value)


def evaluate_tier0_setup_baselines(
    cfg: Any,
    bars: pd.DataFrame,
    features: pd.DataFrame,
    tickbook: Any | None,
    *,
    execution_seed: int,
    random_policy_seed: int,
    period_role: str,
    trade_probability: float = 1.0,
    normalized_risk: float = 0.5,
    absolute_risk_budget_usd: float | None = None,
    tick_fill_slippage_points: float | None = None,
    bootstrap_samples: int = 2000,
    bootstrap_level: float = 0.95,
    bootstrap_seed: int = 42,
    baseline_names: Sequence[str] | None = None,
    additional_policies: Mapping[str, ExistingPolicyArm | RuleSetupBaselineArm] | None = None,
) -> dict[str, dict[str, Any]]:
    """Evaluate Tier 0 controls and optional Tier 1 rules or trained policies.

    ``cfg`` must be the already-selected run configuration. The function does
    not load data or resolve a variant. All policies receive the exact same
    bars, features, tickbook, and ``build_eval_common`` settings; each gets a
    fresh environment and its actual environment-derived action schema. The
    caller must declare the period role, and inspected 2026 dates cannot be
    labeled as development data. Trained policies must provide verified
    checkpoint and action-schema metadata; deterministic rule baselines provide
    policy-emitted semantics and action-schema metadata. Stochastic trained
    policies also provide a dedicated action seed. A supplied absolute risk
    budget sets the shared dollar-band ceiling for every action coordinate; it
    is a maximum requested budget, not a claim of equal realized-risk
    distributions.

    ``baseline_names`` can select a subset so one failed arm does not discard
    completed results from an independent arm.

    Each policy also receives same-trajectory moving-block confidence
    intervals. These describe within-path sampling uncertainty and do not
    replace paired policy or between-seed inference.

    Args:
        cfg: Resolved configuration with setup actions enabled.
        bars: Shared chronological market bars for every policy arm.
        features: Feature matrix aligned with the supplied bars.
        tickbook: Optional tick data shared by all executions.
        policy_models: Mapping of existing policy names to model and metadata.
        execution_seed: Seed used for execution randomness across arms.
        random_policy_seed: Seed controlling the random eligible-setup baseline.
        period_role: Declared role of the evaluated date range.
        trade_probability: Entry probability used by applicable setup baselines.
        normalized_risk: Default normalized risk coordinate for policy arms.
        absolute_risk_budget_usd: Optional shared dollar risk-band ceiling.
        tick_fill_slippage_points: Optional override for configured tick slippage.
        bootstrap_samples: Number of moving-block samples for within-path intervals.
        bootstrap_level: Confidence level for those intervals.
        bootstrap_seed: Seed for interval resampling.
        baseline_names: Optional subset of standard baselines to evaluate.
        additional_policies: Optional trained or deterministic policy arms.

    Returns:
        Completed per-policy outputs, including equity, trade events, and provenance.
    """
    if (
        isinstance(bootstrap_samples, bool)
        or not isinstance(bootstrap_samples, (int, np.integer))
        or bootstrap_samples <= 0
    ):
        raise ValueError("bootstrap_samples must be a positive integer")
    if not np.isfinite(bootstrap_level) or not 0.0 < bootstrap_level < 1.0:
        raise ValueError("bootstrap_level must be finite and between 0 and 1")
    if (
        isinstance(bootstrap_seed, bool)
        or not isinstance(bootstrap_seed, (int, np.integer))
        or bootstrap_seed < 0
    ):
        raise ValueError("bootstrap_seed must be a non-negative integer")
    if not (_config_flag(cfg, "strategy_actions") and _config_flag(cfg, "trade_setup_actions")):
        raise ValueError(
            "Tier 0 setup baselines require env.strategy_actions=true and "
            "env.trade_setup_actions=true"
        )
    for name, value in (
        ("execution_seed", execution_seed),
        ("random_policy_seed", random_policy_seed),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    if period_role not in {"development", "exposed_report_only", "synthetic"}:
        raise ValueError("period_role must be development, exposed_report_only, or synthetic")
    if period_role != "synthetic" and absolute_risk_budget_usd is None:
        raise ValueError(
            "non-synthetic Tier 0 evaluation requires an explicit absolute_risk_budget_usd"
        )
    effective_cfg = cfg
    if absolute_risk_budget_usd is not None:
        try:
            risk_budget = float(absolute_risk_budget_usd)
        except (TypeError, ValueError) as exc:
            raise ValueError("absolute_risk_budget_usd must be finite and positive") from exc
        if (
            isinstance(absolute_risk_budget_usd, bool)
            or not isfinite(risk_budget)
            or risk_budget <= 0.0
        ):
            raise ValueError("absolute_risk_budget_usd must be finite and positive")
        if (
            isinstance(normalized_risk, bool)
            or not isfinite(float(normalized_risk))
            or not 0.0 <= float(normalized_risk) <= 1.0
        ):
            raise ValueError("normalized_risk must be finite and in [0, 1]")
        sizing = _risk_sizing_metadata(cfg)
        static_cap = float(sizing["configured_static_trade_risk_cap_usd"])
        if static_cap > 0.0 and risk_budget > static_cap:
            raise ValueError(
                "absolute_risk_budget_usd exceeds the configured static per-trade risk cap"
            )
        effective_cfg = _with_absolute_risk_budget(
            cfg,
            risk_band_max_usd=risk_budget,
        )
    if not isinstance(bars.index, pd.DatetimeIndex):
        raise TypeError("matched setup baselines require a DatetimeIndex")
    if len(bars) != len(features) or not bars.index.equals(features.index):
        raise ValueError("bars and features must have identical rows and ordered timestamps")
    try:
        resolved_tick_slippage = (
            float(cost_model(effective_cfg).slippage_points)
            if tick_fill_slippage_points is None
            else float(tick_fill_slippage_points)
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("tick_fill_slippage_points must be finite and non-negative") from exc
    if (
        isinstance(tick_fill_slippage_points, bool)
        or not isfinite(resolved_tick_slippage)
        or resolved_tick_slippage < 0.0
    ):
        raise ValueError("tick_fill_slippage_points must be finite and non-negative")
    if period_role != "synthetic" and len(bars):
        dates = bars.index.tz_localize(None) if bars.index.tz is not None else bars.index
        exposed_start = pd.Timestamp("2026-01-01")
        exposed_end = pd.Timestamp("2026-10-16 23:59:59.999999")
        overlaps_exposed = bool(((dates >= exposed_start) & (dates <= exposed_end)).any())
        if overlaps_exposed and period_role != "exposed_report_only":
            raise ValueError("the exposed 2026 interval must be labeled exposed_report_only")
        if period_role == "exposed_report_only" and not overlaps_exposed:
            raise ValueError(
                "exposed_report_only requires overlap with the inspected 2026 interval"
            )

    config_sha256 = _resolved_config_sha256(effective_cfg)
    input_hashes = {
        "bars": dataframe_sha256(bars),
        "features": dataframe_sha256(features),
        "tickbook": tickbook.content_sha256() if tickbook is not None else None,
    }
    validated_additional = {
        name: _validate_additional_policy(name, arm)
        for name, arm in sorted((additional_policies or {}).items())
    }
    if validated_additional and absolute_risk_budget_usd is None:
        raise ValueError("additional policies require an explicit absolute_risk_budget_usd")

    outputs: dict[str, dict[str, Any]] = {}
    available_policy_names = (*BASELINE_NAMES, *validated_additional)
    policy_names = tuple(available_policy_names if baseline_names is None else baseline_names)
    if len(policy_names) != len(set(policy_names)):
        raise ValueError("baseline_names must not contain duplicates")
    unknown_policy_names = sorted(set(policy_names) - set(available_policy_names))
    if unknown_policy_names:
        raise ValueError(f"unknown baseline_names: {unknown_policy_names}")
    if not policy_names:
        raise ValueError("baseline_names must select at least one policy")
    for baseline_name in policy_names:
        # Resolve anew to give every baseline fresh stateful strategy adapters.
        eval_common, _, _, _, _ = build_eval_common(
            effective_cfg,
            args=None,
            tick_fill_slippage_points=resolved_tick_slippage,
        )
        eval_common = dict(eval_common)
        eval_common["execution_seed"] = execution_seed

        # build_eval_common serves both environment construction and rollout.
        # Route values by each API's declared signature at this seam.
        env_parameters = inspect.signature(TradingEnv).parameters
        env_kwargs = {key: value for key, value in eval_common.items() if key in env_parameters}
        env_kwargs["tickbook"] = tickbook
        rollout_kwargs = {
            key: value
            for key, value in eval_common.items()
            if key in inspect.signature(evaluate_model).parameters
        }
        rollout_kwargs.update(
            {
                "tickbook": tickbook,
                "execution_seed": execution_seed,
                "strategy_actions": True,
                "trade_setup_actions": True,
            }
        )
        env = TradingEnv(bars=bars, features=features, episodic=False, **env_kwargs)
        schema = env.action_schema
        if not isinstance(schema, TradeSetupActionSchema):
            raise TypeError("configured environment did not expose a versioned setup action schema")
        if "trade_setup" not in schema.names or "risk" not in schema.names:
            raise ValueError("configured environment action schema lacks setup or risk coordinates")

        if baseline_name == "always_no_trade":
            model: Any = AlwaysNoTradeRolloutModel(AlwaysNoTradePolicy(schema))
            metadata = dict(model.policy_metadata)
            deterministic = True
        elif baseline_name == "random_eligible_setup":
            model = RandomEligibleSetupRolloutModel(
                RandomEligibleSetupPolicy(
                    schema,
                    seed=random_policy_seed,
                    trade_probability=trade_probability,
                    normalized_risk=normalized_risk,
                )
            )
            metadata = dict(model.policy_metadata)
            deterministic = True
        else:
            assert additional_policies is not None
            arm = additional_policies[baseline_name]
            model = arm.model
            metadata = validated_additional[baseline_name]
            if metadata["action_schema"] != schema.to_dict():
                raise ValueError(
                    f"{baseline_name} action_schema does not match the evaluation environment"
                )
            deterministic = metadata["policy_action_mode"] == "deterministic"

        rollout_kwargs["deterministic"] = deterministic
        if baseline_name in validated_additional:
            metadata["evaluation_action_mode"] = metadata["policy_action_mode"]
            if not deterministic:
                with _seeded_action_rng(int(metadata["policy_action_seed"])):
                    raw = evaluate_model(model, bars, features, env=env, **rollout_kwargs)
            else:
                raw = evaluate_model(model, bars, features, env=env, **rollout_kwargs)
        else:
            raw = evaluate_model(model, bars, features, env=env, **rollout_kwargs)
        metrics = calculate_metrics(
            raw["equity"],
            trades=raw["trades"],
            n_sessions=int(raw["n_sessions"]),
            n_breach_sessions=int(raw["n_breach_sessions"]),
            periods_per_year=_periods_per_year(cfg),
            initial_balance=float(eval_common["initial_balance"]),
            **account_path_metric_inputs(raw),
        )
        closed_trade_pnls = np.asarray(
            [
                float(close["pnl"])
                for _, close in pair_trades(raw["trades"])
                if pd.notna(close.get("pnl"))
            ],
            dtype=np.float64,
        )
        confidence_intervals = {
            name: {
                "estimate": interval.estimate,
                "lower": interval.lower,
                "upper": interval.upper,
                "level": interval.level,
            }
            for name, interval in metrics_with_ci(
                np.asarray(raw["equity"], dtype=np.float64),
                closed_trade_pnls,
                periods_per_year=_periods_per_year(cfg),
                n_boot=int(bootstrap_samples),
                level=float(bootstrap_level),
                rng_seed=int(bootstrap_seed),
                initial_balance=float(eval_common["initial_balance"]),
            ).items()
        }
        outputs[baseline_name] = {
            "metrics": metrics,
            "confidence_intervals": {
                "schema": "within_trajectory_bootstrap_ci_v1",
                "method": "moving_block_bar_returns_and_trade_pnl_resampling",
                "n_boot": int(bootstrap_samples),
                "level": float(bootstrap_level),
                "seed": int(bootstrap_seed),
                "block_length_bars": 8,
                "scope": (
                    "within-trajectory sampling uncertainty; not between-seed or paired-policy "
                    "uncertainty"
                ),
                "metrics": confidence_intervals,
            },
            "decisions": raw.get("trade_setup_decisions", pd.DataFrame()),
            "resolved_config": _resolved_config_payload(effective_cfg),
            # This is the environment's complete event ledger. It includes
            # opens, closes, partial fills, rejects, and protective updates.
            "trade_fill_event_ledger": raw["trades"],
            "equity": raw["equity"],
            "policy_metadata": {
                **metadata,
                "execution_seed": execution_seed,
                "random_policy_seed": random_policy_seed
                if baseline_name == "random_eligible_setup"
                else None,
                "action_schema": schema.to_dict(),
                "matched_input_bundle": "shared bars, features, and TickBook inputs",
                "input_hashes": input_hashes,
                "risk_sizing": {
                    **_risk_sizing_metadata(effective_cfg),
                    "policy_normalized_risk": (
                        float(metadata["normalized_risk"])
                        if metadata.get("normalized_risk") is not None
                        else None
                    ),
                    "policy_risk_coordinate_is_constant": bool(
                        metadata.get("risk_coordinate_is_constant", baseline_name in BASELINE_NAMES)
                    ),
                    "absolute_risk_budget_usd": (
                        None
                        if absolute_risk_budget_usd is None
                        else float(absolute_risk_budget_usd)
                    ),
                },
                "resolved_config_sha256": config_sha256,
                "period_role": period_role,
                "tick_fill_slippage_points": resolved_tick_slippage,
                "confidence_interval_protocol": {
                    "schema": "within_trajectory_bootstrap_ci_v1",
                    "n_boot": int(bootstrap_samples),
                    "level": float(bootstrap_level),
                    "seed": int(bootstrap_seed),
                    "block_length_bars": 8,
                    "scope": "within-trajectory only",
                },
                "bars_rows": int(len(bars)),
                "features_rows": int(len(features)),
                "evaluation_start": str(bars.index[0]) if len(bars) else None,
                "evaluation_end": str(bars.index[-1]) if len(bars) else None,
            },
            "evaluation": {
                key: raw[key]
                for key in (
                    "n_sessions",
                    "n_breach_sessions",
                    "n_steps",
                    "exposure_bars",
                    "exposure_fraction",
                    "breach_events",
                    "completed_data_split",
                    "episode_end_reason",
                )
                if key in raw
            },
        }
    return outputs


def _with_absolute_risk_budget(cfg: Any, *, risk_band_max_usd: float) -> Any:
    """Clone the resolved config with a dollar-band risk coordinate.

    Args:
        cfg: Mapping or OmegaConf configuration to copy.
        risk_band_max_usd: Maximum dollar budget represented by the action.

    Returns:
        Independent OmegaConf config using the requested dollar-band ceiling.
    """
    from omegaconf import OmegaConf

    if OmegaConf.is_config(cfg):
        resolved = OmegaConf.to_container(cfg, resolve=True)
    elif isinstance(cfg, Mapping):
        resolved = dict(cfg)
    else:
        raise TypeError("cfg must be a mapping or an OmegaConf config")
    if not isinstance(resolved, Mapping):
        raise TypeError("resolved config must be a mapping")
    effective = OmegaConf.create(dict(resolved))
    OmegaConf.update(effective, "env.risk_mode", "dollar_band", force_add=True)
    OmegaConf.update(
        effective,
        "env.risk_band_max_usd",
        float(risk_band_max_usd),
        force_add=True,
    )
    return effective


def _resolved_config_sha256(cfg: Any) -> str:
    """Hash the fully resolved source configuration deterministically.

    Args:
        cfg: Mapping or OmegaConf configuration to resolve and hash.

    Returns:
        SHA-256 hex digest of canonical JSON configuration content.
    """
    resolved = _resolved_config_payload(cfg)
    encoded = json.dumps(
        resolved,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        allow_nan=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _resolved_config_payload(cfg: Any) -> dict[str, Any]:
    """Return the plain resolved mapping that actually configured evaluation.

    Args:
        cfg: Mapping or OmegaConf configuration used for evaluation.

    Returns:
        Resolved plain dictionary with interpolations evaluated.
    """
    from omegaconf import OmegaConf

    if OmegaConf.is_config(cfg):
        resolved = OmegaConf.to_container(cfg, resolve=True)
    elif isinstance(cfg, Mapping):
        resolved = dict(cfg)
    else:
        raise TypeError("cfg must be a mapping or an OmegaConf config")
    if not isinstance(resolved, dict):
        raise TypeError("resolved config must be a mapping")
    return cast(dict[str, Any], resolved)


def _risk_sizing_metadata(cfg: Any) -> dict[str, Any]:
    """Record the resolved controls that turn risk actions into dollar budgets.

    Args:
        cfg: Resolved configuration containing environment, account, and risk settings.

    Returns:
        Normalized risk-mode settings and effective per-trade sizing limits.
    """
    from omegaconf import OmegaConf

    resolved = (
        OmegaConf.to_container(cfg, resolve=True)
        if OmegaConf.is_config(cfg)
        else dict(cfg)
        if isinstance(cfg, Mapping)
        else None
    )
    if not isinstance(resolved, Mapping):
        raise TypeError("cfg must be a mapping or an OmegaConf config")
    env = resolved.get("env", {})
    strategy = resolved.get("strategy", {})
    strategy_risk = strategy.get("risk", {}) if isinstance(strategy, Mapping) else {}
    trading_policy = resolved.get("trading_policy", {})
    repeated = (
        trading_policy.get("repeated_payout", {}) if isinstance(trading_policy, Mapping) else {}
    )
    ftmo = resolved.get("ftmo", {})
    risk_config = resolved.get("risk", {})
    account = resolved.get("account", {})
    env = env if isinstance(env, Mapping) else {}
    repeated = repeated if isinstance(repeated, Mapping) else {}
    ftmo = ftmo if isinstance(ftmo, Mapping) else {}
    risk_config = risk_config if isinstance(risk_config, Mapping) else {}
    account = account if isinstance(account, Mapping) else {}
    static_risk_limits = [
        float(value)
        for value in (
            ftmo.get("risk_per_trade_limit", 0.0),
            ftmo.get("risk_sizing_limit_usd", 0.0),
        )
        if float(value) > 0.0
    ]
    mode = str(env.get("risk_mode", "dynamic"))
    semantics = {
        "fixed": (
            "fixed_risk_usd is the total stop-risk plus modeled execution-cost budget; action "
            "risk coordinate does not change the request, and volume is rounded down to the "
            "configured broker step"
        ),
        "dynamic": (
            "current equity multiplied by decoded action risk fraction, subject to configured "
            "capacity approvals and per-trade guardrails; modeled execution costs are reserved "
            "before assigning stop exposure and volume is rounded down to broker step"
        ),
        "dollar_band": (
            "normalized action coordinate maps to a requested total budget under "
            "risk_band_max_usd; sizing reserves modeled execution costs before assigning "
            "stop exposure, while lot limits and guardrails may reduce realized exposure"
        ),
    }
    return {
        "risk_mode": mode,
        "risk_budget_semantics": semantics.get(mode, "unknown risk mode"),
        "fixed_risk_usd": float(env.get("fixed_risk_usd", 0.0)),
        "risk_band_max_usd": float(env.get("risk_band_max_usd", 0.0)),
        "risk_band_hold_below_usd": float(env.get("risk_band_hold_below_usd", 0.0)),
        "strategy_risk_frac_range": list(strategy_risk.get("risk_frac_range", [])),
        "legacy_risk_fraction": float(risk_config.get("default_risk_frac", 0.0)),
        "repeated_payout_agent_risk_max_frac": float(repeated.get("agent_risk_max_frac", 0.0)),
        "ftmo_risk_per_trade_limit_usd": float(ftmo.get("risk_per_trade_limit", 0.0)),
        "ftmo_risk_sizing_limit_usd": float(ftmo.get("risk_sizing_limit_usd", 0.0)),
        "ftmo_risk_per_trade_limit_pct": float(ftmo.get("risk_per_trade_limit_pct", 0.0)),
        "ftmo_limit_value_mode": str(ftmo.get("limit_value_mode", "unknown")),
        "configured_static_trade_risk_cap_usd": min(static_risk_limits)
        if static_risk_limits
        else 0.0,
        "trading_policy_mode": str(trading_policy.get("mode", "legacy"))
        if isinstance(trading_policy, Mapping)
        else "legacy",
        "repeated_payout_reserve_cost_buffer_usd": float(
            repeated.get("reserve_cost_buffer_usd", 0.0)
        ),
        "min_lot": float(risk_config.get("min_lot", 0.0)),
        "max_lot": float(risk_config.get("max_lot", 0.0)),
        "lot_step": float(risk_config.get("lot_step", 0.01)),
        "contract_size": float(account.get("contract_size", 0.0)),
    }


def _periods_per_year(cfg: Any) -> int:
    """Resolve annualization periods from a mapping or OmegaConf object.

    Args:
        cfg: Configuration containing the evaluation annualization settings.

    Returns:
        Number of observations per evaluation year.
    """
    if isinstance(cfg, Mapping):
        mapping = cfg
    else:
        try:
            from omegaconf import OmegaConf

            resolved = OmegaConf.to_container(cfg, resolve=True)
        except (TypeError, ValueError):
            resolved = {}
        mapping = resolved if isinstance(resolved, Mapping) else {}
    return evaluation_periods_per_year(mapping)
