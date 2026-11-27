from __future__ import annotations

import builtins
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest


def test_callback_stubs_report_missing_stable_baselines3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    callback_module_path = Path(__file__).resolve().parents[3] / "learning" / "rl" / "callbacks.py"
    module_name = "learning.rl._callbacks_without_sb3_coverage_test"
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

    spec = importlib.util.spec_from_file_location(module_name, callback_module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setattr(builtins, "__import__", import_without_sb3_callbacks)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)

    callback_names = (
        "TrainingProgressCallback",
        "LearningDiagnosticsCallback",
        "ProgressLoggerCallback",
        "EpisodeEquityCallback",
        "BestCheckpointEvalCallback",
        "ClipLogStdCallback",
        "PeriodicCheckpointCallback",
        "LagrangianRiskCallback",
        "EarlyAbortCallback",
    )
    for callback_name in callback_names:
        callback_type = getattr(module, callback_name)
        with pytest.raises(ImportError, match="stable-baselines3 is required"):
            callback_type()
