"""Evidence gate between survival qualification and portfolio optimization."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf
from omegaconf.errors import OmegaConfBaseException

from artifacts.atomic import write_text_atomic
from configuration.paths import repository_root
from decisioning.observations import (
    OBSERVATION_SCHEMA_V1,
    OBSERVATION_SCHEMA_V2,
    build_observation_schema,
)
from evaluation.reporting.run_manifest import (
    SEQUENCE_FEATURE_VALIDITY_SCHEMA_VERSION,
    build_sequence_feature_schema,
    file_sha256,
    source_state,
)
from features.context.trade_setup_candidates import trade_setup_candidate_feature_columns

MIN_SURVIVAL_SEEDS = 6
MIN_SURVIVAL_WF_SPLITS = 5
SURVIVAL_OBSERVATION_SCHEMA = OBSERVATION_SCHEMA_V2
SURVIVAL_DATA_TIMEFRAMES = (
    "M1",
    "M3",
    "M5",
    "M10",
    "M15",
    "M30",
    "H1",
    "H4",
    "D1",
)
SURVIVAL_HIGHER_TIMEFRAMES = SURVIVAL_DATA_TIMEFRAMES[1:]


def _survival_account_contract_error(cfg: Any) -> str | None:
    """Require survival learning to use the user-selected static account contract.

    Args:
        cfg: Resolved account and FTMO configuration to validate.

    Returns:
        Contract mismatch explanation, or ``None`` when the settings match.
    """
    account = cfg.get("account", {}) if hasattr(cfg, "get") else {}
    ftmo = cfg.get("ftmo", {}) if hasattr(cfg, "get") else {}
    if not hasattr(account, "get") or not hasattr(ftmo, "get"):
        return "survival qualification requires account and ftmo mappings"

    numeric_contract = (
        ("account.initial_balance", account.get("initial_balance"), 100_000.0),
        ("ftmo.daily_loss_limit_pct", ftmo.get("daily_loss_limit_pct"), 0.05),
        ("ftmo.max_loss_limit_initial_pct", ftmo.get("max_loss_limit_initial_pct"), 0.10),
        ("ftmo.risk_per_trade_limit_pct", ftmo.get("risk_per_trade_limit_pct"), 0.01),
        ("ftmo.risk_sizing_limit_usd", ftmo.get("risk_sizing_limit_usd"), 900.0),
    )
    invalid = [
        f"{key}={value!r} (expected {expected:g})"
        for key, value, expected in numeric_contract
        if isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isclose(float(value), expected, rel_tol=0.0, abs_tol=1e-12)
    ]
    if str(ftmo.get("limit_value_mode", "")).strip().lower() != "percent_equity":
        invalid.append("ftmo.limit_value_mode must be 'percent_equity'")
    if str(ftmo.get("max_drawdown_mode", "")).strip().lower() != "static":
        invalid.append("ftmo.max_drawdown_mode must be 'static'")
    hard_cap = ftmo.get("risk_per_trade_limit")
    if (
        isinstance(hard_cap, bool)
        or not isinstance(hard_cap, (int, float))
        or float(hard_cap) < 900.0
    ):
        invalid.append("ftmo.risk_per_trade_limit must allow the $900 sizing cap")
    if invalid:
        return "survival qualification account contract mismatch: " + "; ".join(invalid)
    return None


def _survival_timeframe_contract_error(cfg: Any) -> str | None:
    """Require generated setup signals across the full timeframe menu.

    Args:
        cfg: Resolved data, feature, and risk configuration.

    Returns:
        Timeframe mismatch explanation, or ``None`` for the complete menu.
    """
    data = cfg.get("data", {}) if hasattr(cfg, "get") else {}
    features = cfg.get("features", {}) if hasattr(cfg, "get") else {}
    risk = cfg.get("risk", {}) if hasattr(cfg, "get") else {}
    entry_ideas = features.get("entry_ideas", {}) if hasattr(features, "get") else {}
    if not all(hasattr(block, "get") for block in (data, features, entry_ideas, risk)):
        return "survival qualification requires data, features, and risk mappings"
    if entry_ideas.get("enabled") is not True:
        return (
            "survival qualification requires features.entry_ideas.enabled=true "
            "so setup eligibility is generated for the full timeframe ladder"
        )

    expected = {
        "data.timeframes": SURVIVAL_DATA_TIMEFRAMES,
        "features.htf_timeframes": SURVIVAL_HIGHER_TIMEFRAMES,
        "features.entry_ideas.timeframes": SURVIVAL_DATA_TIMEFRAMES,
        "risk.target_timeframes": SURVIVAL_HIGHER_TIMEFRAMES,
    }
    actual = {
        "data.timeframes": data.get("timeframes"),
        "features.htf_timeframes": features.get("htf_timeframes"),
        "features.entry_ideas.timeframes": entry_ideas.get("timeframes"),
        "risk.target_timeframes": risk.get("target_timeframes"),
    }
    invalid = []
    for key, value in actual.items():
        if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, Iterable):
            invalid.append(f"{key}={value!r} (expected {list(expected[key])!r})")
            continue
        if tuple(str(item).strip().upper() for item in value) != expected[key]:
            invalid.append(f"{key}={value!r} (expected {list(expected[key])!r})")
    if invalid:
        return "survival qualification requires the full configured timeframe ladder: " + "; ".join(
            invalid
        )
    return None


def _survival_observation_schema_error(cfg: Any) -> str | None:
    """Require risk budgets and feature validity during policy learning.

    Args:
        cfg: Resolved environment configuration.

    Returns:
        Observation-contract mismatch explanation, or ``None`` when valid.
    """
    env = cfg.get("env", {}) if hasattr(cfg, "get") else {}
    version = str(env.get("observation_schema_version", OBSERVATION_SCHEMA_V1))
    if version != SURVIVAL_OBSERVATION_SCHEMA:
        return (
            "survival training and portfolio use require "
            f"env.observation_schema_version={SURVIVAL_OBSERVATION_SCHEMA}; "
            "account-state-v1 omits the remaining daily and maximum-loss budgets"
        )
    if env.get("feature_validity_channels", False) is not True:
        return (
            "survival training and portfolio use require "
            "env.feature_validity_channels=true so missing features are observable"
        )
    if env.get("reachable_r_validity_mask", False) is not True:
        return (
            "survival training and portfolio use require "
            "env.reachable_r_validity_mask=true so zero-filled unknown reachability is observable"
        )
    return None


def _digest(value: Any) -> str:
    """Hash a JSON-compatible value using stable key ordering.

    Args:
        value: Value to encode as sorted, compact JSON.

    Returns:
        Lowercase hexadecimal SHA-256 digest.
    """
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def survival_config_identity(cfg: Any) -> str:
    """Hash the behavior config shared by qualification and portfolio phases.

    Args:
        cfg: OmegaConf configuration whose behavior settings define the phase.

    Returns:
        Digest excluding reward selector, gate path, and training-step count.
    """
    value = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(value, dict):
        raise ValueError("resolved training configuration must be a mapping")
    value = json.loads(json.dumps(value, default=str))
    value.get("env", {}).pop("reward_mode", None)
    value.get("training", {}).pop("survival_gate_manifest", None)
    value.get("ppo", {}).pop("total_timesteps", None)
    return _digest(value)


def _read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object from disk, rejecting other JSON root types.

    Args:
        path: JSON file to load.

    Returns:
        Parsed object mapping.
    """
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _data_identity(manifest: dict[str, Any]) -> str:
    """Hash the dataset and model-input identities in a run manifest.

    Args:
        manifest: Run-manifest mapping containing data and schema identities.

    Returns:
        Digest of the fields that define the model input dataset.
    """
    return _digest(
        {
            "datasets": manifest.get("datasets"),
            "feature_cache": manifest.get("feature_cache"),
            "source": manifest.get("source"),
            "action_schema": manifest.get("action_schema"),
            "observation_schema": manifest.get("observation_schema"),
            "sequence_feature_schema": manifest.get("sequence_feature_schema"),
        }
    )


