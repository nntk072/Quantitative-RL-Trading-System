from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pytest
from omegaconf import OmegaConf
from research_tools.features.features import verify_real_market_feature_prefix_invariance as AUDIT


def _stub_m1_input_hashes(cfg: Any) -> dict[str, str]:
    """Provide stable input identities for configuration-only tests."""
    symbols = [
        str(value)
        for value in (
            OmegaConf.select(cfg, "data.primary"),
            OmegaConf.select(cfg, "data.secondary"),
        )
        if value
    ]
    return {
        f"{dataset}/{symbol}": f"fixture:{dataset}:{symbol}"
        for dataset in ("training", "testing")
        for symbol in symbols
    }


def test_feature_group_key_tracks_source_clock_model() -> None:
    cfg = OmegaConf.create(
        {
            "features": {},
            "data": {"tz": "Etc/GMT-3", "timestamp_clock": "native"},
            "session": {"tz": "Etc/GMT-3"},
            "strategy": {"session": {"timezone": "Etc/GMT-3"}},
        }
    )

    native_key = AUDIT.feature_config_key(cfg)
    cfg.data.timestamp_clock = "ftmo_mt5_us_dst"

    assert AUDIT.feature_config_key(cfg) != native_key


def test_feature_group_key_tracks_training_fit_interval() -> None:
    cfg = OmegaConf.create(
        {
            "features": {},
            "data": {
                "tz": "Etc/GMT-3",
                "timestamp_clock": "native",
                "split": {
                    "train_start": "2024-12-30",
                    "train_end": "2025-12-31",
                    "test_start": "2026-01-01",
                },
            },
            "session": {"tz": "Etc/GMT-3"},
            "strategy": {"session": {"timezone": "Etc/GMT-3"}},
        }
    )

    original_key = AUDIT.feature_config_key(cfg)
    cfg.data.split.train_end = "2025-11-30"

    assert AUDIT.feature_config_key(cfg) != original_key


def test_configured_training_mask_honors_train_start_and_end() -> None:
    index = pd.date_range("2024-12-29", periods=4, freq="D", tz="Etc/GMT-3")
    cfg = OmegaConf.create(
        {
            "data": {
                "split": {
                    "train_start": "2024-12-30",
                    "train_end": "2024-12-31",
                    "test_start": "2025-01-01",
                }
            }
        }
    )

    mask = AUDIT.configured_training_mask(index, cfg)

    assert mask.tolist() == [False, True, True, False]


