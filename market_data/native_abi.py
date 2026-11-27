"""Python side of the shared data ABI, version 1 (SHARED-DATA-ABI).

The native layer (``native/domain/src/abi`` and ``native/python/src/abi.rs``) takes NumPy arrays
with fixed dtypes and a fixed column order. This module converts the Arrow tables defined in
:mod:`market_data.arrow_schemas` and :mod:`market_data.event_schemas` into those arrays.

Conventions, identical to the Rust layer:

- timestamps are ``int64`` nanoseconds since the epoch in UTC (the Arrow ``timestamp[ns, UTC]``
  physical value);
- a nullable column is a value array plus a ``<name>_valid`` ``uint8`` array (1 = present);
- a missing value is stored as NaN. Converting an Arrow null therefore sets NaN and valid 0.
  Nothing is filled with zero or any other default;
- a table is converted only if it passes the Python validators' schema checks. Converting an
  invalid table does not repair it; the native layer refuses the same defects with typed errors.

The ``*_ABI_LAYOUT`` tuples repeat the Rust layout table. A test in ``native/python/tests`` asserts
that both sides agree, so a change on one side fails until the other side is changed too.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]

from market_data.arrow_schemas import FEATURE_ROW_SCHEMA_ID, SCHEMA_VERSION, require_schema_id

SHARED_DATA_ABI_VERSION = 1
"""Must equal ``qrl_native.shared_data_abi_version()``; checked by the native tests."""

AbiLayout = tuple[tuple[str, str, int, bool], ...]
"""``(name, dtype, rank, nullable)`` per column, in wire order."""

QUOTE_ABI_LAYOUT: AbiLayout = (
    ("event_time_ns", "int64", 1, False),
    ("available_at_ns", "int64", 1, False),
    ("source_sequence", "int64", 1, False),
    ("bid", "float64", 1, True),
    ("ask", "float64", 1, True),
    ("bid_size", "float64", 1, True),
    ("ask_size", "float64", 1, True),
    ("source_flags", "int32", 1, False),
)

BAR_ABI_LAYOUT: AbiLayout = (
    ("event_time_ns", "int64", 1, False),
    ("close_time_ns", "int64", 1, False),
    ("available_at_ns", "int64", 1, False),
    ("source_sequence", "int64", 1, False),
    ("open", "float64", 1, False),
    ("high", "float64", 1, False),
    ("low", "float64", 1, False),
    ("close", "float64", 1, False),
    ("volume", "float64", 1, True),
)

FEATURE_ROW_ABI_LAYOUT: AbiLayout = (
    ("event_time_ns", "int64", 1, False),
    ("available_at_ns", "int64", 1, False),
    ("session_eligible", "uint8", 1, False),
    ("values", "float64", 2, True),
)

OBSERVATION_ABI_LAYOUT: AbiLayout = (
    ("values", "float32", 2, False),
    ("mask", "uint8", 1, False),
)


@dataclass(frozen=True)
class BatchInputs:
    """ABI arguments for one single-instrument batch.

    Attributes:
        schema_id: Schema identity string, as written in the table.
        instrument_id: The one instrument of the batch.
        source_id: The one source of the batch.
        columns: ABI column arrays by name, including ``<name>_valid`` companions.
    """

    schema_id: str
    instrument_id: str
    source_id: str
    columns: dict[str, np.ndarray[Any, Any]]


@dataclass(frozen=True)
class FeatureBlockInputs:
    """ABI arguments for one feature-set block.

    Attributes:
        schema_id: Schema identity string (``feature-row.v1``).
        instrument_id: The one instrument of the block.
        feature_set_id: The one feature set of the block.
        feature_version: The one feature version of the block.
        content_hash: The one content hash of the block.
        width: Feature count declared by the manifest.
        columns: ABI column arrays by name, ``values`` is ``(rows, width)``.
    """

    schema_id: str
    instrument_id: str
    feature_set_id: str
    feature_version: str
    content_hash: str
    width: int
    columns: dict[str, np.ndarray[Any, Any]]


def _single(table: pa.Table, name: str) -> str:
    """Return the one value of a per-row identity column, failing on zero or several values.

    Args:
        table: Arrow table with the identity column.
        name: Column name.

    Returns:
        The single value of the column.
    """
    values = set(table.column(name).to_pylist())
    if len(values) != 1:
        raise ValueError(f"table must carry exactly one {name}, found {sorted(map(str, values))!r}")
    (value,) = values
    return str(value)


def _non_null(table: pa.Table, name: str) -> pa.ChunkedArray:
    """Return a column that the schema declares non-nullable, failing on any null.

    Args:
        table: Arrow table that holds the column.
        name: Column name.

    Returns:
        The non-nullable column.
    """
    column = table.column(name)
    if column.null_count:
        raise ValueError(f"column {name!r} is not nullable but has {column.null_count} null(s)")
    return column


def _ns(table: pa.Table, name: str) -> np.ndarray[Any, Any]:
    """Return a non-nullable timestamp column as contiguous int64 nanoseconds.

    Args:
        table: Arrow table that holds the column.
        name: Column name.

    Returns:
        Contiguous int64 nanosecond timestamps.
    """
    return np.ascontiguousarray(_non_null(table, name).cast(pa.int64()).to_numpy(), dtype=np.int64)


def _int64(table: pa.Table, name: str) -> np.ndarray[Any, Any]:
    """Return a non-nullable integer column as contiguous int64.

    Args:
        table: Arrow table that holds the column.
        name: Column name.

    Returns:
        Contiguous int64 values.
    """
    return np.ascontiguousarray(_non_null(table, name).to_numpy(), dtype=np.int64)


def _nullable_float(
    table: pa.Table, name: str
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    """Return float64 values with NaN at nulls, and a uint8 validity array.

    Args:
        table: Arrow table that holds the column.
        name: Column name.

    Returns:
        Values with NaN at nulls, and a validity array (1 = present).
    """
    column = table.column(name)
    valid = ~column.is_null().to_numpy(zero_copy_only=False)
    raw = column.to_numpy(zero_copy_only=False).astype(np.float64)
    values = np.ascontiguousarray(np.where(valid, raw, np.nan), dtype=np.float64)
    return values, np.ascontiguousarray(valid, dtype=np.uint8)


def _float(table: pa.Table, name: str) -> np.ndarray[Any, Any]:
    """Return a non-nullable float column as contiguous float64.

    Args:
        table: Arrow table that holds the column.
        name: Column name.

    Returns:
        Contiguous float64 values.
    """
    return np.ascontiguousarray(_non_null(table, name).to_numpy(), dtype=np.float64)


def quote_inputs(table: pa.Table) -> BatchInputs:
    """Convert a normalized quote table to quote-batch ABI arrays.

    Args:
        table: Table with the ``QUOTE_SCHEMA`` columns and one instrument and source.

    Returns:
        ABI arguments for ``qrl_native.QuoteBatch.from_columns``.

    Raises:
        ValueError: If the schema is not ``market-event.v1``, identities are not single-valued,
            or a non-nullable column holds a null.
    """
    schema_id = require_schema_id(table, accepted=frozenset({SCHEMA_VERSION}))
    bid, bid_valid = _nullable_float(table, "bid")
    ask, ask_valid = _nullable_float(table, "ask")
    bid_size, bid_size_valid = _nullable_float(table, "bid_size")
    ask_size, ask_size_valid = _nullable_float(table, "ask_size")
    columns: dict[str, np.ndarray[Any, Any]] = {
        "event_time_ns": _ns(table, "event_time"),
        "available_at_ns": _ns(table, "available_at"),
        "source_sequence": _int64(table, "source_sequence"),
        "bid": bid,
        "bid_valid": bid_valid,
        "ask": ask,
        "ask_valid": ask_valid,
        "bid_size": bid_size,
        "bid_size_valid": bid_size_valid,
        "ask_size": ask_size,
        "ask_size_valid": ask_size_valid,
        "source_flags": np.ascontiguousarray(
            _non_null(table, "source_flags").to_numpy(), dtype=np.int32
        ),
    }
    return BatchInputs(
        schema_id=schema_id,
        instrument_id=_single(table, "instrument_id"),
        source_id=_single(table, "source_id"),
        columns=columns,
    )


def bar_inputs(table: pa.Table) -> BatchInputs:
    """Convert a normalized bar table (``BAR_SCHEMA``) to bar-batch ABI arrays.

    Args:
        table: Table with the ``BAR_SCHEMA`` columns and one instrument and source.

    Returns:
        ABI arguments for ``qrl_native.BarBatch.from_columns``.

    Raises:
        ValueError: If the schema is not ``market-event.v1``, identities are not single-valued,
            or a non-nullable column holds a null.
    """
    schema_id = require_schema_id(table, accepted=frozenset({SCHEMA_VERSION}))
    volume, volume_valid = _nullable_float(table, "volume")
    columns: dict[str, np.ndarray[Any, Any]] = {
        "event_time_ns": _ns(table, "event_time"),
        "close_time_ns": _ns(table, "close_time"),
        "available_at_ns": _ns(table, "available_at"),
        "source_sequence": _int64(table, "source_sequence"),
        "open": _float(table, "open"),
        "high": _float(table, "high"),
        "low": _float(table, "low"),
        "close": _float(table, "close"),
        "volume": volume,
        "volume_valid": volume_valid,
    }
    return BatchInputs(
        schema_id=schema_id,
        instrument_id=_single(table, "instrument_id"),
        source_id=_single(table, "source_id"),
        columns=columns,
    )


def feature_block_inputs(table: pa.Table, *, width: int) -> FeatureBlockInputs:
    """Convert a feature-row table (``FEATURE_ROW_SCHEMA``) to feature-block ABI arrays.

    Each ``values`` list must have exactly ``width`` elements, the count in the feature manifest.
    A null list element is a missing feature: its value slot is NaN and its validity is 0.

    Args:
        table: Table with the ``FEATURE_ROW_SCHEMA`` columns for one feature set.
        width: Feature count declared by the manifest.

    Returns:
        ABI arguments for ``qrl_native.FeatureRowBlock.from_columns``.

    Raises:
        ValueError: If identities are not single-valued, the schema differs, or a row's list
            length differs from ``width``.
    """
    schema_id = require_schema_id(table, accepted=frozenset({FEATURE_ROW_SCHEMA_ID}))
    rows = table.num_rows
    values = np.full((rows, width), np.nan, dtype=np.float64)
    valid = np.zeros((rows, width), dtype=np.uint8)
    for row, items in enumerate(_non_null(table, "values").to_pylist()):
        if len(items) != width:
            raise ValueError(f"row {row} has width {len(items)}, expected {width}")
        for column_index, item in enumerate(items):
            if item is not None:
                values[row, column_index] = float(item)
                valid[row, column_index] = 1
    columns: dict[str, np.ndarray[Any, Any]] = {
        "event_time_ns": _ns(table, "event_time"),
        "available_at_ns": _ns(table, "available_at"),
        "session_eligible": np.ascontiguousarray(
            _non_null(table, "session_eligible").to_numpy(zero_copy_only=False), dtype=np.uint8
        ),
        "values": np.ascontiguousarray(values),
        "values_valid": np.ascontiguousarray(valid),
    }
    return FeatureBlockInputs(
        schema_id=schema_id,
        instrument_id=_single(table, "instrument_id"),
        feature_set_id=_single(table, "feature_set_id"),
        feature_version=_single(table, "feature_version"),
        content_hash=_single(table, "content_hash"),
        width=width,
        columns=columns,
    )


def write_cache_atomic(path: Path, data: bytes) -> None:
    """Write a cache container so that readers see either the old file or the complete new one.

    The bytes go to a temporary file in the same directory, are flushed and fsynced, and then
    replace the target with ``os.replace``. A crash leaves at most a stray temporary file, never a
    partial container under the final name.

    Args:
        path: Final cache file path.
        data: Container bytes from ``DatasetView.to_cache_bytes``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def read_cache(path: Path) -> bytes:
    """Return the bytes of a cache container. Validation happens in the native decoder.

    Args:
        path: Cache file path.

    Returns:
        The raw container bytes.
    """
    return path.read_bytes()


__all__ = [
    "BAR_ABI_LAYOUT",
    "BatchInputs",
    "FEATURE_ROW_ABI_LAYOUT",
    "FeatureBlockInputs",
    "OBSERVATION_ABI_LAYOUT",
    "QUOTE_ABI_LAYOUT",
    "SHARED_DATA_ABI_VERSION",
    "bar_inputs",
    "feature_block_inputs",
    "quote_inputs",
    "read_cache",
    "write_cache_atomic",
]
