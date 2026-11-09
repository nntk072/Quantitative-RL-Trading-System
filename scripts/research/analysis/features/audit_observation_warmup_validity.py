#!/usr/bin/env python3
"""Measure non-finite warmup values in the configured policy observation streams.

This audit keeps the training split and model-facing column selection from the
configured pipeline. Higher-timeframe columns are sampled once at each visible
completed-candle boundary, using the environment's timeframe-start rule.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shlex
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from omegaconf import OmegaConf

from configuration.configuration_loader import load_config
from configuration.paths import repository_root
from features import attach_reachable_r, select_obs_columns
from features.context.policy_market import attach_policy_market_context
from features.pipeline.feature_matrix_builder import build_features
from market_data.loading.market_data_ingestion import run_pipeline
from market_data.loading.tick_book_pipeline import build_tick_books
from market_data.splits.definitions import make_train_mask
from simulation.environment.observations import split_obs_columns, timeframe_starts
from simulation.environment.trading_environment_factory import scheduled_session_closes

ROOT = repository_root(__file__)
DEFAULT_CONFIG = ROOT / "config/research/trade_setup_mtf_reasoning_2m.yaml"
DEFAULT_OUTPUT = ROOT / "evidence/research/feature_causality/observation_warmup_validity"
DEFAULT_CACHE = Path(
    "/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/observation_warmup_cache"
)
RAW_MANIFEST = (
    ROOT / "evidence/research/releases/negative-evidence-readiness/RAW_DATA_SHA256_MANIFEST.json"
)
SOURCE_PATHS = (
    "scripts/research/analysis/features/audit_observation_warmup_validity.py",
    "features/pipeline/feature_matrix_builder.py",
    "features/pipeline/feature_cache_identity.py",
    "features/pipeline/normalization.py",
    "features/pipeline/schema.py",
    "features/context/policy_market.py",
    "features/context/reachability.py",
    "simulation/environment/observations.py",
    "simulation/environment/observation_arrays_initialization.py",
    "simulation/environment/observation_runtime.py",
    "market_data/loading/market_data_ingestion.py",
    "market_data/loading/tick_book_pipeline.py",
)


def _sha256(path: Path) -> str:
    """Hash a file without loading it all into memory."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _source_hashes() -> dict[str, str]:
    """Record implementation identities for this measurement."""
    return {path: _sha256(ROOT / path) for path in SOURCE_PATHS}


def _training_mask(index: pd.DatetimeIndex, start: str, end: str) -> NDArray[np.bool_]:
    """Select configured training decision rows, inclusive of the end date."""
    return make_train_mask(index, end, start).to_numpy(dtype=bool)


def _column_rows(
    values: np.ndarray[Any, Any],
    index: pd.DatetimeIndex,
    training_mask: np.ndarray[Any, Any],
    timeframe: str,
    columns: np.ndarray[Any, Any],
    closes: dict[str, str],
    session_start: str,
) -> tuple[np.ndarray[Any, Any], int]:
    """Return rows sampled by the configured stream and its source-row count."""
    if timeframe == "M1":
        rows = np.flatnonzero(training_mask)
        return rows, int(rows.size)
    starts = timeframe_starts(index, timeframe, closes, session_start)
    starts = starts[training_mask[starts]] if starts.size else starts
    return starts, int(starts.size)


