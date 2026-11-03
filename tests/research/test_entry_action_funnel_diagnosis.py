"""Focused rendering checks for the entry-action funnel diagnosis."""

from __future__ import annotations

from scripts.research.analysis.evidence.analyze_entry_action_funnel import render_report


def test_report_uses_arm_specific_unarmed_request_shares() -> None:
    """The narrative percentages must derive from the supplied machine data."""
    diagnosis = {
        "arms": [
            {
                "role": "treatment",
                "entry_attempts": 10,
                "rejected_entry_state": 8,
                "unarmed_request_share": 0.8,
                "entry_opened": 2,
                "entry_open_rate": 0.2,
                "candidate_created": 4,
                "candidate_invalidated": 2,
                "trigger_refused": 1,
                "trigger_requested": 3,
                "trigger_refusal_share": 1 / 3,
                "rejection_counts": {
                    "rejected_cooldown": 1,
                    "rejected_sl": 0,
                    "rejected_rr": 0,
                    "rejected_overnight": 0,
                },
            },
            {
                "role": "control",
                "entry_attempts": 20,
                "rejected_entry_state": 10,
                "unarmed_request_share": 0.5,
                "entry_opened": 10,
                "entry_open_rate": 0.5,
                "candidate_created": 12,
                "candidate_invalidated": 2,
                "trigger_refused": 2,
                "trigger_requested": 12,
                "trigger_refusal_share": 1 / 6,
                "rejection_counts": {
                    "rejected_cooldown": 0,
                    "rejected_sl": 1,
                    "rejected_rr": 1,
                    "rejected_overnight": 0,
                },
            },
        ],
        "interpretation_limit": "diagnostic only",
    }

    report = render_report(diagnosis)

    assert "80.0% of treatment requests and 50.0% of control requests" in report
    assert "2025 training split" in report
    assert "do not support a performance claim" in report
