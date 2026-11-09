import hashlib
from pathlib import Path
from typing import Any

from scripts.research.audits.verify_v3_finished import verify_finished


def _inputs(tmp_path: Path) -> dict[str, Any]:
    sha = "a" * 40
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    evidence_row = {
        "path": str(evidence),
        "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
    }
    progress = {
        "schema_version": "v3-full-progress-v1",
        "source_sha": sha,
        "tasks": {
            str(todo): {
                "status": "PASS",
                "source_sha": sha,
                "result": "verified",
                "evidence": [evidence_row],
            }
            for todo in range(1, 163)
        },
    }
    release_file = tmp_path / "release.md"
    release_file.write_text("released\n", encoding="utf-8")
    release_hash = hashlib.sha256(release_file.read_bytes()).hexdigest()
    return {
        "progress": progress,
        "campaign": {"release_ready": True, "source_commit": sha, "source_clean": True},
        "release_bundle": {
            "status": "pass",
            "verdict": "BLOCKED / NEGATIVE RESULT",
            "required_file_count": 1,
            "artifact_count": 1,
            "artifacts": {
                "release.md": {
                    "path": str(release_file),
                    "sha256": release_hash,
                    "bytes": release_file.stat().st_size,
                }
            },
        },
        "old_boxes": {
            "all_terminal": True,
            "item_count": 70,
            "items": [
                {"old_open_id": item_id, "final_disposition": "COMPLETED"}
                for item_id in range(1, 71)
            ],
        },
        "handoff": {
            "final_sha": sha,
            "next_baseline_sha": sha,
            "branch": "main",
            "ci_status": "success",
            "todo_status_counts": {
                "PASS": 162,
                "FAIL": 0,
                "DEFERRED-NO-GO": 0,
                "PENDING": 0,
                "RUNNING": 0,
            },
        },
        "current_sha": sha,
    }


def test_finished_gate_requires_all_todos_and_verified_release_state(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    failures = verify_finished(
        progress=inputs["progress"],
        campaign=inputs["campaign"],
        release_bundle=inputs["release_bundle"],
        old_boxes=inputs["old_boxes"],
        handoff=inputs["handoff"],
        current_sha=inputs["current_sha"],
        source_clean=True,
    )
    assert failures == []


def test_finished_gate_does_not_accept_pending_todo_162(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    inputs["progress"]["tasks"]["162"]["status"] = "PENDING"
    failures = verify_finished(
        progress=inputs["progress"],
        campaign=inputs["campaign"],
        release_bundle=inputs["release_bundle"],
        old_boxes=inputs["old_boxes"],
        handoff=inputs["handoff"],
        current_sha=inputs["current_sha"],
        source_clean=True,
    )
    assert "TODO 162 FINISHED condition is not PASS" in failures
