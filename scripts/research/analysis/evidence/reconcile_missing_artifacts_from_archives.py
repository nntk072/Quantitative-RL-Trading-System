"""Find byte-identical missing research artifacts inside existing ZIP archives."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any


def _sha256_stream(stream: Any) -> str:
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def _archive_paths(search_root: Path) -> list[Path]:
    paths: set[Path] = set()
    for directory, child_directories, filenames in os.walk(search_root, followlinks=False):
        current = Path(directory)
        child_directories[:] = sorted(
            name for name in child_directories if not (current / name).is_symlink()
        )
        for filename in filenames:
            candidate = current / filename
            if (
                candidate.suffix.lower() == ".zip"
                and candidate.is_file()
                and not candidate.is_symlink()
            ):
                paths.add(candidate.resolve())
    return sorted(paths)


def _load_targets(report_path: Path, dag_path: Path) -> list[dict[str, str]]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    dag = json.loads(dag_path.read_text(encoding="utf-8"))
    node_by_id = {str(node.get("id")): node for node in dag.get("nodes", [])}
    targets: list[dict[str, str]] = []
    for failure in report.get("failures", []):
        if failure.get("kind") != "run_artifact" or failure.get("status") != "missing":
            continue
        node = node_by_id.get(str(failure.get("id")))
        if not isinstance(node, dict):
            continue
        path = node.get("path")
        expected = node.get("sha256")
        node_id = node.get("id")
        if (
            isinstance(path, str)
            and isinstance(expected, str)
            and len(expected) == 64
            and isinstance(node_id, str)
        ):
            targets.append(
                {"id": node_id, "path": path, "basename": Path(path).name, "sha256": expected}
            )
    return targets


def inventory_archive_candidates(
    targets: list[dict[str, str]], archive_paths: list[Path], *, all_members: bool = False
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Index matching basenames or all direct members without decompressing them."""
    target_ids_by_name: dict[str, list[str]] = defaultdict(list)
    for target in targets:
        target_ids_by_name[target["basename"]].append(target["id"])

    candidates: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for archive_path in archive_paths:
        try:
            with zipfile.ZipFile(archive_path) as archive:
                for info in archive.infolist():
                    basename = Path(info.filename).name
                    if info.is_dir() or (not all_members and basename not in target_ids_by_name):
                        continue
                    candidates.append(
                        {
                            "archive": str(archive_path),
                            "member": info.filename,
                            "header_offset": info.header_offset,
                            "basename": basename,
                            "uncompressed_bytes": info.file_size,
                            "compressed_bytes": info.compress_size,
                            "target_ids": (
                                [] if all_members else sorted(target_ids_by_name[basename])
                            ),
                        }
                    )
        except (OSError, RuntimeError, zipfile.BadZipFile, EOFError) as exc:
            errors.append({"archive": str(archive_path), "error": type(exc).__name__})
    return candidates, errors


def _hash_candidate(
    candidate: dict[str, Any],
    targets_by_id: dict[str, dict[str, str]],
    target_ids_by_hash: dict[str, list[str]],
    *,
    all_members: bool,
) -> dict[str, Any]:
    archive_path = Path(candidate["archive"])
    try:
        with zipfile.ZipFile(archive_path) as archive:
            info = next(
                (
                    item
                    for item in archive.infolist()
                    if item.header_offset == candidate["header_offset"]
                    and item.filename == candidate["member"]
                ),
                None,
            )
            if info is None:
                return {**candidate, "status": "member_changed"}
            with archive.open(info) as stream:
                actual_hash = _sha256_stream(stream)
    except (OSError, RuntimeError, zipfile.BadZipFile, EOFError) as exc:
        return {**candidate, "status": "read_error", "error": type(exc).__name__}
    matches = (
        target_ids_by_hash.get(actual_hash, [])
        if all_members
        else [
            target_id
            for target_id in candidate["target_ids"]
            if targets_by_id[target_id]["sha256"] == actual_hash
        ]
    )
    return {
        **candidate,
        "actual_sha256": actual_hash,
        "matching_target_ids": matches,
        "status": "matched" if matches else "different_bytes",
    }


