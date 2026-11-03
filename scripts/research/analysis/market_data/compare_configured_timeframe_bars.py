#!/usr/bin/env python3
"""Compare configured native bars with M1-derived bars and report availability."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
from omegaconf import DictConfig, OmegaConf

from artifacts.atomic import write_json_atomic
from configuration import load_config
from configuration.paths import repository_root
from market_data.loading.bars import load_bars
from market_data.transforms.align import timeframe_close_times
from market_data.transforms.cleaning import clean
from market_data.transforms.resample import TF, resample
from market_data.transforms.session_schedule import scheduled_session_close_map

ROOT = repository_root(__file__)
TIMEFRAMES = ("M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
RULES = {
    "M3": "3min",
    "M5": "5min",
    "M10": "10min",
    "M15": "15min",
    "M30": "30min",
    "H1": "1h",
    "H4": "4h",
    "D1": "1D",
}
OHLCV_COLUMNS = ("open", "high", "low", "close", "tickvol", "vol")
DEFAULT_OUTPUT = (
    ROOT / "evidence/research/releases/negative-evidence-readiness/configured_timeframe_parity.json"
)


def sha256_file(path: Path) -> str:
    """Hash one input file in bounded memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compare_bar_frames(
    native: pd.DataFrame,
    derived: pd.DataFrame,
    columns: tuple[str, ...] = OHLCV_COLUMNS,
) -> dict[str, Any]:
    """Compare row identity and declared numeric fields without hiding gaps."""
    missing_native = derived.index.difference(native.index)
    extra_native = native.index.difference(derived.index)
    common = native.index.intersection(derived.index).sort_values()
    fields: dict[str, Any] = {}
    missing_columns = [
        column
        for column in columns
        if column not in native.columns or column not in derived.columns
    ]
    for column in columns:
        if column not in native.columns or column not in derived.columns:
            continue
        left = pd.to_numeric(native.loc[common, column], errors="coerce").to_numpy(dtype=np.float64)
        right = pd.to_numeric(derived.loc[common, column], errors="coerce").to_numpy(
            dtype=np.float64
        )
        both_nan = np.isnan(left) & np.isnan(right)
        finite = np.isfinite(left) & np.isfinite(right)
        equal = both_nan | (finite & np.isclose(left, right, rtol=1e-10, atol=1e-10))
        mismatch_positions = np.flatnonzero(~equal)
        delta = np.abs(left[finite] - right[finite])
        fields[column] = {
            "compared_rows": int(len(common)),
            "mismatch_rows": int(len(mismatch_positions)),
            "max_abs_delta": float(delta.max(initial=0.0)),
            "first_mismatch_time": (
                pd.Timestamp(common[int(mismatch_positions[0])]).isoformat()
                if len(mismatch_positions)
                else None
            ),
        }
    return {
        "native_rows": int(len(native)),
        "m1_derived_rows": int(len(derived)),
        "native_first_timestamp": (
            pd.Timestamp(native.index[0]).isoformat() if len(native.index) else None
        ),
        "native_last_timestamp": (
            pd.Timestamp(native.index[-1]).isoformat() if len(native.index) else None
        ),
        "m1_derived_first_timestamp": (
            pd.Timestamp(derived.index[0]).isoformat() if len(derived.index) else None
        ),
        "m1_derived_last_timestamp": (
            pd.Timestamp(derived.index[-1]).isoformat() if len(derived.index) else None
        ),
        "common_timestamp_rows": int(len(common)),
        "derived_timestamps_missing_native": int(len(missing_native)),
        "native_timestamps_missing_derived": int(len(extra_native)),
        "first_derived_timestamp_missing_native": (
            pd.Timestamp(missing_native[0]).isoformat() if len(missing_native) else None
        ),
        "first_native_timestamp_missing_derived": (
            pd.Timestamp(extra_native[0]).isoformat() if len(extra_native) else None
        ),
        "missing_comparison_columns": missing_columns,
        "field_comparisons": fields,
    }