def test_feature_group_key_tracks_configured_m1_content(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = OmegaConf.create(
        {
            "features": {},
            "data": {
                "tz": "Etc/GMT-3",
                "timestamp_clock": "native",
                "primary": "US100.cash",
                "secondary": "US500.cash",
                "split": {"train_start": "2024-12-30", "train_end": "2025-12-31"},
            },
            "session": {"tz": "Etc/GMT-3"},
            "strategy": {"session": {"timezone": "Etc/GMT-3"}},
        }
    )
    inputs = {
        (dataset, symbol): tmp_path / f"{dataset}-{symbol}.csv"
        for dataset in ("training", "testing")
        for symbol in ("US100.cash", "US500.cash")
    }
    for path in inputs.values():
        path.write_text("same input", encoding="utf-8")

    def resolve_input(_cfg: Any, symbol: str, dataset_name: str = "training") -> Path:
        return inputs[(dataset_name, symbol)]

    monkeypatch.setattr(AUDIT, "configured_m1_path", resolve_input)
    original_key = AUDIT.feature_config_key(cfg)
    inputs[("training", "US100.cash")].write_text("different input", encoding="utf-8")

    assert AUDIT.feature_config_key(cfg) != original_key


def test_feature_group_key_tracks_risk_point_size_and_price_grid() -> None:
    cfg = OmegaConf.create(
        {
            "features": {},
            "data": {
                "tz": "Etc/GMT-3",
                "timestamp_clock": "native",
                "price_discretization": {"enabled": False, "increment": 0.25},
            },
            "costs": {"point_size": 0.25},
            "session": {"tz": "Etc/GMT-3", "start": "16:30", "end": "23:00"},
            "strategy": {"session": {"timezone": "Etc/GMT-3"}, "ifvg": {}},
        }
    )
    raw_key = AUDIT.feature_config_key(cfg)
    cfg.data.price_discretization.enabled = True

    assert AUDIT.feature_config_key(cfg) != raw_key
    grid_key = AUDIT.feature_config_key(cfg)
    cfg.costs.point_size = 0.5

    assert AUDIT.feature_config_key(cfg) != grid_key


def test_feature_groups_have_one_effective_builder_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AUDIT, "configured_m1_input_hashes", _stub_m1_input_hashes)
    variant_names = [
        line.strip()
        for line in AUDIT.DEFAULT_VARIANT_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    groups: dict[str, set[str]] = {}
    for name in variant_names:
        cfg, _resolved = AUDIT.config_for_variant(name)
        builder_inputs = {
            "features": OmegaConf.to_container(cfg.features, resolve=True),
            "strategy.ifvg": OmegaConf.to_container(
                OmegaConf.select(cfg, "strategy.ifvg"), resolve=True
            ),
            "data.tz": str(OmegaConf.select(cfg, "data.tz")),
            "data.timestamp_clock": str(OmegaConf.select(cfg, "data.timestamp_clock")),
            "data.session_schedule_file": str(OmegaConf.select(cfg, "data.session_schedule_file")),
            "costs.point_size": str(OmegaConf.select(cfg, "costs.point_size")),
            "session.tz": str(OmegaConf.select(cfg, "session.tz")),
            "session.start": str(OmegaConf.select(cfg, "session.start")),
            "session.end": str(OmegaConf.select(cfg, "session.end")),
            "strategy.session.timezone": str(OmegaConf.select(cfg, "strategy.session.timezone")),
        }
        encoded = json.dumps(builder_inputs, sort_keys=True, default=str)
        groups.setdefault(AUDIT.feature_config_key(cfg), set()).add(encoded)

    assert groups
    assert all(len(configurations) == 1 for configurations in groups.values())


def test_default_variant_file_is_the_registered_experiment_run_list() -> None:
    expected = AUDIT.ROOT / "config" / "experiment_runs" / "variant_list.txt"

    assert AUDIT.DEFAULT_VARIANT_FILE == expected
    assert AUDIT.DEFAULT_VARIANT_FILE.is_file()


def test_training_dataset_resolves_the_shared_local_m1_source() -> None:
    cfg, _resolved = AUDIT.config_for_variant("ladder_a0_flat")

    source = AUDIT.configured_m1_path(cfg, str(cfg.data.primary))

    assert source == AUDIT.ROOT / "data/US100.cash_M1_202412300105_202610162349.csv"
    if not source.is_file():
        pytest.skip("real-market M1 source is external to a clean checkout")


def test_testing_dataset_resolves_the_same_local_m1_source() -> None:
    cfg, _resolved = AUDIT.config_for_variant("ladder_a0_flat")

    source = AUDIT.configured_m1_path(cfg, str(cfg.data.primary), "testing")

    assert source == AUDIT.ROOT / "data/US100.cash_M1_202412300105_202610162349.csv"
    if not source.is_file():
        pytest.skip("real-market M1 source is external to a clean checkout")


def test_registered_datasets_share_source_and_use_disjoint_date_windows() -> None:
    cfg, _resolved = AUDIT.config_for_variant("ladder_a0_flat")
    training = cfg.data.datasets.training
    testing = cfg.data.datasets.testing

    assert training.raw_dir == testing.raw_dir == "data"
    assert training.start_date == cfg.data.split.train_start
    assert training.end_date == cfg.data.split.train_end
    assert testing.start_date == cfg.data.split.test_start
    assert testing.end_date == cfg.data.split.test_end


def test_preprocessed_market_bars_are_reused_without_sharing_mutable_frames(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = OmegaConf.create(
        {
            "data": {"tz": "UTC"},
            "session": {"end": "23:00"},
        }
    )
    source = tmp_path / "bars.csv"
    index = pd.date_range("2026-01-05T10:00:00Z", periods=3, freq="1min")
    raw = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
        },
        index=index,
    )
    load_calls = 0

    def load(_path: Path) -> pd.DataFrame:
        nonlocal load_calls
        load_calls += 1
        return raw.copy()

    monkeypatch.setattr(AUDIT, "configured_m1_path", lambda *_args: source)
    monkeypatch.setattr(AUDIT, "configured_price_grid_increment", lambda _cfg: None)
    monkeypatch.setattr(AUDIT, "load_bars", load)
    raw_cache: dict[Path, pd.DataFrame] = {}
    preprocessed_cache: dict[tuple[Path, str, str, float | None, str | None], pd.DataFrame] = {}
    cache_metrics: dict[str, float | int] = {
        "raw_loads": 0,
        "raw_load_seconds": 0.0,
        "preprocessed_builds": 0,
        "preprocessed_cache_hits": 0,
        "preprocessing_seconds": 0.0,
    }

    first, _ = AUDIT.load_market_bars(
        cfg,
        "US100",
        raw_cache=raw_cache,
        preprocessed_cache=preprocessed_cache,
        cache_metrics=cache_metrics,
    )
    first.loc[index[0], "open"] = -1.0
    second, _ = AUDIT.load_market_bars(
        cfg,
        "US100",
        raw_cache=raw_cache,
        preprocessed_cache=preprocessed_cache,
        cache_metrics=cache_metrics,
    )

    assert load_calls == 1
    assert cache_metrics["raw_loads"] == 1
    assert cache_metrics["preprocessed_builds"] == 1
    assert cache_metrics["preprocessed_cache_hits"] == 1
    assert second.loc[index[0], "open"] == 100.0
    assert {"gap_flag", "session", "session_id"}.issubset(second.columns)


