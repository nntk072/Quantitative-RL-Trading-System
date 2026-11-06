#!/usr/bin/env python3
"""Reconcile local M1 tick-volume counts with executable two-sided tick quotes.

The audit is deliberately source-wall-clock based: MT5 tick rows and M1 bars
are compared in their configured fixed-offset carrier without claiming that
the local export is a complete exchange tape. A minute is quote-complete only
when its raw tick-row count matches M1 ``tickvol`` and every raw row contains
a finite, positive, non-crossed bid/ask pair.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from configuration.configuration_loader import load_config
from configuration.paths import repository_root
from market_data.loading.bars import iter_ticks_chunks, load_bars

ROOT = repository_root(__file__)
DEFAULT_CONFIG = ROOT / "config/base/default.yaml"
DEFAULT_OUTPUT = ROOT / "evidence/research/tick_quote_coverage"
CHUNK_ROWS = 500_000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_wall_clock(frame: pd.DataFrame) -> pd.Series:
    timestamp = frame["date"].astype(str) + " " + frame["time"].astype(str)
    return pd.to_datetime(timestamp, format="%Y.%m.%d %H:%M:%S.%f", errors="coerce")


def build_coverage_audit(
    *, config_path: Path, output_dir: Path, symbol: str | None = None
) -> dict[str, Any]:
    cfg = load_config(config_path=config_path)
    dataset = cfg.data.datasets.training
    selected_symbol = symbol or str(cfg.data.primary)
    if selected_symbol not in dataset.m1_files or selected_symbol not in dataset.tick_files:
        raise ValueError(f"training M1 and tick files are not configured for {selected_symbol}")
    raw_dir = ROOT / str(dataset.raw_dir)
    m1_path = raw_dir / str(dataset.m1_files[selected_symbol])
    tick_path = raw_dir / str(dataset.tick_files[selected_symbol])
    train_start = pd.Timestamp(str(cfg.data.split.train_start))
    train_end_exclusive = pd.Timestamp(str(cfg.data.split.train_end)) + pd.Timedelta(days=1)

    bars = load_bars(m1_path)
    bars = bars.loc[(bars.index >= train_start) & (bars.index < train_end_exclusive)]
    if bars.empty:
        raise ValueError("configured training interval has no M1 rows")
    if not bars.index.is_unique:
        raise ValueError("training M1 index must be unique for minute reconciliation")

    source_rows: Counter[int] = Counter()
    valid_quotes: Counter[int] = Counter()
    invalid_quote_rows = 0
    timestamps_min = train_start
    timestamps_max = train_end_exclusive
    for chunk in iter_ticks_chunks(tick_path, chunksize=CHUNK_ROWS):
        timestamps = _parse_wall_clock(chunk)
        keep = timestamps.notna() & (timestamps >= timestamps_min) & (timestamps < timestamps_max)
        if not keep.any():
            continue
        selected = chunk.loc[keep]
        selected_ts = timestamps.loc[keep]
        bid = pd.to_numeric(selected["bid"], errors="coerce").to_numpy(dtype=np.float64)
        ask = pd.to_numeric(selected["ask"], errors="coerce").to_numpy(dtype=np.float64)
        valid = np.isfinite(bid) & np.isfinite(ask) & (bid > 0.0) & (ask > 0.0) & (ask >= bid)
        minute_ns = (selected_ts.dt.floor("min").astype("int64") // 60_000_000_000).to_numpy()
        source_rows.update(Counter(minute_ns.tolist()))
        valid_quotes.update(Counter(minute_ns[valid].tolist()))
        invalid_quote_rows += int((~valid).sum())

    expected = pd.to_numeric(bars["tickvol"], errors="coerce").fillna(-1).astype("int64")
    minute_ns = bars.index.view("int64") // 60_000_000_000
    observed = pd.Series([source_rows.get(int(value), 0) for value in minute_ns], index=bars.index)
    quote_rows = pd.Series(
        [valid_quotes.get(int(value), 0) for value in minute_ns], index=bars.index
    )
    frame = pd.DataFrame(
        {
            "source_tick_rows": observed.astype("int64"),
            "m1_tickvol": expected.astype("int64"),
            "valid_two_sided_quotes": quote_rows.astype("int64"),
        },
        index=bars.index,
    )
    frame.index.name = "bar_open_source_wall_clock"
    frame["row_count_matches_tickvol"] = frame["source_tick_rows"] == frame["m1_tickvol"]
    frame["all_rows_have_valid_quotes"] = (
        frame["valid_two_sided_quotes"] == frame["source_tick_rows"]
    )
    frame["quote_complete"] = (
        frame["row_count_matches_tickvol"]
        & frame["all_rows_have_valid_quotes"]
        & (frame["source_tick_rows"] > 0)
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    coverage_path = output_dir / "minute_quote_coverage.csv"
    frame.to_csv(coverage_path)
    source_files = {
        str(m1_path.relative_to(ROOT)): _sha256(m1_path),
        str(tick_path.relative_to(ROOT)): _sha256(tick_path),
        str(config_path.resolve().relative_to(ROOT)): _sha256(config_path.resolve()),
    }
    differences = frame[frame["source_tick_rows"] != frame["m1_tickvol"]]
    no_quote = frame[frame["valid_two_sided_quotes"] < frame["source_tick_rows"]]
    complete = int(frame["quote_complete"].sum())
    summary: dict[str, Any] = {
        "schema_version": "local-tick-quote-coverage-v1",
        "status": "source_count_reconciled"
        if differences.empty
        else "source_count_mismatches_present",
        "symbol": selected_symbol,
        "time_basis": "MT5 source wall-clock, compared without timezone conversion",
        "training_window": {
            "start_inclusive": train_start.isoformat(),
            "end_exclusive": train_end_exclusive.isoformat(),
        },
        "coverage_rule": (
            "A minute is quote_complete only if raw tick row count equals M1 tickvol, "
            "the count is positive, and every raw row has a finite positive non-crossed bid/ask. "
            "This is a local-source consistency rule, not proof of exchange-tape completeness."
        ),
        "input_sha256": source_files,
        "m1_rows": int(len(frame)),
        "m1_tickvol_total": int(frame["m1_tickvol"].clip(lower=0).sum()),
        "raw_tick_rows_in_training_window": int(frame["source_tick_rows"].sum()),
        "raw_tick_rows_without_valid_quote": invalid_quote_rows,
        "minutes_with_tick_count_mismatch": int(len(differences)),
        "minutes_with_tick_count_match": int(frame["row_count_matches_tickvol"].sum()),
        "minutes_with_all_quote_rows_valid": int(frame["all_rows_have_valid_quotes"].sum()),
        "minutes_quote_complete": complete,
        "minutes_quote_incomplete": int(len(frame) - complete),
        "first_mismatches": [
            {
                "source_wall_clock": pd.Timestamp(str(timestamp)).isoformat(),
                "source_tick_rows": int(row.source_tick_rows),
                "m1_tickvol": int(row.m1_tickvol),
                "valid_two_sided_quotes": int(row.valid_two_sided_quotes),
            }
            for timestamp, row in differences.head(20).iterrows()
        ],
        "first_invalid_quote_minutes": [
            timestamp.isoformat() for timestamp in no_quote.head(20).index
        ],
        "coverage_csv_sha256": _sha256(coverage_path),
    }
    manifest_path = output_dir / "coverage_manifest.json"
    manifest_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    readme_path = output_dir / "README.md"
    readme_path.write_text(
        "# Local tick quote coverage\n\n"
        "This packet reconciles the configured training M1 `tickvol` counts with local raw tick-row counts and checks whether every raw row has a usable two-sided quote. It is a local-source consistency audit, not evidence that the export is complete relative to an external venue. `minute_quote_coverage.csv` can be joined to proposal fill and exit intervals; any interval containing an incomplete minute must remain unresolved for negative-touch claims.\n\n"
        "The training window is configured in the resolved project config. Input hashes and aggregate reconciliation counts are recorded in `coverage_manifest.json`.\n",
        encoding="utf-8",
    )
    outputs = (coverage_path, manifest_path, readme_path)
    (output_dir / "OUTPUT_SHA256SUMS").write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in outputs), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--symbol")
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    print(
        json.dumps(
            build_coverage_audit(
                config_path=config_path, output_dir=output_dir, symbol=args.symbol
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
