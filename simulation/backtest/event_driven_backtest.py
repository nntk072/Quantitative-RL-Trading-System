"""Event-driven backtester engine.

Fill-price semantics
--------------------
Every order fill uses a ``(bid, ask)`` quote obtained in this priority:

1. **Tick data**: a valid quote at the next bar's open timestamp.
2. **Bar-spread fallback**: the next bar's open quote, timestamped at its open.

Mark-to-market and per-trade stop checks use the bar-close quote (long @ bid,
short @ ask).

When ``randomized_fill_latency_ms`` is positive, submitted orders instead use
the first recorded quote at or after a seeded random arrival time strictly
below the configured latency bound. That mode fails closed when no timely tick
exists and never substitutes a candle quote for an execution.

Bar indexes are left-labeled. Equity observations are marked at each bar's
close timestamp, after current-bar protective events and session liquidation,
but before policy orders that execute on a later quote. OHLC-only protective
fills retain their triggering bar interval because their exact intrabar time
is not observable without ticks.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import pandas as pd

from decisioning.observation_state import entry_state_one_hot
from decisioning.observations import (
    OBSERVATION_SCHEMA_V1,
    OBSERVATION_SCHEMA_V2,
    OBSERVATION_SCHEMA_V3,
    ObservationSchema,
    account_state_v2,
    build_observation_schema,
    normalized_account_vector,
    pad_observation_window,
)
from decisioning.regime_observations import REGIME_FEATURES, regime_observation_schema
from decisioning.trade_setup import (
    NO_TRADE_ID,
    TradeSetupActionSchema,
    TradeSetupCandidate,
    TradeSetupExecutionChoice,
    TradeSetupGeometryChoice,
    build_trade_setup_action_schema,
    decode_trade_setup_execution_choice,
    decode_trade_setup_geometry_choice,
    trade_setup_candidate,
    trade_setup_id_from_box,
)
from features import attach_reachable_r, select_obs_columns
from features.context.trade_setup_candidates import (
    trade_setup_candidate_event_identities,
    trade_setup_candidate_mask,
    trade_setup_event_identity_record,
    trade_setup_event_is_current,
)
from market_data.loading.ticks import (
    TickExecutionUnavailable,
    event_keyed_execution_rng,
    limit_entry_execution_rng,
    resolve_tick_execution,
    resolve_tick_limit_execution,
)
from simulation.entry_evidence import build_entry_evidence
from simulation.entry_state import EntryStateMachine
from simulation.environment.observations import (
    DEFAULT_HTF_WINDOWS,
    HTF_BRANCHES,
    closed_window,
    prepare_observation_feature_channels,
    sanitize_observation_values,
    split_obs_columns,
    timeframe_starts,
)
from trading import AccountState
from trading.account import account_state_snapshot
from trading.execution import (
    COST_US100,
    Broker,
    CostModel,
    protective_level_fill_quote,
    raw_spread_to_price,
)
from trading.orders import limit_order_expiry, limit_price_from_atr_offset
from trading.policy import TradingPolicyConfig, resolve_trading_policy_mapping
from trading.risk import FTMOGuardrails, RiskDailyPnlBasis

if TYPE_CHECKING:
    from market_data.loading.ticks import TickBook

PolicyObservation = np.ndarray[Any, Any] | Mapping[str, np.ndarray[Any, Any]]
PolicyAction = int | np.ndarray[Any, Any]
ActionFn = Callable[[PolicyObservation], PolicyAction]
ArrayActionFn = Callable[[np.ndarray[Any, Any]], PolicyAction]
BacktestActionFn = ActionFn | ArrayActionFn


def _scalar_policy_action(policy: BacktestActionFn, observation: PolicyObservation) -> int:
    """Return one integer signal or fail clearly on incompatible action shapes.

    Args:
        policy: Scalar-action policy callable.
        observation: Array or named observation passed to the policy.

    Returns:
        Integer signal emitted by the policy.
    """
    if isinstance(observation, Mapping):
        action = cast(ActionFn, policy)(observation)
    else:
        action = policy(observation)
    if isinstance(action, (bool, np.bool_)) or not isinstance(action, (int, np.integer)):
        raise TypeError(
            "event-driven backtest policies must return one integer scalar action; "
            "schema-versioned action vectors require an explicit adapter"
        )
    return int(action)


def _entry_state_diagnostics(
    machine: EntryStateMachine | None, *, decision_count: int
) -> dict[str, Any]:
    """Serialize lifecycle counters using the same names as TradingEnv.

    Args:
        machine: Entry lifecycle state machine, when enabled.
        decision_count: Number of policy decisions used as the visit-rate denominator.

    Returns:
        Diagnostic fields, or an empty mapping when the machine is disabled.
    """
    if machine is None:
        return {}
    total_steps = max(1, int(decision_count))
    armed_bars = max(1, int(machine.armed_bars))
    return {
        "entry_state_machine": True,
        "entry_state_visits": dict(machine.visits),
        "entry_state_share": {
            state: round(count / total_steps, 6) for state, count in machine.visits.items()
        },
        "candidate_created": int(machine.candidate_created),
        "candidate_expired": int(machine.candidate_expired),
        "candidate_invalidated": int(machine.candidate_invalidated),
        "trigger_requested": int(machine.trigger_requested),
        "trigger_refused": int(machine.trigger_refused),
        "entered": int(machine.entered),
        "closed": int(machine.closed),
        "armed_bars": int(machine.armed_bars),
        "arm_to_trigger_rate": round(machine.entered / armed_bars, 6),
        "trigger_refusal_rate": round(
            machine.trigger_refused / max(1, machine.trigger_requested), 6
        ),
    }


def _geometry_action_record(
    choice: TradeSetupGeometryChoice | None,
) -> dict[str, Any] | None:
    """Serialize selected geometric coordinates for order and open records.

    Args:
        choice: Selected trade geometry, if the policy supplied one.

    Returns:
        Geometry values for event records, or ``None`` when absent.
    """
    if choice is None:
        return None
    return {
        "stop_anchor_fraction": choice.stop_anchor_fraction,
        "target_fraction": choice.target_fraction,
        "target_selections": choice.target_selections,
        "simplex_logits": choice.simplex_logits,
        "exit_mode": choice.exit_mode,
        "sl_mode": choice.sl_mode,
        "sl_mode_explicit": choice.sl_mode_explicit,
        "has_sl_mode": choice.has_sl_mode,
        "tp_mode": choice.tp_mode,
        "tp_mode_explicit": choice.tp_mode_explicit,
        "has_tp_mode": choice.has_tp_mode,
    }


def _policy_action(
    policy: BacktestActionFn,
    observation: PolicyObservation,
    *,
    feature_row: pd.Series,
    trade_setup_schema: TradeSetupActionSchema | None,
    max_limit_offset_atr: float,
    max_limit_ttl_bars: int,
    policy_risk_frac_range: tuple[float, float],
    allow_ema_exit: bool,
    default_sl_mode: str,
    default_tp_mode: str,
    sl_mode_defer_threshold: float,
    tp_mode_defer_threshold: float,
) -> tuple[
    int,
    TradeSetupCandidate | None,
    bool | None,
    TradeSetupExecutionChoice | None,
    float | None,
    TradeSetupGeometryChoice | None,
]:
    """Resolve a scalar signal or a masked, schema-versioned setup choice.

    Args:
        policy: Policy callable producing a scalar or schema-sized action.
        observation: Observation supplied to the policy.
        feature_row: Current feature values used to build candidate eligibility.
        trade_setup_schema: Action schema for candidate selection, if enabled.
        max_limit_offset_atr: Largest permitted ATR offset for limit entries.
        max_limit_ttl_bars: Maximum lifetime of a policy-selected limit order.
        policy_risk_frac_range: Lower and upper bounds for the risk coordinate.
        allow_ema_exit: Whether EMA exit choices are available.
        default_sl_mode: Stop-loss mode used when the policy defers.
        default_tp_mode: Take-profit mode used when the policy defers.
        sl_mode_defer_threshold: Coordinate threshold for default stop behavior.
        tp_mode_defer_threshold: Coordinate threshold for default target behavior.

    Returns:
        Scalar signal, chosen candidate, eligibility, execution choice, risk fraction,
        and selected geometry.
    """
    if trade_setup_schema is None:
        return _scalar_policy_action(policy, observation), None, None, None, None, None

    mask = trade_setup_candidate_mask(feature_row)
    policy_observation = (
        dict(observation) if isinstance(observation, Mapping) else {"seq": observation.copy()}
    )
    policy_observation["trade_setup_mask"] = mask.copy()
    raw_action = np.asarray(cast(ActionFn, policy)(policy_observation), dtype=np.float32).reshape(
        -1
    )
    if raw_action.size != trade_setup_schema.width:
        raise ValueError(
            f"trade setup action width {raw_action.size} disagrees with schema "
            f"{trade_setup_schema.version} (expected {trade_setup_schema.width})"
        )
    if not np.isfinite(raw_action).all():
        raise ValueError("trade setup action values must all be finite")
    clipped_action = [float(value) for value in np.clip(raw_action, -1.0, 1.0)]
    execution_choice = (
        decode_trade_setup_execution_choice(
            clipped_action,
            trade_setup_schema,
            max_limit_offset_atr=max_limit_offset_atr,
            max_limit_ttl_bars=max_limit_ttl_bars,
        )
        if trade_setup_schema.has_entry_execution
        else None
    )
    geometry_choice = decode_trade_setup_geometry_choice(
        clipped_action,
        trade_setup_schema,
        allow_ema_exit=allow_ema_exit,
        default_sl_mode=default_sl_mode,
        default_tp_mode=default_tp_mode,
        sl_mode_defer_threshold=sl_mode_defer_threshold,
        tp_mode_defer_threshold=tp_mode_defer_threshold,
    )
    action_index = trade_setup_schema.indices["trade_setup"]
    candidate_id = trade_setup_id_from_box(float(np.clip(raw_action[action_index], -1.0, 1.0)))
    candidate = trade_setup_candidate(candidate_id)
    eligible = bool(mask[candidate_id] > 0.0)
    risk_index = trade_setup_schema.indices.get("risk")
    if risk_index is None:
        raise ValueError("trade setup action schema has no risk coordinate")
    risk_unit = 0.5 * (float(np.clip(raw_action[risk_index], -1.0, 1.0)) + 1.0)
    risk_frac = policy_risk_frac_range[0] + risk_unit * (
        policy_risk_frac_range[1] - policy_risk_frac_range[0]
    )
    if candidate_id == NO_TRADE_ID or not eligible:
        return 0, candidate, eligible, execution_choice, 0.0, geometry_choice
    return candidate.direction, candidate, eligible, execution_choice, risk_frac, geometry_choice


def _bar_spread_price_units(row: pd.Series, cost_model: CostModel) -> float | None:
    """Convert the bar's raw MT5 ``spread`` column (broker points) to price units.

    MT5 CSVs report ``spread`` in integer broker points (e.g. ``80``), not
    price units. ``CostModel.bar_quote``/``fill_price`` expect the spread
    already in price units (e.g. ``0.6`` for US100), so it must be scaled by
    ``point_size`` here. Without this conversion a raw value like 80 was
    being added directly to the close price, producing bid/ask quotes tens
    to hundreds of points away from the visible candle.

    Args:
        row: Row index or record being processed.
        cost_model: Cost model used by the operation described above.

    Returns:
        Result of convert the bar's raw MT5 ``spread`` column (broker points) to price units.
    """
    if "spread" not in row.index or pd.isna(row["spread"]):
        return None
    return raw_spread_to_price(float(row["spread"]), cost_model.point_size)


def _sl_tp_fill_quote(
    direction: int,
    hit_price: float,
    cost_model: CostModel,
) -> tuple[float, float]:
    """Build a fill quote for an intrabar SL/TP hit on the triggering bar.

    The fill price is pinned to the SL/TP level; the opposite side is
    extended by the model spread so that ``Broker.close_position`` can
    deduct the round-turn spread cost.

    Args:
        direction: Signed trade direction: 1 for long and -1 for short.
        hit_price: Numeric value used for the hit price.
        cost_model: Cost model used by the operation described above.

    Returns:
        Values returned by ``_sl_tp_fill_quote``, in the declared order.
    """
    return protective_level_fill_quote(direction, hit_price, cost_model)


def _bar_quote(row: pd.Series, cost_model: CostModel) -> tuple[float, float]:
    """Derive ``(bid, ask)`` from a bar row (MT5 close = bid).

    Args:
        row: Row index or record being processed.
        cost_model: Cost model used by the operation described above.

    Returns:
        Values returned by ``_bar_quote``, in the declared order.
    """
    bar_spread = _bar_spread_price_units(row, cost_model)
    return cost_model.bar_quote(float(row["close"]), bar_spread=bar_spread)


def _bar_duration(index: pd.DatetimeIndex) -> pd.Timedelta:
    """Estimate bar duration from positive index deltas, defaulting to M1.

    Args:
        index: Position or label identifying the requested item.

    Returns:
        Result of estimate bar duration from positive index deltas, defaulting to M1.
    """
    if len(index) < 2:
        return pd.Timedelta(minutes=1)
    deltas = np.diff(index.to_numpy(dtype="datetime64[ns]").astype("int64"))
    positive = deltas[deltas > 0]
    if positive.size == 0:
        return pd.Timedelta(minutes=1)
    return pd.Timedelta(int(np.median(positive)), unit="ns")


def _fill_quote(
    fill_instant: pd.Timestamp,
    row: pd.Series,
    cost_model: CostModel,
    tickbook: TickBook | None,
) -> tuple[float, float]:
    """Return the fill quote for an order executed at *fill_instant*.

    *row* must be the bar whose time range contains *fill_instant* (i.e. the
    bar actually being executed into) — it is used both as the bar-quote
    fallback and as a sanity range for tick fills.

    Guards against tick-data gaps/outliers: a ``TickBook`` forward-fills
    quotes across data gaps, which can return a stale tick far from the
    current candle. If the tick quote's mid price falls outside this bar's
    ``[low, high]`` range (widened by a small buffer for spread), the tick
    fill is rejected in favour of a bar-based quote, so fills always land
    on/near a visible candle.

    Args:
        fill_instant: Fill instant used by the operation described above.
        row: Row index or record being processed.
        cost_model: Cost model used by the operation described above.
        tickbook: Tickbook used by the operation described above.

    Returns:
        Values returned by ``_fill_quote``, in the declared order.
    """
    return _fill_quote_event(fill_instant, row, cost_model, tickbook)[0]


def _fill_quote_event(
    fill_instant: pd.Timestamp,
    row: pd.Series,
    cost_model: CostModel,
    tickbook: TickBook | None,
    *,
    rng: np.random.Generator | None = None,
    randomized_fill_latency_ms: float = 0.0,
    max_tick_quote_wait_ms: int = 60_000,
    tick_execution_required: bool = False,
) -> tuple[tuple[float, float], pd.Timestamp, str, dict[str, Any]]:
    """Return a delayed execution quote and timing/source metadata.

    Args:
        fill_instant: Fill instant used by the operation described above.
        row: Row index or record being processed.
        cost_model: Cost model used by the operation described above.
        tickbook: Tickbook used by the operation described above.
        rng: Rng used by the operation described above.
        randomized_fill_latency_ms: Numeric value used for the randomized fill latency ms.
        max_tick_quote_wait_ms: Numeric value used for the max tick quote wait ms.
        tick_execution_required: Whether to enable or require the tick execution required.

    Returns:
        Mapping from ``str`` keys to ``Any]`` values.
    """
    if randomized_fill_latency_ms > 30.0 or randomized_fill_latency_ms < 0.0:
        raise ValueError("randomized_fill_latency_ms must be in [0, 30]")
    if max_tick_quote_wait_ms <= 0:
        raise ValueError("max_tick_quote_wait_ms must be positive")
    if tick_execution_required or randomized_fill_latency_ms > 0:
        if tickbook is None or rng is None:
            raise TickExecutionUnavailable("tick-only fills require a TickBook and RNG")
        execution = resolve_tick_execution(
            tickbook,
            fill_instant,
            rng,
            max_latency_ns_exclusive=int(randomized_fill_latency_ms * 1_000_000),
            max_quote_wait_ns=max_tick_quote_wait_ms * 1_000_000,
        )
        if execution is None:
            raise TickExecutionUnavailable(
                f"no executable tick within {max_tick_quote_wait_ms}ms of {fill_instant}"
            )
        return (
            (execution.bid, execution.ask),
            execution.tick_time,
            "tick",
            {
                "order_submission_time": execution.order_time,
                "execution_order_time": execution.order_time,
                "execution_arrival_time": execution.arrival_time,
                "execution_latency_ns": execution.latency_ns,
                "actual_tick_time": execution.tick_time,
                "fill_quote_source": "tick",
            },
        )

    bar_spread = _bar_spread_price_units(row, cost_model)
    if tickbook is not None:
        q = tickbook.quote_at(fill_instant)
        if q is not None:
            bid, ask = q
            mid = (bid + ask) / 2.0
            lo = float(row["low"])
            hi = float(row["high"])
            buffer = max(hi - lo, bar_spread or 0.0, cost_model.spread_points)
            if tick_execution_required or lo - buffer <= mid <= hi + buffer:
                return (
                    q,
                    fill_instant,
                    "tick",
                    {
                        "order_submission_time": fill_instant,
                        "execution_order_time": fill_instant,
                        "execution_arrival_time": fill_instant,
                        "execution_latency_ns": 0,
                        "actual_tick_time": fill_instant,
                        "fill_quote_source": "tick",
                    },
                )
                # In legacy mode, reject outlier ticks and use the candle quote.
    if tick_execution_required:
        raise TickExecutionUnavailable(
            f"no executable tick within {max_tick_quote_wait_ms}ms of {fill_instant}"
        )
    return (
        cost_model.bar_quote(float(row["open"]), bar_spread=bar_spread),
        fill_instant,
        "bar_open",
        {},
    )


def _is_last_ny_bar(bars: pd.DataFrame, i: int, is_ny: bool) -> bool:
    """True on the last NY bar of a session (next bar is non-NY or a time jump).

    Args:
        bars: Market bars to process.
        i: Numeric value used for the i.
        is_ny: Whether to enable or require the is ny.

    Returns:
        Whether is last ny bar meets the requested condition.
    """
    if not is_ny:
        return False
    if i + 1 >= len(bars):
        return True
    nxt = bars.iloc[i + 1]
    next_ny = "session" not in nxt.index or str(nxt["session"]) == "ny"
    if not next_ny:
        return True
    return pd.Timestamp(bars.index[i + 1]) - pd.Timestamp(bars.index[i]) > pd.Timedelta(minutes=1)


def _ny_gap_guard_mask(bars: pd.DataFrame) -> np.ndarray[Any, np.dtype[np.bool_]]:
    """Mark NY bars followed by a skipped non-NY interval and another NY bar.

    Args:
        bars: Chronological market bars with optional session labels.

    Returns:
        Boolean mask marking NY rows whose next NY bar skips intervening rows.
    """
    if "session" in bars.columns:
        ny_mask = bars["session"].eq("ny").to_numpy(dtype=bool)
    else:
        ny_mask = np.ones(len(bars), dtype=bool)
    ny_indices = np.flatnonzero(ny_mask)
    mask = np.zeros(len(bars), dtype=bool)
    for current, following in zip(ny_indices[:-1], ny_indices[1:], strict=True):
        if following > current + 1:
            mask[current] = True
    return mask


def run_backtest(
    bars: pd.DataFrame,
    features: pd.DataFrame,
    policy: BacktestActionFn,
    obs_window: int = 60,
    cost_model: CostModel = COST_US100,
    broker_kwargs: dict[str, Any] | None = None,
    guardrail_kwargs: dict[str, Any] | None = None,
    initial_balance: float = 100_000.0,
    lots: float = 1.0,
    max_loss_per_trade_usd: float | None = None,
    take_profit_per_trade_usd: float | None = None,
    tickbook: TickBook | None = None,
    fill_delay_ms: int = 0,
    randomized_fill_latency_ms: float = 0.0,
    max_tick_quote_wait_ms: int = 60_000,
    tick_execution_required: bool = False,
    execution_seed: int = 0,
    fill_latency_bars: int = 0,
    use_structure_sl_tp: bool = False,
    risk_frac: float | None = None,
    policy_risk_frac_range: tuple[float, float] | None = None,
    rr_ratio: float = 2.0,
    swing_buffer_pts: float = 1.0,
    sl_buffer_pts: float = 0.0,
    min_lot: float = 0.01,
    max_lot: float = 100.0,
    contract_size: float = 1.0,
    hold_on_zero: bool = False,
    exit_action: int | None = None,
    block_overnight: bool = True,
    eod_risk: dict[str, Any] | None = None,
    sl_mode: str = "fixed",
    daily_pnl_basis: RiskDailyPnlBasis | None = None,
    trading_policy: TradingPolicyConfig | Mapping[str, Any] | None = None,
    tick_fill_slippage_points: float | None = None,
    trade_setup_actions: bool = False,
    trade_setup_action_schema: TradeSetupActionSchema | None = None,
    allow_ema_exit: bool = True,
    trade_setup_geometry: bool | None = None,
    strategy: Any | None = None,
    min_sl_atr_mult: float = 0.5,
    min_sl_points: float = 0.0,
    policy_rr_ratio_range: tuple[float, float] | None = None,
    target_timeframes: tuple[str, ...] = ("M5", "M15", "H1"),
    ema_runner_fraction: float = 0.0,
    limit_order_max_offset_atr: float = 1.0,
    limit_order_max_ttl_bars: int = 60,
    limit_order_require_trade_through: bool = False,
    lot_step: float = 0.01,
    tp_mode: str = "fixed",
    sl_mode_defer_threshold: float = 0.1,
    tp_mode_defer_threshold: float = 0.1,
    tp_breakeven_alpha: float = 0.5,
    observation_schema: ObservationSchema | None = None,
    normalize_account: bool = True,
    observation_age_scale_bars: float = 60.0,
    entry_state_machine: bool = False,
    candidate_max_age_bars: int = 5,
    arm_requires_retest: bool = False,
    regime_observation: bool = False,
    mtf_observation: bool = False,
    mtf_windows: Mapping[str, int] | None = None,
    feature_validity_channels: bool = False,
    scheduled_session_closes: dict[str, str] | None = None,
    session_start: str = "16:30",
    vae: Any | None = None,
    pre_ny_by_date: Mapping[Any, np.ndarray[Any, Any]] | None = None,
    pre_ny_data: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Run a full backtest over aligned bars + features.

    Accounting, policy actions, and protective/session events live in focused
    simulation.backtest modules so this function remains the readable
    composition root for the timing-sensitive execution contract.

    Args:
        bars: Market bars to process.
        features: Feature values supplied to the operation.
        policy: Policy used to select or evaluate actions.
        obs_window: Numeric value used for the obs window.
        cost_model: Cost model used by the operation described above.
        broker_kwargs: Key-value data used for the broker kwargs.
        guardrail_kwargs: Key-value data used for the guardrail kwargs.
        initial_balance: Numeric value used for the initial balance.
        lots: Numeric value used for the lots.
        max_loss_per_trade_usd: Max loss per trade usd used by the operation described above.
        take_profit_per_trade_usd: Take profit per trade usd used by the operation described above.
        tickbook: Tickbook used by the operation described above.
        fill_delay_ms: Numeric value used for the fill delay ms.
        randomized_fill_latency_ms: Numeric value used for the randomized fill latency ms.
        max_tick_quote_wait_ms: Numeric value used for the max tick quote wait ms.
        tick_execution_required: Whether to enable or require the tick execution required.
        execution_seed: Numeric value used for the execution seed.
        fill_latency_bars: Whole M1 bars added after the ordinary next-bar entry fill.
        use_structure_sl_tp: Whether to enable or require the use structure sl tp.
        risk_frac: Numeric value used for the risk frac.
        policy_risk_frac_range: Optional lower/upper risk-fraction bounds decoded from
            the setup action's risk coordinate. When omitted, that coordinate retains
            the configured fixed risk fraction for backwards-compatible callers.
        rr_ratio: Numeric value used for the rr ratio.
        swing_buffer_pts: Numeric value used for the swing buffer pts.
        sl_buffer_pts: Confirmed-swing trailing-stop buffer in price units.
        min_lot: Numeric value used for the min lot.
        max_lot: Numeric value used for the max lot.
        lot_step: Broker volume increment used by risk-based position sizing.
        contract_size: Number specifying the contract size for this operation.
        hold_on_zero: Whether to enable or require the hold on zero.
        exit_action: Exit action used by the operation described above.
        block_overnight: Whether to enable or require the block overnight.
        eod_risk: Optional environment-compatible position guard settings. When
            supplied, the backtest uses ``max_loss_usd`` as an intrabar adverse
            excursion cutoff, raised to planned structural-stop risk when
            ``respect_planned_risk`` is true. When omitted, the legacy
            ``max_loss_per_trade_usd`` close cap is retained.
        sl_mode: Static stop-management mode for the scalar-action backtest.
            ``fixed``, ``breakeven``, and ``trailing`` are supported. When a
            learned SL coordinate is present, its neutral band starts at
            ``fixed`` and advances through the state machine.
        tp_mode: Deferred TP-management default when the schema has a TP mode
            coordinate; the mode then advances through the state machine.
        sl_mode_defer_threshold: Neutral-band half-width for the learned SL mode.
        tp_mode_defer_threshold: Neutral-band half-width for the learned TP mode.
        tp_breakeven_alpha: Initial-risk fraction used to pull a TP toward entry.
        observation_schema: Explicit account observation contract. Supplying it
            requests the environment's structured observation for scalar or setup policies.
        normalize_account: Emit the normalized v1 vector; v2/v3 require normalization.
        observation_age_scale_bars: Position-age scale used by account-state-v2/v3.
        entry_state_machine: Track and gate persistent entry opportunities as in TradingEnv.
        candidate_max_age_bars: Maximum evidence age retained by the entry lifecycle.
        arm_requires_retest: Require a current directional retest before arming a candidate.
        regime_observation: Add the versioned completed-D1 regime vector and validity mask.
        mtf_observation: Add the environment's closed higher-timeframe observation windows.
        mtf_windows: Optional per-timeframe row counts overriding environment defaults.
        feature_validity_channels: Append finite-value channels to sequence windows.
        scheduled_session_closes: Optional local-date to NY-close map for clipped HTF bars.
        session_start: Local session-start clock used by HTF availability calculations.
        vae: Optional frozen encoder used to emit the environment's ``vae_z`` input.
        pre_ny_by_date: Per-session VAE input sequences keyed by local market date.
        pre_ny_data: Legacy row-aligned flattened VAE inputs.
        daily_pnl_basis: Optional daily-loss basis override. Session net equity
            includes realized and open PnL since the supplied session reset;
            legacy gross closed losses does not offset wins or include open PnL.
            When ``trading_policy`` is provided, its daily-PnL contract is used.
        trading_policy: Optional validated account-policy configuration. Repeated
            payout mode enables realized-balance withdrawals and account resets;
            its sizing requires structure-derived stop levels.
        tick_fill_slippage_points: Market-fill slippage override (historical
            parameter name retained). Defaults to ``cost_model.slippage_points``
            for tick and bar quotes. Explicit zero preserves a zero-slippage
            replay. Limit entries stay price-bounded.
        trade_setup_actions: Expose the canonical setup eligibility mask to the
            policy and decode its versioned categorical action instead of a
            scalar direction. Risk, stop/target geometry, and position exits
            continue to use the event backtest's configured controls.
        trade_setup_action_schema: Optional configured setup action schema;
            the canonical default schema is used when setup actions are enabled.
        allow_ema_exit: Whether a selected setup action may choose an EMA-21 exit.
        trade_setup_geometry: Apply the setup action's selected stop/target
            geometry. Defaults to enabled with setup actions and disabled for
            scalar-action callers.
        strategy: Strategy contract used by structural order placement. The
            baseline strategy is used when setup geometry is enabled and none
            is supplied.
        min_sl_atr_mult: Minimum structural stop distance as a multiple of ATR-5.
        min_sl_points: Absolute minimum structural stop distance in price units.
        policy_rr_ratio_range: Inclusive lower/upper reward-risk bounds for
            structural targets. Defaults to the environment's ``[1.0, 3.0]``.
        target_timeframes: Higher timeframes permitted for target references.
        ema_runner_fraction: Fraction reserved for the EMA runner when enabled.
        limit_order_max_offset_atr: Maximum policy-selected limit distance from
            the decision close, expressed in ATR units.
        limit_order_max_ttl_bars: Maximum integer M1-bar lifetime for a policy
            selected resting limit.
        limit_order_require_trade_through: Require the executable quote to
            move strictly beyond the limit for queue-position sensitivity.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    from simulation.backtest.accounting import (
        process_repeated_payout,
        record_repeated_cycle_failure,
    )
    from simulation.backtest.policy_actions import apply_policy_action
    from simulation.backtest.protective_events import (
        _default_sl_mode,
        liquidate_terminal_position,
        process_protective_and_account_events,
    )
    from simulation.backtest.runtime import BacktestSettings, BacktestState

    if isinstance(fill_latency_bars, bool):
        raise ValueError("fill_latency_bars must be a non-negative integer")
    raw_fill_latency_bars = fill_latency_bars
    try:
        fill_latency_bars = int(raw_fill_latency_bars)
    except (TypeError, ValueError) as exc:
        raise ValueError("fill_latency_bars must be a non-negative integer") from exc
    if fill_latency_bars < 0 or fill_latency_bars != raw_fill_latency_bars:
        raise ValueError("fill_latency_bars must be a non-negative integer")
    if isinstance(tick_fill_slippage_points, bool):
        raise ValueError("tick_fill_slippage_points must be finite and non-negative")
    try:
        resolved_market_slippage = (
            float(cost_model.slippage_points)
            if tick_fill_slippage_points is None
            else float(tick_fill_slippage_points)
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("tick_fill_slippage_points must be finite and non-negative") from exc
    if not np.isfinite(resolved_market_slippage) or resolved_market_slippage < 0.0:
        raise ValueError("tick_fill_slippage_points must be finite and non-negative")
    if randomized_fill_latency_ms < 0.0 or randomized_fill_latency_ms > 30.0:
        raise ValueError("randomized_fill_latency_ms must be in [0, 30]")
    if not np.isfinite(limit_order_max_offset_atr) or limit_order_max_offset_atr <= 0.0:
        raise ValueError("limit_order_max_offset_atr must be finite and positive")
    if (
        isinstance(limit_order_max_ttl_bars, bool)
        or int(limit_order_max_ttl_bars) != limit_order_max_ttl_bars
        or limit_order_max_ttl_bars < 1
    ):
        raise ValueError("limit_order_max_ttl_bars must be a positive integer")
    sl_mode = str(sl_mode).lower()
    if sl_mode not in {"fixed", "breakeven", "trailing"}:
        raise ValueError(
            "sl_mode must be 'fixed', 'breakeven', or 'trailing' for scalar-action backtests"
        )
    tp_mode = str(tp_mode).lower()
    if tp_mode not in {"fixed", "breakeven", "trailing"}:
        raise ValueError("tp_mode must be 'fixed', 'breakeven', or 'trailing'")
    for name, value in (
        ("sl_mode_defer_threshold", sl_mode_defer_threshold),
        ("tp_mode_defer_threshold", tp_mode_defer_threshold),
    ):
        if not np.isfinite(value) or value < 0.0 or value > 0.5:
            raise ValueError(f"{name} must be finite and in [0, 0.5]")
    if not np.isfinite(tp_breakeven_alpha) or tp_breakeven_alpha < 0.0:
        raise ValueError("tp_breakeven_alpha must be finite and non-negative")
    try:
        sl_buffer_pts = float(sl_buffer_pts)
    except (TypeError, ValueError) as exc:
        raise ValueError("sl_buffer_pts must be finite and non-negative") from exc
    if not np.isfinite(sl_buffer_pts) or sl_buffer_pts < 0.0:
        raise ValueError("sl_buffer_pts must be finite and non-negative")
    if not np.isfinite(lot_step) or lot_step <= 0.0:
        raise ValueError("lot_step must be finite and positive")
    if not trade_setup_actions and trade_setup_action_schema is not None:
        raise ValueError("trade_setup_action_schema requires trade_setup_actions=true")
    extended_observation_requested = bool(
        regime_observation
        or mtf_observation
        or feature_validity_channels
        or mtf_windows is not None
        or vae is not None
        or pre_ny_by_date is not None
        or pre_ny_data is not None
    )
    if vae is None and (pre_ny_by_date is not None or pre_ny_data is not None):
        raise ValueError("pre-NY VAE inputs require vae")
    if vae is not None and not pre_ny_by_date and pre_ny_data is None:
        raise ValueError("vae requires pre_ny_by_date or legacy pre_ny_data")
    resolved_observation_schema: ObservationSchema | None
    if (
        not isinstance(candidate_max_age_bars, (int, np.integer))
        or isinstance(candidate_max_age_bars, (bool, np.bool_))
        or candidate_max_age_bars < 0
    ):
        raise ValueError("candidate_max_age_bars must be a non-negative integer")
    if trade_setup_actions:
        setup_action_schema = (
            build_trade_setup_action_schema()
            if trade_setup_action_schema is None
            else trade_setup_action_schema
        )
        if not isinstance(setup_action_schema, TradeSetupActionSchema):
            raise TypeError("trade_setup_action_schema must be a TradeSetupActionSchema")
        resolved_observation_schema = observation_schema or build_observation_schema(
            entry_state_visibility=bool(entry_state_machine)
        )
        if not isinstance(resolved_observation_schema, ObservationSchema):
            raise TypeError("observation_schema must be an ObservationSchema")
    else:
        setup_action_schema = None
        needs_environment_observation = (
            observation_schema is not None
            or extended_observation_requested
            or bool(entry_state_machine)
        )
        resolved_observation_schema = (
            (
                observation_schema
                or build_observation_schema(entry_state_visibility=bool(entry_state_machine))
            )
            if needs_environment_observation
            else None
        )
    if resolved_observation_schema is not None:
        canonical_observation_schema = build_observation_schema(
            resolved_observation_schema.version,
            entry_state_visibility=resolved_observation_schema.entry_state_visibility,
        )
        if resolved_observation_schema != canonical_observation_schema:
            raise ValueError("observation_schema coordinates disagree with its version")
        if (
            resolved_observation_schema.version in (OBSERVATION_SCHEMA_V2, OBSERVATION_SCHEMA_V3)
            and not normalize_account
        ):
            raise ValueError("account-state-v2/v3 requires normalize_account=True")
        if not np.isfinite(observation_age_scale_bars) or float(observation_age_scale_bars) <= 0.0:
            raise ValueError("observation_age_scale_bars must be finite and positive")
    if not isinstance(arm_requires_retest, (bool, np.bool_)):
        raise ValueError("arm_requires_retest must be boolean")
    apply_setup_geometry = (
        setup_action_schema is not None
        if trade_setup_geometry is None
        else bool(trade_setup_geometry)
    )
    if apply_setup_geometry and setup_action_schema is None:
        raise ValueError("trade_setup_geometry requires trade_setup_actions=true")
    if isinstance(min_sl_atr_mult, bool) or not np.isfinite(min_sl_atr_mult) or min_sl_atr_mult < 0:
        raise ValueError("min_sl_atr_mult must be finite and non-negative")
    if isinstance(min_sl_points, bool) or not np.isfinite(min_sl_points) or min_sl_points < 0:
        raise ValueError("min_sl_points must be finite and non-negative")
    if len(target_timeframes) == 0:
        raise ValueError("target_timeframes must contain at least one timeframe")
    if policy_rr_ratio_range is None:
        resolved_policy_rr_ratio_range = (1.0, 3.0)
    else:
        if len(policy_rr_ratio_range) != 2:
            raise ValueError("policy_rr_ratio_range must contain two values")
        resolved_policy_rr_ratio_range = (
            float(policy_rr_ratio_range[0]),
            float(policy_rr_ratio_range[1]),
        )
        rr_low, rr_high = resolved_policy_rr_ratio_range
        if not np.isfinite(rr_low) or not np.isfinite(rr_high) or rr_low < 0.0 or rr_high < rr_low:
            raise ValueError("policy_rr_ratio_range must be finite, non-negative, and ordered")
    if (
        isinstance(ema_runner_fraction, bool)
        or not np.isfinite(ema_runner_fraction)
        or not 0.0 <= ema_runner_fraction < 1.0
    ):
        raise ValueError("ema_runner_fraction must be finite and in [0, 1)")

    if trading_policy is None:
        resolved_trading_policy = None
    elif isinstance(trading_policy, TradingPolicyConfig):
        resolved_trading_policy = trading_policy.validate()
    elif isinstance(trading_policy, Mapping):
        # Accept both a resolved policy mapping (``TradingPolicyConfig.to_dict``)
        # and a full application configuration mapping.
        if "mode" in trading_policy:
            resolved_trading_policy = TradingPolicyConfig.from_mapping(trading_policy).validate()
        else:
            resolved_trading_policy = resolve_trading_policy_mapping(trading_policy)
    else:
        raise TypeError("trading_policy must be TradingPolicyConfig, a mapping, or None")

    repeated_payout = bool(
        resolved_trading_policy is not None and resolved_trading_policy.repeated_payout
    )
    if resolved_trading_policy is not None:
        policy_daily_basis = resolved_trading_policy.daily_pnl_basis
        if policy_daily_basis is None:
            raise ValueError("trading_policy must define a daily PnL basis")
        if daily_pnl_basis is not None and daily_pnl_basis != policy_daily_basis:
            raise ValueError("daily_pnl_basis conflicts with trading_policy")
        daily_pnl_basis = cast(RiskDailyPnlBasis, policy_daily_basis)
    if repeated_payout:
        assert resolved_trading_policy is not None
        if abs(float(initial_balance) - resolved_trading_policy.operating_balance) > 1e-9:
            raise ValueError("repeated-payout initial_balance must equal operating_balance")
        if not use_structure_sl_tp:
            raise ValueError("repeated-payout backtests require structure-derived stop levels")
        risk_frac = (
            resolved_trading_policy.max_agent_risk_frac if risk_frac is None else float(risk_frac)
        )
        if not 0.0 <= risk_frac <= resolved_trading_policy.max_agent_risk_frac:
            raise ValueError("risk_frac must be within the repeated-payout policy limit")
        repeated_risk_cap = (
            resolved_trading_policy.operating_balance * resolved_trading_policy.max_agent_risk_frac
        )
        max_loss_per_trade_usd = (
            repeated_risk_cap
            if max_loss_per_trade_usd is None
            else min(float(max_loss_per_trade_usd), repeated_risk_cap)
        )
    elif risk_frac is None:
        risk_frac = 0.01

    if policy_risk_frac_range is None:
        # Match TradingEnv's default continuous strategy-risk action range when
        # the schema exposes a learned risk coordinate. Scalar callers retain
        # the historical fixed-risk behavior.
        if setup_action_schema is not None:
            resolved_policy_risk_frac_range = (
                (0.0, float(resolved_trading_policy.max_agent_risk_frac))
                if repeated_payout and resolved_trading_policy is not None
                else (0.005, 0.02)
            )
        else:
            resolved_policy_risk_frac_range = (float(risk_frac), float(risk_frac))
    else:
        if len(policy_risk_frac_range) != 2:
            raise ValueError("policy_risk_frac_range must contain two values")
        resolved_policy_risk_frac_range = (
            float(policy_risk_frac_range[0]),
            float(policy_risk_frac_range[1]),
        )
        low_risk, high_risk = resolved_policy_risk_frac_range
        if (
            not np.isfinite(low_risk)
            or not np.isfinite(high_risk)
            or low_risk < 0.0
            or high_risk < low_risk
        ):
            raise ValueError("policy_risk_frac_range must be finite, non-negative, and ordered")
    if repeated_payout and resolved_trading_policy is not None:
        if resolved_policy_risk_frac_range[1] > resolved_trading_policy.max_agent_risk_frac:
            raise ValueError("policy_risk_frac_range exceeds the repeated-payout policy risk limit")

    common_idx = bars.index.intersection(features.index)
    bars = bars.loc[common_idx]
    features = features.loc[common_idx]
    geometry_max_tp_dist = None
    resolved_strategy = strategy
    if apply_setup_geometry:
        if resolved_strategy is None:
            from trading.strategies import BaselineStrategy

            resolved_strategy = BaselineStrategy()
        if "atr_5" in features.columns:
            from features.context.reachability import max_tp_distance

            geometry_max_tp_dist = max_tp_distance(bars, features["atr_5"]).reindex(bars.index)

    broker = Broker(cost_model=cost_model, **(broker_kwargs or {}))
    resolved_guardrails = dict(guardrail_kwargs or {})
    if repeated_payout:
        assert resolved_trading_policy is not None
        if resolved_trading_policy.max_loss_limit_initial_pct is None:
            raise ValueError("trading_policy.max_loss_limit_initial_pct is required")
        resolved_guardrails.update(
            {
                "risk_per_trade_limit": (
                    resolved_trading_policy.operating_balance
                    * resolved_trading_policy.max_agent_risk_frac
                ),
                "trailing_dd_limit": 0.0,
                "soft_trailing_dd_limit": 0.0,
                "limit_value_mode": "percent_equity",
                "risk_per_trade_limit_pct": resolved_trading_policy.max_agent_risk_frac,
                "daily_loss_limit_pct": resolved_trading_policy.daily_loss_limit_pct,
                "soft_daily_loss_limit_pct": 0.0,
                "max_loss_limit_initial_pct": float(
                    resolved_trading_policy.max_loss_limit_initial_pct
                ),
                "soft_max_loss_limit_initial_pct": 0.0,
            }
        )
    guardrails = FTMOGuardrails(**resolved_guardrails)
    settings = BacktestSettings(
        cost_model=cost_model,
        lots=lots,
        max_loss_per_trade_usd=max_loss_per_trade_usd,
        take_profit_per_trade_usd=take_profit_per_trade_usd,
        tickbook=tickbook,
        fill_delay_ms=fill_delay_ms,
        randomized_fill_latency_ms=randomized_fill_latency_ms,
        max_tick_quote_wait_ms=max_tick_quote_wait_ms,
        tick_execution_required=tick_execution_required,
        use_structure_sl_tp=bool(use_structure_sl_tp or apply_setup_geometry),
        risk_frac=risk_frac,
        policy_risk_frac_range=resolved_policy_risk_frac_range,
        rr_ratio=rr_ratio,
        swing_buffer_pts=swing_buffer_pts,
        min_lot=min_lot,
        max_lot=max_lot,
        lot_step=lot_step,
        contract_size=contract_size,
        # In the categorical setup contract, NO_TRADE means abstain/hold;
        # preserve the scalar API's configurable zero-action behavior.
        hold_on_zero=bool(hold_on_zero or setup_action_schema is not None),
        exit_action=exit_action,
        block_overnight=block_overnight,
        fill_latency_bars=fill_latency_bars,
        eod_risk=None if eod_risk is None else dict(eod_risk),
        execution_seed=int(execution_seed),
        sl_mode=sl_mode,
        tp_mode=tp_mode,
        sl_mode_defer_threshold=float(sl_mode_defer_threshold),
        tp_mode_defer_threshold=float(tp_mode_defer_threshold),
        tp_breakeven_alpha=float(tp_breakeven_alpha),
        sl_buffer_pts=float(sl_buffer_pts),
        tick_fill_slippage_points=resolved_market_slippage,
        trading_policy=resolved_trading_policy,
        trade_setup_geometry=apply_setup_geometry,
        strategy=resolved_strategy,
        min_sl_atr_mult=float(min_sl_atr_mult),
        min_sl_points=float(min_sl_points),
        policy_rr_ratio_range=resolved_policy_rr_ratio_range,
        target_timeframes=tuple(str(tf) for tf in target_timeframes),
        geometry_max_tp_dist=geometry_max_tp_dist,
        allow_multi_tp=bool(setup_action_schema and setup_action_schema.has_multi_tp),
        allow_simplex=bool(setup_action_schema and setup_action_schema.has_simplex),
        ema_runner_fraction=float(ema_runner_fraction),
    )
    state = BacktestState(
        account=AccountState(
            initial_balance=initial_balance,
            policy_mode=(
                resolved_trading_policy.mode if resolved_trading_policy is not None else "legacy"
            ),
            daily_pnl_basis_override=daily_pnl_basis,
        )
    )
    entry_machine = (
        EntryStateMachine(int(candidate_max_age_bars), bool(arm_requires_retest))
        if entry_state_machine
        or bool(
            resolved_observation_schema is not None
            and resolved_observation_schema.entry_state_visibility
        )
        else None
    )
    entry_trigger_pending = False
    confirmed_manipulation_sessions: set[int] = set()
    if entry_machine is not None and resolved_strategy is None:
        from trading.strategies import BaselineStrategy

        resolved_strategy = BaselineStrategy()
        settings = replace(settings, strategy=resolved_strategy)
    account_state_trace_rows: list[dict[str, Any]] = []
    policy_decision_rows: list[dict[str, Any]] = []
    policy_decision_sequence = 0
    current_policy_decision_id = ""

    def build_account_state_trace_row(
        *,
        bar_index: int,
        decision_time: Any,
        valuation_time: Any,
        session_id: int,
        breach_reason: str = "",
    ) -> dict[str, Any]:
        """Snapshot account state at the same boundary as a saved equity mark.

        Args:
            bar_index: Position of the current bar in the backtest input.
            decision_time: Timestamp at which policy decisions are made.
            valuation_time: Timestamp used to value account equity.
            session_id: Identifier of the active trading session.
            breach_reason: Optional reason associated with a risk breach.

        Returns:
            Account-state fields for this pre-action valuation boundary.
        """
        return {
            "backtest_bar_index": int(bar_index),
            **account_state_snapshot(
                state.account,
                valuation_time=valuation_time,
                decision_time=decision_time,
                session_id=session_id,
                state_phase="pre_action_valuation",
                daily_loss_limit_usd=guardrails.daily_limit_for(state.account),
                soft_daily_loss_limit_usd=guardrails.soft_daily_limit_for(state.account),
                max_loss_limit_usd=guardrails.max_loss_limit_for(state.account),
                max_loss_floor_equity=guardrails.max_loss_floor_for(state.account),
                max_drawdown_mode=guardrails.max_drawdown_mode,
                max_drawdown_from_reference_usd=guardrails.max_drawdown_from_reference(
                    state.account
                ),
                soft_max_loss_limit_usd=guardrails.soft_max_loss_limit_for(state.account),
                trailing_drawdown_limit_usd=float(guardrails.trailing_dd_limit),
                soft_trailing_drawdown_limit_usd=float(guardrails.soft_trailing_dd_limit),
                risk_per_trade_limit_usd=guardrails.risk_per_trade_limit_for(state.account),
                position=state.position,
                pending_order=state.pending_entry_order,
                cumulative_payouts=state.cumulative_payouts,
                cycle_count=state.cycle_count,
                breach_reason=breach_reason,
                trade_event_count=len(state.trade_log),
                contract_size=float(settings.contract_size),
            ),
        }

    if setup_action_schema is None:
        observation_features = select_obs_columns(features)
    else:
        observation_features = attach_reachable_r(
            select_obs_columns(features, getattr(resolved_strategy, "raw_columns", ())),
            bars,
            features,
        )
    observation_columns = list(observation_features.columns)
    observation_feature_array: np.ndarray[Any, Any] | None = None
    session_start_indices: np.ndarray[Any, Any] | None = None
    if setup_action_schema is not None or resolved_observation_schema is not None:
        observation_feature_array = observation_features.to_numpy(dtype=np.float32, copy=True)
        session_start_indices = np.arange(len(bars), dtype=np.int64)
        if "session_id" in bars.columns and len(bars):
            session_boundaries = (
                bars["session_id"].ne(bars["session_id"].shift()).fillna(True).to_numpy(dtype=bool)
            )
            session_start_indices = np.maximum.accumulate(
                np.where(session_boundaries, np.arange(len(bars), dtype=np.int64), 0)
            )
    m1_columns, htf_columns = split_obs_columns(observation_columns)
    missing_regime = [name for name in REGIME_FEATURES if name not in observation_columns]
    if regime_observation and missing_regime:
        raise ValueError(f"regime observation is missing required D1 features: {missing_regime}")
    regime_columns = np.asarray(
        [
            observation_columns.index(name)
            for name in REGIME_FEATURES
            if name in observation_columns
        ],
        dtype=np.int64,
    )
    resolved_mtf_windows = dict(DEFAULT_HTF_WINDOWS)
    if mtf_windows:
        for key, value in mtf_windows.items():
            name = str(key).lower()
            if name not in DEFAULT_HTF_WINDOWS:
                raise ValueError(f"unsupported MTF observation window: {key}")
            if isinstance(value, bool) or int(value) != value or int(value) < 1:
                raise ValueError(f"MTF observation window for {key} must be a positive integer")
            resolved_mtf_windows[name] = int(value)

    bar_times = pd.DatetimeIndex(bars.index)
    bar_times_array = bar_times.to_numpy(dtype="datetime64[ns]")
    mtf_starts = (
        {
            key: timeframe_starts(
                bar_times,
                key.upper(),
                scheduled_session_closes,
                session_start,
            )
            for key, _, _ in HTF_BRANCHES
        }
        if mtf_observation
        else {}
    )
    ny_gap_guard = _ny_gap_guard_mask(bars)
    bar_duration = _bar_duration(bar_times)
    feat_array: np.ndarray[Any, Any] = features.values.astype(np.float32)
    feat_array = np.nan_to_num(feat_array, nan=0.0).astype(np.float32)
    n_bars = len(bars)
    execution_rng = np.random.default_rng(int(execution_seed))
    ny_indices = (
        np.flatnonzero(bars["session"].eq("ny").to_numpy())
        if "session" in bars.columns
        else np.arange(n_bars, dtype=int)
    )
    ny_position_by_index = {int(index): position for position, index in enumerate(ny_indices)}
    if (tick_execution_required or randomized_fill_latency_ms > 0) and tickbook is None:
        raise TickExecutionUnavailable("tick-only execution requires a TickBook")

    def policy_observation_at(index: int) -> PolicyObservation:
        """Build the environment's default sequence/account observation for one decision row.

        Args:
            index: Bar index whose preceding data form the observation window.

        Returns:
            Policy observation containing the configured sequence and account channels.
        """
        if setup_action_schema is None and resolved_observation_schema is None:
            return feat_array[index - obs_window : index].copy()

        assert observation_feature_array is not None
        assert session_start_indices is not None
        start = max(0, int(index) - int(obs_window))
        if "session_id" in bars.columns:
            start = max(start, int(session_start_indices[index]))
        raw_sequence = observation_feature_array[start:index].copy()
        if mtf_observation:
            if m1_columns.size:
                raw_sequence = raw_sequence[:, m1_columns]
            else:
                raw_sequence = np.full((raw_sequence.shape[0], 1), np.nan, dtype=np.float32)
        raw_sequence = prepare_observation_feature_channels(
            raw_sequence, include_validity=feature_validity_channels
        )
        sequence, sequence_mask = pad_observation_window(raw_sequence, obs_window)

        position = state.position
        position_direction = float(position.direction) if position is not None else 0.0
        open_pnl = float(state.account.open_pnl) if position is not None else 0.0
        distance_to_stop = 0.0
        if position is not None and position.sl_price is not None:
            distance_to_stop = (
                position.entry_price - position.sl_price
                if position.direction == 1
                else position.sl_price - position.entry_price
            )
        assert resolved_observation_schema is not None
        current_close = float(bars.iloc[index]["close"])
        trailing_dd = float(state.account.trailing_drawdown_pct())
        if resolved_observation_schema.version in (OBSERVATION_SCHEMA_V2, OBSERVATION_SCHEMA_V3):
            position_age_bars = 0.0
            if position is not None and position.entry_timestamp is not None:
                position_age_bars = max(
                    (
                        pd.Timestamp(bar_times_array[index])
                        - pd.Timestamp(str(position.entry_timestamp))
                    ).total_seconds()
                    / 60.0
                    / max(float(bar_duration.total_seconds() / 60.0), 1.0),
                    0.0,
                )
            account = account_state_v2(
                equity=float(state.account.equity),
                initial_balance=float(initial_balance),
                position_direction=position_direction,
                open_pnl=open_pnl,
                planned_risk_usd=(
                    float(position.planned_risk_usd or 0.0) if position is not None else 0.0
                ),
                trailing_drawdown_pct=trailing_dd,
                trailing_drawdown_limit=float(guardrails.trailing_dd_limit),
                daily_loss=float(state.account.canonical_daily_loss()),
                daily_loss_limit=float(guardrails.daily_limit_for(state.account)),
                loss_from_initial=float(state.account.loss_from_initial()),
                max_loss_limit=float(guardrails.max_loss_limit_for(state.account)),
                risk_per_trade_limit=float(guardrails.risk_per_trade_limit_for(state.account)),
                current_price=current_close,
                entry_price=float(position.entry_price) if position is not None else 0.0,
                initial_sl_price=(
                    position.sl_initial_price
                    if position is not None and position.sl_initial_price is not None
                    else position.sl_price
                    if position is not None
                    else None
                ),
                active_sl_price=position.sl_price if position is not None else None,
                remaining_size=float(position.size) if position is not None else 0.0,
                initial_size=(
                    float(position.initial_size or position.size) if position is not None else 0.0
                ),
                position_age_bars=position_age_bars,
                position_age_scale_bars=float(observation_age_scale_bars),
                tp_hit_mask=int(position.tp_hit_mask) if position is not None else 0,
                tp_prices=(
                    (position.tp1_price, position.tp2_price, position.tp3_price)
                    if position is not None
                    else (None, None, None)
                ),
                sl_mode=position.sl_mode if position is not None else "fixed",
                tp_mode=(
                    "fixed"
                    if position is None or position.tp_mode in {"", "rr"}
                    else position.tp_mode
                ),
                exit_mode=(
                    position.exit_mode
                    if position is not None and position.exit_mode
                    else "structural"
                ),
                entry_state=(
                    entry_machine.state
                    if resolved_observation_schema.entry_state_visibility
                    and entry_machine is not None
                    else None
                ),
            )
        elif resolved_observation_schema.version == OBSERVATION_SCHEMA_V1 and normalize_account:
            account = normalized_account_vector(
                equity=float(state.account.equity),
                initial_balance=float(initial_balance),
                pos_dir=position_direction,
                open_pnl=open_pnl,
                dist_to_sl=float(distance_to_stop),
                trailing_dd=trailing_dd,
                close=current_close,
                entry_state=(
                    entry_machine.state
                    if resolved_observation_schema.entry_state_visibility
                    and entry_machine is not None
                    else None
                ),
            )
        else:
            unrealised_r = (
                (open_pnl / state.account.equity * 100.0) if state.account.equity > 0.0 else 0.0
            )
            account = np.asarray(
                [
                    state.account.equity,
                    position_direction,
                    open_pnl,
                    unrealised_r,
                    distance_to_stop,
                    trailing_dd,
                    *(
                        entry_state_one_hot(entry_machine.state)
                        if resolved_observation_schema.entry_state_visibility
                        and entry_machine is not None
                        else ()
                    ),
                ],
                dtype=np.float32,
            )
        observation: dict[str, np.ndarray[Any, Any]] = {
            "seq": sequence,
            "seq_mask": sequence_mask,
            "account": account,
        }
        if regime_observation:
            raw_regime = observation_feature_array[index, regime_columns]
            observation["regime_mask"] = np.isfinite(raw_regime).astype(np.float32)
            observation["regime"] = np.nan_to_num(raw_regime, nan=0.0, posinf=0.0, neginf=0.0)
        if mtf_observation:
            for key, _, seq_key in HTF_BRANCHES:
                window, mask = closed_window(
                    observation_feature_array,
                    mtf_starts[key],
                    int(index),
                    resolved_mtf_windows[key],
                    columns=htf_columns[key],
                    include_validity=feature_validity_channels,
                )
                observation[seq_key] = window
                observation[f"mask_{key}"] = mask
        if vae is not None:
            import torch

            latent_dim = int(vae.encoder.latent_dim)
            seq_len = int(vae.encoder.seq_len)
            n_features = int(vae.encoder.n_features)
            pre_ny_sequence: np.ndarray[Any, Any] | None = None
            if pre_ny_by_date:
                day_key = pd.Timestamp(bar_times[index]).date()
                pre_ny_sequence = pre_ny_by_date.get(day_key)
            elif pre_ny_data is not None and len(pre_ny_data) > 0:
                row_index = min(int(index), len(pre_ny_data) - 1)
                flattened = sanitize_observation_values(
                    np.asarray(pre_ny_data.iloc[row_index].values, dtype=np.float32)
                )
                if flattened.size == seq_len * n_features:
                    pre_ny_sequence = flattened.reshape(seq_len, n_features)
                elif flattened.ndim == 2:
                    pre_ny_sequence = flattened.astype(np.float32, copy=False)

            if pre_ny_sequence is None:
                latent = np.zeros(latent_dim, dtype=np.float32)
            else:
                pre_ny_sequence = sanitize_observation_values(pre_ny_sequence)
                if pre_ny_sequence.shape != (seq_len, n_features):
                    fixed = np.zeros((seq_len, n_features), dtype=np.float32)
                    if pre_ny_sequence.ndim != 2:
                        if pre_ny_sequence.ndim != 1:
                            raise ValueError("pre-NY VAE sequence must be one- or two-dimensional")
                        pre_ny_sequence = pre_ny_sequence.reshape(-1, n_features)
                    kept_rows = min(seq_len, pre_ny_sequence.shape[0])
                    kept_features = min(n_features, pre_ny_sequence.shape[1])
                    if kept_rows > 0 and kept_features > 0:
                        fixed[-kept_rows:, :kept_features] = pre_ny_sequence[
                            -kept_rows:, :kept_features
                        ]
                    pre_ny_sequence = fixed
                tensor = torch.from_numpy(pre_ny_sequence).unsqueeze(0).float()
                device = next(vae.parameters()).device
                with torch.no_grad():
                    mu, _ = vae.encode(tensor.to(device))
                latent = mu.detach().cpu().numpy().astype(np.float32).reshape(-1)
            observation["vae_z"] = latent
        if setup_action_schema is not None:
            observation["trade_setup_mask"] = trade_setup_candidate_mask(
                features.iloc[index]
            ).copy()
        return observation

    def policy_action_at(
        index: int, observation: PolicyObservation
    ) -> tuple[
        int,
        TradeSetupCandidate | None,
        TradeSetupExecutionChoice | None,
        float | None,
        TradeSetupGeometryChoice | None,
    ]:
        """Resolve and record one policy decision at the selected bar.

        Args:
            index: Current decision bar index.
            observation: Observation passed to the policy.

        Returns:
            Signal, candidate, execution choice, risk fraction, and geometry choice.
        """
        nonlocal policy_decision_sequence, current_policy_decision_id, entry_trigger_pending
        (
            action,
            candidate,
            eligible,
            execution_choice,
            selected_risk_frac,
            geometry_choice,
        ) = _policy_action(
            policy,
            observation,
            feature_row=features.iloc[index],
            trade_setup_schema=setup_action_schema,
            max_limit_offset_atr=float(limit_order_max_offset_atr),
            max_limit_ttl_bars=int(limit_order_max_ttl_bars),
            policy_risk_frac_range=resolved_policy_risk_frac_range,
            allow_ema_exit=bool(allow_ema_exit),
            default_sl_mode=(
                _default_sl_mode(state.position, features.iloc[index])
                if setup_action_schema is not None and setup_action_schema.has_sl_mode
                else settings.sl_mode
            ),
            default_tp_mode=settings.tp_mode,
            sl_mode_defer_threshold=settings.sl_mode_defer_threshold,
            tp_mode_defer_threshold=settings.tp_mode_defer_threshold,
        )
        if entry_machine is not None and setup_action_schema is None:
            if entry_machine.state in {"FLAT", "CANDIDATE", "IN_POSITION"}:
                action = 0
            elif action in (-1, 1):
                entry_candidate = entry_machine.request_trigger()
                if entry_candidate is None:
                    action = 0
                else:
                    action = int(entry_candidate.direction)
                    entry_trigger_pending = True
            else:
                action = 0
        policy_decision_sequence += 1
        current_policy_decision_id = f"bt:d{policy_decision_sequence}"
        setup_mask = (
            np.asarray(observation.get("trade_setup_mask", []), dtype=np.float32).reshape(-1)
            if isinstance(observation, Mapping)
            else np.asarray([], dtype=np.float32)
        )
        setup_identity = None
        if candidate is not None and candidate.candidate_id != NO_TRADE_ID and eligible:
            identities = trade_setup_candidate_event_identities(
                features.iloc[index], candidate_ids=(candidate.candidate_id,)
            )
            setup_identity = identities[0] if identities else None
        policy_decision_rows.append(
            {
                "schema_version": "event_backtest_policy_decision.v2",
                "decision_id": current_policy_decision_id,
                "decision_index": int(index),
                "decision_bar_time": pd.Timestamp(bar_times[index]),
                "decision_time": pd.Timestamp(bar_times[index]) + bar_duration,
                "session_id": int(bars.iloc[index].get("session_id", 0)),
                "action": int(action),
                "trade_setup_candidate_id": (
                    None if candidate is None else int(candidate.candidate_id)
                ),
                "trade_setup_idea": None if candidate is None else candidate.idea,
                "trade_setup_timeframe": None if candidate is None else candidate.setup_timeframe,
                "trade_setup_direction": None if candidate is None else candidate.direction,
                **trade_setup_event_identity_record(setup_identity),
                "trade_setup_eligible": eligible,
                "eligibility_status": (
                    "not_applicable"
                    if eligible is None
                    else "eligible"
                    if eligible
                    else "ineligible"
                ),
                "eligible_candidate_count": int(np.count_nonzero(setup_mask > 0.0)),
                "eligible_trade_setup_ids": (
                    np.flatnonzero(setup_mask > 0.0).astype(int).tolist()
                    if setup_action_schema is not None
                    else None
                ),
                "execution_type": (
                    "market" if execution_choice is None else execution_choice.order_type
                ),
                "limit_offset_atr": (
                    None if execution_choice is None else execution_choice.limit_offset_atr
                ),
                "limit_ttl_bars": None if execution_choice is None else execution_choice.ttl_bars,
                "selected_risk_frac": selected_risk_frac,
                "selected_geometry_action": _geometry_action_record(geometry_choice),
                "position_direction_at_decision": (
                    0 if state.position is None else int(state.position.direction)
                ),
                "position_id_at_decision": (
                    None if state.position is None else state.position.position_id
                ),
                "pending_order_id_at_decision": (
                    None
                    if state.pending_entry_order is None
                    else state.pending_entry_order.get("order_id")
                ),
            }
        )
        if candidate is not None and candidate.candidate_id != NO_TRADE_ID and not eligible:
            state.trade_log.append(
                {
                    "type": "reject",
                    "decision_id": current_policy_decision_id,
                    "reason": "trade_setup_inactive",
                    "trade_setup_candidate_id": candidate.candidate_id,
                    "idea": candidate.idea,
                    "setup_timeframe": candidate.setup_timeframe,
                    **trade_setup_event_identity_record(setup_identity),
                    "direction": candidate.direction,
                    "decision_bar": index,
                    "decision_bar_time": bar_times[index],
                    "decision_time": bar_times[index] + bar_duration,
                }
            )
        return action, candidate, execution_choice, selected_risk_frac, geometry_choice

    def selected_setup_context_for_decision(decision_id: str) -> dict[str, Any]:
        """Copy the selected setup lineage from its decision row to rejects.

        Args:
            decision_id: Stable identifier of the policy decision being rejected.

        Returns:
            Available candidate and source-event lineage fields for that decision.
        """
        record = (
            policy_decision_rows[-1]
            if policy_decision_rows
            and str(policy_decision_rows[-1].get("decision_id", "")) == decision_id
            else {}
        )
        return {
            key: record[key]
            for key in (
                "trade_setup_candidate_id",
                "trade_setup_event_identity_version",
                "trade_setup_source_event_id",
                "trade_setup_source_event_identity_status",
                "trade_setup_source_event_times_ns",
            )
            if key in record and record[key] is not None
        }

    for i in range(obs_window, n_bars):
        if entry_machine is not None and i > obs_window:
            if entry_trigger_pending:
                if state.position is not None:
                    entry_machine.mark_position_opened()
                    entry_trigger_pending = False
                elif state.pending_entry_order is None:
                    entry_machine.trigger_refused += 1
                    entry_trigger_pending = False
            if (
                setup_action_schema is not None
                and state.position is not None
                and entry_machine.state != "IN_POSITION"
            ):
                entry_machine.mark_position_opened()
            prior_bar = bars.iloc[i - 1]
            prior_feature = features.iloc[i - 1]
            prior_session = int(prior_bar.get("session_id", 0))
            try:
                manipulation_end = float(prior_feature.get("po3_manipulation_end", 0.0))
            except (TypeError, ValueError):
                manipulation_end = 0.0
            if np.isfinite(manipulation_end) and manipulation_end > 0.0:
                confirmed_manipulation_sessions.add(prior_session)
            if getattr(resolved_strategy, "name", "") == "po3_ifvg":
                setattr(
                    resolved_strategy,
                    "_session_manip_confirmed",
                    prior_session in confirmed_manipulation_sessions,
                )
            evidence = build_entry_evidence(
                strategy=resolved_strategy,
                feature_row=prior_feature,
                bar=i - 1,
                candidate=(
                    entry_machine.candidate
                    if getattr(resolved_strategy, "name", "") == "baseline"
                    else None
                ),
                bars_index=bars.index,
                state_machine_enabled=True,
            )
            entry_machine.observe(evidence)
            if entry_machine.state == "IN_POSITION" and state.position is None:
                entry_machine.mark_closed()
        row = bars.iloc[i]
        bar_time = bar_times[i]
        session = int(row["session_id"]) if "session_id" in row.index else 0
        state.session_set.add(session)
        is_ny = "session" not in row.index or str(row["session"]) == "ny"

        if state.prev_session is None:
            state.prev_session = session
        elif session != state.prev_session:
            state.account.reset_daily()
            state.prev_session = session

        bq = _bar_quote(row, cost_model)
        if state.position is not None:
            broker.mark_to_market(state.account, state.position, bq)

        bar_end = pd.Timestamp(bar_time) + bar_duration
        entry_time = (
            None
            if state.position is None or state.position.entry_timestamp is None
            else pd.Timestamp(cast(Any, state.position.entry_timestamp))
        )
        position_active_in_bar = entry_time is None or entry_time < bar_end
        full_bar_available_after_entry = entry_time is None or entry_time <= pd.Timestamp(bar_time)

        if i + 1 < n_bars:
            fill_instant = bar_times[i + 1]
            fill_row = bars.iloc[i + 1]
        else:
            fill_instant = bar_time
            fill_row = row

        execution_event: tuple[tuple[float, float], pd.Timestamp, str, dict[str, Any]] | None = None

        def resolve_bar_execution() -> tuple[
            tuple[float, float], pd.Timestamp, str, dict[str, Any]
        ]:
            """Resolve and cache the execution quote for this bar's fill time.

            Returns:
                Mapping from ``str`` keys to ``Any]`` values.
            """
            nonlocal execution_event
            if execution_event is None:
                execution_event = _fill_quote_event(
                    fill_instant,
                    fill_row,
                    cost_model,
                    tickbook,
                    rng=(
                        event_keyed_execution_rng(
                            int(execution_seed), f"bar_fill:{pd.Timestamp(fill_instant).value}"
                        )
                        if randomized_fill_latency_ms > 0
                        else execution_rng
                    ),
                    randomized_fill_latency_ms=randomized_fill_latency_ms,
                    max_tick_quote_wait_ms=max_tick_quote_wait_ms,
                    tick_execution_required=tick_execution_required,
                )
                state.current_execution_meta = execution_event[3]
            return execution_event

        if randomized_fill_latency_ms == 0 and not tick_execution_required:
            resolve_bar_execution()

        breach_event_count = len(state.breach_events)
        last_ny = process_protective_and_account_events(
            state,
            settings,
            broker,
            guardrails,
            bars,
            row,
            feature_row=features.iloc[i],
            i=i,
            bar_time=bar_time,
            bar_duration=bar_duration,
            session=session,
            is_ny=is_ny,
            bar_quote=bq,
            entry_time=entry_time,
            position_active_in_bar=position_active_in_bar,
            full_bar_available_after_entry=full_bar_available_after_entry,
            execution_rng=execution_rng,
            resolve_bar_execution=resolve_bar_execution,
            fill_quote_event=_fill_quote_event,
            sl_tp_fill_quote=_sl_tp_fill_quote,
            bar_spread_price_units=_bar_spread_price_units,
            is_last_ny_bar=_is_last_ny_bar,
            eod_guard_due=bool(ny_gap_guard[i]),
        )

        if repeated_payout:
            new_breach_events = state.breach_events[breach_event_count:]
            if new_breach_events:
                # Multiple guardrails may report the same terminal bar; one
                # account cycle can fail only once.
                record_repeated_cycle_failure(state, new_breach_events[0])
                state.year_failed = True
            process_repeated_payout(
                state,
                resolved_trading_policy,
                bar_time,
                max_drawdown_mode=guardrails.max_drawdown_mode,
            )

        state.equity_curve.append(state.account.equity)
        state.equity_times.append(pd.Timestamp(bar_time) + bar_duration)
        state.total_economic_value_curve.append(state.account.equity + state.cumulative_payouts)
        current_breach_events = state.breach_events[breach_event_count:]
        account_state_trace_rows.append(
            build_account_state_trace_row(
                bar_index=i,
                decision_time=bar_time,
                valuation_time=pd.Timestamp(bar_time) + bar_duration,
                session_id=session,
                breach_reason=(
                    str(current_breach_events[0].get("reason", "")) if current_breach_events else ""
                ),
            )
        )

        pending_order = state.pending_entry_order
        action_after_limit_cancel: (
            tuple[
                int,
                TradeSetupCandidate | None,
                TradeSetupExecutionChoice | None,
                float | None,
                TradeSetupGeometryChoice | None,
            ]
            | None
        ) = None
        if pending_order is not None:
            obs = policy_observation_at(i)
            (
                action,
                pending_action_setup,
                execution_choice,
                selected_risk_frac,
                geometry_choice,
            ) = policy_action_at(i, obs)
            if pending_order.get("order_type") == "limit":
                bar_end = pd.Timestamp(bar_time) + bar_duration
                block_reason = None
                if settings.block_overnight and last_ny:
                    block_reason = "session_end_before_limit_fill"
                elif settings.block_overnight and int(pending_order["session_id"]) != session:
                    block_reason = "session_changed_before_limit_fill"
                elif session in state.breached_sessions or state.year_failed:
                    block_reason = "account_guardrail_before_limit_fill"
                elif guardrails.check_soft_daily(
                    state.account
                ) or guardrails.check_soft_trailing_dd(state.account):
                    block_reason = "soft_guardrail_before_limit_fill"
                elif pending_order.get("trade_setup_candidate_id") is not None:
                    setup_is_current, setup_reason = trade_setup_event_is_current(
                        pending_order.get("trade_setup_event_identity"), features.iloc[i]
                    )
                    if not setup_is_current:
                        block_reason = setup_reason
                fill_quote = pending_order.get("fill_quote")
                fill_due = fill_quote is not None and pd.Timestamp(fill_quote.tick_time) <= bar_end
                if block_reason is not None:
                    state.pending_entry_order = None
                    state.trade_log.append(
                        {
                            "type": "order_cancel",
                            "decision_id": pending_order.get("decision_id"),
                            "order_id": pending_order["order_id"],
                            "order_type": "limit",
                            "reason": block_reason,
                            "trade_setup_candidate_id": pending_order.get(
                                "trade_setup_candidate_id"
                            ),
                            **trade_setup_event_identity_record(
                                pending_order.get("trade_setup_event_identity")
                            ),
                            "decision_bar_time": pending_order["decision_bar_time"],
                            "order_submission_time": pending_order["order_submission_time"],
                            "expiry_time": pending_order["expiry_time"],
                            "limit_price": pending_order["limit_price"],
                            "time": bar_time,
                        }
                    )
                    if str(block_reason).startswith("source_setup_"):
                        action_after_limit_cancel = (
                            action,
                            pending_action_setup,
                            execution_choice,
                            selected_risk_frac,
                            geometry_choice,
                        )
                    else:
                        continue
                if block_reason is None and fill_quote is not None and fill_due:
                    state.pending_entry_order = None
                    fill_metadata = {
                        "order_type": "limit",
                        "order_id": pending_order["order_id"],
                        "limit_price": float(pending_order["limit_price"]),
                        "order_submission_time": pd.Timestamp(fill_quote.order_time),
                        "execution_order_time": pd.Timestamp(fill_quote.order_time),
                        "execution_arrival_time": pd.Timestamp(fill_quote.arrival_time),
                        "execution_latency_ns": int(fill_quote.latency_ns),
                        "fill_time": pd.Timestamp(fill_quote.tick_time),
                        "fill_quote_source": "tick",
                    }
                    execution_event = (
                        (float(fill_quote.bid), float(fill_quote.ask)),
                        pd.Timestamp(fill_quote.tick_time),
                        "tick",
                        fill_metadata,
                    )
                    state.current_execution_meta = fill_metadata
                    limit_fill_event = {
                        "type": "order_fill",
                        "decision_id": pending_order.get("decision_id"),
                        "order_id": pending_order["order_id"],
                        "order_type": "limit",
                        "direction": int(pending_order["action"]),
                        "trade_setup_candidate_id": pending_order.get("trade_setup_candidate_id"),
                        **trade_setup_event_identity_record(
                            pending_order.get("trade_setup_event_identity")
                        ),
                        "limit_price": float(pending_order["limit_price"]),
                        "bid": float(fill_quote.bid),
                        "ask": float(fill_quote.ask),
                        "price": float(
                            fill_quote.ask if int(pending_order["action"]) == 1 else fill_quote.bid
                        ),
                        "time": pd.Timestamp(fill_quote.tick_time),
                        "order_submission_time": pd.Timestamp(fill_quote.order_time),
                    }
                    position_sequence_before = state.position_sequence
                    apply_policy_action(
                        state,
                        settings,
                        broker,
                        guardrails,
                        bars,
                        features,
                        i=i,
                        bar_time=pd.Timestamp(pending_order["order_submission_time"]),
                        session=session,
                        action=int(pending_order["action"]),
                        selected_risk_frac=float(
                            pending_order.get("risk_frac", settings.risk_frac)
                        ),
                        resolve_bar_execution=resolve_bar_execution,
                        is_last_ny_bar=_is_last_ny_bar,
                        feature_index=int(pending_order["decision_index"]),
                        decision_bar_time=pd.Timestamp(pending_order["decision_bar_time"]),
                        order_submission_time=pd.Timestamp(pending_order["order_submission_time"]),
                        order_id=str(pending_order["order_id"]),
                        decision_id=pending_order.get("decision_id"),
                        trade_setup=(
                            trade_setup_candidate(int(pending_order["trade_setup_candidate_id"]))
                            if pending_order.get("trade_setup_candidate_id") is not None
                            else None
                        ),
                        trade_setup_event_identity=pending_order.get("trade_setup_event_identity"),
                        selected_geometry=pending_order.get("geometry_choice"),
                        entry_reference_price=float(pending_order["limit_price"]),
                    )
                    if state.position_sequence == position_sequence_before:
                        state.trade_log.append(
                            {
                                "type": "order_cancel",
                                "decision_id": pending_order.get("decision_id"),
                                "order_id": pending_order["order_id"],
                                "order_type": "limit",
                                "reason": "entry_rejected_at_limit_fill",
                                "trade_setup_candidate_id": pending_order.get(
                                    "trade_setup_candidate_id"
                                ),
                                **trade_setup_event_identity_record(
                                    pending_order.get("trade_setup_event_identity")
                                ),
                                "decision_bar_time": pending_order["decision_bar_time"],
                                "order_submission_time": pending_order["order_submission_time"],
                                "expiry_time": pending_order["expiry_time"],
                                "limit_price": pending_order["limit_price"],
                                "trigger_quote_time": pd.Timestamp(fill_quote.tick_time),
                                "trigger_quote_bid": float(fill_quote.bid),
                                "trigger_quote_ask": float(fill_quote.ask),
                                "trigger_quote_price": float(
                                    fill_quote.ask
                                    if int(pending_order["action"]) == 1
                                    else fill_quote.bid
                                ),
                                "time": pd.Timestamp(fill_quote.tick_time),
                            }
                        )
                    else:
                        open_index = next(
                            (
                                index
                                for index, event in enumerate(state.trade_log)
                                if event.get("type") == "open"
                                and event.get("order_id") == pending_order["order_id"]
                            ),
                            None,
                        )
                        if open_index is None:
                            raise RuntimeError(
                                "limit fill opened without a matching position event"
                            )
                        state.trade_log.insert(open_index, limit_fill_event)
                    continue
                elif block_reason is None and bar_end >= pd.Timestamp(pending_order["expiry_time"]):
                    state.pending_entry_order = None
                    state.trade_log.append(
                        {
                            "type": "order_cancel",
                            "decision_id": pending_order.get("decision_id"),
                            "order_id": pending_order["order_id"],
                            "order_type": "limit",
                            "reason": "limit_ttl_expired",
                            "trade_setup_candidate_id": pending_order.get(
                                "trade_setup_candidate_id"
                            ),
                            **trade_setup_event_identity_record(
                                pending_order.get("trade_setup_event_identity")
                            ),
                            "decision_bar_time": pending_order["decision_bar_time"],
                            "order_submission_time": pending_order["order_submission_time"],
                            "expiry_time": pending_order["expiry_time"],
                            "limit_price": pending_order["limit_price"],
                            "time": pd.Timestamp(pending_order["expiry_time"]),
                        }
                    )
                    action_after_limit_cancel = (
                        action,
                        pending_action_setup,
                        execution_choice,
                        selected_risk_frac,
                        geometry_choice,
                    )
                elif block_reason is None:
                    if action in (1, -1):
                        state.trade_log.append(
                            {
                                "type": "reject",
                                "decision_id": current_policy_decision_id,
                                **selected_setup_context_for_decision(current_policy_decision_id),
                                "reason": "entry_pending",
                                "decision_bar": i,
                                "decision_bar_time": bar_time,
                                "decision_time": bar_time + bar_duration,
                                "direction": action,
                            }
                        )
                    continue
            else:
                # Fixed-delay market orders retain the existing scheduled-fill contract.
                action = int(action)
                due_fill_index = i + 1
                block_reason = None
                if settings.block_overnight and int(pending_order["session_id"]) != session:
                    block_reason = "session_changed_before_scheduled_fill"
                elif session in state.breached_sessions or state.year_failed:
                    block_reason = "account_guardrail_before_scheduled_fill"
                elif due_fill_index > int(pending_order["fill_index"]):
                    block_reason = "scheduled_fill_bar_skipped"

                if block_reason is not None:
                    state.pending_entry_order = None
                    state.trade_log.append(
                        {
                            "type": "order_cancel",
                            "decision_id": pending_order.get("decision_id"),
                            "order_id": pending_order["order_id"],
                            "reason": block_reason,
                            "trade_setup_candidate_id": pending_order.get(
                                "trade_setup_candidate_id"
                            ),
                            **trade_setup_event_identity_record(
                                pending_order.get("trade_setup_event_identity")
                            ),
                            "decision_bar_time": pending_order["decision_bar_time"],
                            "order_submission_time": pending_order["order_submission_time"],
                            "scheduled_fill_time": pending_order["scheduled_fill_time"],
                            "time": bar_time,
                        }
                    )
                elif due_fill_index == int(pending_order["fill_index"]):
                    if action in (1, -1):
                        state.trade_log.append(
                            {
                                "type": "reject",
                                "decision_id": current_policy_decision_id,
                                **selected_setup_context_for_decision(current_policy_decision_id),
                                "reason": "entry_pending",
                                "decision_bar": i,
                                "decision_bar_time": bar_time,
                                "decision_time": bar_time + bar_duration,
                                "direction": action,
                            }
                        )
                    state.pending_entry_order = None
                    position_sequence_before = state.position_sequence
                    apply_policy_action(
                        state,
                        settings,
                        broker,
                        guardrails,
                        bars,
                        features,
                        i=i,
                        bar_time=pd.Timestamp(pending_order["order_submission_time"]),
                        session=session,
                        action=int(pending_order["action"]),
                        selected_risk_frac=float(
                            pending_order.get("risk_frac", settings.risk_frac)
                        ),
                        resolve_bar_execution=resolve_bar_execution,
                        is_last_ny_bar=_is_last_ny_bar,
                        feature_index=int(pending_order["decision_index"]),
                        decision_bar_time=pd.Timestamp(pending_order["decision_bar_time"]),
                        order_submission_time=pd.Timestamp(pending_order["order_submission_time"]),
                        order_id=str(pending_order["order_id"]),
                        decision_id=pending_order.get("decision_id"),
                        trade_setup=(
                            trade_setup_candidate(int(pending_order["trade_setup_candidate_id"]))
                            if pending_order.get("trade_setup_candidate_id") is not None
                            else None
                        ),
                        trade_setup_event_identity=pending_order.get("trade_setup_event_identity"),
                        selected_geometry=pending_order.get("geometry_choice"),
                    )
                    if state.position_sequence == position_sequence_before:
                        state.trade_log.append(
                            {
                                "type": "order_cancel",
                                "decision_id": pending_order.get("decision_id"),
                                "order_id": pending_order["order_id"],
                                "reason": "entry_rejected_at_scheduled_fill",
                                "trade_setup_candidate_id": pending_order.get(
                                    "trade_setup_candidate_id"
                                ),
                                **trade_setup_event_identity_record(
                                    pending_order.get("trade_setup_event_identity")
                                ),
                                "decision_bar_time": pending_order["decision_bar_time"],
                                "order_submission_time": pending_order["order_submission_time"],
                                "scheduled_fill_time": pending_order["scheduled_fill_time"],
                                "time": bar_time,
                            }
                        )
                elif action in (1, -1):
                    state.trade_log.append(
                        {
                            "type": "reject",
                            "decision_id": current_policy_decision_id,
                            **selected_setup_context_for_decision(current_policy_decision_id),
                            "reason": "entry_pending",
                            "decision_bar": i,
                            "decision_bar_time": bar_time,
                            "decision_time": bar_time + bar_duration,
                            "direction": action,
                        }
                    )
                elif action == settings.exit_action and state.position is not None:
                    apply_policy_action(
                        state,
                        settings,
                        broker,
                        guardrails,
                        bars,
                        features,
                        i=i,
                        bar_time=bar_time,
                        session=session,
                        action=action,
                        resolve_bar_execution=resolve_bar_execution,
                        is_last_ny_bar=_is_last_ny_bar,
                        order_submission_time=pd.Timestamp(bar_time) + bar_duration,
                    )
                continue

            if action_after_limit_cancel is None:
                continue

        if (
            session in state.breached_sessions
            or state.year_failed
            or not is_ny
            or (block_overnight and last_ny)
        ):
            continue
        if i + 1 >= n_bars:
            continue
        next_bar = bars.iloc[i + 1]
        next_bar_is_ny = "session" not in next_bar.index or str(next_bar["session"]) == "ny"
        entry_fill_on_session_boundary = bool(
            block_overnight and _is_last_ny_bar(bars, i + 1, next_bar_is_ny)
        )

        if action_after_limit_cancel is not None:
            (
                action,
                selected_trade_setup,
                execution_choice,
                selected_risk_frac,
                geometry_choice,
            ) = action_after_limit_cancel
        else:
            obs = policy_observation_at(i)
            (
                action,
                selected_trade_setup,
                execution_choice,
                selected_risk_frac,
                geometry_choice,
            ) = policy_action_at(i, obs)
        feature_row = features.iloc[i]
        setup_identity = None
        if selected_trade_setup is not None:
            identities = trade_setup_candidate_event_identities(
                feature_row, candidate_ids=(selected_trade_setup.candidate_id,)
            )
            setup_identity = identities[0] if identities else None
        if (
            execution_choice is not None
            and execution_choice.order_type == "limit"
            and action in (1, -1)
        ):
            if entry_fill_on_session_boundary:
                state.trade_log.append(
                    {
                        "type": "reject",
                        "decision_id": current_policy_decision_id,
                        "reason": "session_boundary_before_entry_fill",
                        "trade_setup_candidate_id": (
                            None
                            if selected_trade_setup is None
                            else selected_trade_setup.candidate_id
                        ),
                        **trade_setup_event_identity_record(setup_identity),
                        "decision_bar": i,
                        "decision_bar_time": bar_time,
                        "decision_time": bar_time + bar_duration,
                        "direction": action,
                    }
                )
                continue
            if state.position is not None:
                state.trade_log.append(
                    {
                        "type": "reject",
                        "decision_id": current_policy_decision_id,
                        "reason": "limit_entry_requires_flat_account",
                        "trade_setup_candidate_id": (
                            None
                            if selected_trade_setup is None
                            else selected_trade_setup.candidate_id
                        ),
                        **trade_setup_event_identity_record(setup_identity),
                        "decision_bar": i,
                        "decision_bar_time": bar_time,
                        "decision_time": bar_time + bar_duration,
                        "direction": action,
                    }
                )
                continue
            if selected_trade_setup is not None:
                if setup_identity is None or setup_identity.status != "identified":
                    state.trade_log.append(
                        {
                            "type": "reject",
                            "decision_id": current_policy_decision_id,
                            "reason": "limit_entry_source_identity_unavailable",
                            "decision_bar": i,
                            "decision_bar_time": bar_time,
                            "decision_time": bar_time + bar_duration,
                            "trade_setup_candidate_id": selected_trade_setup.candidate_id,
                            **trade_setup_event_identity_record(setup_identity),
                            "direction": action,
                        }
                    )
                    continue
                source_is_current, _ = trade_setup_event_is_current(setup_identity, feature_row)
                if not source_is_current:
                    state.trade_log.append(
                        {
                            "type": "reject",
                            "decision_id": current_policy_decision_id,
                            "reason": "limit_entry_source_setup_unavailable",
                            "decision_bar": i,
                            "decision_bar_time": bar_time,
                            "decision_time": bar_time + bar_duration,
                            "trade_setup_candidate_id": selected_trade_setup.candidate_id,
                            **trade_setup_event_identity_record(setup_identity),
                            "direction": action,
                        }
                    )
                    continue
            atr_value = feature_row.get("atr_5", feature_row.get("atr", np.nan))
            try:
                atr = float(atr_value)
            except (TypeError, ValueError):
                atr = float("nan")
            if not np.isfinite(atr) or atr <= 0.0:
                state.trade_log.append(
                    {
                        "type": "reject",
                        "decision_id": current_policy_decision_id,
                        "reason": "limit_entry_missing_atr",
                        "trade_setup_candidate_id": (
                            None
                            if selected_trade_setup is None
                            else selected_trade_setup.candidate_id
                        ),
                        **trade_setup_event_identity_record(setup_identity),
                        "decision_bar": i,
                        "decision_bar_time": bar_time,
                        "decision_time": bar_time + bar_duration,
                        "direction": action,
                    }
                )
                continue
            if tickbook is None:
                raise TickExecutionUnavailable(
                    "policy-selected limit entries require TickBook quote chronology"
                )
            order_submission_time = pd.Timestamp(bar_time) + bar_duration
            expiry_time = limit_order_expiry(
                order_submission_time,
                execution_choice.ttl_bars,
                bar_duration,
            )
            limit_price = limit_price_from_atr_offset(
                direction=action,
                reference_price=float(row["close"]),
                atr=atr,
                offset_atr=execution_choice.limit_offset_atr,
                point_size=float(cost_model.point_size),
            )
            state.pending_order_sequence += 1
            order_id = f"bt:o{state.pending_order_sequence}"
            assert setup_action_schema is not None
            fill_quote = resolve_tick_limit_execution(
                tickbook,
                action,
                limit_price,
                order_submission_time,
                expiry_time,
                limit_entry_execution_rng(
                    int(execution_seed),
                    order_submission_time,
                    action,
                    limit_price,
                    (None if selected_trade_setup is None else selected_trade_setup.candidate_id),
                ),
                max_latency_ns_exclusive=int(randomized_fill_latency_ms * 1_000_000),
                require_trade_through=bool(limit_order_require_trade_through),
            )
            state.pending_entry_order = {
                "order_id": order_id,
                "order_type": "limit",
                "decision_id": current_policy_decision_id,
                "action": int(action),
                "risk_frac": (
                    settings.risk_frac if selected_risk_frac is None else float(selected_risk_frac)
                ),
                "geometry_choice": geometry_choice,
                "trade_setup_candidate_id": (
                    None if selected_trade_setup is None else selected_trade_setup.candidate_id
                ),
                "trade_setup_event_identity": setup_identity,
                "decision_index": i,
                "decision_bar_time": pd.Timestamp(bar_time),
                "order_submission_time": order_submission_time,
                "expiry_time": expiry_time,
                "limit_price": limit_price,
                "limit_offset_atr": execution_choice.limit_offset_atr,
                "ttl_bars": execution_choice.ttl_bars,
                "fill_quote": fill_quote,
                "session_id": session,
            }
            state.trade_log.append(
                {
                    "type": "order_submit",
                    "decision_id": current_policy_decision_id,
                    "order_id": order_id,
                    "order_type": "limit",
                    "direction": int(action),
                    "trade_setup_candidate_id": (
                        None if selected_trade_setup is None else selected_trade_setup.candidate_id
                    ),
                    "trade_setup_schema_version": setup_action_schema.version,
                    "trade_setup_idea": (
                        None if selected_trade_setup is None else selected_trade_setup.idea
                    ),
                    "trade_setup_timeframe": (
                        None
                        if selected_trade_setup is None
                        else selected_trade_setup.setup_timeframe
                    ),
                    **trade_setup_event_identity_record(setup_identity),
                    "decision_bar": i,
                    "decision_bar_time": pd.Timestamp(bar_time),
                    "decision_time": order_submission_time,
                    "order_submission_time": order_submission_time,
                    "limit_price": limit_price,
                    "selected_geometry_action": _geometry_action_record(geometry_choice),
                    "limit_offset_atr": execution_choice.limit_offset_atr,
                    "ttl_bars": execution_choice.ttl_bars,
                    "expiry_time": expiry_time,
                    "session_id": session,
                }
            )
            continue
        if settings.fill_latency_bars > 0 and action in (1, -1):
            current_ny_pos = ny_position_by_index.get(i)
            target_ny_pos = (
                -1 if current_ny_pos is None else current_ny_pos + 1 + settings.fill_latency_bars
            )
            if target_ny_pos < 0 or target_ny_pos >= len(ny_indices):
                state.trade_log.append(
                    {
                        "type": "reject",
                        "decision_id": current_policy_decision_id,
                        "reason": "terminal_no_fill_bar",
                        "trade_setup_candidate_id": (
                            None
                            if selected_trade_setup is None
                            else selected_trade_setup.candidate_id
                        ),
                        **trade_setup_event_identity_record(setup_identity),
                        "decision_bar": i,
                        "decision_bar_time": bar_time,
                        "decision_time": bar_time + bar_duration,
                        "direction": action,
                    }
                )
                continue
            fill_index = int(ny_indices[target_ny_pos])
            fill_session = (
                int(bars.iloc[fill_index]["session_id"])
                if "session_id" in bars.columns
                else session
            )
            has_same_session_followup = False
            if target_ny_pos + 1 < len(ny_indices):
                next_ny_index = int(ny_indices[target_ny_pos + 1])
                next_session = (
                    int(bars.iloc[next_ny_index]["session_id"])
                    if "session_id" in bars.columns
                    else fill_session
                )
                has_same_session_followup = fill_session == next_session
            crosses_session = fill_session != session
            if block_overnight and (crosses_session or not has_same_session_followup):
                state.trade_log.append(
                    {
                        "type": "reject",
                        "decision_id": current_policy_decision_id,
                        "reason": "overnight_boundary",
                        "trade_setup_candidate_id": (
                            None
                            if selected_trade_setup is None
                            else selected_trade_setup.candidate_id
                        ),
                        **trade_setup_event_identity_record(setup_identity),
                        "decision_bar": i,
                        "decision_bar_time": bar_time,
                        "decision_time": bar_time + bar_duration,
                        "direction": action,
                    }
                )
                continue
            state.pending_order_sequence += 1
            order_id = f"bt:o{state.pending_order_sequence}"
            order_submission_time = pd.Timestamp(bar_time) + bar_duration
            scheduled_fill_time = pd.Timestamp(bar_times[fill_index])
            state.pending_entry_order = {
                "order_id": order_id,
                "decision_id": current_policy_decision_id,
                "action": int(action),
                "risk_frac": (
                    settings.risk_frac if selected_risk_frac is None else float(selected_risk_frac)
                ),
                "geometry_choice": geometry_choice,
                "trade_setup_candidate_id": (
                    None if selected_trade_setup is None else selected_trade_setup.candidate_id
                ),
                "trade_setup_event_identity": setup_identity,
                "decision_index": i,
                "decision_bar_time": pd.Timestamp(bar_time),
                "order_submission_time": order_submission_time,
                "scheduled_fill_time": scheduled_fill_time,
                "fill_index": fill_index,
                "session_id": session,
            }
            state.trade_log.append(
                {
                    "type": "order_submit",
                    "decision_id": current_policy_decision_id,
                    "order_id": order_id,
                    "direction": int(action),
                    **(
                        {}
                        if selected_trade_setup is None
                        else {
                            "trade_setup_candidate_id": selected_trade_setup.candidate_id,
                            "trade_setup_idea": selected_trade_setup.idea,
                            "trade_setup_timeframe": selected_trade_setup.setup_timeframe,
                        }
                    ),
                    **trade_setup_event_identity_record(setup_identity),
                    "decision_bar": i,
                    "decision_bar_time": pd.Timestamp(bar_time),
                    "decision_time": order_submission_time,
                    "order_submission_time": order_submission_time,
                    "scheduled_fill_time": scheduled_fill_time,
                    "selected_geometry_action": _geometry_action_record(geometry_choice),
                    "session_id": session,
                }
            )
            continue
        immediate_order_id: str | None = None
        if (
            action in (1, -1)
            and not entry_fill_on_session_boundary
            and (state.position is None or state.position.direction != int(action))
        ):
            state.pending_order_sequence += 1
            immediate_order_id = f"bt:o{state.pending_order_sequence}"
            state.trade_log.append(
                {
                    "type": "order_submit",
                    "decision_id": current_policy_decision_id,
                    "order_id": immediate_order_id,
                    "order_type": "market",
                    "direction": int(action),
                    "trade_setup_candidate_id": (
                        None if selected_trade_setup is None else selected_trade_setup.candidate_id
                    ),
                    "trade_setup_idea": (
                        None if selected_trade_setup is None else selected_trade_setup.idea
                    ),
                    "trade_setup_timeframe": (
                        None
                        if selected_trade_setup is None
                        else selected_trade_setup.setup_timeframe
                    ),
                    **trade_setup_event_identity_record(setup_identity),
                    "decision_bar": i,
                    "decision_bar_time": pd.Timestamp(bar_time),
                    "decision_time": pd.Timestamp(bar_time) + bar_duration,
                    "order_submission_time": pd.Timestamp(bar_time) + bar_duration,
                    "selected_geometry_action": _geometry_action_record(geometry_choice),
                    "session_id": session,
                }
            )
        apply_policy_action(
            state,
            settings,
            broker,
            guardrails,
            bars,
            features,
            i=i,
            bar_time=bar_time,
            session=session,
            action=action,
            selected_risk_frac=selected_risk_frac,
            resolve_bar_execution=resolve_bar_execution,
            is_last_ny_bar=_is_last_ny_bar,
            order_submission_time=pd.Timestamp(bar_time) + bar_duration,
            trade_setup=selected_trade_setup,
            trade_setup_event_identity=setup_identity,
            selected_geometry=geometry_choice,
            order_id=immediate_order_id,
            decision_id=current_policy_decision_id,
        )

    if state.pending_entry_order is not None:
        pending_order = state.pending_entry_order
        state.trade_log.append(
            {
                "type": "order_cancel",
                "decision_id": pending_order.get("decision_id"),
                "order_id": pending_order["order_id"],
                "order_type": pending_order.get("order_type", "market"),
                "trade_setup_candidate_id": pending_order.get("trade_setup_candidate_id"),
                **trade_setup_event_identity_record(
                    pending_order.get("trade_setup_event_identity")
                ),
                "reason": (
                    "data_end_before_limit_expiry"
                    if pending_order.get("order_type") == "limit"
                    else "data_end_before_scheduled_fill"
                ),
                "decision_bar_time": pending_order["decision_bar_time"],
                "order_submission_time": pending_order["order_submission_time"],
                "scheduled_fill_time": pending_order.get(
                    "scheduled_fill_time", pending_order.get("expiry_time")
                ),
                "limit_price": pending_order.get("limit_price"),
                "time": bar_times[-1] if n_bars else None,
            }
        )
        state.pending_entry_order = None

    liquidate_terminal_position(
        state,
        settings,
        broker,
        bars,
        bar_times,
        bar_duration,
        execution_rng,
        fill_quote_event=_fill_quote_event,
        bar_quote=_bar_quote,
    )

    if repeated_payout:
        process_repeated_payout(
            state,
            resolved_trading_policy,
            bar_times[-1] if n_bars else None,
            max_drawdown_mode=guardrails.max_drawdown_mode,
        )
        if state.equity_curve:
            state.equity_curve[-1] = float(state.account.equity)
            state.total_economic_value_curve[-1] = float(
                state.account.equity + state.cumulative_payouts
            )

    if account_state_trace_rows and n_bars:
        final_trace = account_state_trace_rows[-1]
        account_state_trace_rows[-1] = build_account_state_trace_row(
            bar_index=int(final_trace["backtest_bar_index"]),
            decision_time=bar_times[-1],
            valuation_time=state.equity_times[-1],
            session_id=(int(bars.iloc[-1]["session_id"]) if "session_id" in bars.columns else 0),
            breach_reason=str(final_trace.get("breach_reason", "")),
        )

    trades_df = pd.DataFrame(state.trade_log)
    if "type" not in trades_df.columns:
        trades_df["type"] = pd.Series(dtype=object)
    equity_series = pd.Series(
        state.equity_curve,
        index=pd.DatetimeIndex(state.equity_times, name=bar_times.name),
        dtype=float,
    )
    total_economic_value_series = pd.Series(
        state.total_economic_value_curve,
        index=pd.DatetimeIndex(state.equity_times, name=bar_times.name),
        dtype=float,
    )
    return {
        "equity": equity_series,
        "total_economic_value_curve": total_economic_value_series,
        "equity_valuation_times": pd.DatetimeIndex(state.equity_times, name=bar_times.name),
        "account_state_trace": pd.DataFrame.from_records(account_state_trace_rows),
        "account_state_trace_complete": True,
        "policy_decisions": pd.DataFrame.from_records(policy_decision_rows),
        "policy_decisions_complete": True,
        "entry_state_diagnostics": _entry_state_diagnostics(
            entry_machine, decision_count=len(policy_decision_rows)
        ),
        "entry_state_config": (
            None
            if entry_machine is None
            else {
                "candidate_max_age_bars": int(entry_machine.candidate_max_age_bars),
                "arm_requires_retest": bool(entry_machine.arm_requires_retest),
                "entry_state_visibility": bool(
                    resolved_observation_schema is not None
                    and resolved_observation_schema.entry_state_visibility
                ),
            }
        ),
        "trades": trades_df,
        "account": state.account,
        "breaches": state.breach_log,
        "breach_events": state.breach_events,
        "n_sessions": len(state.session_set),
        "n_breach_sessions": len(state.breached_sessions),
        "n_sessions_with_trades": len(state.sessions_with_trades),
        "n_sessions_skipped": len(state.session_set) - len(state.sessions_with_trades),
        "payout_events": list(state.payout_events),
        "cycle_events": list(state.cycle_events),
        "cumulative_payouts": float(state.cumulative_payouts),
        "cycle_count": int(state.cycle_count),
        "cycle_successes": int(state.cycle_successes),
        "cycle_failures": int(state.cycle_failures),
        "trading_policy_mode": (
            "legacy" if resolved_trading_policy is None else resolved_trading_policy.mode
        ),
        "daily_pnl_basis": state.account.daily_pnl_basis,
        "loss_limit_value_mode": str(guardrails.limit_value_mode),
        "daily_loss_limit_pct": (
            float(guardrails.daily_loss_limit_pct)
            if guardrails.limit_value_mode == "percent_equity"
            else None
        ),
        "daily_loss_limit_usd": float(guardrails.daily_limit_for(state.account)),
        "market_fill_slippage_points": float(resolved_market_slippage),
        "execution_contract": {
            "schema_version": "backtest_execution_contract.v1",
            "cost_model": {
                "spread_points": float(cost_model.spread_points),
                "slippage_points": float(cost_model.slippage_points),
                "commission_per_lot": float(cost_model.commission_per_lot),
                "point_size": float(cost_model.point_size),
                "point_value": float(cost_model.point_value),
            },
            "market_fill": {
                "slippage_points": float(resolved_market_slippage),
                "fill_latency_bars": int(settings.fill_latency_bars),
                "randomized_fill_latency_ms": float(randomized_fill_latency_ms),
                "tick_execution_required": bool(tick_execution_required),
                "max_tick_quote_wait_ms": int(max_tick_quote_wait_ms),
            },
            "limit_order": {
                "policy_selectable": bool(
                    setup_action_schema is not None and setup_action_schema.has_entry_execution
                ),
                "quote_source": (
                    "TickBook"
                    if setup_action_schema is not None and setup_action_schema.has_entry_execution
                    else None
                ),
                "max_offset_atr": float(limit_order_max_offset_atr),
                "max_ttl_bars": int(limit_order_max_ttl_bars),
                "require_trade_through": bool(limit_order_require_trade_through),
                "fill_rule": (
                    "strict_executable_quote_trade_through"
                    if limit_order_require_trade_through
                    else "executable_quote_exact_touch_or_better"
                ),
            },
        },
        "action_schema": None if setup_action_schema is None else setup_action_schema.to_dict(),
        "observation_schema": (
            None if resolved_observation_schema is None else resolved_observation_schema.to_dict()
        ),
        "observation_inputs": (
            None
            if resolved_observation_schema is None
            else {
                "sequence_columns": (
                    [observation_columns[index] for index in m1_columns]
                    if mtf_observation
                    else observation_columns
                ),
                "regime": regime_observation_schema() if regime_observation else None,
                "mtf": {
                    "enabled": bool(mtf_observation),
                    "windows": dict(resolved_mtf_windows) if mtf_observation else {},
                    "timeframes": [key.upper() for key, _, _ in HTF_BRANCHES]
                    if mtf_observation
                    else [],
                    "session_start": str(session_start) if mtf_observation else None,
                    "scheduled_session_closes": dict(scheduled_session_closes or {})
                    if mtf_observation
                    else {},
                    "feature_columns": {
                        key: [observation_columns[index] for index in htf_columns[key]]
                        for key, _, _ in HTF_BRANCHES
                    }
                    if mtf_observation
                    else {},
                },
                "feature_validity_channels": bool(feature_validity_channels),
                "vae": (
                    {
                        "enabled": True,
                        "latent_dim": int(vae.encoder.latent_dim),
                        "sequence_length": int(vae.encoder.seq_len),
                        "feature_count": int(vae.encoder.n_features),
                        "input_source": "per_date" if pre_ny_by_date else "legacy_row_aligned",
                    }
                    if vae is not None
                    else {"enabled": False}
                ),
            }
        ),
        "total_economic_value": float(state.account.equity + state.cumulative_payouts),
        "ending_total_economic_value": float(state.account.equity + state.cumulative_payouts),
    }
