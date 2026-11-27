"""Train-only reanalysis keeps feature snapshots bound to the training rows."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest
from omegaconf import OmegaConf

from evaluation.reanalysis import datasets


def test_reconstruction_uses_exact_train_only_feature_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bars = pd.DataFrame(
        {"close": [100.0, 101.0]},
        index=pd.date_range("2025-01-02 15:00", periods=2, freq="min", tz="UTC"),
    )
    snapshot = tmp_path / "training.parquet"
    snapshot.touch()
    feature_frame = pd.DataFrame({"atr": [1.0, 1.1]}, index=bars.index)
    ticks = {"ES": "training-ticks"}
    cfg = OmegaConf.create(
        {
            "data": {
                "primary": "ES",
                "secondary": "NQ",
                "cache_dir": str(tmp_path / "cache"),
                "session_schedule_file": "schedule.csv",
            },
            "session": {"start": "09:30", "end": "16:00", "tz": "America/New_York"},
        }
    )
    observed: dict[str, Any] = {}

    monkeypatch.setattr(pd, "read_parquet", lambda _path: feature_frame)

    def load_pipeline(_cfg: Any, *, force: bool, datasets: list[str] | None) -> dict[str, Any]:
        observed["pipeline_request"] = (force, datasets)
        return {"ES": {"M1": bars}}

    monkeypatch.setattr(datasets, "run_pipeline", load_pipeline)
    monkeypatch.setattr(
        datasets,
        "build_tick_books",
        lambda _cfg, *, symbols, datasets: {"ES": ticks} if symbols == ["ES"] else {},
    )
    monkeypatch.setattr(datasets, "get_split_config", lambda _cfg: ("train-end", "test-start"))
    monkeypatch.setattr(datasets, "get_train_start_config", lambda _cfg: None)

    def split(
        _bars: pd.DataFrame,
        features: pd.DataFrame,
        _train_end: str,
        _test_start: str,
        _train_start: str | None,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        observed["features"] = features
        return bars, bars.iloc[:0], features, features.iloc[:0]

    monkeypatch.setattr(datasets, "split_train_test", split)
    monkeypatch.setattr(
        datasets,
        "_evaluation_dataset_records",
        lambda **_kwargs: {"train_features": {"sha256": "training-frame-sha256"}},
    )
    monkeypatch.setattr(
        datasets, "_validate_reanalysis_datasets", lambda *_args, **_kwargs: "matched"
    )
    monkeypatch.setattr(
        datasets, "_reanalysis_backend_disposition", lambda *_args, **_kwargs: ("frame", "matched")
    )
    monkeypatch.setattr(
        datasets,
        "attach_policy_market_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("snapshot is already assembled")
        ),
    )

    result = datasets.reconstruct_reanalysis_datasets(
        args=SimpleNamespace(
            train_only_screen=True,
            source_feature_cache=None,
            train_only_feature_snapshot=str(snapshot),
            force=True,
            allow_legacy_data_provenance=False,
        ),
        run_dir=tmp_path / "run",
        cfg=cfg,
        source_manifest={"datasets": {}, "execution_protocol": {}},
    )

    assert observed["pipeline_request"] == (True, ["training"])
    pd.testing.assert_frame_equal(observed["features"], feature_frame)
    pd.testing.assert_frame_equal(result.train_features, feature_frame)
    pd.testing.assert_frame_equal(result.test_features, feature_frame.iloc[:0])
    assert result.primary_ticks == ticks
    assert result.train_feature_snapshot_path == snapshot.resolve()
    assert (
        result.feature_cache_disposition == "train_only_feature_snapshot_verified_by_frame_sha256"
    )
    assert result.evaluated_feature_cache_hash == "training-frame-sha256"
    assert result.dataset_parity_disposition == "matched"


def test_source_cache_replay_rejects_a_changed_saved_run_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "config.yaml").write_text("changed config", encoding="utf-8")
    bars = pd.DataFrame(
        {"close": [100.0]},
        index=pd.date_range("2025-01-02 15:00", periods=1, freq="min", tz="UTC"),
    )
    cfg = OmegaConf.create(
        {
            "data": {
                "primary": "ES",
                "secondary": "NQ",
                "cache_dir": str(tmp_path / "cache"),
            }
        }
    )
    monkeypatch.setattr(
        datasets,
        "run_pipeline",
        lambda _cfg, *, force, datasets: {"ES": {"M1": bars}},
    )
    monkeypatch.setattr(
        datasets,
        "build_tick_books",
        lambda _cfg, *, symbols, datasets: {"ES": None},
    )

    with pytest.raises(ValueError, match="does not match its manifest SHA-256"):
        datasets.reconstruct_reanalysis_datasets(
            args=SimpleNamespace(
                train_only_screen=False,
                source_feature_cache="cache/features.parquet",
                train_only_feature_snapshot=None,
                force=False,
                allow_legacy_data_provenance=False,
            ),
            run_dir=run_dir,
            cfg=cfg,
            source_manifest={
                "config": {"sha256": "0" * 64},
                "feature_cache": {},
                "datasets": {},
            },
        )


def test_train_only_rebuild_uses_training_partition_and_records_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bars = pd.DataFrame(
        {"close": [100.0, 101.0, 102.0]},
        index=pd.date_range("2025-01-02 15:00", periods=3, freq="min", tz="UTC"),
    )
    features = pd.DataFrame({"atr": [1.0, 1.1, 1.2]}, index=bars.index)
    cfg = OmegaConf.create(
        {
            "data": {
                "primary": "ES",
                "secondary": "NQ",
                "cache_dir": str(tmp_path / "cache"),
                "session_schedule_file": "schedule.csv",
            },
            "session": {"start": "09:30", "end": "16:00", "tz": "America/New_York"},
        }
    )
    cache = tmp_path / "cache" / "training.parquet"
    mask = pd.Series([True, True, False], index=bars.index)
    observed: dict[str, Any] = {}

    def load_pipeline(_cfg: Any, *, force: bool, datasets: list[str] | None) -> dict[str, Any]:
        observed["pipeline"] = (force, datasets)
        return {"ES": {"M1": bars}}

    def build_features(
        _bars: pd.DataFrame, *, train_mask: pd.Series, cache_path: Path, **_kwargs: Any
    ) -> pd.DataFrame:
        observed["train_mask"] = train_mask.copy()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(b"rebuilt training feature cache")
        Path(f"{cache_path}.hash").write_text("train-cache-hash\n", encoding="utf-8")
        return features

    monkeypatch.setattr(datasets, "run_pipeline", load_pipeline)
    monkeypatch.setattr(datasets, "build_tick_books", lambda *_args, **_kwargs: {"ES": None})
    monkeypatch.setattr(datasets, "get_split_config", lambda _cfg: ("train-end", "test-start"))
    monkeypatch.setattr(datasets, "get_train_start_config", lambda _cfg: None)
    monkeypatch.setattr(datasets, "_feature_build_scope", lambda *_args, **_kwargs: (mask, cache))
    monkeypatch.setattr(datasets, "build_features", build_features)
    monkeypatch.setattr(
        datasets,
        "attach_policy_market_context",
        lambda _bars, frame, *_args, **_kwargs: frame,
    )
    monkeypatch.setattr(
        datasets,
        "split_train_test",
        lambda _bars, frame, *_args: (bars.iloc[:2], bars.iloc[2:], frame.iloc[:2], frame.iloc[2:]),
    )
    monkeypatch.setattr(
        datasets,
        "_evaluation_dataset_records",
        lambda **_kwargs: {
            "train_bars": {"sha256": "train-bars"},
            "train_features": {"sha256": "train-features"},
        },
    )

    result = datasets.reconstruct_reanalysis_datasets(
        args=SimpleNamespace(
            train_only_screen=True,
            source_feature_cache=None,
            train_only_feature_snapshot=None,
            force=True,
            allow_legacy_data_provenance=False,
        ),
        run_dir=tmp_path / "run",
        cfg=cfg,
        source_manifest={
            "datasets": {
                "train_bars": {"sha256": "train-bars"},
                "train_features": {"sha256": "train-features"},
            }
        },
    )

    assert observed["pipeline"] == (True, ["training"])
    pd.testing.assert_series_equal(observed["train_mask"], mask)
    assert result.feature_cache == cache
    assert result.feature_cache_disposition == (
        "training_partition_rebuilt_train_feature_digest_checked"
    )
    assert result.evaluated_feature_cache_hash == "train-cache-hash"
    assert (
        result.dataset_parity_disposition == "train_only_verified_full_tick_identity_not_reloaded"
    )
