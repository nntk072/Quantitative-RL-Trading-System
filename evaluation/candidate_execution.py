"""Tick-aware conditional replay for fixed candidate proposals.

This path labels one hypothetical order and geometry choice at a time. It does
not model portfolio contention, account state, or a closed-loop policy.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

import numpy as np
import pandas as pd

from evaluation.candidate_outcomes import CandidateConditionalOutcome
from evaluation.candidate_proposals import CandidateProposal
from market_data.loading.ticks import (
    TickBook,
    TickExecutionUnavailable,
    event_keyed_execution_rng,
    resolve_tick_execution,
    resolve_tick_execution_by_deadline,
    resolve_tick_exit,
    resolve_tick_limit_execution,
)
from trading.execution import adverse_tick_fill_quote

_FillStatus = Literal["filled", "unfilled_expired", "censored_order_horizon", "unresolved_data"]


def _aware_timestamp(value: str | pd.Timestamp, name: str) -> pd.Timestamp:
    """Parse an execution timestamp and require timezone awareness.

    Args:
        value: Timestamp value supplied by the proposal or replay caller.
        name: Field name included in validation errors.

    Returns:
        The parsed timezone-aware timestamp.
    """
    timestamp = pd.Timestamp(value)
    if timestamp.tz is None:
        raise ValueError(f"{name} must be timezone-aware")
    return timestamp


def _menu_price(menu: tuple[tuple[str, float], ...], choice: str, name: str) -> float:
    """Return the uniquely named price from an approved geometry menu.

    Args:
        menu: Permitted name and price pairs for the selected geometry.
        choice: Name selected by the candidate proposal.
        name: Geometry field name included in validation errors.

    Returns:
        The unique permitted price associated with ``choice``.
    """
    matches = [float(price) for reference, price in menu if reference == choice]
    if len(matches) != 1:
        raise ValueError(f"{name} must identify exactly one permitted geometry choice")
    return matches[0]


def _entry_start(proposal: CandidateProposal) -> pd.Timestamp:
    """Return the first bar where the configured policy action can fill.

    Args:
        proposal: Candidate proposal with the action-eligibility timestamp.

    Returns:
        The timezone-aware action-fill start timestamp.
    """
    return _aware_timestamp(
        proposal.eligible_action_fill_time or proposal.valid_from,
        "eligible_action_fill_time",
    )


def _tick_window_view(book: TickBook, start: pd.Timestamp, end: pd.Timestamp) -> TickBook:
    """Create a zero-copy TickBook view over the half-open interval [start, end).

    Args:
        book: Source TickBook to slice without copying its quote arrays.
        start: Inclusive start timestamp.
        end: Exclusive end timestamp.

    Returns:
        TickBook view containing quotes in the requested interval.
    """
    start_ns = start.value
    end_ns = end.value
    i0 = int(np.searchsorted(book._ts, start_ns, side="left"))
    i1 = int(np.searchsorted(book._ts, end_ns, side="left"))
    return TickBook(book._ts[i0:i1], book._bid[i0:i1], book._ask[i0:i1])


def _limit_fill(
    book: TickBook,
    proposal: CandidateProposal,
    *,
    observed_until: pd.Timestamp,
    require_trade_through: bool,
    randomized_fill_latency_ms: float,
    execution_seed: int,
    proposal_id: str,
) -> tuple[pd.Timestamp, float] | None:
    """Find the first executable quote touch of a resting limit within its TTL.

    Limit fills retain their hard submitted-price bound. Configured market-order
    slippage is not applied to a resting limit; a quote through the limit may
    improve the fill price, while a quote at the limit is either accepted or
    rejected according to ``require_trade_through``.

    Args:
        book: Tick quotes available during the order lifetime.
        proposal: Candidate limit order and its side, price, and expiry.
        observed_until: Last timestamp with observed quote data.
        require_trade_through: Whether price must pass the submitted limit.
        randomized_fill_latency_ms: Maximum seeded order-arrival delay.
        execution_seed: Seed for deterministic event-keyed latency.
        proposal_id: Stable identity used to derive the event RNG stream.

    Returns:
        First executable fill timestamp and price, or ``None`` if unfilled.
    """
    start = _entry_start(proposal)
    expiry = _aware_timestamp(proposal.expires_at, "expires_at")
    end = min(expiry, observed_until)
    limit_price = float(proposal.proposed_entry_price)
    rng = event_keyed_execution_rng(execution_seed, f"candidate_limit_entry:{proposal_id}")
    quote = resolve_tick_limit_execution(
        book,
        proposal.direction,
        limit_price,
        start,
        end,
        rng,
        max_latency_ns_exclusive=int(randomized_fill_latency_ms * 1_000_000),
        require_trade_through=require_trade_through,
    )
    if quote is None:
        return None
    fill_price = quote.ask if proposal.direction == 1 else quote.bid
    if proposal.direction == 1:
        fill_price = min(float(fill_price), limit_price)
    else:
        fill_price = max(float(fill_price), limit_price)
    return quote.tick_time, float(fill_price)


def _resolve_entry(
    book: TickBook,
    proposal: CandidateProposal,
    *,
    observed_until: pd.Timestamp,
    max_quote_wait_ms: int,
    randomized_fill_latency_ms: float,
    tick_fill_slippage_points: float,
    limit_require_trade_through: bool,
    execution_seed: int,
) -> tuple[_FillStatus, pd.Timestamp | None, float | None]:
    """Resolve a proposal's market or limit entry against executable ticks.

    Args:
        book: Tick quotes available for the entry attempt.
        proposal: Candidate order with side, type, price, and valid lifetime.
        observed_until: Last timestamp with observed quote data.
        max_quote_wait_ms: Maximum delay allowed for a market entry quote.
        randomized_fill_latency_ms: Maximum seeded order-arrival delay.
        tick_fill_slippage_points: Adverse slippage applied to market entries.
        limit_require_trade_through: Whether a limit requires a strict price pass.
        execution_seed: Seed for deterministic event-keyed latency.

    Returns:
        Entry status, fill timestamp, and fill price; unavailable values are ``None``.
    """
    start = _entry_start(proposal)
    expiry = _aware_timestamp(proposal.expires_at, "expires_at")
    end = min(expiry, observed_until)
    if end < start:
        return "censored_order_horizon", None, None

    if proposal.entry_type == "limit":
        fill = _limit_fill(
            book,
            proposal,
            observed_until=end,
            require_trade_through=limit_require_trade_through,
            randomized_fill_latency_ms=randomized_fill_latency_ms,
            execution_seed=execution_seed,
            proposal_id=proposal.proposal_id,
        )
        if fill is not None:
            return "filled", fill[0], fill[1]
        if observed_until < expiry:
            return "censored_order_horizon", None, None
        return "unfilled_expired", None, None

    rng = event_keyed_execution_rng(execution_seed, f"candidate_entry:{proposal.proposal_id}")
    quote = resolve_tick_execution(
        book,
        start,
        rng,
        max_latency_ns_exclusive=int(randomized_fill_latency_ms * 1_000_000),
        max_quote_wait_ns=int(max_quote_wait_ms * 1_000_000),
    )
    if quote is None or quote.tick_time > end:
        return "unresolved_data", None, None
    adjusted = adverse_tick_fill_quote(
        (quote.bid, quote.ask),
        proposal.direction,
        tick_fill_slippage_points,
        opening=True,
    )
    fill_price = adjusted[1] if proposal.direction == 1 else adjusted[0]
    return "filled", quote.tick_time, float(fill_price)


def replay_candidate_proposal(
    proposal: CandidateProposal,
    book: TickBook,
    *,
    stop_choice: str,
    target_choice: str,
    observed_until: str | pd.Timestamp,
    exit_horizon: str | pd.Timestamp,
    session_close_time: str | pd.Timestamp | None = None,
    max_quote_wait_ms: int = 60_000,
    randomized_fill_latency_ms: float = 0.0,
    fill_delay_ms: int = 0,
    tick_fill_slippage_points: float = 0.0,
    limit_require_trade_through: bool = False,
    commission_per_lot: float = 0.0,
    contract_size: float = 1.0,
    execution_seed: int = 0,
    quote_coverage_cutoff: str | pd.Timestamp | None = None,
) -> CandidateConditionalOutcome:
    """Replay one order and one selected bracket through the current TickBook.

    Order censoring is determined against the observed cutoff and proposal TTL.
    Filled trades use the first tick-triggered stop/target, with stop precedence
    on a tick that crosses both and configured latency/quote-wait semantics.
    ``quote_coverage_cutoff`` is the first locally audited incomplete quote
    minute after the eligible action time. Horizons truncated by that boundary
    become unresolved data, while earlier administrative censoring stays
    censored.

    Args:
        proposal: Candidate setup, entry action, and selected geometry.
        book: Current-source tick quotes for the proposal interval.
        stop_choice: Stop reference selected from the proposal's allowed menu.
        target_choice: Target reference selected from the allowed menu.
        observed_until: Last timestamp with quote observations for the replay.
        exit_horizon: Maximum timestamp through which exit events are evaluated.
        session_close_time: Optional session boundary that forces liquidation.
        max_quote_wait_ms: Maximum wait for an executable market-entry quote.
        randomized_fill_latency_ms: Maximum seeded order-arrival delay.
        fill_delay_ms: Historical compatibility argument; only zero is supported.
        tick_fill_slippage_points: Adverse market-entry and exit slippage.
        limit_require_trade_through: Whether limit fills require a strict pass.
        commission_per_lot: Commission charged on each side of the position.
        contract_size: Units represented by one lot for risk and commission math.
        execution_seed: Seed for deterministic event-keyed latency.
        quote_coverage_cutoff: First locally audited incomplete quote minute.

    Returns:
        Conditional outcome status, timestamps, prices, and net-R result.
    """
    if (
        not isinstance(max_quote_wait_ms, (int, np.integer))
        or isinstance(max_quote_wait_ms, (bool, np.bool_))
        or max_quote_wait_ms <= 0
    ):
        raise ValueError("max_quote_wait_ms must be positive")
    if not np.isfinite(randomized_fill_latency_ms) or randomized_fill_latency_ms < 0.0:
        raise ValueError("randomized_fill_latency_ms must be finite and non-negative")
    if not isinstance(limit_require_trade_through, bool):
        raise ValueError("limit_require_trade_through must be boolean")
    if fill_delay_ms < 0:
        raise ValueError("fill_delay_ms cannot be negative")
    if fill_delay_ms != 0:
        raise ValueError("nonzero fill_delay_ms is not supported by this replay contract")
    if (
        not np.isfinite(tick_fill_slippage_points)
        or not np.isfinite(commission_per_lot)
        or tick_fill_slippage_points < 0.0
        or commission_per_lot < 0.0
    ):
        raise ValueError("execution costs must be finite and non-negative")
    if not np.isfinite(contract_size) or contract_size <= 0.0:
        raise ValueError("contract_size must be finite and positive")

    stop = _menu_price(proposal.permissible_stop_choices, stop_choice, "stop_choice")
    target = _menu_price(proposal.permissible_target_choices, target_choice, "target_choice")
    observed = _aware_timestamp(observed_until, "observed_until")
    horizon = _aware_timestamp(exit_horizon, "exit_horizon")
    resolved_session_close_time = session_close_time or proposal.session_close_time
    session_close = (
        _aware_timestamp(resolved_session_close_time, "session_close_time")
        if resolved_session_close_time is not None
        else None
    )
    coverage_gap: pd.Timestamp | None = None
    if quote_coverage_cutoff is not None:
        candidate_gap = _aware_timestamp(quote_coverage_cutoff, "quote_coverage_cutoff")
        if candidate_gap < _entry_start(proposal):
            raise ValueError("quote_coverage_cutoff cannot predate the eligible action time")
        coverage_horizon = min(observed, horizon, session_close or horizon)
        if candidate_gap < coverage_horizon:
            coverage_gap = candidate_gap
            observed = min(observed, candidate_gap)
    expiry = _aware_timestamp(proposal.expires_at, "expires_at")
    fill_status, fill_time, entry_price = _resolve_entry(
        book,
        proposal,
        observed_until=observed,
        max_quote_wait_ms=max_quote_wait_ms,
        randomized_fill_latency_ms=randomized_fill_latency_ms,
        tick_fill_slippage_points=tick_fill_slippage_points,
        limit_require_trade_through=limit_require_trade_through,
        execution_seed=execution_seed,
    )
    if fill_status != "filled" or fill_time is None or entry_price is None:
        unresolved_reason = (
            "market-entry quote unavailable within the configured quote-wait limit"
            if fill_status == "unresolved_data"
            else None
        )
        outcome = CandidateConditionalOutcome(
            proposal_id=proposal.proposal_id,
            status="unresolved_data" if fill_status == "filled" else fill_status,
            evaluated_until=min(observed, expiry).isoformat(),
            order_expires_at=expiry.isoformat(),
            stop_choice=stop_choice,
            target_choice=target_choice,
            unresolved_reason=unresolved_reason,
        )
        return _coverage_unresolved(outcome, coverage_gap)

    if proposal.direction * (entry_price - stop) <= 0.0:
        return CandidateConditionalOutcome(
            proposal_id=proposal.proposal_id,
            status="unresolved_data",
            evaluated_until=fill_time.isoformat(),
            order_expires_at=expiry.isoformat(),
            stop_choice=stop_choice,
            target_choice=target_choice,
            fill_time=fill_time.isoformat(),
            fill_price=entry_price,
            unresolved_reason="selected stop is not protective relative to the realized entry fill",
        )
    if proposal.direction * (target - entry_price) <= 0.0:
        return CandidateConditionalOutcome(
            proposal_id=proposal.proposal_id,
            status="unresolved_data",
            evaluated_until=fill_time.isoformat(),
            order_expires_at=expiry.isoformat(),
            stop_choice=stop_choice,
            target_choice=target_choice,
            fill_time=fill_time.isoformat(),
            fill_price=entry_price,
            unresolved_reason="selected target is not beyond the realized entry fill",
        )
    if session_close is not None and fill_time >= session_close:
        return CandidateConditionalOutcome(
            proposal_id=proposal.proposal_id,
            status="unresolved_data",
            evaluated_until=fill_time.isoformat(),
            order_expires_at=expiry.isoformat(),
            stop_choice=stop_choice,
            target_choice=target_choice,
            fill_time=fill_time.isoformat(),
            fill_price=entry_price,
            unresolved_reason="entry fill occurred at or after the configured session close",
        )
    end = (
        min(horizon, observed, session_close)
        if session_close is not None
        else min(horizon, observed)
    )
    session_close_is_observed = (
        session_close is not None and session_close <= horizon and session_close <= observed
    )
    if end < fill_time:
        return CandidateConditionalOutcome(
            proposal_id=proposal.proposal_id,
            status="unresolved_data",
            evaluated_until=fill_time.isoformat(),
            order_expires_at=expiry.isoformat(),
            stop_choice=stop_choice,
            target_choice=target_choice,
            fill_time=fill_time.isoformat(),
            fill_price=entry_price,
            unresolved_reason="entry fill occurred after the declared exit observation horizon",
        )
    if end == fill_time:
        outcome = CandidateConditionalOutcome(
            proposal_id=proposal.proposal_id,
            status="censored_exit_horizon",
            evaluated_until=end.isoformat(),
            order_expires_at=expiry.isoformat(),
            stop_choice=stop_choice,
            target_choice=target_choice,
            fill_time=fill_time.isoformat(),
            fill_price=entry_price,
        )
        return _coverage_unresolved(outcome, coverage_gap)

    bar_start = fill_time.floor("min")
    # A fixed bracket has no bar-to-bar state changes. Restrict the TickBook to
    # the exact observed half-open interval, then resolve once across it. This
    # avoids a Python call for every minute while preserving source-ordered
    # first-trigger and same-tick stop precedence semantics.
    exit_book = _tick_window_view(book, bar_start, end)
    duration_ns = end.value - bar_start.value
    bar_minutes = max(1, int(np.ceil(duration_ns / pd.Timedelta(minutes=1).value)))
    try:
        exit_event = resolve_tick_exit(
            exit_book,
            bar_start,
            proposal.direction,
            stop,
            target,
            np.random.default_rng(execution_seed),
            bar_minutes=bar_minutes,
            earliest_time=fill_time,
            max_latency_ns_exclusive=int(randomized_fill_latency_ms * 1_000_000),
            max_quote_wait_ns=int(max_quote_wait_ms * 1_000_000),
            event_seed=execution_seed,
        )
    except TickExecutionUnavailable as exc:
        return CandidateConditionalOutcome(
            proposal_id=proposal.proposal_id,
            status="unresolved_data",
            evaluated_until=end.isoformat(),
            order_expires_at=expiry.isoformat(),
            stop_choice=stop_choice,
            target_choice=target_choice,
            fill_time=fill_time.isoformat(),
            fill_price=entry_price,
            unresolved_reason=str(exc),
        )
    if exit_event is None:
        if session_close_is_observed and session_close is not None:
            submission_time = session_close - pd.Timedelta(minutes=1)
            eod_quote = resolve_tick_execution_by_deadline(
                book,
                submission_time,
                session_close,
                event_keyed_execution_rng(
                    execution_seed,
                    f"candidate_session_close:{proposal.proposal_id}:{session_close.value}",
                ),
                max_latency_ns_exclusive=int(randomized_fill_latency_ms * 1_000_000),
                max_quote_wait_ns=int(max_quote_wait_ms * 1_000_000),
            )
            if eod_quote is None:
                return CandidateConditionalOutcome(
                    proposal_id=proposal.proposal_id,
                    status="unresolved_data",
                    evaluated_until=session_close.isoformat(),
                    order_expires_at=expiry.isoformat(),
                    stop_choice=stop_choice,
                    target_choice=target_choice,
                    fill_time=fill_time.isoformat(),
                    fill_price=entry_price,
                    unresolved_reason="no timely executable quote for the forced session close",
                )
            if eod_quote.tick_time < fill_time:
                return CandidateConditionalOutcome(
                    proposal_id=proposal.proposal_id,
                    status="unresolved_data",
                    evaluated_until=session_close.isoformat(),
                    order_expires_at=expiry.isoformat(),
                    stop_choice=stop_choice,
                    target_choice=target_choice,
                    fill_time=fill_time.isoformat(),
                    fill_price=entry_price,
                    unresolved_reason="session-close execution quote predates the entry fill",
                )
            adjusted_eod_quote = adverse_tick_fill_quote(
                (eod_quote.bid, eod_quote.ask),
                proposal.direction,
                tick_fill_slippage_points,
                opening=False,
            )
            eod_price = adjusted_eod_quote[0] if proposal.direction == 1 else adjusted_eod_quote[1]
            risk_points = abs(entry_price - stop)
            net_r = proposal.direction * (eod_price - entry_price) / risk_points - (
                2.0 * commission_per_lot / (contract_size * risk_points)
            )
            return CandidateConditionalOutcome(
                proposal_id=proposal.proposal_id,
                status="filled_resolved",
                evaluated_until=eod_quote.tick_time.isoformat(),
                order_expires_at=expiry.isoformat(),
                stop_choice=stop_choice,
                target_choice=target_choice,
                fill_time=fill_time.isoformat(),
                fill_price=entry_price,
                exit_time=eod_quote.tick_time.isoformat(),
                exit_price=float(eod_price),
                exit_reason="session_close",
                net_r=float(net_r),
            )
        outcome = CandidateConditionalOutcome(
            proposal_id=proposal.proposal_id,
            status="censored_exit_horizon",
            evaluated_until=end.isoformat(),
            order_expires_at=expiry.isoformat(),
            stop_choice=stop_choice,
            target_choice=target_choice,
            fill_time=fill_time.isoformat(),
            fill_price=entry_price,
        )
        return _coverage_unresolved(outcome, coverage_gap)
    if exit_event.quote.tick_time > end:
        outcome = CandidateConditionalOutcome(
            proposal_id=proposal.proposal_id,
            status="censored_exit_horizon",
            evaluated_until=end.isoformat(),
            order_expires_at=expiry.isoformat(),
            stop_choice=stop_choice,
            target_choice=target_choice,
            fill_time=fill_time.isoformat(),
            fill_price=entry_price,
        )
        return _coverage_unresolved(outcome, coverage_gap)
    quote = adverse_tick_fill_quote(
        (exit_event.quote.bid, exit_event.quote.ask),
        proposal.direction,
        tick_fill_slippage_points,
        opening=False,
    )
    exit_price = quote[0] if proposal.direction == 1 else quote[1]
    risk_points = abs(entry_price - stop)
    net_r = proposal.direction * (
        exit_price - entry_price
    ) / risk_points - 2.0 * commission_per_lot / (contract_size * risk_points)
    return CandidateConditionalOutcome(
        proposal_id=proposal.proposal_id,
        status="filled_resolved",
        evaluated_until=exit_event.quote.tick_time.isoformat(),
        order_expires_at=expiry.isoformat(),
        stop_choice=stop_choice,
        target_choice=target_choice,
        fill_time=fill_time.isoformat(),
        fill_price=entry_price,
        exit_time=exit_event.quote.tick_time.isoformat(),
        exit_price=float(exit_price),
        exit_reason=exit_event.kind,
        net_r=float(net_r),
    )


def _coverage_unresolved(
    outcome: CandidateConditionalOutcome, coverage_gap: pd.Timestamp | None
) -> CandidateConditionalOutcome:
    """Convert tape-truncated order/exit horizons into explicit unresolved data.

    Args:
        outcome: Replay result whose order or exit horizon may be censored.
        coverage_gap: First timestamp where quote coverage becomes incomplete.

    Returns:
        An unresolved outcome when the gap precedes resolution, otherwise the
        original outcome unchanged.
    """
    if coverage_gap is None or outcome.status not in {
        "censored_order_horizon",
        "censored_exit_horizon",
    }:
        return outcome
    return replace(
        outcome,
        status="unresolved_data",
        unresolved_reason=(
            "local two-sided quote coverage is incomplete before order expiry"
            if outcome.status == "censored_order_horizon"
            else "local two-sided quote coverage is incomplete before exit resolution"
        ),
    )


__all__ = ["replay_candidate_proposal"]
