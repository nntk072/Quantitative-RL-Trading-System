from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pandas as pd
import pytest
from omegaconf import OmegaConf

from market_data.loading import market_data_ingestion


def test_stable_bar_load_rejects_source_changed_while_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "bars.csv"
    source.write_text("original", encoding="utf-8")

    def replace_during_parse(path: Path, **_kwargs: object) -> pd.DataFrame:
        path.write_text("replacement", encoding="utf-8")
        return pd.DataFrame({"close": [1.0]})

    monkeypatch.setattr(market_data_ingestion, "load_bars", replace_during_parse)

    with pytest.raises(RuntimeError, match="changed while being parsed"):
        market_data_ingestion._load_stable_bars(source)


def test_stable_bar_load_rejects_identity_mismatch_before_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "bars.csv"
    source.write_text("current", encoding="utf-8")
    called = False

    def unexpected_parse(*_args: object, **_kwargs: object) -> pd.DataFrame:
        nonlocal called
        called = True
        return pd.DataFrame({"close": [1.0]})

    monkeypatch.setattr(market_data_ingestion, "load_bars", unexpected_parse)

    with pytest.raises(RuntimeError, match="does not match cache identity"):
        market_data_ingestion._load_stable_bars(source, expected_sha256="wrong")

    assert not called


def test_stable_bar_load_returns_the_digest_of_the_bytes_it_parsed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "bars.csv"
    source.write_text("stable source", encoding="utf-8")
    parsed = pd.DataFrame({"close": [100.0]})
    monkeypatch.setattr(market_data_ingestion, "load_bars", lambda *_args, **_kwargs: parsed)

    bars, digest = market_data_ingestion._load_stable_bars(source, expected_sha256=None)

    assert bars is parsed
    assert digest == cast(Any, market_data_ingestion).file_sha256(source)


@pytest.mark.parametrize(
    "diagnostics",
    [
        {"out_of_order_rows": 1},
        {"conflicting_duplicate_timestamps": 1},
    ],
)
def test_preflight_rejects_source_diagnostics_before_cache_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, diagnostics: dict[str, int]
) -> None:
    frame = pd.DataFrame({"close": [100.0]}, index=pd.DatetimeIndex(["2025-01-02 10:00"]))
    frame.attrs["source_diagnostics"] = diagnostics
    monkeypatch.setattr(market_data_ingestion, "load_bars", lambda *_args, **_kwargs: frame)

    with pytest.raises(ValueError, match="chronology/duplicate diagnostics"):
        market_data_ingestion._preflight_bar_sources(
            [("training", tmp_path, {"US100.cash": "m1.csv"}, {}, None, None)],
            ["US100.cash"],
            ["M1"],
            end_inclusive="2025-01-31",
        )


def test_preflight_allows_nonoverlapping_rows_across_dataset_splits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frames = iter(
        [
            pd.DataFrame({"close": [100.0]}, index=pd.DatetimeIndex(["2025-01-02 10:00"])),
            pd.DataFrame({"close": [101.0]}, index=pd.DatetimeIndex(["2025-01-03 10:00"])),
        ]
    )
    monkeypatch.setattr(market_data_ingestion, "load_bars", lambda *_args, **_kwargs: next(frames))
    specs: list[tuple[str, Path, dict[str, str], dict[str, Any], None, None]] = [
        (name, tmp_path, {"US100.cash": "m1.csv"}, {}, None, None)
        for name in ("training", "validation")
    ]

    market_data_ingestion._preflight_bar_sources(specs, ["US100.cash"], ["M1"], end_inclusive=None)


def test_preflight_rejects_dataset_date_bounds_in_reverse_order(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="start_date after end_date"):
        market_data_ingestion._preflight_bar_sources(
            [("training", tmp_path, {"US100.cash": "bars.csv"}, {}, "2025-02-01", "2025-01-01")],
            ["US100.cash"],
            ["M1"],
            end_inclusive=None,
        )


