#!/usr/bin/env python3
"""Build a training-only ledger of every IFVG source-gap confirmation.

The model feature remains scalar and selects the newest same-row confirmation
per direction. This diagnostic preserves all per-gap confirmations so local
zone collisions can be counted without changing policy action semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

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

ROOT = repository_root(__file__)
DEFAULT_CONFIG = ROOT / "config/research/trade_setup_mtf_reasoning_2m.yaml"
DEFAULT_OUTPUT = ROOT / "evidence/research/ifvg_zone_event_ledger"
RAW_MANIFEST = (
    ROOT / "evidence/research/releases/negative-evidence-readiness/RAW_DATA_SHA256_MANIFEST.json"
)
EVENT_COLUMNS = [
    "confirmation_bar",
    "confirmation_time_ns",
    "side",
    "source_origin_bar",
    "source_origin_time_ns",
    "zone_low",
    "zone_high",
    "pass_bar",
    "pass_time_ns",
    "pass_extreme",
    "selected_by_scalar",
]
COLLISION_COLUMNS = [
    "confirmation_bar",
    "confirmation_time_ns",
    "confirmation_month",
    "side",
    "per_zone_confirmation_count",
    "suppressed_per_zone_confirmations",
    "selected_source_origin_bar",
    "selected_source_origin_time_ns",
]


def _training_slice(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """Keep only rows within the config's inclusive training dates."""
    index = pd.DatetimeIndex(frame.index)
    return frame.loc[make_train_mask(index, end, start)]


def _ifvg_config(cfg: DictConfig) -> IFVGConfig:
    """Resolve the same IFVG threshold and orientation as the feature pipeline."""
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


def _validate_scalar_projection(ledger: pd.DataFrame, scalar: pd.DataFrame) -> None:
    """Require one newest per-zone row for every model-visible scalar pulse."""
    if not ledger.empty and not ledger.columns.is_unique:
        raise ValueError("IFVG event ledger columns must be unique")
    selected = ledger.loc[ledger["selected_by_scalar"]] if not ledger.empty else ledger
    for side, flag, origin in (
        ("bullish", "ifvg_bullish_confirmed", "ifvg_bullish_origin_bar"),
        ("bearish", "ifvg_bearish_confirmed", "ifvg_bearish_origin_bar"),
    ):
        chosen = selected.loc[selected["side"].eq(side)]
        expected_bars = np.flatnonzero(scalar[flag].to_numpy(dtype=bool))
        if chosen["confirmation_bar"].astype(int).tolist() != expected_bars.tolist():
            raise AssertionError(f"per-zone {side} events do not match scalar confirmation rows")
        if not np.array_equal(
            chosen["source_origin_bar"].to_numpy(dtype=int),
            scalar[origin].to_numpy(dtype=float)[expected_bars].astype(int),
        ):
            raise AssertionError(f"per-zone {side} selection does not match scalar source origin")


