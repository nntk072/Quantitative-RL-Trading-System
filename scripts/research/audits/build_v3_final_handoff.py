#!/usr/bin/env python3
"""Build the final V3 handoff from frozen release, campaign, and progress artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from artifacts.atomic import write_json_atomic


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def build_handoff(
    *,
    progress: dict[str, Any],
    campaign: dict[str, Any],
    release_bundle: dict[str, Any],
    old_boxes: dict[str, Any],
    final_sha: str,
    branch: str,
    ci_status: str,
) -> dict[str, Any]:
    """Build a final synchronization handoff without weakening scientific state."""
    if len(final_sha) != 40:
        raise ValueError("final_sha must be a full Git SHA")
    if branch != "main":
        raise ValueError("the final handoff branch must be main")
    if release_bundle.get("status") != "pass":
        raise ValueError("release bundle is incomplete")
    if old_boxes.get("all_terminal") is not True or old_boxes.get("item_count") != 70:
        raise ValueError("all 70 historical open boxes must have terminal dispositions")
    if ci_status != "success":
        raise ValueError("final GitHub CI has not succeeded")
    task_rows = progress.get("tasks")
    if not isinstance(task_rows, dict):
        raise ValueError("invalid V3 progress artifact")
    if progress.get("schema_version") != "v3-full-progress-v1":
        raise ValueError("invalid V3 progress schema")
    if progress.get("source_sha") != final_sha:
        raise ValueError("progress source SHA differs from final source")
    if set(task_rows) != {str(todo) for todo in range(1, 163)}:
        raise ValueError("progress must contain TODO 1..162 exactly")
    for todo, row in task_rows.items():
        if not isinstance(row, dict) or row.get("source_sha") != final_sha:
            raise ValueError(f"TODO {todo} is malformed or tied to another source")
        status = row.get("status")
        if (todo == "162" and status != "PASS") or (
            todo != "162" and status not in {"PASS", "DEFERRED-NO-GO"}
        ):
            raise ValueError(f"TODO {todo} is not in a final state")
        if not isinstance(row.get("result"), str) or not row["result"].strip():
            raise ValueError(f"TODO {todo} has no result rationale")
        if not isinstance(row.get("evidence"), list) or not row["evidence"]:
            raise ValueError(f"TODO {todo} has no evidence")
    release_ready = campaign.get("release_ready") is True
    return {
        "schema_version": "v3-final-handoff-v1",
        "final_sha": final_sha,
        "branch": branch,
        "ci_status": ci_status,
        "release_ready": release_ready,
        "scientific_phase": campaign.get("current_phase"),
        "survival_phase_gate_status": campaign.get("survival_phase_gate_status"),
        "price_survival_qualification_authorized": campaign.get(
            "price_survival_qualification_authorized"
        ),
        "release_verdict": release_bundle.get("verdict"),
        "todo_status_counts": {
            status: sum(1 for row in task_rows.values() if row.get("status") == status)
            for status in ("PASS", "FAIL", "DEFERRED-NO-GO", "PENDING", "RUNNING")
        },
        "old_open_box_count": old_boxes.get("item_count"),
        "next_baseline_sha": final_sha,
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# V3 final handoff",
        "",
        f"- Final SHA: `{payload['final_sha']}`",
        f"- Branch: `{payload['branch']}`",
        f"- GitHub CI: `{payload['ci_status']}`",
        f"- Release verdict: **{payload['release_verdict']}**",
        f"- Campaign phase: `{payload['scientific_phase']}`",
        f"- Survival gate: `{payload['survival_phase_gate_status']}`",
        f"- PRICE authorization: `{payload['price_survival_qualification_authorized']}`",
        f"- Old open boxes dispositioned: `{payload['old_open_box_count']}`",
        "",
        f"`NEXT_BASELINE_SHA={payload['next_baseline_sha']}`",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--progress", type=Path, required=True)
    parser.add_argument("--campaign-state", type=Path, required=True)
    parser.add_argument("--release-bundle", type=Path, required=True)
    parser.add_argument("--old-box-disposition", type=Path, required=True)
    parser.add_argument("--final-sha", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--ci-status", choices=("success", "failure", "pending"), required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()
    payload = build_handoff(
        progress=_object(args.progress),
        campaign=_object(args.campaign_state),
        release_bundle=_object(args.release_bundle),
        old_boxes=_object(args.old_box_disposition),
        final_sha=args.final_sha,
        branch=args.branch,
        ci_status=args.ci_status,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.output_json, payload)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(_markdown(payload), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