def compare_spread_aggregations(
    native: pd.DataFrame, m1: pd.DataFrame, timeframe: str
) -> dict[str, Any]:
    """Compare native spread with M1 mean and last-value aggregation separately."""
    if "spread" not in native.columns or "spread" not in m1.columns:
        return {
            "status": "missing_spread_source",
            "m1_mean_vs_native": None,
            "m1_last_vs_native": None,
        }

    rule = RULES[timeframe]
    m1_spread = m1[["spread"]]
    mean_spread = m1_spread.resample(rule, label="left", closed="left").mean().dropna()
    last_spread = m1_spread.resample(rule, label="left", closed="left").last().dropna()
    mean_result = compare_bar_frames(native, mean_spread, columns=("spread",))
    last_result = compare_bar_frames(native, last_spread, columns=("spread",))
    mean_mismatches = mean_result["field_comparisons"]["spread"]["mismatch_rows"]
    last_mismatches = last_result["field_comparisons"]["spread"]["mismatch_rows"]
    if mean_mismatches == 0 and last_mismatches == 0:
        status = "matches_m1_mean_and_last"
    elif mean_mismatches == 0:
        status = "matches_m1_mean"
    elif last_mismatches == 0:
        status = "matches_m1_last"
    else:
        status = "differs_from_m1_mean_and_last"
    return {
        "status": status,
        "m1_mean_vs_native": mean_result["field_comparisons"].get("spread"),
        "m1_last_vs_native": last_result["field_comparisons"].get("spread"),
        "interpretation_limit": (
            "The comparisons describe observed aggregation behavior; they do not establish "
            "provider semantics for the native spread field."
        ),
    }


def availability_summary(
    m1: pd.DataFrame,
    timeframe_bars: pd.DataFrame,
    timeframe: str,
    scheduled_closes: dict[str, str],
    session_start: str,
) -> dict[str, Any]:
    """Measure the first M1 timestamp at or after each higher-bar close."""
    close_times = timeframe_close_times(
        timeframe_bars,
        timeframe,
        scheduled_closes=scheduled_closes,
        session_start=session_start,
    )
    m1_ns = np.asarray(pd.DatetimeIndex(m1.index), dtype="datetime64[ns]").view(np.int64)
    close_ns = np.asarray(pd.DatetimeIndex(close_times), dtype="datetime64[ns]").view(np.int64)
    positions = np.searchsorted(m1_ns, close_ns, side="left")
    available = positions < len(m1_ns)
    lags = np.full(len(close_ns), np.nan, dtype=np.float64)
    if available.any():
        lags[available] = (m1_ns[positions[available]] - close_ns[available]) / 1e9
    valid_lags = lags[np.isfinite(lags)]
    return {
        "higher_timeframe_rows": int(len(close_ns)),
        "rows_without_later_m1_bar": int((~available).sum()),
        "rows_first_visible_exactly_at_close": int((valid_lags == 0).sum()),
        "rows_first_visible_after_close": int((valid_lags > 0).sum()),
        "max_first_m1_delay_seconds": (
            float(valid_lags.max(initial=0.0)) if len(valid_lags) else None
        ),
        "first_m1_delay_seconds_quantiles": {
            "p50": float(np.quantile(valid_lags, 0.50)) if len(valid_lags) else None,
            "p90": float(np.quantile(valid_lags, 0.90)) if len(valid_lags) else None,
            "p99": float(np.quantile(valid_lags, 0.99)) if len(valid_lags) else None,
        },
    }


def source_row_coverage_summary(
    m1: pd.DataFrame,
    timeframe_bars: pd.DataFrame,
    timeframe: str,
    scheduled_closes: dict[str, str],
    session_start: str,
) -> dict[str, Any]:
    """Compare observed M1 rows in each HTF interval with its nominal minute grid."""
    close_times = timeframe_close_times(
        timeframe_bars,
        timeframe,
        scheduled_closes=scheduled_closes,
        session_start=session_start,
    )
    open_index = pd.DatetimeIndex(timeframe_bars.index)
    close_index = pd.DatetimeIndex(close_times)
    opens_ns = np.fromiter(
        (timestamp.value for timestamp in open_index), dtype=np.int64, count=len(open_index)
    )
    closes_ns = np.fromiter(
        (timestamp.value for timestamp in close_index), dtype=np.int64, count=len(close_index)
    )
    expected = np.maximum(0, np.ceil((closes_ns - opens_ns) / 60_000_000_000)).astype(np.int64)
    observed = (
        m1.resample(RULES[timeframe], label="left", closed="left")
        .size()
        .reindex(timeframe_bars.index, fill_value=0)
        .to_numpy(dtype=np.int64)
    )
    short = observed < expected
    over = observed > expected
    ratios = np.divide(
        observed,
        expected,
        out=np.zeros(len(observed), dtype=np.float64),
        where=expected > 0,
    )
    incomplete = np.flatnonzero(short)
    return {
        "interpretation": (
            "Observed source rows are compared with the nominal one-minute grid inside each "
            "calculated bar interval, clipped by configured session close where applicable. "
            "Incomplete coverage is descriptive and is not classified as data loss because "
            "market closures and instrument schedules are not authoritatively known."
        ),
        "bars": int(len(observed)),
        "expected_m1_grid_rows": int(expected.sum()),
        "observed_m1_rows": int(observed.sum()),
        "bars_with_fewer_rows_than_grid": int(short.sum()),
        "bars_with_more_rows_than_grid": int(over.sum()),
        "bars_with_zero_observed_rows": int((observed == 0).sum()),
        "first_incomplete_bar_timestamp": (
            pd.Timestamp(timeframe_bars.index[int(incomplete[0])]).isoformat()
            if len(incomplete)
            else None
        ),
        "observed_rows_per_bar": {
            "minimum": int(observed.min()) if len(observed) else 0,
            "median": float(np.median(observed)) if len(observed) else 0.0,
            "maximum": int(observed.max()) if len(observed) else 0,
        },
        "expected_rows_per_bar": {
            "minimum": int(expected.min()) if len(expected) else 0,
            "median": float(np.median(expected)) if len(expected) else 0.0,
            "maximum": int(expected.max()) if len(expected) else 0,
        },
        "observed_to_expected_ratio": {
            "minimum": float(ratios.min()) if len(ratios) else 0.0,
            "median": float(np.median(ratios)) if len(ratios) else 0.0,
            "maximum": float(ratios.max()) if len(ratios) else 0.0,
        },
    }


