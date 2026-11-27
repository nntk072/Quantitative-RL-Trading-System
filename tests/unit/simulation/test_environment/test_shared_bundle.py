"""Tests for atomic, immutable shared environment data bundles."""

from __future__ import annotations

import multiprocessing as mp
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

from tests.unit.simulation.test_environment.test_trading_env_golden_traces import (
    _make_deterministic_bars,
    _make_features,
)


def test_observation_schema_bump_changes_default_bundle_identity() -> None:
    """A new observation tensor layout must not reuse v2 bundles."""
    from simulation.environment.shared_bundle import BUNDLE_VERSION, bundle_key

    arrays, config = _fixture_bundle_inputs()
    sources = {"bars": {"size": len(arrays["bar_time_ns"])}}

    assert BUNDLE_VERSION > 2
    assert bundle_key(config, sources) != bundle_key(config, sources, bundle_version=2)


def test_trade_setup_mask_mode_changes_bundle_identity() -> None:
    from simulation.environment.shared_bundle import bundle_key

    _, config = _fixture_bundle_inputs()
    sources = {"bars": {"size": 32}}
    trade_setup_config = {**config, "env": {**config["env"], "trade_setup_actions": True}}

    assert bundle_key(config, sources) != bundle_key(trade_setup_config, sources)


def test_trade_setup_timeframe_contract_changes_bundle_identity() -> None:
    from simulation.environment.shared_bundle import bundle_key

    _, config = _fixture_bundle_inputs()
    sources = {"bars": {"size": 32}}
    scoped_config = {
        **config,
        "env": {**config["env"], "trade_setup_candidate_timeframes": ["M1"]},
    }

    assert bundle_key(config, sources) != bundle_key(scoped_config, sources)


def test_completed_htf_history_mode_changes_bundle_identity() -> None:
    from simulation.environment.shared_bundle import bundle_key

    _, config = _fixture_bundle_inputs()
    sources = {"bars": {"size": 32}}
    hidden_history = {
        **config,
        "env": {**config["env"], "completed_htf_history_enabled": False},
    }

    assert bundle_key(config, sources) != bundle_key(hidden_history, sources)


def test_source_clock_model_changes_bundle_identity() -> None:
    from simulation.environment.shared_bundle import bundle_key

    _, config = _fixture_bundle_inputs()
    sources = {"bars": {"size": 32}}
    fixed_carrier = {**config, "data": {**config["data"], "timestamp_clock": "native"}}
    helsinki_clock = {
        **config,
        "data": {**config["data"], "timestamp_clock": "europe_helsinki"},
    }

    assert bundle_key(fixed_carrier, sources) != bundle_key(helsinki_clock, sources)


def test_bundle_identity_includes_column_names_and_labels() -> None:
    from simulation.environment.shared_bundle import bundle_key

    _, config = _fixture_bundle_inputs()
    sources = {"bars": {"size": 32}}
    columns = {"features_num": ["london_high", "london_low"]}
    labels = {"session": ["asia", "london", "new_york"]}

    base = bundle_key(config, sources, column_names=columns, labels=labels)
    reordered = bundle_key(
        config,
        sources,
        column_names={"features_num": ["london_low", "london_high"]},
        labels=labels,
    )
    relabeled = bundle_key(
        config,
        sources,
        column_names=columns,
        labels={"session": ["asia", "london", "ny"]},
    )

    assert base != reordered
    assert base != relabeled


def test_load_bundle_rejects_interpretation_metadata_mutation(tmp_path: Path) -> None:
    import json

    from simulation.environment.shared_bundle import build_bundle, load_bundle

    arrays, config = _fixture_bundle_inputs()
    bundle_path = build_bundle(
        tmp_path,
        arrays=arrays,
        config=config,
        source_fingerprints={"bars": {"size": 32}},
        column_names={"features_num": ["london_high", "london_low"]},
        labels={"session": ["asia", "london", "new_york"]},
    )
    manifest_path = bundle_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["labels"]["session"][2] = "ny"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="identity"):
        load_bundle(bundle_path)


def _fixture_bundle_inputs() -> tuple[dict[str, np.ndarray[Any, Any]], dict[str, Any]]:
    """Return deterministic source arrays and an observation-relevant config."""
    bars = _make_deterministic_bars(n=32)
    features = _make_features(bars)
    arrays = {
        "bar_ohlc": bars[["open", "high", "low", "close"]].to_numpy(dtype=np.float64),
        "bar_time_ns": bars.index.to_numpy(dtype="datetime64[ns]").view(np.int64).copy(),
        "features_num": features.to_numpy(dtype=np.float64),
    }
    config = {
        "env": {"obs_window": 10},
        "strategy": {"raw_columns": ["last_swing_high", "last_swing_low"]},
        "features": {"hash": "fixture-v1"},
        "data": {"primary": "US100.cash", "split": {"train_end": "2025-01-31"}},
        "logging": {"level": "INFO"},
    }
    return arrays, config


