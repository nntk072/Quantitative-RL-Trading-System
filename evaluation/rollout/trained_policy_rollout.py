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
from evaluation.rollout.trained_policy_decisions import (
    _candidate_geometry_action_trace as _candidate_geometry_action_trace,  # noqa: F401 - compatibility helper
)
from evaluation.rollout.trained_policy_decisions import (
    _decision_result_record as _decision_result_record,  # noqa: F401 - compatibility helper
)
from evaluation.rollout.trained_policy_decisions import (
    _pre_action_setup_identity as _pre_action_setup_identity,  # noqa: F401 - compatibility helper
)
from evaluation.rollout.trained_policy_decisions import (
    _setup_choice_probability_summary as _setup_choice_probability_summary,  # noqa: F401 - compatibility helper
)
from evaluation.rollout.trained_policy_decisions import (
    make_action_fn as make_action_fn,
)
from simulation.environment.env import TradingEnv
from trading.execution import COST_US100, CostModel

BAR_CLOSE_EXPOSURE_MEASURE = "fraction_of_evaluation_steps_with_position_at_bar_close"
CONSTRAINT_COST_SCHEMA = "discounted_constraint_cost_v1"
MAX_LOSS_FRACTION_CONSTRAINT_COST_SCHEMA = "max_loss_fraction_constraint_cost_v1"


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
    trade_setup_candidate_timeframes: tuple[str, ...] = (
        "M1",
        "M3",
        "M5",
        "M10",
        "M15",
        "M30",
        "H1",
        "H4",
        "D1",
    ),
    completed_htf_history_enabled: bool = True,
    candidate_geometry_actions: bool = False,
    agent_entry_execution: bool = False,
    entry_state_machine: bool = False,
    candidate_max_age_bars: int = 5,
    arm_requires_retest: bool = False,
    entry_state_observation: bool = True,
    observation_schema_version: str = "account-state-v1",
    observation_age_scale_bars: float = 60.0,
    reachable_r_validity_mask: bool = False,
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
    fill_latency_bars: int = 0,
    tick_fill_slippage_points: float | None = None,
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
    feature_validity_channels: bool = False,
    target_timeframes: tuple[str, ...] = ("M5", "M15", "H1"),
    scheduled_session_closes: dict[str, str] | None = None,
    session_start: str = "08:30",
    session_end: str = "15:00",
    session_timezone: str = "America/Chicago",
    source_clock_model: str = "native",
    env: TradingEnv | None = None,
    legacy_sequence_columns: bool = False,
    sequence_columns_override: tuple[str, ...] | None = None,
    trading_policy: dict[str, Any] | None = None,
    lot_step: float = 0.01,
    limit_order_max_offset_atr: float = 1.0,
    limit_order_max_ttl_bars: int = 60,
    limit_order_require_trade_through: bool = False,
    server_side_protective_orders: bool = False,
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
        lot_step: Broker volume increment used for risk-based sizing.
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
        trade_setup_candidate_timeframes: Timeframes that can contribute setup candidates.
        completed_htf_history_enabled: Whether completed HTF history enters observations.
        candidate_geometry_actions: Whether the policy consumes the fixed candidate
            price-geometry observation tensor.
        agent_entry_execution: Whether the policy selects market or limit execution.
        entry_state_machine: Whether to enable or require the entry state machine.
        candidate_max_age_bars: Market bar or price data used for walk a trained RL ``model`` over *bars*/*features* and collect trades.
        arm_requires_retest: Whether to enable or require the arm requires retest.
        entry_state_observation: Whether to enable or require the entry state observation.
        observation_schema_version: Text or path value identifying the observation schema version.
        observation_age_scale_bars: Market bar or price data used for walk a trained RL ``model`` over *bars*/*features* and collect trades.
        reachable_r_validity_mask: Whether to append the reachable-R validity sequence channel.
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
        fill_latency_bars: Whole-M1-bar delay applied to entry orders.
        tick_fill_slippage_points: Market-fill slippage override. Defaults to the
            supplied ``cost_model.slippage_points``; explicit zero preserves a
            zero-slippage replay.
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
        feature_validity_channels: Whether sequence streams include per-feature finite masks.
        target_timeframes: Items supplied for the target timeframes, in input order.
        scheduled_session_closes: Key-value data used for the scheduled session closes.
        session_start: Text or path value identifying the session start.
        session_end: Session close in the configured session timezone.
        session_timezone: IANA timezone used for session boundaries.
        source_clock_model: Interpretation of raw chart-index wall labels.
        env: Environment whose state is read or updated.
        legacy_sequence_columns: Whether to enable or require the legacy sequence columns.
        sequence_columns_override: Exact saved input coordinates for a bounded replay.
        trading_policy: Key-value data used for the trading policy.
        limit_order_max_offset_atr: Maximum policy limit distance in ATR units.
        limit_order_max_ttl_bars: Maximum pending-limit lifetime in M1 bars.
        limit_order_require_trade_through: Whether limit fills require a trade through the price.
        server_side_protective_orders: Resolve attached SL/TP orders on triggering ticks.

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
    if (env is not None and sequence_columns_override is not None) and tuple(
        getattr(env, "_obs_columns", ())
    ) != sequence_columns_override:
        raise ValueError(
            "supplied evaluation environment does not use the recorded sequence coordinates"
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
            lot_step=lot_step,
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
            trade_setup_candidate_timeframes=trade_setup_candidate_timeframes,
            completed_htf_history_enabled=completed_htf_history_enabled,
            candidate_geometry_actions=candidate_geometry_actions,
            agent_entry_execution=agent_entry_execution,
            entry_state_machine=entry_state_machine,
            candidate_max_age_bars=candidate_max_age_bars,
            arm_requires_retest=arm_requires_retest,
            entry_state_observation=entry_state_observation,
            observation_schema_version=observation_schema_version,
            observation_age_scale_bars=observation_age_scale_bars,
            reachable_r_validity_mask=reachable_r_validity_mask,
            legacy_sequence_columns=legacy_sequence_columns,
            sequence_columns_override=sequence_columns_override,
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
            fill_latency_bars=fill_latency_bars,
            tick_fill_slippage_points=(
                float(cost_model.slippage_points)
                if tick_fill_slippage_points is None
                else float(tick_fill_slippage_points)
            ),
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
            feature_validity_channels=feature_validity_channels,
            target_timeframes=target_timeframes,
            scheduled_session_closes=scheduled_session_closes,
            session_start=session_start,
            session_end=session_end,
            session_timezone=session_timezone,
            source_clock_model=source_clock_model,
            trading_policy=trading_policy,
            limit_order_max_offset_atr=limit_order_max_offset_atr,
            limit_order_max_ttl_bars=limit_order_max_ttl_bars,
            limit_order_require_trade_through=limit_order_require_trade_through,
            server_side_protective_orders=server_side_protective_orders,
        )

    if execution_seed is None:
        obs, _ = env.reset()
    else:
        obs, _ = env.reset(seed=execution_seed)
    done = False
    truncated = False
    decision_results: list[Any] = []
    action_fn = make_action_fn(
        model,
        continuous_actions,
        deterministic,
        strategy_actions=strategy_actions,
        decision_callback=decision_results.append,
    )
    action_counts: Counter[str] = Counter()
    trade_setup_decision_rows: list[dict[str, Any]] = []
    policy_decision_rows: list[dict[str, Any]] = []
    account_state_rows: list[dict[str, Any]] = []
    account_state_trace_complete = True
    reward_sum = 0.0
    reward_attribution = RewardAttribution()
    n_steps = 0
    exposure_bars = 0
    final_info: dict[str, Any] = {}
    constrained_state = getattr(model, "_constrained_rl_state", None)
    constraint_rows: list[dict[str, Any]] = []
    constraint_discount_gamma: float | None = None
    cost_normalization_limits_usd: tuple[float, float, float] | None = None
    if constrained_state is not None:
        if not isinstance(constrained_state, dict) or constrained_state.get("version") not in {
            2,
            3,
        }:
            raise ValueError("Evaluation requires a supported constrained-RL checkpoint state")
        state_version = int(constrained_state["version"])
        gamma_key = "gamma" if state_version == 2 else "cost_discount_gamma"
        gamma_value = constrained_state.get(gamma_key)
        if (
            isinstance(gamma_value, bool)
            or not isinstance(gamma_value, (int, float))
            or not np.isfinite(float(gamma_value))
            or not 0.0 < float(gamma_value) <= 1.0
        ):
            raise ValueError(f"Constrained-RL checkpoint {gamma_key} must be finite and in (0, 1]")
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
                    raise ValueError(
                        "Constrained-RL checkpoint loss-limit metadata is missing or invalid"
                    )
            daily_limit = float(cast(float, raw_daily_limit))
            max_loss_limit = float(cast(float, raw_max_loss_limit))
            trailing_limit = float(cast(float, raw_trailing_limit))
            if daily_limit < 0.0 or max_loss_limit <= 0.0 or trailing_limit < 0.0:
                raise ValueError(
                    "Constrained-RL checkpoint loss-limit metadata is outside valid bounds"
                )
            cost_normalization_limits_usd = (daily_limit, max_loss_limit, trailing_limit)
    discount_factor = 1.0
    while not (done or truncated):
        action = action_fn(obs)
        decision_result = decision_results.pop() if decision_results else None
        decision_candidate_count: int | None = None
        eligible_candidate_ids: list[int] | None = None
        if isinstance(obs, dict) and "trade_setup_mask" in obs:
            decision_mask = np.asarray(obs["trade_setup_mask"], dtype=np.float32).reshape(-1)
            decision_candidate_count = int(np.count_nonzero(decision_mask))
            eligible_candidate_ids = np.flatnonzero(decision_mask).astype(int).tolist()
        trade_setup_record: dict[str, Any] | None = None
        policy = getattr(model, "policy", None)
        coordinates = (
            tuple(decision_result.action_schema.coordinates)
            if decision_result is not None
            else tuple(getattr(policy, "hybrid_action_coordinates", ()))
        )
        setup_coordinate = "trade_setup" if "trade_setup" in coordinates else None
        if strategy_actions and setup_coordinate is not None and isinstance(obs, dict):
            from decisioning.trade_setup import (
                NO_TRADE_ID,
                TRADE_SETUP_ACTION_VERSION,
                TRADE_SETUP_CANDIDATES,
                trade_setup_id_from_box,
            )
            from features.context.trade_setup_candidates import (
                TRADE_SETUP_EVENT_IDENTITY_VERSION,
            )

            values = np.asarray(action, dtype=np.float32).reshape(-1)
            setup_index = coordinates.index(setup_coordinate)
            selected_id = trade_setup_id_from_box(float(values[setup_index]))
            mask = np.asarray(obs.get("trade_setup_mask", []), dtype=np.float32).reshape(-1)
            is_valid = selected_id == NO_TRADE_ID or (
                selected_id < len(mask) and bool(mask[selected_id] > 0.0)
            )
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
                "trade_setup_schema_version": TRADE_SETUP_ACTION_VERSION,
                "trade_setup_event_identity_version": TRADE_SETUP_EVENT_IDENTITY_VERSION,
                "trade_setup_source_event_id": None,
                "trade_setup_source_event_identity_status": (
                    "not_applicable"
                    if candidate.is_no_trade
                    else "candidate_ineligible"
                    if not is_valid
                    else "identity_not_emitted"
                ),
                "trade_setup_source_event_times_ns": [],
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
                _setup_choice_probability_summary(
                    getattr(policy, "last_trade_setup_probabilities", None), mask, selected_id
                )
            )
            trade_setup_record.update(
                {f"action_{name}": float(values[index]) for index, name in enumerate(coordinates)}
            )
            if is_valid:
                trade_setup_record.update(_pre_action_setup_identity(env, selected_id))
        if strategy_actions:
            action_key = str(tuple(np.round(np.asarray(action).reshape(-1), 4)))
        else:
            action_key = str(action)
        action_counts[action_key] += 1
        trade_event_start_index = len(env.trade_log)
        decision_bar_index = int(env.step_idx)
        session_ids = getattr(env, "_session_ids_arr", None)
        decision_session_id = int(session_ids[decision_bar_index]) if session_ids is not None else 0
        decision_observation = obs
        if trade_setup_record is not None:
            decision_bar_index = int(env.step_idx)
        obs, reward, done, truncated, info = env.step(action)
        candidate_geometry_trace: dict[str, Any] = {}
        if candidate_geometry_actions:
            if trade_setup_record is None or not isinstance(decision_observation, dict):
                raise RuntimeError(
                    "candidate-geometry rollout requires a trade-setup action and Dict observation"
                )
            candidate_geometry_trace = _candidate_geometry_action_trace(
                decision_observation,
                int(trade_setup_record["trade_setup_candidate_id"]),
                info,
            )
        decision_id = str(info.get("decision_id", ""))
        decision_row: dict[str, Any] = {
            "schema_version": "environment_policy_decision.completed_bar.v1",
            "decision_id": decision_id,
            "decision_index": decision_bar_index,
            "decision_bar_index": decision_bar_index,
            "decision_bar_time": str(
                info.get("decision_bar_time", env._bar_time(decision_bar_index))
            ),
            "decision_time": str(info.get("decision_time", "")),
            "session_id": decision_session_id,
            "action": int(info.get("action", 0)),
            "execution_type": str(info.get("execution_type", "market")),
            "limit_offset_atr": float(info.get("limit_offset_atr", 0.0)),
            "limit_ttl_bars": int(info.get("limit_ttl_bars", 1)),
            "position_direction_at_decision": int(info.get("position_direction_at_decision", 0)),
            "position_id_at_decision": info.get("position_id_at_decision"),
            "pending_order_id_at_decision": info.get("pending_order_id_at_decision"),
            "trade_event_start_index": trade_event_start_index,
            "trade_event_end_index_exclusive": len(env.trade_log),
        }
        if decision_result is not None:
            decision_row["typed_decision"] = _decision_result_record(model, decision_result)
        if "trade_setup_candidate_id" in info:
            decision_row.update(
                {
                    "trade_setup_candidate_id": info.get("trade_setup_candidate_id"),
                    "trade_setup_eligible": info.get("trade_setup_eligible"),
                    "trade_setup_idea": info.get("trade_setup_selected_idea"),
                    "trade_setup_timeframe": info.get("trade_setup_selected_timeframe"),
                    "trade_setup_direction": info.get("trade_setup_selected_direction"),
                    "trade_setup_source_event_id": info.get("trade_setup_source_event_id"),
                    "trade_setup_source_event_identity_status": info.get(
                        "trade_setup_source_event_identity_status"
                    ),
                }
            )
        if trade_setup_record is not None:
            for key in (
                "trade_setup_event_identity_version",
                "trade_setup_source_event_id",
                "trade_setup_source_event_identity_status",
                "trade_setup_source_event_times_ns",
            ):
                if key in trade_setup_record:
                    decision_row[key] = trade_setup_record[key]
        if decision_candidate_count is not None:
            decision_row["eligible_candidate_count"] = decision_candidate_count
            decision_row["eligible_trade_setup_ids"] = eligible_candidate_ids
        decision_row.update(candidate_geometry_trace)
        policy_decision_rows.append(decision_row)
        account_snapshot = info.get("account_state_snapshot")
        if isinstance(account_snapshot, dict):
            account_state_rows.append({"rollout_step": n_steps + 1, **account_snapshot})
        else:
            account_state_trace_complete = False
        if trade_setup_record is not None:
            recorded_candidate_id = info.get("trade_setup_candidate_id")
            recorded_eligible = info.get("trade_setup_eligible")
            if recorded_candidate_id != trade_setup_record["trade_setup_candidate_id"]:
                raise RuntimeError(
                    "environment decision trace candidate ID disagrees with the policy action"
                )
            if not isinstance(recorded_eligible, (bool, np.bool_)) or bool(
                recorded_eligible
            ) != bool(trade_setup_record["selection_valid"]):
                raise RuntimeError(
                    "environment decision trace eligibility disagrees with the observation mask "
                    f"(candidate_id={recorded_candidate_id!r}, "
                    f"recorded={recorded_eligible!r}, "
                    f"observation_mask={trade_setup_record['selection_valid']!r})"
                )
            trade_setup_record.update(candidate_geometry_trace)
            trade_setup_record["trade_setup_action_schema_version"] = str(
                info.get("trade_setup_action_schema_version", "")
            )
            trade_setup_record["trade_setup_eligible"] = bool(recorded_eligible)
            trade_setup_record["selected_idea"] = str(info.get("trade_setup_selected_idea", ""))
            trade_setup_record["selected_timeframe"] = str(
                info.get("trade_setup_selected_timeframe", "")
            )
            trade_setup_record["selected_direction"] = int(
                info.get("trade_setup_selected_direction", 0)
            )
            decision_time = info.get("decision_time", "")
            valuation_time = info.get(
                "valuation_time", env.equity_times[-1] if env.equity_times else ""
            )
            # Keep `time` as a compatibility alias, but define it as the policy
            # decision time. Valuation/fill timing is recorded separately.
            trade_setup_record["time"] = str(decision_time)
            trade_setup_record["decision_time"] = str(decision_time)
            trade_setup_record["decision_bar_time"] = str(
                info.get("decision_bar_time", env._bar_time(decision_bar_index))
            )
            trade_setup_record["valuation_time"] = str(valuation_time)
            trade_setup_record["decision_id"] = str(info.get("decision_id", ""))
            trade_setup_record["decision_bar_index"] = decision_bar_index
            trade_setup_record["entry_rejection_reason"] = str(
                info.get("entry_rejection_reason", "")
            )
            trade_setup_record["entry_state"] = str(info.get("entry_state", ""))
            trade_setup_record["position_open_after_step"] = bool(info.get("position", False))
            # These half-open indices address raw rows in result["trades"] and
            # the matching trades.csv. They retain rejects and management events
            # as well as fills, so every setup decision has an auditable outcome.
            trade_setup_record["trade_event_start_index"] = trade_event_start_index
            trade_setup_record["trade_event_end_index_exclusive"] = len(env.trade_log)
            trade_setup_decision_rows.append(trade_setup_record)
        final_info = info
        reward_sum += float(reward)
        reward_attribution.add(float(reward), info.get("reward_parts"))
        n_steps += 1
        if constraint_discount_gamma is not None:
            raw_constraints = info.get("constraints", {})
            if not isinstance(raw_constraints, dict):
                raise ValueError("Evaluation step is missing its constraint-cost record")
            component_costs = {
                "daily_cost": _finite_constraint_cost(raw_constraints, "daily_cost"),
                "max_loss_cost": _finite_constraint_cost(raw_constraints, "max_loss_cost"),
                "trailing_cost": _finite_constraint_cost(raw_constraints, "trailing_cost"),
            }
            if cost_normalization_limits_usd is not None:
                daily_limit, max_loss_limit, trailing_limit = cost_normalization_limits_usd
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
    # A daily-floor breach permanently fails the account/evaluation, even
    # though its allowance is recalculated from each session's opening equity.
    daily_loss_is_session_scoped = False
    hard_breach_events = breach_events
    fail_time = (
        hard_breach_events[0].get("detection_time", hard_breach_events[0].get("time"))
        if hard_breach_events
        else None
    )
    episode_equity = final_info.get("episode_equity", {})
    completed_data_split = episode_equity.get("completed_data_split") is True
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
                MAX_LOSS_FRACTION_CONSTRAINT_COST_SCHEMA
                if cost_normalization_limits_usd is not None
                else CONSTRAINT_COST_SCHEMA
            ),
            "cost_unit": (
                "fraction_of_max_loss_limit"
                if cost_normalization_limits_usd is not None
                else "max_of_original_normalized_constraint_units"
            ),
            "definition": (
                "per_step_max_limit_increase_normalized_to_max_loss_limit_and_breach_indicator"
                if cost_normalization_limits_usd is not None
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
        "policy_decisions": pd.DataFrame.from_records(policy_decision_rows),
        "policy_decisions_complete": len(policy_decision_rows) == n_steps,
        "account_state_trace": (
            pd.DataFrame.from_records(account_state_rows)
            if account_state_trace_complete
            else pd.DataFrame()
        ),
        "account_state_trace_complete": account_state_trace_complete,
        "account": env.account,
        "breaches": env.breach_log,
        "breach_events": env.breach_events,
        "n_sessions": n_sessions,
        "n_breach_sessions": len(env.breached_sessions),
        "n_sessions_with_trades": days_traded,
        "n_sessions_skipped": n_sessions - days_traded,
        "days_traded": days_traded,
        "survived_full_year": survived_full_year,
        "daily_loss_is_session_scoped": daily_loss_is_session_scoped,
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
        "peak_eod_dd_policy_ok": episode_equity.get("peak_eod_dd_policy_ok") is True,
        "action_counts": dict(action_counts),
        **(
            {
                "trade_setup_decisions": trade_setup_decisions,
                "trade_setup_policy_metrics": trade_setup_metrics,
            }
            if trade_setup_metrics is not None
            else {}
        ),
        **(
            {"policy_metadata": model.policy_metadata}
            if isinstance(getattr(model, "policy_metadata", None), dict)
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
