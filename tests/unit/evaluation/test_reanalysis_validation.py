"""Frozen checkpoint replay rejects incompatible inputs before evaluation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pandas as pd
import pytest

from artifacts.identity import file_sha256
from evaluation.reanalysis import datasets as reanalysis_datasets
from evaluation.reanalysis.validation import (
    resolve_execution_seed,
    resolve_recorded_sequence_schema,
    validate_checkpoint_manifest_hash,
    validate_sequence_input_width,
    validate_stop_candidate_schema,
    validate_train_only_feature_snapshot_request,
)
from evaluation.reporting.run_manifest import build_sequence_feature_schema


def test_train_only_snapshot_request_rejects_conflicting_replay_modes() -> None:
    validate_train_only_feature_snapshot_request(
        train_only_screen=False,
        source_feature_cache=None,
        train_only_feature_snapshot=None,
    )
    with pytest.raises(ValueError, match="requires --train-only-screen"):
        validate_train_only_feature_snapshot_request(
            train_only_screen=False,
            source_feature_cache=None,
            train_only_feature_snapshot="features.parquet",
        )
    with pytest.raises(ValueError, match="cannot be combined"):
        validate_train_only_feature_snapshot_request(
            train_only_screen=True,
            source_feature_cache="source.parquet",
            train_only_feature_snapshot="features.parquet",
        )


def test_execution_seed_prefers_explicit_then_valid_recorded_values() -> None:
    manifest = {
        "seed": True,
        "training_protocol": {"seed": -4},
        "metrics_protocol": {"execution_seed": 17},
    }
    assert resolve_execution_seed(5, manifest) == 5
    assert resolve_execution_seed(None, manifest) == 17
    assert resolve_execution_seed(None, {"training_protocol": {"seed": 9}}) == 9
    assert resolve_execution_seed(None, {"seed": 3}) == 3
    assert resolve_execution_seed(None, {}) is None
    with pytest.raises(ValueError, match="non-negative"):
        resolve_execution_seed(-1, manifest)


def test_sequence_width_requires_checkpoint_observation_shape() -> None:
    model = SimpleNamespace(
        observation_space=SimpleNamespace(spaces={"seq": SimpleNamespace(shape=(64, 7))})
    )
    assert validate_sequence_input_width(model, 7) == 7
    with pytest.raises(ValueError, match="input width disagrees"):
        validate_sequence_input_width(model, 8)
    with pytest.raises(ValueError, match="input width disagrees"):
        validate_sequence_input_width(SimpleNamespace(), 7)


def test_recorded_sequence_schema_checks_replay_scope_and_exact_coordinates() -> None:
    schema = build_sequence_feature_schema(["close", "atr"])
    kwargs = {
        "available_columns": {"close"},
        "generated_columns": {"atr"},
        "train_only_screen": True,
        "has_train_only_feature_snapshot": True,
        "mtf_enabled": False,
        "feature_validity_channels": False,
    }
    resolved, columns = resolve_recorded_sequence_schema(schema, **cast(Any, kwargs))
    assert resolved == schema
    assert columns == ("close", "atr")
    validity_schema = build_sequence_feature_schema(["close"], include_validity_channels=True)
    validity_kwargs = {**kwargs, "generated_columns": set(), "feature_validity_channels": True}
    assert resolve_recorded_sequence_schema(validity_schema, **cast(Any, validity_kwargs)) == (
        validity_schema,
        ("close",),
    )

    invalid_contexts = (
        ({**kwargs, "train_only_screen": False}, "requires --train-only-screen"),
        (
            {**kwargs, "has_train_only_feature_snapshot": False},
            "requires --train-only-feature-snapshot",
        ),
        ({**kwargs, "mtf_enabled": True}, "does not support MTF"),
    )
    for invalid_kwargs, message in invalid_contexts:
        with pytest.raises(ValueError, match=message):
            resolve_recorded_sequence_schema(schema, **cast(Any, invalid_kwargs))

    malformed_schemas = (
        None,
        {**schema, "columns": []},
        {**schema, "columns": ["close", "close"]},
        {**schema, "version": "unknown"},
        {**schema, "columns": ["absent"], "width": 1},
        {**schema, "schema_sha256": "bad"},
    )
    for invalid in malformed_schemas:
        with pytest.raises(ValueError):
            resolve_recorded_sequence_schema(invalid, **cast(Any, kwargs))
    missing_schema = build_sequence_feature_schema(["absent"])
    with pytest.raises(ValueError, match="columns are absent"):
        resolve_recorded_sequence_schema(missing_schema, **cast(Any, kwargs))


def test_stop_schema_and_checkpoint_hash_preserve_legacy_and_versioned_labels(
    tmp_path: Path,
) -> None:
    expected = {"menu": "legacy_last_accepted_swing_v1"}
    assert (
        validate_stop_candidate_schema(
            checkpoint_schema=None,
            manifest_schema=None,
            expected_schema=expected,
            allow_legacy=True,
        )
        == "legacy_opt_in"
    )
    assert (
        validate_stop_candidate_schema(
            checkpoint_schema=expected,
            manifest_schema=expected,
            expected_schema=expected,
            allow_legacy=False,
        )
        == "versioned"
    )
    assert (
        validate_stop_candidate_schema(
            checkpoint_schema={"menu": "old"},
            manifest_schema={"menu": "old"},
            expected_schema=expected,
            allow_legacy=False,
            allow_changed_menu=True,
        )
        == "changed_policy_diagnostic"
    )
    with pytest.raises(ValueError, match="legacy opt-in"):
        validate_stop_candidate_schema(
            checkpoint_schema=None,
            manifest_schema=None,
            expected_schema={"menu": "expanded"},
            allow_legacy=True,
        )

    checkpoint = tmp_path / "checkpoint.zip"
    checkpoint.write_bytes(b"checkpoint bytes")
    digest = file_sha256(checkpoint)
    assert (
        validate_checkpoint_manifest_hash(checkpoint, {"checkpoint": {"sha256": digest}})
        == "verified"
    )
    assert validate_checkpoint_manifest_hash(checkpoint, {}) == "unavailable_legacy_manifest"
    with pytest.raises(ValueError, match="SHA-256"):
        validate_checkpoint_manifest_hash(checkpoint, {"checkpoint": {"sha256": "wrong"}})


@pytest.mark.parametrize("checkpoint_record", [None, [], {}])
def test_checkpoint_manifest_without_hash_is_labeled_legacy(
    tmp_path: Path, checkpoint_record: Any
) -> None:
    checkpoint = tmp_path / "checkpoint.zip"
    checkpoint.write_bytes(b"checkpoint bytes")

    assert (
        validate_checkpoint_manifest_hash(checkpoint, {"checkpoint": checkpoint_record})
        == "unavailable_legacy_manifest"
    )


def test_train_only_feature_snapshot_requires_exact_ordered_timestamp_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = tmp_path / "train_features.parquet"
    snapshot.touch()
    expected = pd.date_range("2026-01-02 16:30", periods=3, freq="min")
    features = pd.DataFrame({"close": [1.0, 2.0, 3.0]}, index=expected)
    monkeypatch.setattr(pd, "read_parquet", lambda _path: features)

    loaded, resolved, digest = reanalysis_datasets._load_train_only_feature_snapshot(
        snapshot, expected
    )
    pd.testing.assert_frame_equal(loaded, features)
    assert resolved == snapshot.resolve()
    assert len(digest) == 64

    with pytest.raises(FileNotFoundError, match="is missing"):
        reanalysis_datasets._load_train_only_feature_snapshot(
            tmp_path / "missing.parquet", expected
        )

    monkeypatch.setattr(pd, "read_parquet", lambda _path: None)
    with pytest.raises(TypeError, match="DataFrame"):
        reanalysis_datasets._load_train_only_feature_snapshot(snapshot, expected)

    monkeypatch.setattr(pd, "read_parquet", lambda _path: pd.DataFrame({"x": [1, 2, 3]}))
    with pytest.raises(ValueError, match="DatetimeIndex"):
        reanalysis_datasets._load_train_only_feature_snapshot(snapshot, expected)

    for invalid_index, message in (
        (pd.DatetimeIndex([expected[0], expected[0], expected[2]]), "unique and ordered"),
        (pd.DatetimeIndex([expected[1], expected[0], expected[2]]), "unique and ordered"),
        (expected[:2], "do not exactly match"),
    ):
        invalid = pd.DataFrame({"close": range(len(invalid_index))}, index=invalid_index)
        monkeypatch.setattr(pd, "read_parquet", lambda _path, value=invalid: value)
        with pytest.raises(ValueError, match=message):
            reanalysis_datasets._load_train_only_feature_snapshot(snapshot, expected)