def test_preflight_rejects_overlapping_rows_before_cache_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index = pd.DatetimeIndex([pd.Timestamp("2025-01-02 10:00:00")])
    frame = pd.DataFrame({"close": [100.0]}, index=index)
    frame.attrs["source_diagnostics"] = {}
    monkeypatch.setattr(market_data_ingestion, "load_bars", lambda *_args, **_kwargs: frame)
    specs: list[tuple[str, Path, dict[str, str], dict[str, Any], str | None, str | None]] = [
        (name, tmp_path, {"US100.cash": "bars.csv"}, {}, None, None)
        for name in ("training", "validation")
    ]

    with pytest.raises(ValueError, match="overlapping M1 rows"):
        market_data_ingestion._preflight_bar_sources(
            specs, ["US100.cash"], ["M1"], end_inclusive=None
        )


def test_preflight_loads_unique_native_sources_with_effective_date_bounds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[Path, pd.Timestamp | None, pd.Timestamp | None]] = []
    frame = pd.DataFrame({"close": [100.0]}, index=pd.DatetimeIndex(["2025-01-03 10:00:00"]))

    def record_load(
        path: Path,
        *,
        start_inclusive: pd.Timestamp | None = None,
        end_exclusive: pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        seen.append((path, start_inclusive, end_exclusive))
        return frame.copy()

    monkeypatch.setattr(market_data_ingestion, "load_bars", record_load)

    market_data_ingestion._preflight_bar_sources(
        [
            (
                "training",
                tmp_path,
                {"US100.cash": "m1.tsv"},
                {
                    "M1": {"US100.cash": "m1.tsv"},
                    "M5": {"US100.cash": "m5.tsv"},
                },
                "2025-01-02",
                "2025-01-04",
            )
        ],
        ["US100.cash"],
        ["M1", "M5"],
        end_inclusive="2025-01-03",
    )

    assert seen == [
        (
            tmp_path / "m1.tsv",
            pd.Timestamp("2025-01-02"),
            pd.Timestamp("2025-01-04"),
        ),
        (
            tmp_path / "m5.tsv",
            pd.Timestamp("2025-01-02"),
            pd.Timestamp("2025-01-04"),
        ),
    ]


def test_pipeline_rejects_reverse_dataset_dates_before_source_access(
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
                    "training": {
                        "raw_dir": str(tmp_path / "training"),
                        "m1_files": {"US100.cash": "bars.csv"},
                        "start_date": "2025-02-01",
                        "end_date": "2025-01-01",
                    }
                },
            },
            "session": {"tz": "UTC", "end": "23:00"},
        }
    )
    monkeypatch.setattr(market_data_ingestion, "_preflight_bar_sources", lambda *_a, **_k: None)
    monkeypatch.setattr(
        market_data_ingestion,
        "_load_stable_bars",
        lambda *_args, **_kwargs: pytest.fail("invalid date bounds must fail before source access"),
    )

    with pytest.raises(ValueError, match="start_date after end_date"):
        market_data_ingestion.run_pipeline(cfg)


def test_pipeline_rejects_close_stamped_data_before_reading_sources(
    tmp_path: Path,
) -> None:
    from omegaconf import OmegaConf

    cfg = OmegaConf.create(
        {
            "data": {
                "cache_dir": str(tmp_path),
                "tz": "UTC",
                "timestamp_clock": "native",
                "bar_timestamp_convention": "close",
            },
            "session": {"tz": "UTC", "end": "23:00"},
        }
    )

    with pytest.raises(ValueError, match="open-stamped bars"):
        market_data_ingestion.run_pipeline(cfg)


