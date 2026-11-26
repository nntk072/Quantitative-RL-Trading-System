"""DatasetView at the Python boundary: folds, fitted state, copies and cache corruption (SHARED-DATA-ABI)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

ViewFactory = Callable[..., Any]


def test_view_reports_rows_folds_fitted_and_a_stable_hash(make_view: ViewFactory) -> None:
    first = make_view([(1, 3, 4, 6, 0, 0)], ("norm-v1", 1, 2))
    second = make_view([(1, 3, 4, 6, 0, 0)], ("norm-v1", 1, 2))
    assert first.rows == 6
    assert first.folds == [(1, 3, 4, 6, 0, 0)]
    assert first.fitted == ("norm-v1", 1, 2)
    assert first.content_hash == second.content_hash
    assert len(first.content_hash) == 16


def test_bars_and_features_are_copies_with_the_same_values(make_view: ViewFactory) -> None:
    view = make_view([(1, 3, 4, 6, 0, 0)])
    bars = view.bars()
    assert bars.rows == 6
    assert bars.instrument_id == "US100"
    features = view.features()
    assert features.width == 2
    assert features.feature_set_id == "core-v1"


def test_purge_and_embargo_that_do_not_fit_are_refused(native: Any, make_view: ViewFactory) -> None:
    with pytest.raises(native.AbiError, match="purge and embargo must fit"):
        make_view([(1, 3, 4, 6, 2, 1)])


def test_overlapping_test_folds_are_refused(native: Any, make_view: ViewFactory) -> None:
    with pytest.raises(native.AbiError, match="test folds must not overlap"):
        make_view([(1, 2, 3, 5, 0, 0), (1, 3, 4, 6, 0, 0)])


def test_fitted_state_outside_the_training_range_is_refused(
    native: Any, make_view: ViewFactory
) -> None:
    with pytest.raises(native.AbiError, match="outside this fold's training range"):
        make_view([(1, 3, 4, 6, 0, 0)], ("norm-v1", 0, 4))


def test_fitted_state_without_folds_is_refused(native: Any, make_view: ViewFactory) -> None:
    with pytest.raises(native.AbiError, match="requires folds"):
        make_view([], ("norm-v1", 1, 2))


def test_cache_round_trip_keeps_hash_folds_and_fitted_state(
    native: Any, make_view: ViewFactory
) -> None:
    view = make_view([(1, 3, 4, 6, 0, 0)], ("norm-v1", 1, 2))
    data = bytes(view.to_cache_bytes())
    restored = native.dataset_view_from_cache_bytes(data)
    assert restored.content_hash == view.content_hash
    assert restored.folds == view.folds
    assert restored.fitted == view.fitted
    assert bytes(restored.to_cache_bytes()) == data


def test_every_single_byte_flip_of_the_cache_is_refused(
    native: Any, small_view_bytes: bytes
) -> None:
    for index in range(len(small_view_bytes)):
        corrupt = bytearray(small_view_bytes)
        corrupt[index] ^= 0x5A
        with pytest.raises(native.AbiError):
            native.dataset_view_from_cache_bytes(bytes(corrupt))


def test_every_truncation_of_the_cache_is_refused(native: Any, small_view_bytes: bytes) -> None:
    for length in range(len(small_view_bytes)):
        with pytest.raises(native.AbiError):
            native.dataset_view_from_cache_bytes(small_view_bytes[:length])


def test_cache_refusals_raise_the_cache_exception_class(
    native: Any, small_view_bytes: bytes
) -> None:
    data = bytearray(small_view_bytes)
    data[-1] ^= 0x01
    with pytest.raises(native.AbiCacheError, match="checksum mismatch"):
        native.dataset_view_from_cache_bytes(bytes(data))
    assert issubclass(native.AbiCacheError, native.AbiError)


def test_cache_with_an_unsupported_version_raises_the_version_error(
    native: Any, small_view_bytes: bytes
) -> None:
    data = bytearray(small_view_bytes)
    data[8] = 2
    with pytest.raises(native.AbiVersionError, match="version 2"):
        native.dataset_view_from_cache_bytes(bytes(data))
