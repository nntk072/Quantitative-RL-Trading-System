"""Development-only seed runs never request locked report-only evaluation."""

from __future__ import annotations

from typing import Any

from training.runner.seed_runtime import SeedRunner


def test_development_seed_lifecycle_skips_test_split_and_keeps_stage_order() -> None:
    runner: Any = object.__new__(SeedRunner)
    runner.development_only = True
    events: list[str] = []

    def prepare() -> object:
        events.append("prepare")
        return object()

    def train() -> object:
        events.append("train")
        return object()

    def evaluate_train() -> object:
        events.append("evaluate_train")
        return object()

    def persist() -> object:
        events.append("persist")
        return object()

    runner.prepare_training = prepare
    runner.train_model = train
    runner._write_training_progress_artifacts = lambda: events.append("progress")

    def reject_test_evaluation() -> None:
        raise AssertionError("development-only run evaluated the report-only test split")

    runner.evaluate_test_split = reject_test_evaluation
    runner.evaluate_train_split = evaluate_train
    runner.write_artifacts = persist
    runner.build_result = lambda: {"status": "complete"}

    result = runner.run()

    assert result == {"status": "complete"}
    assert events == ["prepare", "train", "progress", "evaluate_train", "persist"]
