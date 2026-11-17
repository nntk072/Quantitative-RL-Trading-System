from __future__ import annotations

from pathlib import Path

from research_tools.studies.handlers.features import _causal_availability


def test_causal_audit_blocks_when_candidate_identity_inputs_are_missing(tmp_path: Path) -> None:
    report = _causal_availability(tmp_path, tmp_path / "audit-output")

    assert report["diagnostic_status"] == "blocked_missing_input"
    assert "candidate" in report["required_input"]
