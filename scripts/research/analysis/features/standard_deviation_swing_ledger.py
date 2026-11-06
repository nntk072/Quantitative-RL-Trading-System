"""Count selected-profile swing-leg availability and retracement episodes.

The ledger describes the producer's one-current-leg projection. It is not a
ground-truth ontology of market events, policy actions, orders, or trades.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from omegaconf import DictConfig, OmegaConf

from configuration.configuration_loader import load_config
from configuration.paths import repository_root
from features import build_features
from market_data.loading.market_data_ingestion import run_pipeline
from market_data.splits.definitions import make_train_mask

ROOT = repository_root(__file__)
DEFAULT_CONFIG = ROOT / "config/research/trade_setup_mtf_reasoning_2m.yaml"
DEFAULT_OUTPUT = ROOT / "evidence/research/standard_deviation_swing_legs"
TIMEFRAMES = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
LEG_COLUMNS = (
    "timeframe",
    "direction",
    "leg_start_time_ns",
    "leg_end_time_ns",
    "first_available_time",
    "last_available_time",
    "available_rows",
    "availability_episodes",
    "eligible_rows",
    "eligibility_episodes",
    "first_eligible_time",
    "last_eligible_time",
)
GROUP_COLUMNS = (
    "direction",
    "leg_start_time_ns",
    "leg_end_time_ns",
    "timeframes",
    "timeframe_count",
    "eligible_rows_across_timeframes",
    "first_available_time",
)


def _active_timeframes(cfg: DictConfig) -> list[str]:
    block = cfg.features.get("entry_ideas")
    if not block or not bool(block.get("enabled", False)):
        return []
    configured = block.get("timeframes")
    selected = {str(item).upper() for item in configured} if configured else set(TIMEFRAMES)
    return [timeframe for timeframe in TIMEFRAMES if timeframe in selected]


def _timestamp(value: Any) -> int | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return int(round(number))


def _swing_leg_ledger(
    features: pd.DataFrame,
    timeframes: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Summarize each visible source leg and its retracement eligibility spans."""
    if not isinstance(features.index, pd.DatetimeIndex):
        raise TypeError("feature index must be a DatetimeIndex")
    leg_rows: list[dict[str, Any]] = []
    source_groups: dict[tuple[int, int, int], dict[str, Any]] = defaultdict(
        lambda: {"timeframes": set(), "eligible_rows": 0, "first_available": None}
    )
    summary: dict[str, dict[str, int]] = {}

    for timeframe in timeframes:
        prefix = "" if timeframe == "M1" else f"{timeframe}_"
        required = (
            f"{prefix}standard_deviation_leg_valid",
            f"{prefix}standard_deviation_leg_direction",
            f"{prefix}standard_deviation_leg_start_time_ns",
            f"{prefix}standard_deviation_leg_end_time_ns",
        )
        missing = [column for column in required if column not in features.columns]
        if missing:
            raise ValueError(f"{timeframe} swing-leg features are missing: {missing}")
        numeric = {
            column: pd.to_numeric(features[column], errors="coerce").to_numpy(dtype=float)
            for column in required
        }
        valid = np.isfinite(numeric[required[0]]) & (numeric[required[0]] > 0.0)
        direction_values = numeric[required[1]]
        starts = numeric[required[2]]
        ends = numeric[required[3]]
        times = pd.DatetimeIndex(features.index)
        timeframe_summary = {
            "long_source_legs": 0,
            "short_source_legs": 0,
            "source_valid_rows": 0,
            "eligible_legs": 0,
            "eligible_rows": 0,
            "eligible_episodes": 0,
            "legs_without_retracement": 0,
        }

        for direction in (1, -1):
            side = "long" if direction > 0 else "short"
            eligible_column = f"entry_idea_standard_deviation_{timeframe}_{side}"
            if eligible_column not in features.columns:
                raise ValueError(f"candidate eligibility column is missing: {eligible_column}")
            eligible_values = (
                pd.to_numeric(features[eligible_column], errors="coerce")
                .fillna(0.0)
                .to_numpy(dtype=float)
                > 0.0
            )
            records: dict[tuple[int, int], dict[str, Any]] = {}
            previous_key: tuple[int, int] | None = None
            previous_valid = False
            previous_eligible = False

            for position in range(len(features)):
                key: tuple[int, int] | None = None
                start_ns = _timestamp(starts[position])
                end_ns = _timestamp(ends[position])
                row_valid = bool(
                    valid[position]
                    and direction_values[position] == direction
                    and start_ns is not None
                    and end_ns is not None
                )
                if row_valid and start_ns is not None and end_ns is not None:
                    key = (start_ns, end_ns)
                    record = records.setdefault(
                        key,
                        {
                            "timeframe": timeframe,
                            "direction": side,
                            "leg_start_time_ns": start_ns,
                            "leg_end_time_ns": end_ns,
                            "first_available_time": times[position].isoformat(),
                            "last_available_time": times[position].isoformat(),
                            "available_rows": 0,
                            "availability_episodes": 0,
                            "eligible_rows": 0,
                            "eligibility_episodes": 0,
                            "first_eligible_time": "",
                            "last_eligible_time": "",
                        },
                    )
                    record["last_available_time"] = times[position].isoformat()
                    record["available_rows"] += 1
                    if not (previous_valid and previous_key == key):
                        record["availability_episodes"] += 1
                    timeframe_summary[f"{'long' if direction > 0 else 'short'}_source_legs"] = len(
                        records
                    )
                    timeframe_summary["source_valid_rows"] += 1

                    if eligible_values[position]:
                        if not (previous_valid and previous_key == key and previous_eligible):
                            record["eligibility_episodes"] += 1
                            timeframe_summary["eligible_episodes"] += 1
                        record["eligible_rows"] += 1
                        record["first_eligible_time"] = (
                            record["first_eligible_time"] or times[position].isoformat()
                        )
                        record["last_eligible_time"] = times[position].isoformat()
                        timeframe_summary["eligible_rows"] += 1
                    previous_key = key
                    previous_valid = True
                    previous_eligible = bool(eligible_values[position])
                else:
                    previous_key = None
                    previous_valid = False
                    previous_eligible = False

            for key, record in records.items():
                if int(record["eligible_rows"]) > 0:
                    timeframe_summary["eligible_legs"] += 1
                else:
                    timeframe_summary["legs_without_retracement"] += 1
                start_ns, end_ns = key
                group_key = (direction, start_ns, end_ns)
                group = source_groups[group_key]
                group["timeframes"].add(timeframe)
                group["eligible_rows"] += int(record["eligible_rows"])
                first_time = record["first_available_time"]
                if group["first_available"] is None or first_time < group["first_available"]:
                    group["first_available"] = first_time
                leg_rows.append(record)
        summary[timeframe] = timeframe_summary

    group_rows = [
        {
            "direction": "long" if direction > 0 else "short",
            "leg_start_time_ns": start_ns,
            "leg_end_time_ns": end_ns,
            "timeframes": json.dumps(sorted(group["timeframes"], key=TIMEFRAMES.index)),
            "timeframe_count": len(group["timeframes"]),
            "eligible_rows_across_timeframes": int(group["eligible_rows"]),
            "first_available_time": group["first_available"],
        }
        for (direction, start_ns, end_ns), group in sorted(source_groups.items())
    ]
    legs = pd.DataFrame(leg_rows, columns=LEG_COLUMNS)
    if not legs.empty:
        legs = legs.sort_values(
            ["timeframe", "direction", "leg_start_time_ns", "leg_end_time_ns"],
            kind="stable",
        ).reset_index(drop=True)
    groups = pd.DataFrame(group_rows, columns=GROUP_COLUMNS)
    totals = {
        "source_leg_projection_rows": int(len(legs)),
        "eligible_source_legs": int(legs["eligible_rows"].gt(0).sum()) if not legs.empty else 0,
        "source_legs_without_retracement": int(legs["eligible_rows"].eq(0).sum())
        if not legs.empty
        else 0,
        "source_tuple_groups_across_timeframes": int(len(groups)),
        "tuple_groups_on_multiple_timeframes": int(groups["timeframe_count"].gt(1).sum())
        if not groups.empty
        else 0,
    }
    return legs, groups, {"by_timeframe": summary, "totals": totals}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_checksums(output_dir: Path) -> None:
    lines = [
        f"{_sha256(path)}  {path.name}"
        for path in sorted(output_dir.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name != "OUTPUT_SHA256SUMS"
    ]
    (output_dir / "OUTPUT_SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _training_slice(
    frames: dict[str, pd.DataFrame], start: str, end: str
) -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    for timeframe, frame in frames.items():
        index = pd.DatetimeIndex(frame.index)
        result[timeframe] = frame.loc[make_train_mask(index, end, start)]
    return result


def build_ledger(
    config_path: Path = DEFAULT_CONFIG,
    output_dir: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    """Build a selected-profile, training-only swing-leg ledger."""
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty evidence directory: {output_dir}")
    cfg = load_config(config_path=config_path)
    if not bool(cfg.features.get("entry_ideas", {}).get("enabled", False)):
        raise ValueError("entry_ideas must be enabled in the selected config")
    timeframes = _active_timeframes(cfg)
    if not timeframes:
        raise ValueError("no standard-deviation source timeframes are enabled")

    cfg.data.cache_dir = str(ROOT / "cache/trade_setup_opportunity_census")
    datasets = run_pipeline(cfg, datasets=["training"])
    primary_symbol = str(cfg.data.primary)
    secondary_symbol = str(cfg.data.secondary)
    train_start = str(cfg.data.split.train_start)
    train_end = str(cfg.data.split.train_end)
    primary_frames = _training_slice(datasets[primary_symbol], train_start, train_end)
    secondary_frames = _training_slice(datasets[secondary_symbol], train_start, train_end)
    primary = primary_frames["M1"]
    secondary = secondary_frames["M1"]
    train_mask = pd.Series(True, index=primary.index, dtype=bool)
    features = build_features(
        primary,
        secondary,
        cfg=cfg,
        train_mask=train_mask,
        timeframe_bars=primary_frames,
        secondary_timeframe_bars=secondary_frames,
    )
    legs, groups, counts = _swing_leg_ledger(features, timeframes)

    resolved_config = OmegaConf.to_yaml(cfg, resolve=True)
    raw_manifest = (
        ROOT
        / "evidence/research/releases/negative-evidence-readiness/RAW_DATA_SHA256_MANIFEST.json"
    )
    manifest = json.loads(raw_manifest.read_text(encoding="utf-8"))
    manifest_files = {entry["path"]: entry for entry in manifest["files"]}
    training_input_hashes: dict[str, str] = {}
    training_spec = cfg.data.datasets.training
    for symbol in (primary_symbol, secondary_symbol):
        relative_inputs = [training_spec.m1_files[symbol]]
        relative_inputs.extend(
            timeframe_files[symbol]
            for timeframe_files in training_spec.timeframe_files.values()
            if symbol in timeframe_files
        )
        for relative_input in relative_inputs:
            relative_path = (Path(str(training_spec.raw_dir)) / str(relative_input)).as_posix()
            if relative_path not in manifest_files:
                raise ValueError(f"training input absent from local manifest: {relative_path}")
            manifest_record = manifest_files[relative_path]
            input_path = ROOT / relative_path
            stat = input_path.stat()
            if stat.st_size != int(manifest_record["size_bytes"]):
                raise ValueError(f"training input size differs from manifest: {relative_path}")
            manifest_mtime = pd.Timestamp(manifest_record["mtime_utc"]).timestamp()
            if abs(stat.st_mtime - manifest_mtime) > 1.0:
                raise ValueError(f"training input mtime differs from manifest: {relative_path}")
            training_input_hashes[relative_path] = str(manifest_record["sha256"])
    source_paths = (
        "features/context/swing_retracement.py",
        "features/technical/structure.py",
        "features/context/entry_ideas.py",
        "features/pipeline/feature_matrix_builder.py",
        "scripts/research/analysis/features/standard_deviation_swing_ledger.py",
    )
    metadata: dict[str, Any] = {
        "schema": "qrl.standard_deviation_swing_leg_projection.v1",
        "status": "descriptive_training_feature_projection_only",
        "interpretation": (
            "Rows count the selected feature producer's latest confirmed swing-leg projections "
            "and retracement eligibility episodes. They are not ground-truth market-event counts, "
            "policy choices, orders, fills, or economic results."
        ),
        "config_path": (
            config_path.resolve().relative_to(ROOT.resolve()).as_posix()
            if config_path.resolve().is_relative_to(ROOT.resolve())
            else str(config_path.resolve())
        ),
        "resolved_config_sha256": hashlib.sha256(resolved_config.encode("utf-8")).hexdigest(),
        "training_period": {"start": train_start, "end_inclusive": train_end},
        "primary_symbol": primary_symbol,
        "secondary_symbol": secondary_symbol,
        "m1_rows": int(len(primary)),
        "feature_rows": int(len(features)),
        "active_source_timeframes": timeframes,
        "source_event_key": ["direction", "leg_start_time_ns", "leg_end_time_ns"],
        "availability_definition": (
            "First/last M1 feature row where the timeframe-prefixed leg-valid flag and matching "
            "direction expose the same source pivot pair. This is pipeline availability, not "
            "external feed publication time."
        ),
        "eligibility_definition": (
            "Contiguous eligible M1 rows for the exact source leg and configured candidate side; "
            "a renewed eligible span after a gap is counted as another episode."
        ),
        "cross_timeframe_definition": (
            "Exact equality of serialized direction and source pivot-time keys across timeframe "
            "projections. It is a linkage relation, not proof of one shared logical event."
        ),
        "counts": counts,
        "source_hashes": {path: _sha256(ROOT / path) for path in source_paths},
        "raw_data_manifest_path": str(raw_manifest.relative_to(ROOT)),
        "raw_data_manifest_sha256": _sha256(raw_manifest),
        "training_input_sha256": training_input_hashes,
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "limitations": [
            "The upstream structure producer exposes the latest confirmed pivot pair, not every latent or overlapping swing pattern.",
            "Float-backed epoch-nanosecond feature fields can lose subsecond precision; source keys are not exact publication instants.",
            "Eligibility episodes do not establish separate policy decisions, executable opportunities, or fills.",
            "No report-period rows, checkpoints, policy actions, environment steps, or economic outcomes are used.",
        ],
    }
    legs.to_csv(output_dir / "swing_leg_eligibility_ledger.csv", index=False)
    groups.to_csv(output_dir / "cross_timeframe_swing_leg_key_groups.csv", index=False)
    (output_dir / "resolved_config.yaml").write_text(resolved_config, encoding="utf-8")
    (output_dir / "ledger.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    readme = "\n".join(
        [
            "# Standard-deviation swing-leg projection ledger",
            "",
            "This training-only packet counts the selected producer's latest confirmed swing-leg projections and the contiguous candidate eligibility spans attached to each source leg.",
            "",
            f"- Training window: {train_start} through {train_end}; primary symbol: `{primary_symbol}`.",
            f"- Source timeframes: {', '.join(timeframes)}.",
            f"- Source leg projections: {counts['totals']['source_leg_projection_rows']:,}; with at least one retracement eligibility row: {counts['totals']['eligible_source_legs']:,}.",
            f"- Exact source-key groups appear on multiple timeframes: {counts['totals']['tuple_groups_on_multiple_timeframes']:,}; these are key matches, not proof of shared logical events.",
            "- A source leg is keyed by direction and the ordered source pivot times. Availability is the first M1 feature row carrying that valid leg key.",
            "- Eligibility episodes count contiguous rows for one candidate/leg; they are not separate orders or trades.",
            "- The producer exposes only its latest confirmed swing pair; overlapping latent legs are not represented.",
            "- Timestamp keys inherit float64 subsecond precision limits and do not establish feed publication time.",
            "- No report-period rows, policy actions, checkpoint loads, environment steps, or economic outcomes are used.",
            "",
            "## Files",
            "",
            "- `swing_leg_eligibility_ledger.csv`: one row per timeframe/source-leg/direction projection.",
            "- `cross_timeframe_swing_leg_key_groups.csv`: exact source-time-key matches across timeframes.",
            "- `ledger.json`: input, config, source, scope, and count metadata.",
            "- `resolved_config.yaml`: resolved selected configuration.",
            "- `OUTPUT_SHA256SUMS`: output checksums.",
            "",
            "Reproduce on a compatible Triton allocation with the repository's active environment:",
            "",
            "```bash",
            ".venv/bin/python -m scripts.research.analysis.features.standard_deviation_swing_ledger",
            "```",
            "",
        ]
    )
    (output_dir / "README.md").write_text(readme, encoding="utf-8")
    _write_checksums(output_dir)
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    metadata = build_ledger(config_path, output_dir)
    totals = metadata["counts"]["totals"]
    print(
        "swing-leg ledger: "
        f"legs={totals['source_leg_projection_rows']} "
        f"eligible={totals['eligible_source_legs']} "
        f"cross_tf_groups={totals['tuple_groups_on_multiple_timeframes']} "
        f"output={output_dir}"
    )


if __name__ == "__main__":
    main()
