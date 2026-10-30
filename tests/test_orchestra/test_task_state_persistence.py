from __future__ import annotations

from pathlib import Path

from orchestra.task_state_store import TaskState


def test_task_state_save_creates_directory_and_loads_atomically(tmp_path: Path) -> None:
    state_dir = tmp_path / "nested" / "task-state"
    state = TaskState("task-a", "preserve state", state_dir)

    state.save()
    restored = TaskState.load("task-a", state_dir)

    assert restored.data["task_description"] == "preserve state"
    assert restored.state_file.is_file()
    assert not list(state_dir.glob("*.tmp"))
