"""Native (Rust ``qrl_native``) backend for the sequential structure kernels.

The Python reference in :mod:`features.technical.swings` stays the default and the oracle.
This module is an explicit, opt-in backend: it never falls back silently. When the native
extension is missing or stale, the call raises ``ImportError`` so the caller chooses the
reference backend deliberately.

Arrays cross the boundary as little-endian bytes (``float64`` values and one byte per boolean
bar). The Rust kernel returns the same columns, in the same order and with the same dtypes, as
the reference frame.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any

import numpy as np
import pandas as pd

NATIVE_KERNEL_NAME = "retained_swing_levels"


def load_qrl_native() -> ModuleType:
    """Import the native extension and check that it exposes the retained-level kernel.

    Returns:
        The imported ``qrl_native`` module.

    Raises:
        ImportError: If the extension is not importable or lacks the kernel (for example a
            wheel built before this kernel existed).
    """
    try:
        native: ModuleType = importlib.import_module("qrl_native")
    except ImportError as exc:
        raise ImportError(
            "retained-level native backend requested but qrl_native is not importable; "
            "build native/python or select backend='python'"
        ) from exc
    if not callable(getattr(native, NATIVE_KERNEL_NAME, None)):
        raise ImportError(
            f"qrl_native does not expose {NATIVE_KERNEL_NAME}; rebuild the native wheel from "
            "this revision or select backend='python'"
        )
    return native


def _from_bytes(payload: bytes, dtype: str) -> np.ndarray[Any, Any]:
    """Decode little-endian bytes into a writable array (a copy, not a read-only view).

    Args:
        payload: Raw bytes produced by the native kernel.
        dtype: Little-endian numpy dtype string of the elements.

    Returns:
        A writable one-dimensional array.
    """
    return np.frombuffer(payload, dtype=dtype).copy()


def _float_bytes(values: np.ndarray[Any, Any]) -> bytes:
    """Encode a float array as contiguous little-endian ``float64`` bytes.

    Args:
        values: Numeric array to encode.

    Returns:
        The raw little-endian bytes of the array.
    """
    return np.ascontiguousarray(values, dtype="<f8").tobytes()


def _bool_bytes(values: np.ndarray[Any, Any]) -> bytes:
    """Encode a boolean array as one byte per element.

    Args:
        values: Boolean array to encode.

    Returns:
        One byte per element, 0 or 1.
    """
    return np.ascontiguousarray(values, dtype=np.uint8).tobytes()


def retained_swing_levels_native(
    swings: pd.DataFrame,
    bars: pd.DataFrame,
    *,
    max_levels: int,
) -> pd.DataFrame:
    """Compute retained swing levels with the native kernel.

    Args:
        swings: Output of :func:`features.technical.swings.detect_swings`.
        bars: OHLC frame aligned with ``swings`` (needs ``high``, ``low`` and ``close``).
        max_levels: Cap on retained levels per side per bar, at least one.

    Returns:
        Frame indexed like ``swings`` with the same columns, order and dtypes as the reference.

    Raises:
        ImportError: If the native extension is unavailable.
        ValueError: If the native kernel refuses the inputs.
    """
    native = load_qrl_native()
    width = max(int(max_levels), 1)
    n = len(swings)
    (
        n_high,
        n_low,
        swept_high,
        swept_low,
        swept_high_loc,
        swept_low_loc,
        high_levels,
        high_locs,
        low_levels,
        low_locs,
    ) = native.retained_swing_levels(
        _bool_bytes(swings["swing_high_event"].to_numpy(dtype=bool)),
        _bool_bytes(swings["swing_low_event"].to_numpy(dtype=bool)),
        _float_bytes(swings["swing_high_extreme"].to_numpy(dtype=float)),
        _float_bytes(swings["swing_low_extreme"].to_numpy(dtype=float)),
        _float_bytes(swings["swing_high_location"].to_numpy(dtype=float)),
        _float_bytes(swings["swing_low_location"].to_numpy(dtype=float)),
        _float_bytes(bars["high"].to_numpy(dtype=float)),
        _float_bytes(bars["low"].to_numpy(dtype=float)),
        _float_bytes(bars["close"].to_numpy(dtype=float)),
        width,
    )
    matrix_shape = (n, width)
    cols: dict[str, np.ndarray[Any, Any]] = {
        "n_retained_highs": _from_bytes(n_high, "<i8").astype(np.int64),
        "n_retained_lows": _from_bytes(n_low, "<i8").astype(np.int64),
        "swept_high": _from_bytes(swept_high, "<f8"),
        "swept_low": _from_bytes(swept_low, "<f8"),
        "swept_high_loc": _from_bytes(swept_high_loc, "<f8"),
        "swept_low_loc": _from_bytes(swept_low_loc, "<f8"),
    }
    high_matrix = _from_bytes(high_levels, "<f8").reshape(matrix_shape)
    high_loc_matrix = _from_bytes(high_locs, "<f8").reshape(matrix_shape)
    low_matrix = _from_bytes(low_levels, "<f8").reshape(matrix_shape)
    low_loc_matrix = _from_bytes(low_locs, "<f8").reshape(matrix_shape)
    for slot in range(width):
        cols[f"retained_high_{slot + 1}"] = high_matrix[:, slot]
        cols[f"retained_low_{slot + 1}"] = low_matrix[:, slot]
        cols[f"retained_high_{slot + 1}_loc"] = high_loc_matrix[:, slot]
        cols[f"retained_low_{slot + 1}_loc"] = low_loc_matrix[:, slot]
    return pd.DataFrame(cols, index=swings.index)
