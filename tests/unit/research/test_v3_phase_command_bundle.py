from pathlib import Path

from scripts.research.audits.build_v3_phase_command_bundle import build_bundle


def test_phase_bundle_is_bound_to_reviewed_source_and_commands(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    import hashlib

    review = {
        "schema_version": "v3-phase-review-v2",
        "status": "pass",
        "source_commit": "a" * 40,
        "gate_id": "portfolio_objective_freeze_review",
        "claim": "frozen",
        "reviewed_at_utc": "2026-11-09T15:00:00Z",
        "frozen_parameters": {"objective": "x"},
        "evidence": [
            {
                "path": str(evidence),
                "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
            }
        ],
        "frozen_commands": [
            {
                "id": "portfolio_seed42",
                "argv": ["python", "-c", "print('ok')"],
                "depends_on": [],
                "artifact_roots": [],
                "experiment": True,
            }
        ],
    }
    bundle = build_bundle(review, source_sha="a" * 40, source_clean=True)
    assert bundle["phase"] == "portfolio_objective_freeze_review"
    assert bundle["commands"][0]["experiment"] is True
