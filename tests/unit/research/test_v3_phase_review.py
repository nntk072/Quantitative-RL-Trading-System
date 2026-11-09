from pathlib import Path

import pytest
from scripts.research.audits.record_v3_phase_review import build_phase_review


def test_phase_review_can_freeze_direct_experiment_commands(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    record = build_phase_review(
        gate_id="portfolio_objective_freeze_review",
        status="pass",
        source_commit="a" * 40,
        reviewed_by="reviewer",
        reviewed_at_utc="2026-11-09T15:00:00Z",
        evidence_paths=[evidence],
        exposed_report_period_used_for_selection=False,
        preregistered_thresholds_changed_post_hoc=False,
        incompatible_source_or_config_identity_accepted=False,
        claim="objective and direct command frozen",
        note="reviewed",
        frozen_commands=[
            {
                "id": "portfolio_seed42",
                "argv": [".venv/bin/python", "-m", "training.runner.training"],
                "depends_on": [],
                "resource_lock": "GPU_TRAIN_LOCK",
                "artifact_roots": ["/scratch/out"],
                "experiment": True,
            }
        ],
        frozen_parameters={"objective": "prospectively frozen"},
    )
    assert record["frozen_commands"][0]["experiment"] is True


def test_phase_review_rejects_scheduler_commands(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Slurm|scheduler"):
        build_phase_review(
            gate_id="x",
            status="pass",
            source_commit="a" * 40,
            reviewed_by="reviewer",
            reviewed_at_utc="2026-11-09T15:00:00Z",
            evidence_paths=[evidence],
            exposed_report_period_used_for_selection=False,
            preregistered_thresholds_changed_post_hoc=False,
            incompatible_source_or_config_identity_accepted=False,
            claim="x",
            note="x",
            frozen_commands=[{"id": "bad", "argv": ["srun", "echo", "x"]}],
        )