@pytest.mark.parametrize(
    ("config_path", "changed_value"),
    [
        ("data.tz", "Etc/GMT-3"),
        ("session.end", "22:00"),
        ("data.price_increment", 0.25),
    ],
)
def test_preprocessed_market_cache_key_tracks_transform_semantics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    config_path: str,
    changed_value: str | float,
) -> None:
    cfg = OmegaConf.create(
        {
            "data": {"tz": "UTC", "price_increment": None},
            "session": {"end": "23:00"},
        }
    )
    source = tmp_path / "bars.csv"
    index = pd.date_range("2026-01-05T10:00:00Z", periods=3, freq="1min")
    raw = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
        },
        index=index,
    )
    monkeypatch.setattr(AUDIT, "configured_m1_path", lambda *_args: source)
    monkeypatch.setattr(
        AUDIT, "configured_price_grid_increment", lambda value: value.data.price_increment
    )
    monkeypatch.setattr(AUDIT, "load_bars", lambda _path: raw.copy())
    raw_cache: dict[Path, pd.DataFrame] = {}
    preprocessed_cache: dict[tuple[Path, str, str, float | None, str | None], pd.DataFrame] = {}

    AUDIT.load_market_bars(cfg, "US100", raw_cache=raw_cache, preprocessed_cache=preprocessed_cache)
    OmegaConf.update(cfg, config_path, changed_value)
    AUDIT.load_market_bars(cfg, "US100", raw_cache=raw_cache, preprocessed_cache=preprocessed_cache)

    assert len(preprocessed_cache) == 2


def test_load_all_market_bars_applies_timezone_aware_inclusive_cutoff_to_both_splits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = OmegaConf.create(
        {
            "data": {
                "tz": "Etc/GMT-3",
                "split": {
                    "train_start": "2024-12-30",
                    "train_end": "2025-12-31",
                    "test_start": "2026-01-01",
                },
                "datasets": {
                    dataset: {
                        "raw_dir": str(tmp_path / dataset),
                        "m1_files": {
                            symbol: f"{dataset}-{symbol}.csv"
                            for symbol in ("US100.cash", "US500.cash")
                        },
                    }
                    for dataset in ("training", "testing")
                },
            },
            "session": {"end": "23:00"},
        }
    )
    training_index = pd.date_range("2025-12-31 23:57", periods=3, freq="1min")
    training_raw = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
        },
        index=training_index,
    )
    testing_index = pd.date_range("2026-01-01 00:00", periods=2, freq="1min")
    testing_raw = pd.DataFrame(
        {
            "open": [9_999.0, 10_001.0],
            "high": [10_000.0, 10_002.0],
            "low": [9_998.0, 10_000.0],
            "close": [9_999.5, 10_001.5],
        },
        index=testing_index,
    )
    bounded_loads: dict[Path, pd.Timestamp] = {}
    preprocessed_closes: list[float] = []

    def load(path: Path, end_exclusive: pd.Timestamp | None = None) -> pd.DataFrame:
        source = testing_raw if "testing" in path.parts else training_raw
        if end_exclusive is None:
            return source.copy()
        bounded_loads[path] = end_exclusive
        return source.loc[source.index < end_exclusive].copy()

    def quantize(frame: pd.DataFrame, _increment: float | None) -> pd.DataFrame:
        preprocessed_closes.extend(frame["close"].tolist())
        return frame.copy()

    monkeypatch.setattr(AUDIT, "configured_price_grid_increment", lambda _cfg: None)
    monkeypatch.setattr(
        AUDIT,
        "configured_m1_path",
        lambda _cfg, symbol, dataset_name="training": AUDIT.ROOT / dataset_name / f"{symbol}.csv",
    )
    monkeypatch.setattr(AUDIT, "load_bars", load)
    monkeypatch.setattr(
        AUDIT,
        "load_m1_source_index",
        lambda path: testing_index if "testing" in path.parts else training_index,
    )
    monkeypatch.setattr(AUDIT, "quantize_bar_prices", quantize)
    source_indexes: dict[Path, pd.DatetimeIndex] = {}

    for symbol in ("US100.cash", "US500.cash"):
        bars, _paths, splits = AUDIT.load_all_market_bars(
            cfg,
            symbol,
            raw_cache={},
            preprocessed_cache={},
            inclusive_max_timestamp="2025-12-31T20:59:00Z",
            source_index_cache=source_indexes,
        )

        expected_index = training_index.tz_localize("Etc/GMT-3")
        assert bars.index.equals(expected_index)
        assert bars["close"].tolist() == [100.5, 101.5, 102.5]
        assert [(part["dataset"], part["rows"], part["end"]) for part in splits] == [
            ("training", 3, expected_index[-1].isoformat()),
            ("testing", 0, None),
        ]
    assert set(bounded_loads.values()) == {pd.Timestamp("2025-12-31 23:59:00.000000001")}
    assert len(bounded_loads) == 4
    assert preprocessed_closes == [100.5, 101.5, 102.5] * 2
    assert 9_999.5 not in preprocessed_closes