def _has_training_abort_conflict(cfg: Any) -> bool:
    """Whether activity or policy-fit aborts conflict with survival qualification.

    Args:
        cfg: Resolved training configuration.

    Returns:
        Whether an early activity or equity-gate abort is enabled.
    """
    training = cfg.get("training", {}) if hasattr(cfg, "get") else {}
    block = training.get("early_abort", {}) if hasattr(training, "get") else {}
    if block is None:
        return False
    if not hasattr(block, "get"):
        return True
    if not bool(block.get("enabled", True)):
        return False
    return bool(block.get("stop_on_no_trades", False)) or bool(
        block.get("stop_on_equity_gate", False)
    )


def _has_full_split_cap_conflict(cfg: Any) -> bool:
    """Whether qualification config can shorten its training path or dataset.

    Args:
        cfg: Resolved training and environment configuration.

    Returns:
        Whether the run uses a capped episode or dataset.
    """
    training = cfg.get("training", {}) if hasattr(cfg, "get") else {}
    env = cfg.get("env", {}) if hasattr(cfg, "get") else {}
    return (
        str(training.get("episode_mode", "full_split")).strip().lower() != "full_split"
        or training.get("max_days") is not None
        or env.get("max_episode_steps") is not None
    )


def _complete_breach_free_path(record: dict[str, Any], *, survival_key: str) -> bool:
    """Require explicit completion, survival, and a typed zero-breach count.

    Args:
        record: Evaluation result fields for one seed or fold.
        survival_key: Result key that records survival status.

    Returns:
        Whether the path completed and survived with zero breach sessions.
    """
    breaches = record.get("n_breach_sessions")
    return (
        record.get(survival_key) is True
        and record.get("completed_data_split") is True
        and isinstance(breaches, int)
        and not isinstance(breaches, bool)
        and breaches == 0
    )


