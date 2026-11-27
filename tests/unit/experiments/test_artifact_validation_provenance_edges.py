"""Admission rejects incomplete or mismatched experiment attempt evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from experiments.runs.artifact_validation import verify_run_artifacts


@pytest.mark.parametrize("contents", [None, "{"])
def test_artifact_admission_rejects_missing_or_invalid_provenance(
    tmp_path: Path, contents: str | None
) -> None:
    run = tmp_path / "attempt"
    run.mkdir()
    if contents is not None:
        (run / "attempt_provenance.json").write_text(contents, encoding="utf-8")

    admitted, reason = verify_run_artifacts(
        run,
        "variant__seed7",
        100,
        expected_fingerprint="a" * 64,
        expected_attempt=1,
    )

    assert admitted is False
    assert reason == "missing or invalid attempt_provenance.json"


def test_artifact_admission_rejects_provenance_identity_that_omits_the_requested_run(
    tmp_path: Path,
) -> None:
    identity = {"steps": 100, "jobs": ["other__seed7"]}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    (tmp_path / "attempt_provenance.json").write_text(
        json.dumps(
            {
                "run_key": "variant__seed7",
                "variant": "variant",
                "seed": 7,
                "requested_timesteps": 100,
                "attempt": 1,
                "experiment_run_fingerprint": fingerprint,
                "identity": identity,
            }
        ),
        encoding="utf-8",
    )

    admitted, reason = verify_run_artifacts(
        tmp_path,
        "variant__seed7",
        100,
        expected_fingerprint=fingerprint,
        expected_attempt=1,
    )

    assert admitted is False
    assert reason == "attempt provenance identity does not include the requested run"


def test_artifact_admission_skips_corrupt_logs_and_reports_missing_training_record(
    tmp_path: Path,
) -> None:
    run = tmp_path / "attempt"
    run.mkdir()
    identity = {"steps": 100, "jobs": ["variant__seed7"]}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    (run / "attempt_provenance.json").write_text(
        json.dumps(
            {
                "run_key": "variant__seed7",
                "variant": "variant",
                "seed": 7,
                "requested_timesteps": 100,
                "attempt": 1,
                "experiment_run_fingerprint": fingerprint,
                "identity": identity,
            }
        ),
        encoding="utf-8",
    )
    (run / "training_log.json").write_text("not json", encoding="utf-8")

    admitted, reason = verify_run_artifacts(
        run,
        "variant__seed7",
        100,
        expected_fingerprint=fingerprint,
        expected_attempt=1,
    )

    assert admitted is False
    assert reason == "missing valid training record/checkpoint at requested 100 steps"
