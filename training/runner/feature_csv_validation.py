"""Validation for externally supplied feature matrices."""

from __future__ import annotations

import numpy as np
import pandas as pd


def validate_feature_csv_against_canonical(
    supplied: pd.DataFrame,
    canonical: pd.DataFrame,
    *,
    rtol: float = 1e-12,
    atol: float = 1e-12,
) -> None:
    """Require a supplied feature matrix to match the local fit-scoped build.

    Args:
        supplied: Feature rows loaded from a caller-provided CSV.
        canonical: Features rebuilt from local bars/config with train-only fit scope.
        rtol: Relative comparison tolerance for CSV float round-tripping.
        atol: Absolute comparison tolerance for CSV float round-tripping.

    Raises:
        ValueError: If row identity, column identity, or any value differs.
    """
    if not supplied.index.is_unique or not canonical.index.is_unique:
        raise ValueError("feature CSV and canonical feature index must be unique")
    if not supplied.index.equals(canonical.index):
        raise ValueError("feature CSV index does not exactly match the source bars")
    if not supplied.columns.equals(canonical.columns):
        raise ValueError("feature CSV columns/order do not match the configured feature build")
    try:
        supplied_values = supplied.to_numpy(dtype=np.float64)
        canonical_values = canonical.to_numpy(dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("feature CSV and canonical feature matrix must be numeric") from exc
    if supplied_values.shape != canonical_values.shape:
        raise ValueError("feature CSV shape does not match the configured feature build")

    equal = np.isclose(supplied_values, canonical_values, rtol=rtol, atol=atol, equal_nan=True)
    if not bool(equal.all()):
        row, column = np.argwhere(~equal)[0]
        raise ValueError(
            "feature CSV differs from the train-scoped canonical build at "
            f"row={supplied.index[int(row)]!s}, column={supplied.columns[int(column)]!s}"
        )


__all__ = ["validate_feature_csv_against_canonical"]