def _concurrent_build(cache_dir: str, result_queue: Any) -> None:
    """Build one identical bundle in a child process."""
    from simulation.environment.shared_bundle import build_bundle

    arrays, config = _fixture_bundle_inputs()
    result_queue.put(
        str(
            build_bundle(
                cache_dir,
                arrays=arrays,
                config=config,
                source_fingerprints={"bars": {"size": 32}},
            )
        )
    )


def test_bundle_round_trip_matches_source(tmp_path: Path) -> None:
    """Every saved array reloads byte-for-byte equal to its input."""
    from simulation.environment.shared_bundle import build_bundle, load_bundle

    arrays, config = _fixture_bundle_inputs()
    bundle_path = build_bundle(
        tmp_path,
        arrays=arrays,
        config=config,
        source_fingerprints={"bars": {"size": 32}},
        column_names={"features_num": ["london_high", "london_low"]},
    )
    loaded = load_bundle(bundle_path)

    assert set(loaded.arrays) == set(arrays)
    for name, source in arrays.items():
        np.testing.assert_array_equal(loaded.arrays[name], source)
    assert loaded.manifest["column_names"]["features_num"] == [
        "london_high",
        "london_low",
    ]


def test_bundle_load_and_reuse_reject_same_shape_content_tampering(tmp_path: Path) -> None:
    import json

    from simulation.environment.shared_bundle import build_bundle, load_bundle

    arrays, config = _fixture_bundle_inputs()
    bundle_path = build_bundle(
        tmp_path,
        arrays=arrays,
        config=config,
        source_fingerprints={"bars": {"size": 32}},
    )
    array_path = bundle_path / "bar_ohlc.npy"
    corrupted = np.load(array_path, allow_pickle=False)
    corrupted[0, 0] += 1.0
    np.save(array_path, corrupted, allow_pickle=False)
    assert (
        list(corrupted.shape)
        == json.loads((bundle_path / "manifest.json").read_text(encoding="utf-8"))["arrays"][
            "bar_ohlc"
        ]["shape"]
    )

    with pytest.raises(ValueError, match="content digest mismatch"):
        load_bundle(bundle_path)
    with pytest.raises(ValueError, match="content digest mismatch"):
        build_bundle(
            tmp_path,
            arrays=arrays,
            config=config,
            source_fingerprints={"bars": {"size": 32}},
        )


def test_build_is_idempotent(tmp_path: Path) -> None:
    """A second build reuses the completed directory without rewriting files."""
    from simulation.environment.shared_bundle import build_bundle

    arrays, config = _fixture_bundle_inputs()
    first = build_bundle(
        tmp_path,
        arrays=arrays,
        config=config,
        source_fingerprints={"bars": {"size": 32}},
    )
    mtimes = {path.name: path.stat().st_mtime_ns for path in first.iterdir()}
    second = build_bundle(
        tmp_path,
        arrays=arrays,
        config=config,
        source_fingerprints={"bars": {"size": 32}},
    )

    assert second == first
    assert {path.name: path.stat().st_mtime_ns for path in second.iterdir()} == mtimes


def test_reuse_only_validates_and_reuses_existing_bundle(tmp_path: Path) -> None:
    """Reuse-only mode checks identity and data without writing bundle files."""
    from simulation.environment.shared_bundle import build_bundle

    arrays, config = _fixture_bundle_inputs()
    sources = {"bars": {"size": 32}}
    first = build_bundle(
        tmp_path,
        arrays=arrays,
        config=config,
        source_fingerprints=sources,
    )
    mtimes = {path.name: path.stat().st_mtime_ns for path in first.iterdir()}

    reused = build_bundle(
        tmp_path,
        arrays=arrays,
        config=config,
        source_fingerprints=sources,
        reuse_only=True,
    )

    assert reused == first
    assert {path.name: path.stat().st_mtime_ns for path in reused.iterdir()} == mtimes

    altered = {name: value.copy() for name, value in arrays.items()}
    altered["bar_ohlc"][0, 0] += 1.0
    with pytest.raises(ValueError, match="cached bundle array differs"):
        build_bundle(
            tmp_path,
            arrays=altered,
            config=config,
            source_fingerprints=sources,
            reuse_only=True,
        )

    altered_shape = {name: value.copy() for name, value in arrays.items()}
    altered_shape["bar_ohlc"] = altered_shape["bar_ohlc"][:-1]
    with pytest.raises(ValueError, match="cached bundle array metadata differs"):
        build_bundle(
            tmp_path,
            arrays=altered_shape,
            config=config,
            source_fingerprints=sources,
            reuse_only=True,
        )


def test_reuse_only_fails_when_bundle_is_missing(tmp_path: Path) -> None:
    """Reuse-only mode never silently builds a missing bundle."""
    from simulation.environment.shared_bundle import build_bundle

    arrays, config = _fixture_bundle_inputs()
    with pytest.raises(FileNotFoundError, match="required reusable bundle"):
        build_bundle(
            tmp_path,
            arrays=arrays,
            config=config,
            source_fingerprints={"bars": {"size": 32}},
            reuse_only=True,
        )


