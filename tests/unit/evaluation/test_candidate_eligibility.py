import pandas as pd

from evaluation.candidate_eligibility import (
    CandidateActionEligibilityIndex,
    classify_candidate_action_eligibility,
)


def _market() -> tuple[pd.DatetimeIndex, pd.Series, pd.Series]:
    index = pd.DatetimeIndex(
        [
            "2025-01-02T16:30:00Z",
            "2025-01-02T16:31:00Z",
            "2025-01-02T16:32:00Z",
            "2025-01-02T22:59:00Z",
            "2025-01-02T23:00:00Z",
            "2025-01-02T23:01:00Z",
            "2025-01-03T16:30:00Z",
            "2025-01-03T16:31:00Z",
            "2025-01-03T16:32:00Z",
        ]
    )
    sessions = pd.Series(["ny", "ny", "ny", "ny", "ny", "closed", "ny", "ny", "ny"])
    session_ids = pd.Series([1, 1, 1, 1, 1, 1, 2, 2, 2])
    return index, sessions, session_ids


def test_off_session_rows_are_classified_without_dropping_them() -> None:
    index, sessions, session_ids = _market()

    result = classify_candidate_action_eligibility(
        index, sessions, 5, session_ids=session_ids, open_manipulation_bars=0
    )

    assert not result.eligible
    assert result.reason == "off_session"


def test_open_blackout_is_counted_from_first_ny_bar() -> None:
    index, sessions, session_ids = _market()

    blackout = classify_candidate_action_eligibility(
        index, sessions, 1, session_ids=session_ids, open_manipulation_bars=2
    )
    eligible = classify_candidate_action_eligibility(
        index, sessions, 2, session_ids=session_ids, open_manipulation_bars=2
    )

    assert blackout.reason == "open_blackout"
    assert eligible.eligible
    assert eligible.fill_position == 3
    assert eligible.fill_time == index[3].isoformat()
    assert eligible.session_close_time == "2025-01-02T23:01:00+00:00"


def test_last_ny_bar_cannot_fill_outside_the_session() -> None:
    index, sessions, session_ids = _market()

    result = classify_candidate_action_eligibility(
        index, sessions, 4, session_ids=session_ids, open_manipulation_bars=0
    )

    assert result.reason == "fill_bar_off_session"

    penultimate_fill = classify_candidate_action_eligibility(
        index, sessions, 3, session_ids=session_ids, open_manipulation_bars=0
    )
    assert penultimate_fill.reason == "overnight_boundary"

    overnight_allowed = classify_candidate_action_eligibility(
        index,
        sessions,
        4,
        session_ids=session_ids,
        open_manipulation_bars=0,
        block_overnight=False,
    )
    assert overnight_allowed.eligible
    assert overnight_allowed.fill_position == 5


def test_fill_latency_that_crosses_sessions_is_rejected_when_blocked() -> None:
    index, sessions, session_ids = _market()

    blocked = classify_candidate_action_eligibility(
        index,
        sessions,
        3,
        session_ids=session_ids,
        fill_latency_bars=1,
        open_manipulation_bars=0,
        block_overnight=True,
    )
    allowed = classify_candidate_action_eligibility(
        index,
        sessions,
        3,
        session_ids=session_ids,
        fill_latency_bars=1,
        open_manipulation_bars=0,
        block_overnight=False,
    )

    assert blocked.reason == "overnight_boundary"
    assert allowed.eligible
    assert allowed.fill_position == 6


def test_precomputed_index_classifies_many_events_without_rebuilding_masks() -> None:
    index, sessions, session_ids = _market()
    eligibility = CandidateActionEligibilityIndex(
        index,
        sessions,
        session_ids=session_ids,
        open_manipulation_bars=0,
    )

    assert eligibility.classify(2).eligible
    assert eligibility.classify(3).reason == "overnight_boundary"
    assert eligibility.classify(5).reason == "off_session"
