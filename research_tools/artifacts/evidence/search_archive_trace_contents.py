"""Search local ZIP text-member headers for recoverable decision/order traces.

The scanner reads only a bounded prefix from candidate text members. It does
not extract members or infer that a missing match proves global absence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import tempfile
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_TEXT_SUFFIXES = {
    ".csv",
    ".tsv",
    ".json",
    ".jsonl",
    ".ndjson",
    ".yaml",
    ".yml",
    ".txt",
    ".log",
}
_PREFIX_BYTES = 64 * 1024
_CANDIDATE_FIELDS = {
    "candidate_id",
    "selected_candidate_id",
    "trade_setup_candidate_id",
}
_EVENT_FIELDS = {"source_event_id", "trade_setup_source_event_id", "event_id"}
_ACTION_FIELDS = {"action", "action_id", "decision_id", "inference_id"}
_TIME_FIELDS = {"timestamp", "decision_time", "action_time", "time"}
_ORDER_FIELDS = {"order_id", "order_attempt_id", "submission_id", "fill_id"}
_JSON_KEY = re.compile(r"[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']\s*:")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _member_fields(name: str, payload: bytes) -> set[str]:
    """Return normalized header or JSON key names from a bounded prefix."""
    text = payload.decode("utf-8-sig", errors="replace")
    suffix = Path(name).suffix.lower()
    if suffix in {".csv", ".tsv"}:
        first = next((line for line in text.splitlines() if line.strip()), "")
        try:
            fields = next(csv.reader([first], delimiter="\t" if suffix == ".tsv" else ","))
        except (csv.Error, StopIteration):
            fields = []
        return {field.strip().lower() for field in fields if field.strip()}
    return {match.group(1).lower() for match in _JSON_KEY.finditer(text)}


def _classifications(fields: set[str]) -> list[str]:
    classes: list[str] = []
    if fields & _CANDIDATE_FIELDS and fields & _EVENT_FIELDS and fields & _ACTION_FIELDS:
        classes.append("candidate_decision_event_trace")
    if (
        fields & _CANDIDATE_FIELDS
        and fields & _ORDER_FIELDS
        and fields & (_ACTION_FIELDS | _TIME_FIELDS)
    ):
        classes.append("candidate_order_or_fill_trace")
    if "proposal_id" in fields and fields & _CANDIDATE_FIELDS and fields & _EVENT_FIELDS:
        classes.append("candidate_proposal_trace")
    if "decision_id" in fields and fields & _ORDER_FIELDS:
        classes.append("decision_order_link_trace")
    return classes


def scan_archive_contents(root: Path) -> dict[str, Any]:
    """Inspect a bounded prefix of text members in ZIPs below ``root``."""
    resolved_root = root.expanduser().resolve(strict=True)
    if not resolved_root.is_dir():
        raise NotADirectoryError(resolved_root)

    archive_paths: set[Path] = set()
    for directory, child_directories, filenames in os.walk(resolved_root, followlinks=False):
        current = Path(directory)
        child_directories[:] = sorted(
            name for name in child_directories if not (current / name).is_symlink()
        )
        for filename in filenames:
            path = current / filename
            if path.suffix.lower() == ".zip" and path.is_file() and not path.is_symlink():
                archive_paths.add(path.resolve())
    archives = sorted(archive_paths)
    archive_records: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    read_errors: list[dict[str, str]] = []
    suffix_counts: Counter[str] = Counter()
    all_suffix_counts: Counter[str] = Counter()
    signature_counts: Counter[str] = Counter()
    zip_container_suffix_counts: Counter[str] = Counter()
    member_count = 0
    text_member_count = 0
    bytes_read = 0

    for archive_path in archives:
        archive_stat = archive_path.stat()
        archive_record: dict[str, Any] = {
            "path": str(archive_path),
            "size_bytes": archive_stat.st_size,
            "mtime_ns": archive_stat.st_mtime_ns,
            "status": "readable",
            "member_count": 0,
            "text_members_inspected": 0,
        }
        try:
            with zipfile.ZipFile(archive_path) as archive:
                members = archive.infolist()
                archive_record["member_count"] = len(members)
                member_count += len(members)
                for member in members:
                    if member.is_dir():
                        continue
                    suffix = Path(member.filename).suffix.lower()
                    all_suffix_counts[suffix or "<none>"] += 1
                    try:
                        with archive.open(member) as stream:
                            payload = stream.read(_PREFIX_BYTES if suffix in _TEXT_SUFFIXES else 16)
                    except (OSError, RuntimeError, zipfile.BadZipFile, EOFError) as exc:
                        read_errors.append(
                            {
                                "archive": str(archive_path),
                                "member": member.filename,
                                "error_type": type(exc).__name__,
                                "error": str(exc),
                            }
                        )
                        continue
                    if payload.startswith(b"PAR1"):
                        signature_counts["parquet"] += 1
                    elif payload.startswith(b"SQLite format 3\x00"):
                        signature_counts["sqlite"] += 1
                    elif payload.startswith(b"PK\x03\x04"):
                        signature_counts["zip_container"] += 1
                        zip_container_suffix_counts[suffix or "<none>"] += 1
                    if suffix not in _TEXT_SUFFIXES:
                        continue
                    text_member_count += 1
                    archive_record["text_members_inspected"] += 1
                    suffix_counts[suffix] += 1
                    bytes_read += len(payload)
                    fields = _member_fields(member.filename, payload)
                    classifications = _classifications(fields)
                    if classifications:
                        matches.append(
                            {
                                "archive": str(archive_path),
                                "member": member.filename,
                                "uncompressed_size_bytes": member.file_size,
                                "prefix_bytes_read": len(payload),
                                "classifications": classifications,
                                "matched_fields": sorted(
                                    fields
                                    & (
                                        _CANDIDATE_FIELDS
                                        | _EVENT_FIELDS
                                        | _ACTION_FIELDS
                                        | _TIME_FIELDS
                                        | _ORDER_FIELDS
                                        | {"proposal_id"}
                                    )
                                ),
                            }
                        )
        except (OSError, RuntimeError, zipfile.BadZipFile, EOFError) as exc:
            archive_record["status"] = "unreadable"
            archive_record["error_type"] = type(exc).__name__
            archive_record["error"] = str(exc)
        archive_records.append(archive_record)

    return {
        "schema_version": "qrl.archive_trace_content_search.v1",
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "search_root": str(resolved_root),
        "directory_symlinks_followed": False,
        "archive_count": len(archive_records),
        "readable_archive_count": sum(record["status"] == "readable" for record in archive_records),
        "unreadable_archive_count": sum(
            record["status"] == "unreadable" for record in archive_records
        ),
        "archive_member_count": member_count,
        "text_members_inspected": text_member_count,
        "prefix_bytes_per_member_max": _PREFIX_BYTES,
        "prefix_bytes_read_total": bytes_read,
        "text_members_by_suffix": dict(sorted(suffix_counts.items())),
        "recognized_binary_signatures": dict(sorted(signature_counts.items())),
        "zip_container_signatures_by_suffix": dict(sorted(zip_container_suffix_counts.items())),
        "members_with_binary_signatures_probed": sum(all_suffix_counts.values()),
        "all_member_files_by_suffix": dict(sorted(all_suffix_counts.items())),
        "uninspected_member_files_by_suffix": dict(
            sorted(
                (suffix, count)
                for suffix, count in all_suffix_counts.items()
                if suffix not in _TEXT_SUFFIXES
            )
        ),
        "match_count": len(matches),
        "matches": matches,
        "member_read_error_count": len(read_errors),
        "member_read_errors": read_errors,
        "archive_records": archive_records,
        "archive_contents_hashed": False,
        "member_contents_extracted": False,
        "scanner_sha256": _sha256(Path(__file__).resolve()),
        "limitations": [
            "Only the first 64 KiB of CSV, TSV, JSON, JSONL, YAML, text, and log members were inspected.",
            "Parquet, SQLite, binary members, and fields beyond the inspected text prefix were not searched.",
            "Directory symlinks and archives outside the supplied root were not traversed.",
            "A matching header is a recovery lead, not proof of valid lineage or usable evidence.",
            "No match is not proof of global absence.",
        ],
    }


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = scan_archive_contents(args.root)
    _write_json_atomic(args.out, report)
    print(
        f"ZIP content-prefix search: {report['archive_count']} archives, "
        f"{report['text_members_inspected']} text members, "
        f"{report['match_count']} leads, {report['unreadable_archive_count']} unreadable archives"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
