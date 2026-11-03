#!/usr/bin/env python3
"""Hash the bounded local data inventory without copying raw market files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from configuration.paths import repository_root

ROOT = repository_root(__file__)
RELEASE_DIR = ROOT / "evidence/research/releases/negative-evidence-readiness"
DEFAULT_INVENTORY_PATH = (
    Path("/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System")
    / "local_market_data_inventory.json"
)
DEFAULT_OUTPUT_PATH = RELEASE_DIR / "RAW_DATA_SHA256_MANIFEST.json"
DEFAULT_CAMPAIGN_AUDIT_PATH = RELEASE_DIR / "current_source_market_input_audit.json"


def _sha256(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _stable_path_identity(path: Path, *, root: Path | None = None) -> str:
    """Prefer a repository-relative identity for in-repository evidence paths."""
    root = ROOT if root is None else root
    logical_path = path if path.is_absolute() else Path.cwd() / path
    try:
        return logical_path.absolute().relative_to(root.absolute()).as_posix()
    except ValueError:
        return str(path)


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


def _manifest_diff(expected: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    """Summarize identity differences without dumping every checksum row."""
    ignored = {"created_at_utc", "files"}
    top_level = {
        key: {"expected": expected.get(key), "observed": observed.get(key)}
        for key in sorted((expected.keys() | observed.keys()) - ignored)
        if expected.get(key) != observed.get(key)
    }
    expected_files = {
        (item.get("path"), item.get("resolved_path")): item for item in expected.get("files", [])
    }
    observed_files = {
        (item.get("path"), item.get("resolved_path")): item for item in observed.get("files", [])
    }
    changed_files: list[dict[str, Any]] = []
    for identity in sorted(expected_files.keys() | observed_files.keys()):
        before = expected_files.get(identity)
        after = observed_files.get(identity)
        if before != after:
            changed_fields = sorted(
                key
                for key in (before or {}).keys() | (after or {}).keys()
                if (before or {}).get(key) != (after or {}).get(key)
            )
            changed_files.append(
                {
                    "path": identity[0],
                    "changed_fields": changed_fields,
                    "expected_sha256": before.get("sha256") if before else None,
                    "observed_sha256": after.get("sha256") if after else None,
                    "expected_size_bytes": before.get("size_bytes") if before else None,
                    "observed_size_bytes": after.get("size_bytes") if after else None,
                    "expected_mtime_utc": before.get("mtime_utc") if before else None,
                    "observed_mtime_utc": after.get("mtime_utc") if after else None,
                }
            )
    return {
        "top_level_fields": top_level,
        "changed_file_count": len(changed_files),
        "changed_files_sample": changed_files[:20],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory",
        type=Path,
        default=DEFAULT_INVENTORY_PATH,
        help="local file inventory JSON; paths inside it resolve from the repository root",
    )
    parser.add_argument(
        "--campaign-audit",
        type=Path,
        default=DEFAULT_CAMPAIGN_AUDIT_PATH,
        help="current report containing selected-campaign observed input hashes",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="checksum manifest path; --write refuses to overwrite an existing file",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--write", action="store_true", help="write a new manifest; refuses overwrite"
    )
    mode.add_argument(
        "--check", action="store_true", help="verify inputs against the existing manifest"
    )
    args = parser.parse_args()
    if args.write and args.output.exists():
        raise FileExistsError(f"Refusing to overwrite {args.output}")
    if args.check and not args.output.is_file():
        raise FileNotFoundError(f"Cannot verify missing manifest: {args.output}")
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    campaign_audit = json.loads(args.campaign_audit.read_text(encoding="utf-8"))
    selected_campaign_hashes = {
        str(item["path"]): str(item["observed_sha256"])
        for item in campaign_audit["inputs"]
        if item.get("path") and item.get("observed_sha256")
    }
    files: list[dict[str, Any]] = []
    hashed_targets: dict[str, tuple[str, int, int, int, int, str]] = {}
    selected_campaign_match_targets: set[str] = set()
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
        expected_campaign_hash = selected_campaign_hashes.get(resolved_relative_path)
        campaign_hash_match = (
            expected_campaign_hash == digest if expected_campaign_hash is not None else None
        )
        if campaign_hash_match is False:
            raise RuntimeError(f"Selected campaign hash mismatch: {relative_path}")
        if campaign_hash_match is True:
            selected_campaign_match_targets.add(resolved_relative_path)
        inventory_total_bytes += actual_size
        files.append(
            {
                "path": relative_path,
                "resolved_path": resolved_relative_path,
                "size_bytes": actual_size,
                "sha256": digest,
                "mtime_utc": mtime_utc,
                "is_symlink": declared_path.is_symlink(),
                "selected_campaign_hash_match": campaign_hash_match,
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
        "source_inventory": args.inventory.name,
        "source_inventory_path": _stable_path_identity(args.inventory),
        "source_inventory_sha256": _sha256(args.inventory)[0],
        "campaign_input_audit_path": _stable_path_identity(args.campaign_audit),
        "campaign_input_audit_sha256": _sha256(args.campaign_audit)[0],
        "inventory_file_count": len(files),
        "distinct_resolved_file_count": len(hashed_targets),
        "inventory_total_bytes": inventory_total_bytes,
        "distinct_resolved_total_bytes": sum(item[1] for item in hashed_targets.values()),
        "selected_campaign_unique_data_file_matches": len(selected_campaign_match_targets),
        "files": files,
        "scope_note": (
            "Hashes and metadata only; raw data remain local and are not copied. "
            "This does not establish provider rights, license terms, or schedule correctness."
        ),
    }
    if args.write:
        _write_exclusive(args.output, payload)
        status = "written"
    else:
        expected = json.loads(args.output.read_text(encoding="utf-8"))
        comparable = {key: value for key, value in payload.items() if key != "created_at_utc"}
        expected_comparable = {
            key: value for key, value in expected.items() if key != "created_at_utc"
        }
        if comparable != expected_comparable:
            difference = _manifest_diff(expected_comparable, comparable)
            print(json.dumps({"manifest_difference": difference}, indent=2), file=sys.stderr)
            raise RuntimeError("Current local data inventory does not match its checksum manifest")
        status = "verified"
    print(
        json.dumps(
            {
                "status": status,
                "manifest": str(args.output),
                "inventory_file_count": len(files),
                "distinct_resolved_file_count": len(hashed_targets),
                "inventory_total_bytes": inventory_total_bytes,
                "distinct_resolved_total_bytes": sum(item[1] for item in hashed_targets.values()),
                "selected_campaign_unique_data_file_matches": len(selected_campaign_match_targets),
            }
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