def _validate_qualification_manifest(
    *, manifest: dict[str, Any], cfg: Any, args: Any, seed: int
) -> None:
    """Require run provenance to describe the exact survival qualification.

    Args:
        manifest: Run manifest emitted by the completed training run.
        cfg: Configuration requested for the qualification run.
        args: Parsed training options that define algorithm and fold settings.
        seed: Expected seed for this run.
    """
    if int(manifest.get("seed", -1)) != int(seed):
        raise ValueError("run-manifest seed does not match the configured seed")
    protocol = manifest.get("training_protocol", {})
    if not isinstance(protocol, dict):
        raise ValueError("run-manifest training protocol must be an object")
    reward = protocol.get("reward", {})
    walk_forward = protocol.get("walk_forward", {})
    architecture = manifest.get("training_architecture", {})
    stop_schema = manifest.get("stop_candidate_schema", {})
    constrained = protocol.get("constrained_rl", {})
    if not all(
        isinstance(item, dict)
        for item in (reward, walk_forward, architecture, stop_schema, constrained)
    ):
        raise ValueError("run-manifest qualification metadata must be objects")
    if protocol.get("training_phase") != "survival_qualification":
        raise ValueError("run manifest does not identify survival-qualification training")
    observation_schema = manifest.get("observation_schema")
    env_cfg = cfg.get("env", {}) if hasattr(cfg, "get") else {}
    entry_state_visibility = bool(
        env_cfg.get("entry_state_machine", False) and env_cfg.get("entry_state_observation", False)
    )
    expected_observation_schema = build_observation_schema(
        SURVIVAL_OBSERVATION_SCHEMA,
        entry_state_visibility=entry_state_visibility,
    ).to_dict()
    if (
        not isinstance(observation_schema, dict)
        or observation_schema.get("version") != SURVIVAL_OBSERVATION_SCHEMA
        or observation_schema.get("observation_width")
        != expected_observation_schema["observation_width"]
        or observation_schema.get("observation_coordinates")
        != expected_observation_schema["observation_coordinates"]
        or observation_schema.get("entry_state_visibility") is not entry_state_visibility
    ):
        raise ValueError(
            "run manifest observation schema does not match the configured survival "
            "risk-budget coordinates"
        )
    sequence_schema = manifest.get("sequence_feature_schema")
    if not isinstance(sequence_schema, dict):
        raise ValueError("run manifest lacks the survival sequence feature schema")
    columns = sequence_schema.get("columns")
    if not isinstance(columns, list) or not columns:
        raise ValueError("run manifest has an invalid survival sequence feature schema")
    if "reachable_r_valid" not in columns:
        raise ValueError("run manifest sequence schema omits reachable_r_valid")
    expected_sequence_schema = build_sequence_feature_schema(
        columns, include_validity_channels=True
    )
    if (
        sequence_schema.get("version") != SEQUENCE_FEATURE_VALIDITY_SCHEMA_VERSION
        or sequence_schema != expected_sequence_schema
    ):
        raise ValueError(
            "run manifest sequence feature schema does not include valid missingness channels"
        )
    required_setup_columns = {column for _, column in trade_setup_candidate_feature_columns()}
    missing_setup_columns = required_setup_columns.difference(columns)
    if missing_setup_columns:
        raise ValueError(
            "run manifest sequence schema omits timeframe-specific setup eligibility "
            f"features ({len(missing_setup_columns)} missing)"
        )
    if protocol.get("mvp_mode") is not False:
        raise ValueError("survival qualification used a capped MVP dataset")
    if protocol.get("locked_oos_selection_allowed") is not False:
        raise ValueError("survival qualification allowed locked-OOS selection")
    if protocol.get("algorithm") != str(args.algo) or protocol.get("seed") != int(seed):
        raise ValueError("training protocol algorithm or seed differs from the gate request")
    if reward.get("mode") != "survival" or reward.get("selector") != str(args.reward):
        raise ValueError("training protocol reward differs from the survival gate request")
    if not walk_forward.get("enabled") or int(walk_forward.get("folds", 0)) != int(args.wf_splits):
        raise ValueError("training protocol walk-forward setup differs from the gate request")
    if architecture.get("algorithm") != str(args.algo) or architecture.get("arch") != str(
        args.arch
    ):
        raise ValueError("training architecture differs from the survival gate request")
    if stop_schema.get("strategy_name") != str(args.strategy):
        raise ValueError("training strategy differs from the survival gate request")
    if bool(constrained.get("enabled", False)):
        raise ValueError("survival qualification used a scalarized constrained objective")

    config_record = manifest.get("config", {})
    if not isinstance(config_record, dict):
        raise ValueError("run-manifest configuration record must be an object")
    config_path = Path(str(config_record.get("path", ""))).expanduser().resolve(strict=True)
    if file_sha256(config_path) != config_record.get("sha256"):
        raise ValueError("effective configuration snapshot checksum differs from run manifest")
    try:
        saved_cfg = OmegaConf.load(config_path)
    except (OSError, OmegaConfBaseException) as exc:
        raise ValueError(f"effective configuration snapshot cannot be loaded: {exc}") from exc
    if str(saved_cfg.env.get("reward_mode", "")).strip().lower() != "survival":
        raise ValueError("effective configuration snapshot did not train with survival reward")
    account_contract_error = _survival_account_contract_error(saved_cfg)
    if account_contract_error:
        raise ValueError(account_contract_error)
    timeframe_contract_error = _survival_timeframe_contract_error(saved_cfg)
    if timeframe_contract_error:
        raise ValueError(timeframe_contract_error)
    if saved_cfg.env.get("strict_research_eligibility", False) is not True:
        raise ValueError("survival run configuration did not require strict NY-session eligibility")
    if _has_full_split_cap_conflict(saved_cfg):
        raise ValueError("survival run configuration capped the training split")
    if _has_training_abort_conflict(saved_cfg):
        raise ValueError("survival run configuration enabled activity or equity-gate early aborts")
    if survival_config_identity(saved_cfg) != survival_config_identity(cfg):
        raise ValueError("effective configuration snapshot differs from the survival gate request")