def test_pipeline_selects_requested_dataset_and_caps_rows_at_inclusive_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    training_dir = tmp_path / "training"
    report_dir = tmp_path / "report"
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
                    "training": {
                        "raw_dir": str(training_dir),
                        "m1_files": {"US100.cash": "train.csv"},
                        "start_date": "2025-01-01",
                        "end_date": "2025-01-05",
                    },
                    "report": {
                        "raw_dir": str(report_dir),
                        "m1_files": {"US100.cash": "report.csv"},
                    },
                },
            },
            "session": {"tz": "UTC", "end": "23:00"},
        }
    )
    source = pd.DataFrame(
        {"close": [100.0, 101.0, 102.0]},
        index=pd.DatetimeIndex(["2025-01-01 12:00Z", "2025-01-02 12:00Z", "2025-01-03 00:00Z"]),
    )
    observed: dict[str, Any] = {}

    def preflight(specs: Any, *_args: Any, **_kwargs: Any) -> None:
        observed["datasets"] = [spec[0] for spec in specs]

    def load_bars(path: Path, **kwargs: Any) -> pd.DataFrame:
        observed["source_path"] = path
        observed["load_kwargs"] = kwargs
        return source.copy()

    monkeypatch.setattr(market_data_ingestion, "_preflight_bar_sources", preflight)
    monkeypatch.setattr(market_data_ingestion, "load_bars", load_bars)
    monkeypatch.setattr(market_data_ingestion, "quantize_bar_prices", lambda bars, _grid: bars)
    monkeypatch.setattr(market_data_ingestion, "clean", lambda bars, **_kwargs: bars)
    monkeypatch.setattr(market_data_ingestion, "add_session_labels", lambda bars, **_kwargs: bars)
    monkeypatch.setattr(market_data_ingestion, "add_session_id", lambda bars, **_kwargs: bars)

    result = market_data_ingestion.run_pipeline(
        cfg, datasets=["training"], end_inclusive="2025-01-02"
    )

    assert observed["datasets"] == ["training"]
    assert observed["source_path"] == training_dir / "train.csv"
    assert observed["load_kwargs"]["end_exclusive"] == pd.Timestamp("2025-01-03")
    assert result["US100.cash"]["M1"]["close"].tolist() == [100.0, 101.0]
    assert result["US100.cash"]["M1"].index.max() < pd.Timestamp("2025-01-03", tz="UTC")
    assert not (tmp_path / "cache").exists()


def test_pipeline_uses_legacy_all_dataset_and_preserves_empty_timeframe_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir = tmp_path / "cache"
    cfg = OmegaConf.create(
        {
            "data": {
                "cache_dir": str(cache_dir),
                "raw_dir": str(tmp_path / "bars"),
                "m1_files": {"US100.cash": "US100_M1.csv"},
                "tz": "UTC",
                "timestamp_clock": "native",
                "bar_timestamp_convention": "open",
                "symbols": ["US100.cash"],
                "timeframes": ["M1", "M5"],
            },
            "session": {"tz": "UTC", "end": "23:00"},
        }
    )
    source = pd.DataFrame(index=pd.DatetimeIndex([], tz="UTC", name="datetime"))
    observed: dict[str, Any] = {}
    monkeypatch.setattr(
        market_data_ingestion,
        "_preflight_bar_sources",
        lambda specs, *_args, **_kwargs: observed.update(dataset_names=[x[0] for x in specs]),
    )
    monkeypatch.setattr(
        market_data_ingestion,
        "_load_stable_bars",
        lambda path, **_kwargs: (observed.update(source=path) or source.copy(), "source-hash"),
    )
    monkeypatch.setattr(market_data_ingestion, "quantize_bar_prices", lambda bars, _grid: bars)

    result = market_data_ingestion.run_pipeline(cfg)

    assert observed["dataset_names"] == ["all"]
    assert observed["source"] == tmp_path / "bars" / "US100_M1.csv"
    assert cache_dir.is_dir()
    assert result["US100.cash"]["M1"].empty
    assert result["US100.cash"]["M5"].empty
    m5_index = result["US100.cash"]["M5"].index
    assert isinstance(m5_index, pd.DatetimeIndex)
    assert m5_index.tz is not None


def test_pipeline_rejects_unknown_dataset_before_preflight(
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
                    "training": {
                        "raw_dir": str(tmp_path / "training"),
                        "m1_files": {"US100.cash": "bars.csv"},
                    }
                },
            },
            "session": {"tz": "UTC", "end": "23:00"},
        }
    )
    monkeypatch.setattr(
        market_data_ingestion,
        "_preflight_bar_sources",
        lambda *_args, **_kwargs: pytest.fail("unknown datasets must fail before preflight"),
    )

    with pytest.raises(ValueError, match="requested datasets are not configured"):
        market_data_ingestion.run_pipeline(cfg, datasets=["report"])
