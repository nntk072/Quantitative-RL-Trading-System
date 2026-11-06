#!/usr/bin/env python3
"""Inventory scratch symlink targets without traversing linked directories."""

from __future__ import annotations

import argparse
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.research.analysis.evidence.search_archive_trace_contents import (
    _write_json_atomic,
)


def inventory_symlinks(root: Path, focus_names: set[str]) -> dict[str, Any]:
    """Record symlink targets and summarize roots outside focused workspaces."""
    resolved_root = root.expanduser().resolve(strict=True)
    if not resolved_root.is_dir():
        raise NotADirectoryError(resolved_root)
    records: list[dict[str, Any]] = []
    other_root_counts: Counter[str] = Counter()

    def add_record(path: Path, is_directory_entry: bool) -> None:
        raw_target = os.readlink(path)
        resolved_target = (path.parent / raw_target).resolve(strict=False)
        try:
            relative = path.relative_to(resolved_root)
        except ValueError:
            relative = path
        top_level = relative.parts[0] if relative.parts else "."
        is_focused = top_level in focus_names
        target_exists = resolved_target.exists()
        record = {
            "path": str(path),
            "target": raw_target,
            "resolved_target": str(resolved_target),
            "target_exists": target_exists,
            "target_is_directory": resolved_target.is_dir() if target_exists else False,
            "path_is_directory_symlink": is_directory_entry,
        }
        if is_focused:
            records.append(record)
        else:
            other_root_counts[top_level] += 1

    for directory, child_directories, filenames in os.walk(resolved_root, followlinks=False):
        current = Path(directory)
        child_directories.sort()
        linked_directories = [name for name in child_directories if (current / name).is_symlink()]
        for name in linked_directories:
            add_record(current / name, True)
        child_directories[:] = [
            name for name in child_directories if name not in linked_directories
        ]
        for name in sorted(filenames):
            path = current / name
            if path.is_symlink():
                add_record(path, False)

    return {
        "schema_version": "qrl.scratch_symlink_inventory.v1",
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "search_root": str(resolved_root),
        "followed_symlink_directories": False,
        "focus_top_level_names": sorted(focus_names),
        "total_symlink_count": sum(other_root_counts.values()) + len(records),
        "focused_symlink_count": len(records),
        "focused_missing_target_count": sum(not item["target_exists"] for item in records),
        "focused_directory_symlink_count": sum(
            item["path_is_directory_symlink"] for item in records
        ),
        "focused_symlinks": records,
        "nonfocused_symlink_counts_by_top_level": dict(sorted(other_root_counts.items())),
        "limitations": [
            "Targets were resolved for inventory only; target directories were not traversed by this command.",
            "Only symlinks under the supplied root were enumerated.",
            "A target outside the scan root may require a separate evidence search.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--focus-name",
        action="append",
        default=[],
        help="Record matching top-level workspace links in detail; may be repeated.",
    )
    args = parser.parse_args()
    report = inventory_symlinks(args.root, set(args.focus_name))
    _write_json_atomic(args.out, report)
    print(
        f"Symlink inventory: {report['total_symlink_count']} links, "
        f"{report['focused_symlink_count']} focused, "
        f"{report['focused_missing_target_count']} missing focused targets"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
