#!/usr/bin/env python3
"""Audit configured FVG retest events and same-timeframe zone suppression.

The feature pipeline keeps FVG blocks separate by source timeframe, while each
timeframe's scalar retest flag selects one overlapping source zone. This
training-only diagnostic retains every per-zone retest, records completed-bar
availability on the M1 spine, and measures the within-timeframe projection.
Counts are detector events, not independent setups, policy proposals, or trades.
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
from features.po3.fvg import build_fvg_zone_features_with_event_ledger
from features.po3.fvg_detection import FVGConfig
from market_data.loading.market_data_ingestion import run_pipeline
from market_data.transforms.align import timeframe_close_times
from market_data.transforms.resample import resample
from market_data.transforms.session_schedule import scheduled_session_close_map

ROOT = repository_root(__file__)
DEFAULT_CONFIG = ROOT / "config/features/fvg_ifvg_mtf.yaml"
DEFAULT_OUTPUT = ROOT / "evidence/research/fvg_timeframe_event_ledger"
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
    "zone_start_time_ns",
    "source_origin_bar",
    "source_origin_time_ns",
    "zone_low",
    "zone_high",
    "selected_by_scalar",
]
COLLISION_COLUMNS = [
    "source_timeframe",
    "confirmation_bar",
    "confirmation_time_ns",
    "confirmation_month",
    "side",
    "per_zone_retest_count",
    "suppressed_per_zone_retests",
    "selected_zone_start_time_ns",
]


def _training_slice(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """Keep rows within the inclusive configured training dates."""
    index = pd.DatetimeIndex(frame.index)
    lower = pd.Timestamp(start)
    upper = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
    if index.tz is not None:
        lower = lower.tz_localize(index.tz) if lower.tzinfo is None else lower.tz_convert(index.tz)
        upper = upper.tz_localize(index.tz) if upper.tzinfo is None else upper.tz_convert(index.tz)
    return frame.loc[(index >= lower) & (index <= upper)]


def _configured_timeframes(cfg: DictConfig) -> list[Timeframe]:
    """Resolve FVG source timeframes using the feature builder's fallback."""
    configured = OmegaConf.select(cfg, "features.fvg_timeframes")
    if configured is None:
        configured = OmegaConf.select(cfg, "features.htf_timeframes")
    if configured is None:
        values: Sequence[Any] = TIMEFRAME_ORDER
    else:
        values = configured
    result: list[Timeframe] = ["M1"]
    for value in values:
        timeframe = str(value).upper()
        if timeframe not in SUPPORTED_TIMEFRAMES:
            raise ValueError(f"unsupported FVG timeframe: {timeframe}")
        if timeframe not in result:
            result.append(timeframe)
    return result


def _fvg_config(cfg: DictConfig) -> FVGConfig:
    """Resolve the retest buffer used by the configured feature builder."""
    fraction = OmegaConf.select(cfg, "features.gap_reaction_buffer_fraction")
    enabled = OmegaConf.select(cfg, "features.gap_reaction_buffer_enabled")
    return FVGConfig(
        reaction_buffer_fraction=0.1 if fraction is None else float(fraction),
        reaction_buffer_enabled=True if enabled is None else bool(enabled),
    )


def _validate_scalar_projection(events: pd.DataFrame, scalar: pd.DataFrame) -> None:
    """Require selected per-zone rows to reproduce scalar retest pulses."""
    if not events.empty and not events.columns.is_unique:
        raise ValueError("FVG event ledger columns must be unique")
    for side, flag, origin in (
        ("bullish", "fvg_retest_bull", "fvg_bull_retest_origin_time_ns"),
        ("bearish", "fvg_retest_bear", "fvg_bear_retest_origin_time_ns"),
    ):
        selected = events.loc[events["side"].eq(side) & events["selected_by_scalar"]].sort_values(
            "confirmation_bar"
        )
        expected_bars = np.flatnonzero(scalar[flag].to_numpy(dtype=bool))
        if selected["confirmation_bar"].astype(int).tolist() != expected_bars.tolist():
            raise AssertionError(f"per-zone {side} events do not match scalar FVG retest rows")
        expected_origins = scalar[origin].to_numpy(dtype=float)[expected_bars].astype("int64")
        if not np.array_equal(
            selected["zone_start_time_ns"].to_numpy(dtype="int64"), expected_origins
        ):
            raise AssertionError(f"per-zone {side} source zone differs from scalar origin")
    if events.duplicated(["confirmation_bar", "side", "zone_start_time_ns"]).any():
        raise AssertionError("a source FVG zone confirmed more than once on one row and side")


