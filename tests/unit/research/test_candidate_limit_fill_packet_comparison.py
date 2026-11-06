from __future__ import annotations

import pandas as pd
import pytest
from scripts.research.analysis.evaluation.compare_candidate_limit_fill_packets import (
    compare_limit_fill_frames,
)


def test_candidate_limit_fill_comparison_pairs_status_and_resolved_return() -> None:
    exact = pd.DataFrame(
        [
            {"proposal_id": "p1", "outcome_id": "o1", "status": "filled_resolved", "net_r": 1.0},
            {
                "proposal_id": "p2",
                "outcome_id": "o2",
                "status": "unresolved_data",
                "net_r": float("nan"),
            },
            {"proposal_id": "p3", "outcome_id": "o3", "status": "filled_resolved", "net_r": 0.5},
        ]
    )
    strict = pd.DataFrame(
        [
            {
                "proposal_id": "p1",
                "outcome_id": "o1",
                "status": "unfilled_expired",
                "net_r": float("nan"),
            },
            {"proposal_id": "p2", "outcome_id": "o2", "status": "filled_resolved", "net_r": 0.4},
            {"proposal_id": "p3", "outcome_id": "o3", "status": "filled_resolved", "net_r": 0.25},
        ]
    )

    report = compare_limit_fill_frames(exact, strict)

    assert report["paired_limit_outcome_count"] == 3
    assert report["status_transitions"] == {
        "filled_resolved -> filled_resolved": 1,
        "filled_resolved -> unfilled_expired": 1,
        "unresolved_data -> filled_resolved": 1,
    }
    assert report["both_resolved_count"] == 1
    assert report["strict_minus_exact_net_r"]["mean"] == -0.25
    assert report["policy_value_claim"] is False


def test_candidate_limit_fill_comparison_rejects_unpaired_identities() -> None:
    exact = pd.DataFrame(
        [{"proposal_id": "p1", "outcome_id": "o1", "status": "filled_resolved", "net_r": 1.0}]
    )
    strict = pd.DataFrame(
        [{"proposal_id": "p1", "outcome_id": "o2", "status": "filled_resolved", "net_r": 1.0}]
    )

    with pytest.raises(ValueError, match="identities differ"):
        compare_limit_fill_frames(exact, strict)


def test_candidate_limit_fill_comparison_rejects_cross_proposal_pairing() -> None:
    exact = pd.DataFrame(
        [{"proposal_id": "p1", "outcome_id": "o1", "status": "filled_resolved", "net_r": 1.0}]
    )
    strict = pd.DataFrame(
        [{"proposal_id": "p2", "outcome_id": "o1", "status": "filled_resolved", "net_r": 1.0}]
    )

    with pytest.raises(ValueError, match="different candidate proposals"):
        compare_limit_fill_frames(exact, strict)
