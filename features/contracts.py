"""Versioned model-input views produced from market datasets."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

InputKind = Literal["handcrafted_features", "raw_market", "learned_representation"]


@dataclass(frozen=True, slots=True)
class InputSchema:
    """Versioned schema describing a model input tensor or array.

    Attributes:
        version: Identifier for the schema revision.
        kind: Input representation category.
    """

    schema_id: str
    version: str
    kind: InputKind
    columns: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate and initialize InputSchema after construction."""
        if not self.schema_id or not self.version or not self.columns:
            raise ValueError("input schema identity, version, and columns are required")
        if len(set(self.columns)) != len(self.columns):
            raise ValueError("input schema columns must be unique")


@dataclass(frozen=True, slots=True)
class InputView:
    """Named view of values supplied to a model input.

    Attributes:
        dataset_id: Stable identity of the source dataset.
        values: Rows of numeric input values.
    """

    schema: InputSchema
    dataset_id: str
    values: Sequence[Sequence[float]]

    def __post_init__(self) -> None:
        """Validate and initialize InputView after construction."""
        if not self.dataset_id:
            raise ValueError("input view must identify its source dataset")
        width = len(self.schema.columns)
        if any(len(row) != width for row in self.values):
            raise ValueError("input values do not match the declared schema width")


__all__ = ["InputKind", "InputSchema", "InputView"]
