"""Search ZIP member names for archived decision and order trace exports.

The scanner reads ZIP central directories only. It does not extract member
contents or hash full archives, so its result is a scoped filename search, not
proof that no differently named trace exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

_TRACE_MEMBER_PATTERNS = (
    re.compile(
        r"(^|/)(trade_setup_decisions|decision_ledger|action_ledger|order_attempts|"
        r"order_submissions|accepted_orders|candidate_to_action)\.csv$",
        re.IGNORECASE,
    ),
    re.compile(
        r"(candidate.{0,24}action|action.{0,24}candidate|decision.{0,16}trace|"
        r"order.{0,16}(attempt|submission|accept))",
        re.IGNORECASE,
    ),
)


def scan_archive_roots(roots: list[Path]) -> dict[str, Any]:
    """Inventory matching ZIP member names under explicit filesystem roots."""
    resolved_roots = sorted({root.expanduser().resolve(strict=True) for root in roots})
    if not resolved_roots:
        raise ValueError("at least one search root is required")
    for root in resolved_roots:
        if not root.is_dir():
            raise NotADirectoryError(root)

    archive_paths: set[Path] = set()
    for root in resolved_roots:
        for directory, child_directories, filenames in os.walk(root, followlinks=False):
            current = Path(directory)
            child_directories[:] = sorted(
                name for name in child_directories if not (current / name).is_symlink()
            )
            for filename in filenames:
                path = current / filename
                if path.suffix.lower() == ".zip" and path.is_file() and not path.is_symlink():
                    archive_paths.add(path.resolve())

    archives: list[dict[str, Any]] = []
    matches: list[dict[str, str]] = []
    member_count = 0
    for archive_path in sorted(archive_paths):
        stat = archive_path.stat()
        record: dict[str, Any] = {
            "path": str(archive_path),
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "read_status": "readable",
            "member_count": 0,
        }
        try:
            with ZipFile(archive_path) as archive:
                names = archive.namelist()
        except (BadZipFile, EOFError, OSError, RuntimeError) as exc:
            record["read_status"] = "unreadable"
            record["error_type"] = type(exc).__name__
            record["error"] = str(exc)
            archives.append(record)
            continue

        record["member_count"] = len(names)
        member_count += len(names)
        archives.append(record)
        for member_name in names:
            if any(pattern.search(member_name) for pattern in _TRACE_MEMBER_PATTERNS):
                matches.append({"archive": str(archive_path), "member": member_name})

    script_path = Path(__file__).resolve()
    script_sha256 = hashlib.sha256(script_path.read_bytes()).hexdigest()
    return {
        "schema": "qrl.archived_trace_member_search.v1",
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "search_roots": [str(root) for root in resolved_roots],
        "directory_symlinks_followed": False,
        "archive_count": len(archives),
        "readable_archive_count": sum(record["read_status"] == "readable" for record in archives),
        "unreadable_archive_count": sum(
            record["read_status"] == "unreadable" for record in archives
        ),
        "member_count": member_count,
        "matching_member_count": len(matches),
        "matches": matches,
        "archives": archives,
        "archive_contents_hashed": False,
        "member_contents_extracted": False,
        "scanner_path": str(script_path),
        "scanner_sha256": script_sha256,
        "limitations": [
            "Search is based on ZIP member names; traces with other names may be missed.",
            "Unreadable or zero-byte archives could not be searched.",
            "Directory symlinks were not traversed; pass a resolved target root when needed.",
            "Archive and member bytes were not hashed or extracted.",
        ],
    }


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON report with atomic replacement on the destination filesystem."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            temporary_path = Path(stream.name)
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def main(argv: list[str] | None = None) -> int:
    """Search explicitly supplied roots and write the machine-readable report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    report = scan_archive_roots(args.root)
    _write_json_atomic(args.out.expanduser(), report)
    print(
        "ZIP member search: "
        f"{report['archive_count']} archives, {report['member_count']} readable members, "
        f"{report['matching_member_count']} matches, "
        f"{report['unreadable_archive_count']} unreadable"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
