import pytest

from decisioning.trade_setup import TRADE_SETUP_CANDIDATES
from evaluation.candidate_proposals import (
    CandidateProposal,
    build_decision_proposals,
)


def _proposal(**overrides: object) -> CandidateProposal:
    values: dict[str, object] = {
        "candidate_id": 3,
        "idea_family": "ifvg_retest",
        "source_timeframe": "M5",
        "direction": 1,
        "source_event_id": "event-abc",
        "signal_confirmed_at": "2025-01-02T10:00:00Z",
        "quote_observed_at": "2025-01-02T10:00:59Z",
        "valid_from": "2025-01-02T10:01:00Z",
        "expires_at": "2025-01-02T11:01:00Z",
        "entry_type": "limit",
        "proposed_entry_price": 100.5,
        "permissible_stop_choices": (("swing_low", 99.0), ("atr", 99.5)),
        "permissible_target_choices": (("tp1", 102.0), ("tp2", 103.0)),
        "price_increment": 0.25,
        "max_wait_seconds": 3600.0,
        "source_zone_low": 100.0,
        "source_zone_high": 101.0,
        "atr_scale": 2.0,
        "spread_at_proposal": 0.5,
    }
    values.update(overrides)
    return CandidateProposal(**values)  # type: ignore[arg-type]


def test_candidate_proposal_has_stable_identity_and_versioned_record() -> None:
    first = _proposal()
    second = _proposal()

    assert first.proposal_id == second.proposal_id
    assert first.to_record()["schema_version"] == "candidate-proposal-v2"
    assert first.to_record()["permissible_target_choices"] == (
        ("tp1", 102.0),
        ("tp2", 103.0),
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("signal_confirmed_at", "2025-01-02T10:00:00", "timezone"),
        ("valid_from", "2025-01-02T09:59:00Z", "before signal confirmation"),
        ("quote_observed_at", "2025-01-02T10:02:00Z", "after candidate validity begins"),
        ("expires_at", "2025-01-02T10:01:00Z", "after valid_from"),
        ("proposed_entry_price", 100.4, "align to price_increment"),
        ("permissible_stop_choices", (("invalid", 101.0),), "loss side"),
        (
            "permissible_target_choices",
            (("tp1", 102.0), ("tp2", 101.0)),
            "ordered away",
        ),
        ("proposed_entry_price", 101.5, "within its declared source zone"),
    ],
)
def test_candidate_proposal_rejects_invalid_causality_or_geometry(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _proposal(**{field: value})


def test_policy_eligible_proposal_requires_fill_and_session_deadline() -> None:
    with pytest.raises(ValueError, match="requires action fill and session close"):
        _proposal(policy_eligibility="eligible")

    eligible = _proposal(
        policy_eligibility="eligible",
        eligible_action_fill_time="2025-01-02T10:01:00Z",
        session_close_time="2025-01-02T16:00:00Z",
    )
    assert eligible.to_record()["policy_eligibility"] == "eligible"
    assert eligible.eligible_action_fill_time == "2025-01-02T10:01:00Z"

    with pytest.raises(ValueError, match="eligible action chronology"):
        _proposal(
            policy_eligibility="eligible",
            eligible_action_fill_time="2025-01-02T10:01:00Z",
            session_close_time="2025-01-02T10:01:00Z",
        )


def test_decision_proposals_build_market_and_pending_zone_entries_with_fresh_geometry() -> None:
    geometry_entries: list[float] = []

    def geometry_for_entry(
        entry: float,
    ) -> tuple[tuple[tuple[str, float], ...], tuple[tuple[str, float], ...]]:
        geometry_entries.append(entry)
        return (
            (("swing", entry - 1.0), ("atr", entry - 0.5)),
            (("tp1", entry + 2.0), ("tp2", entry + 3.0)),
        )

    proposals = build_decision_proposals(
        TRADE_SETUP_CANDIDATES[3],
        source_event_id="event-abc",
        signal_confirmed_at="2025-01-02T10:00:00Z",
        quote_observed_at="2025-01-02T10:00:59Z",
        valid_from="2025-01-02T10:01:00Z",
        expires_at="2025-01-02T11:01:00Z",
        bid=100.0,
        ask=100.5,
        price_increment=0.25,
        max_wait_seconds=3600.0,
        geometry_for_entry=geometry_for_entry,
        source_zone=(99.5, 100.25),
        atr_scale=2.0,
    )

    assert len(proposals) == 2
    assert [proposal.entry_type for proposal in proposals] == ["market", "limit"]
    assert [proposal.proposed_entry_price for proposal in proposals] == [100.5, 100.0]
    assert geometry_entries == [100.5, 100.0]
    assert all(proposal.source_event_id == "event-abc" for proposal in proposals)


def test_decision_proposals_omit_already_marketable_zone_limit_and_illegal_geometry() -> None:
    proposals = build_decision_proposals(
        TRADE_SETUP_CANDIDATES[3],
        source_event_id="event-abc",
        signal_confirmed_at="2025-01-02T10:00:00Z",
        quote_observed_at="2025-01-02T10:00:59Z",
        valid_from="2025-01-02T10:01:00Z",
        expires_at="2025-01-02T11:01:00Z",
        bid=100.0,
        ask=100.5,
        price_increment=0.25,
        max_wait_seconds=3600.0,
        geometry_for_entry=lambda _entry: None,
        source_zone=(100.5, 101.0),
    )

    assert proposals == ()
