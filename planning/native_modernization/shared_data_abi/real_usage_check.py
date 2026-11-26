"""Real-usage check of the shared data ABI on a tracked pre-2026 sample (SHARED-DATA-ABI).

Run it the way a user would: the built native extension on PYTHONPATH, the Arrow-to-ABI adapter,
and the public batch and view constructors. It reads one MT5 M1 export that is tracked in the repo
(`data/examples/`), converts it to a bar table, builds a causal feature table, validates both
through the native layer, builds a DatasetView with one walk-forward fold and a fitted-state
reference, writes the cache atomically, reads it back, and confirms that a corrupted copy is refused.

The sample must lie entirely before 2026-01-01. The script refuses any later row, because the
2026 reporting interval is locked and must not be used for any check.

Usage: python real_usage_check.py <worktree> <output_dir>
Exit code 0 means every check passed. Any failure raises and exits non-zero.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]

from market_data.arrow_schemas import mt5_export_to_bars
from market_data.event_schemas import FEATURE_ROW_SCHEMA
from market_data.native_abi import (
    bar_inputs,
    feature_block_inputs,
    read_cache,
    write_cache_atomic,
)

qrl_native = importlib.import_module("qrl_native")

SAMPLE = "data/examples/US100.cash_M1_202412300105_202501020334.csv"
LOCKED_BOUNDARY = np.datetime64("2026-01-01T00:00:00", "ns")
TRAIN_ROWS = 2000


def _load_bars(root: Path) -> tuple[pa.Table, dict[str, Any]]:
    raw = pd.read_csv(root / SAMPLE, sep="\t")
    raw.columns = [str(name).strip("<>") for name in raw.columns]
    table, problems = mt5_export_to_bars(
        raw, instrument_id="US100.cash", timeframe="M1", source_id="mt5-export-example"
    )
    event = table.column("event_time").cast(pa.int64()).to_numpy().view("datetime64[ns]")
    if event.size and event.max() >= LOCKED_BOUNDARY:
        raise SystemExit("sample contains 2026 rows; refusing to use the locked interval")
    digest = hashlib.sha256((root / SAMPLE).read_bytes()).hexdigest()
    return table, {
        "source_rows": len(raw),
        "bars": table.num_rows,
        "quarantined_dst_rows": len(problems),
        "first_bar": str(event.min()),
        "last_bar": str(event.max()),
        "sample_sha256": digest,
    }


def _feature_table(bars: pa.Table, content_hash: str) -> pa.Table:
    close = bars.column("close").to_numpy(zero_copy_only=False)
    high = bars.column("high").to_numpy(zero_copy_only=False)
    low = bars.column("low").to_numpy(zero_copy_only=False)
    rows = bars.num_rows
    event = bars.column("event_time")
    values: list[list[float | None]] = [
        [float(c), float(h - lo)] for c, h, lo in zip(close, high, low, strict=True)
    ]
    values[0] = [None, None]  # warm-up row: missing, not zero
    return pa.table(
        {
            "event_time": event,
            "available_at": event,
            "instrument_id": pa.array(["US100.cash"] * rows),
            "feature_set_id": pa.array(["example-core"] * rows),
            "feature_version": pa.array(["0.0.1"] * rows),
            "content_hash": pa.array([content_hash] * rows),
            "schema_id": pa.array(["feature-row.v1"] * rows),
            "session_eligible": pa.array([True] * rows),
            "values": pa.array(
                values, type=pa.list_(pa.field("item", pa.float64(), nullable=True))
            ),
        },
        schema=FEATURE_ROW_SCHEMA,
    )


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    checks: dict[str, object] = {}

    bars_table, sample_info = _load_bars(root)
    checks["sample"] = sample_info

    bar_arrays = bar_inputs(bars_table)
    bars = qrl_native.BarBatch.from_columns(
        schema_id=bar_arrays.schema_id,
        instrument_id=bar_arrays.instrument_id,
        source_id=bar_arrays.source_id,
        columns=bar_arrays.columns,
    )
    close_back = np.frombuffer(bars.column("close"), dtype="<f8")
    assert np.array_equal(close_back, bar_arrays.columns["close"])
    checks["bar_batch_rows"] = bars.rows

    feature_table = _feature_table(bars_table, sample_info["sample_sha256"])
    feature_arrays = feature_block_inputs(feature_table, width=2)
    block = qrl_native.FeatureRowBlock.from_columns(
        schema_id=feature_arrays.schema_id,
        instrument_id=feature_arrays.instrument_id,
        feature_set_id=feature_arrays.feature_set_id,
        feature_version=feature_arrays.feature_version,
        content_hash=feature_arrays.content_hash,
        width=feature_arrays.width,
        columns=feature_arrays.columns,
    )
    values_back = np.frombuffer(block.column("values"), dtype="<f8").reshape(bars.rows, 2)
    assert np.array_equal(values_back, feature_arrays.columns["values"], equal_nan=True)
    checks["feature_block_rows"] = block.rows

    rows = bars.rows
    train_end = min(TRAIN_ROWS, rows)
    view = qrl_native.DatasetView(
        bars,
        block,
        [(0, train_end, train_end, rows, 0, 0)],
        ("norm-v1", 0, train_end),
    )
    checks["view_content_hash"] = view.content_hash

    cache_path = out / "dataset_view.qrlds"
    write_cache_atomic(cache_path, bytes(view.to_cache_bytes()))
    restored = qrl_native.dataset_view_from_cache_bytes(read_cache(cache_path))
    assert restored.content_hash == view.content_hash
    checks["cache_bytes"] = cache_path.stat().st_size
    checks["cache_round_trip"] = "ok"

    corrupt = bytearray(read_cache(cache_path))
    corrupt[len(corrupt) // 2] ^= 0x01
    try:
        qrl_native.dataset_view_from_cache_bytes(bytes(corrupt))
    except qrl_native.AbiCacheError as error:
        checks["corrupt_cache_refusal"] = str(error)
    else:
        raise SystemExit("corrupted cache was accepted")

    checks["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    summary = {"status": "passed", "checks": checks}
    (out / "real_usage_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
