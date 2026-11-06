from dataclasses import replace
from typing import Any, Literal, NotRequired, TypedDict, cast

import pytest

from evaluation.candidate_outcomes import CandidateConditionalOutcome


class _OutcomeValues(TypedDict):
    proposal_id: str
    status: Literal[
        "filled_resolved",
        "unfilled_expired",
        "censored_order_horizon",
        "censored_exit_horizon",
        "unresolved_data",
    ]
    evaluated_until: str
    order_expires_at: str
    stop_choice: str
    target_choice: str
    fill_time: NotRequired[str | None]
    fill_price: NotRequired[float | None]
    exit_time: NotRequired[str | None]
    exit_price: NotRequired[float | None]
    exit_reason: NotRequired[str | None]
    net_r: NotRequired[float | None]
    unresolved_reason: NotRequired[str | None]


def _outcome(**overrides: Any) -> CandidateConditionalOutcome:
    values: _OutcomeValues = {
        "proposal_id": "cp1-example",
        "status": "filled_resolved",
        "evaluated_until": "2025-01-02T10:03:00Z",
        "order_expires_at": "2025-01-02T10:02:00Z",
        "stop_choice": "swing_low",
        "target_choice": "tp1",
        "fill_time": "2025-01-02T10:01:00Z",
        "fill_price": 100.5,
        "exit_time": "2025-01-02T10:02:00Z",
        "exit_price": 101.0,
        "exit_reason": "tp",
        "net_r": 1.0 / 3.0,
    }
    cast(Any, values).update(overrides)
    return CandidateConditionalOutcome(**values)


def test_outcome_identity_is_stable_and_bracket_specific() -> None:
    first = _outcome()
    same = _outcome()
    other_bracket = _outcome(target_choice="tp2")

    assert first.outcome_id == same.outcome_id
    assert first.outcome_id != other_bracket.outcome_id
    assert first.to_record()["schema_version"] == "candidate-conditional-outcome-v2"


def test_unresolved_fill_preserves_fill_without_return_label() -> None:
    outcome = _outcome(
        status="unresolved_data",
        evaluated_until="2025-01-02T10:01:00Z",
        exit_time=None,
        exit_price=None,
        exit_reason=None,
        net_r=None,
        unresolved_reason="target fell behind realized entry after a market gap",
    )

    assert outcome.fill_price == 100.5
    assert outcome.net_r is None
    assert outcome.unresolved_reason


def test_unfilled_order_requires_full_expiry() -> None:
    with pytest.raises(ValueError, match="before expiry"):
        _outcome(
            status="unfilled_expired",
            evaluated_until="2025-01-02T10:01:30Z",
            fill_time=None,
            fill_price=None,
            exit_time=None,
            exit_price=None,
            exit_reason=None,
            net_r=None,
        )

    outcome = _outcome(
        status="unfilled_expired",
        evaluated_until="2025-01-02T10:02:00Z",
        fill_time=None,
        fill_price=None,
        exit_time=None,
        exit_price=None,
        exit_reason=None,
        net_r=None,
    )
    assert outcome.net_r is None
    with pytest.raises(ValueError, match="cannot carry execution"):
        replace(outcome, net_r=0.1)


def test_order_censor_requires_cutoff_before_expiry() -> None:
    with pytest.raises(ValueError, match="must end before expiry"):
        _outcome(
            status="censored_order_horizon",
            evaluated_until="2025-01-02T10:02:00Z",
            fill_time=None,
            fill_price=None,
            exit_time=None,
            exit_price=None,
            exit_reason=None,
            net_r=None,
        )


def test_censored_exit_never_has_realized_return() -> None:
    with pytest.raises(ValueError, match="no realized exit label"):
        _outcome(
            status="censored_exit_horizon",
            evaluated_until="2025-01-02T10:02:00Z",
            exit_time=None,
            exit_price=None,
            exit_reason=None,
            net_r=0.0,
        )

    outcome = _outcome(
        status="censored_exit_horizon",
        evaluated_until="2025-01-02T10:02:00Z",
        exit_time=None,
        exit_price=None,
        exit_reason=None,
        net_r=None,
    )
    assert outcome.fill_time == "2025-01-02T10:01:00Z"
    assert outcome.fill_price == 100.5


def test_unresolved_fill_requires_both_timestamp_and_price() -> None:
    with pytest.raises(ValueError, match="both time and price"):
        _outcome(
            status="unresolved_data",
            evaluated_until="2025-01-02T10:01:00Z",
            fill_price=None,
            exit_time=None,
            exit_price=None,
            exit_reason=None,
            net_r=None,
            unresolved_reason="quote gap after a known fill",
        )


def test_resolved_outcome_requires_chronological_complete_execution() -> None:
    outcome = _outcome()
    assert outcome.estimand == "conditional_fixed_entry"
    assert outcome.to_record()["schema_version"] == "candidate-conditional-outcome-v2"

    with pytest.raises(ValueError, match="requires fill, exit, and net R"):
        replace(outcome, net_r=None)
    with pytest.raises(ValueError, match="resolved fill chronology"):
        replace(
            outcome,
            fill_time="2025-01-02T10:03:00Z",
            exit_time="2025-01-02T10:04:00Z",
        )