def test_load_all_market_bars_slices_shared_source_by_dataset_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shared_source = AUDIT.ROOT / "data" / "shared.csv"
    cfg = OmegaConf.create(
        {
            "data": {
                "tz": "UTC",
                "split": {
                    "train_start": "2025-12-31",
                    "train_end": "2025-12-31",
                    "test_start": "2026-01-01",
                    "test_end": "2026-01-01",
                },
                "datasets": {
                    "training": {
                        "raw_dir": "data",
                        "m1_files": {"US100.cash": "shared.csv"},
                        "start_date": "2025-12-31",
                        "end_date": "2025-12-31",
                    },
                    "testing": {
                        "raw_dir": "data",
                        "m1_files": {"US100.cash": "shared.csv"},
                        "start_date": "2026-01-01",
                        "end_date": "2026-01-01",
                    },
                },
            },
            "session": {"end": "23:00"},
        }
    )
    index = pd.DatetimeIndex(
        [
            "2025-12-30 23:59:00",
            "2025-12-31 23:58:00",
            "2025-12-31 23:59:00",
            "2026-01-01 00:00:00",
            "2026-01-01 00:01:00",
            "2026-01-02 00:00:00",
        ]
    )
    raw = pd.DataFrame(
        {
            "open": [99.0, 100.0, 101.0, 200.0, 201.0, 299.0],
            "high": [100.0, 101.0, 102.0, 201.0, 202.0, 300.0],
            "low": [98.0, 99.0, 100.0, 199.0, 200.0, 298.0],
            "close": [99.5, 100.5, 101.5, 200.5, 201.5, 299.5],
        },
        index=index,
    )
    load_calls = 0

    def load(_path: Path, **_bounds: Any) -> pd.DataFrame:
        nonlocal load_calls
        load_calls += 1
        return raw.copy()

    monkeypatch.setattr(AUDIT, "configured_price_grid_increment", lambda _cfg: None)
    monkeypatch.setattr(
        AUDIT,
        "configured_m1_path",
        lambda _cfg, _symbol, _dataset_name="training": shared_source,
    )
    monkeypatch.setattr(AUDIT, "load_bars", load)

    bars, paths, splits = AUDIT.load_all_market_bars(
        cfg,
        "US100.cash",
        raw_cache={},
        preprocessed_cache={},
    )

    assert paths == [shared_source, shared_source]
    assert bars["close"].tolist() == [100.5, 101.5, 200.5, 201.5]
    assert bars.index.is_unique and bars.index.is_monotonic_increasing
    assert [(part["dataset"], part["rows"]) for part in splits] == [
        ("training", 2),
        ("testing", 2),
    ]
    assert load_calls == 1


def test_source_index_validation_reads_only_date_time_columns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "bars.csv"
    source.write_text(
        "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\n"
        "2025.12.31\t23:59:00\t100\t101\t99\t100.5\n"
        "2026.01.01\t00:00:00\tBAD_PRICE\tBAD_PRICE\tBAD_PRICE\tBAD_PRICE\n",
        encoding="utf-8",
    )
    read_csv = pd.read_csv
    read_calls: list[tuple[int | None, list[str] | None]] = []

    def track_columns(*args: Any, **kwargs: Any) -> pd.DataFrame:
        nrows = kwargs.get("nrows")
        usecols = kwargs.get("usecols")
        read_calls.append((nrows, list(usecols) if usecols is not None else None))
        return cast(pd.DataFrame, read_csv(*args, **kwargs))

    monkeypatch.setattr(pd, "read_csv", track_columns)

    index = AUDIT.load_m1_source_index(source)

    assert index.tolist() == [
        pd.Timestamp("2025-12-31 23:59:00"),
        pd.Timestamp("2026-01-01 00:00:00"),
    ]
    assert read_calls == [(0, None), (None, ["<DATE>", "<TIME>"])]


