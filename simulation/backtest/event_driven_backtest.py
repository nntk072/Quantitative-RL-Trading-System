"""Event-driven backtester engine.

Fill-price semantics
--------------------
Every order fill uses a ``(bid, ask)`` quote obtained in this priority:

1. **Tick data**: a valid quote at the next bar's open timestamp.
2. **Bar-spread fallback**: the next bar's close quote, timestamped at its
   close rather than at its open.

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
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import pandas as pd

from market_data.loading.ticks import (
    TickExecutionUnavailable,
    event_keyed_execution_rng,
    resolve_tick_execution,
)
from trading import AccountState
from trading.execution import (
    COST_US100,
    Broker,
    CostModel,
    protective_level_fill_quote,
    raw_spread_to_price,
)
from trading.policy.config import TradingPolicyConfig, resolve_trading_policy_mapping
from trading.risk import FTMOGuardrails, RiskDailyPnlBasis

if TYPE_CHECKING:
    from market_data.loading.ticks import TickBook

ActionFn = Callable[[np.ndarray[Any, Any]], int]


def _scalar_policy_action(policy: ActionFn, observation: np.ndarray[Any, Any]) -> int:
    """Return one integer signal or fail clearly on incompatible action shapes."""
    action = policy(observation)
    if isinstance(action, (bool, np.bool_)) or not isinstance(action, (int, np.integer)):
        raise TypeError(
            "event-driven backtest policies must return one integer scalar action; "
            "schema-versioned action vectors require an explicit adapter"
        )
    return int(action)


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
    bar_close_time: pd.Timestamp | None = None,
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
        bar_close_time: Bar close time used by the operation described above.
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
        cost_model.bar_quote(float(row["close"]), bar_spread=bar_spread),
        fill_instant if bar_close_time is None else bar_close_time,
        "bar_close",
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
    """Mark NY bars followed by a skipped non-NY interval and another NY bar."""
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
    policy: ActionFn,
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
    tick_fill_slippage_points: float = 0.0,
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
        rr_ratio: Numeric value used for the rr ratio.
        swing_buffer_pts: Numeric value used for the swing buffer pts.
        sl_buffer_pts: Confirmed-swing trailing-stop buffer in price units.
        min_lot: Numeric value used for the min lot.
        max_lot: Numeric value used for the max lot.
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
            ``fixed``, ``breakeven``, and ``trailing`` are supported. Learned
            per-action stop mode vectors require a separate action-schema adapter.
        daily_pnl_basis: Optional daily-loss basis override. Session net equity
            includes realized and open PnL since the supplied session reset;
            legacy gross closed losses does not offset wins or include open PnL.
            When ``trading_policy`` is provided, its daily-PnL contract is used.
        trading_policy: Optional validated account-policy configuration. Repeated
            payout mode enables realized-balance withdrawals and account resets;
            its sizing requires structure-derived stop levels.
        tick_fill_slippage_points: Adverse slippage applied to tick-sourced
            market entries and closes; bar fills and structural level fills
            retain their existing cost-model behavior.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    from simulation.backtest.accounting import (
        process_repeated_payout,
        record_repeated_cycle_failure,
    )
    from simulation.backtest.policy_actions import apply_policy_action
    from simulation.backtest.protective_events import (
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
    if (
        isinstance(tick_fill_slippage_points, bool)
        or not np.isfinite(tick_fill_slippage_points)
        or tick_fill_slippage_points < 0.0
    ):
        raise ValueError("tick_fill_slippage_points must be finite and non-negative")
    sl_mode = str(sl_mode).lower()
    if sl_mode not in {"fixed", "breakeven", "trailing"}:
        raise ValueError(
            "sl_mode must be 'fixed', 'breakeven', or 'trailing' for scalar-action backtests"
        )
    try:
        sl_buffer_pts = float(sl_buffer_pts)
    except (TypeError, ValueError) as exc:
        raise ValueError("sl_buffer_pts must be finite and non-negative") from exc
    if not np.isfinite(sl_buffer_pts) or sl_buffer_pts < 0.0:
        raise ValueError("sl_buffer_pts must be finite and non-negative")

    if trading_policy is None:
        resolved_trading_policy = None
    elif isinstance(trading_policy, TradingPolicyConfig):
        resolved_trading_policy = trading_policy.validate()
    elif isinstance(trading_policy, Mapping):
        # Accept both a resolved policy mapping (``TradingPolicyConfig.to_dict``)
        # and a full application configuration mapping.
        if "mode" in trading_policy:
            resolved_trading_policy = TradingPolicyConfig(**dict(trading_policy)).validate()
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

    broker = Broker(cost_model=cost_model, **(broker_kwargs or {}))
    resolved_guardrails = dict(guardrail_kwargs or {})
    if repeated_payout:
        assert resolved_trading_policy is not None
        resolved_guardrails.update(
            {
                "daily_loss_limit": resolved_trading_policy.daily_loss_limit,
                "max_loss_limit": (
                    resolved_trading_policy.operating_balance
                    - resolved_trading_policy.account_floor
                ),
                "risk_per_trade_limit": (
                    resolved_trading_policy.operating_balance
                    * resolved_trading_policy.max_agent_risk_frac
                ),
                "soft_daily_loss_limit": 0.0,
                "soft_max_loss_limit": 0.0,
                "trailing_dd_limit": 0.0,
                "soft_trailing_dd_limit": 0.0,
                "limit_value_mode": "fixed_usd",
                "risk_per_trade_limit_pct": 0.0,
                "daily_loss_limit_pct": 0.0,
                "soft_daily_loss_limit_pct": 0.0,
                "max_loss_limit_initial_pct": 0.0,
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
        use_structure_sl_tp=use_structure_sl_tp,
        risk_frac=risk_frac,
        rr_ratio=rr_ratio,
        swing_buffer_pts=swing_buffer_pts,
        min_lot=min_lot,
        max_lot=max_lot,
        contract_size=contract_size,
        hold_on_zero=hold_on_zero,
        exit_action=exit_action,
        block_overnight=block_overnight,
        fill_latency_bars=fill_latency_bars,
        eod_risk=None if eod_risk is None else dict(eod_risk),
        execution_seed=int(execution_seed),
        sl_mode=sl_mode,
        sl_buffer_pts=float(sl_buffer_pts),
        tick_fill_slippage_points=float(tick_fill_slippage_points),
        trading_policy=resolved_trading_policy,
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

    common_idx = bars.index.intersection(features.index)
    bars = bars.loc[common_idx]
    features = features.loc[common_idx]

    bar_times = pd.DatetimeIndex(bars.index)
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

    for i in range(obs_window, n_bars):
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
            fill_bar_close = fill_instant + bar_duration
        else:
            fill_instant = bar_time
            fill_row = row
            fill_bar_close = bar_time + bar_duration

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
                    bar_close_time=fill_bar_close,
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
            process_repeated_payout(state, resolved_trading_policy, bar_time)

        state.equity_curve.append(state.account.equity)
        state.equity_times.append(pd.Timestamp(bar_time) + bar_duration)
        state.total_economic_value_curve.append(state.account.equity + state.cumulative_payouts)

        pending_order = state.pending_entry_order
        if pending_order is not None:
            obs = feat_array[i - obs_window : i].copy()
            action = _scalar_policy_action(policy, obs)
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
                        "order_id": pending_order["order_id"],
                        "reason": block_reason,
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
                    resolve_bar_execution=resolve_bar_execution,
                    is_last_ny_bar=_is_last_ny_bar,
                    feature_index=int(pending_order["decision_index"]),
                    decision_bar_time=pd.Timestamp(pending_order["decision_bar_time"]),
                    order_id=str(pending_order["order_id"]),
                )
                if state.position_sequence == position_sequence_before:
                    state.trade_log.append(
                        {
                            "type": "order_cancel",
                            "order_id": pending_order["order_id"],
                            "reason": "entry_rejected_at_scheduled_fill",
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
                )
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

        obs = feat_array[i - obs_window : i].copy()
        action = _scalar_policy_action(policy, obs)
        if settings.fill_latency_bars > 0 and action in (1, -1):
            current_ny_pos = ny_position_by_index.get(i)
            target_ny_pos = (
                -1 if current_ny_pos is None else current_ny_pos + 1 + settings.fill_latency_bars
            )
            if target_ny_pos < 0 or target_ny_pos >= len(ny_indices):
                state.trade_log.append(
                    {
                        "type": "reject",
                        "reason": "terminal_no_fill_bar",
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
                        "reason": "overnight_boundary",
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
                "action": int(action),
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
                    "order_id": order_id,
                    "direction": int(action),
                    "decision_bar": i,
                    "decision_bar_time": pd.Timestamp(bar_time),
                    "decision_time": order_submission_time,
                    "order_submission_time": order_submission_time,
                    "scheduled_fill_time": scheduled_fill_time,
                    "session_id": session,
                }
            )
            continue
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
        )

    if state.pending_entry_order is not None:
        pending_order = state.pending_entry_order
        state.trade_log.append(
            {
                "type": "order_cancel",
                "order_id": pending_order["order_id"],
                "reason": "data_end_before_scheduled_fill",
                "decision_bar_time": pending_order["decision_bar_time"],
                "order_submission_time": pending_order["order_submission_time"],
                "scheduled_fill_time": pending_order["scheduled_fill_time"],
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
        )
        if state.equity_curve:
            state.equity_curve[-1] = float(state.account.equity)
            state.total_economic_value_curve[-1] = float(
                state.account.equity + state.cumulative_payouts
            )

    trades_df = pd.DataFrame(state.trade_log)
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
        "total_economic_value": float(state.account.equity + state.cumulative_payouts),
        "ending_total_economic_value": float(state.account.equity + state.cumulative_payouts),
    }
