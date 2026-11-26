"""Round trips and refusals of the shared data ABI at the Python boundary (SHARED-DATA-ABI).

Arrays are built from the Arrow schemas, converted by ``market_data.native_abi``, passed to the
native batches, read back as bytes and compared with the inputs. Refusals must raise the typed
exception named for their category, with the column in the message.
"""

from __future__ import annotations

from typing import Any

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

qrl_native = pytest.importorskip("qrl_native")

T0 = np.datetime64("2024-03-04T10:00:00", "ns")
MINUTE = np.timedelta64(1, "m")
UTC_NS = pa.timestamp("ns", tz="UTC")


def _times(rows: int) -> np.ndarray[Any, Any]:
    return (T0 + np.arange(rows) * MINUTE).astype("datetime64[ns]")


def _quote_table(rows: int = 4) -> pa.Table:
    event = _times(rows)
    bid: list[float | None] = [1.10 + 0.001 * i for i in range(rows)]
    ask: list[float | None] = [1.11 + 0.001 * i for i in range(rows)]
    bid[1] = None  # one-sided quote: bid missing
    return pa.table(
        {
            "event_time": pa.array(event, type=UTC_NS),
            "available_at": pa.array(event, type=UTC_NS),
            "source_sequence": pa.array(np.arange(rows, dtype=np.int64)),
            "instrument_id": pa.array(["EURUSD"] * rows),
            "source_id": pa.array(["broker-csv"] * rows),
            "schema_id": pa.array([SCHEMA_VERSION] * rows),
            "bid": pa.array(bid, type=pa.float64()),
            "ask": pa.array(ask, type=pa.float64()),
            "bid_size": pa.array([5.0] * rows, type=pa.float64()),
            "ask_size": pa.array([None] * rows, type=pa.float64()),
            "source_flags": pa.array(np.zeros(rows, dtype=np.int32)),
        },
        schema=QUOTE_SCHEMA,
    )


def _bar_table(rows: int = 3) -> pa.Table:
    event = _times(rows)
    close = event + MINUTE
    return pa.table(
        {
            "event_time": pa.array(event, type=UTC_NS),
            "close_time": pa.array(close, type=UTC_NS),
            "available_at": pa.array(close, type=UTC_NS),
            "source_sequence": pa.array(np.arange(rows, dtype=np.int64)),
            "instrument_id": pa.array(["US100"] * rows),
            "source_id": pa.array(["mt5-export"] * rows),
            "schema_id": pa.array([SCHEMA_VERSION] * rows),
            "open": pa.array([100.0] * rows, type=pa.float64()),
            "high": pa.array([101.0] * rows, type=pa.float64()),
            "low": pa.array([99.0] * rows, type=pa.float64()),
            "close": pa.array([100.5] * rows, type=pa.float64()),
            "volume": pa.array(
                [10.0, None, 12.0][:rows] + [1.0] * max(0, rows - 3), type=pa.float64()
            ),
        },
        schema=BAR_SCHEMA,
    )


def _feature_table(rows: int = 3, width: int = 2) -> pa.Table:
    event = _times(rows)
    values = [[None] * width] + [[0.5 + i] * width for i in range(1, rows)]
    return pa.table(
        {
            "event_time": pa.array(event, type=UTC_NS),
            "available_at": pa.array(event, type=UTC_NS),
            "instrument_id": pa.array(["US100"] * rows),
            "feature_set_id": pa.array(["core-v1"] * rows),
            "feature_version": pa.array(["1.0.0"] * rows),
            "content_hash": pa.array(["sha256:abc"] * rows),
            "schema_id": pa.array(["feature-row.v1"] * rows),
            "session_eligible": pa.array([True] * rows),
            "values": pa.array(
                values, type=pa.list_(pa.field("item", pa.float64(), nullable=True))
            ),
        },
        schema=FEATURE_ROW_SCHEMA,
    )


def _bytes_to(batch: Any, name: str, dtype: str) -> np.ndarray[Any, Any]:
    return np.frombuffer(batch.column(name), dtype=dtype)


# ---- version and layout ----------------------------------------------------------------------


def test_native_version_is_the_python_version() -> None:
    assert qrl_native.shared_data_abi_version() == SHARED_DATA_ABI_VERSION == 1


def test_require_abi_version_refuses_other_versions() -> None:
    qrl_native.require_abi_version(1)
    with pytest.raises(qrl_native.AbiVersionError, match="version 2"):
        qrl_native.require_abi_version(2)