def test_build_is_atomic_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed array write leaves neither a final bundle nor temporary files."""
    import simulation.environment.shared_bundle as shared_bundle

    arrays, config = _fixture_bundle_inputs()
    key = shared_bundle.bundle_key(config, {"bars": {"size": 32}})
    original_writer = shared_bundle._write_array
    writes = 0

    def fail_writer(path: Path, array: np.ndarray[Any, Any]) -> None:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("simulated write failure")
        original_writer(path, array)

    monkeypatch.setattr(shared_bundle, "_write_array", fail_writer)
    with pytest.raises(OSError, match="simulated write failure"):
        shared_bundle.build_bundle(
            tmp_path,
            arrays=arrays,
            config=config,
            source_fingerprints={"bars": {"size": 32}},
        )

    bundle_root = tmp_path / "shared_env"
    assert not (bundle_root / key).exists()
    assert list(bundle_root.glob(f"{key}.tmp-*")) == []


def test_concurrent_builds_produce_one_bundle(tmp_path: Path) -> None:
    """Concurrent builders serialize on the key lock and return one bundle."""
    context = mp.get_context("spawn")
    results = context.Queue()
    workers = [
        context.Process(target=_concurrent_build, args=(str(tmp_path), results)) for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=30)
        assert worker.exitcode == 0
    paths = [Path(results.get(timeout=10)) for _ in workers]

    assert paths[0] == paths[1]
    assert len(list((tmp_path / "shared_env").glob("*/manifest.json"))) == 1


def test_key_uses_observation_relevant_config_only() -> None:
    """Observation settings affect the key while logging settings do not."""
    from simulation.environment.shared_bundle import bundle_key

    _, config = _fixture_bundle_inputs()
    source_fingerprints = {"bars": {"size": 32}}
    changed_logging = {**config, "logging": {"level": "DEBUG"}}
    changed_window = {**config, "env": {"obs_window": 20}}

    assert bundle_key(config, source_fingerprints) == bundle_key(
        changed_logging, source_fingerprints
    )
    assert bundle_key(config, source_fingerprints) != bundle_key(
        changed_window, source_fingerprints
    )


def test_bundle_arrays_are_read_only(tmp_path: Path) -> None:
    """Every mmap loaded from the bundle is read-only."""
    from simulation.environment.shared_bundle import build_bundle, load_bundle

    arrays, config = _fixture_bundle_inputs()
    bundle_path = build_bundle(
        tmp_path,
        arrays=arrays,
        config=config,
        source_fingerprints={"bars": {"size": 32}},
    )
    loaded = load_bundle(bundle_path)

    assert all(array.flags.writeable is False for array in loaded.arrays.values())


@pytest.mark.parametrize(
    ("arrays", "error", "message"),
    [
        ({}, ValueError, "at least one array"),
        ({"../escape": np.asarray([1])}, ValueError, "invalid bundle array name"),
        ({"bars": object()}, TypeError, "must be a numpy array"),
        ({"bars": np.asarray([object()], dtype=object)}, TypeError, "object dtype"),
    ],
)
def test_build_rejects_unsafe_or_unsupported_array_inputs(
    tmp_path: Path,
    arrays: object,
    error: type[Exception],
    message: str,
) -> None:
    from simulation.environment.shared_bundle import build_bundle

    source_arrays = cast(dict[str, np.ndarray[Any, Any]], arrays)
    with pytest.raises(error, match=message):
        build_bundle(
            tmp_path,
            arrays=source_arrays,
            config={},
            source_fingerprints={},
        )

    assert not (tmp_path / "shared_env").exists()


def test_bundle_key_normalizes_paths_and_ignores_non_mapping_config_branches() -> None:
    from simulation.environment.shared_bundle import bundle_key

    path_config = {"features": Path("features/config.json"), "env": 7}
    string_config = {"features": "features/config.json", "env": 7}

    assert bundle_key(path_config, {}) == bundle_key(string_config, {})


@pytest.mark.parametrize(
    ("mutate_manifest", "message"),
    [
        (lambda manifest: manifest.update(arrays={}), "no array entries"),
        (
            lambda manifest: manifest["arrays"]["bar_ohlc"].update(file="../outside.npy"),
            "invalid array filename",
        ),
        (
            lambda manifest: manifest["arrays"]["bar_ohlc"].update(shape=[1]),
            "array metadata mismatch",
        ),
    ],
)
def test_load_bundle_rejects_missing_entries_and_unsafe_array_paths(
    tmp_path: Path,
    mutate_manifest: Any,
    message: str,
) -> None:
    import json

    from simulation.environment.shared_bundle import build_bundle, load_bundle

    arrays, config = _fixture_bundle_inputs()
    bundle_path = build_bundle(
        tmp_path,
        arrays=arrays,
        config=config,
        source_fingerprints={"bars": {"size": 32}},
    )
    manifest_path = bundle_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutate_manifest(manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_bundle(bundle_path)
