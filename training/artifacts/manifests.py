"""Training run manifest and schema helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from omegaconf import OmegaConf

from evaluation.reporting.run_manifest import build_sequence_feature_schema
from simulation.environment.observations import HTF_BRANCHES
from simulation.environment.trading_environment_factory import mtf_settings
from training.artifacts.flags import strict_nonnegative_int

POLICY_INPUT_SCHEMA_VERSION = "policy-input-streams-v1"


def entry_funnel_by_split(
    train_result: dict[str, Any] | None, test_result: dict[str, Any] | None
) -> dict[str, dict[str, Any]]:
    """Build separately labeled train and report-only test entry funnels.

    Args:
        train_result: Key-value data used for the train result.
        test_result: Key-value data used for the test result.

    Returns:
        Mapping from ``str`` keys to ``dict[str, Any]`` values.
    """
    from training.configuration.variants import compute_tier1_funnel

    result: dict[str, dict[str, Any]] = {}
    for split, split_result in (("train", train_result), ("test", test_result)):
        if split_result is None:
            continue
        result[split] = compute_tier1_funnel(
            split_result.get("entry_diag"),
            split_result.get("entry_state_diagnostics"),
        )
    return result


def build_training_log(
    *,
    seed: int,
    mvp: bool,
    algo: str,
    arch: str,
    reward: str,
    timesteps: int,
    train_bars: int,
    test_bars: int,
    test_m: Any | None,
    test_result: dict[str, Any] | None,
    environment_reward_mode: str = "dsr",
    equity_log_growth_scale: float = 100.0,
    train_result: dict[str, Any] | None = None,
    strategy: str = "baseline",
    strategy_actions: bool = False,
    action_space_width: int | None = None,
    observation_account_dim: int | None = None,
    observation_space_shapes: dict[str, list[int]] | None = None,
    action_schema: dict[str, Any] | None = None,
    observation_schema: dict[str, Any] | None = None,
    env_flags: dict[str, Any] | None = None,
    oos_role: str = "final_report_only",
) -> dict[str, Any]:
    """Build the training_log.json dict from run results.

    Args:
        seed: Random seed used to make sampling reproducible.
        mvp: Whether to enable or require the mvp.
        algo: Text or path value identifying the algo.
        arch: Text or path value identifying the arch.
        reward: Text or path value identifying the reward.
        timesteps: Numeric value used for the timesteps.
        train_bars: Market bar or price data used for build the training_log.json dict from run results.
        test_bars: Market bar or price data used for build the training_log.json dict from run results.
        test_m: Test metrics, or ``None`` when report-only evaluation was not run.
        test_result: Report-only result, or ``None`` when it was not evaluated.
        environment_reward_mode: Text or path value identifying the environment reward mode.
        equity_log_growth_scale: Numeric value used for the equity log growth scale.
        train_result: Key-value data used for the train result.
        strategy: Strategy used to select or evaluate trades.
        strategy_actions: Whether to enable or require the strategy actions.
        action_space_width: Number specifying the action space width for this operation.
        observation_account_dim: Observation account dim used by the operation described above.
        observation_space_shapes: Items supplied for the observation space shapes, in input order.
        action_schema: Key-value data used for the action schema.
        observation_schema: Key-value data used for the observation schema.
        env_flags: Boolean or status values aligned with the input env flags.
        oos_role: Text or path value identifying the oos role.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    if (test_m is None) != (test_result is None):
        raise ValueError("test result and metrics must either both be present or both be absent")
    test_evaluated = test_m is not None and test_result is not None
    log_dict: dict[str, Any] = {
        "seed": seed,
        "mvp": mvp,
        "algo": algo,
        "arch": arch,
        # `reward` is the legacy CLI selector (DSR/sweep shaping); the
        # environment objective is recorded separately to avoid ambiguity.
        "reward": reward,
        "environment_reward_mode": environment_reward_mode,
        "equity_log_growth_scale": equity_log_growth_scale,
        "strategy": strategy,
        "strategy_actions": strategy_actions,
        "timesteps": timesteps,
        "train_bars": train_bars,
        "test_bars": test_bars,
        "evaluation_scope": (
            "development_only" if oos_role == "development_only" else "all_configured_splits"
        ),
        "test_evaluation_status": "completed" if test_evaluated else "not_run",
        "test_sharpe": float(test_m.sharpe) if test_m is not None else None,
        "test_max_dd": float(test_m.max_drawdown) if test_m is not None else None,
        "test_trades": test_m.n_trades if test_m is not None else None,
        "test_return": float(test_m.total_return_pct) if test_m is not None else None,
        "test_breaches": (
            strict_nonnegative_int(test_result.get("n_breach_sessions", 0))
            if test_result is not None
            else None
        ),
        "test_n_sessions": int(test_result.get("n_sessions", 0))
        if test_result is not None
        else None,
        "test_days_traded": int(test_result.get("days_traded", 0))
        if test_result is not None
        else None,
        "test_survived_full_year": (
            test_result.get("survived_full_year") is True if test_result is not None else None
        ),
        "test_completed_data_split": (
            test_result.get("completed_data_split") is True if test_result is not None else None
        ),
        "test_episode_end_reason": (
            test_result.get("episode_end_reason") if test_result is not None else None
        ),
        "test_max_trailing_dd": (
            float(test_result.get("max_trailing_dd", test_m.max_drawdown))
            if test_result is not None and test_m is not None
            else None
        ),
        "test_fail_time": (
            str(test_result["fail_time"])
            if test_result is not None and test_result.get("fail_time") is not None
            else None
        ),
        "timestamp": datetime.now().isoformat(),
    }
    log_dict["entry_funnel_by_split"] = entry_funnel_by_split(train_result, test_result)
    if action_space_width is not None:
        log_dict["action_space_width"] = action_space_width
    if observation_account_dim is not None:
        log_dict["observation_account_dim"] = observation_account_dim
    if observation_space_shapes is not None:
        log_dict["observation_space_shapes"] = observation_space_shapes
    if action_schema is not None:
        log_dict["action_schema"] = action_schema
    if observation_schema is not None:
        log_dict["observation_schema"] = observation_schema
    if env_flags is not None:
        log_dict["env_flags"] = env_flags
    log_dict["oos_role"] = oos_role
    return log_dict


