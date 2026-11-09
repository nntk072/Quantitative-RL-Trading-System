from typing import Any

from scripts.research.audits.v3_campaign_gatekeeper import build_campaign_state


def _plan() -> dict[str, Any]:
    return {
        "survival_qualification": {
            "required_seeds": [42, 43, 44, 45, 46, 47],
            "minimum_unique_seeds": 6,
            "minimum_walk_forward_splits": 5,
        },
        "post_survival_review_gates": [
            "checkpoint_repeatability_review",
            "portfolio_objective_freeze_review",
            "primary_statistical_selection_review",
            "finalist_robustness_review",
            "finalist_freeze_review",
            "exposed_report_once_review",
            "metrics_evidence_refresh_review",
            "thesis_outputs_review",
            "documentation_cleanup_review",
            "final_release_review",
            "negative_result_release_review",
        ],
    }


def test_campaign_rejects_unbacked_readiness_summary_booleans() -> None:
    science = {
        "schema_version": "pretraining-scientific-readiness-v1",
        "status": "pass",
        "source_commit": "a" * 40,
        "source_clean": True,
        "scientific_training_authorized": True,
        "price_training_authorized": False,
    }
    state = build_campaign_state(
        plan=_plan(),
        scientific_readiness=science,
        survival_gate=None,
        phase_reviews={},
        source_commit="a" * 40,
        source_clean=True,
    )
    assert state["current_phase"] == "pretraining_scientific_readiness"
    assert state["scientific_readiness_valid"] is False
    assert state["scientific_readiness_errors"]
    assert state["survival_qualification_authorized"] is False
    assert state["price_survival_qualification_authorized"] is False


def test_malformed_failure_gate_cannot_disposition_survival_as_negative() -> None:
    science = {
        "schema_version": "pretraining-scientific-readiness-v1",
        "status": "pass",
        "source_commit": "a" * 40,
        "source_clean": True,
        "scientific_training_authorized": True,
        "price_training_authorized": False,
    }
    state = build_campaign_state(
        plan=_plan(),
        scientific_readiness=science,
        survival_gate={"schema_version": 1, "status": "fail"},
        phase_reviews={},
        source_commit="a" * 40,
        source_clean=True,
    )
    assert state["survival_phase_gate_status"] == "invalid"
    assert state["negative_result_release_ready"] is False
