#!/usr/bin/env python3
"""Audit IFVG zone confirmations and cross-timeframe scalar suppression.

This training-only diagnostic retains every source-gap confirmation for each
configured IFVG timeframe, projects it to the first M1 row where the current
pipeline exposes it, and reproduces the source-timeframe precedence used by
``align_ifvg_zone_timeframes``. Counts describe detector events only; they do
not imply independent setups, policy proposals, orders, or trades.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import pandas as pd
from omegaconf import DictConfig, OmegaConf

from configuration.configuration_loader import load_config
from configuration.paths import repository_root
from features.po3.fvg_detection import FVGConfig, detect_fvg
from features.po3.ifvg_detection import (
    IFVGConfig,
    detect_ifvg_confirmation,
    detect_ifvg_confirmation_events,
)
from market_data.loading.market_data_ingestion import run_pipeline
from market_data.splits.definitions import make_train_mask
from market_data.transforms.align import timeframe_close_times
from market_data.transforms.resample import resample
from market_data.transforms.session_schedule import scheduled_session_close_map

ROOT = repository_root(__file__)
DEFAULT_CONFIG = ROOT / "config/2_po3_ifvg.yaml"
DEFAULT_OUTPUT = ROOT / "evidence/research/ifvg_timeframe_collision_ledger"
RAW_MANIFEST = (
    ROOT / "evidence/research/releases/negative-evidence-readiness/RAW_DATA_SHA256_MANIFEST.json"
)
Timeframe = Literal["M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1"]
TIMEFRAME_ORDER: tuple[Timeframe, ...] = ("M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
SUPPORTED_TIMEFRAMES = frozenset((*TIMEFRAME_ORDER, "M1"))
EVENT_COLUMNS = [
    "source_timeframe",
    "confirmation_bar",
    "confirmation_time_ns",
    "effective_availability_time_ns",
    "effective_availability_m1_bar",
    "side",
    "source_origin_bar",
    "source_origin_time_ns",
    "zone_low",
    "zone_high",
    "pass_bar",
    "pass_time_ns",
    "pass_extreme",
    "selected_by_source_scalar",
    "selected_by_merged_scalar",
]
COLLISION_COLUMNS = [
    "availability_m1_bar",
    "availability_time_ns",
    "side",
    "per_zone_event_count",
    "source_scalar_event_count",
    "source_timeframe_count",
    "selected_source_timeframe",
    "suppressed_zone_event_count",
]


def _training_slice(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """Keep rows within the inclusive configured training dates."""
    index = pd.DatetimeIndex(frame.index)
    return frame.loc[make_train_mask(index, end, start)]


def _ifvg_config(cfg: DictConfig) -> IFVGConfig:
    """Resolve the detector options used by the feature pipeline."""
    threshold = OmegaConf.select(cfg, "features.gap_reaction_buffer_fraction")
    if threshold is None:
        threshold = OmegaConf.select(cfg, "strategy.ifvg.close_through_threshold")
    buffer_enabled = OmegaConf.select(cfg, "features.gap_reaction_buffer_enabled")
    opposing = OmegaConf.select(cfg, "strategy.ifvg.require_opposing_fvg")
    return IFVGConfig(
        close_through_threshold=0.1 if threshold is None else float(threshold),
        inverse_opposing_fvg=bool(opposing),
        close_through_buffer_enabled=True if buffer_enabled is None else bool(buffer_enabled),
    )


def _configured_timeframes(cfg: DictConfig) -> list[Timeframe]:
    """Return M1 followed by enabled IFVG MTF sources in production order."""
    block = OmegaConf.select(cfg, "features.ifvg_mtf")
    if not block or not bool(block.get("enabled", False)):
        return ["M1"]
    configured: list[Timeframe] = []
    for value in block.get("timeframes", TIMEFRAME_ORDER):
        timeframe = str(value).upper()
        if timeframe not in SUPPORTED_TIMEFRAMES:
            raise ValueError(f"unsupported IFVG timeframe: {timeframe}")
        configured.append(timeframe)
    return ["M1", *[tf for tf in configured if tf != "M1"]]


def _source_events(
    bars: pd.DataFrame,
    timeframe: Timeframe,
    primary_index: pd.DatetimeIndex,
    ifvg_config: IFVGConfig,
    *,
    scheduled_closes: dict[str, str],
    session_start: str,
) -> pd.DataFrame:
    """Return source-gap events with source-scalar and M1 availability identity."""
    fvg = detect_fvg(bars, FVGConfig())
    scalar = detect_ifvg_confirmation(bars, fvg, ifvg_config)
    ledger = detect_ifvg_confirmation_events(bars, fvg, ifvg_config)
    if not ledger.columns.is_unique:
        raise ValueError("IFVG event ledger columns must be unique")

    for side, flag, origin in (
        ("bullish", "ifvg_bullish_confirmed", "ifvg_bullish_origin_bar"),
        ("bearish", "ifvg_bearish_confirmed", "ifvg_bearish_origin_bar"),
    ):
        chosen = ledger.loc[ledger["selected_by_scalar"] & ledger["side"].eq(side)]
        expected = np.flatnonzero(scalar[flag].to_numpy(dtype=bool))
        if chosen["confirmation_bar"].astype(int).tolist() != expected.tolist():
            raise AssertionError(f"{timeframe} per-zone {side} events disagree with scalar pulses")
        if not np.array_equal(
            chosen["source_origin_bar"].to_numpy(dtype=int),
            scalar[origin].to_numpy(dtype=float)[expected].astype(int),
        ):
            raise AssertionError(f"{timeframe} selected {side} origin differs from scalar output")

    if timeframe == "M1":
        closes = pd.Series(bars.index, index=bars.index)
    else:
        closes = timeframe_close_times(bars, timeframe, scheduled_closes, session_start)

    rows: list[dict[str, Any]] = []
    for raw_event in ledger.to_dict(orient="records"):
        event = cast(dict[str, Any], raw_event)
        source_bar = int(event["confirmation_bar"])
        available_at = closes.iloc[source_bar]
        if pd.isna(available_at):
            m1_bar = -1
            available_ns = -1
        else:
            available_timestamp = pd.Timestamp(available_at)
            m1_bar = int(primary_index.searchsorted(available_timestamp, side="left"))
            available_ns = int(available_timestamp.value)
            if m1_bar >= len(primary_index):
                m1_bar = -1
        rows.append(
            {
                "source_timeframe": timeframe,
                **event,
                "confirmation_bar": source_bar,
                "confirmation_time_ns": int(pd.Timestamp(bars.index[source_bar]).value),
                "effective_availability_time_ns": available_ns,
                "effective_availability_m1_bar": m1_bar,
                "selected_by_source_scalar": bool(event["selected_by_scalar"]),
                "selected_by_merged_scalar": False,
            }
        )
    return pd.DataFrame(rows, columns=EVENT_COLUMNS)


def _mark_merged_scalar_selection(events: pd.DataFrame, precedence: Sequence[str]) -> pd.DataFrame:
    """Mark one source-scalar event per available M1 row and side."""
    result = events.copy()
    if result.empty:
        return result
    priority = {timeframe: rank for rank, timeframe in enumerate(precedence)}
    source_events = result.loc[
        result["selected_by_source_scalar"] & result["effective_availability_m1_bar"].ge(0)
    ]
    for (_, _), group in source_events.groupby(
        ["effective_availability_m1_bar", "side"], sort=False
    ):
        selected = group.assign(
            _priority=group["source_timeframe"].map(priority).fillna(len(priority))
        ).sort_values(["_priority", "confirmation_bar"], ascending=[True, False], kind="stable")
        result.loc[selected.index[0], "selected_by_merged_scalar"] = True
    return result


def _collision_table(events: pd.DataFrame) -> pd.DataFrame:
    """Summarize coincident source-zone events at the merged M1 boundary."""
    rows: list[dict[str, Any]] = []
    visible = events.loc[events["effective_availability_m1_bar"].ge(0)]
    for (bar, side), group in visible.groupby(["effective_availability_m1_bar", "side"], sort=True):
        if len(group) < 2:
            continue
        merged = group.loc[group["selected_by_merged_scalar"]]
        if len(merged) != 1:
            raise AssertionError("each merged IFVG collision must select exactly one source event")
        rows.append(
            {
                "availability_m1_bar": int(cast(int, bar)),
                "availability_time_ns": int(group["effective_availability_time_ns"].iloc[0]),
                "side": str(side),
                "per_zone_event_count": int(len(group)),
                "source_scalar_event_count": int(group["selected_by_source_scalar"].sum()),
                "source_timeframe_count": int(group["source_timeframe"].nunique()),
                "selected_source_timeframe": str(merged["source_timeframe"].iloc[0]),
                "suppressed_zone_event_count": int(len(group) - 1),
            }
        )
    return pd.DataFrame(rows, columns=COLLISION_COLUMNS)


def _source_hashes() -> dict[str, str]:
    paths = (
        "features/pipeline/feature_build_inputs.py",
        "features/po3/fvg_detection.py",
        "features/po3/ifvg_detection.py",
        "features/po3/po3_phase_state.py",
        "features/pipeline/po3_stage.py",
        "market_data/transforms/align.py",
        "market_data/transforms/resample.py",
        "market_data/transforms/session_schedule.py",
        "market_data/loading/market_data_ingestion.py",
        "scripts/research/analysis/features/ifvg_timeframe_collision_ledger.py",
    )
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in paths}


def _input_identity(cfg: DictConfig, symbol: str, timeframes: Sequence[str]) -> dict[str, str]:
    """Validate every configured native source input against the pinned manifest."""
    manifest = json.loads(RAW_MANIFEST.read_text(encoding="utf-8"))
    spec = cfg.data.datasets.training
    manifest_by_path = {item["path"]: item for item in manifest["files"]}
    filenames = {"M1": spec.m1_files.get(symbol)}
    timeframe_files = spec.timeframe_files
    for timeframe in timeframes:
        filename = timeframe_files.get(timeframe, {}).get(symbol)
        if filename is not None:
            filenames[timeframe] = str(filename)

    identities: dict[str, str] = {}
    for timeframe, filename in filenames.items():
        if filename is None:
            continue
        relative = (Path(str(spec.raw_dir)) / str(filename)).as_posix()
        entry = manifest_by_path.get(relative)
        if entry is None:
            raise ValueError(f"training input absent from pinned local data manifest: {relative}")
        path = ROOT / relative
        stat = path.stat()
        if stat.st_size != int(entry["size_bytes"]):
            raise ValueError(f"training input size differs from pinned manifest: {relative}")
        manifest_mtime = pd.Timestamp(entry["mtime_utc"]).timestamp()
        if abs(stat.st_mtime - manifest_mtime) > 1.0:
            raise ValueError(f"training input mtime differs from pinned manifest: {relative}")
        identities[relative] = str(entry["sha256"])
    return identities


def _schedule_identity(cfg: DictConfig) -> dict[str, str] | None:
    """Hash the configured session schedule used for MTF availability."""
    value = OmegaConf.select(cfg, "data.session_schedule_file")
    if value is None:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        raise FileNotFoundError(f"configured session schedule does not exist: {path}")
    name = (
        path.resolve().relative_to(ROOT.resolve()).as_posix()
        if path.resolve().is_relative_to(ROOT.resolve())
        else str(path.resolve())
    )
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _write_checksums(output_dir: Path) -> None:
    rows = []
    for path in sorted(output_dir.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != "OUTPUT_SHA256SUMS":
            rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    (output_dir / "OUTPUT_SHA256SUMS").write_text("\n".join(rows) + "\n", encoding="utf-8")


def build_ledger(
    cfg: DictConfig,
    output_dir: Path,
    *,
    config_path: Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Build a training-only per-zone and cross-timeframe IFVG packet."""
    # Reuse the existing prepared bar cache; the audit owns its output packet,
    # but does not need another copy of the raw-to-parquet cache.
    cfg.data.cache_dir = str(ROOT / "cache/trade_setup_opportunity_census")
    datasets = run_pipeline(cfg, datasets=["training"])
    symbol = str(cfg.data.primary)
    start = str(cfg.data.split.train_start)
    end = str(cfg.data.split.train_end)
    primary = _training_slice(datasets[symbol]["M1"], start, end)
    if primary.empty:
        raise ValueError("configured training-only M1 input is empty")

    timeframes = _configured_timeframes(cfg)
    ifvg_config = _ifvg_config(cfg)
    scheduled_closes = scheduled_session_close_map(cfg)
    session_start = str(OmegaConf.select(cfg, "session.start") or "16:30")
    frames: dict[str, pd.DataFrame] = {"M1": primary}
    for timeframe in timeframes:
        if timeframe == "M1":
            continue
        source = datasets[symbol].get(timeframe)
        if source is None:
            source = resample(primary, cast(Timeframe, timeframe))
        frames[timeframe] = _training_slice(source, start, end)

    ledgers = [
        _source_events(
            frames[timeframe],
            timeframe,
            pd.DatetimeIndex(primary.index),
            ifvg_config,
            scheduled_closes=scheduled_closes,
            session_start=session_start,
        )
        for timeframe in timeframes
        if timeframe in frames and not frames[timeframe].empty
    ]
    events = (
        pd.concat(ledgers, ignore_index=True) if ledgers else pd.DataFrame(columns=EVENT_COLUMNS)
    )
    events = _mark_merged_scalar_selection(events, timeframes)
    collisions = _collision_table(events)
    output_dir.mkdir(parents=True, exist_ok=True)
    events.to_csv(output_dir / "ifvg_timeframe_event_ledger.csv", index=False)
    collisions.to_csv(output_dir / "ifvg_timeframe_collisions.csv", index=False)

    source_scalar_count = int(events["selected_by_source_scalar"].sum()) if not events.empty else 0
    merged_scalar_count = int(events["selected_by_merged_scalar"].sum()) if not events.empty else 0
    visible_count = (
        int(events["effective_availability_m1_bar"].ge(0).sum()) if not events.empty else 0
    )
    per_tf = (
        {
            str(timeframe): {
                "zone_events": int(len(group)),
                "source_scalar_events": int(group["selected_by_source_scalar"].sum()),
                "merged_scalar_events": int(group["selected_by_merged_scalar"].sum()),
            }
            for timeframe, group in events.groupby("source_timeframe", sort=False)
        }
        if not events.empty
        else {}
    )

    resolved_config = OmegaConf.to_yaml(cfg, resolve=True)
    (output_dir / "resolved_config.yaml").write_text(resolved_config, encoding="utf-8")
    summary = {
        "status": "descriptive_training_ifvg_detector_events_only",
        "interpretation": "Per-zone IFVG confirmations by source timeframe, projected to the first M1 availability row and compared with current first-source-wins scalar merging.",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_hashes": _source_hashes(),
        "config_path": config_path.resolve().relative_to(ROOT.resolve()).as_posix()
        if config_path.resolve().is_relative_to(ROOT.resolve())
        else str(config_path.resolve()),
        "resolved_config_sha256": hashlib.sha256(resolved_config.encode("utf-8")).hexdigest(),
        "training_period": {"start": start, "end_inclusive": end},
        "primary_symbol": symbol,
        "training_m1_rows": int(len(primary)),
        "source_timeframes_in_merge_order": timeframes,
        "derived_timeframes": list(cfg.data.derived_timeframes.get(symbol, [])),
        "ifvg_config": {
            "close_through_threshold": ifvg_config.close_through_threshold,
            "inverse_opposing_fvg": ifvg_config.inverse_opposing_fvg,
            "close_through_buffer_enabled": ifvg_config.close_through_buffer_enabled,
        },
        "per_timeframe_counts": per_tf,
        "per_zone_event_count": int(len(events)),
        "visible_per_zone_event_count": visible_count,
        "source_scalar_event_count": source_scalar_count,
        "merged_scalar_event_count": merged_scalar_count,
        "same_availability_row_side_collision_count": int(len(collisions)),
        "suppressed_visible_zone_event_count": int(visible_count - merged_scalar_count),
        "collision_definition": "Multiple per-zone confirmations of the same direction map to one M1 availability row; the merged feature exposes the first configured source timeframe's scalar-selected event.",
        "limitations": [
            "Detector events are not logical setups, policy proposals, orders, or trades.",
            "Source timestamps inherit the supplied local bar index; provider publication time and authoritative calendar are not established.",
            "The merged scalar feature records one source per side and availability row; this packet measures the source events hidden by that projection.",
        ],
        "local_data_manifest": str(RAW_MANIFEST.relative_to(ROOT)),
        "local_data_manifest_sha256": hashlib.sha256(RAW_MANIFEST.read_bytes()).hexdigest(),
        "training_input_sha256": _input_identity(cfg, symbol, timeframes),
        "session_schedule_identity": _schedule_identity(cfg),
        "output_files": [
            "ifvg_timeframe_event_ledger.csv",
            "ifvg_timeframe_collisions.csv",
            "README.md",
            "event_ledger.json",
            "resolved_config.yaml",
            "OUTPUT_SHA256SUMS",
        ],
    }
    readme = [
        "# Training-only IFVG timeframe collision ledger",
        "",
        "This packet compares each configured source timeframe's per-zone IFVG confirmations with the existing merged scalar feature. It preserves the source-timeframe order used by the feature pipeline.",
        "",
        f"- Primary instrument: `{symbol}`; training dates: {start} through {end} inclusive.",
        f"- Source merge order: `{', '.join(timeframes)}`.",
        f"- Configured derived source timeframes: `{', '.join(cfg.data.derived_timeframes.get(symbol, [])) or 'none'}`.",
        f"- Per-zone detector events: {len(events):,}; visible by the end of the primary M1 index: {visible_count:,}.",
        f"- Source-scalar events: {source_scalar_count:,}; merged-scalar events: {merged_scalar_count:,}.",
        f"- Same-availability-row/direction collision groups: {len(collisions):,}; visible detector events suppressed by the merged scalar: {visible_count - merged_scalar_count:,}.",
        "- These are detector-event counts, not logical setup counts, policy proposals, trades, or economic opportunities.",
        "- MTF availability follows `timeframe_close_times` and the configured session close map; external feed publication time and calendar authority are not asserted.",
        "",
        "## Files",
        "",
        "- `ifvg_timeframe_event_ledger.csv`: one row per source-gap confirmation, including its source selection and merged-scalar selection.",
        "- `ifvg_timeframe_collisions.csv`: same-side confirmations mapped to the same M1 availability row.",
        "- `event_ledger.json`: config, source, local-input, and scope identities.",
        "- `OUTPUT_SHA256SUMS`: SHA-256 for every packet file except the checksum file itself.",
        "",
        "Reproduce from the repository root with:",
        "",
        "```bash",
        ".venv-x86/bin/python -m scripts.research.analysis.features.ifvg_timeframe_collision_ledger",
        "```",
        "",
    ]
    (output_dir / "README.md").write_text("\n".join(readme), encoding="utf-8")
    (output_dir / "event_ledger.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_checksums(output_dir)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    cfg = load_config(config_path=config_path)
    result = build_ledger(cfg, args.output_dir, config_path=config_path)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
