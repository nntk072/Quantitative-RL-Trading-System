"""Find byte-identical missing run artifacts among retained local files."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from scripts.research.analysis.evidence.reconcile_missing_artifacts_from_archives import (
    _load_targets,
    _sha256_stream,
)


def _file_candidates(
    targets: list[dict[str, str]], root: Path
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    names = {target["basename"] for target in targets}
    candidates: list[dict[str, Any]] = []
    walk_errors: list[dict[str, str]] = []

    def record_walk_error(error: OSError) -> None:
        walk_errors.append(
            {
                "path": str(error.filename or ""),
                "error": type(error).__name__,
            }
        )

    for directory, child_directories, filenames in os.walk(
        root, followlinks=False, onerror=record_walk_error
    ):
        current = Path(directory)
        child_directories[:] = sorted(
            name for name in child_directories if not (current / name).is_symlink()
        )
        for filename in filenames:
            if filename not in names:
                continue
            path = current / filename
            if path.is_symlink() or not path.is_file():
                continue
            candidates.append(
                {
                    "path": str(path),
                    "basename": filename,
                    "size_bytes": path.stat().st_size,
                }
            )
    return sorted(candidates, key=lambda item: item["path"]), walk_errors


def _hash_file(candidate: dict[str, Any]) -> dict[str, Any]:
    path = Path(candidate["path"])
    try:
        with path.open("rb") as stream:
            actual_hash = _sha256_stream(stream)
    except OSError as exc:
        return {**candidate, "status": "read_error", "error": type(exc).__name__}
    return {**candidate, "sha256": actual_hash, "status": "hashed"}


def reconcile_filesystem(
    report_path: Path,
    dag_path: Path,
    search_root: Path,
    *,
    max_candidate_bytes: int,
    workers: int = 4,
) -> dict[str, Any]:
    """Hash same-basename files and match against declared target content hashes."""
    targets = _load_targets(report_path, dag_path)
    root = search_root.resolve(strict=True)
    candidates, walk_errors = _file_candidates(targets, root)
    candidate_bytes = sum(int(item["size_bytes"]) for item in candidates)
    result: dict[str, Any] = {
        "schema": "missing-run-artifact-filesystem-reconciliation-v1",
        "search_root": str(root),
        "target_count": len(targets),
        "candidate_file_count": len(candidates),
        "candidate_bytes": candidate_bytes,
        "hashing_limit_bytes": max_candidate_bytes,
        "walk_error_count": len(walk_errors),
        "walk_errors": walk_errors,
        "matches": [],
        "unmatched_target_ids": sorted(target["id"] for target in targets),
    }
    if candidate_bytes > max_candidate_bytes:
        result["status"] = "hash_limit_exceeded"
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        hashed = list(executor.map(_hash_file, candidates))
    targets_by_hash: dict[str, list[dict[str, str]]] = defaultdict(list)
    for target in targets:
        targets_by_hash[target["sha256"]].append(target)
    matched: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in hashed:
        for target in targets_by_hash.get(candidate.get("sha256", ""), []):
            matched[target["id"]].append(candidate)
    read_error_count = sum(row["status"] == "read_error" for row in hashed)
    if read_error_count and walk_errors:
        status = "incomplete_walk_and_read_errors"
    elif read_error_count:
        status = "incomplete_read_errors"
    elif walk_errors:
        status = "incomplete_walk_errors"
    else:
        status = "complete"
    result.update(
        {
            "status": status,
            "hashed_file_count": sum(row["status"] == "hashed" for row in hashed),
            "read_error_count": read_error_count,
            "matches": [
                {"target": next(t for t in targets if t["id"] == target_id), "files": rows}
                for target_id, rows in sorted(matched.items())
            ],
            "unmatched_target_ids": sorted(set(t["id"] for t in targets) - set(matched)),
            "candidate_files": hashed,
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(
            "evidence/research/releases/negative-evidence-readiness/PROVENANCE_BYTE_VERIFICATION.json"
        ),
    )
    parser.add_argument(
        "--dag",
        type=Path,
        default=Path(
            "evidence/research/releases/negative-evidence-readiness/EXPERIMENT_PROVENANCE_DAG.json"
        ),
    )
    parser.add_argument("--search-root", type=Path, default=Path("/scratch/work/nguyenl37"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-candidate-bytes", type=int, default=30 * 1024**3)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    result = reconcile_filesystem(
        args.report,
        args.dag,
        args.search_root,
        max_candidate_bytes=args.max_candidate_bytes,
        workers=args.workers,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "candidate_files"}, indent=2
        )
    )
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