@pytest.mark.parametrize(
    ("payload", "layout"),
    [
        ("quote", QUOTE_ABI_LAYOUT),
        ("bar", BAR_ABI_LAYOUT),
        ("feature_row", FEATURE_ROW_ABI_LAYOUT),
        ("observation", OBSERVATION_ABI_LAYOUT),
    ],
)
def test_native_layout_matches_the_python_layout_in_order(
    payload: str, layout: tuple[tuple[str, str, int, bool], ...]
) -> None:
    native = [
        (name, dtype, rank, nullable)
        for name, dtype, rank, nullable, _unit in qrl_native.abi_layout(payload)
    ]
    assert native == list(layout)


def test_observation_widths_match_the_decisioning_coordinate_tuples() -> None:
    from decisioning.observations import V1_COORDINATES, V2_COORDINATES

    assert qrl_native.observation_width("account-state-v1") == len(V1_COORDINATES) == 6
    assert qrl_native.observation_width("account-state-v2") == len(V2_COORDINATES) == 28
    with pytest.raises(qrl_native.AbiVersionError):
        qrl_native.observation_width("feature-row.v1")


def test_native_schema_ids_are_the_python_schema_constants() -> None:
    from decisioning.observations import OBSERVATION_SCHEMA_V1, OBSERVATION_SCHEMA_V2
    from market_data.arrow_schemas import (
        BAR_REVISED_SCHEMA_ID,
        FEATURE_ROW_SCHEMA_ID,
        NORMALIZED_EVENT_SCHEMA_ID,
        SCHEMA_VERSION,
    )

    python_ids = {
        SCHEMA_VERSION,
        NORMALIZED_EVENT_SCHEMA_ID,
        FEATURE_ROW_SCHEMA_ID,
        BAR_REVISED_SCHEMA_ID,
        OBSERVATION_SCHEMA_V1,
        OBSERVATION_SCHEMA_V2,
    }
    assert set(qrl_native.schema_ids()) == python_ids


def test_unknown_payload_name_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="unknown payload"):
        qrl_native.abi_layout("tick")


# ---- round trips -----------------------------------------------------------------------------


def test_quote_round_trip_keeps_values_masks_and_missing_slots() -> None:
    table = _quote_table()
    inputs = quote_inputs(table)
    batch = qrl_native.QuoteBatch.from_columns(
        schema_id=inputs.schema_id,
        instrument_id=inputs.instrument_id,
        source_id=inputs.source_id,
        columns=inputs.columns,
    )

    assert batch.rows == 4
    assert batch.schema_id == "market-event.v1"
    assert batch.instrument_id == "EURUSD"
    for name in ("event_time_ns", "available_at_ns", "source_sequence"):
        np.testing.assert_array_equal(_bytes_to(batch, name, "<i8"), inputs.columns[name])
    np.testing.assert_array_equal(
        _bytes_to(batch, "source_flags", "<i4"), inputs.columns["source_flags"]
    )
    np.testing.assert_array_equal(_bytes_to(batch, "bid", "<f8"), inputs.columns["bid"])
    np.testing.assert_array_equal(_bytes_to(batch, "bid_valid", "u1"), inputs.columns["bid_valid"])
    assert _bytes_to(batch, "bid_valid", "u1").tolist() == [1, 0, 1, 1]
    assert np.isnan(_bytes_to(batch, "bid", "<f8")[1])
    assert _bytes_to(batch, "ask_size_valid", "u1").tolist() == [0, 0, 0, 0]


def test_bar_round_trip_keeps_ohlc_and_missing_volume() -> None:
    inputs = bar_inputs(_bar_table())
    batch = qrl_native.BarBatch.from_columns(
        schema_id=inputs.schema_id,
        instrument_id=inputs.instrument_id,
        source_id=inputs.source_id,
        columns=inputs.columns,
    )
    assert batch.rows == 3
    for name in ("open", "high", "low", "close"):
        np.testing.assert_array_equal(_bytes_to(batch, name, "<f8"), inputs.columns[name])
    np.testing.assert_array_equal(
        _bytes_to(batch, "close_time_ns", "<i8"), inputs.columns["close_time_ns"]
    )
    assert _bytes_to(batch, "volume_valid", "u1").tolist() == [1, 0, 1]


