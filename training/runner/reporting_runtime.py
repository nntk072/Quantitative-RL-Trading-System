from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from artifacts.atomic import write_text_atomic
from training.artifacts import aggregate_seed_results, build_training_log
from training.artifacts.aggregation import _recorded_true
from training.callbacks.activity import classify_zero_trade_cause


def finalize_training_run(
    *,
    cfg: Any,
    args: Any,
    is_multi_seed: bool,
    seed_results: list[dict[str, Any]],
    timesteps: int,
    train_bar_count: int,
    test_bar_count: int,
    run_dir: Path,
    feat_cache: Path,
    feature_columns: list[str],
    seeds: list[int],
) -> dict[str, Any]:
    """Aggregate seed results, persist the training log, and emit optional W&B metrics.

    Args:
        cfg: Run configuration used by this operation.
        args: Parsed command-line arguments for this operation.
        is_multi_seed: Whether to enable or require the is multi seed.
        seed_results: Items supplied for the seed results, in input order.
        timesteps: Numeric value used for the timesteps.
        train_bar_count: Number specifying the train bar count for this operation.
        test_bar_count: Number specifying the test bar count for this operation.
        run_dir: Text or path value identifying the run dir.
        feat_cache: Text or path value identifying the feat cache.
        feature_columns: Items supplied for the feature columns, in input order.
        seeds: Items supplied for the seeds, in input order.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    strategy_actions = bool(cfg.env.get("strategy_actions", False))
    strategy_name = (
        "baseline" if not strategy_actions else str(cfg.strategy.get("name", args.strategy))
    )

    if is_multi_seed:
        training_log = aggregate_seed_results(
            seed_results=seed_results,
            seed=args.seed,
            mvp=args.mvp,
            algo=args.algo,
            arch=args.arch,
            reward=args.reward,
            timesteps=timesteps,
            train_bars=train_bar_count,
            test_bars=test_bar_count,
            strategy=strategy_name,
            strategy_actions=strategy_actions,
            cfg=cfg,
            args=args,
            run_dir=run_dir,
        )
    else:
        single = seed_results[0]
        training_log = build_training_log(
            seed=single["seed"],
            mvp=args.mvp,
            algo=args.algo,
            arch=args.arch,
            reward=args.reward,
            environment_reward_mode=str(cfg.env.get("reward_mode", "dsr")),
            equity_log_growth_scale=float(cfg.env.get("equity_log_growth_scale", 100.0)),
            timesteps=timesteps,
            train_bars=train_bar_count,
            test_bars=test_bar_count,
            test_m=single["test_m"],
            test_result=single["test_result"],
            train_result=single.get("train_result"),
            strategy=strategy_name,
            strategy_actions=strategy_actions,
            action_space_width=single.get("action_space_width"),
            observation_account_dim=single.get("observation_account_dim"),
            observation_space_shapes=single.get("observation_space_shapes"),
            action_schema=single.get("action_schema"),
            observation_schema=single.get("observation_schema"),
            env_flags=single.get("env_flags"),
            oos_role=single.get("oos_role", "final_report_only"),
        )
        training_log["train_equity_ok"] = single["train_gate"].get("ok") is True
        training_log["train_end_equity"] = float(single["train_gate"]["end_equity"])
        training_log["train_equity_slope"] = float(single["train_gate"]["slope"])
        training_log["train_equity_reason"] = str(single["train_gate"]["reason"])
        training_log["early_abort_reason"] = single["abort_reason"] or ""
        training_log["timesteps_completed"] = single["model_num_timesteps"]

    inactive_seeds = [
        int(result["seed"])
        for result in seed_results
        if result["train_activity_gate"].get("ok") is not True
    ]
    survival_objective = str(cfg.env.get("reward_mode", "dsr")).strip().lower() == "survival"
    survival_ok_by_seed = (
        {
            str(result["seed"]): _complete_breach_free_train_split(
                result.get("train_result", {}), result.get("train_gate", {})
            )
            for result in seed_results
        }
        if survival_objective
        else {}
    )
    failed_survival_seeds = [
        int(result["seed"])
        for result in seed_results
        if not (
            survival_ok_by_seed[str(result["seed"])]
            if survival_objective
            else result["train_gate"].get("ok") is True
        )
    ]
    policy_fit_miss_seeds = [
        int(result["seed"])
        for result in seed_results
        if _peak_dd_policy_missed(result["train_gate"])
    ]
    hard_survival_failure_seeds = [
        int(result["seed"])
        for result in seed_results
        if result["train_gate"].get("ok") is not True
        and not _peak_dd_policy_only_miss(result["train_gate"])
    ]
    if survival_objective:
        hard_survival_failure_seeds = list(failed_survival_seeds)
    aborts = {
        str(result["seed"]): str(result["abort_reason"])
        for result in seed_results
        if result["abort_reason"]
    }
    expected_seeds = [int(value) for value in seeds]
    result_seeds = [int(result["seed"]) for result in seed_results]
    seed_results_cover_request = (
        bool(expected_seeds)
        and len(expected_seeds) == len(set(expected_seeds))
        and len(result_seeds) == len(expected_seeds)
        and len(result_seeds) == len(set(result_seeds))
        and set(result_seeds) == set(expected_seeds)
    )
    training_completed_by_seed = {
        str(result["seed"]): int(result.get("model_num_timesteps", 0)) >= int(timesteps)
        for result in seed_results
    }
    training_completed = (
        seed_results_cover_request and all(training_completed_by_seed.values()) and not aborts
    )
    train_split_survival_ok = (
        seed_results_cover_request and bool(seed_results) and not failed_survival_seeds
        if survival_objective
        else None
    )
    training_admissible = training_completed and not (
        failed_survival_seeds or aborts or (inactive_seeds and not survival_objective)
    )
    if any("nonfinite" in reason.lower() for reason in aborts.values()):
        overall_status = "FAIL_NUMERICAL"
    elif aborts:
        overall_status = "FAIL_EARLY_ABORT"
    elif hard_survival_failure_seeds:
        overall_status = "FAIL_TRAIN_SPLIT_SURVIVAL" if survival_objective else "FAIL_SURVIVAL"
    elif survival_objective:
        overall_status = "PASS_TRAIN_SPLIT_SURVIVAL" if training_completed else "INCOMPLETE"
    elif inactive_seeds:
        overall_status = "FAIL_INACTIVE"
    elif policy_fit_miss_seeds and training_completed:
        overall_status = "COMPLETED_POLICY_MISS_RETRAIN_REQUIRED"
    elif policy_fit_miss_seeds:
        overall_status = "INCOMPLETE_POLICY_MISS"
    else:
        overall_status = "PASS_ACTIVE" if training_completed else "INCOMPLETE"
    training_log["train_activity_ok"] = bool(seed_results) and not inactive_seeds
    training_log["train_split_survival_ok"] = train_split_survival_ok
    training_log["train_activity_ok_by_seed"] = {
        str(result["seed"]): _recorded_true(result["train_activity_gate"].get("ok"))
        for result in seed_results
    }
    training_log["train_split_survival_ok_by_seed"] = survival_ok_by_seed or None
    training_log["train_portfolio_fit_ok_by_seed"] = {
        str(result["seed"]): _recorded_true(result["train_gate"].get("ok"))
        for result in seed_results
    }
    if survival_objective:
        # Do not let the older return/equity-fit gate overrule survival status.
        training_log["train_equity_ok"] = bool(train_split_survival_ok)
    training_log["train_activity_status_by_seed"] = {
        str(result["seed"]): str(result["train_activity_gate"]["status"]) for result in seed_results
    }
    activity_statuses = [str(result["train_activity_gate"]["status"]) for result in seed_results]
    training_log["train_activity_status"] = (
        "NO_RESULTS"
        if not activity_statuses
        else "INACTIVE"
        if "INACTIVE" in activity_statuses
        else "ACTIVE_SPARSE"
        if "ACTIVE_SPARSE" in activity_statuses
        else "ACTIVE"
    )
    training_log["train_n_trades"] = {
        str(result["seed"]): int(result["train_activity_gate"]["n_trades"])
        for result in seed_results
    }
    training_log["best_checkpoint_status_by_seed"] = {
        str(result["seed"]): str(result.get("best_checkpoint_status", "NO_ACTIVE_CHECKPOINT"))
        for result in seed_results
    }
    training_log["best_checkpoint_n_trades_by_seed"] = {
        str(result["seed"]): int(result.get("best_checkpoint_n_trades", 0))
        for result in seed_results
    }
    training_log["deterministic_viability_evaluations_by_seed"] = {
        str(result["seed"]): result.get("deterministic_viability_evaluations", [])
        for result in seed_results
    }
    training_log["zero_trade_diagnosis_by_seed"] = {
        str(result["seed"]): classify_zero_trade_cause(
            int(result["train_activity_gate"]["n_trades"]),
            result.get("train_result", {}).get("entry_state_diagnostics"),
            result.get("train_result", {}).get("entry_diag"),
        )
        for result in seed_results
    }
    if len(seed_results) == 1:
        training_log["zero_trade_diagnosis"] = training_log["zero_trade_diagnosis_by_seed"][
            str(seed_results[0]["seed"])
        ]
    training_log["inactive_seeds"] = inactive_seeds
    training_log["failed_survival_seeds"] = failed_survival_seeds
    training_log["hard_survival_failure_seeds"] = hard_survival_failure_seeds
    training_log["hard_risk_ok_by_seed"] = {
        str(result["seed"]): (
            result["train_gate"].get("hard_risk_ok") is True
            and result["train_gate"].get("breached") is False
            if survival_objective
            else _hard_risk_pass(result["train_gate"])
        )
        for result in seed_results
    }
    training_log["policy_fit_miss_seeds"] = policy_fit_miss_seeds
    training_log["policy_fit_status"] = (
        "MISS"
        if policy_fit_miss_seeds
        else (
            "DISABLED"
            if all(
                float(result["train_gate"].get("peak_trailing_dd_limit", 0.0)) <= 0.0
                for result in seed_results
            )
            else "PASS"
        )
    )
    training_log["training_completed_by_seed"] = training_completed_by_seed
    training_log["training_completed"] = training_completed
    training_log["seed_results_cover_request"] = seed_results_cover_request
    training_log["missing_seed_results"] = sorted(set(expected_seeds) - set(result_seeds))
    training_log["unexpected_seed_results"] = sorted(set(result_seeds) - set(expected_seeds))
    training_log["retraining_recommended"] = bool(
        policy_fit_miss_seeds and training_completed and not survival_objective
    )
    training_log["early_abort_reasons_by_seed"] = aborts
    training_log["training_admissible"] = training_admissible
    training_log["training_admissibility_scope"] = (
        "all_configured_train_splits_only"
        if survival_objective
        else "all_configured_training_splits"
    )
    if survival_objective:
        training_log["qualification_gate_artifact"] = "survival_phase_gate.json"
    training_log["overall_status"] = overall_status

    sequence_schemas = [
        result["sequence_feature_schema"]
        for result in seed_results
        if result.get("sequence_feature_schema") is not None
    ]
    if sequence_schemas:
        if any(schema != sequence_schemas[0] for schema in sequence_schemas[1:]):
            raise ValueError("multi-seed run produced inconsistent sequence feature schemas")
        training_log["sequence_feature_schema"] = sequence_schemas[0]

    training_log["phase_timings_seconds"] = {
        str(result["seed"]): result["phase_timings_seconds"] for result in seed_results
    }
    training_log["run_manifests"] = [str(result["run_manifest"]) for result in seed_results]
    cache_hash_path = Path(str(feat_cache) + ".hash")
    if not cache_hash_path.is_file():
        raise RuntimeError(f"feature cache hash sidecar missing: {cache_hash_path}")
    training_log["feature_cache_hash"] = cache_hash_path.read_text(encoding="utf-8").strip()
    training_log["feature_cache_name"] = feat_cache.name
    effective_config_path = run_dir / "config.yaml"
    if not effective_config_path.is_file():
        raise RuntimeError(f"effective config snapshot missing: {effective_config_path}")
    training_log["effective_config_sha256"] = hashlib.sha256(
        effective_config_path.read_bytes()
    ).hexdigest()
    training_log["feature_columns"] = feature_columns
    training_log["feature_schema_sha256"] = hashlib.sha256(
        json.dumps(training_log["feature_columns"], separators=(",", ":")).encode()
    ).hexdigest()
    write_text_atomic(run_dir / "training_log.json", json.dumps(training_log, indent=2))
    if hard_survival_failure_seeds:
        raise SystemExit(f"TRAIN_SURVIVAL_FAILED: seeds={hard_survival_failure_seeds}")
    if inactive_seeds and not survival_objective:
        raise SystemExit(f"TRAIN_ACTIVITY_FAILED: zero train-replay trades; seeds={inactive_seeds}")
    if aborts:
        raise SystemExit(f"TRAIN_EARLY_ABORT: {aborts}")

    if args.wandb:
        try:
            import wandb
        except ImportError:
            raise SystemExit("--wandb requires the wandb package: pip install wandb")
        wandb.init(
            project="aalto-liquidity-sweep",
            name=run_dir.name,
            config={
                "algo": args.algo,
                "arch": args.arch,
                "reward": args.reward,
                "seed": args.seed,
                "mvp": args.mvp,
                "timesteps": timesteps,
                "n_seeds": len(seeds),
            },
        )
        if args.allow_locked_oos_for_selection:
            wandb.log(
                {
                    "sharpe": training_log.get(
                        "test_sharpe_mean", training_log.get("test_sharpe", 0.0)
                    ),
                    "test_sharpe": training_log.get(
                        "test_sharpe_mean", training_log.get("test_sharpe", 0.0)
                    ),
                    "test_max_dd": training_log.get(
                        "test_max_dd_mean", training_log.get("test_max_dd", 0.0)
                    ),
                    "test_trades": training_log.get(
                        "test_n_trades_mean", training_log.get("test_trades", 0)
                    ),
                    "test_return": training_log.get(
                        "test_total_return_pct_mean", training_log.get("test_return", 0.0)
                    ),
                    "test_breaches": training_log.get("test_breaches", 0),
                }
            )
        wandb.finish()

    return training_log


def _peak_dd_policy_missed(gate: dict[str, Any]) -> bool:
    """Identify policy non-fit even when another hard-risk condition also failed.

    Args:
        gate: Key-value data used for the gate.

    Returns:
        Whether peak dd policy missed meets the requested condition.
    """
    reasons = {part.strip() for part in str(gate.get("reason", "")).split(",") if part.strip()}
    return "peak_trailing_dd" in reasons


def _complete_breach_free_train_split(outcome: Any, gate: Any) -> bool:
    """Return whether one result proves a completed, breach-free train split.

    Args:
        outcome: Full-split evaluation result recorded by the rollout.
        gate: Train-equity assessment containing the explicit hard-risk result.

    Returns:
        Whether the outcome proves survival through the complete train split.
    """
    if not isinstance(outcome, dict) or not isinstance(gate, dict):
        return False
    breaches = outcome.get("n_breach_sessions")
    return (
        gate.get("hard_risk_ok") is True
        and gate.get("breached") is False
        and outcome.get("survived_full_year") is True
        and outcome.get("completed_data_split") is True
        and isinstance(breaches, int)
        and not isinstance(breaches, bool)
        and breaches == 0
    )


def _hard_risk_pass(gate: Any) -> bool:
    """Require typed, internally consistent hard-risk evidence.

    Args:
        gate: Persisted hard-risk gate record.

    Returns:
        Whether available breach and hard-risk fields show a passing result.
    """
    if not isinstance(gate, dict):
        return False
    has_hard_risk = "hard_risk_ok" in gate
    has_breached = "breached" in gate
    hard_risk_ok = gate.get("hard_risk_ok")
    breached = gate.get("breached")
    if has_hard_risk and not isinstance(hard_risk_ok, bool):
        return False
    if has_breached and not isinstance(breached, bool):
        return False
    if has_hard_risk and has_breached and hard_risk_ok is breached:
        return False
    if has_hard_risk:
        return hard_risk_ok is True
    return has_breached and breached is False


def _peak_dd_policy_only_miss(gate: dict[str, Any]) -> bool:
    """Separate a DD-only policy miss from a hard-risk or malformed-gate failure.

    Args:
        gate: Key-value data used for the gate.

    Returns:
        Whether peak dd policy only miss meets the requested condition.
    """
    reasons = {part.strip() for part in str(gate.get("reason", "")).split(",") if part.strip()}
    return (
        gate.get("ok") is False
        and "peak_trailing_dd" in reasons
        and gate.get("breached") is False
        and ("hard_risk_ok" not in gate or gate.get("hard_risk_ok") is True)
        and "max_loss_stopped_trading" not in reasons
    )