def reconcile_archives(
    report_path: Path,
    dag_path: Path,
    search_root: Path,
    *,
    hash_candidates: bool,
    all_members: bool = False,
    max_uncompressed_bytes: int,
    workers: int = 4,
) -> dict[str, Any]:
    """Search archive members by basename and verify candidate bytes by SHA-256."""
    targets = _load_targets(report_path, dag_path)
    archives = _archive_paths(search_root.resolve(strict=True))
    candidates, archive_errors = inventory_archive_candidates(
        targets, archives, all_members=all_members
    )
    candidates.sort(key=lambda item: (item["archive"], item["member"], item["header_offset"]))
    candidate_bytes = sum(int(item["uncompressed_bytes"]) for item in candidates)
    report: dict[str, Any] = {
        "schema": "missing-run-artifact-archive-reconciliation-v1",
        "search_root": str(search_root.resolve()),
        "target_count": len(targets),
        "archive_count": len(archives),
        "member_candidate_count": len(candidates),
        "all_direct_members": all_members,
        "candidate_uncompressed_bytes": candidate_bytes,
        "hashing_requested": hash_candidates,
        "hashing_limit_bytes": max_uncompressed_bytes,
        "archive_read_error_count": len(archive_errors),
        "archive_read_errors": archive_errors,
        "targets": targets,
    }
    if not hash_candidates:
        report.update({"status": "inventory_only", "matches": []})
        if not all_members:
            report["candidate_members"] = candidates
        return report
    if candidate_bytes > max_uncompressed_bytes:
        report.update(
            {
                "status": "hash_limit_exceeded",
                "matches": [],
            }
        )
        return report

    targets_by_id = {target["id"]: target for target in targets}
    target_ids_by_hash: dict[str, list[str]] = defaultdict(list)
    for target in targets:
        target_ids_by_hash[target["sha256"]].append(target["id"])
    hashed: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [
            executor.submit(
                _hash_candidate,
                candidate,
                targets_by_id,
                target_ids_by_hash,
                all_members=all_members,
            )
            for candidate in candidates
        ]
        for future in concurrent.futures.as_completed(futures):
            hashed.append(future.result())
    hashed.sort(key=lambda item: (item["archive"], item["member"], item["header_offset"]))
    matched: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in hashed:
        for target_id in candidate.get("matching_target_ids", []):
            matched[target_id].append(candidate)
    report.update(
        {
            "status": (
                "complete"
                if not archive_errors and not any(item["status"] == "read_error" for item in hashed)
                else "incomplete_archive_errors"
            ),
            "hashed_candidate_count": len(hashed),
            "member_read_error_count": sum(item["status"] == "read_error" for item in hashed),
            "matches": [
                {
                    "target": targets_by_id[target_id],
                    "archive_members": matches,
                }
                for target_id, matches in sorted(matched.items())
            ],
            "unmatched_target_ids": sorted(set(targets_by_id) - set(matched)),
            "candidate_members": hashed,
        }
    )
    if not all_members:
        report["candidate_members"] = hashed
    return report


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
    parser.add_argument("--hash-candidates", action="store_true")
    parser.add_argument(
        "--all-members",
        action="store_true",
        help="index and hash every direct ZIP member, regardless of its filename",
    )
    parser.add_argument("--max-uncompressed-bytes", type=int, default=10 * 1024**3)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    report = reconcile_archives(
        args.report,
        args.dag,
        args.search_root,
        hash_candidates=args.hash_candidates,
        all_members=args.all_members,
        max_uncompressed_bytes=args.max_uncompressed_bytes,
        workers=args.workers,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "candidate_members"}, indent=2
        )
    )
    return 0 if report["status"] not in {"hash_limit_exceeded"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
