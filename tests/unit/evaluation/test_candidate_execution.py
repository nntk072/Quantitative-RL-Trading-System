from dataclasses import replace
from typing import Any

import pandas as pd
import pytest

from evaluation.candidate_execution import replay_candidate_proposal
from evaluation.candidate_proposals import CandidateProposal
from market_data.loading.ticks import TickBook, TickExecutionUnavailable


def _reason(outcome: Any) -> str:
    reason = outcome.unresolved_reason
    assert isinstance(reason, str)
    return reason


def _proposal(*, entry_type: str = "market", entry: float = 100.5) -> CandidateProposal:
    return CandidateProposal(
        candidate_id=3,
        idea_family="ifvg_retest",
        source_timeframe="M5",
        direction=1,
        source_event_id="event-abc",
        signal_confirmed_at="2025-01-02T10:00:00Z",
        quote_observed_at="2025-01-02T10:00:59Z",
        valid_from="2025-01-02T10:01:00Z",
        expires_at="2025-01-02T10:02:00Z",
        entry_type=entry_type,  # type: ignore[arg-type]
        proposed_entry_price=entry,
        permissible_stop_choices=(("swing_low", 99.0),),
        permissible_target_choices=(("tp1", 101.0), ("tp2", 102.0)),
        price_increment=0.25,
        max_wait_seconds=60.0,
        policy_eligibility="eligible",
        eligible_action_fill_time="2025-01-02T10:01:00Z",
        session_close_time="2025-01-02T10:05:00Z",
        source_zone_low=99.0 if entry_type == "limit" else None,
        source_zone_high=100.5 if entry_type == "limit" else None,
    )


def _book(rows: list[tuple[str, float, float]]) -> TickBook:
    times = (
        pd.DatetimeIndex([value[0] for value in rows]).tz_convert("UTC")
        if rows
        else pd.DatetimeIndex([], tz="UTC")
    )
    return TickBook(
        times.to_numpy(dtype="datetime64[ns]").view("i8").copy(),
        pd.Series([value[1] for value in rows]).to_numpy(dtype=float),
        pd.Series([value[2] for value in rows]).to_numpy(dtype=float),
    )


def test_market_entry_replays_to_first_target_with_real_tick_sides() -> None:
    proposal = _proposal()
    book = _book(
        [
            ("2025-01-02T10:01:00Z", 100.0, 100.5),
            ("2025-01-02T10:01:10Z", 101.0, 101.5),
        ]
    )

    outcome = replay_candidate_proposal(
        proposal,
        book,
        stop_choice="swing_low",
        target_choice="tp1",
        observed_until="2025-01-02T10:04:00Z",
        exit_horizon="2025-01-02T10:03:00Z",
    )

    assert outcome.status == "filled_resolved"
    assert outcome.fill_price == 100.5
    assert outcome.exit_price == 101.0
    assert outcome.net_r == pytest.approx(1.0 / 3.0)
    assert outcome.exit_reason == "tp"


def test_market_entry_waits_until_the_configured_eligible_fill_bar() -> None:
    proposal = replace(
        _proposal(),
        eligible_action_fill_time="2025-01-02T10:02:00Z",
        proposal_id="",
    )
    book = _book(
        [
            ("2025-01-02T10:01:00Z", 100.0, 100.5),
            ("2025-01-02T10:01:30Z", 101.0, 101.5),
            ("2025-01-02T10:02:00Z", 100.0, 100.5),
            ("2025-01-02T10:02:30Z", 101.0, 101.5),
        ]
    )

    outcome = replay_candidate_proposal(
        proposal,
        book,
        stop_choice="swing_low",
        target_choice="tp1",
        observed_until="2025-01-02T10:04:00Z",
        exit_horizon="2025-01-02T10:03:00Z",
    )

    assert outcome.status == "filled_resolved"
    assert outcome.fill_time == "2025-01-02T10:02:00+00:00"
    assert outcome.exit_time == "2025-01-02T10:02:30+00:00"


def test_fixed_bracket_replays_across_minute_boundaries() -> None:
    proposal = _proposal()
    book = _book(
        [
            ("2025-01-02T10:01:00Z", 100.0, 100.5),
            ("2025-01-02T10:02:00Z", 100.25, 100.75),
            ("2025-01-02T10:02:30Z", 101.0, 101.5),
        ]
    )

    outcome = replay_candidate_proposal(
        proposal,
        book,
        stop_choice="swing_low",
        target_choice="tp1",
        observed_until="2025-01-02T10:04:00Z",
        exit_horizon="2025-01-02T10:03:00Z",
    )

    assert outcome.status == "filled_resolved"
    assert outcome.exit_time == "2025-01-02T10:02:30+00:00"
    assert outcome.exit_reason == "tp"


