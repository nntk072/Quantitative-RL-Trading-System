#!/usr/bin/env python3
"""Inventory nested checkpoint-container member names without extracting them."""

from __future__ import annotations

import argparse
import json
import os
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from artifacts.atomic import write_json_atomic

DEFAULT_HINTS = ("p6", "ladder18", "selected", "a4a", "a4b", "seed50", "train2025")
CONTAINER_SUFFIXES = (".pth", ".zip")


def _archive_paths(root: Path) -> list[Path]:
    """Return regular ZIP paths without following directory or file symlinks."""
    archives: list[Path] = []
    for directory, child_dirs, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        child_dirs[:] = [name for name in child_dirs if not (current / name).is_symlink()]
        for name in filenames:
            path = current / name
            if path.suffix.casefold() == ".zip" and path.is_file() and not path.is_symlink():
                archives.append(path.resolve())
    return sorted(set(archives))


def inventory_archive_containers(
    root: Path,
    *,
    name_hints: tuple[str, ...] = DEFAULT_HINTS,
) -> dict[str, Any]:
    """List nested `.pth` and `.zip` member names in local ZIP archives.

    The scan reads archive central directories only. It neither extracts nor
    hashes members and makes no claim about archives outside ``root``.
    """
    root = root.resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    hints = tuple(value.casefold() for value in name_hints if value)
    archives = _archive_paths(root)
    records: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for path in archives:
        try:
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    if member.is_dir() or not member.filename.casefold().endswith(
                        CONTAINER_SUFFIXES
                    ):
                        continue
                    matched_hints = [
                        hint
                        for hint in hints
                        if hint in f"{path.as_posix()}/{member.filename}".casefold()
                    ]
                    records.append(
                        {
                            "archive": str(path),
                            "member": member.filename,
                            "size_bytes": member.file_size,
                            "name_hints": matched_hints,
                        }
                    )
        except (OSError, zipfile.BadZipFile, EOFError, RuntimeError) as error:
            errors.append({"archive": str(path), "error_type": type(error).__name__})

    suffix_counts = Counter(Path(row["member"]).suffix.casefold() for row in records)
    selected = [row for row in records if row["name_hints"]]
    return {
        "schema_version": "archive-container-member-inventory-v1",
        "root": str(root),
        "archive_count": len(archives),
        "nested_container_member_count": len(records),
        "nested_container_members_by_suffix": dict(sorted(suffix_counts.items())),
        "name_hints": list(name_hints),
        "name_hint_member_count": len(selected),
        "name_hint_members": selected,
        "outer_archive_errors": errors,
        "limitations": [
            "Only regular ZIP files reachable under the declared root are searched.",
            "Directory symlinks and file symlinks are not followed.",
            "Only member names and uncompressed sizes are read; nested bytes are not extracted, parsed, or hashed.",
            "A name hint is a recovery lead, not proof of checkpoint identity or lineage.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--name-hint", action="append", dest="name_hints")
    args = parser.parse_args()
    report = inventory_archive_containers(
        args.root,
        name_hints=tuple(args.name_hints) if args.name_hints else DEFAULT_HINTS,
    )
    output = args.out.resolve()
    write_json_atomic(output, report)
    print(
        json.dumps(
            {
                "report": str(output),
                "archive_count": report["archive_count"],
                "nested_container_member_count": report["nested_container_member_count"],
                "name_hint_member_count": report["name_hint_member_count"],
                "outer_archive_error_count": len(report["outer_archive_errors"]),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
