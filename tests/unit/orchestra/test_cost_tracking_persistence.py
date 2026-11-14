from __future__ import annotations

from pathlib import Path

from orchestra.cost import CostTracker


def test_cost_tracker_persists_under_a_new_state_directory(tmp_path: Path) -> None:
    state_dir = tmp_path / "nested" / "cost-state"
    tracker = CostTracker(state_dir)

    record = tracker.record_usage("ollama/devstral-local", 400, 200, task_id="task-a")
    restored = CostTracker(state_dir)

    assert record["prompt_tokens"] == 400
    assert restored.get_daily_summary()["total_calls"] == 1
    assert restored.cost_file.is_file()


def test_cost_tracker_records_known_and_unknown_runtime_metrics(tmp_path: Path) -> None:
    tracker = CostTracker(tmp_path)
    tracker.record_usage(
        "ollama/devstral-local",
        400,
        200,
        task_id="task-a",
        role="planner",
        success=False,
        elapsed_seconds=2.5,
        retry_count=1,
    )
    tracker.record_task_outcome(
        "task-a",
        "failed",
        metadata={"task_input_sha256": "abc", "delegation_policy": "adaptive"},
    )
    tracker.record_batch("task-a", "planning", 3.0, [2.5], 1, 0)
    restored = CostTracker(tmp_path)

    summary = restored.get_task_cost("task-a")
    assert summary is not None
    assert summary["successful_calls"] == 0
    assert summary["elapsed_seconds"] == 2.5
    assert summary["retry_count"] == 1
    assert summary["cached_prompt_tokens"] is None
    assert summary["tool_invocations"] is None
    assert summary["pipeline_status"] == "failed"
    assert summary["task_metadata"]["task_input_sha256"] == "abc"
    assert summary["configured_cost_calls"] == 1
    assert summary["fallback_cost_calls"] == 0
    assert summary["token_sources"] == ["estimated"]
    assert restored.get_daily_summary()["batches"][0]["parallel_efficiency"] == 0.8333


def test_cost_tracker_reads_legacy_records_without_new_fields(tmp_path: Path) -> None:
    tracker = CostTracker(tmp_path)
    tracker._data[tracker._today()] = {
        "calls": [
            {"model": "legacy/model", "prompt_tokens": 4, "completion_tokens": 2, "task_id": "old"}
        ],
        "totals": {"prompt_tokens": 4, "completion_tokens": 2, "total_cost": 0.0},
    }
    tracker._save()

    summary = CostTracker(tmp_path).get_task_cost("old")

    assert summary is not None
    assert summary["successful_calls"] == 1
    assert summary["elapsed_seconds"] is None
    assert summary["cached_prompt_tokens"] is None
