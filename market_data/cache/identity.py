from __future__ import annotations

from typing import Any

from artifacts.identity import artifact_id


def market_data_cache_id(
    *, dataset_id: str, transform: str, config: Any, schema_version: int = 1
) -> str:
    """Build a stable cache identity from dataset and transform semantics.

    Args:
        dataset_id: Identity of the source market data.
        transform: Name of the applied transform pipeline.
        config: Values that affect transformed output.
        schema_version: Cache schema revision.

    Returns:
        Deterministic cache identifier.
    """
    return str(
        artifact_id(
            "market-data-cache",
            {
                "dataset_id": dataset_id,
                "transform": transform,
                "config": config,
                "schema_version": schema_version,
            },
        )
    )