def build_survival_gate(
    *,
    cfg: Any,
    args: Any,
    run_dir: Path,
    seed_results: list[dict[str, Any]],
    seeds: list[int],
    forced_failures: list[str] | None = None,
) -> Path:
    """Write a passing gate only when every required seed and WF fold survives.

    Args:
        cfg: Resolved qualification configuration.
        args: Parsed run options used to validate the protocol.
        run_dir: Directory containing per-seed results and manifests.
        seed_results: Completed result records for configured seeds.
        seeds: Required seed values for qualification.
        forced_failures: Optional pre-existing reasons that must fail the gate.

    Returns:
        Path to the written survival gate manifest.
    """
    # Callers that already know qualification failed must not accidentally write
    # a passing artifact just because stale per-seed evidence happens to exist.
    failures = [reason for reason in (forced_failures or []) if reason]
    evidence: list[dict[str, Any]] = []
    if str(cfg.env.get("reward_mode", "")).lower() != "survival":
        failures.append("qualification reward mode is not survival")
    account_contract_error = _survival_account_contract_error(cfg)
    if account_contract_error:
        failures.append(account_contract_error)
    timeframe_contract_error = _survival_timeframe_contract_error(cfg)
    if timeframe_contract_error:
        failures.append(timeframe_contract_error)
    if cfg.env.get("strict_research_eligibility", False) is not True:
        failures.append("survival qualification requires env.strict_research_eligibility=true")
    observation_error = _survival_observation_schema_error(cfg)
    if observation_error:
        failures.append(observation_error)
    if _has_training_abort_conflict(cfg):
        failures.append("survival qualification cannot enable activity or equity-gate early aborts")
    if _has_full_split_cap_conflict(cfg):
        failures.append("survival qualification requires the complete uncapped training split")
    if len(seeds) < MIN_SURVIVAL_SEEDS or len(set(seeds)) != len(seeds):
        failures.append(f"requires at least {MIN_SURVIVAL_SEEDS} unique seeds")
    if not args.walk_forward or int(args.wf_splits) < MIN_SURVIVAL_WF_SPLITS:
        failures.append(f"at least {MIN_SURVIVAL_WF_SPLITS} purged walk-forward folds are required")
    if bool(getattr(args, "mvp", False)):
        failures.append("survival qualification cannot use the capped MVP dataset")
    if bool(getattr(args, "allow_locked_oos_for_selection", False)):
        failures.append("survival qualification cannot select using exposed report-period data")
    results_by_seed = {int(result["seed"]): result for result in seed_results}
    if len(results_by_seed) != len(seed_results):
        failures.append("training results contain duplicate seeds")
    if set(results_by_seed) != set(map(int, seeds)):
        failures.append("training results do not match the configured seed set")

    common_data_identity: str | None = None
    for seed in map(int, seeds):
        result = results_by_seed.get(seed)
        if result is None:
            continue
        seed_dir = run_dir / "seeds" / f"seed{seed}" if len(seeds) > 1 else run_dir
        manifest_path = seed_dir / "run_manifest.json"
        gate_path = seed_dir / "train_equity_gate.json"
        outcome_path = seed_dir / "train_path_outcome.json"
        wf_path = seed_dir / "walk_forward.json"
        try:
            manifest = _read_json(manifest_path)
            _validate_qualification_manifest(manifest=manifest, cfg=cfg, args=args, seed=seed)
            train_gate = _read_json(gate_path)
            outcome = _read_json(outcome_path)
            wf = _read_json(wf_path)
            checkpoint = seed_dir / str(manifest["artifact_paths"]["checkpoint"])
            if not checkpoint.is_file():
                raise ValueError("seed checkpoint is missing")
            checkpoint_hash = file_sha256(checkpoint)
            if checkpoint_hash != manifest["checkpoint"]["sha256"]:
                raise ValueError("seed checkpoint hash differs from run manifest")
            if (
                train_gate.get("hard_risk_ok") is not True
                or train_gate.get("breached") is not False
            ):
                raise ValueError("train equity evidence reports a hard-risk failure")
            if not _complete_breach_free_path(outcome, survival_key="survived_full_split"):
                raise ValueError("full train-split survival gate failed")
            folds = wf.get("folds", [])
            if len(folds) != int(args.wf_splits):
                raise ValueError("walk-forward fold count differs from required split count")
            if any(
                not isinstance(fold, dict)
                or not _complete_breach_free_path(fold, survival_key="survived_full_year")
                for fold in folds
            ):
                raise ValueError("one or more purged walk-forward folds breached or ended early")
            data_identity = _data_identity(manifest)
            if common_data_identity is not None and data_identity != common_data_identity:
                raise ValueError("seed data or model schema identity differs from other seeds")
            common_data_identity = data_identity
            evidence.append(
                {
                    "seed": seed,
                    "checkpoint": str(checkpoint.resolve()),
                    "checkpoint_sha256": checkpoint_hash,
                    "run_manifest": str(manifest_path.resolve()),
                    "run_manifest_sha256": file_sha256(manifest_path),
                    "train_gate": str(gate_path.resolve()),
                    "train_gate_sha256": file_sha256(gate_path),
                    "train_path_outcome": str(outcome_path.resolve()),
                    "train_path_outcome_sha256": file_sha256(outcome_path),
                    "walk_forward": str(wf_path.resolve()),
                    "walk_forward_sha256": file_sha256(wf_path),
                    "data_identity": data_identity,
                    "datasets": manifest.get("datasets"),
                    "feature_cache_identity": manifest.get("feature_cache"),
                    "feature_cache_hash": manifest.get("feature_cache", {}).get("sha256"),
                    "source": manifest.get("source"),
                    "action_schema": manifest.get("action_schema"),
                    "observation_schema": manifest.get("observation_schema"),
                    "sequence_feature_schema": manifest.get("sequence_feature_schema"),
                }
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            failures.append(f"seed {seed}: {exc}")

    if len(evidence) != len(seeds):
        failures.append("not every configured seed has complete evidence")
    gate = {
        "schema_version": 1,
        "status": "pass" if not failures else "fail",
        "priority": "survival_before_portfolio_optimization",
        "minimum_seed_count": MIN_SURVIVAL_SEEDS,
        "minimum_walk_forward_splits": MIN_SURVIVAL_WF_SPLITS,
        "seeds": list(map(int, seeds)),
        "walk_forward_splits": int(args.wf_splits),
        "config_identity": survival_config_identity(cfg),
        "algo": str(args.algo),
        "arch": str(args.arch),
        "strategy": str(args.strategy),
        "reward_selector": str(args.reward),
        "data_identity": common_data_identity,
        "evidence": evidence,
        "failures": failures,
    }
    path = run_dir / "survival_phase_gate.json"
    write_text_atomic(path, json.dumps(gate, indent=2))
    if failures:
        raise SystemExit(f"SURVIVAL_PHASE_GATE_FAILED: {failures}")
    return path


def validate_portfolio_gate(*, cfg: Any, args: Any) -> dict[str, Any] | None:
    """Validate a portfolio run's referenced qualification gate and checkpoint.

    Args:
        cfg: Resolved portfolio configuration.
        args: Parsed training arguments identifying the checkpoint and policy setup.

    Returns:
        Validated qualification gate, or ``None`` when no gate is configured.
    """
    reward_mode = str(cfg.env.get("reward_mode", "dsr")).strip().lower()
    raw_path = cfg.training.get("survival_gate_manifest")
    if reward_mode == "survival" or raw_path:
        observation_error = _survival_observation_schema_error(cfg)
        if observation_error:
            raise SystemExit(observation_error)
    if reward_mode == "survival":
        account_contract_error = _survival_account_contract_error(cfg)
        if account_contract_error:
            raise SystemExit(account_contract_error)
        timeframe_contract_error = _survival_timeframe_contract_error(cfg)
        if timeframe_contract_error:
            raise SystemExit(timeframe_contract_error)
        if cfg.env.get("strict_research_eligibility", False) is not True:
            raise SystemExit(
                "survival qualification requires env.strict_research_eligibility=true "
                "to reject a missing NY-session calendar"
            )
        if _has_training_abort_conflict(cfg):
            raise SystemExit(
                "survival qualification cannot enable activity or equity-gate early aborts"
            )
        if raw_path:
            raise SystemExit("survival qualification must not reference a prior portfolio gate")
        if args.mvp or not args.walk_forward or int(args.wf_splits) < MIN_SURVIVAL_WF_SPLITS:
            raise SystemExit(
                "survival qualification requires full-split training and at least five "
                "purged walk-forward folds"
            )
        if bool(args.allow_locked_oos_for_selection):
            raise SystemExit(
                "survival qualification cannot select using exposed report-period data"
            )
        if bool(cfg.get("constrained_rl", {}).get("enabled", False)):
            raise SystemExit("survival qualification cannot combine with scalarized Q5 rewards")
        if _has_full_split_cap_conflict(cfg):
            raise SystemExit("survival qualification requires the complete uncapped training split")
        from trading.policy import resolve_trading_policy

        if resolve_trading_policy(cfg).repeated_payout:
            raise SystemExit("survival qualification does not support repeated payouts")
        if args.algo == "ppo" and (
            float(cfg.ppo.get("gamma", 0.99)) != 1.0
            or float(cfg.ppo.get("gae_lambda", 0.95)) != 1.0
        ):
            raise SystemExit("survival qualification requires PPO gamma=1 and gae_lambda=1")
        if args.algo == "sac" and float(cfg.sac.get("gamma", 0.99)) != 1.0:
            raise SystemExit("survival qualification requires SAC gamma=1")
        if args.algo not in {"ppo", "sac"}:
            raise SystemExit(f"survival qualification does not support {args.algo!r}")
        seeds = list(args.seeds) if args.seeds else [args.seed]
        if len(seeds) < MIN_SURVIVAL_SEEDS or len(set(seeds)) != len(seeds):
            raise SystemExit(f"survival qualification requires {MIN_SURVIVAL_SEEDS} unique seeds")
        return None
    if not raw_path:
        raise SystemExit(
            "portfolio reward training is blocked until training.survival_gate_manifest "
            "references a passing survival qualification"
        )
    if cfg.env.get("strict_research_eligibility", False) is not True:
        raise SystemExit(
            "portfolio training requires env.strict_research_eligibility=true "
            "to match the survival qualification"
        )
    if _has_training_abort_conflict(cfg):
        raise SystemExit(
            "portfolio training config has activity or equity-gate early aborts "
            "that conflict with survival qualification"
        )
    if args.algo not in {"ppo", "sac"} or not args.resume_checkpoint:
        raise SystemExit("portfolio phase requires an SB3 resume from a gated survival checkpoint")
    portfolio_seeds = list(args.seeds) if args.seeds else [args.seed]
    if len(portfolio_seeds) != 1:
        raise SystemExit("portfolio checkpoint resume requires exactly one seed per run")
    if bool(args.allow_locked_oos_for_selection):
        raise SystemExit("portfolio training cannot select using exposed report-period data")
    try:
        gate_path = Path(str(raw_path)).expanduser().resolve(strict=True)
        gate = _read_json(gate_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"invalid survival phase gate: {exc}") from exc
    raw_seeds = gate.get("seeds")
    entries = gate.get("evidence")
    walk_forward_splits = gate.get("walk_forward_splits")
    minimum_seed_count = gate.get("minimum_seed_count")
    minimum_walk_forward_splits = gate.get("minimum_walk_forward_splits")
    if (
        not isinstance(gate.get("schema_version"), int)
        or isinstance(gate.get("schema_version"), bool)
        or gate.get("schema_version") != 1
        or gate.get("priority") != "survival_before_portfolio_optimization"
        or gate.get("status") != "pass"
        or not isinstance(raw_seeds, list)
        or len(raw_seeds) < MIN_SURVIVAL_SEEDS
        or not isinstance(entries, list)
        or not isinstance(walk_forward_splits, int)
        or isinstance(walk_forward_splits, bool)
        or walk_forward_splits < MIN_SURVIVAL_WF_SPLITS
        or not isinstance(minimum_seed_count, int)
        or isinstance(minimum_seed_count, bool)
        or minimum_seed_count < MIN_SURVIVAL_SEEDS
        or not isinstance(minimum_walk_forward_splits, int)
        or isinstance(minimum_walk_forward_splits, bool)
        or minimum_walk_forward_splits < MIN_SURVIVAL_WF_SPLITS
    ):
        raise SystemExit("survival phase gate is not a passing six-seed gate")
    if any(not isinstance(value, int) or isinstance(value, bool) for value in raw_seeds):
        raise SystemExit("survival gate seed list must contain integer seeds")
    if any(not isinstance(item, dict) for item in entries):
        raise SystemExit("survival gate evidence entries must be objects")
    gate_seeds = list(raw_seeds)
    entry_seeds = [item.get("seed") for item in entries]
    if any(not isinstance(value, int) or isinstance(value, bool) for value in entry_seeds):
        raise SystemExit("survival gate evidence must contain integer seeds")
    if len(set(gate_seeds)) != len(gate_seeds) or len(set(entry_seeds)) != len(entries):
        raise SystemExit("survival gate seed list or evidence contains duplicates")
    if set(entry_seeds) != set(gate_seeds):
        raise SystemExit("survival gate seed list and evidence set do not match")
    if gate.get("config_identity") != survival_config_identity(cfg):
        raise SystemExit("portfolio config differs from the survival-qualified behavior config")
    if (str(args.algo), str(args.arch), str(args.strategy)) != (
        gate.get("algo"),
        gate.get("arch"),
        gate.get("strategy"),
    ):
        raise SystemExit(
            "portfolio algorithm, architecture, or strategy differs from qualification"
        )
    if str(args.reward) != gate.get("reward_selector"):
        raise SystemExit("portfolio reward selector differs from survival qualification")
    seed = int(portfolio_seeds[0])
    entry = next(
        (item for item in gate.get("evidence", []) if int(item.get("seed", -1)) == seed),
        None,
    )
    if entry is None:
        raise SystemExit(f"seed {seed} is not present in the survival phase gate")
    checkpoint = Path(str(args.resume_checkpoint)).expanduser().resolve()
    if checkpoint != Path(str(entry["checkpoint"])).resolve():
        raise SystemExit("resume checkpoint is not the checkpoint qualified for this seed")
    current_source = source_state(repository_root(__file__))
    if entry.get("source") != current_source:
        raise SystemExit("portfolio source tree differs from the survival-qualified source tree")
    expected_data_identity = gate.get("data_identity")
    for evidence in entries:
        try:
            for hash_key, path_key in (
                ("checkpoint_sha256", "checkpoint"),
                ("run_manifest_sha256", "run_manifest"),
                ("train_gate_sha256", "train_gate"),
                ("train_path_outcome_sha256", "train_path_outcome"),
                ("walk_forward_sha256", "walk_forward"),
            ):
                path = Path(str(evidence[path_key]))
                if not path.is_file() or file_sha256(path) != evidence[hash_key]:
                    raise ValueError(f"{path_key} checksum differs from survival gate evidence")
            manifest_path = Path(str(evidence["run_manifest"]))
            manifest = _read_json(manifest_path)
            _validate_qualification_manifest(
                manifest=manifest, cfg=cfg, args=args, seed=int(evidence["seed"])
            )
            checkpoint_path = Path(str(manifest["checkpoint"]["path"])).resolve(strict=True)
            if checkpoint_path != Path(str(evidence["checkpoint"])).resolve():
                raise ValueError("run-manifest checkpoint path differs from gate evidence")
            if file_sha256(checkpoint_path) != evidence["checkpoint_sha256"]:
                raise ValueError("checkpoint checksum differs from gate evidence")
            train_gate = _read_json(Path(str(evidence["train_gate"])))
            if (
                train_gate.get("hard_risk_ok") is not True
                or train_gate.get("breached") is not False
            ):
                raise ValueError("train equity evidence reports a hard-risk failure")
            outcome = _read_json(Path(str(evidence["train_path_outcome"])))
            if not _complete_breach_free_path(outcome, survival_key="survived_full_split"):
                raise ValueError("train split no longer verifies as a complete survivor")
            wf = _read_json(Path(str(evidence["walk_forward"])))
            folds = wf.get("folds", [])
            if len(folds) != int(gate.get("walk_forward_splits", -1)) or any(
                not isinstance(fold, dict)
                or not _complete_breach_free_path(fold, survival_key="survived_full_year")
                for fold in folds
            ):
                raise ValueError("walk-forward survival evidence is incomplete or failed")
            if _data_identity(manifest) != expected_data_identity:
                raise ValueError("per-seed data identity differs from the passing gate")
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SystemExit(
                f"invalid survival qualification for seed {evidence.get('seed')}: {exc}"
            ) from exc
    return gate


def validate_portfolio_data(
    *, gate: dict[str, Any], dataset_records: dict[str, Any], feat_cache: Path
) -> None:
    """Require portfolio data and feature-cache identity to match qualification.

    Args:
        gate: Passing survival gate containing per-seed data identities.
        dataset_records: Dataset manifest records for the portfolio run.
        feat_cache: Feature-cache path whose hash sidecar identifies its content.
    """
    seeds = gate.get("evidence", [])
    if not seeds:
        raise SystemExit("survival gate has no per-seed data evidence")
    try:
        cache_hash = Path(str(feat_cache) + ".hash").read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SystemExit(f"portfolio feature-cache identity is unavailable: {exc}") from exc
    expected = seeds[0]
    if dataset_records != expected.get("datasets"):
        raise SystemExit("portfolio datasets differ from the survival-qualified datasets")
    if cache_hash != expected.get("feature_cache_hash"):
        raise SystemExit("portfolio feature cache differs from survival-qualified features")
