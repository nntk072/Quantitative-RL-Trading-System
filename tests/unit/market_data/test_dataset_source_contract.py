from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from market_data.contracts import DatasetRef, DatasetSource, MarketDataset, MarketEventSchema


@dataclass
class _TupleSource:
    rows: tuple[dict[str, object], ...]

    def load(self, reference: DatasetRef) -> MarketDataset:
        return MarketDataset(reference=reference, events=self.rows)


@dataclass
class _MappingSource:
    rows: list[dict[str, object]]

    def load(self, reference: DatasetRef) -> MarketDataset:
        return MarketDataset(reference=reference, events=tuple(dict(row) for row in self.rows))


def test_distinct_sources_resolve_the_same_logical_market_dataset() -> None:
    schema = MarketEventSchema(
        event_type="bar",
        version="ohlc-v1",
        fields=("time", "open", "high", "low", "close"),
        time_field="time",
    )
    reference = DatasetRef(
        dataset_id="us100-2025-m1",
        instrument_id="US100.cash",
        start=datetime(2025, 1, 1, tzinfo=UTC),
        end=datetime(2025, 1, 2, tzinfo=UTC),
        timezone="UTC",
        schema=schema,
        provenance_id="provider-a:sha256:test",
    )
    rows = ({"time": "2025-01-01T00:00:00Z", "close": 1.0},)
    sources: tuple[DatasetSource, ...] = (
        _TupleSource(rows),
        _MappingSource([dict(row) for row in rows]),
    )

    datasets = tuple(source.load(reference) for source in sources)

    assert all(dataset.reference == reference for dataset in datasets)
    assert datasets[0].events == datasets[1].events


@pytest.mark.parametrize(
    "values",
    [
        ("", "v1", ("time",), "time"),
        ("bar", "v1", (), "time"),
        ("bar", "v1", ("time", "time"), "time"),
        ("bar", "v1", ("close",), "time"),
    ],
)
def test_event_schema_rejects_missing_or_ambiguous_contract_fields(
    values: tuple[str, str, tuple[str, ...], str],
) -> None:
    with pytest.raises(ValueError):
        MarketEventSchema(*values)


@pytest.mark.parametrize(
    ("dataset_id", "instrument_id", "start", "end", "timezone", "provenance_id", "message"),
    [
        (
            "",
            "US100",
            datetime(2025, 1, 1, tzinfo=UTC),
            datetime(2025, 1, 2, tzinfo=UTC),
            "UTC",
            "src",
            "identities",
        ),
        (
            "d",
            "US100",
            datetime(2025, 1, 1),
            datetime(2025, 1, 2, tzinfo=UTC),
            "UTC",
            "src",
            "timezone-aware",
        ),
        (
            "d",
            "US100",
            datetime(2025, 1, 2, tzinfo=UTC),
            datetime(2025, 1, 1, tzinfo=UTC),
            "UTC",
            "src",
            "precede",
        ),
        (
            "d",
            "US100",
            datetime(2025, 1, 1, tzinfo=UTC),
            datetime(2025, 1, 2, tzinfo=UTC),
            "",
            "src",
            "timezone is required",
        ),
    ],
)
def test_dataset_reference_rejects_invalid_identity_bounds_and_timezone(
    dataset_id: str,
    instrument_id: str,
    start: datetime,
    end: datetime,
    timezone: str,
    provenance_id: str,
    message: str,
) -> None:
    schema = MarketEventSchema("bar", "v1", ("time",), "time")

    with pytest.raises(ValueError, match=message):
        DatasetRef(dataset_id, instrument_id, start, end, timezone, schema, provenance_id)
