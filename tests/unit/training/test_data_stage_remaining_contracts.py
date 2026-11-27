"""Remaining fail-closed contracts for training data preparation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from configuration.configuration_loader import load_config
from training.runner.data_stage import _prepare_training_data
from training.runner.stages import TrainingConfigurationStage


def test_confirmed_htf_prebuilt_cache_requires_sweep_audit_sidecar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An otherwise valid cache cannot bypass the confirmed-HTF audit artifact."""
    cfg = load_config(config_path="config/research/survival_qualification.yaml")
    cfg.evaluation.development_only = False
    cfg.costs.use_tick_execution = False
    cfg.features.po3_reference_mode = "htf_confirmed"
    cfg.data.cache_dir = str(tmp_path / "cache")

    primary_symbol = str(cfg.data.primary)
    cache = tmp_path / "prebuilt-features.parquet"
    cache.write_bytes(b"feature cache")
    Path(f"{cache}.hash").write_text("current-hash\n", encoding="utf-8")
    bars = pd.DataFrame(
        {"open": [100.0], "high": [101.0], "low": [99.0], "close": [100.5]},
        index=pd.DatetimeIndex(["2025-01-02 14:30:00Z"]),
    )

    monkeypatch.setattr(
        "training.runner.data_stage.run_pipeline",
        lambda *_args, **_kwargs: {primary_symbol: {"M1": bars}},
    )
    monkeypatch.setattr("training.runner.data_stage.build_tick_books", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        "training.runner.data_stage.get_split_config",
        lambda _cfg: ("2025-01-02", "2025-01-03"),
    )
    monkeypatch.setattr("training.runner.data_stage.get_train_start_config", lambda _cfg: None)
    monkeypatch.setattr(
        "training.runner.data_stage.make_train_mask", lambda index, *_args: [True] * len(index)
    )
    monkeypatch.setattr(
        "training.runner.data_stage.resolve_randomized_fill_latency_ms", lambda _cfg: 0.0
    )
    monkeypatch.setattr(
        "training.runner.data_stage.resolve_tick_execution_required", lambda _cfg: False
    )
    monkeypatch.setattr(
        "training.runner.data_stage.feature_cache_content_hash",
        lambda *_args, **_kwargs: "current-hash",
    )
    monkeypatch.setattr(
        "training.runner.data_stage.build_features",
        lambda *_args, **_kwargs: pytest.fail("missing HTF audit must fail before cache loading"),
    )

    stage = TrainingConfigurationStage(
        args=SimpleNamespace(force=False, mvp=False, use_vae=False),
        cfg=cfg,
        device="cpu",
        lagrangian_cb=None,
    )
    stage.cfg.data.prebuilt_feature_cache = str(cache)

    with pytest.raises(FileNotFoundError, match="missing its HTF sweep audit"):
        _prepare_training_data(stage)

    assert not Path(f"{cache}.htf_sweeps.parquet").exists()
