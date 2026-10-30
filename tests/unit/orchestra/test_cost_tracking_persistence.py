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