def action_space_width(env: Any) -> int | None:
    """Return the action space width for logging.

    Args:
        env: Environment whose state is read or updated.

    Returns:
        Result of return the action space width for logging.
    """
    action_space = getattr(env, "action_space", None)
    if action_space is None:
        return None
    shape = getattr(action_space, "shape", None)
    if shape:
        return int(shape[0])
    if hasattr(action_space, "n"):
        return int(action_space.n)
    return None


def action_schema_manifest(env: Any) -> dict[str, Any] | None:
    """Return declared coordinate names and flags, never infer from width.

    Args:
        env: Environment whose state is read or updated.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    schema = getattr(env, "action_schema", None)
    to_dict = getattr(schema, "to_dict", None)
    if not callable(to_dict):
        return None
    result = to_dict()
    return result if isinstance(result, dict) else None


def observation_schema_manifest(env: Any) -> dict[str, Any] | None:
    """Return explicit account observation coordinate meanings.

    Args:
        env: Environment whose state is read or updated.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    schema = getattr(env, "observation_schema", None)
    to_dict = getattr(schema, "to_dict", None)
    if not callable(to_dict):
        return None
    result = to_dict()
    if not isinstance(result, dict):
        return None
    policy_input_schema = effective_policy_input_schema_manifest(env)
    result["effective_policy_input_schema"] = policy_input_schema
    effective_history_enabled = bool(policy_input_schema["completed_htf_history_enabled"])
    regime_schema = getattr(env, "regime_observation_schema", None)
    if isinstance(regime_schema, dict):
        result["regime_observation"] = regime_schema
    setup_schema = getattr(env, "trade_setup_observation_schema", None)
    if isinstance(setup_schema, dict):
        result["trade_setup_observation"] = {
            **setup_schema,
            "completed_htf_history_enabled": effective_history_enabled,
        }
    candidate_schema = getattr(env, "candidate_geometry_observation_schema", None)
    if isinstance(candidate_schema, dict):
        result["candidate_geometry_observation"] = {
            **candidate_schema,
            "completed_htf_history_enabled": effective_history_enabled,
        }
    return result