def test_load_market_bars_default_keeps_all_source_rows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = OmegaConf.create({"data": {"tz": "UTC"}, "session": {"end": "23:00"}})
    source = tmp_path / "bars.csv"
    index = pd.date_range("2026-01-05T10:00:00Z", periods=3, freq="1min")
    raw = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
        },
        index=index,
    )
    monkeypatch.setattr(AUDIT, "configured_m1_path", lambda *_args: source)
    monkeypatch.setattr(AUDIT, "configured_price_grid_increment", lambda _cfg: None)
    monkeypatch.setattr(AUDIT, "load_bars", lambda _path: raw.copy())

    bars, _source = AUDIT.load_market_bars(cfg, "US100.cash")

    assert bars.index.equals(index)
    assert bars["close"].tolist() == [100.5, 101.5, 102.5]


@pytest.mark.parametrize(
    ("cutoff", "error"),
    [
        ("2025-12-31 23:59:00", "timezone-aware"),
        ("2026-01-05T10:02:00Z", "inside source data range"),
    ],
)
def test_inclusive_max_timestamp_requires_aware_in_range_value(cutoff: str, error: str) -> None:
    index = pd.date_range("2026-01-05T10:00:00Z", periods=3, freq="1min")

    with pytest.raises(ValueError, match=error):
        AUDIT.resolve_inclusive_max_timestamp(cutoff, index, "UTC")


def test_cutoffs_must_leave_later_rows_for_comparison() -> None:
    index = pd.date_range("2025-12-30", periods=3, freq="D", tz="Etc/GMT-3")

    assert AUDIT.resolve_cutoffs(["2025-12-31"], index) == [index[1]]
    with pytest.raises(ValueError, match="later rows available"):
        AUDIT.resolve_cutoffs(["2026-03-09"], index)


def test_compare_prefix_accepts_equal_values_and_nan_masks() -> None:
    index = pd.date_range("2025-12-30", periods=3, freq="D", tz="Etc/GMT-3")
    reference = pd.DataFrame({"signal": [1.0, float("nan"), float("inf")]}, index=index)

    result = AUDIT.compare_prefix(reference, reference.copy(), index[-1])

    assert result["passed"] is True
    assert result["compared_values"] == 3
    assert result["max_abs_delta"] == 0.0


def test_compare_prefix_reports_numeric_and_nan_mask_changes() -> None:
    index = pd.date_range("2025-12-30", periods=3, freq="D", tz="Etc/GMT-3")
    reference = pd.DataFrame({"signal": [1.0, float("nan"), 3.0]}, index=index)
    candidate = pd.DataFrame({"signal": [1.01, 2.0, 3.0]}, index=index)

    result = AUDIT.compare_prefix(reference, candidate, index[-1])

    assert result["passed"] is False
    assert result["changed_feature_count"] == 1
    assert result["changed_features"][0]["mismatch_rows"] == 2
    assert result["changed_features"][0]["nan_mask_mismatches"] == 1
    assert result["changed_features"][0]["max_abs_delta"] == pytest.approx(0.01)


@pytest.mark.parametrize(
    ("candidate", "reason"),
    [
        (
            pd.DataFrame(
                {"signal": [1.0]}, index=pd.date_range("2025-12-30", periods=1, tz="Etc/GMT-3")
            ),
            "prefix indexes differ",
        ),
        (
            pd.DataFrame(
                {"other": [1.0]}, index=pd.date_range("2025-12-30", periods=2, tz="Etc/GMT-3")
            ),
            "feature columns differ",
        ),
    ],
)
def test_compare_prefix_rejects_index_or_column_mismatch(
    candidate: pd.DataFrame, reason: str
) -> None:
    index = pd.date_range("2025-12-30", periods=2, freq="D", tz="Etc/GMT-3")
    reference = pd.DataFrame({"signal": [1.0, 2.0]}, index=index)

    result = AUDIT.compare_prefix(reference, candidate, index[-1])

    assert result["passed"] is False
    assert result["reason"] == reason