def _summarize_stream(
    values: np.ndarray[Any, Any],
    feature_names: list[str],
    rows: np.ndarray[Any, Any],
    timeframe: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Summarize finite, missing, leading-warmup, and zero-collision values."""
    output: list[dict[str, Any]] = []
    missing_cells = 0
    total_cells = int(rows.size * len(feature_names))
    columns_with_missing = 0
    columns_with_zero_collision = 0
    for local_index, name in enumerate(feature_names):
        column = values[rows, local_index].astype(np.float64, copy=False)
        finite = np.isfinite(column)
        missing = int((~finite).sum())
        leading = int(np.argmax(finite)) if finite.any() else int(finite.size)
        interior = int(missing - leading)
        finite_zeros = int((column[finite] == 0.0).sum())
        collision = bool(missing and finite_zeros)
        missing_cells += missing
        columns_with_missing += int(missing > 0)
        columns_with_zero_collision += int(collision)
        output.append(
            {
                "timeframe": timeframe,
                "feature": name,
                "sampled_rows": int(rows.size),
                "finite_rows": int(finite.sum()),
                "nonfinite_rows": missing,
                "nonfinite_fraction": float(missing / finite.size) if finite.size else None,
                "leading_nonfinite_rows": leading,
                "interior_nonfinite_rows": interior,
                "finite_zero_rows": finite_zeros,
                "missing_collides_with_finite_zero": collision,
            }
        )
    summary = {
        "timeframe": timeframe,
        "feature_count": len(feature_names),
        "sampled_rows": int(rows.size),
        "sampled_cells": total_cells,
        "nonfinite_cells": missing_cells,
        "nonfinite_fraction": float(missing_cells / total_cells) if total_cells else None,
        "features_with_nonfinite_values": columns_with_missing,
        "features_where_missing_collides_with_finite_zero": columns_with_zero_collision,
    }
    return output, summary


def build_audit(config_path: Path, output_dir: Path, cache_dir: Path) -> dict[str, Any]:
    """Build the configured training-only feature matrix and audit its model inputs."""
    cfg = load_config(config_path=str(config_path))
    regeneration_command = shlex.join(
        [
            ".venv/bin/python",
            str(Path(__file__).relative_to(ROOT)),
            "--config",
            str(config_path.relative_to(ROOT)),
            "--output-dir",
            str(output_dir),
            "--cache-dir",
            str(cache_dir),
        ]
    )
    return build_audit_from_config(
        cfg,
        config_label=str(config_path.relative_to(ROOT)),
        config_sha256=_sha256(config_path),
        output_dir=output_dir,
        cache_dir=cache_dir,
        regeneration_command=regeneration_command,
    )


def build_audit_from_config(
    cfg: Any,
    *,
    config_label: str,
    config_sha256: str,
    output_dir: Path,
    cache_dir: Path,
    regeneration_command: str,
) -> dict[str, Any]:
    """Audit a resolved runtime config without serializing it through YAML."""
    cfg.data.cache_dir = str(cache_dir)
    datasets = run_pipeline(cfg, datasets=["training"])
    primary_symbol = str(cfg.data.primary)
    secondary_symbol = str(cfg.data.secondary)
    primary_frames = datasets[primary_symbol]
    secondary_frames = datasets[secondary_symbol]
    bars = primary_frames["M1"]
    secondary = secondary_frames["M1"]
    index = pd.DatetimeIndex(bars.index)
    training_mask = _training_mask(
        index, str(cfg.data.split.train_start), str(cfg.data.split.train_end)
    )
    if not training_mask.any():
        raise ValueError("configured training interval contains no M1 rows")
    mask_series = pd.Series(training_mask, index=index, dtype=bool)

    features = build_features(
        bars,
        secondary=secondary,
        cfg=cfg,
        train_mask=mask_series,
        timeframe_bars=primary_frames,
        secondary_timeframe_bars=secondary_frames,
    )
    ticks = build_tick_books(cfg, symbols=[primary_symbol], datasets=["training"]).get(
        primary_symbol
    )
    schedule_path = Path(str(cfg.data.session_schedule_file))
    if not schedule_path.is_absolute():
        schedule_path = ROOT / schedule_path
    features = attach_policy_market_context(
        bars,
        features,
        ticks,
        schedule_path=schedule_path,
        session_start=str(cfg.session.start),
        session_end=str(cfg.session.end),
    )
    raw_columns = tuple(str(value) for value in cfg.strategy.get("raw_columns", []))
    observation_frame = attach_reachable_r(
        select_obs_columns(features, raw_columns),
        bars,
        features,
        include_validity_mask=bool(cfg.env.get("reachable_r_validity_mask", False)),
    )
    observation_values = observation_frame.to_numpy(dtype=np.float32, copy=True)
    names = [str(column) for column in observation_frame.columns]
    m1_columns, htf_columns = split_obs_columns(names)
    close_map = scheduled_session_closes(cfg)
    stream_rows: list[dict[str, Any]] = []
    stream_summaries: list[dict[str, Any]] = []
    stream_specs = [("M1", m1_columns)] + [
        (key.upper(), columns) for key, columns in htf_columns.items()
    ]
    for timeframe, column_indices in stream_specs:
        if column_indices.size == 0:
            continue
        feature_names = [names[int(position)] for position in column_indices]
        sampled_rows, source_rows = _column_rows(
            observation_values,
            index,
            training_mask,
            timeframe,
            column_indices,
            close_map,
            str(cfg.session.start),
        )
        selected_values = observation_values[np.ix_(sampled_rows, column_indices)]
        rows, summary = _summarize_stream(
            selected_values,
            feature_names,
            np.arange(len(sampled_rows), dtype=np.int64),
            timeframe,
        )
        summary["source_rows"] = source_rows
        stream_rows.extend(rows)
        stream_summaries.append(summary)

    output_dir.mkdir(parents=True, exist_ok=True)
    columns = [
        "timeframe",
        "feature",
        "sampled_rows",
        "finite_rows",
        "nonfinite_rows",
        "nonfinite_fraction",
        "leading_nonfinite_rows",
        "interior_nonfinite_rows",
        "finite_zero_rows",
        "missing_collides_with_finite_zero",
    ]
    with (output_dir / "column_warmup.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(stream_rows)

    summary = {
        "schema_version": 1,
        "status": "measured_training_split",
        "config_path": config_label,
        "config_sha256": config_sha256,
        "resolved_config_sha256": hashlib.sha256(
            OmegaConf.to_yaml(cfg, resolve=True).encode("utf-8")
        ).hexdigest(),
        "raw_data_manifest": str(RAW_MANIFEST.relative_to(ROOT)),
        "raw_data_manifest_sha256": _sha256(RAW_MANIFEST),
        "raw_input_scope": "Configured training dataset; run_pipeline and TickBook cache identities are content-derived.",
        "primary_symbol": primary_symbol,
        "secondary_symbol": secondary_symbol,
        "training_start": str(cfg.data.split.train_start),
        "training_end": str(cfg.data.split.train_end),
        "training_m1_rows": int(training_mask.sum()),
        "observation_feature_count": len(names),
        "mtf_enabled": str(cfg.agent.arch).startswith("mtf"),
        "stream_summaries": stream_summaries,
        "semantics": {
            "nonfinite_values": "remaining unavailable values after feature construction and normalization; the observation constructor converts them to zero",
            "zero_variance_normalization": "finite values in a fitted zero-variance window normalize to zero; missing fit statistics and missing source values remain nonfinite",
            "finite_zero_collision": "at least one nonfinite value and one genuine finite zero in the same stream feature",
            "htf_sampling": "one value row at each environment timeframe_starts boundary within the training split",
            "m1_sampling": "all configured training rows; the environment later clips sequence history to session rows",
        },
        "source_sha256": _source_hashes(),
        "limitations": [
            "This measures feature-level nonfinite and finite-zero overlap; it does not assign every missing value a semantic cause without producer-specific review.",
            "It is not a learned-policy or economic result.",
            "A missing value can be an intentional inactive event, source warmup, unavailable market context, or another producer-specific state.",
        ],
    }
    (output_dir / "warmup_validity_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "resolved_config.yaml").write_text(
        OmegaConf.to_yaml(cfg, resolve=True), encoding="utf-8"
    )
    readme = [
        "# Observation feature warmup and validity audit",
        "",
        "This packet measures non-finite values in the current configured model-facing feature columns over the local training split. M1 rows and higher-timeframe completed-candle boundaries are sampled from the same feature pipeline and timeframe-start rule used by the environment.",
        "",
        "`column_warmup.csv` reports each stream feature's sampled row count, finite/non-finite values, leading and interior missing counts, finite zero count, and whether a finite zero collides with missing values. Finite values in zero-variance normalization windows map to zero; unavailable source values and fit statistics remain nonfinite and are later zero-filled by observation construction. The report does not assign every missing value a cause without producer-specific review.",
        "",
        "This is input-contract evidence, not a learned-policy or economic result. The configured input manifest, resolved config, and source identities are recorded in `warmup_validity_summary.json`.",
        "",
        "## Regeneration",
        "",
        f"`{regeneration_command}`",
        "",
    ]
    (output_dir / "README.md").write_text("\n".join(readme), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    args = parser.parse_args(argv)
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    summary = build_audit(config_path.resolve(), output_dir.resolve(), args.cache_dir.resolve())
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
