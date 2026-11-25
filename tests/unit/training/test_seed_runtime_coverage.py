"""Focused lifecycle and report-only safety contracts for per-seed training."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from training.runner import seed_runtime


def test_development_only_seed_cannot_evaluate_report_only_split() -> None:
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.development_only = True

    with pytest.raises(
        RuntimeError, match="development-only runs must not evaluate the report-only split"
    ):
        runner.evaluate_test_split()


def test_test_split_evaluation_requires_a_decision_provider() -> None:
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.development_only = False
    runner.context = SimpleNamespace(
        preparation=SimpleNamespace(configuration=SimpleNamespace(cfg=SimpleNamespace()))
    )
    runner.seed = 42
    runner.provider = None

    with pytest.raises(RuntimeError, match="decision provider was not created for evaluation"):
        runner.evaluate_test_split()


def test_test_split_evaluation_requires_a_saved_final_checkpoint() -> None:
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.development_only = False
    runner.context = SimpleNamespace(
        preparation=SimpleNamespace(
            configuration=SimpleNamespace(cfg=SimpleNamespace()),
            run_assets=SimpleNamespace(test_eval_spec=None),
            data=SimpleNamespace(test_bars=None, test_feat=None, primary_ticks=None),
        )
    )
    runner.seed = 42
    runner.provider = object()
    runner.phase_timings_seconds = {}
    runner.eval_common = {}
    runner.model_path = None

    with pytest.raises(RuntimeError, match="learner did not produce a final checkpoint path"):
        runner.evaluate_test_split()


@pytest.mark.parametrize("selected_seeds", [[], [99]])
def test_seed_subset_rejects_empty_or_unconfigured_work_before_training(
    monkeypatch: pytest.MonkeyPatch, selected_seeds: list[int]
) -> None:
    context: Any = SimpleNamespace(
        preparation=SimpleNamespace(run_assets=SimpleNamespace(seeds=[7, 11, 23]))
    )
    constructed_seeds: list[int] = []

    class RecordingSeedRunner:
        def __init__(self, _context: Any, seed: int) -> None:
            constructed_seeds.append(seed)
            self.seed = seed
            self.timesteps = 100

        def run(self) -> dict[str, int]:
            return {"seed": self.seed}

    monkeypatch.setattr(seed_runtime, "SeedRunner", RecordingSeedRunner)

    with pytest.raises(
        ValueError, match="selected seed work must be a non-empty subset of the configured seeds"
    ):
        seed_runtime.run_seed_training(context, selected_seeds=selected_seeds)

    assert constructed_seeds == []


def test_seed_subset_runs_configured_order_and_returns_last_seed_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context: Any = SimpleNamespace(
        preparation=SimpleNamespace(run_assets=SimpleNamespace(seeds=[7, 11, 23]))
    )
    constructed_seeds: list[int] = []

    class RecordingSeedRunner:
        def __init__(self, _context: Any, seed: int) -> None:
            constructed_seeds.append(seed)
            self.seed = seed
            self.timesteps = seed * 1_000

        def run(self) -> dict[str, int]:
            return {"seed": self.seed}

    monkeypatch.setattr(seed_runtime, "SeedRunner", RecordingSeedRunner)

    results, timesteps = seed_runtime.run_seed_training(context, selected_seeds=[23, 7])

    assert constructed_seeds == [7, 23]
    assert results == [{"seed": 7}, {"seed": 23}]
    assert timesteps == 23_000