def configured_path(root: Path, raw_dir: str, filename: str) -> Path:
    """Resolve one configured relative market-input path."""
    path = (root / raw_dir / filename).resolve()
    path.relative_to(root.resolve())
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def audit_dataset(
    cfg: DictConfig,
    root: Path,
    dataset_name: str,
    dataset: DictConfig,
) -> list[dict[str, Any]]:
    """Audit each configured symbol/timeframe in one split export."""
    raw_dir = str(dataset.raw_dir)
    m1_files = dataset.get("m1_files", {})
    timeframe_files = dataset.get("timeframe_files", {})
    derived_by_symbol = cfg.data.get("derived_timeframes", {})
    scheduled_closes = scheduled_session_close_map(cfg)
    session_start = str(OmegaConf.select(cfg, "session.start", default="16:30"))
    results: list[dict[str, Any]] = []

    for symbol in cfg.data.symbols:
        m1_path = configured_path(root, raw_dir, str(m1_files[str(symbol)]))
        m1 = clean(load_bars(m1_path), tz=str(cfg.data.tz))
        derived_timeframes = {
            str(value).upper() for value in derived_by_symbol.get(str(symbol), [])
        }
        for timeframe in TIMEFRAMES:
            native_name = timeframe_files.get(timeframe, {}).get(str(symbol))
            if native_name:
                native_path = configured_path(root, raw_dir, str(native_name))
                native = clean(load_bars(native_path), tz=str(cfg.data.tz))
                origin = "native"
                source_paths = {"m1": m1_path, "timeframe": native_path}
                comparison = compare_bar_frames(native, resample(m1, cast(TF, timeframe)))
                spread_comparison = compare_spread_aggregations(native, m1, timeframe)
            else:
                native_path = None
                if timeframe not in derived_timeframes:
                    results.append(
                        {
                            "dataset": dataset_name,
                            "symbol": str(symbol),
                            "timeframe": timeframe,
                            "origin": "missing_configuration",
                            "status": "blocked",
                        }
                    )
                    continue
                native = resample(m1, cast(TF, timeframe))
                origin = "derived_from_m1"
                source_paths = {"m1": m1_path}
                comparison = {
                    "native_rows": None,
                    "m1_derived_rows": int(len(native)),
                    "common_timestamp_rows": None,
                    "derived_timestamps_missing_native": None,
                    "native_timestamps_missing_derived": None,
                    "field_comparisons": {},
                }
                spread_comparison = {
                    "status": "not_applicable_derived_from_m1",
                    "m1_mean_vs_native": None,
                    "m1_last_vs_native": None,
                }

            counts = m1.resample(RULES[timeframe], label="left", closed="left").size()
            m1_counts = counts.reindex(native.index, fill_value=0)
            result = {
                "dataset": dataset_name,
                "period_role": (
                    "development_training" if dataset_name == "training" else "exposed_report_only"
                ),
                "symbol": str(symbol),
                "timeframe": timeframe,
                "origin": origin,
                "source_paths": {
                    key: value.relative_to(root).as_posix() for key, value in source_paths.items()
                },
                "source_sha256": {key: sha256_file(value) for key, value in source_paths.items()},
                "m1_rows": int(len(m1)),
                "m1_first_timestamp": pd.Timestamp(m1.index[0]).isoformat(),
                "m1_last_timestamp": pd.Timestamp(m1.index[-1]).isoformat(),
                "m1_observed_rows_per_bar": {
                    "minimum": int(m1_counts.min()) if len(m1_counts) else 0,
                    "median": float(m1_counts.median()) if len(m1_counts) else 0.0,
                    "maximum": int(m1_counts.max()) if len(m1_counts) else 0,
                },
                "availability": availability_summary(
                    m1, native, timeframe, scheduled_closes, session_start
                ),
                "source_row_coverage": source_row_coverage_summary(
                    m1, native, timeframe, scheduled_closes, session_start
                ),
                "spread_aggregation_comparison": spread_comparison,
                **comparison,
            }
            if origin == "native":
                result["timeframe_source_sha256"] = result["source_sha256"]["timeframe"]
            result["status"] = (
                "derived_only"
                if origin == "derived_from_m1"
                else "exact_timestamp_and_ohlcv_parity"
                if comparison["derived_timestamps_missing_native"] == 0
                and comparison["native_timestamps_missing_derived"] == 0
                and not comparison["missing_comparison_columns"]
                and all(
                    value["mismatch_rows"] == 0
                    for value in comparison["field_comparisons"].values()
                )
                else "timestamp_or_ohlcv_differences_observed"
            )
            results.append(result)
    return results