def _source_events(
    bars: pd.DataFrame,
    timeframe: Timeframe,
    primary_index: pd.DatetimeIndex,
    fvg_config: FVGConfig,
    *,
    scheduled_closes: dict[str, str],
    session_start: str,
) -> pd.DataFrame:
    """Return each source-zone retest and its aligned M1 availability row."""
    scalar, native_events = build_fvg_zone_features_with_event_ledger(bars, fvg_config=fvg_config)
    _validate_scalar_projection(native_events, scalar)
    closes = (
        pd.Series(bars.index, index=bars.index)
        if timeframe == "M1"
        else timeframe_close_times(bars, timeframe, scheduled_closes, session_start)
    )
    rows: list[dict[str, Any]] = []
    for raw_event in native_events.to_dict(orient="records"):
        event = cast(dict[str, Any], raw_event)
        source_bar = int(event["confirmation_bar"])
        available_at = closes.iloc[source_bar]
        if pd.isna(available_at):
            m1_bar = -1
            available_ns = -1
        else:
            available = pd.Timestamp(available_at)
            m1_bar = int(primary_index.searchsorted(available, side="left"))
            available_ns = int(available.value)
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
            }
        )
    return pd.DataFrame(rows, columns=EVENT_COLUMNS)


def _collision_table(
    events: pd.DataFrame, bars_by_timeframe: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """Summarize same-source-row/side zone overlaps hidden by the scalar."""
    rows: list[dict[str, Any]] = []
    for (timeframe, bar, side), group in events.groupby(
        ["source_timeframe", "confirmation_bar", "side"], sort=True
    ):
        if len(group) < 2:
            continue
        chosen = group.loc[group["selected_by_scalar"]]
        if len(chosen) != 1:
            raise AssertionError("each same-row FVG collision must choose one source zone")
        source_bar = int(cast(int, bar))
        bars = bars_by_timeframe[str(timeframe)]
        rows.append(
            {
                "source_timeframe": str(timeframe),
                "confirmation_bar": source_bar,
                "confirmation_time_ns": int(group["confirmation_time_ns"].iloc[0]),
                "confirmation_month": pd.Timestamp(bars.index[source_bar]).strftime("%Y-%m"),
                "side": str(side),
                "per_zone_retest_count": int(len(group)),
                "suppressed_per_zone_retests": int(len(group) - 1),
                "selected_zone_start_time_ns": int(chosen["zone_start_time_ns"].iloc[0]),
            }
        )
    return pd.DataFrame(rows, columns=COLLISION_COLUMNS)


def _source_hashes() -> dict[str, str]:
    paths = (
        "features/po3/fvg.py",
        "features/po3/fvg_detection.py",
        "features/po3/zones.py",
        "features/pipeline/feature_matrix_builder.py",
        "market_data/loading/market_data_ingestion.py",
        "market_data/transforms/align.py",
        "market_data/transforms/resample.py",
        "market_data/transforms/session_schedule.py",
        "scripts/research/analysis/features/fvg_timeframe_event_ledger.py",
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
    for filename in filenames.values():
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
    """Build a training-only per-zone FVG retest packet by source timeframe."""
    cfg.data.cache_dir = str(ROOT / "cache/trade_setup_opportunity_census")
    datasets = run_pipeline(cfg, datasets=["training"])
    symbol = str(cfg.data.primary)
    start = str(cfg.data.split.train_start)
    end = str(cfg.data.split.train_end)
    primary = _training_slice(datasets[symbol]["M1"], start, end)
    if primary.empty:
        raise ValueError("configured training-only M1 input is empty")

    timeframes = _configured_timeframes(cfg)
    fvg_config = _fvg_config(cfg)
    scheduled_closes = scheduled_session_close_map(cfg)
    session_start = str(OmegaConf.select(cfg, "session.start") or "16:30")
    bars_by_timeframe: dict[str, pd.DataFrame] = {"M1": primary}
    for timeframe in timeframes:
        if timeframe == "M1":
            continue
        source = datasets[symbol].get(timeframe)
        if source is None:
            source = resample(primary, timeframe)
        bars_by_timeframe[timeframe] = _training_slice(source, start, end)

    ledgers = [
        _source_events(
            bars_by_timeframe[timeframe],
            timeframe,
            pd.DatetimeIndex(primary.index),
            fvg_config,
            scheduled_closes=scheduled_closes,
            session_start=session_start,
        )
        for timeframe in timeframes
        if timeframe in bars_by_timeframe and not bars_by_timeframe[timeframe].empty
    ]
    events = (
        pd.concat(ledgers, ignore_index=True) if ledgers else pd.DataFrame(columns=EVENT_COLUMNS)
    )
    collisions = _collision_table(events, bars_by_timeframe)
    output_dir.mkdir(parents=True, exist_ok=True)
    events.to_csv(output_dir / "fvg_timeframe_event_ledger.csv", index=False)
    collisions.to_csv(output_dir / "fvg_timeframe_collisions.csv", index=False)

    per_timeframe = (
        {
            str(timeframe): {
                "per_zone_retests": int(len(group)),
                "scalar_retests": int(group["selected_by_scalar"].sum()),
                "collision_groups": int(
                    len(collisions.loc[collisions["source_timeframe"].eq(timeframe)])
                ),
                "suppressed_zone_retests": int(
                    collisions.loc[
                        collisions["source_timeframe"].eq(timeframe), "suppressed_per_zone_retests"
                    ].sum()
                ),
            }
            for timeframe, group in events.groupby("source_timeframe", sort=False)
        }
        if not events.empty
        else {}
    )
    resolved_config = OmegaConf.to_yaml(cfg, resolve=True)
    (output_dir / "resolved_config.yaml").write_text(resolved_config, encoding="utf-8")
    summary: dict[str, Any] = {
        "status": "descriptive_training_fvg_detector_events_only",
        "interpretation": "Per-zone FVG retest confirmations by configured source timeframe; per-timeframe scalar selection suppresses older overlapping zones.",
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
        "source_timeframes": timeframes,
        "derived_timeframes": list(cfg.data.derived_timeframes.get(symbol, [])),
        "fvg_config": {
            "reaction_buffer_fraction": fvg_config.reaction_buffer_fraction,
            "reaction_buffer_enabled": fvg_config.reaction_buffer_enabled,
        },
        "per_timeframe_counts": per_timeframe,
        "per_zone_retest_count": int(len(events)),
        "visible_per_zone_retest_count": int(events["effective_availability_m1_bar"].ge(0).sum())
        if not events.empty
        else 0,
        "scalar_retest_count": int(events["selected_by_scalar"].sum()) if not events.empty else 0,
        "collision_group_count": int(len(collisions)),
        "suppressed_visible_per_zone_retest_count": int(
            events["effective_availability_m1_bar"].ge(0).sum()
            - (events["effective_availability_m1_bar"].ge(0) & events["selected_by_scalar"]).sum()
        )
        if not events.empty
        else 0,
        "collision_definition": "More than one source FVG zone confirms a retest for the same source timeframe, source row, and direction; the source-timeframe scalar feature selects one zone.",
        "limitations": [
            "Per-timeframe blocks remain separate in the feature matrix; this ledger does not imply cross-timeframe scalar merging.",
            "Detector events are not logical setups, policy proposals, orders, or trades.",
            "Source timestamps inherit local bar indices; external feed publication time and authoritative calendar are not established.",
        ],
        "local_data_manifest": str(RAW_MANIFEST.relative_to(ROOT)),
        "local_data_manifest_sha256": hashlib.sha256(RAW_MANIFEST.read_bytes()).hexdigest(),
        "training_input_sha256": _input_identity(cfg, symbol, timeframes),
        "session_schedule_identity": _schedule_identity(cfg),
        "output_files": [
            "fvg_timeframe_event_ledger.csv",
            "fvg_timeframe_collisions.csv",
            "README.md",
            "event_ledger.json",
            "resolved_config.yaml",
            "OUTPUT_SHA256SUMS",
        ],
    }
    readme = [
        "# Training-only FVG timeframe event ledger",
        "",
        "This packet records per-zone FVG retest confirmations on each configured source timeframe and compares them with that timeframe's scalar feature projection. The feature matrix keeps each timeframe as a separate block.",
        "",
        f"- Primary instrument: `{symbol}`; training dates: {start} through {end} inclusive.",
        f"- Source timeframes: `{', '.join(timeframes)}`; derived: `{', '.join(summary['derived_timeframes']) or 'none'}`.",
        f"- Per-zone confirmations: {summary['per_zone_retest_count']:,}; visible by the end of the M1 spine: {summary['visible_per_zone_retest_count']:,}.",
        f"- Source scalar retest pulses: {summary['scalar_retest_count']:,}; same-timeframe collision groups: {summary['collision_group_count']:,}; visible zone retests not represented by a scalar: {summary['suppressed_visible_per_zone_retest_count']:,}.",
        f"- Retest buffer: enabled `{fvg_config.reaction_buffer_enabled}` at fraction `{fvg_config.reaction_buffer_fraction}`.",
        "- These are detector-event counts, not logical setup counts, policy actions, trades, or economic results.",
        "",
        "## Files",
        "",
        "- `fvg_timeframe_event_ledger.csv`: one row per source-zone retest confirmation and its M1 availability boundary.",
        "- `fvg_timeframe_collisions.csv`: same-timeframe/source-row/direction groups with multiple zone confirmations.",
        "- `event_ledger.json`: config, source, input, and scope identities.",
        "- `OUTPUT_SHA256SUMS`: SHA-256 for every packet file except the checksum file itself.",
        "",
        "Reproduce from the repository root with:",
        "",
        "```bash",
        ".venv-x86/bin/python -m scripts.research.analysis.features.fvg_timeframe_event_ledger",
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
    print(
        json.dumps(
            build_ledger(cfg, args.output_dir, config_path=config_path), indent=2, sort_keys=True
        )
    )


if __name__ == "__main__":
    main()