def test_feature_round_trip_keeps_warm_up_missing_and_matrix_order() -> None:
    inputs = feature_block_inputs(_feature_table(rows=3, width=2), width=2)
    block = qrl_native.FeatureRowBlock.from_columns(
        schema_id=inputs.schema_id,
        instrument_id=inputs.instrument_id,
        feature_set_id=inputs.feature_set_id,
        feature_version=inputs.feature_version,
        content_hash=inputs.content_hash,
        width=inputs.width,
        columns=inputs.columns,
    )
    assert block.rows == 3
    assert block.width == 2
    assert block.feature_set_id == "core-v1"
    values = _bytes_to(block, "values", "<f8").reshape(3, 2)
    np.testing.assert_array_equal(values, inputs.columns["values"])
    assert np.isnan(values[0]).all()
    assert _bytes_to(block, "values_valid", "u1").reshape(3, 2)[0].tolist() == [0, 0]
    assert _bytes_to(block, "session_eligible", "u1").tolist() == [1, 1, 1]


def test_observation_round_trip_keeps_left_padding_and_float32_values() -> None:
    values = np.zeros((4, 6), dtype=np.float32)
    values[2:] = np.arange(12, dtype=np.float32).reshape(2, 6) / 10.0
    mask = np.array([0, 0, 1, 1], dtype=np.uint8)
    window = qrl_native.ObservationWindow.from_columns(
        schema_id="account-state-v1", columns={"values": values, "mask": mask}
    )
    assert window.rows == 4
    assert window.width == 6
    np.testing.assert_array_equal(_bytes_to(window, "values", "<f4").reshape(4, 6), values)
    np.testing.assert_array_equal(_bytes_to(window, "mask", "u1"), mask)


def test_native_batch_is_a_copy_and_ignores_later_changes_to_the_arrays() -> None:
    inputs = bar_inputs(_bar_table())
    # Arrow-backed arrays are read-only, so the caller's writable copy is the one mutated.
    writable = dict(inputs.columns)
    writable["close"] = np.array(inputs.columns["close"], copy=True)
    before = writable["close"].copy()
    batch = qrl_native.BarBatch.from_columns(
        schema_id=inputs.schema_id,
        instrument_id=inputs.instrument_id,
        source_id=inputs.source_id,
        columns=writable,
    )
    writable["close"][:] = -1.0
    np.testing.assert_array_equal(_bytes_to(batch, "close", "<f8"), before)


def test_read_only_arrays_are_accepted_because_the_native_side_only_reads() -> None:
    inputs = bar_inputs(_bar_table())
    for array in inputs.columns.values():
        array.flags.writeable = False
    batch = qrl_native.BarBatch.from_columns(
        schema_id=inputs.schema_id,
        instrument_id=inputs.instrument_id,
        source_id=inputs.source_id,
        columns=inputs.columns,
    )
    assert batch.rows == 3


def test_unknown_column_name_on_a_batch_is_a_key_error() -> None:
    inputs = bar_inputs(_bar_table())
    batch = qrl_native.BarBatch.from_columns(
        schema_id=inputs.schema_id,
        instrument_id=inputs.instrument_id,
        source_id=inputs.source_id,
        columns=inputs.columns,
    )
    with pytest.raises(KeyError, match="no column named"):
        batch.column("vwap")


# ---- rejections: dtype and byte order (TypeError) ---------------------------------------------


def _quote_columns() -> dict[str, np.ndarray[Any, Any]]:
    return dict(quote_inputs(_quote_table(3)).columns)


def _build_quote(
    columns: dict[str, np.ndarray[Any, Any]], schema_id: str = "market-event.v1"
) -> Any:
    return qrl_native.QuoteBatch.from_columns(
        schema_id=schema_id, instrument_id="EURUSD", source_id="broker-csv", columns=columns
    )


@pytest.mark.parametrize(
    ("column", "replacement"),
    [
        ("bid", lambda: np.array([1.1, 1.1, 1.1], dtype=np.float32)),
        ("source_sequence", lambda: np.array([0, 1, 2], dtype=np.int32)),
        ("bid_valid", lambda: np.array([True, True, True])),
        ("bid", lambda: np.array([1.1, 1.1, 1.1], dtype=">f8")),
        ("bid", lambda: [1.1, 1.1, 1.1]),
    ],
)
def test_wrong_dtype_byte_order_or_non_buffer_is_a_type_error(
    column: str, replacement: Any
) -> None:
    columns = _quote_columns()
    columns[column] = replacement()
    with pytest.raises(TypeError):
        _build_quote(columns)


def test_numpy_bool_mask_is_refused_because_the_mask_dtype_is_uint8() -> None:
    columns = _quote_columns()
    columns["ask_valid"] = np.array([True, True, True])
    with pytest.raises(TypeError, match="ask_valid"):
        _build_quote(columns)


