"""Inventory serialized encoder class paths in saved Stable-Baselines3 archives."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from artifacts.atomic import write_json_atomic

_MAX_METADATA_BYTES = 16 * 1024 * 1024
_CLASS_PATH = re.compile(rb"models\.encoders\.[A-Za-z_][A-Za-z0-9_.]*")
_LEGACY_MODULES = (
    "models.encoders.common.",
    "models.encoders.core.",
    "models.encoders.mtf_efficiency_common.",
)
_CHECKPOINT_PARENTS = {"model", "bootstrap_checkpoints", "checkpoints"}


def _is_checkpoint_archive(path: Path) -> bool:
    return path.suffix.lower() == ".zip" and (
        path.parent.name in _CHECKPOINT_PARENTS
        or path.name in {"ppo_best.zip", "ppo_final.zip", "ppo_latest.zip"}
    )


def _archive_record(path: Path, root: Path) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": path.relative_to(root).as_posix(),
        "size_bytes": path.stat().st_size,
        "metadata_members_scanned": [],
        "serialized_encoder_class_paths": [],
        "legacy_module_references": [],
        "status": "ok",
    }
    try:
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                is_metadata = member.filename == "data" or member.filename.endswith(
                    (".json", ".yaml", ".yml", ".txt")
                )
                if not is_metadata or member.file_size > _MAX_METADATA_BYTES:
                    continue
                payload = archive.read(member)
                record["metadata_members_scanned"].append(member.filename)
                paths = {
                    match.decode("ascii", errors="replace")
                    for match in _CLASS_PATH.findall(payload)
                }
                record["serialized_encoder_class_paths"].extend(paths)
            record["serialized_encoder_class_paths"] = sorted(
                set(record["serialized_encoder_class_paths"])
            )
            record["legacy_module_references"] = sorted(
                module
                for module in _LEGACY_MODULES
                if any(
                    class_path.startswith(module)
                    for class_path in record["serialized_encoder_class_paths"]
                )
            )
            if not record["metadata_members_scanned"]:
                record["status"] = "no-readable-metadata"
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        record["status"] = "archive-read-error"
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record


def build_inventory(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    paths = sorted(path for path in root.rglob("*.zip") if _is_checkpoint_archive(path))
    archives = [_archive_record(path, root) for path in paths]
    legacy_archives = [item for item in archives if item["legacy_module_references"]]
    return {
        "schema_version": "checkpoint-serialized-class-inventory-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "root": str(root),
        "scope": (
            "ZIP checkpoint archives beneath model, bootstrap_checkpoints, or "
            "checkpoints directories, plus named PPO archives. Reads only "
            "data/JSON/YAML/text metadata up to 16 MiB per member."
        ),
        "safety": (
            "No pickle/cloudpickle deserialization and no tensor/model weights "
            "are loaded. Source snapshots and non-checkpoint ZIPs are excluded."
        ),
        "summary": {
            "checkpoint_archives": len(archives),
            "archives_with_legacy_encoder_module_references": len(legacy_archives),
            "archive_read_errors": sum(item["status"] == "archive-read-error" for item in archives),
            "archives_without_readable_metadata": sum(
                item["status"] == "no-readable-metadata" for item in archives
            ),
        },
        "legacy_references": legacy_archives,
        "archives": archives,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("outputs"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/agent_state/checkpoint_serialized_class_inventory.json"),
    )
    args = parser.parse_args()
    inventory = build_inventory(args.root)
    write_json_atomic(args.output, inventory, default=None)
    print(json.dumps(inventory["summary"], sort_keys=True))
    print(f"inventory: {args.output}")


if __name__ == "__main__":
    main()
