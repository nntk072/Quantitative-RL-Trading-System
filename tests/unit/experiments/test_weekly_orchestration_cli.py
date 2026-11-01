"""Tests for the weekly orchestration command-line entry point."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import experiments.runs.orchestration as orchestration_cli


def test_parse_args_resolves_weekly_options(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qrl-weekly",
            "--week",
            "12",
            "--batches",
            "2",
            "--seeds",
            "1",
            "7",
            "--strategies",
            "baseline",
            "--steps",
            "100",
            "--output-root",
            "runs",
            "--retries",
            "1",
        ],
    )

    args = orchestration_cli.parse_args()

    assert args.week == 12
    assert args.batches == 2
    assert args.seeds == [1, 7]
    assert args.strategies == ["baseline"]
    assert args.steps == 100
    assert args.output_root == "runs"
    assert args.retries == 1


@pytest.mark.parametrize(("option", "value"), [("--batches", "0"), ("--retries", "-1")])
def test_main_rejects_invalid_batch_counts(
    monkeypatch: pytest.MonkeyPatch, option: str, value: str
) -> None:
    monkeypatch.setattr(sys, "argv", ["qrl-weekly", "--week", "12", option, value])

    with pytest.raises(SystemExit, match="--batches must be positive"):
        orchestration_cli.main()


def test_main_runs_the_requested_week_without_training_in_test(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["qrl-weekly", "--week", "5", "--seeds", "42", "--strategies", "baseline"],
    )
    received: dict[str, object] = {}
    output_dir = Path("weekly-output")

    class FakeOrchestrator:
        def __init__(self, root: Path) -> None:
            received["root"] = root

        def run_week(self, week: int, specs: list[object], *, retries: int) -> Path:
            received.update(week=week, specs=specs, retries=retries)
            return output_dir

    monkeypatch.setattr(orchestration_cli, "WeeklyOrchestrator", FakeOrchestrator)

    orchestration_cli.main()

    assert received["root"] == Path("outputs/research_progress")
    assert received["week"] == 5
    assert received["retries"] == 0
    assert "Weekly artifacts written to weekly-output" in capsys.readouterr().out