# ---- rejections: layout (AbiError) -----------------------------------------------------------


def test_non_contiguous_strided_view_is_refused_not_copied() -> None:
    columns = _quote_columns()
    wide = np.repeat(np.array([1.1, 0.0, 1.1, 0.0, 1.1, 0.0]), 1)
    columns["bid"] = wide[::2]
    with pytest.raises(qrl_native.AbiError, match="bid: array must be C-contiguous"):
        _build_quote(columns)


def test_fortran_order_matrix_is_refused() -> None:
    inputs = feature_block_inputs(_feature_table(rows=3, width=2), width=2)
    columns = dict(inputs.columns)
    columns["values"] = np.asfortranarray(columns["values"])
    with pytest.raises(qrl_native.AbiError, match="values: array must be C-contiguous"):
        qrl_native.FeatureRowBlock.from_columns(
            schema_id=inputs.schema_id,
            instrument_id=inputs.instrument_id,
            feature_set_id=inputs.feature_set_id,
            feature_version=inputs.feature_version,
            content_hash=inputs.content_hash,
            width=2,
            columns=columns,
        )


def test_length_mismatch_names_the_column() -> None:
    columns = _quote_columns()
    columns["ask"] = np.array([1.11, 1.11], dtype=np.float64)
    columns["ask_valid"] = np.array([1, 1], dtype=np.uint8)
    with pytest.raises(qrl_native.AbiError, match="ask: expected length 3, found 2"):
        _build_quote(columns)


def test_missing_and_unexpected_keys_are_refused() -> None:
    columns = _quote_columns()
    del columns["bid_size_valid"]
    with pytest.raises(qrl_native.AbiError, match='missing column "bid_size_valid"'):
        _build_quote(columns)
    columns = _quote_columns()
    columns["mid"] = np.zeros(3)
    with pytest.raises(qrl_native.AbiError, match='unexpected column "mid"'):
        _build_quote(columns)


def test_matrix_where_a_vector_is_required_is_refused() -> None:
    columns = _quote_columns()
    columns["bid"] = np.zeros((3, 1), dtype=np.float64)
    with pytest.raises(qrl_native.AbiError, match="bid: expected 1 dimension"):
        _build_quote(columns)


def test_empty_batch_is_refused_rather_than_reported_as_success() -> None:
    columns = {
        name: np.zeros(
            0, dtype=np.int64 if name.endswith("_ns") or name == "source_sequence" else np.float64
        )
        for name in (
            "event_time_ns",
            "available_at_ns",
            "source_sequence",
            "bid",
            "ask",
            "bid_size",
            "ask_size",
        )
    }
    columns["bid_valid"] = np.zeros(0, dtype=np.uint8)
    columns["ask_valid"] = np.zeros(0, dtype=np.uint8)
    columns["bid_size_valid"] = np.zeros(0, dtype=np.uint8)
    columns["ask_size_valid"] = np.zeros(0, dtype=np.uint8)
    columns["source_flags"] = np.zeros(0, dtype=np.int32)
    with pytest.raises(qrl_native.AbiError, match="at least one row"):
        _build_quote(columns)


# ---- rejections: finiteness, sentinels and masks (AbiError) -----------------------------------


@pytest.mark.parametrize("bad", [np.inf, -np.inf, np.nan])
def test_non_finite_present_price_is_refused_at_its_row(bad: float) -> None:
    columns = _quote_columns()
    columns["ask"] = np.array([1.11, bad, 1.11])
    with pytest.raises(qrl_native.AbiError, match=r"ask\[1\]: present values must be finite"):
        _build_quote(columns)


def test_sentinel_zero_in_a_missing_slot_is_refused() -> None:
    columns = _quote_columns()
    columns["bid"] = np.array([1.1, 0.0, 1.1])  # bid_valid[1] == 0 from the Arrow null
    with pytest.raises(qrl_native.AbiError, match=r"bid\[1\]: a missing value must be NaN"):
        _build_quote(columns)


def test_mask_value_other_than_zero_or_one_is_refused() -> None:
    columns = _quote_columns()
    columns["bid_valid"] = np.array([1, 2, 1], dtype=np.uint8)
    with pytest.raises(qrl_native.AbiError, match=r"bid_valid\[1\]: mask values must be 0 or 1"):
        _build_quote(columns)


