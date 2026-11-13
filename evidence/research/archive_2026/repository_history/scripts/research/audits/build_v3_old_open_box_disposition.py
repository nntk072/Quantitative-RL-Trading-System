#!/usr/bin/env python3
"""Map all 70 historical open boxes to explicit final V3 dispositions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_MAP = ROOT / "config/research/v3_old_open_box_map.yaml"


def _progress(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "v3-full-progress-v1":
        raise ValueError("invalid V3 progress file")
    return value


def build_dispositions(mapping: dict[str, Any], progress: dict[str, Any]) -> dict[str, Any]:
    """Resolve each historical item from its mapped V3 TODO terminal states."""
    items = mapping.get("items")
    if not isinstance(items, list) or len(items) != 70:
        raise ValueError("old-box map must contain exactly 70 items")
    if mapping.get("item_count") != 70:
        raise ValueError("old-box declared item_count must equal 70")
    task_states = progress["tasks"]
    rows: list[dict[str, Any]] = []
    old_ids: list[int] = []
    for item in items:
        old_id = item.get("old_open_id")
        if isinstance(old_id, bool) or not isinstance(old_id, int):
            raise ValueError("old_open_id values must be integers")
        old_ids.append(old_id)
        raw_refs = item.get("todo_refs", [])
        if not isinstance(raw_refs, list) or any(
            isinstance(value, bool) or not isinstance(value, int) for value in raw_refs
        ):
            raise ValueError(f"old box {old_id} todo_refs must be integer IDs")
        refs = list(raw_refs)
        if any(todo < 1 or todo > 162 for todo in refs) or len(refs) != len(set(refs)):
            raise ValueError(f"old box {old_id} has invalid or duplicate V3 TODO references")
        states = [task_states[str(todo)]["status"] for todo in refs if str(todo) in task_states]
        if refs and len(states) != len(refs):
            disposition = "BLOCKED"
            reason = "one or more mapped TODOs are absent from the progress tracker"
        elif refs and all(state == "PASS" for state in states):
            disposition = "COMPLETED"
            reason = f"completed via TODOs {refs}"
        elif (
            refs
            and all(state in {"PASS", "DEFERRED-NO-GO"} for state in states)
            and any(state == "DEFERRED-NO-GO" for state in states)
        ):
            disposition = "DEFERRED-NO-GO"
            reason = f"bounded no-go in mapped TODOs {refs}"
        elif refs and any(state == "FAIL" for state in states):
            disposition = "BLOCKED"
            reason = f"mapped TODO failure in {refs}"
        else:
            disposition = "PENDING"
            reason = item.get("disposition_path", "")
        rows.append(
            {
                **item,
                "mapped_statuses": states,
                "final_disposition": disposition,
                "reason": reason,
            }
        )
    if old_ids != list(range(1, 71)):
        raise ValueError("old-open IDs must be exactly 1..70 in order")
    return {
        "schema_version": "v3-old-open-box-disposition-v1",
        "item_count": len(rows),
        "all_terminal": all(
            row["final_disposition"] in {"COMPLETED", "DEFERRED-NO-GO"} for row in rows
        ),
        "items": rows,
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# V3 historical open-box dispositions",
        "",
        "| Old item | Checklist line | Final disposition | V3 mapping |",
        "|---:|---:|---|---|",
    ]
    for row in payload["items"]:
        refs = ", ".join(str(x) for x in row["todo_refs"]) or row["disposition_path"]
        lines.append(
            f"| {row['old_open_id']} | {row['checklist_line']} | "
            f"{row['final_disposition']} | {refs} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--progress", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()
    map_path = args.map if args.map.is_absolute() else ROOT / args.map
    mapping = OmegaConf.to_container(OmegaConf.load(map_path), resolve=True)
    if not isinstance(mapping, dict) or not all(isinstance(key, str) for key in mapping):
        raise ValueError("old-box mapping must be a YAML mapping")
    payload = build_dispositions(
        {str(key): value for key, value in mapping.items()}, _progress(args.progress)
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.output_json, payload)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(_markdown(payload), encoding="utf-8")
    print(json.dumps({"items": payload["item_count"], "all_terminal": payload["all_terminal"]}))
    return 0 if payload["all_terminal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