def effective_policy_input_schema_manifest(env: Any) -> dict[str, Any]:
    """Describe the effective sequence streams actually exposed to a policy.

    ``sequence_feature_schema`` retains the historical ordered source-column
    record. This schema records which of those columns reach each policy stream.

    Args:
        env: Built environment whose observation streams are read.

    Returns:
        Versioned stream schema for the effective policy input.
    """
    columns = getattr(env, "_obs_columns", None)
    if not isinstance(columns, (list, tuple)):
        raise RuntimeError("training environment does not expose sequence feature columns")
    mtf = bool(getattr(env, "mtf", False))
    history_enabled = mtf and bool(getattr(env, "completed_htf_history_enabled", True))
    return build_effective_policy_input_schema(
        [str(column) for column in columns],
        mtf=mtf,
        trade_setup_actions=bool(getattr(env, "trade_setup_actions", False)),
        completed_htf_history_enabled=history_enabled,
        validity_channels=bool(getattr(env, "feature_validity_channels", False)),
    )


def build_effective_policy_input_schema(
    columns: list[str] | tuple[str, ...],
    *,
    trade_setup_actions: bool,
    completed_htf_history_enabled: bool,
    validity_channels: bool,
    mtf: bool | None = None,
    runtime_arch: str | None = None,
) -> dict[str, Any]:
    """Build a versioned schema of policy-visible sequence streams.

    Args:
        columns: Historical ordered source columns from the sequence schema.
        trade_setup_actions: Whether setup masks make the base sequence M1-only.
        completed_htf_history_enabled: Whether those HTF streams contain history.
        validity_channels: Whether each stream appends finite-value indicators.
        mtf: Whether the runtime emits higher-timeframe observation streams.
        runtime_arch: Runtime architecture used to resolve MTF when ``mtf`` is omitted.

    Returns:
        Versioned policy input schema with effective stream keys and columns.
    """
    if mtf is None:
        if runtime_arch is None:
            raise ValueError("mtf or runtime_arch is required for the policy input schema")
        mtf, _ = mtf_settings({}, runtime_arch)
    higher_timeframe_prefixes = tuple(prefix for _, prefix, _ in HTF_BRANCHES)
    m1_only_sequence = mtf or trade_setup_actions
    base_columns = [
        column
        for column in columns
        if not m1_only_sequence or not str(column).startswith(higher_timeframe_prefixes)
    ]
    streams: list[dict[str, Any]] = [
        {
            "timeframe": "M1",
            "sequence_key": "seq",
            "mask_key": "seq_mask",
            "columns": base_columns,
            "history_available": True,
        }
    ]
    if mtf:
        for key, prefix, sequence_key in HTF_BRANCHES:
            streams.append(
                {
                    "timeframe": key.upper(),
                    "sequence_key": sequence_key,
                    "mask_key": f"mask_{key}",
                    "columns": [column for column in columns if str(column).startswith(prefix)],
                    "history_available": bool(completed_htf_history_enabled),
                }
            )
    return {
        "version": POLICY_INPUT_SCHEMA_VERSION,
        "mtf_enabled": bool(mtf),
        "trade_setup_actions": bool(trade_setup_actions),
        "m1_only_sequence": bool(m1_only_sequence),
        "completed_htf_history_enabled": bool(mtf and completed_htf_history_enabled),
        "validity_channels": bool(validity_channels),
        "streams": streams,
    }


