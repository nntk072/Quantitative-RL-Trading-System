"""Python side of the shared data ABI: layouts and Arrow-to-ABI conversion (SHARED-DATA-ABI).

These tests need no native extension. They check that the ABI layout constants agree with the
Arrow schemas, and that conversion keeps missing values as NaN with an explicit validity array
and never fills them with a default.
"""

from __future__ import annotations

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
import pytest

from market_data.arrow_schemas import BAR_SCHEMA, QUOTE_SCHEMA, SCHEMA_VERSION
from market_data.event_schemas import FEATURE_ROW_SCHEMA
from market_data.native_abi import (
    BAR_ABI_LAYOUT,
    FEATURE_ROW_ABI_LAYOUT,
    OBSERVATION_ABI_LAYOUT,
    QUOTE_ABI_LAYOUT,
    SHARED_DATA_ABI_VERSION,
    bar_inputs,
    feature_block_inputs,
    quote_inputs,
)

UTC_NS = pa.timestamp("ns", tz="UTC")
T0 = np.datetime64("2024-03-04T10:00:00", "ns")
MINUTE = np.timedelta64(1, "m")


def _arrow_to_abi_name(name: str) -> str:
    """Map an Arrow column name to its ABI name: timestamps carry an explicit ``_ns`` unit."""
    timestamp_names = {"event_time", "close_time", "available_at"}
    return f"{name}_ns" if name in timestamp_names else name


def _arrow_dtype_name(field: pa.Field) -> str:
    """Map an Arrow field type to the ABI dtype: timestamps are int64 ns, booleans are uint8."""
    if pa.types.is_timestamp(field.type) or pa.types.is_int64(field.type):
        return "int64"
    if pa.types.is_int32(field.type):
        return "int32"
    if pa.types.is_float64(field.type):
        return "float64"
    if pa.types.is_boolean(field.type):
        return "uint8"
    raise AssertionError(f"no ABI dtype for Arrow type {field.type} on {field.name}")


def _identity_fields(schema: pa.Schema) -> set[str]:
    return {
        "instrument_id",
        "source_id",
        "schema_id",
        "feature_set_id",
        "feature_version",
        "content_hash",
    }


@pytest.mark.parametrize(
    ("schema", "layout"),
    [(QUOTE_SCHEMA, QUOTE_ABI_LAYOUT), (BAR_SCHEMA, BAR_ABI_LAYOUT)],
)
def test_quote_and_bar_layouts_follow_the_arrow_schema_order(
    schema: pa.Schema, layout: tuple[tuple[str, str, int, bool], ...]
) -> None:
    numeric = [field for field in schema if field.name not in _identity_fields(schema)]
    expected = [
        (_arrow_to_abi_name(field.name), _arrow_dtype_name(field), 1, field.nullable)
        for field in numeric
    ]
    assert [(name, dtype, rank, nullable) for name, dtype, rank, nullable in layout] == expected


def test_feature_layout_follows_the_feature_row_schema_order() -> None:
    numeric = [
        field
        for field in FEATURE_ROW_SCHEMA
        if field.name not in _identity_fields(FEATURE_ROW_SCHEMA)
    ]
    names = [_arrow_to_abi_name(field.name) for field in numeric]
    assert names == [name for name, *_ in FEATURE_ROW_ABI_LAYOUT[:3]] + ["values"]
    assert FEATURE_ROW_ABI_LAYOUT[3] == ("values", "float64", 2, True)


def test_observation_layout_is_a_float32_matrix_and_a_uint8_mask() -> None:
    assert OBSERVATION_ABI_LAYOUT == (("values", "float32", 2, False), ("mask", "uint8", 1, False))


def test_python_abi_version_matches_the_rust_contract_version() -> None:
    assert SHARED_DATA_ABI_VERSION == 1


def _quote_table(schema_id: str = SCHEMA_VERSION) -> pa.Table:
    event = (T0 + np.arange(3) * MINUTE).astype("datetime64[ns]")
    return pa.table(
        {
            "event_time": pa.array(event, type=UTC_NS),
            "available_at": pa.array(event, type=UTC_NS),
            "source_sequence": pa.array(np.arange(3, dtype=np.int64)),
            "instrument_id": pa.array(["EURUSD"] * 3),
            "source_id": pa.array(["broker-csv"] * 3),
            "schema_id": pa.array([schema_id] * 3),
            "bid": pa.array([1.1, None, 1.2], type=pa.float64()),
            "ask": pa.array([1.11, 1.11, None], type=pa.float64()),
            "bid_size": pa.array([None, None, None], type=pa.float64()),
            "ask_size": pa.array([2.0, 2.0, 2.0], type=pa.float64()),
            "source_flags": pa.array(np.zeros(3, dtype=np.int32)),
        },
        schema=QUOTE_SCHEMA,
    )


def test_quote_conversion_keeps_nulls_as_nan_with_a_zero_validity_bit() -> None:
    inputs = quote_inputs(_quote_table())
    assert inputs.schema_id == "market-event.v1"
    assert inputs.instrument_id == "EURUSD"
    assert inputs.source_id == "broker-csv"
    bid = inputs.columns["bid"]
    assert bid[0] == 1.1
    assert np.isnan(bid[1])
    assert inputs.columns["bid_valid"].tolist() == [1, 0, 1]
    assert inputs.columns["bid_valid"].dtype == np.uint8
    assert bid.dtype == np.float64
    assert bid.flags.c_contiguous