def test_tick_after_exit_horizon_cannot_resolve_the_candidate() -> None:
    proposal = _proposal()
    book = _book(
        [
            ("2025-01-02T10:01:00Z", 100.0, 100.5),
            ("2025-01-02T10:03:10Z", 101.0, 101.5),
        ]
    )

    outcome = replay_candidate_proposal(
        proposal,
        book,
        stop_choice="swing_low",
        target_choice="tp1",
        observed_until="2025-01-02T10:04:00Z",
        exit_horizon="2025-01-02T10:03:00Z",
    )

    assert outcome.status == "censored_exit_horizon"
    assert outcome.net_r is None


def test_unresolved_bracket_is_force_closed_at_local_session_deadline() -> None:
    proposal = _proposal()
    book = _book(
        [
            ("2025-01-02T10:01:00Z", 100.0, 100.5),
            ("2025-01-02T10:02:10Z", 100.2, 100.7),
        ]
    )

    outcome = replay_candidate_proposal(
        proposal,
        book,
        stop_choice="swing_low",
        target_choice="tp1",
        observed_until="2025-01-02T10:04:00Z",
        exit_horizon="2025-01-02T10:04:00Z",
        session_close_time="2025-01-02T10:03:00Z",
    )

    assert outcome.status == "filled_resolved"
    assert outcome.exit_time == "2025-01-02T10:02:10+00:00"
    assert outcome.exit_reason == "session_close"


def test_missing_session_close_quote_is_unresolved_with_known_fill() -> None:
    proposal = _proposal()
    book = _book([("2025-01-02T10:01:00Z", 100.0, 100.5)])

    outcome = replay_candidate_proposal(
        proposal,
        book,
        stop_choice="swing_low",
        target_choice="tp1",
        observed_until="2025-01-02T10:04:00Z",
        exit_horizon="2025-01-02T10:04:00Z",
        session_close_time="2025-01-02T10:03:00Z",
    )

    assert outcome.status == "unresolved_data"
    assert outcome.fill_time == "2025-01-02T10:01:00+00:00"
    assert outcome.fill_price == 100.5
    assert "forced session close" in _reason(outcome)


def test_session_close_quote_before_fill_is_not_used_as_a_close() -> None:
    proposal = replace(
        _proposal(),
        valid_from="2025-01-02T10:02:30Z",
        expires_at="2025-01-02T10:03:30Z",
        eligible_action_fill_time="2025-01-02T10:02:30Z",
        session_close_time="2025-01-02T10:03:00Z",
        proposal_id="",
    )
    book = _book(
        [
            ("2025-01-02T10:02:10Z", 100.0, 100.5),
            ("2025-01-02T10:02:30Z", 100.0, 100.5),
        ]
    )

    outcome = replay_candidate_proposal(
        proposal,
        book,
        stop_choice="swing_low",
        target_choice="tp1",
        observed_until="2025-01-02T10:04:00Z",
        exit_horizon="2025-01-02T10:04:00Z",
        session_close_time="2025-01-02T10:03:00Z",
    )

    assert outcome.status == "unresolved_data"
    assert outcome.fill_time == "2025-01-02T10:02:30+00:00"
    assert "predates the entry fill" in _reason(outcome)


def test_limit_entry_requires_an_executable_touch_and_uses_price_improvement() -> None:
    proposal = _proposal(entry_type="limit", entry=100.0)
    book = _book(
        [
            ("2025-01-02T10:01:00Z", 100.0, 100.25),
            ("2025-01-02T10:01:10Z", 99.5, 99.75),
            ("2025-01-02T10:01:20Z", 101.0, 101.25),
        ]
    )

    outcome = replay_candidate_proposal(
        proposal,
        book,
        stop_choice="swing_low",
        target_choice="tp1",
        observed_until="2025-01-02T10:04:00Z",
        exit_horizon="2025-01-02T10:03:00Z",
    )

    assert outcome.status == "filled_resolved"
    assert outcome.fill_time == "2025-01-02T10:01:10+00:00"
    assert outcome.fill_price == 99.75
    assert outcome.exit_reason == "tp"


