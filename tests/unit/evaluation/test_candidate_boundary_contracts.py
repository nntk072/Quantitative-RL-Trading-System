"""Candidate records and indexes reject incomplete or ambiguous evidence."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pytest

from evaluation.candidate_eligibility import CandidateActionEligibilityIndex
from evaluation.candidate_outcomes import CandidateConditionalOutcome
from evaluation.candidate_proposals import CandidateProposal
from evaluation.candidate_quote_coverage import CandidateQuoteCoverage


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
        "permissible_stop_choices": (("swing_low", 99.0),),
        "permissible_target_choices": (("tp1", 102.0),),
        "price_increment": 0.25,
        "max_wait_seconds": 3600.0,
        "source_zone_low": 100.0,
        "source_zone_high": 101.0,
    }
    values.update(overrides)
    return CandidateProposal(**values)  # type: ignore[arg-type]


def _outcome(**overrides: object) -> CandidateConditionalOutcome:
    values: dict[str, object] = {
        "proposal_id": "cp2-example",
        "status": "filled_resolved",
        "evaluated_until": "2025-01-02T10:03:00Z",
        "order_expires_at": "2025-01-02T10:02:00Z",
        "stop_choice": "swing_low",
        "target_choice": "tp1",
        "fill_time": "2025-01-02T10:01:00Z",
        "fill_price": 100.5,
        "exit_time": "2025-01-02T10:02:00Z",
        "exit_price": 102.0,
        "exit_reason": "tp",
        "net_r": 1.0,
    }
    values.update(overrides)
    return CandidateConditionalOutcome(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"candidate_id": True}, "candidate_id must identify"),
        ({"spread_at_proposal": float("nan")}, "spread_at_proposal must be finite"),
        ({"source_zone_high": None}, "source zone requires both low and high"),
        (
            {"permissible_stop_choices": (("same", 99.0), ("same", 98.0))},
            "choice names must be unique",
        ),
    ],
)
def test_candidate_proposal_rejects_ambiguous_or_nonfinite_identity_inputs(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _proposal(**overrides)


def test_conditional_outcome_rejects_unknown_schema_and_nonfinite_return() -> None:
    with pytest.raises(ValueError, match="unsupported conditional outcome schema"):
        _outcome(schema_version="candidate-conditional-outcome.v1")
    with pytest.raises(ValueError, match="net_r must be finite"):
        _outcome(net_r=float("inf"))

    with pytest.raises(ValueError, match="must include a timezone"):
        _outcome(evaluated_until="2025-01-02T10:03:00")


def test_candidate_eligibility_requires_aligned_sorted_unique_inputs() -> None:
    index = pd.date_range("2025-01-02 16:30", periods=3, freq="min", tz="UTC")
    labels = pd.Series(["ny", "ny", "ny"])

    with pytest.raises(ValueError, match="sorted unique"):
        CandidateActionEligibilityIndex(index[[0, 0, 2]], labels)
    with pytest.raises(ValueError, match="session_labels must align"):
        CandidateActionEligibilityIndex(index, labels.iloc[:2])

    eligibility = CandidateActionEligibilityIndex(index, labels)
    with pytest.raises(ValueError, match="outside the bar index"):
        eligibility.classify(True)
    with pytest.raises(ValueError, match="outside the bar index"):
        eligibility.classify(3)


@pytest.mark.parametrize(
    "frame",
    [
        pd.DataFrame({"bar_open_source_wall_clock": ["2025-01-02 16:00"]}),
        pd.DataFrame(
            {
                "bar_open_source_wall_clock": ["2025-01-02 16:01", "2025-01-02 16:00"],
                "quote_complete": [True, True],
            }
        ),
    ],
)
def test_quote_coverage_rejects_missing_or_unordered_minute_evidence(
    tmp_path: Path, frame: pd.DataFrame
) -> None:
    path = tmp_path / "coverage.csv"
    frame.to_csv(path, index=False)

    with pytest.raises(ValueError, match="contain rows and quote_complete|sorted and unique"):
        CandidateQuoteCoverage.from_csv(path, timezone="UTC")


def test_replacing_a_valid_candidate_outcome_keeps_immutable_input_contract() -> None:
    outcome = _outcome()

    with pytest.raises(ValueError, match="unsupported conditional outcome status"):
        replace(outcome, status=cast(Any, "unresolved"))