def _collision_table(ledger: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    """Return only row/direction groups where scalar selection suppresses zones."""
    rows: list[dict[str, Any]] = []
    if ledger.empty:
        return pd.DataFrame(columns=COLLISION_COLUMNS)
    for (bar, side), group in ledger.groupby(["confirmation_bar", "side"], sort=True):
        if len(group) < 2:
            continue
        selected = group.loc[group["selected_by_scalar"]]
        if len(selected) != 1:
            raise AssertionError("each same-row IFVG collision must select exactly one source gap")
        bar_index = int(cast(int, bar))
        chosen = selected.iloc[0]
        rows.append(
            {
                "confirmation_bar": bar_index,
                "confirmation_time_ns": int(group["confirmation_time_ns"].iloc[0]),
                "confirmation_month": pd.Timestamp(bars.index[bar_index]).strftime("%Y-%m"),
                "side": str(side),
                "per_zone_confirmation_count": int(len(group)),
                "suppressed_per_zone_confirmations": int(len(group) - 1),
                "selected_source_origin_bar": int(chosen["source_origin_bar"]),
                "selected_source_origin_time_ns": int(chosen["source_origin_time_ns"]),
            }
        )
    return pd.DataFrame(rows, columns=COLLISION_COLUMNS)


def _monthly_summary(ledger: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    """Summarize per-zone events, scalar pulses, and suppressed collisions by month."""
    columns = [
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
    work["confirmation_month"] = [
        pd.Timestamp(bars.index[int(row)]).strftime("%Y-%m") for row in work["confirmation_bar"]
    ]
    grouped = work.groupby(["confirmation_month", "side"], sort=True).agg(
        per_zone_confirmations=("side", "size"),
        scalar_confirmation_pulses=("selected_by_scalar", "sum"),
    )
    grouped["suppressed_per_zone_confirmations"] = (
        grouped["per_zone_confirmations"] - grouped["scalar_confirmation_pulses"]
    )
    collisions = _collision_table(ledger, bars)
    if collisions.empty:
        grouped["collision_rows"] = 0
    else:
        collision_counts = collisions.groupby(["confirmation_month", "side"]).size()
        grouped["collision_rows"] = collision_counts
        grouped["collision_rows"] = grouped["collision_rows"].fillna(0)
    result = grouped.reset_index()
    result["collision_rows"] = result["collision_rows"].astype(int)
    return result.loc[:, columns]


def _input_identity(cfg: DictConfig, symbol: str) -> dict[str, str]:
    """Validate and identify the current local M1 input against its pinned manifest."""
    manifest = json.loads(RAW_MANIFEST.read_text(encoding="utf-8"))
    spec = cfg.data.datasets.training
    relative = (Path(str(spec.raw_dir)) / str(spec.m1_files[symbol])).as_posix()
    entry = {item["path"]: item for item in manifest["files"]}.get(relative)
    if entry is None:
        raise ValueError(f"training input absent from pinned local data manifest: {relative}")
    path = ROOT / relative
    stat = path.stat()
    if stat.st_size != int(entry["size_bytes"]):
        raise ValueError(f"training input size differs from pinned manifest: {relative}")
    manifest_mtime = pd.Timestamp(entry["mtime_utc"]).timestamp()
    if abs(stat.st_mtime - manifest_mtime) > 1.0:
        raise ValueError(f"training input mtime differs from pinned manifest: {relative}")
    return {relative: str(entry["sha256"])}


def _source_hashes() -> dict[str, str]:
    paths = (
        "features/po3/fvg_detection.py",
        "features/po3/ifvg_detection.py",
        "features/po3/po3_phase_state.py",
        "features/pipeline/po3_stage.py",
        "market_data/loading/market_data_ingestion.py",
        "scripts/research/analysis/features/ifvg_zone_event_ledger.py",
    )
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in paths}


def _git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _write_checksums(output_dir: Path) -> None:
    """Write stable SHA-256 entries for every packet file except the manifest itself."""
    rows = []
    for path in sorted(output_dir.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != "OUTPUT_SHA256SUMS":
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            rows.append(f"{digest}  {path.name}")
    (output_dir / "OUTPUT_SHA256SUMS").write_text("\n".join(rows) + "\n", encoding="utf-8")


def build_ledger(
    cfg: DictConfig,
    output_dir: Path,
    *,
    config_path: Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Build the training-only IFVG per-zone and scalar-collision evidence packet."""
    cfg.data.cache_dir = str(ROOT / "cache/trade_setup_opportunity_census")
    datasets = run_pipeline(cfg, datasets=["training"])
    symbol = str(cfg.data.primary)
    start = str(cfg.data.split.train_start)
    end = str(cfg.data.split.train_end)
    bars = _training_slice(datasets[symbol]["M1"], start, end)
    if bars.empty:
        raise ValueError("configured training-only M1 input is empty")

    fvg = detect_fvg(bars, FVGConfig())
    ifvg_config = _ifvg_config(cfg)
    scalar = detect_ifvg_confirmation(bars, fvg, ifvg_config)
    ledger = detect_ifvg_confirmation_events(bars, fvg, ifvg_config)
    ledger = ledger.reindex(columns=EVENT_COLUMNS)
    _validate_scalar_projection(ledger, scalar)
    collisions = _collision_table(ledger, bars)
    monthly = _monthly_summary(ledger, bars)

    output_dir.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(output_dir / "ifvg_zone_event_ledger.csv", index=False)
    collisions.to_csv(output_dir / "ifvg_confirmation_collisions.csv", index=False)
    monthly.to_csv(output_dir / "monthly_collision_summary.csv", index=False)

    per_zone_count = int(len(ledger))
    scalar_pulse_count = int(ledger["selected_by_scalar"].sum()) if not ledger.empty else 0
    collision_count = int(len(collisions))
    suppressed_count = (
        int(collisions["suppressed_per_zone_confirmations"].sum()) if collision_count else 0
    )
    collision_groups_by_side = (
        {str(side): int(count) for side, count in collisions.groupby("side").size().items()}
        if collision_count
        else {}
    )
    suppressed_by_side = (
        {
            str(side): int(count)
            for side, count in collisions.groupby("side")["suppressed_per_zone_confirmations"]
            .sum()
            .items()
        }
        if collision_count
        else {}
    )
    collision_size_distribution = (
        {
            str(size): int(count)
            for size, count in collisions["per_zone_confirmation_count"]
            .value_counts()
            .sort_index()
            .items()
        }
        if collision_count
        else {}
    )
    side_summary = (
        "; ".join(
            f"{side}: {count:,} groups, {suppressed_by_side[side]:,} suppressed"
            for side, count in sorted(collision_groups_by_side.items())
        )
        or "none"
    )
    size_summary = (
        ", ".join(
            f"{size} zones: {count:,} rows" for size, count in collision_size_distribution.items()
        )
        or "none"
    )
    readme_lines = [
        "# Training-only IFVG zone event ledger",
        "",
        "This packet records every source FVG that independently satisfies the configured IFVG confirmation rule. It compares that per-zone ledger with the existing scalar feature, which selects the newest matching source gap per row and direction.",
        "",
        f"- Primary instrument: `{symbol}`; source timeframe: `M1`.",
        f"- Training dates: {start} through {end} inclusive; rows: {len(bars):,}.",
        f"- Per-zone confirmations: {per_zone_count:,}; scalar confirmation pulses: {scalar_pulse_count:,}.",
        f"- Same-row/direction collision groups: {collision_count:,}; additional per-zone confirmations suppressed by scalar projection: {suppressed_count:,}.",
        f"- Collision groups by direction: {side_summary}.",
        f"- Collision group sizes (source gaps per row/direction): {size_summary}.",
        f"- IFVG close-through threshold: {ifvg_config.close_through_threshold}; inverse opposing gap: {ifvg_config.inverse_opposing_fvg}; buffer enabled: {ifvg_config.close_through_buffer_enabled}.",
        "- The selected flag marks the newest source gap under the production detector's source-time order. Ledger rows describe detector events, not policy proposals, trades, or independent economic opportunities.",
        "- Source bars and date labels use the current local training data loaded through the configured pipeline.",
        "",
        "## Files",
        "",
        "- `ifvg_zone_event_ledger.csv`: one row per per-zone confirmation, with formation, pass-through, confirmation, geometry, and scalar-selection provenance.",
        "- `ifvg_confirmation_collisions.csv`: only row/direction groups with more than one confirmed source gap.",
        "- `monthly_collision_summary.csv`: monthly per-zone confirmations, scalar pulses, suppressed events, and collision rows.",
        "- `event_ledger.json`: data/config/source identities and scope.",
        "- `OUTPUT_SHA256SUMS`: SHA-256 for every packet file except the checksum file itself.",
        "",
        "Reproduce from the repository root with:",
        "",
        "```bash",
        ".venv-x86/bin/python -m scripts.research.analysis.features.ifvg_zone_event_ledger",
        "```",
        "",
    ]
    (output_dir / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")

    resolved_config = OmegaConf.to_yaml(cfg, resolve=True)
    (output_dir / "resolved_config.yaml").write_text(resolved_config, encoding="utf-8")
    local_inputs = _input_identity(cfg, symbol)
    metadata: dict[str, Any] = {
        "status": "descriptive_training_zone_events_only",
        "interpretation": "Per-zone IFVG detector confirmations versus the newest-zone scalar projection; not policy proposals, trades, or returns.",
        "source_commit": _git_commit(),
        "source_hashes": _source_hashes(),
        "config_path": (
            config_path.resolve().relative_to(ROOT.resolve()).as_posix()
            if config_path.resolve().is_relative_to(ROOT.resolve())
            else str(config_path.resolve())
        ),
        "resolved_config_sha256": hashlib.sha256(resolved_config.encode("utf-8")).hexdigest(),
        "training_period": {"start": start, "end_inclusive": end},
        "training_m1_rows": int(len(bars)),
        "primary_symbol": symbol,
        "source_timeframe": "M1",
        "ifvg_config": {
            "close_through_threshold": ifvg_config.close_through_threshold,
            "inverse_opposing_fvg": ifvg_config.inverse_opposing_fvg,
            "close_through_buffer_enabled": ifvg_config.close_through_buffer_enabled,
        },
        "per_zone_confirmation_count": per_zone_count,
        "scalar_confirmation_pulse_count": scalar_pulse_count,
        "collision_group_count": collision_count,
        "suppressed_per_zone_confirmation_count": suppressed_count,
        "collision_groups_by_side": collision_groups_by_side,
        "suppressed_per_zone_confirmations_by_side": suppressed_by_side,
        "collision_group_size_distribution": collision_size_distribution,
        "collision_definition": "A collision is a same-row, same-direction group with more than one independently confirmed source FVG; the scalar feature selects the newest gap and exposes one pulse.",
        "local_data_manifest": str(RAW_MANIFEST.relative_to(ROOT)),
        "local_data_manifest_sha256": hashlib.sha256(RAW_MANIFEST.read_bytes()).hexdigest(),
        "training_input_sha256": local_inputs,
        "output_files": [
            "ifvg_zone_event_ledger.csv",
            "ifvg_confirmation_collisions.csv",
            "monthly_collision_summary.csv",
            "README.md",
            "event_ledger.json",
            "resolved_config.yaml",
            "OUTPUT_SHA256SUMS",
        ],
    }
    (output_dir / "event_ledger.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_checksums(output_dir)
    return metadata


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
