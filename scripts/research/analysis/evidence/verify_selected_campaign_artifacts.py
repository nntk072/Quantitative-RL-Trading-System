#!/usr/bin/env python3
"""Verify retained source, run, config, and checkpoint bytes for a selected campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_MANIFEST = (
    ROOT
    / "evidence/research/releases/negative-evidence-readiness/selected_pair_viability_manifest.json"
)
DEFAULT_REGISTRY = (
    ROOT / "evidence/research/releases/negative-evidence-readiness/CHECKPOINT_REGISTRY.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "evidence/research/releases/negative-evidence-readiness/selected_campaign_artifact_integrity.json"
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class VerificationError(ValueError):
    """Raised when a selected campaign artifact fails identity verification."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_sha256(path: Path) -> tuple[str, int]:
    """Hash a file only when its identity and size stay stable during the read."""
    before = path.stat()
    digest = _sha256(path)
    after = path.stat()
    before_identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if before_identity != after_identity:
        raise VerificationError(f"file changed while hashing: {path}")
    return digest, after.st_size


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _resolve_archived_path(
    value: str,
    *,
    repo_root: Path,
    archive_root: Path,
) -> tuple[Path, str]:
    """Resolve an artifact through the checkout outputs link or archive root."""
    candidate = Path(value)
    lexical = candidate if candidate.is_absolute() else repo_root / candidate
    if candidate.is_absolute():
        try:
            lexical.relative_to(repo_root)
        except ValueError:
            try:
                lexical.relative_to(archive_root)
            except ValueError as exc:
                raise VerificationError(
                    f"artifact path is outside approved roots: {value}"
                ) from exc
    resolved = lexical.resolve()
    try:
        relative = _relative_path(resolved, archive_root)
        return resolved, f"archive/{relative}"
    except ValueError:
        try:
            relative = _relative_path(resolved, repo_root)
        except ValueError as exc:
            raise VerificationError(f"resolved artifact escapes approved roots: {value}") from exc
        return resolved, relative


