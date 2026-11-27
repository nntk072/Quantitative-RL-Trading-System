"""Exact source-cache and prebuilt-cache replay contracts."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest
from omegaconf import OmegaConf

from artifacts.identity import file_sha256
from evaluation.reanalysis import datasets
from evaluation.reanalysis.provenance import _feature_build_scope


def test_source_cache_reconstruction_reuses_verified_features_and_matches_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "source-run"
    run_dir.mkdir()
    config_path = run_dir / "config.yaml"
    config_path.write_text("source config", encoding="utf-8")
    cache_path = tmp_path / "source-features.parquet"
    cache_path.write_bytes(b"saved feature cache")
    Path(f"{cache_path}.hash").write_text("source-content-hash\n", encoding="utf-8")

    index = pd.date_range("2025-01-02 15:00", periods=3, freq="min", tz="UTC")
    primary = pd.DataFrame({"close": [100.0, 101.0, 102.0]}, index=index)
    secondary = pd.DataFrame({"close": [200.0, 201.0, 202.0]}, index=index)
    features = pd.DataFrame({"atr": [1.0, 1.1, 1.2]}, index=index)
    cfg = OmegaConf.create(
        {
            "data": {
                "primary": "ES",
                "secondary": "NQ",
                "cache_dir": str(tmp_path / "cache"),
                "session_schedule_file": "schedule.csv",
                "timestamp_clock": "native",
            },
            "session": {"start": "09:30", "end": "16:00", "tz": "America/New_York"},
        }
    )
    records = {
        name: {"sha256": f"{name}-digest"}
        for name in ("train_bars", "train_features", "test_bars", "test_features")
    }
    pipeline_requests: list[list[str] | None] = []
    attached: list[pd.DataFrame] = []

    def load_pipeline(
        _cfg: Any, *, force: bool, datasets: list[str] | None
    ) -> dict[str, dict[str, pd.DataFrame]]:
        assert force is False
        pipeline_requests.append(datasets)
        return {"ES": {"M1": primary}, "NQ": {"M1": secondary}}

    def split(
        bars: pd.DataFrame,
        frame: pd.DataFrame,
        _train_end: str,
        _test_start: str,
        _train_start: str | None,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        return bars.iloc[:2], bars.iloc[2:], frame.iloc[:2], frame.iloc[2:]

    monkeypatch.setattr(datasets, "run_pipeline", load_pipeline)
    monkeypatch.setattr(
        datasets,
        "build_tick_books",
        lambda *_args, **_kwargs: {"ES": "tick-book"},
    )
    monkeypatch.setattr(
        datasets,
        "get_split_config",
        lambda _cfg: ("2025-01-02T15:01:00Z", "2025-01-02T15:02:00Z"),
    )
    monkeypatch.setattr(datasets, "get_train_start_config", lambda _cfg: None)
    monkeypatch.setattr(datasets, "split_train_test", split)
    monkeypatch.setattr(datasets, "split_bars", lambda bars, *_args: (bars.iloc[:2], bars.iloc[2:]))
    monkeypatch.setattr(pd, "read_parquet", lambda _path: features)

    def attach_context(
        _bars: pd.DataFrame,
        frame: pd.DataFrame,
        *_args: object,
        **_kwargs: object,
    ) -> pd.DataFrame:
        attached.append(frame)
        return frame

    monkeypatch.setattr(datasets, "attach_policy_market_context", attach_context)
    monkeypatch.setattr(datasets, "_evaluation_dataset_records", lambda **_kwargs: records)

    result = datasets.reconstruct_reanalysis_datasets(
        args=SimpleNamespace(
            train_only_screen=False,
            source_feature_cache=str(cache_path),
            train_only_feature_snapshot=None,
            force=False,
            allow_legacy_data_provenance=False,
        ),
        run_dir=run_dir,
        cfg=cfg,
        source_manifest={
            "config": {"sha256": file_sha256(config_path)},
            "feature_cache": {
                "identity": cache_path.name,
                "sha256": "source-content-hash",
                "file_sha256": file_sha256(cache_path),
            },
            "datasets": records,
            "execution_protocol": {"data_source": "frames"},
        },
    )

    assert pipeline_requests == [None]
    assert attached == [features]
    assert result.features is features
    assert result.source_cache_replay_path == cache_path.resolve()
    assert result.feature_cache_disposition == "source_cache_replay_verified"
    assert result.evaluated_feature_cache_hash == "source-content-hash"
    assert result.dataset_parity_disposition == "verified"
    assert result.backend_parity_disposition == "same_backend"
    assert result.train_secondary is not None and len(result.train_secondary) == 2


def test_prebuilt_htf_confirmed_cache_requires_its_sweep_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bars = pd.DataFrame(
        {"close": [100.0, 101.0]},
        index=pd.date_range("2025-01-01", periods=2, freq="min", tz="UTC"),
    )
    cache = tmp_path / "prebuilt.parquet"
    cache.write_bytes(b"cache")
    Path(f"{cache}.hash").write_text("expected\n", encoding="utf-8")
    cfg = OmegaConf.create(
        {
            "data": {"prebuilt_feature_cache": str(cache)},
            "features": {"po3_reference_mode": "htf_confirmed"},
        }
    )
    monkeypatch.setattr(
        "evaluation.reanalysis.provenance.feature_cache_content_hash",
        lambda *_args, **_kwargs: "expected",
    )

    with pytest.raises(FileNotFoundError, match="HTF sweep audit"):
        _feature_build_scope(bars, cfg, tmp_path, "ES", "2025-01-01")

    audit_path = Path(f"{cache}.htf_sweeps.parquet")
    audit_path.touch()
    mask, resolved_cache = _feature_build_scope(bars, cfg, tmp_path, "ES", "2025-01-01")
    assert mask.tolist() == [True, True]
    assert resolved_cache == cache.resolve()


def test_train_only_replay_rejects_full_source_cache_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index = pd.date_range("2025-01-02 15:00", periods=1, freq="min", tz="UTC")
    bars = pd.DataFrame({"close": [100.0]}, index=index)
    cfg = OmegaConf.create(
        {
            "data": {"primary": "ES", "secondary": "NQ", "cache_dir": str(tmp_path)},
        }
    )
    monkeypatch.setattr(
        datasets,
        "run_pipeline",
        lambda *_args, **_kwargs: {"ES": {"M1": bars}},
    )
    monkeypatch.setattr(datasets, "build_tick_books", lambda *_args, **_kwargs: {"ES": None})
    monkeypatch.setattr(datasets, "get_split_config", lambda _cfg: ("train-end", "test-start"))
    monkeypatch.setattr(datasets, "get_train_start_config", lambda _cfg: None)

    with pytest.raises(ValueError, match="cannot use --source-feature-cache"):
        datasets.reconstruct_reanalysis_datasets(
            args=SimpleNamespace(
                train_only_screen=True,
                source_feature_cache="full-cache.parquet",
                train_only_feature_snapshot=None,
                force=False,
                allow_legacy_data_provenance=False,
            ),
            run_dir=tmp_path / "run",
            cfg=cfg,
            source_manifest={"feature_cache": {"identity": "full-cache.parquet"}},
        )
