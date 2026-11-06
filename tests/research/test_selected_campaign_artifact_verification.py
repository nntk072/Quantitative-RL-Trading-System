"""Tests for selected campaign source and checkpoint byte verification."""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts.research.analysis.evidence import verify_selected_campaign_artifacts as verify


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    repo = tmp_path / "Quantitative-RL-Trading-System"
    archive = tmp_path / "Quantitative-RL-Trading-System-research-archive"
    repo.mkdir()
    archive.mkdir()
    (repo / "outputs").symlink_to(archive / "outputs", target_is_directory=True)
    campaign_id = "campaign_demo"
    campaign_dir = archive / "outputs/gpu_campaigns" / campaign_id
    campaign_dir.mkdir(parents=True)

    source_file = b"source implementation\n"
    source_manifest_bytes = json.dumps(
        {
            "schema_version": 1,
            "git_sha": "a" * 40,
            "files": {"features/demo.py": hashlib.sha256(source_file).hexdigest()},
        },
        sort_keys=True,
    ).encode()
    snapshot_path = campaign_dir / "source_snapshot.zip"
    with zipfile.ZipFile(snapshot_path, "w", compression=zipfile.ZIP_DEFLATED) as snapshot:
        snapshot.writestr("features/demo.py", source_file)
        snapshot.writestr("source_manifest.json", source_manifest_bytes)
    campaign = {
        "fingerprint": "campaign-fingerprint",
        "git_sha": "a" * 40,
        "source_snapshot": {
            "path": "source_snapshot.zip",
            "sha256": _sha256(snapshot_path),
            "manifest_sha256": hashlib.sha256(source_manifest_bytes).hexdigest(),
            "file_count": 1,
        },
    }
    campaign_json = campaign_dir / "campaign.json"
    campaign_json.write_text(json.dumps(campaign), encoding="utf-8")

    runs = []
    for arm in ("A4A", "A4B"):
        run_dir = campaign_dir / "runs" / arm
        run_dir.mkdir(parents=True)
        checkpoint_path = run_dir / "model/ppo_final.zip"
        checkpoint_path.parent.mkdir()
        checkpoint_path.write_bytes(f"{arm} checkpoint".encode())
        config_path = run_dir / "config.yaml"
        config_path.write_text(f"arm: {arm}\n", encoding="utf-8")
        run_manifest_path = run_dir / "run_manifest.json"
        run_manifest_path.write_text(
            json.dumps(
                {
                    "source": {"head": "b" * 40},
                    "checkpoint": {
                        "path": str(checkpoint_path),
                        "sha256": _sha256(checkpoint_path),
                    },
                    "config": {"path": str(config_path), "sha256": _sha256(config_path)},
                    "feature_cache": {"path": str(repo / "cache/missing.parquet")},
                }
            ),
            encoding="utf-8",
        )
        run_id = f"{campaign_id}/{arm}/seed50"
        runs.append(
            {
                "run_id": run_id,
                "identity": {"source_commit": "b" * 40},
                "artifacts": [
                    {
                        "role": "run_manifest",
                        "path": f"outputs/gpu_campaigns/{campaign_id}/runs/{arm}/run_manifest.json",
                        "sha256": _sha256(run_manifest_path),
                    },
                    {
                        "role": "resolved_run_config",
                        "path": f"outputs/gpu_campaigns/{campaign_id}/runs/{arm}/config.yaml",
                        "sha256": _sha256(config_path),
                    },
                ],
            }
        )

    manifest_path = repo / "selected_pair_viability_manifest.json"
    manifest_path.write_text(
        json.dumps({"schema": "qrl.research_result_manifest.v2", "runs": runs}),
        encoding="utf-8",
    )
    registry_path = repo / "CHECKPOINT_REGISTRY.json"
    registry_path.write_text(
        json.dumps(
            {
                "campaign_path": f"outputs/gpu_campaigns/{campaign_id}",
                "campaign_fingerprint": "campaign-fingerprint",
                "checkpoints": [{"arm": "A4A"}, {"arm": "A4B"}],
            }
        ),
        encoding="utf-8",
    )
    return repo, archive, manifest_path, registry_path, campaign_json


def _mock_git(monkeypatch: pytest.MonkeyPatch) -> None:
    def run(args: list[str], **_: object) -> SimpleNamespace:
        if args[1] == "rev-parse":
            return SimpleNamespace(returncode=0, stdout="c" * 40 + "\n")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(subprocess, "run", run)


def test_build_report_verifies_source_snapshot_and_both_checkpoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, archive, manifest, registry, _ = _fixture(tmp_path)
    _mock_git(monkeypatch)

    report = verify.build_report(manifest, registry, repo_root=repo, archive_root=archive)

    assert report["status"] == "passed_with_scoped_limits"
    assert report["source_snapshot"]["manifested_file_count"] == 1
    assert report["source_snapshot"]["manifested_file_hashes_match"] == 1
    assert {run["arm"] for run in report["runs"]} == {"A4A", "A4B"}
    assert all(run["final_checkpoint"]["sha256"] for run in report["runs"])
    assert all(not run["feature_cache_at_recorded_path_exists"] for run in report["runs"])


def test_build_report_rejects_changed_checkpoint_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, archive, manifest, registry, campaign_json = _fixture(tmp_path)
    checkpoint = campaign_json.parent / "runs/A4A/model/ppo_final.zip"
    checkpoint.write_bytes(b"changed checkpoint")
    _mock_git(monkeypatch)

    with pytest.raises(verify.VerificationError, match="final checkpoint SHA-256 mismatch"):
        verify.build_report(manifest, registry, repo_root=repo, archive_root=archive)


def test_build_report_rejects_source_snapshot_member_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, archive, manifest, registry, campaign_json = _fixture(tmp_path)
    snapshot_path = campaign_json.parent / "source_snapshot.zip"
    with zipfile.ZipFile(snapshot_path, "a") as snapshot:
        snapshot.writestr("features/extra.py", b"unlisted")
    campaign = json.loads(campaign_json.read_text(encoding="utf-8"))
    campaign["source_snapshot"]["sha256"] = _sha256(snapshot_path)
    campaign_json.write_text(json.dumps(campaign), encoding="utf-8")
    _mock_git(monkeypatch)

    with pytest.raises(verify.VerificationError, match="members differ from its manifest"):
        verify.build_report(manifest, registry, repo_root=repo, archive_root=archive)


def test_build_report_rejects_archived_path_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, archive, manifest, registry, _ = _fixture(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["runs"][0]["artifacts"][0]["path"] = "../../outside/run_manifest.json"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    _mock_git(monkeypatch)

    with pytest.raises(verify.VerificationError, match="resolved artifact escapes approved roots"):
        verify.build_report(manifest, registry, repo_root=repo, archive_root=archive)