def _require_hash(path: Path, expected: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(expected, str) or not SHA256_PATTERN.fullmatch(expected):
        raise VerificationError(f"{label} has no valid SHA-256 identity")
    if not path.is_file():
        raise FileNotFoundError(f"{label} is unavailable: {path}")
    actual, size = _stable_sha256(path)
    if actual != expected:
        raise VerificationError(f"{label} SHA-256 mismatch: expected {expected}, got {actual}")
    return {"sha256": actual, "size_bytes": size}


def _git_is_ancestor(older: str, newer: str, *, repo_root: Path) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        raise VerificationError(f"git could not compare source revisions {older} and {newer}")
    return result.returncode == 0


def _verify_source_snapshot(
    snapshot_path: Path,
    snapshot_record: dict[str, Any],
    *,
    campaign_git_sha: str,
) -> dict[str, Any]:
    snapshot_hash = _require_hash(
        snapshot_path, snapshot_record.get("sha256"), label="campaign source snapshot"
    )
    with zipfile.ZipFile(snapshot_path) as archive:
        member_names = {name for name in archive.namelist() if not name.endswith("/")}
        if "source_manifest.json" not in member_names:
            raise VerificationError("source snapshot lacks source_manifest.json")
        manifest_bytes = archive.read("source_manifest.json")
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        expected_manifest_hash = snapshot_record.get("manifest_sha256")
        if manifest_hash != expected_manifest_hash:
            raise VerificationError("embedded source manifest SHA-256 mismatch")
        source_manifest = json.loads(manifest_bytes)
        files = source_manifest.get("files")
        if not isinstance(files, dict):
            raise VerificationError("embedded source manifest files field must be a mapping")
        if source_manifest.get("git_sha") != campaign_git_sha:
            raise VerificationError("campaign and embedded source manifest commits differ")
        expected_members = set(files) | {"source_manifest.json"}
        if member_names != expected_members:
            raise VerificationError(
                "source snapshot members differ from its manifest: "
                f"missing={sorted(expected_members - member_names)[:5]}, "
                f"extra={sorted(member_names - expected_members)[:5]}"
            )
        mismatches: list[str] = []
        for name, expected in files.items():
            member_path = PurePosixPath(name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise VerificationError(f"unsafe source snapshot member path: {name}")
            if not isinstance(expected, str) or not SHA256_PATTERN.fullmatch(expected):
                raise VerificationError(f"source manifest has invalid hash for {name}")
            actual = hashlib.sha256(archive.read(name)).hexdigest()
            if actual != expected:
                mismatches.append(name)
        if mismatches:
            raise VerificationError(f"source snapshot content hashes differ: {mismatches[:5]}")

    expected_count = snapshot_record.get("file_count")
    if expected_count != len(files):
        raise VerificationError(
            f"source snapshot file count mismatch: expected {expected_count}, got {len(files)}"
        )
    return {
        **snapshot_hash,
        "embedded_manifest_sha256": manifest_hash,
        "manifested_file_count": len(files),
        "manifested_file_hashes_match": len(files),
        "git_sha": campaign_git_sha,
    }


def build_report(
    manifest_path: Path = DEFAULT_MANIFEST,
    registry_path: Path = DEFAULT_REGISTRY,
    *,
    repo_root: Path = ROOT,
    archive_root: Path | None = None,
) -> dict[str, Any]:
    """Rehash the selected campaign's archived run manifests, configs, and policies."""
    started = time.perf_counter()
    repo_root = repo_root.resolve()
    archive_root = (
        archive_root or repo_root.parent / f"{repo_root.name}-research-archive"
    ).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "qrl.research_result_manifest.v2":
        raise VerificationError("selected result manifest is not schema v2")
    campaign_path_value = registry.get("campaign_path")
    campaign_relative = PurePosixPath(str(campaign_path_value))
    if campaign_relative.is_absolute() or ".." in campaign_relative.parts:
        raise VerificationError("checkpoint registry campaign path is unsafe")
    campaign_dir, campaign_display_path = _resolve_archived_path(
        str(campaign_relative), repo_root=repo_root, archive_root=archive_root
    )
    campaign_json_path = campaign_dir / "campaign.json"
    campaign_json_hash = _stable_sha256(campaign_json_path)[0]
    campaign = json.loads(campaign_json_path.read_text(encoding="utf-8"))
    if campaign.get("fingerprint") != registry.get("campaign_fingerprint"):
        raise VerificationError("campaign fingerprint differs from checkpoint registry")
    campaign_git_sha = campaign.get("git_sha")
    if not isinstance(campaign_git_sha, str) or not GIT_COMMIT_PATTERN.fullmatch(campaign_git_sha):
        raise VerificationError("campaign has no valid source commit")

    snapshot_record = campaign.get("source_snapshot")
    if not isinstance(snapshot_record, dict):
        raise VerificationError("campaign has no source snapshot record")
    snapshot_relative = PurePosixPath(str(snapshot_record.get("path", "")))
    if snapshot_relative.is_absolute() or ".." in snapshot_relative.parts:
        raise VerificationError("campaign source snapshot path is unsafe")
    snapshot_path = campaign_dir.joinpath(*snapshot_relative.parts)
    snapshot_report = _verify_source_snapshot(
        snapshot_path, snapshot_record, campaign_git_sha=campaign_git_sha
    )

    run_records = manifest.get("runs")
    if not isinstance(run_records, list) or len(run_records) != 2:
        raise VerificationError("selected result manifest must contain exactly two runs")
    registry_arms = {item.get("arm") for item in registry.get("checkpoints", [])}
    run_arms = {PurePosixPath(item.get("run_id", "")).parts[1] for item in run_records}
    if run_arms != registry_arms or run_arms != {"A4A", "A4B"}:
        raise VerificationError("run arms do not match the selected checkpoint registry")

    current_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    verified_runs: list[dict[str, Any]] = []
    for run in run_records:
        run_id = run["run_id"]
        if PurePosixPath(run_id).parts[0] != campaign_relative.name:
            raise VerificationError(f"run {run_id} belongs to a different campaign")
        arm = PurePosixPath(run_id).parts[1]
        artifacts = run.get("artifacts", [])
        run_record = next((a for a in artifacts if a.get("role") == "run_manifest"), None)
        config_record = next((a for a in artifacts if a.get("role") == "resolved_run_config"), None)
        if run_record is None or config_record is None:
            raise VerificationError(f"run {run_id} lacks run manifest or config artifact")
        run_manifest_path, run_manifest_display = _resolve_archived_path(
            run_record["path"], repo_root=repo_root, archive_root=archive_root
        )
        run_manifest_hash = _require_hash(
            run_manifest_path, run_record.get("sha256"), label=f"{arm} run manifest"
        )
        run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
        config_path, config_display = _resolve_archived_path(
            config_record["path"], repo_root=repo_root, archive_root=archive_root
        )
        config_hash = _require_hash(
            config_path, config_record.get("sha256"), label=f"{arm} resolved config"
        )
        recorded_config = run_manifest.get("config", {})
        recorded_config_path, _ = _resolve_archived_path(
            recorded_config.get("path", ""), repo_root=repo_root, archive_root=archive_root
        )
        if recorded_config_path != config_path:
            raise VerificationError(f"{arm} run manifest and result manifest config paths differ")
        if recorded_config.get("sha256") != config_hash["sha256"]:
            raise VerificationError(f"{arm} run manifest config hash differs from current bytes")

        checkpoint_record = run_manifest.get("checkpoint", {})
        checkpoint_path, checkpoint_display = _resolve_archived_path(
            checkpoint_record.get("path", ""), repo_root=repo_root, archive_root=archive_root
        )
        checkpoint_hash = _require_hash(
            checkpoint_path,
            checkpoint_record.get("sha256"),
            label=f"{arm} final checkpoint",
        )
        identity = run.get("identity", {})
        run_source_commit = run_manifest.get("source", {}).get("head")
        if identity.get("source_commit") != run_source_commit:
            raise VerificationError(f"{arm} source commit differs between result and run manifests")
        campaign_to_run = _git_is_ancestor(campaign_git_sha, run_source_commit, repo_root=repo_root)
        run_to_current = _git_is_ancestor(run_source_commit, current_head, repo_root=repo_root)
        if not campaign_to_run or not run_to_current:
            raise VerificationError(f"{arm} source commit ancestry is inconsistent")

        feature_cache = run_manifest.get("feature_cache", {})
        cache_path = Path(feature_cache.get("path", ""))
        verified_runs.append(
            {
                "arm": arm,
                "run_id": run_id,
                "source_commit": run_source_commit,
                "campaign_commit_is_ancestor": campaign_to_run,
                "run_commit_is_ancestor_of_current_head": run_to_current,
                "run_manifest": {"path": run_manifest_display, **run_manifest_hash},
                "resolved_config": {"path": config_display, **config_hash},
                "final_checkpoint": {"path": checkpoint_display, **checkpoint_hash},
                "feature_cache_at_recorded_path_exists": cache_path.is_file(),
                "feature_cache_recorded_identity": feature_cache.get("identity"),
                "feature_cache_recorded_file_sha256": feature_cache.get("file_sha256"),
            }
        )

    return {
        "schema": "qrl.selected_campaign_artifact_integrity.v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "status": "passed_with_scoped_limits",
        "campaign_id": campaign_relative.name,
        "campaign_fingerprint": campaign["fingerprint"],
        "campaign_json": {
            "path": f"{campaign_display_path}/campaign.json",
            "sha256": campaign_json_hash,
        },
        "campaign_source_commit": campaign_git_sha,
        "source_snapshot": snapshot_report,
        "runs": verified_runs,
        "scope": {
            "campaign_artifacts_rehashed": [
                "campaign.json",
                "source_snapshot.zip and every manifested source member",
                "both run manifests",
                "both resolved configs",
                "both final checkpoints",
            ],
            "raw_data_rehashed": False,
            "feature_cache_rehashed": False,
            "checkpoint_loaded_or_replayed": False,
            "training_performed": False,
            "archive_wide_checkpoint_search": False,
        },
        "limitations": [
            "This verifies archived identity and bytes; it does not reproduce the historical model run.",
            "Raw data identity remains covered by the separate selected-campaign input audit.",
            "The recorded feature cache is reported only at its run-manifest path; it is not required for this checkpoint-byte verification.",
            "The separate replacement18 checkpoint-recovery freeze is a different campaign and is not used as P6 checkpoint evidence.",
        ],
        "elapsed_seconds": time.perf_counter() - started,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.out if args.out.is_absolute() else ROOT / args.out
    output = output.resolve()
    output.relative_to(ROOT)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing evidence: {output}")
    report = build_report(args.manifest, args.registry)
    write_json_atomic(output, report, default=None)
    print(
        json.dumps(
            {
                "report": str(output),
                "campaign_id": report["campaign_id"],
                "source_files_verified": report["source_snapshot"]["manifested_file_count"],
                "checkpoints_verified": len(report["runs"]),
                "status": report["status"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
