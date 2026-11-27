"""Seed artifact export uses source bars from configured data bundles."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest
from omegaconf import OmegaConf

from simulation.environment import bundles
from training.runner import seed_runtime


def test_write_artifacts_exports_bars_from_train_and_test_bundles(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    feature_cache = tmp_path / "features.parquet"
    feature_cache.write_bytes(b"features")
    Path(f"{feature_cache}.hash").write_text("cache-hash\n", encoding="utf-8")
    missing_normalization = tmp_path / "missing-normalization.json"
    train_export = pd.DataFrame({"close": [101.0]})
    test_export = pd.DataFrame({"close": [202.0]})
    exported: list[object] = []
    saved: dict[str, Any] = {}
    bundle_map = {"train-bundle": train_export, "test-bundle": test_export}

    def bars_for_export(bundle_path: object) -> pd.DataFrame:
        exported.append(bundle_path)
        return bundle_map[str(bundle_path)]

    monkeypatch.setattr(bundles, "bars_for_export", bars_for_export)
    monkeypatch.setattr(seed_runtime, "save_run", lambda **kwargs: saved.update(kwargs))
    monkeypatch.setattr(seed_runtime, "write_run_config_snapshot", lambda *_args: None)
    context = SimpleNamespace(
        preparation=SimpleNamespace(
            configuration=SimpleNamespace(
                args=SimpleNamespace(resume_checkpoint=None, algo="ppo", arch="mlp"),
                cfg=OmegaConf.create({"output": {}}),
            ),
            run_assets=SimpleNamespace(
                bundle_path="train-bundle",
                test_bundle_path="test-bundle",
                data_source="bundle",
                is_multi_seed=False,
            ),
            data=SimpleNamespace(
                train_bars=pd.DataFrame({"close": [-1.0]}),
                test_bars=pd.DataFrame({"close": [-2.0]}),
                train_sec=None,
                test_sec=None,
                feat_cache=feature_cache,
                dataset_records={},
                train_start="2025-01-01",
                train_end="2025-06-30",
                test_start="2025-07-01",
                feature_normalization_state_path=missing_normalization,
                primary_ticks=None,
                primary_sym="ES",
                schedule_path=None,
            ),
        )
    )
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.context = context
    runner.seed = 42
    runner.model = SimpleNamespace(num_timesteps=10)
    runner.seed_dir = seed_dir
    runner.train_env = object()
    runner.timesteps = 10
    runner.stop_candidate_schema = {}
    runner.model_path = seed_dir / "model"
    runner.fit_result = SimpleNamespace(artifact=SimpleNamespace(sha256="unused"))
    runner.test_result = None
    runner.test_m = None
    runner.train_result = {"status": "survived"}
    runner.train_m = object()
    runner.phase_timings_seconds = {}

    with pytest.raises(FileNotFoundError, match="train-fitted normalization state"):
        runner.write_artifacts()

    assert exported == ["train-bundle", "test-bundle"]
    assert saved["train_bars"] is train_export
    assert saved["test_bars"] is test_export
