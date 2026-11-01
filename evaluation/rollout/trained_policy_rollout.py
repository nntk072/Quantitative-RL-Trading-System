"""Roll a trained PPO/SAC model through :class:`TradingEnv` to produce trades.

``simulation.backtest.run_backtest`` drives a rule-based ``policy``
callable (plain ``np.ndarray`` in, ``int`` action out in ``{-1, 0, 1, exit}``)
through a lightweight event loop. The RL model, however, was trained against
``TradingEnv``'s own **Dict** observation (``{"seq": ..., "account": ...}``)
and **Discrete(20)** action space (which additionally encodes risk_frac/
rr_ratio variants for entries) or **Box(-1, 1)** for continuous actions —
those formats don't match ``run_backtest``'s interface at all.

Rather than reverse-engineer an adapter, this module evaluates the model by
walking it through the *exact* environment class/action space it was trained
on, using ``TradingEnv(..., episodic=False)`` so a guardrail breach blocks
new trading for the rest of that session instead of ending the whole
rollout early (see the ``episodic`` parameter docstring on ``TradingEnv``).

The returned dict mirrors ``run_backtest``'s return shape so it can be
passed straight into ``evaluation.calculate_metrics`` and
``evaluation.reporting.run_artifact_writer.save_run`` unchanged.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, cast

import numpy as np
import pandas as pd

from evaluation.metrics import max_drawdown
from evaluation.metrics.reward_attribution import RewardAttribution
from simulation.environment.env import TradingEnv
from trading.execution import COST_US100, CostModel

BAR_CLOSE_EXPOSURE_MEASURE = "fraction_of_evaluation_steps_with_position_at_bar_close"
CONSTRAINT_COST_SCHEMA = "q5_discounted_constraint_cost_v1"
Q5_MAX_LOSS_FRACTION_COST_SCHEMA = "q5_max_loss_fraction_cost_v1"


def _finite_constraint_cost(constraints: dict[str, Any], key: str) -> float:
    """Process constraint cost.

    Args:
        constraints: Key-value data used for the constraints.
        key: Text or path value identifying the key.

    Returns:
        Numeric result returned by ``_finite_constraint_cost``.
    """
    value = constraints.get(key, 0.0)
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise ValueError(f"evaluation constraint cost {key!r} must be numeric")
    numeric = float(value)
    if not np.isfinite(numeric):
        raise ValueError(f"evaluation constraint cost {key!r} must be finite")
    return max(0.0, numeric)


def make_action_fn(
    model: Any,
    continuous_actions: bool = False,
    deterministic: bool = True,
    strategy_actions: bool = False,
) -> Any:
    """Return an observation → action callable with explicit action typing.

    PPO trains on ``TradingEnv``'s discrete action space, so the policy's
    integer action id is passed through unchanged; SAC trains on the
    continuous Box space and yields a float position-sizing fraction.
    When ``strategy_actions`` is set (Idea 1 PO3 Box(4)), the full float32
    vector is returned so eval matches training.

    A backend-neutral DecisionProvider follows the same rollout path after its
    semantic output is validated and adapted to the environment action shape.

    This is the single shared implementation — ``scripts/train_rl.py`` and
    ``scripts/compare_encoders.py`` used to each carry private copies.

    Args:
        model: Model used for this operation.
        continuous_actions: Whether to enable or require the continuous actions.
        deterministic: Whether to enable or require the deterministic.
        strategy_actions: Whether to enable or require the strategy actions.

    Returns:
        Result of return an observation → action callable with explicit action typing.
    """
    if hasattr(model, "metadata") and hasattr(model, "predict"):
        from evaluation.rollout.provider import make_provider_action_fn

        return make_provider_action_fn(
            model,
            input_schema_version=model.metadata.input_schema_version,
            deterministic=deterministic,
            continuous_actions=continuous_actions,
            strategy_actions=strategy_actions,
        )

    def action_fn(obs: dict[str, Any]) -> Any:
        """Predict one rollout action and adapt it to the configured action shape.

        Args:
            obs: Key-value data used for the obs.

        Returns:
            Result of predict one rollout action and adapt it to the configured action shape.
        """
        action = model.predict(obs, deterministic=deterministic)[0]
        arr = np.asarray(action, dtype=np.float32).reshape(-1)
        if strategy_actions:
            return arr.astype(np.float32, copy=False)
        scalar = arr[0]
        return float(scalar) if continuous_actions else int(scalar)

    return action_fn


def evaluate_model(
    model: Any,
    bars: pd.DataFrame,
    features: pd.DataFrame,
    obs_window: int = 60,
    initial_balance: float = 100_000.0,
    cost_model: CostModel = COST_US100,
    broker_kwargs: dict[str, Any] | None = None,
    guardrail_kwargs: dict[str, Any] | None = None,
    risk_frac_range: tuple[float, float] = (0.005, 0.02),
    rr_ratio_range: tuple[float, float] = (1.0, 3.0),
    swing_buffer_pts: float = 1.0,
    min_lot: float = 0.01,
    max_lot: float = 100.0,
    contract_size: float = 1.0,
    max_loss_per_trade_usd: float = 100.0,
    dsr_eta: float = 0.01,
    deterministic: bool = True,
    max_episode_steps: int | None = None,
    continuous_actions: bool = False,
    use_sweep_reward: bool = False,
    sweep_alpha: float = 0.1,
    sweep_beta: float = 0.01,
    sweep_hold_bars: int = 3,
    dsr_weight: float = 0.3,
    sweep_weight: float = 0.7,
    block_overnight: bool = True,
    eod_risk: dict[str, Any] | None = None,
    use_vae: bool = False,
    vae: Any | None = None,
    strategy: Any = None,
    strategy_actions: bool = False,
    trade_setup_actions: bool = False,
    entry_state_machine: bool = False,
    candidate_max_age_bars: int = 5,
    arm_requires_retest: bool = False,
    entry_state_observation: bool = True,
    observation_schema_version: str = "account-state-v1",
    observation_age_scale_bars: float = 60.0,
    strict_research_eligibility: bool = False,
    strategy_reward: Any = None,
    strategy_weight: float = 0.0,
    sl_buffer_pts: float = 0.0,
    pre_ny_by_date: dict[Any, Any] | None = None,
    min_sl_atr_mult: float = 0.5,
    min_sl_points: float = 0.0,
    max_entries_per_session: int = 0,
    open_manipulation_bars: int = 10,
    entry_cooldown_bars: int = 0,
    reward_mode: str = "dsr",
    equity_log_growth_scale: float = 100.0,
    fixed_risk_usd: float = 0.0,
    risk_band_max_usd: float = 0.0,
    risk_band_hold_below_usd: float = 0.0,
    risk_mode: str = "dynamic",
    allow_ema_exit: bool = True,
    ema_runner_fraction: float = 0.0,
    entry_intensity_threshold: float = 0.0,
    peak_trailing_dd_limit: float = 0.0,
    tickbook: Any | None = None,
    tick_execution_required: bool = False,
    fill_delay_ms: int = 0,
    randomized_fill_latency_ms: float = 0.0,
    max_tick_quote_wait_ms: int = 60_000,
    tick_fill_slippage_points: float = 0.0,
    execution_seed: int | None = None,
    agent_direction_control: bool = False,
    direction_override_threshold: float = 0.0,
    sl_mode: str = "fixed",
    tp_mode: str = "fixed",
    tp_reference: str = "structural",
    allow_agent_sl_mode: bool = True,
    sl_mode_defer_threshold: float = 0.1,
    allow_agent_tp_mode: bool = False,
    tp_mode_defer_threshold: float = 0.1,
    allow_multi_tp: bool = False,
    allow_simplex: bool = True,
    tp_breakeven_alpha: float = 0.5,
    risk_floor: float = 0.0005,
    mtf: bool = False,
    mtf_windows: dict[str, int] | None = None,
    regime_observation: bool = False,
    target_timeframes: tuple[str, ...] = ("M5", "M15", "H1"),
    scheduled_session_closes: dict[str, str] | None = None,
    session_start: str = "16:30",
    env: TradingEnv | None = None,
    legacy_sequence_columns: bool = False,
    trading_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Walk a trained RL ``model`` over *bars*/*features* and collect trades.

    Parameters mirror ``TradingEnv.__init__`` exactly. ``risk_frac_range`` and
    ``rr_ratio_range`` change what the model's discrete entry actions *mean*
    (they define the 3x3 grid of risk/reward variants), so callers **must**
    pass the same ranges used to build the training environment or the
    model's learned action semantics will not line up.

    ``legacy_sequence_columns`` is reserved for explicit historical checkpoint
    replay when the source manifest lacks ordered feature coordinates. It must
    not be used to train a new policy.

    Args:
        model: Model used for this operation.
        bars: Market bars to process.
        features: Feature values supplied to the operation.
        obs_window: Numeric value used for the obs window.
        initial_balance: Numeric value used for the initial balance.
        cost_model: Cost model used by the operation described above.
        broker_kwargs: Key-value data used for the broker kwargs.
        guardrail_kwargs: Key-value data used for the guardrail kwargs.
        risk_frac_range: Items supplied for the risk frac range, in input order.
        rr_ratio_range: Items supplied for the rr ratio range, in input order.
        swing_buffer_pts: Numeric value used for the swing buffer pts.
        min_lot: Numeric value used for the min lot.
        max_lot: Numeric value used for the max lot.
        contract_size: Number specifying the contract size for this operation.
        max_loss_per_trade_usd: Numeric value used for the max loss per trade usd.
        dsr_eta: Numeric value used for the dsr eta.
        deterministic: Whether to enable or require the deterministic.
        max_episode_steps: Number specifying the max episode steps for this operation.
        continuous_actions: Whether to enable or require the continuous actions.
        use_sweep_reward: Whether to enable or require the use sweep reward.
        sweep_alpha: Numeric value used for the sweep alpha.
        sweep_beta: Numeric value used for the sweep beta.
        sweep_hold_bars: Market bar or price data used for walk a trained RL ``model`` over *bars*/*features* and collect trades.
        dsr_weight: Numeric value used for the dsr weight.
        sweep_weight: Numeric value used for the sweep weight.
        block_overnight: Whether to enable or require the block overnight.
        eod_risk: Key-value data used for the eod risk.
        use_vae: Whether to enable or require the use vae.
        vae: Vae used by the operation described above.
        strategy: Strategy used to select or evaluate trades.
        strategy_actions: Whether to enable or require the strategy actions.
        trade_setup_actions: Whether to enable or require the trade setup actions.
        entry_state_machine: Whether to enable or require the entry state machine.
        candidate_max_age_bars: Market bar or price data used for walk a trained RL ``model`` over *bars*/*features* and collect trades.
        arm_requires_retest: Whether to enable or require the arm requires retest.
        entry_state_observation: Whether to enable or require the entry state observation.
        observation_schema_version: Text or path value identifying the observation schema version.
        observation_age_scale_bars: Market bar or price data used for walk a trained RL ``model`` over *bars*/*features* and collect trades.
        strict_research_eligibility: Whether to enable or require the strict research eligibility.
        strategy_reward: Strategy reward used by the operation described above.
        strategy_weight: Numeric value used for the strategy weight.
        sl_buffer_pts: Numeric value used for the sl buffer pts.
        pre_ny_by_date: Key-value data used for the pre ny by date.
        min_sl_atr_mult: Numeric value used for the min sl atr mult.
        min_sl_points: Numeric value used for the min sl points.
        max_entries_per_session: Numeric value used for the max entries per session.
        open_manipulation_bars: Market bar or price data used for walk a trained RL ``model`` over *bars*/*features* and collect trades.
        entry_cooldown_bars: Market bar or price data used for walk a trained RL ``model`` over *bars*/*features* and collect trades.
        reward_mode: Text or path value identifying the reward mode.
        equity_log_growth_scale: Numeric value used for the equity log growth scale.
        fixed_risk_usd: Numeric value used for the fixed risk usd.
        risk_band_max_usd: Numeric value used for the risk band max usd.
        risk_band_hold_below_usd: Numeric value used for the risk band hold below usd.
        risk_mode: Text or path value identifying the risk mode.
        allow_ema_exit: Whether to enable or require the allow ema exit.
        ema_runner_fraction: Numeric value used for the ema runner fraction.
        entry_intensity_threshold: Numeric value used for the entry intensity threshold.
        peak_trailing_dd_limit: Numeric value used for the peak trailing dd limit.
        tickbook: Tickbook used by the operation described above.
        tick_execution_required: Whether to enable or require the tick execution required.
        fill_delay_ms: Numeric value used for the fill delay ms.
        randomized_fill_latency_ms: Numeric value used for the randomized fill latency ms.
        max_tick_quote_wait_ms: Numeric value used for the max tick quote wait ms.
        tick_fill_slippage_points: Numeric value used for the tick fill slippage points.
        execution_seed: Execution seed used by the operation described above.
        agent_direction_control: Whether to enable or require the agent direction control.
        direction_override_threshold: Numeric value used for the direction override threshold.
        sl_mode: Text or path value identifying the sl mode.
        tp_mode: Text or path value identifying the tp mode.
        tp_reference: Text or path value identifying the tp reference.
        allow_agent_sl_mode: Whether to enable or require the allow agent sl mode.
        sl_mode_defer_threshold: Numeric value used for the sl mode defer threshold.
        allow_agent_tp_mode: Whether to enable or require the allow agent tp mode.
        tp_mode_defer_threshold: Numeric value used for the tp mode defer threshold.
        allow_multi_tp: Whether to enable or require the allow multi tp.
        allow_simplex: Whether to enable or require the allow simplex.
        tp_breakeven_alpha: Numeric value used for the tp breakeven alpha.
        risk_floor: Numeric value used for the risk floor.
        mtf: Whether to enable or require the mtf.
        mtf_windows: Key-value data used for the mtf windows.
        regime_observation: Whether to enable or require the regime observation.
        target_timeframes: Items supplied for the target timeframes, in input order.
        scheduled_session_closes: Key-value data used for the scheduled session closes.
        session_start: Text or path value identifying the session start.
        env: Environment whose state is read or updated.
        legacy_sequence_columns: Whether to enable or require the legacy sequence columns.
        trading_policy: Key-value data used for the trading policy.

    Returns:
        dict with keys ``equity``, ``trades``, ``account``, ``breaches``,:
        ``breach_events``, ``n_sessions``, ``n_breach_sessions``,:
        ``n_sessions_with_trades``, ``n_sessions_skipped`` — the same shape:
        produced by ``simulation.backtest.run_backtest``.:
    """
    if (
        env is not None
        and legacy_sequence_columns
        and not bool(getattr(env, "_legacy_sequence_columns", False))
    ):
        raise ValueError(
            "supplied evaluation environment does not use the requested legacy sequence columns"
        )
    if execution_seed is not None and execution_seed < 0:
        raise ValueError("execution_seed must be non-negative")
    effective_latency_ms = randomized_fill_latency_ms
    if env is not None:
        effective_latency_ms = float(
            getattr(env, "randomized_fill_latency_ms", randomized_fill_latency_ms)
        )
    if effective_latency_ms > 0 and execution_seed is None:
        raise ValueError("execution_seed is required for randomized tick-fill evaluation")
    if env is None:
        env = TradingEnv(
            bars=bars,
            features=features,
            obs_window=obs_window,
            initial_balance=initial_balance,
            cost_model=cost_model,
            broker_kwargs=broker_kwargs,
            guardrail_kwargs=guardrail_kwargs,
            risk_frac_range=risk_frac_range,
            rr_ratio_range=rr_ratio_range,
            swing_buffer_pts=swing_buffer_pts,
            min_lot=min_lot,
            max_lot=max_lot,
            contract_size=contract_size,
            max_loss_per_trade_usd=max_loss_per_trade_usd,
            dsr_eta=dsr_eta,
            episodic=False,
            max_episode_steps=max_episode_steps,
            continuous_actions=continuous_actions,
            use_sweep_reward=use_sweep_reward,
            sweep_alpha=sweep_alpha,
            sweep_beta=sweep_beta,
            sweep_hold_bars=sweep_hold_bars,
            dsr_weight=dsr_weight,
            sweep_weight=sweep_weight,
            block_overnight=block_overnight,
            eod_risk=eod_risk,
            use_vae=use_vae,
            vae=vae,
            strategy=strategy,
            strategy_actions=strategy_actions,
            trade_setup_actions=trade_setup_actions,
            entry_state_machine=entry_state_machine,
            candidate_max_age_bars=candidate_max_age_bars,
            arm_requires_retest=arm_requires_retest,
            entry_state_observation=entry_state_observation,
            observation_schema_version=observation_schema_version,
            observation_age_scale_bars=observation_age_scale_bars,
            legacy_sequence_columns=legacy_sequence_columns,
            strict_research_eligibility=strict_research_eligibility,
            strategy_reward=strategy_reward,
            strategy_weight=strategy_weight,
            sl_buffer_pts=sl_buffer_pts,
            pre_ny_by_date=pre_ny_by_date,
            min_sl_atr_mult=min_sl_atr_mult,
            min_sl_points=min_sl_points,
            max_entries_per_session=max_entries_per_session,
            open_manipulation_bars=open_manipulation_bars,
            entry_cooldown_bars=entry_cooldown_bars,
            reward_mode=reward_mode,
            equity_log_growth_scale=equity_log_growth_scale,
            fixed_risk_usd=fixed_risk_usd,
            risk_band_max_usd=risk_band_max_usd,
            risk_band_hold_below_usd=risk_band_hold_below_usd,
            risk_mode=risk_mode,
            allow_ema_exit=allow_ema_exit,
            ema_runner_fraction=ema_runner_fraction,
            entry_intensity_threshold=entry_intensity_threshold,
            peak_trailing_dd_limit=peak_trailing_dd_limit,
            tickbook=tickbook,
            tick_execution_required=tick_execution_required,
            fill_delay_ms=fill_delay_ms,
            randomized_fill_latency_ms=randomized_fill_latency_ms,
            max_tick_quote_wait_ms=max_tick_quote_wait_ms,
            tick_fill_slippage_points=tick_fill_slippage_points,
            agent_direction_control=agent_direction_control,
            direction_override_threshold=direction_override_threshold,
            sl_mode=sl_mode,
            tp_mode=tp_mode,
            tp_reference=tp_reference,
            allow_agent_sl_mode=allow_agent_sl_mode,
            sl_mode_defer_threshold=sl_mode_defer_threshold,
            allow_agent_tp_mode=allow_agent_tp_mode,
            tp_mode_defer_threshold=tp_mode_defer_threshold,
            allow_multi_tp=allow_multi_tp,
            allow_simplex=allow_simplex,
            tp_breakeven_alpha=tp_breakeven_alpha,
            risk_floor=risk_floor,
            mtf=mtf,
            mtf_windows=mtf_windows,
            regime_observation=regime_observation,
            target_timeframes=target_timeframes,
            scheduled_session_closes=scheduled_session_closes,
            session_start=session_start,
            trading_policy=trading_policy,
        )

    if execution_seed is None:
        obs, _ = env.reset()
    else:
        obs, _ = env.reset(seed=execution_seed)
    done = False
    truncated = False
    action_fn = make_action_fn(
        model, continuous_actions, deterministic, strategy_actions=strategy_actions
    )
    action_counts: Counter[str] = Counter()
    trade_setup_decision_rows: list[dict[str, Any]] = []
    reward_sum = 0.0
    reward_attribution = RewardAttribution()
    n_steps = 0
    exposure_bars = 0
    final_info: dict[str, Any] = {}
    constrained_state = getattr(model, "_constrained_rl_state", None)
    constraint_rows: list[dict[str, Any]] = []
    constraint_discount_gamma: float | None = None
    q5_cost_v3_limits: tuple[float, float, float] | None = None
    if constrained_state is not None:
        if not isinstance(constrained_state, dict) or constrained_state.get("version") not in {
            2,
            3,
        }:
            raise ValueError("Q5 evaluation requires a supported constrained-RL checkpoint state")
        state_version = int(constrained_state["version"])
        gamma_key = "gamma" if state_version == 2 else "cost_discount_gamma"
        gamma_value = constrained_state.get(gamma_key)
        if (
            isinstance(gamma_value, bool)
            or not isinstance(gamma_value, (int, float))
            or not np.isfinite(float(gamma_value))
            or not 0.0 < float(gamma_value) <= 1.0
        ):
            raise ValueError(f"Q5 checkpoint {gamma_key} must be finite and in (0, 1]")
        constraint_discount_gamma = float(gamma_value)
        if state_version == 3:
            raw_daily_limit = constrained_state.get("daily_loss_limit_usd")
            raw_max_loss_limit = constrained_state.get("max_loss_limit_usd")
            raw_trailing_limit = constrained_state.get("trailing_dd_limit_usd")
            for value in (raw_daily_limit, raw_max_loss_limit, raw_trailing_limit):
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not np.isfinite(float(value))
                ):
                    raise ValueError("Q5 checkpoint loss-limit metadata is missing or invalid")
            daily_limit = float(cast(float, raw_daily_limit))
            max_loss_limit = float(cast(float, raw_max_loss_limit))
            trailing_limit = float(cast(float, raw_trailing_limit))
            if daily_limit < 0.0 or max_loss_limit <= 0.0 or trailing_limit < 0.0:
                raise ValueError("Q5 checkpoint loss-limit metadata is outside valid bounds")
            q5_cost_v3_limits = (daily_limit, max_loss_limit, trailing_limit)
    discount_factor = 1.0
    while not (done or truncated):
        action = action_fn(obs)
        trade_setup_record: dict[str, Any] | None = None
        policy = getattr(model, "policy", None)
        coordinates = tuple(getattr(policy, "hybrid_action_coordinates", ()))
        setup_coordinate = "trade_setup" if "trade_setup" in coordinates else None
        if strategy_actions and setup_coordinate is not None and isinstance(obs, dict):
            from decisioning.trade_setup import TRADE_SETUP_CANDIDATES, trade_setup_id_from_box

            values = np.asarray(action, dtype=np.float32).reshape(-1)
            setup_index = coordinates.index(setup_coordinate)
            selected_id = trade_setup_id_from_box(float(values[setup_index]))
            mask = np.asarray(obs.get("trade_setup_mask", []), dtype=np.float32).reshape(-1)
            is_valid = selected_id < len(mask) and bool(mask[selected_id] > 0.0)
            candidate = TRADE_SETUP_CANDIDATES[selected_id]
            raw_entropy = getattr(policy, "last_trade_setup_entropy", None)
            entropy_value = (
                float(np.asarray(raw_entropy.detach().cpu()).reshape(-1)[0])
                if raw_entropy is not None
                else float("nan")
            )
            trade_setup_record = {
                "step": n_steps + 1,
                "trade_setup_candidate_id": selected_id,
                "idea": candidate.idea or "",
                "setup_timeframe": candidate.setup_timeframe or "",
                "direction": int(candidate.direction),
                "is_no_trade": bool(candidate.is_no_trade),
                "selection_valid": is_valid,
                "eligible_trade_setup_count": int(np.count_nonzero(mask)),
                "eligible_trade_setup_ids": np.flatnonzero(mask).astype(int).tolist(),
                "trade_setup_entropy_nats": entropy_value,
            }
            trade_setup_record.update(
                {
                    f"action_{name}": float(values[index])
                    for index, name in enumerate(coordinates)
                    if name != setup_coordinate
                }
            )
        if strategy_actions:
            action_key = str(tuple(np.round(np.asarray(action).reshape(-1), 4)))
        else:
            action_key = str(action)
        action_counts[action_key] += 1
        obs, reward, done, truncated, info = env.step(action)
        if trade_setup_record is not None:
            trade_setup_record["time"] = str(env.equity_times[-1]) if env.equity_times else ""
            trade_setup_decision_rows.append(trade_setup_record)
        final_info = info
        reward_sum += float(reward)
        reward_attribution.add(float(reward), info.get("reward_parts"))
        n_steps += 1
        if constraint_discount_gamma is not None:
            raw_constraints = info.get("constraints", {})
            if not isinstance(raw_constraints, dict):
                raise ValueError("Q5 evaluation step is missing its constraint-cost record")
            component_costs = {
                "daily_cost": _finite_constraint_cost(raw_constraints, "daily_cost"),
                "max_loss_cost": _finite_constraint_cost(raw_constraints, "max_loss_cost"),
                "trailing_cost": _finite_constraint_cost(raw_constraints, "trailing_cost"),
            }
            if q5_cost_v3_limits is not None:
                daily_limit, max_loss_limit, trailing_limit = q5_cost_v3_limits
                component_costs = {
                    "daily_cost": component_costs["daily_cost"] * daily_limit / max_loss_limit,
                    "max_loss_cost": component_costs["max_loss_cost"],
                    "trailing_cost": (
                        component_costs["trailing_cost"] * trailing_limit / max_loss_limit
                        if trailing_limit > 0.0
                        else 0.0
                    ),
                }
            breach_indicator = float(
                any(
                    bool(raw_constraints.get(key, False))
                    for key in ("daily_breach", "max_loss_breach", "trailing_breach")
                )
            )
            step_cost = max(*component_costs.values(), breach_indicator)
            constraint_rows.append(
                {
                    "step": n_steps,
                    "time": pd.Timestamp(env.equity_times[-1]).isoformat(),
                    "discount_factor": discount_factor,
                    **component_costs,
                    "breach_indicator": breach_indicator,
                    "step_cost": step_cost,
                    "discounted_step_cost": discount_factor * step_cost,
                }
            )
            discount_factor *= constraint_discount_gamma
            # Measure exposure at the decision-bar close. This avoids treating
            # overnight/weekend gaps as market exposure and is reproducible from
            # the environment's per-step position state.
        exposure_bars += int(bool(info.get("position", False)))

    equity_series = pd.Series(
        env.equity_curve,
        index=pd.DatetimeIndex(env.equity_times),
    )
    trades_df = pd.DataFrame(env.trade_log)
    trade_setup_decisions = pd.DataFrame.from_records(trade_setup_decision_rows)
    trade_setup_metrics: dict[str, Any] | None = None
    if trade_setup_decision_rows:
        from evaluation.metrics.trade_setup_policy import summarize_trade_setup_decisions

        trade_setup_metrics = summarize_trade_setup_decisions(trade_setup_decisions, trades_df)
        policy_class = type(getattr(model, "policy", None)).__name__
        trade_setup_metrics["policy_class"] = policy_class
        trade_setup_metrics["setup_conditioned_execution_active"] = (
            policy_class == "TradeSetupConditionedClampedStdMultiInputPolicy"
        )

    n_sessions = len(env.all_sessions)
    days_traded = len(env.sessions_with_trades)
    breach_events = list(env.breach_events)
    # In chronological account mode a daily-loss limit blocks only that
    # session, and evaluation resumes next session. Episodic and repeated-
    # payout modes terminate on that same event, so it remains a failure there.
    daily_loss_is_session_scoped = not bool(getattr(env, "episodic", False)) and not bool(
        getattr(env, "repeated_payout_policy", False)
    )
    hard_breach_events = [
        event
        for event in breach_events
        if event.get("reason") != "daily_loss" or not daily_loss_is_session_scoped
    ]
    fail_time = hard_breach_events[0]["time"] if hard_breach_events else None
    episode_equity = final_info.get("episode_equity", {})
    completed_data_split = bool(episode_equity.get("completed_data_split", False))
    episode_end_reason = episode_equity.get("episode_end_reason")
    survived_full_year = not hard_breach_events and completed_data_split

    constraint_cost_summary = None
    constraint_cost_frame = None
    if constraint_discount_gamma is not None:
        constraint_cost_frame = pd.DataFrame.from_records(constraint_rows)
        component_summary = {
            key: {
                "undiscounted_total": float(constraint_cost_frame[key].sum()),
                "discounted_total": float(
                    (constraint_cost_frame[key] * constraint_cost_frame["discount_factor"]).sum()
                ),
            }
            for key in ("daily_cost", "max_loss_cost", "trailing_cost")
        }
        constraint_cost_summary = {
            "schema": (
                Q5_MAX_LOSS_FRACTION_COST_SCHEMA
                if q5_cost_v3_limits is not None
                else CONSTRAINT_COST_SCHEMA
            ),
            "cost_unit": (
                "fraction_of_max_loss_limit"
                if q5_cost_v3_limits is not None
                else "max_of_original_normalized_constraint_units"
            ),
            "definition": (
                "per_step_max_limit_increase_normalized_to_max_loss_limit_and_breach_indicator"
                if q5_cost_v3_limits is not None
                else "per_step_max_of_normalized_daily_max_loss_trailing_costs_and_breach_indicator"
            ),
            "discount_gamma": constraint_discount_gamma,
            "n_steps": len(constraint_cost_frame),
            "undiscounted_total": float(constraint_cost_frame["step_cost"].sum()),
            "discounted_total": float(constraint_cost_frame["discounted_step_cost"].sum()),
            "components": component_summary,
        }

    return {
        "equity": equity_series,
        "trades": trades_df,
        "account": env.account,
        "breaches": env.breach_log,
        "breach_events": env.breach_events,
        "n_sessions": n_sessions,
        "n_breach_sessions": len(env.breached_sessions),
        "n_sessions_with_trades": days_traded,
        "n_sessions_skipped": n_sessions - days_traded,
        "days_traded": days_traded,
        "survived_full_year": survived_full_year,
        "completed_data_split": completed_data_split,
        "episode_end_reason": episode_end_reason,
        "reward_sum": reward_sum,
        "reward_attribution": reward_attribution.as_dict(),
        "n_steps": n_steps,
        "exposure_bars": exposure_bars,
        "exposure_fraction": float(exposure_bars / n_steps) if n_steps else 0.0,
        "exposure_measure": BAR_CLOSE_EXPOSURE_MEASURE,
        "fail_time": fail_time,
        "max_trailing_dd": float(max_drawdown(env.equity_curve)),
        "peak_eod_trailing_dd_limit_usd": float(
            episode_equity.get("peak_eod_trailing_dd_limit_usd", 0.0)
        ),
        "max_peak_eod_trailing_dd_usd": float(
            episode_equity.get("max_peak_eod_trailing_dd_usd", 0.0)
        ),
        "peak_eod_dd_policy_ok": bool(episode_equity.get("peak_eod_dd_policy_ok", True)),
        "action_counts": dict(action_counts),
        **(
            {
                "trade_setup_decisions": trade_setup_decisions,
                "trade_setup_policy_metrics": trade_setup_metrics,
            }
            if trade_setup_metrics is not None
            else {}
        ),
        "entry_diag": dict(env._entry_diag),
        "trading_policy_mode": getattr(getattr(env, "trading_policy", None), "mode", "legacy"),
        "cumulative_payouts": float(getattr(env, "cumulative_payouts", 0.0)),
        "total_economic_value": float(
            getattr(getattr(env, "account", None), "equity", 0.0)
            + getattr(env, "cumulative_payouts", 0.0)
        ),
        "cycle_count": int(getattr(env, "cycle_count", 0)),
        "cycle_successes": int(getattr(env, "cycle_successes", 0)),
        "cycle_failures": int(getattr(env, "cycle_failures", 0)),
        "cycle_events": pd.DataFrame(getattr(env, "cycle_events", [])),
        "payout_events": pd.DataFrame(getattr(env, "payout_events", [])),
        "entry_state_diagnostics": (
            env.entry_state_diagnostics()
            if callable(getattr(env, "entry_state_diagnostics", None))
            else {}
        ),
        **(
            {
                "constraint_costs": constraint_cost_frame,
                "constraint_cost_summary": constraint_cost_summary,
            }
            if constraint_cost_summary is not None
            else {}
        ),
    }


def evaluate_provider(
    provider: Any,
    bars: pd.DataFrame,
    features: pd.DataFrame,
    **kwargs: Any,
) -> dict[str, Any]:
    """Evaluate a backend-neutral decision provider through the trading environment.

    Args:
        provider: Provider used by the operation described above.
        bars: Market bars to process.
        features: Feature values supplied to the operation.
        **kwargs: Kwargs used by the operation described above.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    if not hasattr(provider, "metadata") or not hasattr(provider, "predict"):
        raise TypeError("evaluate_provider requires a DecisionProvider implementation")
    return evaluate_model(provider, bars, features, **kwargs)
