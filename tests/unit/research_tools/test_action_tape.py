"""Tests for strict, timestamp-keyed simulator action tapes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from research_tools.simulation.evaluation.action_tape import ActionTape


def _write_tape(path: Path, actions: list[dict[str, object]]) -> Path:
    path.write_text(
        json.dumps({"schema_version": "qrl.task13.action_tape.v1", "actions": actions}),
        encoding="utf-8",
    )
    return path


def test_action_tape_requires_exact_ordered_timestamps_and_full_consumption(
    tmp_path: Path,
) -> None:
    tape = ActionTape.load(
        _write_tape(
            tmp_path / "tape.json",
            [
                {"decision_time_utc": "2025-01-02T14:30:00Z", "action": 1},
                {"decision_time_utc": "2025-01-02T14:31:00Z", "action": [0.25, -0.5]},
            ],
        )
    )

    assert tape.next_action("2025-01-02T14:30:00+00:00") == 1
    vector = tape.next_action("2025-01-02T14:31:00Z")
    assert vector == [0.25, -0.5]
    if isinstance(vector, list):
        vector[0] = 0.0
    assert tape.actions[1][1] == (0.25, -0.5)
    tape.assert_fully_consumed()


def test_action_tape_timestamp_mismatch_does_not_advance_cursor(tmp_path: Path) -> None:
    tape = ActionTape.load(
        _write_tape(
            tmp_path / "tape.json",
            [{"decision_time_utc": "2025-01-02T14:30:00Z", "action": 1}],
        )
    )

    with pytest.raises(ValueError, match="timestamp mismatch"):
        tape.next_action("2025-01-02T14:31:00Z")

    assert tape.next_action("2025-01-02T14:30:00Z") == 1
    tape.assert_fully_consumed()


@pytest.mark.parametrize(
    "actions",
    [
        [
            {"decision_time_utc": "2025-01-02T14:31:00Z", "action": 1},
            {"decision_time_utc": "2025-01-02T14:30:00Z", "action": 0},
        ],
        [
            {"decision_time_utc": "2025-01-02T14:30:00Z", "action": 1},
            {"decision_time_utc": "2025-01-02T14:30:00+00:00", "action": 0},
        ],
        [{"decision_time_utc": "2025-01-02T14:30:00Z", "action": True}],
        [{"decision_time_utc": "2025-01-02T14:30:00Z", "action": 0.5}],
    ],
)
def test_action_tape_rejects_nonmonotonic_duplicate_or_unsupported_actions(
    tmp_path: Path,
    actions: list[dict[str, object]],
) -> None:
    with pytest.raises(ValueError):
        ActionTape.load(_write_tape(tmp_path / "tape.json", actions))


def test_action_tape_rejects_unconsumed_actions_and_reads_past_end(tmp_path: Path) -> None:
    tape = ActionTape.load(
        _write_tape(
            tmp_path / "tape.json",
            [
                {"decision_time_utc": "2025-01-02T14:30:00Z", "action": 1},
                {"decision_time_utc": "2025-01-02T14:31:00Z", "action": 0},
            ],
        )
    )

    with pytest.raises(ValueError, match="unconsumed"):
        tape.assert_fully_consumed()
    tape.next_action("2025-01-02T14:30:00Z")
    tape.next_action("2025-01-02T14:31:00Z")
    with pytest.raises(ValueError, match="exhausted"):
        tape.next_action("2025-01-02T14:32:00Z")
