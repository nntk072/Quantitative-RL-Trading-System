#!/usr/bin/env python3
"""Hash the bounded local data inventory without copying raw market files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
INVENTORY_PATH = (
    Path("/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System")
    / "final_research_release_inventory_20261101.json"
)
RELEASE_DIR = ROOT / "evidence/research/releases/negative-evidence-readiness-2026-11-01"
OUTPUT_PATH = RELEASE_DIR / "RAW_DATA_SHA256_MANIFEST.json"
P6_AUDIT_PATH = RELEASE_DIR / "current_source_market_input_audit.json"


def _sha256(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _write_exclusive(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(payload, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise FileExistsError(f"Refusing to overwrite {path}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--write", action="store_true", help="write a new manifest; refuses overwrite"
    )
    mode.add_argument(
        "--check", action="store_true", help="verify inputs against the existing manifest"
    )
    args = parser.parse_args()
    if args.write and OUTPUT_PATH.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT_PATH}")
    if args.check and not OUTPUT_PATH.is_file():
        raise FileNotFoundError(f"Cannot verify missing manifest: {OUTPUT_PATH}")
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    p6_audit = json.loads(P6_AUDIT_PATH.read_text(encoding="utf-8"))
    p6_hashes = {
        str(item["path"]): str(item["observed_sha256"])
        for item in p6_audit["inputs"]
        if item.get("path") and item.get("observed_sha256")
    }
    files: list[dict[str, Any]] = []
    hashed_targets: dict[str, tuple[str, int, int, int, int, str]] = {}
    p6_match_targets: set[str] = set()
    inventory_total_bytes = 0
    for index, item in enumerate(inventory["raw_data_files"], start=1):
        declared_path = Path(item["path"]).absolute()
        relative_path = declared_path.relative_to(ROOT.resolve()).as_posix()
        source_path = declared_path.resolve(strict=True)
        resolved_relative_path = source_path.relative_to(ROOT.resolve()).as_posix()
        before = source_path.stat()
        cached = hashed_targets.get(resolved_relative_path)
        if cached is None:
            digest, actual_size = _sha256(source_path)
            after = source_path.stat()
            if (before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
            ):
                raise RuntimeError(f"Input changed while hashing: {relative_path}")
            mtime_utc = datetime.fromtimestamp(after.st_mtime, UTC).isoformat()
            hashed_targets[resolved_relative_path] = (
                digest,
                actual_size,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                mtime_utc,
            )
        else:
            digest, actual_size, inode, size, mtime_ns, mtime_utc = cached
            if (before.st_ino, before.st_size, before.st_mtime_ns) != (inode, size, mtime_ns):
                raise RuntimeError(f"Input changed between inventory aliases: {relative_path}")
        if actual_size != int(item["size_bytes"]):
            raise RuntimeError(
                f"Inventory size mismatch for {relative_path}: "
                f"expected {item['size_bytes']}, read {actual_size}"
            )
        expected_p6_hash = p6_hashes.get(resolved_relative_path)
        p6_match = expected_p6_hash == digest if expected_p6_hash is not None else None
        if p6_match is False:
            raise RuntimeError(f"P6 campaign hash mismatch: {relative_path}")
        if p6_match is True:
            p6_match_targets.add(resolved_relative_path)
        inventory_total_bytes += actual_size
        files.append(
            {
                "path": relative_path,
                "resolved_path": resolved_relative_path,
                "size_bytes": actual_size,
                "sha256": digest,
                "mtime_utc": mtime_utc,
                "is_symlink": declared_path.is_symlink(),
                "p6_campaign_hash_match": p6_match,
            }
        )
        print(
            f"hashed {index}/{len(inventory['raw_data_files'])}: "
            f"{relative_path} ({actual_size} bytes)",
            flush=True,
        )
    payload = {
        "schema": "qrl.local_raw_data_sha256_manifest.v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "source_inventory": INVENTORY_PATH.name,
        "inventory_file_count": len(files),
        "distinct_resolved_file_count": len(hashed_targets),
        "inventory_total_bytes": inventory_total_bytes,
        "distinct_resolved_total_bytes": sum(item[1] for item in hashed_targets.values()),
        "p6_campaign_unique_data_file_matches": len(p6_match_targets),
        "files": files,
        "scope_note": (
            "Hashes and metadata only; raw data remain local and are not copied. "
            "This does not establish provider rights, license terms, or schedule correctness."
        ),
    }
    if args.write:
        _write_exclusive(OUTPUT_PATH, payload)
        status = "written"
    else:
        expected = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        comparable = {key: value for key, value in payload.items() if key != "created_at_utc"}
        expected_comparable = {
            key: value for key, value in expected.items() if key != "created_at_utc"
        }
        if comparable != expected_comparable:
            raise RuntimeError("Current local data inventory does not match its checksum manifest")
        status = "verified"
    print(
        json.dumps(
            {
                "status": status,
                "manifest": str(OUTPUT_PATH),
                "inventory_file_count": len(files),
                "distinct_resolved_file_count": len(hashed_targets),
                "inventory_total_bytes": inventory_total_bytes,
                "distinct_resolved_total_bytes": sum(item[1] for item in hashed_targets.values()),
                "p6_campaign_unique_data_file_matches": len(p6_match_targets),
            }
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