def test_limit_fill_sensitivity_requires_trade_through_when_requested() -> None:
    proposal = _proposal(entry_type="limit", entry=100.0)
    book = _book(
        [
            ("2025-01-02T10:01:00Z", 99.75, 100.0),
            ("2025-01-02T10:01:10Z", 99.5, 99.75),
            ("2025-01-02T10:01:20Z", 99.25, 99.5),
            ("2025-01-02T10:02:00Z", 101.0, 101.25),
        ]
    )
    common: dict[str, Any] = {
        "stop_choice": "swing_low",
        "target_choice": "tp1",
        "observed_until": "2025-01-02T10:04:00Z",
        "exit_horizon": "2025-01-02T10:03:00Z",
    }

    exact_touch = replay_candidate_proposal(proposal, book, **common)
    trade_through = replay_candidate_proposal(
        proposal, book, limit_require_trade_through=True, **common
    )

    assert exact_touch.status == "filled_resolved"
    assert exact_touch.fill_time == "2025-01-02T10:01:00+00:00"
    assert exact_touch.fill_price == 100.0
    assert trade_through.status == "filled_resolved"
    assert trade_through.fill_time == "2025-01-02T10:01:10+00:00"
    assert trade_through.fill_price == 99.75


def test_limit_fill_keeps_hard_price_bound_and_ignores_market_slippage() -> None:
    proposal = _proposal(entry_type="limit", entry=100.0)
    book = _book(
        [
            ("2025-01-02T10:01:00Z", 99.0, 99.5),
            ("2025-01-02T10:02:00Z", 101.0, 101.25),
        ]
    )

    outcome = replay_candidate_proposal(
        proposal,
        book,
        stop_choice="swing_low",
        target_choice="tp1",
        observed_until="2025-01-02T10:04:00Z",
        exit_horizon="2025-01-02T10:03:00Z",
        tick_fill_slippage_points=5.0,
    )

    assert outcome.status == "filled_resolved"
    assert outcome.fill_price == 99.5
    assert outcome.fill_price <= proposal.proposed_entry_price


def test_limit_fill_uses_deterministic_latency_and_inclusive_expiry() -> None:
    proposal = replace(
        _proposal(entry_type="limit", entry=100.0),
        expires_at="2025-01-02T10:01:10Z",
        proposal_id="",
    )
    book = _book(
        [
            ("2025-01-02T10:01:10Z", 99.5, 99.75),
            ("2025-01-02T10:02:00Z", 101.0, 101.25),
            ("2025-01-02T10:02:01Z", 101.0, 101.25),
        ]
    )

    def replay():
        return replay_candidate_proposal(
            proposal,
            book,
            stop_choice="swing_low",
            target_choice="tp1",
            observed_until="2025-01-02T10:04:00Z",
            exit_horizon="2025-01-02T10:03:00Z",
            randomized_fill_latency_ms=500.0,
            execution_seed=19,
        )

    first = replay()
    second = replay()

    assert first == second
    assert first.status == "filled_resolved"
    assert first.fill_time == "2025-01-02T10:01:10+00:00"


