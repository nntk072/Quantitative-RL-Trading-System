"""Search one additional ZIP level for byte-identical missing run artifacts.

The scanner opens bounded nested ZIP members in memory, hashes their direct
members, and compares SHA-256 values with the current provenance report. It
does not extract files or deserialize checkpoints.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from collections import defaultdict
from io import BytesIO
from pathlib import Path
from typing import Any

from scripts.research.analysis.evidence.reconcile_missing_artifacts_from_archives import (
    _load_targets,
    _sha256_stream,
)


def _read_nested_zip(
    archive_path: Path,
    member_name: str,
    member_header_offset: int,
    *,
    max_container_bytes: int,
) -> tuple[bytes | None, str | None]:
    """Read one listed inner archive without writing it to disk."""
    try:
        with zipfile.ZipFile(archive_path) as outer:
            member = next(
                (
                    info
                    for info in outer.infolist()
                    if info.filename == member_name and info.header_offset == member_header_offset
                ),
                None,
            )
            if member is None:
                return None, "member_missing"
            if member.file_size > max_container_bytes:
                return None, "container_size_limit"
            with outer.open(member) as stream:
                payload = stream.read(max_container_bytes + 1)
            if len(payload) > max_container_bytes:
                return None, "container_size_limit"
            if not zipfile.is_zipfile(BytesIO(payload)):
                return None, "not_zip"
            return payload, None
    except (OSError, RuntimeError, zipfile.BadZipFile, EOFError) as error:
        return None, type(error).__name__


def _nested_records(
    nested_report_path: Path,
    search_root: Path,
    *,
    max_container_bytes: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Load only previously inspected nested ZIP members under the declared root."""
    report = json.loads(nested_report_path.read_text(encoding="utf-8"))
    root = search_root.resolve(strict=True)
    records: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    for row in report.get("nested_archives", []):
        archive = Path(str(row.get("archive", "")))
        member = row.get("member")
        size = int(row.get("uncompressed_size_bytes", 0))
        try:
            resolved = archive.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError):
            skipped.append(
                {"archive": str(archive), "member": member, "reason": "outside_or_missing_root"}
            )
            continue
        if archive.is_symlink() or not resolved.is_file():
            skipped.append(
                {"archive": str(archive), "member": member, "reason": "not_regular_file"}
            )
            continue
        if row.get("status") != "scanned":
            skipped.append(
                {"archive": str(resolved), "member": member, "reason": str(row.get("status"))}
            )
            continue
        if not isinstance(member, str) or not member:
            skipped.append(
                {"archive": str(resolved), "member": member, "reason": "invalid_member_name"}
            )
            continue
        if size > max_container_bytes:
            skipped.append(
                {"archive": str(resolved), "member": member, "reason": "container_size_limit"}
            )
            continue
        key = (str(resolved), member, size)
        if key in seen:
            continue
        seen.add(key)
        try:
            with zipfile.ZipFile(resolved) as outer:
                for info in outer.infolist():
                    if info.filename == member and info.file_size == size:
                        records.append(
                            {
                                "archive": str(resolved),
                                "member": member,
                                "size_bytes": size,
                                "header_offset": int(info.header_offset),
                            }
                        )
        except (OSError, RuntimeError, zipfile.BadZipFile, EOFError):
            skipped.append(
                {"archive": str(resolved), "member": member, "reason": "outer_archive_unreadable"}
            )
    return records, skipped, int(report.get("read_error_count", 0))


