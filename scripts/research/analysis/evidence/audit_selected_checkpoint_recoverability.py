#!/usr/bin/env python3
"""Check exact checkpoint recovery for a frozen paired research comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_FREEZE = Path(
    "/scratch/work/nguyenl37/Quantitative-RL-Trading-System-research-archive/outputs/"
    "agent_state/architecture_refactor_baseline_source_3fbbb74/docs/thesis/evidence/"
    "p6_selected_pair_freeze_20261019.json"
)
DEFAULT_ARCHIVE_ROOT = Path(
    "/scratch/work/nguyenl37/Quantitative-RL-Trading-System-research-archive/outputs"
)
DEFAULT_REPORT = (
    ROOT / "evidence/research/historical_variant_screen_recoverability/"
    "selected_checkpoint_recoverability.json"
)
EXPECTED_SCHEMA = "aalto.rq1_selected_pair_freeze.v1"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_sha256(path: Path) -> str:
    """Hash a checkpoint only when its identity and size stay stable while read."""
    before = path.stat()
    digest = sha256(path)
    after = path.stat()
    stable_identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    final_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if stable_identity != final_identity:
        raise RuntimeError(f"checkpoint changed while hashing: {path}")
    return digest


def _run_path(archive_root: Path, source_run: str) -> Path:
    relative = Path(source_run)
    if relative.parts and relative.parts[0] == "outputs":
        relative = Path(*relative.parts[1:])
    candidate = (archive_root / relative).resolve()
    candidate.relative_to(archive_root.resolve())
    return candidate


def build_report(
    freeze_path: Path = DEFAULT_FREEZE,
    archive_root: Path = DEFAULT_ARCHIVE_ROOT,
) -> dict[str, Any]:
    """Hash only ZIP candidates matching each frozen variant and seed."""
    started = time.perf_counter()
    freeze_path = freeze_path.resolve()
    archive_root = archive_root.resolve()
    if not archive_root.is_dir():
        raise FileNotFoundError(f"checkpoint archive root is not a directory: {archive_root}")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze.get("schema") != EXPECTED_SCHEMA:
        raise ValueError(f"unsupported freeze schema: {freeze.get('schema')!r}")
    runs = freeze.get("runs")
    if not isinstance(runs, dict) or set(runs) != {"control", "treatment"}:
        raise ValueError("freeze must contain exactly the control and treatment runs")

    arms: dict[str, dict[str, Any]] = {}
    for arm, run in runs.items():
        if not isinstance(run, dict):
            raise ValueError(f"malformed {arm} run record")
        variant = run.get("variant")
        seed = run.get("seed")
        expected = run.get("checkpoint_sha256")
        source_run = run.get("source_run")
        if (
            not isinstance(variant, str)
            or not variant
            or not isinstance(seed, int)
            or not isinstance(source_run, str)
            or not isinstance(expected, str)
            or not SHA256_PATTERN.fullmatch(expected)
        ):
            raise ValueError(f"malformed frozen checkpoint identity for {arm}")

        expected_run_dir = _run_path(archive_root, source_run)
        candidates = sorted(
            path
            for path in archive_root.rglob("*.zip")
            if (
                any(
                    part.casefold() == variant.casefold()
                    or part.casefold().startswith(f"{variant.casefold()}__seed{seed}")
                    for part in path.parts
                )
                and f"seed{seed}" in path.as_posix().casefold()
            )
        )
        candidate_records: list[dict[str, Any]] = []
        matches: list[str] = []
        scanned_bytes = 0
        for path in candidates:
            digest = stable_sha256(path)
            size = path.stat().st_size
            scanned_bytes += size
            relative = path.relative_to(archive_root).as_posix()
            candidate_records.append({"path": relative, "bytes": size, "sha256": digest})
            if digest == expected:
                matches.append(relative)

        arms[arm] = {
            "variant": variant,
            "seed": seed,
            "expected_checkpoint_sha256": expected,
            "source_run_path": source_run,
            "source_run_directory_exists": expected_run_dir.is_dir(),
            "targeted_candidate_count": len(candidates),
            "targeted_candidate_bytes_hashed": scanned_bytes,
            "exact_match_paths": matches,
            "exact_match_count": len(matches),
            "candidates": candidate_records,
        }

    all_matched = all(record["exact_match_count"] > 0 for record in arms.values())
    return {
        "schema": "qrl.selected_checkpoint_recoverability.v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "campaign_id": freeze.get("campaign", {}).get("id"),
        "claim_scope": (
            "Exact SHA-256 recovery check for the two frozen seed-specific checkpoints, "
            "limited to archive ZIP paths whose names include the frozen variant and seed."
        ),
        "inputs": {
            "freeze_path": str(freeze_path),
            "freeze_sha256": sha256(freeze_path),
            "archive_root": str(archive_root),
            "audit_script_path": str(Path(__file__).resolve().relative_to(ROOT)),
            "audit_script_sha256": sha256(Path(__file__).resolve()),
        },
        "scope": {
            "archive_candidate_glob": "**/*.zip",
            "name_filter": "frozen variant token and seed token must both occur in path",
            "archive_paths_inspected": sum(
                record["targeted_candidate_count"] for record in arms.values()
            ),
            "checkpoint_bytes_hashed": sum(
                record["targeted_candidate_bytes_hashed"] for record in arms.values()
            ),
            "archive_wide_content_hashing": False,
            "full_scratch_search": False,
        },
        "arms": arms,
        "disposition": (
            "both frozen checkpoints have exact SHA-256 matches in the targeted archive paths"
            if all_matched
            else "one or more frozen checkpoints have no exact match in the targeted archive paths"
        ),
        "limitations": [
            "No global absence claim is made for differently named archives, other roots, or external backups.",
            "A filename match identifies a search candidate, not a lineage-valid replacement for the frozen run.",
            "This audit performs no model loading, evaluation, training, deletion, or archive modification.",
        ],
        "elapsed_seconds": time.perf_counter() - started,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    output = args.out if args.out.is_absolute() else ROOT / args.out
    output = output.resolve()
    output.relative_to(ROOT)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing evidence: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(args.freeze, args.archive_root)
    temporary = output.with_name(f".{output.name}.{time.time_ns()}.tmp")
    try:
        temporary.write_text(
            json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "report": str(output),
                "archive_paths_inspected": report["scope"]["archive_paths_inspected"],
                "disposition": report["disposition"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