def build_report(
    root: Path = ROOT,
    *,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Load configured local splits and compare all supplied timeframes."""
    selected_config = config_path or root / "config/base/default.yaml"
    if not selected_config.is_absolute():
        selected_config = root / selected_config
    cfg = load_config(config_path=selected_config)
    dataset_cfg = cfg.data.get("datasets")
    if not dataset_cfg:
        raise ValueError("configured timeframe parity requires data.datasets")
    outputs = []
    for dataset_name in ("training", "testing"):
        dataset = dataset_cfg.get(dataset_name)
        if dataset is None:
            raise ValueError(f"configured dataset split is missing: {dataset_name}")
        outputs.extend(audit_dataset(cfg, root, dataset_name, dataset))
    schedule_value = OmegaConf.select(cfg, "data.session_schedule_file")
    schedule_path = Path(str(schedule_value)).expanduser() if schedule_value else None
    if schedule_path is not None and not schedule_path.is_absolute():
        schedule_path = root / schedule_path
    script_path = Path(__file__).resolve()
    try:
        display_config_path = selected_config.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        display_config_path = str(selected_config.resolve())
    return {
        "schema_version": 1,
        "audit_id": "configured_timeframe_parity",
        "config_path": display_config_path,
        "config_sha256": sha256_file(selected_config),
        "audit_script_path": script_path.relative_to(root).as_posix(),
        "audit_script_sha256": sha256_file(script_path),
        "timestamp_clock_model": str(cfg.data.timestamp_clock),
        "data_timezone_carrier": str(cfg.data.tz),
        "bar_timestamp_convention": str(cfg.data.bar_timestamp_convention),
        "session_schedule_path": (
            schedule_path.resolve().relative_to(root.resolve()).as_posix()
            if schedule_path is not None
            else None
        ),
        "session_schedule_sha256": (
            sha256_file(schedule_path.resolve())
            if schedule_path is not None and schedule_path.is_file()
            else None
        ),
        "calendar_limit": (
            "Configured schedule closes are applied to availability summaries. "
            "This audit does not establish that the schedule is authoritative or "
            "classify missing market bars as data loss."
        ),
        "m1_derived_aggregation": {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "tickvol": "sum",
            "vol": "sum",
            "spread": "mean",
            "spread_note": (
                "Native spread is separately compared with M1 mean and last-value "
                "aggregations; no provider meaning is inferred."
            ),
            "incomplete_source_bin_policy": (
                "A nonempty partial M1 bin is retained. Its HTF value becomes available at the "
                "nominal close or configured session close, whichever is earlier, and is first "
                "joined to an observed M1 row at or after that boundary."
            ),
        },
        "timeframes": outputs,
    }


def main() -> int:
    """Write a machine-readable local parity and first-availability report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/base/default.yaml")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.out if args.out.is_absolute() else ROOT / args.out
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    report = build_report(config_path=config_path)
    write_json_atomic(output, report, default=None)
    print(json.dumps({"report": str(output), "rows": len(report["timeframes"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
