#!/usr/bin/env python3
"""Measure order-block retest events hidden by the scalar latest-zone view."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pandas as pd
from omegaconf import DictConfig, OmegaConf

from configuration.configuration_loader import load_config
from configuration.paths import repository_root
from features.context.order_blocks import build_order_block_features_with_event_ledger
from market_data.loading.market_data_ingestion import run_pipeline
from market_data.splits.definitions import make_train_mask
from market_data.transforms.resample import TF, resample

ROOT = repository_root(__file__)
DEFAULT_CONFIG = ROOT / "config/research/trade_setup_mtf_reasoning_2m.yaml"
DEFAULT_OUTPUT = ROOT / "evidence/research/order_block_zone_event_ledger"
RAW_MANIFEST = (
    ROOT / "evidence/research/releases/negative-evidence-readiness/RAW_DATA_SHA256_MANIFEST.json"
)
LEDGER_COLUMNS = [
    "timeframe",
    "confirmation_month",
    "zone_id",
    "side",
    "confirmation_bar",
    "confirmation_time_ns",
    "source_origin_bar",
    "source_origin_time_ns",
    "zone_low",
    "zone_high",
    "selected_by_scalar",
]


def _training_slice(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """Keep rows in the configured inclusive training interval."""
    index = pd.DatetimeIndex(frame.index)
    return frame.loc[make_train_mask(index, end, start)]


def _validate_scalar_projection(ledger: pd.DataFrame, scalar: pd.DataFrame) -> None:
    """Require selected per-zone events to reproduce scalar retest pulses."""
    for side in ("bull", "bear"):
        selected = ledger.loc[ledger["side"].eq(side) & ledger["selected_by_scalar"]]
        expected = scalar.loc[scalar[f"ob_{side}_retest"].gt(0.0)]
        expected_bars = [scalar.index.get_loc(time) for time in expected.index]
        if selected["confirmation_bar"].astype(int).tolist() != expected_bars:
            raise AssertionError(f"selected {side} events do not match scalar retest pulses")
        expected_origins = expected[f"ob_{side}_origin_time_ms"].to_numpy(dtype=float)
        actual_origins = selected["source_origin_time_ns"].to_numpy(dtype="int64") // 1_000_000
        if not (expected_origins == actual_origins).all():
            raise AssertionError(f"selected {side} events do not match scalar source origins")


def _collision_table(
    ledger: pd.DataFrame, bars_by_timeframe: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """Return same-timeframe, same-row, same-direction multi-zone confirmations."""
    rows: list[dict[str, Any]] = []
    columns = [
        "timeframe",
        "confirmation_bar",
        "confirmation_time_ns",
        "confirmation_month",
        "side",
        "per_zone_confirmation_count",
        "suppressed_per_zone_confirmations",
        "selected_zone_id",
    ]
    for (timeframe, bar, side), group in ledger.groupby(
        ["timeframe", "confirmation_bar", "side"], sort=True
    ):
        if len(group) < 2:
            continue
        selected = group.loc[group["selected_by_scalar"]]
        if len(selected) > 1:
            raise AssertionError("a scalar collision cannot select multiple zones")
        bar_index = cast(int, bar)
        rows.append(
            {
                "timeframe": str(timeframe),
                "confirmation_bar": bar_index,
                "confirmation_time_ns": int(group["confirmation_time_ns"].iloc[0]),
                "confirmation_month": pd.Timestamp(
                    bars_by_timeframe[str(timeframe)].index[bar_index]
                ).strftime("%Y-%m"),
                "side": str(side),
                "per_zone_confirmation_count": int(len(group)),
                "suppressed_per_zone_confirmations": int(len(group) - len(selected)),
                "selected_zone_id": (
                    int(selected["zone_id"].iloc[0]) if len(selected) == 1 else None
                ),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _monthly_summary(ledger: pd.DataFrame, collisions: pd.DataFrame) -> pd.DataFrame:
    """Summarize per-zone events and scalar suppression by month."""
    columns = [
        "timeframe",
        "confirmation_month",
        "side",
        "per_zone_confirmations",
        "scalar_confirmation_pulses",
        "suppressed_per_zone_confirmations",
        "collision_rows",
    ]
    if ledger.empty:
        return pd.DataFrame(columns=columns)
    work = ledger.copy()
    grouped = work.groupby(["timeframe", "confirmation_month", "side"], sort=True).agg(
        per_zone_confirmations=("side", "size"),
        scalar_confirmation_pulses=("selected_by_scalar", "sum"),
    )
    grouped["suppressed_per_zone_confirmations"] = (
        grouped["per_zone_confirmations"] - grouped["scalar_confirmation_pulses"]
    )
    if collisions.empty:
        grouped["collision_rows"] = 0
    else:
        counts = collisions.groupby(["timeframe", "confirmation_month", "side"], sort=True).size()
        grouped["collision_rows"] = counts
        grouped["collision_rows"] = grouped["collision_rows"].fillna(0)
    result = grouped.reset_index()
    result["collision_rows"] = result["collision_rows"].astype(int)
    return result.loc[:, columns]


def _retest_event_counts(
    ledger: pd.DataFrame,
    scalar_counts: dict[str, int],
    collisions: pd.DataFrame,
) -> dict[str, int]:
    """Separate scalar-unselected events from same-row collision suppression."""
    scalar_pulses = sum(scalar_counts.values())
    selected_events = int(ledger["selected_by_scalar"].sum())
    if selected_events != scalar_pulses:
        raise AssertionError("selected zone events do not reconcile with scalar retest pulses")
    return {
        "per_zone_retest_event_count": int(len(ledger)),
        "scalar_retest_pulse_count": scalar_pulses,
        "not_selected_by_scalar_retest_event_count": int(len(ledger) - selected_events),
        "collision_suppressed_per_zone_event_count": (
            int(collisions["suppressed_per_zone_confirmations"].sum())
            if not collisions.empty
            else 0
        ),
        "collision_group_count": int(len(collisions)),
    }


def _input_identity(cfg: DictConfig, symbol: str) -> dict[str, str]:
    """Require local training M1 data to match the pinned raw-data manifest."""
    manifest = json.loads(RAW_MANIFEST.read_text(encoding="utf-8"))
    spec = cfg.data.datasets.training
    relative = (Path(str(spec.raw_dir)) / str(spec.m1_files[symbol])).as_posix()
    entry = {item["path"]: item for item in manifest["files"]}.get(relative)
    if entry is None:
        raise ValueError(f"training input absent from pinned local data manifest: {relative}")
    path = ROOT / relative
    if path.stat().st_size != int(entry["size_bytes"]):
        raise ValueError(f"training input size differs from pinned manifest: {relative}")
    with path.open("rb") as stream:
        actual_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual_sha256 != str(entry["sha256"]):
        raise ValueError(f"training input content differs from pinned manifest: {relative}")
    return {relative: actual_sha256}


def _source_hashes() -> dict[str, str]:
    """Capture diagnostic source identities before local data processing."""
    paths = (
        "features/context/order_blocks.py",
        "market_data/transforms/resample.py",
        "market_data/loading/market_data_ingestion.py",
        "scripts/research/analysis/features/order_block_zone_event_ledger.py",
    )
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}


def build_ledger(
    cfg: DictConfig,
    output_dir: Path,
    *,
    config_path: Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Build a training-only per-zone order-block retest packet."""
    source_hashes = _source_hashes()
    cfg.data.cache_dir = str(ROOT / "cache/order_block_zone_event_ledger")
    datasets = run_pipeline(cfg, datasets=["training"])
    symbol = str(cfg.data.primary)
    start = str(cfg.data.split.train_start)
    end = str(cfg.data.split.train_end)
    source_m1 = datasets[symbol]["M1"]
    m1_bars = _training_slice(source_m1, start, end)
    if m1_bars.empty:
        raise ValueError("configured training-only M1 input is empty")

    order_block_cfg = cfg.features.order_blocks
    timeframes = tuple(str(item) for item in order_block_cfg.timeframes)
    params = {
        "swing_period": int(order_block_cfg.swing_period),
        "impulse_atr": float(order_block_cfg.impulse_atr),
        "search_bars": int(order_block_cfg.search_bars),
        "max_age_bars": int(order_block_cfg.max_age_bars),
    }
    bars_by_timeframe: dict[str, pd.DataFrame] = {}
    ledgers: list[pd.DataFrame] = []
    scalar_counts: dict[str, int] = {}
    for timeframe in timeframes:
        resampled = resample(source_m1, cast(TF, timeframe))
        bars = _training_slice(resampled, start, end)
        scalar, zone_events = build_order_block_features_with_event_ledger(
            bars,
            swing_period=int(order_block_cfg.swing_period),
            impulse_atr=float(order_block_cfg.impulse_atr),
            search_bars=int(order_block_cfg.search_bars),
            max_age_bars=int(order_block_cfg.max_age_bars),
        )
        _validate_scalar_projection(zone_events, scalar)
        zone_events.insert(0, "timeframe", timeframe)
        zone_events.insert(
            1,
            "confirmation_month",
            [
                pd.Timestamp(bars.index[int(bar)]).strftime("%Y-%m")
                for bar in zone_events["confirmation_bar"]
            ],
        )
        bars_by_timeframe[timeframe] = bars
        ledgers.append(zone_events.reindex(columns=LEDGER_COLUMNS))
        scalar_counts[timeframe] = int(
            scalar[["ob_bull_retest", "ob_bear_retest"]].to_numpy().sum()
        )

    ledger = (
        pd.concat(ledgers, ignore_index=True) if ledgers else pd.DataFrame(columns=LEDGER_COLUMNS)
    )
    collisions = _collision_table(ledger, bars_by_timeframe)
    monthly = _monthly_summary(ledger, collisions)
    event_counts = _retest_event_counts(ledger, scalar_counts, collisions)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(output_dir / "order_block_zone_retest_events.csv", index=False)
    collisions.to_csv(output_dir / "order_block_retest_collisions.csv", index=False)
    monthly.to_csv(output_dir / "monthly_collision_summary.csv", index=False)

    resolved_config = OmegaConf.to_yaml(cfg, resolve=True)
    (output_dir / "resolved_config.yaml").write_text(resolved_config, encoding="utf-8")
    inputs = _input_identity(cfg, symbol)
    metadata: dict[str, Any] = {
        "status": "descriptive_training_order_block_events_only",
        "interpretation": (
            "Independent per-zone retest confirmations versus the scalar latest-zone view; "
            "not policy proposals, trades, or returns."
        ),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_hashes": source_hashes,
        "config_path": (
            config_path.resolve().relative_to(ROOT.resolve()).as_posix()
            if config_path.resolve().is_relative_to(ROOT.resolve())
            else str(config_path.resolve())
        ),
        "resolved_config_sha256": hashlib.sha256(resolved_config.encode("utf-8")).hexdigest(),
        "training_period": {"start": start, "end_inclusive": end},
        "primary_symbol": symbol,
        "training_m1_rows": int(len(m1_bars)),
        "timeframes": list(timeframes),
        "order_block_parameters": params,
        "detector_enabled_in_config": bool(order_block_cfg.enabled),
        **event_counts,
        "scalar_retest_pulse_count_by_timeframe": scalar_counts,
        "local_data_manifest_sha256": hashlib.sha256(RAW_MANIFEST.read_bytes()).hexdigest(),
        "training_input_sha256": inputs,
    }
    (output_dir / "event_ledger.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    readme = [
        "# Training-only order-block zone event ledger",
        "",
        "This packet records zone-specific retest confirmations and compares them with the existing scalar feature, which exposes only the current latest zone per direction.",
        "",
        f"- Instrument: {symbol}; training interval: {start} through {end}; M1 rows: {len(m1_bars):,}.",
        f"- Timeframes: {', '.join(timeframes)}; detector enabled in resolved config: {bool(order_block_cfg.enabled)}.",
        f"- Per-zone confirmations: {len(ledger):,}; scalar retest pulses: {sum(scalar_counts.values()):,}; collision groups: {len(collisions):,}.",
        f"- Per-zone confirmations not selected by the scalar view: {event_counts['not_selected_by_scalar_retest_event_count']:,}; suppressed confirmations within same-row collision groups: {event_counts['collision_suppressed_per_zone_event_count']:,}.",
        "- Counts describe the detector on current local training bars. They do not establish policy eligibility, publication timing, independent opportunities, or economic value.",
        "",
        "## Files",
        "",
        "- order_block_zone_retest_events.csv: one row per per-zone retest confirmation.",
        "- order_block_retest_collisions.csv: same-timeframe, same-row, same-direction multi-zone confirmations.",
        "- monthly_collision_summary.csv: monthly per-zone and scalar counts by timeframe and direction.",
        "- resolved_config.yaml and event_ledger.json: configuration, source, and data identities.",
    ]
    (output_dir / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    checksums = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in sorted(output_dir.iterdir())
        if path.is_file() and path.name != "OUTPUT_SHA256SUMS"
    ]
    (output_dir / "OUTPUT_SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    return metadata


def main() -> None:
    """Run the configured local training-only event audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    cfg = load_config(config_path=config_path)
    print(json.dumps(build_ledger(cfg, args.output_dir, config_path=config_path), indent=2))


if __name__ == "__main__":
    main()
