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


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", "candidate-proposal-v1", "unsupported candidate proposal schema"),
        ("candidate_id", 0, "non-no-trade setup"),
        ("candidate_id", True, "non-no-trade setup"),
        ("direction", 0, "direction must be -1 or 1"),
        ("idea_family", " ", "idea_family and source_timeframe are required"),
        ("source_event_id", "", "source_event_id is required"),
        ("source_geometry_id", " ", "source_geometry_id is required"),
        ("entry_type", "stop", "entry_type must be market or limit"),
        ("max_wait_seconds", 30.0, "expiry cannot exceed its declared maximum wait"),
        ("price_increment", 0.0, "must be positive"),
        ("permissible_stop_choices", (), "at least one legal stop and target"),
        ("permissible_target_choices", (), "at least one legal stop and target"),
        (
            "permissible_stop_choices",
            (("stop", 99.0), ("stop", 98.0)),
            "names must be unique",
        ),
        (
            "permissible_target_choices",
            (("target", 102.0), ("target", 103.0)),
            "names must be unique",
        ),
        ("permissible_stop_choices", (("", 99.0),), "require named finite prices"),
        ("permissible_target_choices", (("target", float("nan")),), "require named finite prices"),
        ("permissible_stop_choices", (("stop", 99.1),), "align to price_increment"),
        ("permissible_target_choices", (("target", 99.0),), "beyond entry"),
        ("source_zone_low", None, "requires both low and high"),
        ("source_zone_low", 102.0, "bounds must be ordered"),
        ("atr_scale", 0.0, "atr_scale must be positive"),
        ("spread_at_proposal", -0.1, "cannot be negative"),
        ("latency_estimate_ms", -1.0, "cannot be negative"),
        ("estimated_round_trip_cost_points", -1.0, "cannot be negative"),
        ("current_regime", " ", "must be explicit or 'unknown'"),
        ("policy_eligibility", "unknown", "must be eligible or not_evaluated"),
        (
            "eligible_action_fill_time",
            "2025-01-02T10:01:00Z",
            "cannot carry eligibility times",
        ),
    ],
)
def test_candidate_proposal_rejects_invalid_identity_geometry_and_metadata(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _proposal(**{field: value})


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {
                "policy_eligibility": "eligible",
                "eligible_action_fill_time": "2025-01-02T10:00:59Z",
                "session_close_time": "2025-01-02T16:00:00Z",
            },
            "eligible action chronology",
        ),
        (
            {
                "policy_eligibility": "eligible",
                "eligible_action_fill_time": "2025-01-02T10:01:00Z",
                "session_close_time": "2025-01-02T16:00:00",
            },
            "session_close_time must include a timezone",
        ),
    ],
)
def test_candidate_proposal_rejects_invalid_eligibility_chronology(
    overrides: dict[str, str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _proposal(**overrides)


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


def test_decision_proposals_can_omit_market_entry_and_reject_invalid_zone() -> None:
    geometry_entries: list[float] = []

    def record_geometry_entry(entry: float) -> None:
        geometry_entries.append(entry)

    proposals = build_decision_proposals(
        TRADE_SETUP_CANDIDATES[3],
        source_event_id="event-abc",
        signal_confirmed_at="2025-01-02T10:00:00Z",
        quote_observed_at="2025-01-02T10:00:59Z",
        valid_from="2025-01-02T10:01:00Z",
        expires_at="2025-01-02T10:02:00Z",
        bid=100.0,
        ask=100.5,
        price_increment=0.25,
        max_wait_seconds=60.0,
        geometry_for_entry=record_geometry_entry,
        include_market=False,
    )

    assert proposals == ()
    assert geometry_entries == []
    with pytest.raises(ValueError, match="source zone bounds must be ordered"):
        build_decision_proposals(
            TRADE_SETUP_CANDIDATES[3],
            source_event_id="event-abc",
            signal_confirmed_at="2025-01-02T10:00:00Z",
            quote_observed_at="2025-01-02T10:00:59Z",
            valid_from="2025-01-02T10:01:00Z",
            expires_at="2025-01-02T10:02:00Z",
            bid=100.0,
            ask=100.5,
            price_increment=0.25,
            max_wait_seconds=60.0,
            geometry_for_entry=lambda _entry: None,
            source_zone=(101.0, 100.0),
        )


def test_short_proposals_use_bid_market_entry_and_resting_zone_limit_geometry() -> None:
    short_candidate = next(
        candidate
        for candidate in TRADE_SETUP_CANDIDATES
        if not candidate.is_no_trade and candidate.direction == -1
    )
    geometry_entries: list[float] = []

    def geometry_for_entry(
        entry: float,
    ) -> tuple[tuple[tuple[str, float], ...], tuple[tuple[str, float], ...]]:
        geometry_entries.append(entry)
        return (("swing", entry + 1.0),), (("target", entry - 2.0),)

    proposals = build_decision_proposals(
        short_candidate,
        source_event_id="short-event",
        signal_confirmed_at="2025-01-02T10:00:00Z",
        quote_observed_at="2025-01-02T10:00:59Z",
        valid_from="2025-01-02T10:01:00Z",
        expires_at="2025-01-02T10:02:00Z",
        bid=100.0,
        ask=100.5,
        price_increment=0.25,
        max_wait_seconds=60.0,
        geometry_for_entry=geometry_for_entry,
        source_zone=(100.5, 101.0),
    )

    assert [proposal.entry_type for proposal in proposals] == ["market", "limit"]
    assert [proposal.proposed_entry_price for proposal in proposals] == [100.0, 100.75]
    assert geometry_entries == [100.0, 100.75]
    assert all(
        proposal.permissible_stop_choices[0][1] > proposal.proposed_entry_price
        for proposal in proposals
    )
    assert all(
        proposal.permissible_target_choices[0][1] < proposal.proposed_entry_price
        for proposal in proposals
    )


@pytest.mark.parametrize(
    ("bid", "ask", "price_increment", "message"),
    [
        (0.0, 100.5, 0.25, "quote must be positive and non-crossed"),
        (100.5, 100.0, 0.25, "quote must be positive and non-crossed"),
        (100.0, 100.5, 0.0, "price_increment must be positive"),
    ],
)
def test_decision_proposals_reject_non_executable_quote_geometry(
    bid: float, ask: float, price_increment: float, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        build_decision_proposals(
            TRADE_SETUP_CANDIDATES[3],
            source_event_id="event-abc",
            signal_confirmed_at="2025-01-02T10:00:00Z",
            quote_observed_at="2025-01-02T10:00:59Z",
            valid_from="2025-01-02T10:01:00Z",
            expires_at="2025-01-02T11:01:00Z",
            bid=bid,
            ask=ask,
            price_increment=price_increment,
            max_wait_seconds=3600.0,
            geometry_for_entry=lambda _entry: (
                (("stop", 99.0),),
                (("target", 102.0),),
            ),
        )


def test_no_trade_setup_never_produces_an_executable_proposal() -> None:
    no_trade = next(candidate for candidate in TRADE_SETUP_CANDIDATES if candidate.is_no_trade)

    with pytest.raises(ValueError, match="NO_TRADE does not produce"):
        build_decision_proposals(
            no_trade,
            source_event_id="no-trade-event",
            signal_confirmed_at="2025-01-02T10:00:00Z",
            quote_observed_at="2025-01-02T10:00:59Z",
            valid_from="2025-01-02T10:01:00Z",
            expires_at="2025-01-02T11:01:00Z",
            bid=100.0,
            ask=100.5,
            price_increment=0.25,
            max_wait_seconds=3600.0,
            geometry_for_entry=lambda _entry: pytest.fail("no-trade geometry must not be built"),
        )
