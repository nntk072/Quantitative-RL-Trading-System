"""Pipeline dataset selection fails before opening unselected sources."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from omegaconf import DictConfig, OmegaConf

from market_data.loading import market_data_ingestion


def _config(tmp_path: Path, *, configured_datasets: bool) -> DictConfig:
    data: dict[str, object] = {
        "cache_dir": str(tmp_path / "cache"),
        "tz": "UTC",
        "timestamp_clock": "native",
        "bar_timestamp_convention": "open",
        "symbols": ["US100.cash"],
        "timeframes": ["M1"],
        "m1_files": {"US100.cash": "bars.csv"},
    }
    if configured_datasets:
        data["datasets"] = {
            "training": {
                "raw_dir": str(tmp_path / "raw"),
                "m1_files": {"US100.cash": "bars.csv"},
            }
        }
    return OmegaConf.create({"data": data, "session": {"tz": "UTC", "end": "16:00"}})


def test_configured_pipeline_rejects_unknown_dataset_before_source_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        market_data_ingestion,
        "_preflight_bar_sources",
        lambda *_args, **_kwargs: pytest.fail("unknown dataset must fail before source preflight"),
    )

    with pytest.raises(ValueError, match="requested datasets are not configured:.*missing"):
        market_data_ingestion.run_pipeline(
            _config(tmp_path, configured_datasets=True), datasets=["missing"]
        )


def test_single_dataset_pipeline_accepts_only_the_all_selector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        market_data_ingestion,
        "_preflight_bar_sources",
        lambda *_args, **_kwargs: pytest.fail("invalid selector must fail before source preflight"),
    )

    with pytest.raises(ValueError, match="only the 'all' dataset is configured"):
        market_data_ingestion.run_pipeline(
            _config(tmp_path, configured_datasets=False), datasets=["validation"]
        )


@pytest.mark.parametrize(
    ("native_files", "require_native", "message"),
    [
        ({}, True, "native M5 source .* is required but not configured"),
        (
            {"M5": {"US100.cash": "missing-m5.csv"}},
            False,
            "configured native M5 source .* is missing",
        ),
    ],
)
def test_pipeline_rejects_unavailable_native_timeframe_before_cache_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    native_files: dict[str, dict[str, str]],
    require_native: bool,
    message: str,
) -> None:
    cfg = OmegaConf.create(
        {
            "data": {
                "cache_dir": str(tmp_path / "cache"),
                "require_native_timeframes": require_native,
                "tz": "UTC",
                "timestamp_clock": "native",
                "bar_timestamp_convention": "open",
                "symbols": ["US100.cash"],
                "timeframes": ["M1", "M5"],
                "datasets": {
                    "all": {
                        "raw_dir": str(tmp_path / "raw"),
                        "m1_files": {"US100.cash": "m1.csv"},
                        "timeframe_files": native_files,
                    }
                },
            },
            "session": {"tz": "UTC", "end": "23:00"},
        }
    )
    m1 = pd.DataFrame({"close": [100.0]}, index=pd.DatetimeIndex(["2025-01-01 10:00:00"], tz="UTC"))
    monkeypatch.setattr(market_data_ingestion, "_preflight_bar_sources", lambda *_a, **_k: None)
    monkeypatch.setattr(
        market_data_ingestion, "_load_stable_bars", lambda *_args, **_kwargs: (m1, "source-hash")
    )
    monkeypatch.setattr(market_data_ingestion, "quantize_bar_prices", lambda bars, _grid: bars)
    monkeypatch.setattr(market_data_ingestion, "clean", lambda bars, **_kwargs: bars)
    monkeypatch.setattr(market_data_ingestion, "add_session_labels", lambda bars, **_kwargs: bars)
    monkeypatch.setattr(market_data_ingestion, "add_session_id", lambda bars, **_kwargs: bars)
    monkeypatch.setattr(market_data_ingestion, "load_bar_cache", lambda *_args: m1.copy())

    with pytest.raises(FileNotFoundError, match=message):
        market_data_ingestion.run_pipeline(cfg)


def test_pipeline_builds_declared_derived_timeframe_without_native_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = OmegaConf.create(
        {
            "data": {
                "cache_dir": str(tmp_path / "cache"),
                "raw_dir": str(tmp_path / "raw"),
                "m1_files": {"US100.cash": "m1.csv"},
                "derived_timeframes": {"US100.cash": ["M5"]},
                "require_native_timeframes": True,
                "tz": "UTC",
                "timestamp_clock": "native",
                "bar_timestamp_convention": "open",
                "symbols": ["US100.cash"],
                "timeframes": ["M1", "M5"],
            },
            "session": {"tz": "UTC", "end": "23:00"},
        }
    )
    source = pd.DataFrame(
        {"close": [100.0]}, index=pd.DatetimeIndex(["2025-01-01 10:00:00"], tz="UTC")
    )
    derived = pd.DataFrame(
        {"close": [100.0]}, index=pd.DatetimeIndex(["2025-01-01 10:00:00"], tz="UTC")
    )
    calls: list[str] = []
    monkeypatch.setattr(market_data_ingestion, "_preflight_bar_sources", lambda *_a, **_k: None)
    monkeypatch.setattr(market_data_ingestion, "load_bars", lambda *_args, **_kwargs: source.copy())
    monkeypatch.setattr(market_data_ingestion, "quantize_bar_prices", lambda bars, _grid: bars)
    monkeypatch.setattr(market_data_ingestion, "clean", lambda bars, **_kwargs: bars)
    monkeypatch.setattr(market_data_ingestion, "add_session_labels", lambda bars, **_kwargs: bars)
    monkeypatch.setattr(market_data_ingestion, "add_session_id", lambda bars, **_kwargs: bars)

    def resample(bars: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        assert bars is source or bars.equals(source)
        calls.append(timeframe)
        return derived

    monkeypatch.setattr(market_data_ingestion, "resample", resample)

    result = market_data_ingestion.run_pipeline(cfg, end_inclusive="2025-01-01")

    assert calls == ["M5"]
    assert result["US100.cash"]["M5"]["close"].tolist() == [100.0]
    assert not (tmp_path / "cache").exists()


def test_pipeline_rejects_duplicate_rows_after_combining_datasets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = OmegaConf.create(
        {
            "data": {
                "cache_dir": str(tmp_path / "cache"),
                "tz": "UTC",
                "timestamp_clock": "native",
                "bar_timestamp_convention": "open",
                "symbols": ["US100.cash"],
                "timeframes": ["M1"],
                "datasets": {
                    name: {
                        "raw_dir": str(tmp_path / name),
                        "m1_files": {"US100.cash": "bars.csv"},
                    }
                    for name in ("training", "validation")
                },
            },
            "session": {"tz": "UTC", "end": "23:00"},
        }
    )
    source = pd.DataFrame(
        {"close": [100.0]}, index=pd.DatetimeIndex(["2025-01-01 10:00:00"], tz="UTC")
    )
    _patch_nonempty_pipeline(monkeypatch, source)

    with pytest.raises(ValueError, match="overlapping M1 rows in configured data splits"):
        market_data_ingestion.run_pipeline(cfg)


def test_pipeline_fails_closed_if_full_span_cache_identity_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = _config(tmp_path, configured_datasets=False)
    OmegaConf.update(cfg, "data.raw_dir", str(tmp_path / "raw"), force_add=True)
    source = pd.DataFrame(
        {"close": [100.0]}, index=pd.DatetimeIndex(["2025-01-01 10:00:00"], tz="UTC")
    )
    _patch_nonempty_pipeline(monkeypatch, source)
    monkeypatch.setattr(market_data_ingestion, "build_bar_cache_identity", lambda **_kwargs: None)

    with pytest.raises(AssertionError, match="full-span bar processing requires cache identity"):
        market_data_ingestion.run_pipeline(cfg)


def _patch_nonempty_pipeline(monkeypatch: pytest.MonkeyPatch, source: pd.DataFrame) -> None:
    monkeypatch.setattr(market_data_ingestion, "_preflight_bar_sources", lambda *_a, **_k: None)
    monkeypatch.setattr(
        market_data_ingestion,
        "_load_stable_bars",
        lambda *_args, **_kwargs: (source.copy(), "source-hash"),
    )
    monkeypatch.setattr(market_data_ingestion, "quantize_bar_prices", lambda bars, _grid: bars)
    monkeypatch.setattr(market_data_ingestion, "clean", lambda bars, **_kwargs: bars)
    monkeypatch.setattr(market_data_ingestion, "add_session_labels", lambda bars, **_kwargs: bars)
    monkeypatch.setattr(market_data_ingestion, "add_session_id", lambda bars, **_kwargs: bars)
    monkeypatch.setattr(market_data_ingestion, "load_bar_cache", lambda *_args: None)
    monkeypatch.setattr(market_data_ingestion, "write_bar_cache", lambda *_args: None)
