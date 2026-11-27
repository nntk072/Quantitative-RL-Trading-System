from __future__ import annotations

import builtins
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from training.callbacks.dashboard import TrainingDashboardCallback


def test_dashboard_eval_appends_prefix_record_and_skips_missed_intervals(
    tmp_path: Path,
) -> None:
    dashboard_path = tmp_path / "nested" / "dashboard.csv"
    callback = TrainingDashboardCallback(
        total_timesteps=100,
        eval_every=10,
        eval_fn=lambda: {"return_pct": 1.25},
        log_path=dashboard_path,
    )
    callback.num_timesteps = 25
    callback._since_eval_reward = 3.0
    callback._since_eval_steps = 2

    callback._maybe_eval()

    eval_log_path = dashboard_path.parent / "dashboard_train_prefix_evaluations.jsonl"
    record = json.loads(eval_log_path.read_text(encoding="utf-8").splitlines()[0])
    assert record == {
        "role": "training_prefix_monitor",
        "timestep": 25,
        "return_pct": 1.25,
    }
    assert callback._eval_just_ran
    assert callback._next_eval == 30
    assert callback._since_eval_reward == 0.0
    assert callback._since_eval_steps == 0


def test_dashboard_eval_record_uses_serializable_fallback(tmp_path: Path) -> None:
    dashboard_path = tmp_path / "dashboard.csv"
    callback = TrainingDashboardCallback(
        total_timesteps=10,
        eval_every=1,
        eval_fn=lambda: {"artifact": object()},
        log_path=dashboard_path,
    )
    callback.num_timesteps = 1

    callback._maybe_eval()

    record = json.loads(
        (tmp_path / "dashboard_train_prefix_evaluations.jsonl").read_text(encoding="utf-8")
    )
    assert record["role"] == "training_prefix_monitor"
    assert record["timestep"] == 1
    assert isinstance(record["artifact"], str)


def test_dashboard_callback_reports_missing_stable_baselines3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    callback_path = Path(__file__).resolve().parents[3] / "training" / "callbacks" / "dashboard.py"
    module_name = "training.callbacks._dashboard_without_sb3_coverage_test"
    original_import = builtins.__import__

    def import_without_sb3_callbacks(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] | list[str] = (),
        level: int = 0,
    ) -> Any:
        if name == "stable_baselines3.common.callbacks":
            raise ImportError("stable-baselines3 callback dependency intentionally unavailable")
        return original_import(name, globals, locals, fromlist, level)

    spec = importlib.util.spec_from_file_location(module_name, callback_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setattr(builtins, "__import__", import_without_sb3_callbacks)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)

    fallback_callback = cast(Any, module).TrainingDashboardCallback
    with pytest.raises(
        ImportError, match="stable-baselines3 is required for TrainingDashboardCallback"
    ):
        fallback_callback()
