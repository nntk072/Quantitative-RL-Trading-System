"""Regression tests for fold-scoped fitted normalization statistics."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from features.pipeline.normalization import (
    apply_rolling_zscore_state,
    fit_rolling_zscore_state,
    rolling_zscore,
)


def test_frozen_fold_does_not_drift_over_validation_rows() -> None:
    frame = pd.DataFrame({"feature": [10.0, 20.0, 30.0, 40.0, 90.0, 110.0]})
    train_mask = pd.Series([True, True, True, True, False, False])

    normalized = rolling_zscore(frame, window=2, train_mask=train_mask, mode="frozen_fold")

    # Terminal train window = (30, 40), mean=35, population std=5.
    assert normalized.loc[4, "feature"] == pytest.approx((90.0 - 35.0) / 5.0)
    assert normalized.loc[5, "feature"] == pytest.approx((110.0 - 35.0) / 5.0)


def test_frozen_fold_validation_poisoning_preserves_train_values() -> None:
    original = pd.DataFrame({"feature": [10.0, 20.0, 30.0, 40.0, 50.0]})
    altered = original.copy()
    altered.loc[4, "feature"] = 1_000_000.0
    mask = pd.Series([True, True, True, True, False])

    a = rolling_zscore(original, window=2, train_mask=mask, mode="frozen_fold")
    b = rolling_zscore(altered, window=2, train_mask=mask, mode="frozen_fold")

    pd.testing.assert_frame_equal(a.iloc[:4], b.iloc[:4])
    assert a.loc[4, "feature"] == pytest.approx(3.0)
    assert b.loc[4, "feature"] == pytest.approx((1_000_000.0 - 35.0) / 5.0)


@pytest.mark.parametrize("mode", ["legacy_masked_window", "frozen_fold"])
def test_zero_variance_window_maps_finite_values_to_zero(mode: str) -> None:
    frame = pd.DataFrame({"feature": [2.0, 2.0, 2.0, 3.0]})
    mask = pd.Series([True, True, True, False])

    normalized = rolling_zscore(frame, window=2, train_mask=mask, mode=mode)

    assert normalized.loc[1, "feature"] == pytest.approx(0.0)
    assert normalized.loc[2, "feature"] == pytest.approx(0.0)
    assert normalized.loc[3, "feature"] == pytest.approx(1.0)


@pytest.mark.parametrize("mode", ["legacy_masked_window", "frozen_fold"])
def test_fitted_state_reproduces_frozen_validation_transform(mode: str) -> None:
    frame = pd.DataFrame({"feature": [10.0, 20.0, 30.0, 40.0, 90.0, 110.0]})
    train_mask = pd.Series([True, True, True, True, False, False])
    state = fit_rolling_zscore_state(frame, train_mask=train_mask, window=2, mode=mode)

    normalized = rolling_zscore(frame, window=2, train_mask=train_mask, mode=mode)
    live = apply_rolling_zscore_state(frame.iloc[4:].copy(), state)

    pd.testing.assert_frame_equal(live, normalized.iloc[4:])


def test_fitted_state_rejects_changed_feature_order() -> None:
    frame = pd.DataFrame({"first": [1.0, 2.0], "second": [3.0, 4.0]})
    state = fit_rolling_zscore_state(
        frame,
        train_mask=pd.Series([True, True]),
        window=2,
    )

    with pytest.raises(ValueError, match="columns differ"):
        apply_rolling_zscore_state(frame[["second", "first"]], state)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [("mode", "runtime_refit", "unsupported mode"), ("window", 0, "invalid window")],
)
def test_fitted_state_rejects_invalid_fit_contract_metadata(
    field: str, value: object, message: str
) -> None:
    frame = pd.DataFrame({"feature": [1.0, 2.0]})
    state = fit_rolling_zscore_state(
        frame,
        train_mask=pd.Series([True, True]),
        window=2,
    )
    state[field] = value

    with pytest.raises(ValueError, match=message):
        apply_rolling_zscore_state(frame, state)


@pytest.mark.parametrize(
    "operation",
    ["transform", "serialized-state"],
    ids=["transform", "serialized-state"],
)
@pytest.mark.parametrize(
    ("mask", "message"),
    [
        (pd.Series([1, 0, 1]), "boolean dtype"),
        (pd.Series([True, False], index=[0, 1]), "cover every feature row"),
        (pd.Series([False, False, False]), "nonempty training observations"),
        (pd.Series([True, False, True], index=[0, 0, 1]), "unique row indexes"),
    ],
    ids=["non-boolean", "missing-row", "empty-fit", "duplicate-index"],
)
def test_normalization_rejects_invalid_training_masks(
    operation: str, mask: pd.Series[Any], message: str
) -> None:
    frame = pd.DataFrame({"feature": [1.0, 2.0, 3.0]})
    fit = rolling_zscore if operation == "transform" else fit_rolling_zscore_state

    with pytest.raises(ValueError, match=message):
        fit(frame, train_mask=mask)