def test_non_positive_price_is_refused() -> None:
    columns = _quote_columns()
    columns["bid"] = np.array([1.1, -0.5, 1.1])
    columns["bid_valid"] = np.array([1, 1, 1], dtype=np.uint8)
    with pytest.raises(qrl_native.AbiError, match=r"bid\[1\]: value must be strictly positive"):
        _build_quote(columns)


def test_observation_with_nan_coordinate_is_refused() -> None:
    values = np.zeros((2, 6), dtype=np.float32)
    values[1, 3] = np.nan
    with pytest.raises(qrl_native.AbiError, match=r"values\[1\]: present values must be finite"):
        qrl_native.ObservationWindow.from_columns(
            schema_id="account-state-v1",
            columns={"values": values, "mask": np.array([1, 1], dtype=np.uint8)},
        )


# ---- rejections: schema and version (AbiVersionError) ------------------------------------------


@pytest.mark.parametrize("schema_id", ["market-event.v3", "feature-row.v1", "market-event.v2", ""])
def test_unknown_or_foreign_quote_schema_is_refused(schema_id: str) -> None:
    with pytest.raises(qrl_native.AbiVersionError, match="unsupported schema_id"):
        _build_quote(_quote_columns(), schema_id=schema_id)


def test_bar_v2_is_refused_until_a_revision_is_resolved_to_a_v1_view() -> None:
    inputs = bar_inputs(_bar_table())
    with pytest.raises(qrl_native.AbiVersionError, match="market-event.v2"):
        qrl_native.BarBatch.from_columns(
            schema_id="market-event.v2",
            instrument_id=inputs.instrument_id,
            source_id=inputs.source_id,
            columns=inputs.columns,
        )


def test_observation_width_must_match_its_schema() -> None:
    values = np.zeros((2, 28), dtype=np.float32)
    with pytest.raises(qrl_native.AbiError, match="values: expected width 6, found 28"):
        qrl_native.ObservationWindow.from_columns(
            schema_id="account-state-v1",
            columns={"values": values, "mask": np.array([1, 1], dtype=np.uint8)},
        )


def test_observation_padding_must_be_a_zero_left_prefix() -> None:
    values = np.zeros((3, 6), dtype=np.float32)
    values[2] = 0.1
    with pytest.raises(
        qrl_native.AbiError, match=r"observation\[1\]: padding must precede real rows"
    ):
        qrl_native.ObservationWindow.from_columns(
            schema_id="account-state-v1",
            columns={"values": values, "mask": np.array([1, 0, 1], dtype=np.uint8)},
        )


def test_feature_width_must_match_the_manifest_width() -> None:
    inputs = feature_block_inputs(_feature_table(rows=3, width=2), width=2)
    with pytest.raises(qrl_native.AbiError, match="values: expected width 3, found 2"):
        qrl_native.FeatureRowBlock.from_columns(
            schema_id=inputs.schema_id,
            instrument_id=inputs.instrument_id,
            feature_set_id=inputs.feature_set_id,
            feature_version=inputs.feature_version,
            content_hash=inputs.content_hash,
            width=3,
            columns=inputs.columns,
        )


def test_feature_row_list_of_the_wrong_length_is_refused_by_the_adapter() -> None:
    table = _feature_table(rows=3, width=2)
    with pytest.raises(ValueError, match="row 0 has width 2, expected 3"):
        feature_block_inputs(table, width=3)


def test_feature_information_after_event_time_is_refused_natively() -> None:
    table = _feature_table(rows=2, width=2)
    late = table.set_column(
        table.schema.get_field_index("available_at"),
        "available_at",
        pa.array(_times(2) + MINUTE, type=UTC_NS),
    )
    inputs = feature_block_inputs(late, width=2)
    with pytest.raises(qrl_native.AbiError, match="available after its event_time"):
        qrl_native.FeatureRowBlock.from_columns(
            schema_id=inputs.schema_id,
            instrument_id=inputs.instrument_id,
            feature_set_id=inputs.feature_set_id,
            feature_version=inputs.feature_version,
            content_hash=inputs.content_hash,
            width=2,
            columns=inputs.columns,
        )


def test_quotes_with_a_decreasing_source_sequence_are_refused() -> None:
    table = _quote_table(3)
    sequence = pa.array(np.array([0, 2, 1], dtype=np.int64))
    table = table.set_column(
        table.schema.get_field_index("source_sequence"), "source_sequence", sequence
    )
    inputs = quote_inputs(table)
    with pytest.raises(qrl_native.AbiError, match="source_sequence must strictly increase"):
        _build_quote(dict(inputs.columns))