def test_short_limit_fill_keeps_minimum_price_bound() -> None:
    proposal = replace(
        _proposal(entry_type="limit", entry=100.0),
        direction=-1,
        permissible_stop_choices=(("swing_high", 101.0),),
        permissible_target_choices=(("tp1", 99.0),),
        proposal_id="",
    )
    book = _book(
        [
            ("2025-01-02T10:01:00Z", 100.0, 100.25),
            ("2025-01-02T10:01:10Z", 100.25, 100.5),
            ("2025-01-02T10:02:00Z", 98.75, 99.0),
        ]
    )

    outcome = replay_candidate_proposal(
        proposal,
        book,
        stop_choice="swing_high",
        target_choice="tp1",
        observed_until="2025-01-02T10:04:00Z",
        exit_horizon="2025-01-02T10:03:00Z",
    )

    assert outcome.status == "filled_resolved"
    assert outcome.fill_time == "2025-01-02T10:01:00+00:00"
    assert outcome.fill_price == 100.0
    assert outcome.fill_price >= proposal.proposed_entry_price


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"max_quote_wait_ms": 1.5}, "max_quote_wait_ms must be positive"),
        ({"randomized_fill_latency_ms": float("nan")}, "randomized_fill_latency_ms"),
        ({"limit_require_trade_through": 1}, "limit_require_trade_through must be boolean"),
        ({"tick_fill_slippage_points": float("inf")}, "execution costs must be finite"),
        ({"contract_size": float("nan")}, "contract_size must be finite"),
    ],
)
def test_replay_rejects_invalid_execution_contract_values(
    overrides: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        replay_candidate_proposal(
            _proposal(),
            _book([]),
            stop_choice="swing_low",
            target_choice="tp1",
            observed_until="2025-01-02T10:04:00Z",
            exit_horizon="2025-01-02T10:03:00Z",
            **overrides,
        )


def test_limit_without_touch_is_unfilled_after_expiry_but_censored_before_it() -> None:
    proposal = _proposal(entry_type="limit", entry=100.0)
    book = _book([("2025-01-02T10:01:00Z", 100.0, 100.25)])
    common: dict[str, Any] = {
        "stop_choice": "swing_low",
        "target_choice": "tp1",
        "exit_horizon": "2025-01-02T10:04:00Z",
    }

    censored = replay_candidate_proposal(
        proposal,
        book,
        observed_until="2025-01-02T10:01:30Z",
        **common,
    )
    expired = replay_candidate_proposal(
        proposal,
        book,
        observed_until="2025-01-02T10:02:00Z",
        **common,
    )

    assert censored.status == "censored_order_horizon"
    assert censored.net_r is None
    assert expired.status == "unfilled_expired"
    assert expired.net_r is None


def test_limit_without_touch_before_quote_coverage_gap_is_unresolved() -> None:
    proposal = _proposal(entry_type="limit", entry=100.0)
    book = _book([("2025-01-02T10:01:00Z", 100.0, 100.25)])

    outcome = replay_candidate_proposal(
        proposal,
        book,
        stop_choice="swing_low",
        target_choice="tp1",
        observed_until="2025-01-02T10:04:00Z",
        exit_horizon="2025-01-02T10:04:00Z",
        quote_coverage_cutoff="2025-01-02T10:01:30Z",
    )

    assert outcome.status == "unresolved_data"
    assert outcome.fill_time is None
    assert outcome.net_r is None
    assert "coverage is incomplete" in _reason(outcome)


def test_filled_trade_without_exit_before_quote_coverage_gap_is_unresolved() -> None:
    proposal = _proposal()
    book = _book([("2025-01-02T10:01:00Z", 100.0, 100.5)])

    outcome = replay_candidate_proposal(
        proposal,
        book,
        stop_choice="swing_low",
        target_choice="tp1",
        observed_until="2025-01-02T10:04:00Z",
        exit_horizon="2025-01-02T10:04:00Z",
        quote_coverage_cutoff="2025-01-02T10:02:00Z",
    )

    assert outcome.status == "unresolved_data"
    assert outcome.fill_time == "2025-01-02T10:01:00+00:00"
    assert outcome.net_r is None
    assert "coverage is incomplete" in _reason(outcome)


def test_resolved_exit_before_quote_coverage_gap_remains_resolved() -> None:
    proposal = _proposal()
    book = _book(
        [
            ("2025-01-02T10:01:00Z", 100.0, 100.5),
            ("2025-01-02T10:01:20Z", 101.0, 101.5),
        ]
    )

    outcome = replay_candidate_proposal(
        proposal,
        book,
        stop_choice="swing_low",
        target_choice="tp1",
        observed_until="2025-01-02T10:04:00Z",
        exit_horizon="2025-01-02T10:04:00Z",
        quote_coverage_cutoff="2025-01-02T10:02:00Z",
    )

    assert outcome.status == "filled_resolved"
    assert outcome.exit_time == "2025-01-02T10:01:20+00:00"


def test_filled_trade_without_a_protective_exit_is_right_censored() -> None:
    proposal = _proposal()
    book = _book([("2025-01-02T10:01:00Z", 100.0, 100.5)])

    outcome = replay_candidate_proposal(
        proposal,
        book,
        stop_choice="swing_low",
        target_choice="tp1",
        observed_until="2025-01-02T10:04:00Z",
        exit_horizon="2025-01-02T10:03:00Z",
    )

    assert outcome.status == "censored_exit_horizon"
    assert outcome.fill_price == 100.5
    assert outcome.net_r is None


def test_fill_after_declared_exit_horizon_is_unresolved_with_fill() -> None:
    proposal = _proposal()
    book = _book([("2025-01-02T10:01:00Z", 100.0, 100.5)])

    outcome = replay_candidate_proposal(
        proposal,
        book,
        stop_choice="swing_low",
        target_choice="tp1",
        observed_until="2025-01-02T10:04:00Z",
        exit_horizon="2025-01-02T10:00:00Z",
    )

    assert outcome.status == "unresolved_data"
    assert outcome.fill_time == "2025-01-02T10:01:00+00:00"
    assert "after the declared exit observation horizon" in _reason(outcome)


def test_stop_trigger_without_timely_exit_quote_preserves_known_fill(monkeypatch) -> None:
    proposal = _proposal()
    book = _book([("2025-01-02T10:01:00Z", 100.0, 100.5)])

    def unavailable(*args, **kwargs):
        raise TickExecutionUnavailable(
            "SL triggered at 2025-01-02T10:01:10Z, but no timely quote exists"
        )

    monkeypatch.setattr("evaluation.candidate_execution.resolve_tick_exit", unavailable)

    outcome = replay_candidate_proposal(
        proposal,
        book,
        stop_choice="swing_low",
        target_choice="tp1",
        observed_until="2025-01-02T10:04:00Z",
        exit_horizon="2025-01-02T10:03:00Z",
    )

    assert outcome.status == "unresolved_data"
    assert outcome.proposal_id == proposal.proposal_id
    assert outcome.fill_time == "2025-01-02T10:01:00+00:00"
    assert outcome.fill_price == 100.5
    assert "no timely quote" in _reason(outcome)


def test_market_gap_through_stop_is_unresolved_and_keeps_fill() -> None:
    proposal = _proposal()
    book = _book([("2025-01-02T10:01:00Z", 98.0, 98.5)])

    outcome = replay_candidate_proposal(
        proposal,
        book,
        stop_choice="swing_low",
        target_choice="tp1",
        observed_until="2025-01-02T10:04:00Z",
        exit_horizon="2025-01-02T10:03:00Z",
    )

    assert outcome.status == "unresolved_data"
    assert outcome.fill_price == 98.5
    assert "not protective" in _reason(outcome)


def test_market_gap_past_target_is_unresolved_and_keeps_fill() -> None:
    proposal = _proposal()
    book = _book([("2025-01-02T10:01:00Z", 101.0, 101.5)])

    outcome = replay_candidate_proposal(
        proposal,
        book,
        stop_choice="swing_low",
        target_choice="tp1",
        observed_until="2025-01-02T10:04:00Z",
        exit_horizon="2025-01-02T10:03:00Z",
    )

    assert outcome.status == "unresolved_data"
    assert outcome.fill_price == 101.5
    assert "not beyond" in _reason(outcome)


@pytest.mark.parametrize(
    (
        "entry_type",
        "direction",
        "entry_price",
        "stop_price",
        "target_price",
        "entry_quote",
        "trigger_quote",
        "expected_exit",
    ),
    [
        ("market", 1, 100.5, 99.0, 101.0, (100.0, 100.5), (101.0, 101.5), 101.0),
        ("limit", 1, 100.0, 99.0, 101.0, (99.75, 100.0), (101.0, 101.5), 101.0),
        ("market", -1, 100.0, 101.5, 99.0, (100.0, 100.25), (98.75, 99.0), 99.0),
        ("limit", -1, 100.0, 101.5, 99.0, (100.0, 100.25), (98.75, 99.0), 99.0),
    ],
)
def test_fixed_brackets_execute_on_first_server_side_trigger_without_second_latency(
    entry_type: str,
    direction: int,
    entry_price: float,
    stop_price: float,
    target_price: float,
    entry_quote: tuple[float, float],
    trigger_quote: tuple[float, float],
    expected_exit: float,
) -> None:
    proposal = replace(
        _proposal(entry_type=entry_type, entry=entry_price),
        direction=direction,
        permissible_stop_choices=(("protective_stop", stop_price),),
        permissible_target_choices=(("protective_target", target_price),),
        proposal_id="",
    )
    if entry_type == "limit":
        proposal = replace(
            proposal,
            source_zone_low=min(entry_price, entry_price - 0.25),
            source_zone_high=max(entry_price, entry_price + 0.25),
            proposal_id="",
        )
    book = _book(
        [
            ("2025-01-02T10:01:00.500Z", *entry_quote),
            ("2025-01-02T10:01:10.000Z", *trigger_quote),
            (
                "2025-01-02T10:01:10.400Z",
                trigger_quote[0] + (0.25 if direction == 1 else -0.25),
                trigger_quote[1] + (0.25 if direction == 1 else -0.25),
            ),
        ]
    )

    outcome = replay_candidate_proposal(
        proposal,
        book,
        stop_choice="protective_stop",
        target_choice="protective_target",
        observed_until="2025-01-02T10:04:00Z",
        exit_horizon="2025-01-02T10:03:00Z",
        randomized_fill_latency_ms=500.0,
        execution_seed=19,
    )

    assert outcome.status == "filled_resolved"
    assert outcome.exit_reason == "tp"
    assert outcome.exit_time == "2025-01-02T10:01:10+00:00"
    assert outcome.exit_price == expected_exit