def test_quote_conversion_never_writes_zero_into_a_missing_slot() -> None:
    inputs = quote_inputs(_quote_table())
    for name in ("bid", "ask", "bid_size", "ask_size"):
        missing = inputs.columns[f"{name}_valid"] == 0
        assert np.isnan(inputs.columns[name][missing]).all(), name


def test_quote_conversion_refuses_a_different_schema_version() -> None:
    with pytest.raises(ValueError, match="unsupported schema_id"):
        quote_inputs(_quote_table(schema_id="market-event.v2"))


def test_quote_conversion_refuses_several_instruments_in_one_batch() -> None:
    table = _quote_table()
    instruments = pa.array(["EURUSD", "EURUSD", "GBPUSD"])
    table = table.set_column(
        table.schema.get_field_index("instrument_id"), "instrument_id", instruments
    )
    with pytest.raises(ValueError, match="exactly one instrument_id"):
        quote_inputs(table)


def test_quote_conversion_refuses_a_null_in_a_non_nullable_column() -> None:
    table = _quote_table()
    sequence = pa.array([0, None, 2], type=pa.int64())
    table = table.set_column(
        table.schema.get_field_index("source_sequence"), "source_sequence", sequence
    )
    with pytest.raises(ValueError, match="source_sequence"):
        quote_inputs(table)


def _bar_table() -> pa.Table:
    event = (T0 + np.arange(2) * MINUTE).astype("datetime64[ns]")
    close = event + MINUTE
    return pa.table(
        {
            "event_time": pa.array(event, type=UTC_NS),
            "close_time": pa.array(close, type=UTC_NS),
            "available_at": pa.array(close, type=UTC_NS),
            "source_sequence": pa.array(np.arange(2, dtype=np.int64)),
            "instrument_id": pa.array(["US100"] * 2),
            "source_id": pa.array(["mt5-export"] * 2),
            "schema_id": pa.array([SCHEMA_VERSION] * 2),
            "open": pa.array([100.0, 100.5], type=pa.float64()),
            "high": pa.array([101.0, 101.0], type=pa.float64()),
            "low": pa.array([99.0, 99.5], type=pa.float64()),
            "close": pa.array([100.5, 100.7], type=pa.float64()),
            "volume": pa.array([None, 7.0], type=pa.float64()),
        },
        schema=BAR_SCHEMA,
    )


def test_bar_conversion_maps_timestamps_to_int64_nanoseconds() -> None:
    table = _bar_table()
    inputs = bar_inputs(table)
    expected_close = table.column("close_time").cast(pa.int64()).to_numpy()
    np.testing.assert_array_equal(inputs.columns["close_time_ns"], expected_close)
    assert inputs.columns["close_time_ns"].dtype == np.int64
    assert inputs.columns["volume_valid"].tolist() == [0, 1]
    assert np.isnan(inputs.columns["volume"][0])


def test_bar_conversion_refuses_a_null_open_price() -> None:
    table = _bar_table()
    table = table.set_column(
        table.schema.get_field_index("open"), "open", pa.array([None, 100.5], type=pa.float64())
    )
    with pytest.raises(ValueError, match="open"):
        bar_inputs(table)


def _feature_table() -> pa.Table:
    event = (T0 + np.arange(3) * MINUTE).astype("datetime64[ns]")
    return pa.table(
        {
            "event_time": pa.array(event, type=UTC_NS),
            "available_at": pa.array(event, type=UTC_NS),
            "instrument_id": pa.array(["US100"] * 3),
            "feature_set_id": pa.array(["core-v1"] * 3),
            "feature_version": pa.array(["1.0.0"] * 3),
            "content_hash": pa.array(["sha256:abc"] * 3),
            "schema_id": pa.array(["feature-row.v1"] * 3),
            "session_eligible": pa.array([True, False, True]),
            "values": pa.array(
                [[None, None], [0.5, None], [0.7, 0.8]],
                type=pa.list_(pa.field("item", pa.float64(), nullable=True)),
            ),
        },
        schema=FEATURE_ROW_SCHEMA,
    )


def test_feature_conversion_marks_null_list_items_missing_and_keeps_manifest_order() -> None:
    inputs = feature_block_inputs(_feature_table(), width=2)
    assert inputs.schema_id == "feature-row.v1"
    assert inputs.feature_set_id == "core-v1"
    assert inputs.content_hash == "sha256:abc"
    assert inputs.columns["values_valid"].tolist() == [[0, 0], [1, 0], [1, 1]]
    values = inputs.columns["values"]
    assert np.isnan(values[0]).all()
    assert values[2].tolist() == [0.7, 0.8]
    assert inputs.columns["session_eligible"].tolist() == [1, 0, 1]
    assert inputs.columns["session_eligible"].dtype == np.uint8


def test_feature_conversion_refuses_a_width_that_differs_from_the_manifest() -> None:
    with pytest.raises(ValueError, match="row 0 has width 2, expected 3"):
        feature_block_inputs(_feature_table(), width=3)


def test_feature_conversion_refuses_a_feature_row_schema_it_does_not_accept() -> None:
    table = _feature_table()
    table = table.set_column(
        table.schema.get_field_index("schema_id"), "schema_id", pa.array(["feature-row.v2"] * 3)
    )
    with pytest.raises(ValueError, match="unsupported schema_id"):
        feature_block_inputs(table, width=2)