def sequence_feature_schema_manifest(env: Any) -> dict[str, Any]:
    """Return the ordered source-column record retained for sequence compatibility.

    This historical schema hashes the environment's full selected source-column
    list. ``effective_policy_input_schema_manifest`` records the M1/HTF streams
    and the columns each policy actually receives.

    Args:
        env: Environment whose state is read or updated.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    columns = getattr(env, "_obs_columns", None)
    if not isinstance(columns, (list, tuple)):
        raise RuntimeError("training environment does not expose sequence feature columns")
    return build_sequence_feature_schema(
        [str(column) for column in columns],
        include_validity_channels=bool(getattr(env, "feature_validity_channels", False)),
    )


def training_protocol_manifest(
    *, model: Any, cfg: Any, args: Any, seed: int, requested_steps: int, algo: str = "ppo"
) -> dict[str, Any]:
    """Persist the effective optimizer/reward/risk protocol for later reproduction.

    Args:
        model: Model used for this operation.
        cfg: Run configuration used by this operation.
        args: Parsed command-line arguments for this operation.
        seed: Random seed used to make sampling reproducible.
        requested_steps: Number specifying the requested steps for this operation.
        algo: Text or path value identifying the algo.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    n_envs = int(model.n_envs)
    if algo == "ppo":
        n_steps = int(model.n_steps)
        batch_size = int(cfg.ppo.batch_size)
        minibatches = (n_envs * n_steps + batch_size - 1) // batch_size
        optimizer_protocol = {
            "ppo": {
                "requested_n_envs": cfg.get("quality_execution", {}).get(
                    "requested_n_envs", n_envs
                ),
                "effective_n_envs": cfg.get("quality_execution", {}).get(
                    "effective_n_envs", n_envs
                ),
                "exact_n_envs_required": bool(
                    cfg.get("quality_execution", {}).get("exact_n_envs", False)
                ),
                "logical_n_envs": n_envs,
                "n_steps_per_env": n_steps,
                "aggregate_rollout_steps": int(n_envs * n_steps),
                "batch_size": batch_size,
                "epochs": int(cfg.ppo.n_epochs),
                "minibatches_per_epoch": minibatches,
                "updates_per_rollout": int(minibatches * int(cfg.ppo.n_epochs)),
                "learning_rate": float(cfg.ppo.learning_rate),
                "gamma": float(cfg.ppo.gamma),
                "gae_lambda": float(cfg.ppo.gae_lambda),
                "clip_range": float(cfg.ppo.clip_range),
                "entropy_coefficient": float(model.ent_coef),
                "actor_architecture": str(cfg.ppo.get("actor_arch", "shared")),
            }
        }
    elif algo == "sac":
        optimizer_protocol = {
            "sac": {
                "logical_n_envs": n_envs,
                "learning_rate": float(cfg.sac.learning_rate),
                "buffer_size": int(cfg.sac.buffer_size),
                "batch_size": int(cfg.sac.batch_size),
                "tau": float(cfg.sac.tau),
                "gamma": float(cfg.sac.gamma),
                "train_freq": cfg.sac.train_freq,
                "gradient_steps": int(cfg.sac.gradient_steps),
                "learning_starts": int(cfg.sac.learning_starts),
                "entropy_coefficient": str(cfg.sac.ent_coef),
            }
        }
    else:
        raise ValueError(f"unsupported training algorithm for protocol manifest: {algo}")
    quality_variant = str(cfg.get("quality_variant_id", ""))
    quality_lineage = None
    if quality_variant:
        from training.configuration.quality import quality_variant_metadata

        quality_lineage = quality_variant_metadata(quality_variant)
    ftmo = OmegaConf.to_container(cfg.get("ftmo", {}), resolve=True)
    return {
        "quality_variant": quality_lineage,
        "constrained_rl": {
            "enabled": bool(cfg.get("constrained_rl", {}).get("enabled", False)),
            "method": f"primal_dual_scalarized_return_{algo}",
            "cost": "max_per_step_increase_normalized_to_max_loss_limit",
            "cost_unit": "fraction_of_max_loss_limit",
            "episode_cost_budget": float(
                cfg.get("constrained_rl", {}).get("episode_cost_budget", 1.0)
            ),
            "dual_learning_rate": float(
                cfg.get("constrained_rl", {}).get("dual_learning_rate", 0.1)
            ),
            "lambda_initial": float(cfg.get("constrained_rl", {}).get("lambda_initial", 0.0)),
            "lambda_max": float(cfg.get("constrained_rl", {}).get("lambda_max", 100.0)),
            "cost_discount_gamma": float(
                cfg.get("constrained_rl", {}).get("cost_discount_gamma", 1.0)
            ),
        },
        "seed": int(seed),
        "algorithm": algo,
        "worker_seeds": [int(seed + index) for index in range(n_envs)],
        "requested_steps": int(requested_steps),
        "completed_steps": int(model.num_timesteps),
        "data_source": str(cfg.env.get("data_source", "frames")),
        "walk_forward": {
            "enabled": bool(getattr(args, "walk_forward", False)),
            "folds": int(getattr(args, "wf_splits", 0)),
            "purge_bars": int(getattr(args, "purge_bars", 0)),
            "embargo_bars": int(getattr(args, "embargo_bars", 0)),
        },
        "mvp_mode": bool(getattr(args, "mvp", False)),
        "locked_oos_selection_allowed": bool(
            getattr(args, "allow_locked_oos_for_selection", False)
        ),
        "observation_schema_version": str(
            cfg.env.get("observation_schema_version", "account-state-v1")
        ),
        "observation_age_scale_bars": float(cfg.env.get("observation_age_scale_bars", 60.0)),
        "action_distribution": str(
            cfg.ppo.get("policy_distribution", "clamped_diagonal_gaussian")
            if algo == "ppo"
            else "squashed_diagonal_gaussian"
        ),
        "reward": {
            "mode": str(cfg.env.get("reward_mode", "dsr")),
            "selector": str(getattr(args, "reward", "dsr")),
            "dsr_eta": float(cfg.env.get("reward_dsr_eta", 0.01)),
            "fixed_risk_usd": float(cfg.env.get("fixed_risk_usd", 0.0)),
            "equity_log_growth_scale": float(cfg.env.get("equity_log_growth_scale", 100.0)),
        },
        "risk": {
            "mode": str(cfg.env.get("risk_mode", "dynamic")),
            "ftmo": ftmo,
            "eod_peak_trailing_dd_limit_usd": float(
                cfg.env.get("eod_risk", {}).get("peak_trailing_dd_limit_usd", 0.0)
            ),
            "risk_per_trade_limit": float(cfg.get("ftmo", {}).get("risk_per_trade_limit", 1000.0)),
            "risk_band_max_usd": float(cfg.env.get("risk_band_max_usd", 0.0)),
            "risk_band_hold_below_usd": float(cfg.env.get("risk_band_hold_below_usd", 0.0)),
            "risk_band_budget_includes_execution_reserve": (
                str(cfg.env.get("risk_mode", "dynamic")) == "dollar_band"
            ),
        },
        **optimizer_protocol,
        "environment": {
            "vector_backend": str(cfg.env.get("vector_backend", "subproc")),
            "strategy_actions": bool(cfg.env.get("strategy_actions", False)),
            "entry_state_machine": bool(cfg.env.get("entry_state_machine", False)),
            "entry_state_observation": bool(cfg.env.get("entry_state_observation", True)),
        },
    }


def observation_account_dim(env: Any) -> int:
    """Return the account observation dimension from the env's observation space.

    Args:
        env: Environment whose state is read or updated.

    Returns:
        Numeric result returned by ``observation_account_dim``.
    """
    obs_space = getattr(env, "observation_space", None)
    if obs_space is None:
        return 0
    account_space = getattr(obs_space, "spaces", {}).get("account")
    if account_space is None:
        return 0
    return int(account_space.shape[0])


def observation_space_shapes(env: Any) -> dict[str, list[int]]:
    """Return every observation branch shape for the run manifest.

    Args:
        env: Environment whose state is read or updated.

    Returns:
        Mapping from ``str`` keys to ``list[int]`` values.
    """
    obs_space = getattr(env, "observation_space", None)
    spaces_by_key = getattr(obs_space, "spaces", {})
    return {
        str(key): [int(size) for size in space.shape]
        for key, space in spaces_by_key.items()
        if hasattr(space, "shape")
    }
