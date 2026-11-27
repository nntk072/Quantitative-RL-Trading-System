from __future__ import annotations

import pandas as pd
import pytest

from features.contracts import InputKind, InputSchema, InputView
from features.input_view import input_view_from_frame


@pytest.mark.parametrize(
    "kind",
    ["handcrafted_features", "raw_market", "learned_representation"],
)
def test_distinct_input_representations_share_one_schema_contract(kind: InputKind) -> None:
    schema = InputSchema("market-input", "v1", kind, ("x0", "x1"))

    view = InputView(schema, "dataset-1", ((0.1, 0.2), (0.3, 0.4)))

    assert view.schema.kind == kind
    assert len(view.values) == 2


def test_input_view_rejects_width_schema_mismatch() -> None:
    schema = InputSchema("market-input", "v1", "raw_market", ("close", "volume"))
    with pytest.raises(ValueError, match="schema width"):
        InputView(schema, "dataset-1", ((1.0,),))


@pytest.mark.parametrize(
    ("schema_id", "version", "columns"),
    [("", "v1", ("close",)), ("bars", "", ("close",)), ("bars", "v1", ())],
)
def test_input_schema_requires_identity_version_and_columns(
    schema_id: str, version: str, columns: tuple[str, ...]
) -> None:
    with pytest.raises(ValueError, match="identity, version, and columns are required"):
        InputSchema(schema_id, version, "raw_market", columns)


def test_input_schema_rejects_duplicate_column_names() -> None:
    with pytest.raises(ValueError, match="columns must be unique"):
        InputSchema("bars", "v1", "raw_market", ("close", "close"))


def test_input_view_requires_dataset_identity() -> None:
    schema = InputSchema("bars", "v1", "raw_market", ("close",))

    with pytest.raises(ValueError, match="identify its source dataset"):
        InputView(schema, "", ((1.0,),))


def test_input_view_from_frame_selects_declared_columns_and_rejects_missing_ones() -> None:
    schema = InputSchema("bars", "v1", "raw_market", ("close", "volume"))
    frame = pd.DataFrame({"volume": [2, 3], "close": [100, 101], "unused": [9, 9]})

    view = input_view_from_frame(frame, dataset_id="fixture", schema=schema)

    assert view.values == ((100.0, 2.0), (101.0, 3.0))
    with pytest.raises(ValueError, match=r"missing schema columns: \['volume'\]"):
        input_view_from_frame(frame.drop(columns=["volume"]), dataset_id="fixture", schema=schema)
