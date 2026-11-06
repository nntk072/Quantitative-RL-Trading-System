#!/usr/bin/env python3
"""Search ZIP containers inside local archives for bounded trace headers.

The scanner never extracts members or deserializes binary checkpoint data. It
reads nested ZIP members only when their uncompressed size is at most the
configured limit, then inspects bounded prefixes of supported text members.
"""

from __future__ import annotations

import argparse
import os
import zipfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from scripts.research.analysis.evidence.search_archive_trace_contents import (
    _PREFIX_BYTES,
    _TEXT_SUFFIXES,
    _classifications,
    _member_fields,
    _write_json_atomic,
)

_ZIP_MAGIC = b"PK\x03\x04"


def search_nested_archives(root: Path, *, max_nested_bytes: int) -> dict[str, Any]:
    """Inspect trace-like text headers in bounded nested ZIP members."""
    resolved_root = root.expanduser().resolve(strict=True)
    if not resolved_root.is_dir():
        raise NotADirectoryError(resolved_root)
    archive_paths: set[Path] = set()
    for directory, child_directories, filenames in os.walk(resolved_root, followlinks=False):
        current = Path(directory)
        child_directories[:] = sorted(
            name for name in child_directories if not (current / name).is_symlink()
        )
        archive_paths.update(
            (current / name).resolve()
            for name in filenames
            if (current / name).suffix.lower() == ".zip"
            and (current / name).is_file()
            and not (current / name).is_symlink()
        )

    nested_records: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    skipped_oversize = 0
    for archive_path in sorted(archive_paths):
        try:
            with zipfile.ZipFile(archive_path) as archive:
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    try:
                        with archive.open(member) as stream:
                            if stream.read(4) != _ZIP_MAGIC:
                                continue
                    except (OSError, RuntimeError, zipfile.BadZipFile, EOFError) as exc:
                        errors.append(
                            {
                                "archive": str(archive_path),
                                "member": member.filename,
                                "error": f"{type(exc).__name__}: {exc}",
                            }
                        )
                        continue
                    record: dict[str, Any] = {
                        "archive": str(archive_path),
                        "member": member.filename,
                        "uncompressed_size_bytes": member.file_size,
                        "status": "not_scanned",
                    }
                    nested_records.append(record)
                    if member.file_size > max_nested_bytes:
                        record["status"] = "skipped_size_limit"
                        skipped_oversize += 1
                        continue
                    try:
                        with archive.open(member) as stream:
                            payload = stream.read(max_nested_bytes + 1)
                        with zipfile.ZipFile(BytesIO(payload)) as nested:
                            record["status"] = "scanned"
                            record["nested_member_count"] = len(nested.infolist())
                            record["text_members_inspected"] = 0
                            for nested_member in nested.infolist():
                                suffix = Path(nested_member.filename).suffix.lower()
                                if nested_member.is_dir() or suffix not in _TEXT_SUFFIXES:
                                    continue
                                with nested.open(nested_member) as stream:
                                    header = stream.read(_PREFIX_BYTES)
                                record["text_members_inspected"] += 1
                                classes = _classifications(
                                    _member_fields(nested_member.filename, header)
                                )
                                if classes:
                                    matches.append(
                                        {
                                            "archive": str(archive_path),
                                            "nested_archive_member": member.filename,
                                            "member": nested_member.filename,
                                            "prefix_bytes_read": len(header),
                                            "classifications": classes,
                                        }
                                    )
                    except (OSError, RuntimeError, zipfile.BadZipFile, EOFError) as exc:
                        record["status"] = "unreadable"
                        record["error"] = f"{type(exc).__name__}: {exc}"
                        errors.append(
                            {
                                "archive": str(archive_path),
                                "member": member.filename,
                                "error": record["error"],
                            }
                        )
        except (OSError, RuntimeError, zipfile.BadZipFile, EOFError) as exc:
            errors.append(
                {
                    "archive": str(archive_path),
                    "member": "",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    return {
        "schema_version": "qrl.nested_archive_trace_search.v1",
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "search_root": str(resolved_root),
        "outer_archive_count": len(archive_paths),
        "nested_zip_count": len(nested_records),
        "nested_archives_skipped_size_limit": skipped_oversize,
        "max_nested_uncompressed_bytes": max_nested_bytes,
        "text_prefix_bytes_per_member_max": _PREFIX_BYTES,
        "nested_archives": nested_records,
        "trace_match_count": len(matches),
        "trace_matches": matches,
        "read_error_count": len(errors),
        "read_errors": errors,
        "members_extracted": False,
        "binary_members_deserialized": False,
        "limitations": [
            "Only nested ZIP containers with an uncompressed size within the configured limit were inspected.",
            "Only the first 64 KiB of supported text members were searched.",
            "Checkpoint tensor and pickle payloads were not deserialized.",
            "No match is not proof of global absence outside the searched local root.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-nested-bytes", type=int, default=64 * 1024 * 1024)
    args = parser.parse_args()
    if args.max_nested_bytes <= 0:
        parser.error("--max-nested-bytes must be positive")
    report = search_nested_archives(args.root, max_nested_bytes=args.max_nested_bytes)
    _write_json_atomic(args.out, report)
    print(
        f"Nested ZIP search: {report['nested_zip_count']} containers, "
        f"{report['trace_match_count']} trace leads, {report['read_error_count']} read errors"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
