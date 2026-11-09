"""Trading performance metrics shared by baselines, supervised models, and RL agents.

All metrics are computed from an equity curve (one value per bar) and,
optionally, a list of per-trade PnL values. Functions are pure and
framework-free so they can be unit-tested against hand-computed fixtures.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, TypedDict

import numpy as np
from numpy.typing import NDArray

DEFAULT_PERIODS_PER_YEAR = 252 * 24  # hourly bars fallback
METRIC_DEFINITION_VERSION = "qrl.performance_metrics.v4"
_POSITION_CLOSE_TYPES = frozenset(
    {"close", "stop_close", "tp_close", "forced_close", "eod_close", "tp_partial_close"}
)


class _AccountPathMetrics(TypedDict):
    daily_return_count: int | None
    daily_return_mean_pct: float | None
    daily_return_std_pct: float | None
    daily_return_min_pct: float | None
    daily_return_max_pct: float | None
    time_to_ruin_sessions: int | None
    ruin_event_observed: bool | None
    ruin_time_censored: bool | None
    daily_return_availability: str | None
    time_to_ruin_availability: str | None


def _nonnegative_count(value: Any, *, field_name: str) -> int:
    """Require an integer count without accepting booleans or coercible values.

    Args:
        value: Count value to validate.
        field_name: Configuration or result field name for the error message.

    Returns:
        Validated nonnegative integer count.
    """
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < 0:
        raise ValueError(f"{field_name} must be a nonnegative integer")
    return int(value)


@dataclass(frozen=True)
class PerformanceMetrics:
    """Aggregate returns, trade statistics, and risk-breach measures for a run.

    ``breach_count`` retains the caller-supplied count for compatibility.
    ``breach_event_count`` counts ledger events, while ``breach_session_count``
    and ``breach_rate`` have distinct-session semantics.
    """

    sharpe: float = 0.0
    sortino: float = 0.0
    calmar: float = 0.0
    max_drawdown: float = 0.0
    total_return_pct: float = 0.0
    total_pnl: float = 0.0
    profit_factor: float = 0.0
    win_rate: float = 0.0
    expectancy: float = 0.0
    n_trades: int = 0
    breach_count: int = 0
    breach_event_count: int | None = None
    breach_event_count_availability: str | None = "breach_event_history_unavailable"
    breach_session_count: int | None = None
    breach_rate: float | None = None
    breach_rate_availability: str | None = "breached_session_count_unavailable"
    turnover: float = 0.0
    max_consec_loss: int = 0
    avg_trade: float = 0.0
    daily_return_count: int | None = None
    daily_return_mean_pct: float | None = None
    daily_return_std_pct: float | None = None
    daily_return_min_pct: float | None = None
    daily_return_max_pct: float | None = None
    daily_return_availability: str | None = "account_state_trace_missing_or_invalid"
    time_to_ruin_sessions: int | None = None
    ruin_event_observed: bool | None = None
    ruin_time_censored: bool | None = None
    time_to_ruin_availability: str | None = "account_state_trace_missing_or_invalid"
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR
    metric_definition_version: str = METRIC_DEFINITION_VERSION
    extras: dict[str, float] = field(default_factory=dict)


def completed_position_trade_pnls(
    trade_records: Iterable[Mapping[str, Any]],
) -> tuple[list[float], int, int]:
    """Return completed-position PnLs, realized fill count, and open-position count.

    Position-aware records aggregate all realized legs once per completed
    position. Explicit malformed completion markers and identified positions
    without a final close remain excluded. Legacy records without a completion
    marker may infer completion from a final close event. Older records without
    a position ID retain the one-record-per-trade convention.

    Args:
        trade_records: Items supplied for the trade records, in input order.

    Returns:
        Values returned by ``completed_position_trade_pnls``, in the declared order.
    """

    def finite_value(value: Any) -> float | None:
        """Coerce one trade-log value to a finite float when possible.

        Args:
            value: Value to process.

        Returns:
            Result of coerce one trade-log value to a finite float when possible.
        """
        if value is None or isinstance(value, (bool, np.bool_)):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if np.isfinite(number) else None

    position_pnls: dict[str, float] = {}
    position_summaries: dict[str, float] = {}
    position_ids: list[str] = []
    seen_position_ids: set[str] = set()
    completed_positions: set[str] = set()
    incomplete_pnl_positions: set[str] = set()
    legacy_pnls: list[float] = []
    fill_count = 0

    for record in trade_records:
        position_id = record.get("position_id")
        if position_id is None or (
            isinstance(position_id, (float, np.floating)) and np.isnan(position_id)
        ):
            pnl = finite_value(record.get("pnl"))
            if pnl is not None:
                legacy_pnls.append(pnl)
                fill_count += 1
            continue

        key = str(position_id)
        if not key:
            pnl = finite_value(record.get("pnl"))
            if pnl is not None:
                legacy_pnls.append(pnl)
                fill_count += 1
            continue

        if key not in seen_position_ids:
            position_ids.append(key)
            seen_position_ids.add(key)
        event_type = str(record.get("type", "")).strip().lower()
        pnl = finite_value(record.get("pnl"))
        raw_net_pnl = record.get("net_pnl")
        net_pnl = finite_value(raw_net_pnl)
        net_pnl_missing = raw_net_pnl is None or (
            isinstance(raw_net_pnl, (float, np.floating)) and np.isnan(raw_net_pnl)
        )
        fill_pnl = net_pnl if net_pnl is not None else pnl if net_pnl_missing else None
        if fill_pnl is not None:
            position_pnls[key] = position_pnls.get(key, 0.0) + fill_pnl
            fill_count += 1
        elif event_type in _POSITION_CLOSE_TYPES:
            incomplete_pnl_positions.add(key)

        completion_marked = "position_complete" in record
        completion = record.get("position_complete")
        explicit_completion: bool | None = None
        if isinstance(completion, (bool, np.bool_)):
            explicit_completion = bool(completion)
        elif isinstance(completion, str):
            normalized = completion.strip().lower()
            if normalized in {"true", "1"}:
                explicit_completion = True
            elif normalized in {"false", "0"}:
                explicit_completion = False
        else:
            completion_number = finite_value(completion)
            if completion_number in {0.0, 1.0}:
                explicit_completion = bool(completion_number)

        is_final_event = event_type not in {"", "open", "reject", "tp_partial_close"}
        if explicit_completion is True or (
            not completion_marked and is_final_event and fill_pnl is not None
        ):
            completed_positions.add(key)
            summary = finite_value(record.get("position_net_pnl"))
            if summary is not None:
                position_summaries[key] = summary

    completed_pnls = list(legacy_pnls)
    completed_with_pnl: set[str] = set()
    for key in position_ids:
        if key not in completed_positions:
            continue
        summary = position_summaries.get(key)
        if summary is not None:
            completed_pnls.append(summary)
            completed_with_pnl.add(key)
        elif key in position_pnls and key not in incomplete_pnl_positions:
            completed_pnls.append(position_pnls[key])
            completed_with_pnl.add(key)
    incomplete_positions = len(seen_position_ids - completed_with_pnl)
    return completed_pnls, fill_count, incomplete_positions


def sweep_delay_breakdown(
    trade_log: Sequence[dict[str, Any]],
    delay_key: str = "sweep_delay_s",
    level_key: str = "level_type",
) -> dict[str, float | int | None]:
    """Summarise Sweep Delay and Asian-vs-London targeting from open trades.

    Args:
        trade_log: The environment's ``trade_log`` list.
        delay_key: Trade-log key holding the delay in seconds.
        level_key: Trade-log key holding the swept level name.

    Returns:
        Dict with ``sweep_delay_mean_s``, ``sweep_delay_median_s``,
        ``n_entries``, ``london_pct`` and ``asian_pct`` (percent of
        entries attributed to London/Asian levels). Delay statistics are
        ``None`` when no finite delay was observed; level percentages are
        ``None`` when no entry was attributed to either level family.
    """
    delays: list[float] = []
    london = 0
    asian = 0
    n_entries = 0
    for trade in trade_log:
        if trade.get("type") != "open":
            continue
        n_entries += 1
        delay = trade.get(delay_key)
        if delay is not None and np.isfinite(delay):
            delays.append(float(delay))
        level = str(trade.get(level_key, ""))
        if "london" in level:
            london += 1
        elif "asian" in level:
            asian += 1

    total = float(london + asian)
    return {
        "sweep_delay_mean_s": float(np.mean(delays)) if delays else None,
        "sweep_delay_median_s": float(np.median(delays)) if delays else None,
        "n_entries": n_entries,
        "london_pct": london / total * 100.0 if total else None,
        "asian_pct": asian / total * 100.0 if total else None,
    }


def _account_path_metrics(
    account_state_trace: Sequence[Mapping[str, Any]] | None,
    breach_events: Sequence[Mapping[str, Any]] | None,
    *,
    breach_count: int,
    completed_data_split: bool | None,
) -> _AccountPathMetrics:
    """Derive session returns and right-censored time-to-ruin from snapshots.

    Daily returns use the simulator's supplied session IDs and opening equity.
    They include in-session payouts as economic value, but are unavailable if a
    payout crosses a session boundary without an unambiguous valuation row.
    Only closed sessions contribute to daily-return summaries. Time-to-ruin is
    the count of observed sessions through the first recorded hard breach; a
    path with no breach is right-censored at its observed session count.

    Args:
        account_state_trace: Ordered account snapshots grouped by session.
        breach_events: Hard breach events observed during the same path.
        breach_count: Compatibility count when detailed events are unavailable.
        completed_data_split: Whether all requested data rows were evaluated.

    Returns:
        Typed daily-return and time-to-ruin metrics with availability reasons.
    """
    empty: _AccountPathMetrics = {
        "daily_return_count": None,
        "daily_return_mean_pct": None,
        "daily_return_std_pct": None,
        "daily_return_min_pct": None,
        "daily_return_max_pct": None,
        "time_to_ruin_sessions": None,
        "ruin_event_observed": None,
        "ruin_time_censored": None,
        "daily_return_availability": "account_state_trace_missing_or_invalid",
        "time_to_ruin_availability": "account_state_trace_missing_or_invalid",
    }
    if not account_state_trace:
        return empty

    def number(value: Any) -> float | None:
        """Return a finite numeric account field or mark it unavailable.

        Args:
            value: Raw value read from an account-state snapshot.

        Returns:
            Finite number, or ``None`` when the value is unavailable.
        """
        if isinstance(value, (bool, np.bool_)) or not isinstance(
            value, (int, float, np.integer, np.floating)
        ):
            return None
        numeric = float(value)
        return numeric if np.isfinite(numeric) else None

    groups: list[tuple[int, list[Mapping[str, Any]]]] = []
    positions: dict[int, int] = {}
    for row in account_state_trace:
        session_id = row.get("session_id")
        if isinstance(session_id, (bool, np.bool_)) or not isinstance(
            session_id, (int, np.integer)
        ):
            return empty
        session = int(session_id)
        if session not in positions:
            positions[session] = len(groups)
            groups.append((session, []))
        group_index = positions[session]
        if group_index != len(groups) - 1:
            return empty
        if any(
            number(row.get(key)) is None
            for key in ("equity", "session_start_equity", "cumulative_payouts")
        ):
            return empty
        groups[group_index][1].append(row)
    if not groups:
        return empty

    empty["time_to_ruin_availability"] = "breach_event_history_unavailable"

    # A payout first observed at the next session boundary has ambiguous daily
    # attribution. Keep the time-to-ruin estimate, but omit daily-return stats.
    payout_boundary_ambiguous = False
    first_payout = number(groups[0][1][0].get("cumulative_payouts"))
    if first_payout is None or not math.isclose(first_payout, 0.0, abs_tol=1e-9):
        payout_boundary_ambiguous = True
    for (_, previous), (_, current) in zip(groups, groups[1:]):
        previous_payout = number(previous[-1].get("cumulative_payouts"))
        current_payout = number(current[0].get("cumulative_payouts"))
        if (
            previous_payout is None
            or current_payout is None
            or not math.isclose(previous_payout, current_payout, rel_tol=0.0, abs_tol=1e-9)
        ):
            payout_boundary_ambiguous = True

    daily_returns: list[float] = []
    if not payout_boundary_ambiguous:
        complete_count = max(0, len(groups) - 1)
        if completed_data_split is True:
            complete_count = len(groups)
        for _, rows in groups[:complete_count]:
            starting_equity = number(rows[0].get("session_start_equity"))
            ending_equity = number(rows[-1].get("equity"))
            payouts_open = number(rows[0].get("cumulative_payouts"))
            payouts_close = number(rows[-1].get("cumulative_payouts"))
            if (
                starting_equity is None
                or ending_equity is None
                or payouts_open is None
                or payouts_close is None
            ):
                return empty
            opening_value = starting_equity + payouts_open
            closing_value = ending_equity + payouts_close
            if opening_value <= 0.0 or closing_value <= 0.0:
                return empty
            daily_returns.append((closing_value / opening_value - 1.0) * 100.0)
        empty["daily_return_availability"] = (
            None if daily_returns else "no_complete_session_outcomes"
        )
    else:
        empty["daily_return_availability"] = "payout_boundary_attribution_ambiguous"

    empty["daily_return_count"] = len(daily_returns)
    if daily_returns:
        values = np.asarray(daily_returns, dtype=float)
        empty["daily_return_mean_pct"] = float(values.mean())
        empty["daily_return_min_pct"] = float(values.min())
        empty["daily_return_max_pct"] = float(values.max())
        if values.size >= 2:
            empty["daily_return_std_pct"] = float(values.std(ddof=1))

    if breach_events is None:
        return empty
    if not isinstance(breach_events, Sequence) or isinstance(breach_events, (str, bytes)):
        empty["time_to_ruin_availability"] = "breach_event_history_malformed"
        return empty
    if breach_events:
        event_positions: list[int] = []
        for event in breach_events:
            if not isinstance(event, Mapping):
                empty["time_to_ruin_availability"] = "breach_event_history_malformed"
                return empty
            session_id = event.get("session_id")
            if isinstance(session_id, (bool, np.bool_)) or not isinstance(
                session_id, (int, np.integer)
            ):
                empty["time_to_ruin_availability"] = "breach_event_session_id_missing_or_invalid"
                return empty
            event_position = positions.get(int(session_id))
            if event_position is None:
                empty["time_to_ruin_availability"] = "breach_session_not_in_account_trace"
                return empty
            event_positions.append(event_position)
        event_position = min(event_positions)
        empty["time_to_ruin_sessions"] = event_position + 1
        empty["ruin_event_observed"] = True
        empty["ruin_time_censored"] = False
        empty["time_to_ruin_availability"] = None
    else:
        if breach_count > 0:
            empty["time_to_ruin_availability"] = "breach_count_without_event_timing"
            return empty
        empty["time_to_ruin_sessions"] = len(groups)
        empty["ruin_event_observed"] = False
        empty["ruin_time_censored"] = True
        empty["time_to_ruin_availability"] = None
    return empty


def _bar_returns(equity: NDArray[np.float64]) -> NDArray[np.float64]:
    """Compute simple bar-over-bar returns from an equity curve.

    Args:
        equity: Current account equity in account currency.

    Returns:
        Array returned by ``_bar_returns``.
    """
    if equity.size < 2:
        return np.empty(0)
    return equity[1:] / equity[:-1] - 1.0


def max_drawdown(equity: Sequence[float] | NDArray[np.float64]) -> float:
    """Return peak-to-trough decline as a positive fraction.

    Args:
        equity: Equity values ordered in time.

    Returns:
        Largest relative decline from a running peak, in ``[0, 1]``.
    """
    curve = np.asarray(equity, dtype=float)
    if curve.size == 0:
        return 0.0
    running_peak = np.maximum.accumulate(curve)
    drawdowns = 1.0 - curve / running_peak
    return float(np.clip(drawdowns.max(), 0.0, 1.0))


def _sharpe(returns: NDArray[np.float64], periods_per_year: int) -> float:
    """Process the requested value.

    Args:
        returns: Returns used by the operation described above.
        periods_per_year: Numeric value used for the periods per year.

    Returns:
        Numeric result returned by ``_sharpe``.
    """
    if returns.size < 2:
        return 0.0
    std = returns.std(ddof=1)
    if std == 0.0:
        return 0.0
    return float(returns.mean() / std * np.sqrt(periods_per_year))


def _sortino(returns: NDArray[np.float64], periods_per_year: int) -> float:
    """Process the requested value.

    Args:
        returns: Returns used by the operation described above.
        periods_per_year: Numeric value used for the periods per year.

    Returns:
        Numeric result returned by ``_sortino``.
    """
    if returns.size < 2:
        return 0.0
    downside = np.minimum(returns, 0.0)
    downside_std = float(np.sqrt((downside**2).mean()))
    if downside_std == 0.0:
        return 0.0
    return float(returns.mean() / downside_std * np.sqrt(periods_per_year))


def _trade_stats(trade_pnls: NDArray[np.float64]) -> dict[str, float]:
    """Profit factor, win rate and expectancy from per-trade PnLs.

    Args:
        trade_pnls: Trade pnls used by the operation described above.

    Returns:
        Mapping from ``str`` keys to ``float`` values.
    """
    n = int(trade_pnls.size)
    if n == 0:
        return {"profit_factor": 0.0, "win_rate": 0.0, "expectancy": 0.0}
    gains = trade_pnls[trade_pnls > 0]
    losses = trade_pnls[trade_pnls < 0]
    gross_loss = float(-losses.sum())
    if gross_loss == 0.0:
        profit_factor = (
            float("inf")
            if gains.size
            else float("nan")  # Breakevens provide neither gains nor losses.
        )
    else:
        profit_factor = float(gains.sum() / gross_loss)
    return {
        "profit_factor": profit_factor,
        "win_rate": float(gains.size / n),
        "expectancy": float(trade_pnls.mean()),
    }


def _max_consec_loss(pnls: NDArray[np.float64]) -> int:
    """Longest streak of consecutive negative trade PnLs.

    Args:
        pnls: Pnls used by the operation described above.

    Returns:
        Numeric result returned by ``_max_consec_loss``.
    """
    max_streak = current = 0
    for pnl in pnls:
        if pnl < 0:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak


def compute_metrics(
    equity_curve: Sequence[float] | NDArray[np.floating[Any]],
    initial_balance: float,
    trade_pnls: Sequence[float] | None = None,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
    breach_count: int = 0,
    n_sessions: int = 1,
    n_breach_sessions: int | None = None,
    extras: dict[str, float] | None = None,
    account_state_trace: Sequence[Mapping[str, Any]] | None = None,
    breach_events: Sequence[Mapping[str, Any]] | None = None,
    completed_data_split: bool | None = None,
) -> PerformanceMetrics:
    """Compute the standard metric set for one evaluation run.

    Args:
        equity_curve: Equity after each bar, starting at ``initial_balance``.
        initial_balance: Account balance before the first bar.
        trade_pnls: Per-trade PnL of closed trades, if available.
        periods_per_year: Bars per year used to annualise ratios.
        breach_count: Caller-supplied breach count retained for compatibility.
        n_sessions: Number of trading sessions in the run; used for
            ``breach_rate`` (fraction of sessions with a breach).
        n_breach_sessions: Number of distinct sessions containing a breach.
            If omitted, it is derived from ``breach_events`` when available.
        extras: Caller-specific metrics (e.g. sweep delay) merged into output.
        account_state_trace: Complete per-step account snapshots, when retained.
            Supplied session IDs and opening equity define daily returns.
        breach_events: Ordered hard-breach events, used to measure observed
            time-to-ruin or right-censor a surviving path.
        completed_data_split: Whether evaluation reached the declared split end;
            required before including its final partial session return.

    Returns:
        A frozen :class:`PerformanceMetrics` instance.

    Raises:
        ValueError: If the equity curve is empty or the initial balance is
            not strictly positive.
    """
    raw_curve = list(equity_curve)
    numeric_types = (int, float, np.integer, np.floating)
    if any(
        isinstance(value, (bool, np.bool_)) or not isinstance(value, numeric_types)
        for value in raw_curve
    ):
        raise ValueError("equity_curve values must be finite numbers")
    curve = np.asarray(raw_curve, dtype=float)
    if curve.size == 0:
        raise ValueError("equity_curve must contain at least one value")
    if (
        isinstance(initial_balance, (bool, np.bool_))
        or not isinstance(initial_balance, numeric_types)
        or not np.isfinite(initial_balance)
        or initial_balance <= 0
    ):
        raise ValueError("initial_balance must be positive")
    if (
        isinstance(periods_per_year, (bool, np.bool_))
        or not isinstance(periods_per_year, (int, np.integer))
        or periods_per_year <= 0
    ):
        raise ValueError("periods_per_year must be positive")
    breach_count = _nonnegative_count(breach_count, field_name="breach_count")
    n_sessions = _nonnegative_count(n_sessions, field_name="n_sessions")
    if n_breach_sessions is not None:
        n_breach_sessions = _nonnegative_count(n_breach_sessions, field_name="n_breach_sessions")
    breach_session_count: int | None = n_breach_sessions
    breach_rate_availability: str | None = None
    breach_event_count: int | None = None
    breach_event_count_availability: str | None = "breach_event_history_unavailable"
    event_history_is_sequence = isinstance(breach_events, Sequence) and not isinstance(
        breach_events, (str, bytes)
    )
    if breach_events is not None and not event_history_is_sequence:
        breach_session_count = None
        breach_rate_availability = "breach_event_history_malformed"
        breach_event_count_availability = "breach_event_history_malformed"
    elif breach_events is None and breach_count == 0:
        breach_event_count = 0
        breach_event_count_availability = None
    elif event_history_is_sequence:
        assert breach_events is not None
        event_session_ids: set[int] = set()
        event_sessions_valid = True
        event_rows_valid = True
        for event in breach_events:
            if not isinstance(event, Mapping):
                event_rows_valid = False
                event_sessions_valid = False
                break
            session_id = event.get("session_id")
            if isinstance(session_id, (bool, np.bool_)) or not isinstance(
                session_id, (int, np.integer)
            ):
                event_sessions_valid = False
                continue
            event_session_ids.add(int(session_id))
        if event_rows_valid:
            breach_event_count = len(breach_events)
            breach_event_count_availability = None
        else:
            breach_event_count_availability = "breach_event_history_malformed"
        if not event_sessions_valid:
            breach_session_count = None
            breach_rate_availability = "breach_event_session_id_missing_or_invalid"
        elif n_breach_sessions is not None and n_breach_sessions != len(event_session_ids):
            breach_session_count = None
            breach_rate_availability = "breach_session_count_disagrees_with_events"
        else:
            breach_session_count = len(event_session_ids)
    elif breach_session_count is None and breach_count == 0:
        breach_session_count = 0
    if breach_rate_availability is None:
        if breach_session_count is None:
            breach_rate_availability = "distinct_breach_session_count_unavailable"
        elif n_sessions == 0:
            breach_rate_availability = "no_sessions_for_denominator"
        elif breach_session_count > n_sessions:
            breach_session_count = None
            breach_rate_availability = "breach_session_count_exceeds_session_count"
        else:
            breach_rate_availability = None
    if not np.all(np.isfinite(curve)):
        raise ValueError("equity_curve values must be finite")
    if np.any(curve <= 0):
        raise ValueError("equity_curve values must be positive")

        # Callers may supply end-of-bar valuations without the opening capital.
        # Preserve an explicitly included opening balance, otherwise count the
        # first valuation's profit or loss in the return path and drawdown.
    path = curve if curve[0] == initial_balance else np.concatenate(([initial_balance], curve))
    returns = _bar_returns(path)
    mdd = max_drawdown(path)
    total_pnl = float(curve[-1] - initial_balance)
    # ``curve`` may either include the initial balance or contain only
    # end-of-bar valuations. ``returns`` always counts elapsed bar intervals,
    # so use it as the annualisation duration in both representations.
    years = returns.size / periods_per_year
    if years > 0:
        annualised_log_return = (math.log(float(curve[-1])) - math.log(initial_balance)) / years
        try:
            annualised = math.expm1(annualised_log_return)
        except OverflowError:
            annualised = math.inf if annualised_log_return > 0.0 else -1.0
    else:
        annualised = 0.0

    raw_pnls = list(trade_pnls) if trade_pnls is not None else []
    if any(
        isinstance(value, (bool, np.bool_)) or not isinstance(value, numeric_types)
        for value in raw_pnls
    ):
        raise ValueError("trade_pnls values must be finite numbers")
    try:
        pnls = np.asarray(raw_pnls, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("trade_pnls values must be finite numbers") from exc
    if not np.isfinite(pnls).all():
        raise ValueError("trade_pnls values must be finite numbers")
    stats = _trade_stats(pnls)
    path_metrics = _account_path_metrics(
        account_state_trace,
        breach_events,
        breach_count=breach_count,
        completed_data_split=completed_data_split,
    )

    calmar = float(annualised / mdd) if mdd > 0 else 0.0
    return PerformanceMetrics(
        sharpe=_sharpe(returns, periods_per_year),
        sortino=_sortino(returns, periods_per_year),
        calmar=calmar,
        max_drawdown=mdd,
        total_return_pct=float(total_pnl / initial_balance * 100.0),
        total_pnl=total_pnl,
        profit_factor=stats["profit_factor"],
        win_rate=stats["win_rate"],
        expectancy=stats["expectancy"],
        n_trades=int(pnls.size),
        breach_count=breach_count,
        breach_event_count=breach_event_count,
        breach_event_count_availability=breach_event_count_availability,
        breach_session_count=breach_session_count,
        breach_rate=(
            breach_session_count / n_sessions
            if breach_session_count is not None and n_sessions > 0
            else None
        ),
        breach_rate_availability=breach_rate_availability,
        turnover=float(pnls.size / curve.size) if curve.size else 0.0,
        max_consec_loss=_max_consec_loss(pnls),
        avg_trade=stats["expectancy"],
        **path_metrics,
        periods_per_year=periods_per_year,
        metric_definition_version=METRIC_DEFINITION_VERSION,
        extras=dict(extras or {}),
    )

    # M1 bars per year: kept as the default for the pandas adapter below so the
    # migrated training runners preserve their historical annualisation.


LEGACY_M1_PERIODS_PER_YEAR = 252 * 390


def evaluation_periods_per_year(config: Mapping[str, Any]) -> int:
    """Resolve annualization basis, preserving legacy M1 values for old configs.

    Args:
        config: Configuration values used by this operation.

    Returns:
        Numeric result returned by ``evaluation_periods_per_year``.
    """
    evaluation = config.get("evaluation", {})
    raw = (
        evaluation.get("periods_per_year", LEGACY_M1_PERIODS_PER_YEAR)
        if isinstance(evaluation, Mapping)
        else LEGACY_M1_PERIODS_PER_YEAR
    )
    if isinstance(raw, bool):
        raise ValueError("evaluation.periods_per_year must be a positive integer")
    try:
        periods = int(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("evaluation.periods_per_year must be a positive integer") from exc
    if periods <= 0 or (isinstance(raw, float) and raw != periods):
        raise ValueError("evaluation.periods_per_year must be a positive integer")
    return periods


def account_path_metric_inputs(result: Mapping[str, Any]) -> dict[str, Any]:
    """Return only complete, typed account-path evidence for metric calculation.

    Evaluation results may deliberately omit an incomplete account trace. This
    adapter prevents a partial trace or malformed completion flag from being
    treated as full-path daily-return or time-to-ruin evidence.

    Args:
        result: Evaluation result containing account trace and breach evidence.

    Returns:
        Validated trace, breach events, and completion flag for metric calculation.
    """
    trace = result.get("account_state_trace")
    if result.get("account_state_trace_complete") is not True:
        trace = None
    breaches = result.get("breach_events")
    if not isinstance(breaches, Sequence) or isinstance(breaches, (str, bytes)):
        breaches = None
    completed = result.get("completed_data_split")
    if not isinstance(completed, bool):
        completed = None
    return {
        "account_state_trace": trace,
        "breach_events": breaches,
        "completed_data_split": completed,
    }


def calculate_metrics(
    equity: Any,
    trades: Any = None,
    n_sessions: int = 1,
    n_breach_sessions: int | None = None,
    periods_per_year: int = LEGACY_M1_PERIODS_PER_YEAR,
    initial_balance: float | None = None,
    account_state_trace: Any = None,
    breach_events: Sequence[Mapping[str, Any]] | None = None,
    completed_data_split: bool | None = None,
) -> PerformanceMetrics:
    """Pandas-friendly adapter matching the legacy ``eval.metrics`` signature.

    Accepts a ``pd.Series`` (or any sequence) equity curve and an optional
    trade/event ledger. Position-aware lifecycle records are reduced to completed-position
    PnL before delegating to :func:`compute_metrics`. The initial balance is taken from the first
    equity value when ``initial_balance`` is ``None``, matching the legacy
    behaviour of the migrated training runners.

    Args:
        equity: Bar-level equity curve (``pd.Series`` or sequence).
        trades: Trade records or lifecycle event ledger (typically a ``pd.DataFrame``), or None.
        n_sessions: Number of trading sessions, for ``breach_rate``.
        n_breach_sessions: Sessions in which a guardrail breach occurred.
        periods_per_year: Bars per year for annualisation.  Defaults to M1
            bars (``252 * 390``) to match the legacy evaluation runs.
        initial_balance: Account balance before the first bar.  When ``None``,
            the first value of the equity curve is used as the initial balance.
        account_state_trace: Complete per-step account snapshot DataFrame or
            sequence, when available.
        breach_events: Ordered hard-breach records from the evaluation.
        completed_data_split: Whether evaluation reached the declared split end.

    Returns:
        A frozen :class:`PerformanceMetrics` instance.
    """
    curve = (
        equity.to_numpy(dtype=float)
        if hasattr(equity, "to_numpy")
        else np.asarray(equity, dtype=float)
    )  # noqa: E501
    if curve.size == 0:
        raise ValueError("equity must contain at least one value")
    if n_breach_sessions is not None:
        n_breach_sessions = _nonnegative_count(n_breach_sessions, field_name="n_breach_sessions")

    trade_pnls: list[float] | None = None
    fill_count = 0
    incomplete_positions = 0
    if trades is not None and len(trades) > 0:
        if hasattr(trades, "to_dict") and hasattr(trades, "columns"):
            records = trades.to_dict(orient="records")
        elif isinstance(trades, Sequence) and all(isinstance(row, Mapping) for row in trades):
            records = trades
        else:
            records = []
        if records:
            trade_pnls, fill_count, incomplete_positions = completed_position_trade_pnls(records)
        elif "pnl" in trades:
            pnl = trades["pnl"]
            pnl = pnl.dropna() if hasattr(pnl, "dropna") else pnl
            trade_pnls = [float(v) for v in pnl]

    init_bal = float(curve[0]) if initial_balance is None else float(initial_balance)

    trace_records: Sequence[Mapping[str, Any]] | None = None
    if account_state_trace is not None:
        if hasattr(account_state_trace, "to_dict") and hasattr(account_state_trace, "columns"):
            trace_records = account_state_trace.to_dict(orient="records")
        elif isinstance(account_state_trace, Sequence) and not isinstance(
            account_state_trace, (str, bytes)
        ):
            trace_records = account_state_trace

    return compute_metrics(
        curve,
        initial_balance=init_bal,
        trade_pnls=trade_pnls,
        periods_per_year=periods_per_year,
        breach_count=n_breach_sessions if n_breach_sessions is not None else 0,
        n_sessions=n_sessions,
        n_breach_sessions=n_breach_sessions,
        account_state_trace=trace_records,
        breach_events=breach_events,
        completed_data_split=completed_data_split,
        extras={
            "fill_count": float(fill_count),
            "incomplete_positions": float(incomplete_positions),
            "entry_active": float(bool(trade_pnls)),
        },
    )
