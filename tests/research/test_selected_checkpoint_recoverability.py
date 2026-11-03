import hashlib
import json
from pathlib import Path

import pytest
import scripts.research.analysis.evidence.audit_selected_checkpoint_recoverability as audit
from scripts.research.analysis.evidence.audit_selected_checkpoint_recoverability import (
    build_report,
    stable_sha256,
)


def _freeze(path: Path, checkpoints: dict[str, tuple[str, str]]) -> Path:
    runs = {}
    for arm, (variant, checkpoint_sha) in checkpoints.items():
        runs[arm] = {
            "variant": variant,
            "seed": 50,
            "checkpoint_sha256": checkpoint_sha,
            "source_run": f"outputs/campaign/runs/{variant}__seed50/attempt3/run",
        }
    path.write_text(
        json.dumps(
            {
                "schema": "aalto.rq1_selected_pair_freeze.v1",
                "campaign": {"id": "selected-pair"},
                "runs": runs,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_report_hashes_only_name_matched_candidates_and_finds_exact_checkpoints(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "outputs"
    archive.mkdir()
    control_variant = "control_policy"
    treatment_variant = "treatment_policy"
    control_content = b"control checkpoint bytes"
    treatment_content = b"treatment checkpoint bytes"
    control = archive / "campaign" / f"{control_variant}__seed50" / "model.zip"
    treatment = archive / "campaign" / f"{treatment_variant}__seed50" / "model.zip"
    unrelated = archive / "campaign" / "other_policy__seed50" / "model.zip"
    prefix_collision = archive / "campaign" / "control_policy_extended__seed50" / "model.zip"
    for path, content in (
        (control, control_content),
        (treatment, treatment_content),
        (unrelated, b"not a candidate"),
        (prefix_collision, b"not the frozen variant"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    freeze = _freeze(
        tmp_path / "freeze.json",
        {
            "control": (control_variant, hashlib.sha256(control_content).hexdigest()),
            "treatment": (treatment_variant, hashlib.sha256(treatment_content).hexdigest()),
        },
    )

    report = build_report(freeze, archive)

    assert report["scope"]["archive_paths_inspected"] == 2
    assert report["arms"]["control"]["exact_match_paths"] == [
        "campaign/control_policy__seed50/model.zip"
    ]
    assert report["arms"]["treatment"]["exact_match_count"] == 1
    assert report["disposition"].startswith("both frozen checkpoints have exact")


def test_report_records_missing_exact_hash_without_global_absence_claim(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "outputs"
    candidate = archive / "campaign/control_policy__seed50/model.zip"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"different checkpoint")
    freeze = _freeze(
        tmp_path / "freeze.json",
        {
            "control": ("control_policy", hashlib.sha256(b"expected").hexdigest()),
            "treatment": ("treatment_policy", hashlib.sha256(b"also expected").hexdigest()),
        },
    )

    report = build_report(freeze, archive)

    assert report["arms"]["control"]["targeted_candidate_count"] == 1
    assert report["arms"]["control"]["exact_match_count"] == 0
    assert report["arms"]["treatment"]["targeted_candidate_count"] == 0
    assert report["scope"]["full_scratch_search"] is False
    assert any("No global absence claim" in item for item in report["limitations"])


def test_stable_hash_returns_digest_for_unchanged_checkpoint(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.zip"
    candidate.write_bytes(b"checkpoint")

    assert stable_sha256(candidate) == hashlib.sha256(b"checkpoint").hexdigest()


def test_report_fails_closed_when_archive_root_is_missing(tmp_path: Path) -> None:
    freeze = _freeze(
        tmp_path / "freeze.json",
        {
            "control": ("control_policy", hashlib.sha256(b"control").hexdigest()),
            "treatment": ("treatment_policy", hashlib.sha256(b"treatment").hexdigest()),
        },
    )

    with pytest.raises(FileNotFoundError, match="archive root is not a directory"):
        build_report(freeze, tmp_path / "missing_archive")


def test_stable_hash_rejects_checkpoint_changed_during_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = tmp_path / "candidate.zip"
    candidate.write_bytes(b"original checkpoint")

    def hash_then_replace(path: Path) -> str:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        path.write_bytes(b"replacement checkpoint")
        return digest

    monkeypatch.setattr(audit, "sha256", hash_then_replace)

    with pytest.raises(RuntimeError, match="changed while hashing"):
        stable_sha256(candidate)
