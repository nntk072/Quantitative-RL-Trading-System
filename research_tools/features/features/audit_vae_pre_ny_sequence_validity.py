#!/usr/bin/env python3
"""Measure missing-bar and padding semantics in the VAE pre-NY input path."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from learning.self_supervised.vae_pre_ny import build_pre_ny_by_date
from market_data.loading.bars import load_bars
from market_data.transforms.resample import resample

_START = time(1, 5)
_END = time(16, 29)
_EXPECTED_LAST_M5 = time(16, 25)
_OHLCV = ("open", "high", "low", "close", "volume")
_SOURCE_PATHS = (
    "learning/self_supervised/vae_pre_ny.py",
    "market_data/loading/bars.py",
    "market_data/transforms/resample.py",
    "models/auxiliary/vae.py",
    "learning/rl/vae_extractor.py",
    "training/runner/vae.py",
    "training/runner/data_stage.py",
    "config/experiments.yaml",
    "config/vae.yaml",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_input(bars: pd.DataFrame) -> pd.DataFrame:
    work = bars.copy()
    if "volume" not in work.columns:
        work["volume"] = work["tickvol"] if "tickvol" in work.columns else 0.0
    return work.loc[:, [name for name in _OHLCV if name in work.columns]]


def audit(
    input_path: Path,
    config_path: Path,
    start_date: date,
    end_date: date,
    repo_root: Path,
) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    seq_len = int(config["seq_len"])
    n_features = int(config["n_features"])
    bars = load_bars(input_path)
    bars_index = pd.DatetimeIndex(bars.index)
    date_mask = np.asarray((bars_index.date >= start_date) & (bars_index.date <= end_date))
    bars = bars.loc[date_mask]
    bars_index = pd.DatetimeIndex(bars.index)
    work = _normalized_input(bars)
    m5 = resample(work, "M5")
    m5_index = pd.DatetimeIndex(m5.index)
    sequences = build_pre_ny_by_date(bars, seq_len=seq_len, n_features=n_features)
    dataset_path = Path(config["data_path"])
    if not dataset_path.is_absolute():
        dataset_path = repo_root / dataset_path
    dataset_report: dict[str, Any]
    if dataset_path.is_file():
        dataset = np.load(dataset_path, mmap_mode="r", allow_pickle=False)
        if dataset.ndim != 3:
            dataset_report = {
                "path": str(dataset_path),
                "sha256": _sha256(dataset_path),
                "shape": list(dataset.shape),
                "dtype": str(dataset.dtype),
                "valid_shape": False,
            }
        else:
            finite = np.isfinite(dataset)
            zero_rows = np.all(dataset == 0.0, axis=2)
            leading_zero_rows = []
            for sequence_zero_rows in zero_rows:
                nonzero = np.flatnonzero(~sequence_zero_rows)
                leading_zero_rows.append(int(nonzero[0]) if nonzero.size else int(dataset.shape[1]))
            dataset_report = {
                "path": str(dataset_path),
                "sha256": _sha256(dataset_path),
                "shape": list(dataset.shape),
                "dtype": str(dataset.dtype),
                "valid_shape": bool(dataset.shape[1:] == (seq_len, n_features)),
                "finite_values": int(finite.sum()),
                "nonfinite_values": int(finite.size - finite.sum()),
                "all_zero_rows": int(zero_rows.sum()),
                "sequences_with_leading_zero_rows": int(
                    sum(count > 0 for count in leading_zero_rows)
                ),
                "total_leading_zero_rows": int(sum(leading_zero_rows)),
                "max_leading_zero_rows": max(leading_zero_rows, default=0),
                "zero_fraction_by_feature": [
                    float(np.mean(dataset[:, :, feature] == 0.0))
                    for feature in range(dataset.shape[2])
                ],
                "has_date_or_session_identity": False,
                "aligned_to_current_m1_audit": False,
            }
    else:
        dataset_report = {
            "path": str(dataset_path),
            "exists": False,
            "aligned_to_current_m1_audit": False,
        }

    observed_days = sorted({stamp.date() for stamp in bars_index})
    daily_rows: list[dict[str, Any]] = []
    for day in observed_days:
        expected_m5 = pd.date_range(
            pd.Timestamp.combine(day, _START),
            pd.Timestamp.combine(day, _EXPECTED_LAST_M5),
            freq="5min",
        )
        day_m5_mask = np.asarray(m5_index.date == day)
        day_m5 = m5.loc[day_m5_mask]
        day_m5_index = pd.DatetimeIndex(day_m5.index)
        time_mask = np.asarray((day_m5_index.time >= _START) & (day_m5_index.time <= _END))
        selected = day_m5.loc[time_mask]
        actual_labels = pd.DatetimeIndex(selected.index)
        present = expected_m5.intersection(actual_labels)

        date_mask = np.asarray(bars_index.date == day)
        duplicate_m1_rows = int(bars_index[date_mask].duplicated(keep=False).sum())
        day_bars = bars.loc[date_mask]
        day_bars_index = pd.DatetimeIndex(day_bars.index)
        day_counts = day_bars.groupby(level=0).size()
        day_counts.index = pd.DatetimeIndex(day_counts.index)
        input_columns = [
            name for name in ("open", "high", "low", "close", "tickvol") if name in day_bars
        ]
        day_nonfinite = (
            pd.Series(
                (~np.isfinite(day_bars[input_columns].to_numpy(dtype=float))).any(axis=1),
                index=day_bars.index,
            )
            .groupby(level=0)
            .sum()
        )
        expected_minutes = pd.date_range(expected_m5[0], periods=len(expected_m5) * 5, freq="1min")
        minute_counts = day_counts.reindex(expected_minutes, fill_value=0)
        minute_index = pd.DatetimeIndex(minute_counts.index)
        bin_counts = minute_counts.groupby(minute_index.floor("5min")).sum()
        expected_m1_count = int(len(expected_minutes))
        observed_m1_count = int(minute_counts.sum())
        incomplete_m1_bins = int((bin_counts != 5).sum())
        nonfinite_m1_rows = int(day_nonfinite.reindex(expected_minutes, fill_value=0).sum())
        pre_ny_time_mask = np.asarray(
            (day_bars_index.time >= _START) & (day_bars_index.time <= _END)
        )

        seq = sequences.get(day)
        if seq is None:
            padded_prefix_rows = None
            sequence_nonfinite_values = None
            sequence_all_zero_rows = None
        else:
            # The production builder right-aligns the most recent values and pads
            # the left with exact zero rows when fewer than seq_len rows exist.
            used_rows = min(len(selected), seq_len)
            padded_prefix_rows = seq_len - used_rows
            sequence_nonfinite_values = int((~np.isfinite(seq)).sum())
            sequence_all_zero_rows = int(np.all(seq == 0.0, axis=1).sum())

        daily_rows.append(
            {
                "date": day.isoformat(),
                "m1_rows_in_pre_ny_window": int(pre_ny_time_mask.sum()),
                "expected_m1_rows": expected_m1_count,
                "observed_expected_m1_rows": observed_m1_count,
                "incomplete_m5_bins_by_m1_coverage": incomplete_m1_bins,
                "nonfinite_m1_rows_in_expected_bins": nonfinite_m1_rows,
                "duplicate_m1_rows_for_date": duplicate_m1_rows,
                "expected_m5_rows": int(len(expected_m5)),
                "observed_m5_rows": int(len(actual_labels)),
                "expected_m5_labels_present": int(len(present)),
                "expected_m5_labels_missing": int(len(expected_m5.difference(actual_labels))),
                "unexpected_m5_labels_in_window": int(len(actual_labels.difference(expected_m5))),
                "production_sequence_present": seq is not None,
                "production_sequence_rows": None if seq is None else int(len(seq)),
                "production_sequence_padded_prefix_rows": padded_prefix_rows,
                "production_sequence_nonfinite_values": sequence_nonfinite_values,
                "production_sequence_all_zero_rows": sequence_all_zero_rows,
            }
        )

    summary = {
        "observed_calendar_days": len(observed_days),
        "production_sequences": sum(row["production_sequence_present"] for row in daily_rows),
        "days_with_any_missing_expected_m1": sum(
            row["observed_expected_m1_rows"] < row["expected_m1_rows"] for row in daily_rows
        ),
        "days_with_incomplete_m5_bins": sum(
            row["incomplete_m5_bins_by_m1_coverage"] > 0 for row in daily_rows
        ),
        "days_with_missing_expected_m5_labels": sum(
            row["expected_m5_labels_missing"] > 0 for row in daily_rows
        ),
        "days_with_duplicate_m1_rows": sum(
            row["duplicate_m1_rows_for_date"] > 0 for row in daily_rows
        ),
        "days_with_nonfinite_m1_rows": sum(
            row["nonfinite_m1_rows_in_expected_bins"] > 0 for row in daily_rows
        ),
        "total_missing_expected_m1_rows": sum(
            row["expected_m1_rows"] - row["observed_expected_m1_rows"] for row in daily_rows
        ),
        "total_missing_expected_m5_labels": sum(
            row["expected_m5_labels_missing"] for row in daily_rows
        ),
        "total_production_padding_rows": sum(
            row["production_sequence_padded_prefix_rows"] or 0 for row in daily_rows
        ),
        "days_with_production_padding": sum(
            (row["production_sequence_padded_prefix_rows"] or 0) > 0 for row in daily_rows
        ),
        "days_with_nonfinite_production_sequence": sum(
            (row["production_sequence_nonfinite_values"] or 0) > 0 for row in daily_rows
        ),
    }
    return {
        "schema": "vae-pre-ny-sequence-validity-v1",
        "scope": {
            "input": str(input_path),
            "config": str(config_path),
            "start_date_inclusive": start_date.isoformat(),
            "end_date_inclusive": end_date.isoformat(),
            "window_start_inclusive": _START.isoformat(),
            "window_end_inclusive": _END.isoformat(),
            "expected_m5_labels_start": _START.isoformat(),
            "expected_m5_labels_end": _EXPECTED_LAST_M5.isoformat(),
            "source_timezone_interpretation": "Use timestamps and local wall-clock labels as supplied; no external calendar or timezone authority is asserted.",
            "claim_limit": "Describes input completeness, resampled rows, normalization output, and fixed-shape padding only. It does not measure learned VAE quality or policy value.",
        },
        "input": {
            "sha256": _sha256(input_path),
            "rows_in_date_scope": int(len(bars)),
            "start": None if bars.empty else bars.index.min().isoformat(),
            "end": None if bars.empty else bars.index.max().isoformat(),
            "duplicate_timestamps": int(bars.index.duplicated(keep=False).sum()),
        },
        "config": {
            "sha256": _sha256(config_path),
            "seq_len": seq_len,
            "n_features": n_features,
        },
        "training_dataset": dataset_report,
        "training_contract": {
            "partitioning": "training/runner/vae.py::prepare_data uses random_split at 70/15/15 without a date key or explicit generator.",
            "reconstruction_loss": "training/runner/vae.py::VAELoss uses summed MSE over every timestep and feature; there is no validity-mask argument.",
            "runtime_input": "training/runner/data_stage.py builds pre_ny_by_date from current primary M1 bars only when --use-vae is supplied; the separate training command consumes config/vae.yaml data_path.",
            "candidate_registration": "config/experiments.yaml registers ablation_conditional_narrative with use_vae=1; this audit does not assert that a checkpoint exists or was used in a run.",
            "implication": "Current training data lack date/session identity and contain leading all-zero rows; random splitting and unmasked reconstruction do not establish chronological train-only fitting or distinguish padded rows from valid zero-valued inputs.",
        },
        "source_hashes": {
            relpath: _sha256(repo_root / relpath)
            for relpath in (
                *_SOURCE_PATHS,
                "scripts/research/analysis/features/audit_vae_pre_ny_sequence_validity.py",
            )
        },
        "summary": summary,
        "days": daily_rows,
        "disposition": {
            "fixed_shape_padding_is_masked_in_current_vae_loss": False,
            "validity_channel_is_present_in_current_vae_input": False,
            "policy_use_authorized_by_this_audit": False,
            "reason": "The current VAE input and reconstruction loss have no per-timestep validity mask; measured padding or missing source bars therefore cannot be distinguished from valid values by this audit.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Current local M1 bar CSV")
    parser.add_argument("--config", type=Path, default=Path("config/vae.yaml"))
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True, help="JSON output path")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    if args.end_date < args.start_date:
        parser.error("--end-date must be on or after --start-date")
    report = audit(args.input, args.config, args.start_date, args.end_date, args.repo_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": report["summary"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
