"""Inventory recorded model observation/action shapes and decision traces.

This command reads run manifests, training logs, exported result reports, and
explicitly named trace files. It never loads model weights or changes source
artifacts. A trade ledger or aggregate setup report is not counted as a
per-decision policy trace.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

_JSON_NAMES = {
    "run_manifest.json",
    "training_log.json",
    "project_results_report.json",
    "reanalysis_manifest.json",
    "campaign_results_summary.json",
}
_TRACE_NAME_PARTS = (
    "decision_trace",
    "action_trace",
    "setup_trace",
    "candidate_trace",
    "trade_setup_decisions",
)
_TRACE_FILE_NAMES = {"decisions.csv"}
_DECISION_KEYS = {
    "decision_time",
    "decision_ts",
    "decision_index",
    "decision_step",
    "decision_id",
}
_SELECTED_SETUP_KEYS = {
    "selected_setup_id",
    "chosen_setup_id",
    "trade_setup_id",
    "trade_setup_candidate_id",
}
_ENTRY_GEOMETRY_KEYS = {"proposed_entry_price", "entry_price", "entry_price_or_offset"}
_STOP_GEOMETRY_KEYS = {"proposed_stop_price", "stop_price", "stop_anchor", "initial_stop"}
_TARGET_GEOMETRY_KEYS = {"proposed_target_price", "target_price", "target_anchor"}
_TTL_GEOMETRY_KEYS = {"order_ttl", "ttl", "expires_at", "max_wait"}
_MAX_JSON_BYTES = 64 * 1024 * 1024


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest of one file without changing it."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _walk_json(value: Any, path: str = "$") -> Any:
    """Yield mapping/list nodes with JSON paths for conservative inspection."""
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_json(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_json(child, f"{path}[{index}]")


def _shape_map(value: Any) -> dict[str, list[int]] | None:
    """Normalize a documented observation shape mapping when all dims are ints."""
    if not isinstance(value, dict) or not value:
        return None
    result: dict[str, list[int]] = {}
    for key, shape in value.items():
        if not isinstance(shape, list) or not all(
            isinstance(dimension, int) and not isinstance(dimension, bool) for dimension in shape
        ):
            return None
        result[str(key)] = [int(dimension) for dimension in shape]
    return result


def _record_trace_status(value: Any) -> tuple[bool, bool, list[str]]:
    """Find row collections that record selected setups and explicit price geometry."""
    setup_trace = False
    geometry_trace = False
    paths: list[str] = []
    for node_path, node in _walk_json(value):
        if not isinstance(node, list) or not node or not all(isinstance(row, dict) for row in node):
            continue
        path_has_setup_trace = False
        for row in node:
            has_decision, has_selected_setup, has_geometry = _trace_row_status(row)
            if not (has_decision and has_selected_setup):
                continue
            path_has_setup_trace = True
            setup_trace = True
            if has_geometry:
                geometry_trace = True
        if path_has_setup_trace:
            paths.append(node_path)
    return setup_trace, geometry_trace, paths


def _value_present(value: Any) -> bool:
    """Return whether a serialized trace value represents observed data."""
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, str):
        return value.strip().lower() not in {"", "nan", "none", "null"}
    if isinstance(value, float):
        return math.isfinite(value)
    return True


def _row_has_value(row: dict[str, Any], field_names: set[str]) -> bool:
    """Check for a populated, case-insensitive field in one trace record."""
    return any(
        str(key).lower() in field_names and _value_present(value) for key, value in row.items()
    )


def _trace_row_status(row: dict[str, Any]) -> tuple[bool, bool, bool]:
    """Check one record for a decision, selected setup, and complete geometry."""
    has_decision = _row_has_value(row, _DECISION_KEYS)
    has_setup = _row_has_value(row, _SELECTED_SETUP_KEYS)
    has_geometry = all(
        _row_has_value(row, fields)
        for fields in (
            _ENTRY_GEOMETRY_KEYS,
            _STOP_GEOMETRY_KEYS,
            _TARGET_GEOMETRY_KEYS,
            _TTL_GEOMETRY_KEYS,
        )
    )
    return has_decision, has_setup, has_geometry


def _inspect_json(path: Path, relative_path: str) -> dict[str, Any]:
    """Extract shape, action schema, and trace evidence from one known JSON artifact."""
    record: dict[str, Any] = {
        "path": relative_path,
        "kind": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "observation_shapes": [],
        "action_schemas": [],
        "action_space_widths": [],
        "checkpoint_references": [],
        "per_decision_setup_trace": False,
        "per_decision_price_geometry_trace": False,
        "trace_record_paths": [],
    }
    if record["size_bytes"] > _MAX_JSON_BYTES:
        record["parse_status"] = "skipped_above_size_limit"
        return record
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        record["parse_status"] = f"unreadable_or_invalid_json:{type(exc).__name__}"
        return record
    record["parse_status"] = "parsed"
    for node_path, node in _walk_json(payload):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            if "checkpoint" in str(key).lower() and isinstance(value, dict):
                reference_path = value.get("path")
                recorded_sha = value.get("sha256")
                if isinstance(reference_path, str) or isinstance(recorded_sha, str):
                    record["checkpoint_references"].append(
                        {
                            "json_path": f"{node_path}.{key}",
                            "path": reference_path if isinstance(reference_path, str) else None,
                            "sha256_recorded": recorded_sha
                            if isinstance(recorded_sha, str)
                            else None,
                        }
                    )
        shapes = _shape_map(node.get("observation_space_shapes"))
        if shapes is not None:
            record["observation_shapes"].append({"json_path": node_path, "shapes": shapes})
        schema = node.get("action_schema")
        if isinstance(schema, dict) and isinstance(schema.get("width"), int):
            record["action_schemas"].append(
                {
                    "json_path": f"{node_path}.action_schema",
                    "version": schema.get("version"),
                    "width": schema["width"],
                    "coordinates": schema.get("coordinates"),
                }
            )
        width = node.get("action_space_width")
        if isinstance(width, int) and not isinstance(width, bool):
            record["action_space_widths"].append(
                {"json_path": f"{node_path}.action_space_width", "width": width}
            )
    setup_trace, geometry_trace, trace_paths = _record_trace_status(payload)
    record["per_decision_setup_trace"] = setup_trace
    record["per_decision_price_geometry_trace"] = geometry_trace
    record["trace_record_paths"] = trace_paths
    return record


def _inspect_trace_file(path: Path, relative_path: str) -> dict[str, Any]:
    """Inspect an explicitly named CSV/JSONL trace by its row schema."""
    has_data_rows = False
    has_setup_trace = False
    has_geometry_trace = False
    headers: set[str] = set()
    try:
        if path.suffix.lower() == ".csv":
            with path.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.reader(stream)
                field_names = [value.strip().lower() for value in next(reader, [])]
                headers = set(field_names)
                for values in reader:
                    row = dict(zip(field_names, values, strict=False))
                    has_data_rows |= any(_value_present(value) for value in values)
                    has_decision, has_setup, has_geometry = _trace_row_status(row)
                    has_setup_trace |= has_data_rows and has_decision and has_setup
                    has_geometry_trace |= (
                        has_data_rows and has_decision and has_setup and has_geometry
                    )
                    if has_geometry_trace:
                        break
        elif path.suffix.lower() == ".jsonl":
            with path.open(encoding="utf-8") as stream:
                for line in stream:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        continue
                    headers.update(str(key).lower() for key in row)
                    has_data_rows |= any(_value_present(value) for value in row.values())
                    has_decision, has_setup, has_geometry = _trace_row_status(row)
                    has_setup_trace |= has_data_rows and has_decision and has_setup
                    has_geometry_trace |= (
                        has_data_rows and has_decision and has_setup and has_geometry
                    )
                    if has_geometry_trace:
                        break
    except (OSError, UnicodeDecodeError, csv.Error, json.JSONDecodeError):
        headers = set()
        has_data_rows = False
        has_setup_trace = False
        has_geometry_trace = False
    return {
        "path": relative_path,
        "kind": "named_trace_file",
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "columns": sorted(headers),
        "row_evidence_status": "rows_present" if has_data_rows else "no_data_rows",
        "per_decision_setup_trace": has_setup_trace,
        "per_decision_price_geometry_trace": has_geometry_trace,
    }


def _candidate_files(roots: list[Path]) -> tuple[list[tuple[Path, Path]], list[tuple[Path, Path]]]:
    """Discover known immutable JSON artifact types and explicitly named traces."""
    json_files: list[tuple[Path, Path]] = []
    trace_files: list[tuple[Path, Path]] = []
    seen: set[Path] = set()
    for root in roots:
        resolved_root = root.resolve()
        if not resolved_root.exists():
            continue
        # Archived source snapshots commonly contain symlinks back to the live
        # checkout. Following those links creates recursive path aliases and
        # can make a single artifact appear under arbitrarily repeated paths.
        # The supplied roots are the intended physical scan boundary.
        for directory, dirnames, filenames in os.walk(resolved_root, followlinks=False):
            dirnames[:] = sorted(name for name in dirnames if name not in {".git", "__pycache__"})
            for name in sorted(filenames):
                path = Path(directory, name)
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                try:
                    relative = path.relative_to(resolved_root).as_posix()
                except ValueError:
                    relative = path.name
                if name in _JSON_NAMES:
                    json_files.append((path, root / relative))
                elif path.suffix.lower() in {".csv", ".jsonl"} and (
                    name.lower() in _TRACE_FILE_NAMES
                    or any(part in name.lower() for part in _TRACE_NAME_PARTS)
                ):
                    trace_files.append((path, root / relative))
    return json_files, trace_files


def build_report(roots: list[Path]) -> dict[str, Any]:
    """Build the reusable artifact inventory without opening model weights."""
    json_files, trace_files = _candidate_files(roots)
    artifacts = [_inspect_json(path, relative.as_posix()) for path, relative in json_files]
    artifacts.extend(
        _inspect_trace_file(path, relative.as_posix()) for path, relative in trace_files
    )
    found_shapes = any(item.get("observation_shapes") for item in artifacts)
    found_actions = any(
        item.get("action_schemas") or item.get("action_space_widths") for item in artifacts
    )
    setup_paths = sorted(
        {
            f"{item['path']}::{record_path}"
            for item in artifacts
            if item.get("per_decision_setup_trace") and "path" in item
            for record_path in item.get("trace_record_paths", ["file_rows"])
        }
    )
    geometry_paths = sorted(
        {
            f"{item['path']}::{record_path}"
            for item in artifacts
            if item.get("per_decision_price_geometry_trace") and "path" in item
            for record_path in item.get("trace_record_paths", ["file_rows"])
        }
    )
    return {
        "schema_version": 1,
        "evidence_id": "model_observation_action_artifact_inventory",
        "scope": "read-only inventory of recognized run manifests, training logs, result reports, reanalysis manifests, and explicitly named decision/action/setup/candidate trace files",
        "roots": [str(root) for root in roots],
        "artifact_count": len(artifacts),
        "shape_evidence_status": "found" if found_shapes else "not_found_in_scanned_artifacts",
        "action_schema_evidence_status": "found"
        if found_actions
        else "not_found_in_scanned_artifacts",
        "per_decision_setup_trace_status": "found"
        if setup_paths
        else "not_found_in_scanned_artifacts",
        "per_decision_price_geometry_trace_status": "found"
        if geometry_paths
        else "not_found_in_scanned_artifacts",
        "per_decision_setup_trace_paths": setup_paths,
        "per_decision_price_geometry_trace_paths": geometry_paths,
        "limitations": [
            "This scanner recognizes documented JSON artifact names and explicitly named CSV/JSONL trace files; it does not infer policy decisions from trade-level summaries or aggregate setup counts.",
            "Directory symlinks are not followed; artifacts reachable only through a symlink outside the supplied roots are not included.",
            "Checkpoint paths and recorded digests are copied from surrounding manifests; checkpoint existence and bytes are not verified, and opaque weights are not loaded or parsed.",
            "not_found_in_scanned_artifacts means no qualifying trace was found under the supplied roots; it is not proof that no trace exists elsewhere.",
            "Observation shapes and action schemas are reported from recorded artifacts. Configured windows or source code are not substituted for missing run-specific tensor shapes.",
        ],
        "artifacts": artifacts,
    }


def parse_args() -> argparse.Namespace:
    """Parse the artifact roots and output path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        action="append",
        type=Path,
        required=True,
        default=[],
        help="Narrow artifact root to scan; repeat for independent roots. Required to keep scans bounded.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "evidence/research/model_observation_and_action_semantics/run_artifact_shape_inventory.json"
        ),
        help="JSON report destination.",
    )
    return parser.parse_args()


def main() -> None:
    """Write one deterministic JSON inventory from the supplied roots."""
    args = parse_args()
    report = build_report(args.root)
    report["generator"] = {
        "path": "scripts/research/analysis/models/inspect_observation_action_artifacts.py",
        "sha256": _sha256(Path(__file__).resolve()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"artifacts={report['artifact_count']} shapes={report['shape_evidence_status']} "
        f"action_schemas={report['action_schema_evidence_status']} "
        f"setup_trace={report['per_decision_setup_trace_status']} "
        f"price_geometry_trace={report['per_decision_price_geometry_trace_status']} "
        f"report={args.output}"
    )


if __name__ == "__main__":
    main()