def reconcile_nested_archives(
    missing_report_path: Path,
    provenance_dag_path: Path,
    nested_report_path: Path,
    search_root: Path,
    *,
    max_container_bytes: int,
    max_uncompressed_bytes: int,
) -> dict[str, Any]:
    """Hash direct members of bounded nested ZIPs and match missing targets."""
    targets = _load_targets(missing_report_path, provenance_dag_path)
    records, skipped, known_outer_errors = _nested_records(
        nested_report_path,
        search_root,
        max_container_bytes=max_container_bytes,
    )
    target_ids_by_hash: dict[str, list[str]] = defaultdict(list)
    targets_by_id = {row["id"]: row for row in targets}
    for target in targets:
        target_ids_by_hash[target["sha256"]].append(target["id"])

    member_count = 0
    uncompressed_bytes = 0
    read_errors: list[dict[str, str]] = []
    for record in records:
        payload, read_error = _read_nested_zip(
            Path(record["archive"]),
            record["member"],
            int(record["header_offset"]),
            max_container_bytes=max_container_bytes,
        )
        if read_error is not None or payload is None:
            read_errors.append(
                {
                    "archive": record["archive"],
                    "container_member": record["member"],
                    "error": read_error or "unknown_read_error",
                }
            )
            continue
        try:
            with zipfile.ZipFile(BytesIO(payload)) as nested:
                for info in nested.infolist():
                    if info.is_dir():
                        continue
                    member_count += 1
                    uncompressed_bytes += int(info.file_size)
        except (OSError, RuntimeError, zipfile.BadZipFile, EOFError) as error:
            read_errors.append(
                {
                    "archive": record["archive"],
                    "container_member": record["member"],
                    "error": type(error).__name__,
                }
            )

    base = {
        "schema": "missing-run-artifact-nested-archive-reconciliation-v1",
        "search_root": str(search_root.resolve()),
        "target_count": len(targets),
        "nested_container_count": len(records),
        "skipped_container_count": len(skipped),
        "skipped_containers": skipped,
        "nested_member_count": member_count,
        "nested_member_uncompressed_bytes": uncompressed_bytes,
        "hashing_limit_bytes": max_uncompressed_bytes,
        "nested_read_error_count": len(read_errors),
        "nested_read_errors": read_errors,
        "known_outer_archive_error_count": known_outer_errors,
        "matches": [],
        "unmatched_target_ids": sorted(targets_by_id),
        "limitations": [
            "Search is limited to previously inventoried nested ZIP members under the declared root.",
            "Only one nested ZIP level is hashed; deeper nested containers are not recursively opened.",
            "Outer archives that were unreadable during the prior inventory remain unsearched.",
            "Checkpoint tensors and pickle payloads are hashed as bytes but never deserialized.",
            "No match does not prove global absence outside the declared local root.",
        ],
    }
    if uncompressed_bytes > max_uncompressed_bytes:
        return {**base, "status": "hash_limit_exceeded", "hashed_member_count": 0}

    matches: dict[str, list[dict[str, Any]]] = defaultdict(list)
    hashed_count = 0
    hash_errors: list[dict[str, str]] = []
    for record in records:
        payload, hash_error = _read_nested_zip(
            Path(record["archive"]),
            record["member"],
            int(record["header_offset"]),
            max_container_bytes=max_container_bytes,
        )
        if hash_error is not None or payload is None:
            hash_errors.append(
                {
                    "archive": record["archive"],
                    "container_member": record["member"],
                    "error": hash_error or "unknown_read_error",
                }
            )
            continue
        try:
            with zipfile.ZipFile(BytesIO(payload)) as nested:
                for member_info in nested.infolist():
                    if member_info.is_dir():
                        continue
                    with nested.open(member_info) as stream:
                        digest = _sha256_stream(stream)
                    hashed_count += 1
                    for target_id in target_ids_by_hash.get(digest, []):
                        matches[target_id].append(
                            {
                                "archive": record["archive"],
                                "container_member": record["member"],
                                "member": member_info.filename,
                                "sha256": digest,
                            }
                        )
        except (OSError, RuntimeError, zipfile.BadZipFile, EOFError) as error:
            hash_errors.append(
                {
                    "archive": record["archive"],
                    "container_member": record["member"],
                    "error": type(error).__name__,
                }
            )
            continue
    matched_ids = set(matches)
    status = (
        "incomplete_nested_read_errors"
        if read_errors or hash_errors
        else "complete_inventoried_nested_members_with_unreadable_outer_archives"
        if known_outer_errors
        else "complete_inventoried_nested_members"
    )
    return {
        **base,
        "status": status,
        "hashed_member_count": hashed_count,
        "hash_error_count": len(hash_errors),
        "hash_errors": hash_errors,
        "matches": [
            {"target": targets_by_id[target_id], "members": members}
            for target_id, members in sorted(matches.items())
        ],
        "unmatched_target_ids": sorted(set(targets_by_id) - matched_ids),
    }


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
    parser.add_argument(
        "--nested-report",
        type=Path,
        default=Path(
            "evidence/research/historical_variant_screen_recoverability/nested_archive_trace_search.json"
        ),
    )
    parser.add_argument("--search-root", type=Path, default=Path("/scratch/work/nguyenl37"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-container-bytes", type=int, default=80 * 1024**2)
    parser.add_argument("--max-uncompressed-bytes", type=int, default=100 * 1024**3)
    args = parser.parse_args()
    report = reconcile_nested_archives(
        args.report,
        args.dag,
        args.nested_report,
        args.search_root,
        max_container_bytes=args.max_container_bytes,
        max_uncompressed_bytes=args.max_uncompressed_bytes,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: value
                for key, value in report.items()
                if key
                not in {"limitations", "skipped_containers", "nested_read_errors", "hash_errors"}
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] != "hash_limit_exceeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
