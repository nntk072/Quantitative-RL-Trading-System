#!/usr/bin/env python3
"""Measure training-only availability of source-zone geometry by setup candidate.

This is a feature-support audit. It does not propose entries, stops, targets,
order lifetimes, orders, fills, returns, or policy actions.
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
from scripts.research.analysis.features.training_context import (
    DEFAULT_CONFIG,
    TIMEFRAMES,
    candidate_supported,
    training_slice,
)

from configuration.configuration_loader import load_config
from configuration.paths import repository_root
from decisioning.trade_setup import NO_TRADE_ID, TRADE_SETUP_CANDIDATES
from features import build_features
from features.context.trade_setup_candidates import trade_setup_candidate_feature_columns
from features.technical.indicators import atr as calculate_atr
from market_data.loading.market_data_ingestion import run_pipeline

ROOT = repository_root(__file__)
DEFAULT_OUTPUT = ROOT / "evidence/research/candidate_geometry_support"
_ZONE_FAMILIES = {
    "order_block": ("ob",),
    "standard_deviation": (),
    "fvg_retest": ("fvg",),
    "ifvg_retest": ("ifvg",),
    "ifvg_unretested": ("ifvg",),
}
_PO3_TIMEFRAME_CODES = (1, 3, 5, 10, 15, 30, 60, 240, 1440)
GEOMETRY_SUPPORT_SCHEMA_VERSION = "candidate-price-geometry-support-v3"


def _active_mask(features: pd.DataFrame, candidate_id: int) -> tuple[pd.Series, str | None]:
    """Return the candidate's finite active rows and their source column."""
    column = dict(trade_setup_candidate_feature_columns()).get(candidate_id)
    if column is None or column not in features.columns:
        return pd.Series(False, index=features.index), column
    values = pd.to_numeric(features[column], errors="coerce")
    return values.notna() & np.isfinite(values) & values.gt(0.0), column


def _geometry_specs(candidate: Any) -> list[tuple[str, str | None, str, str]]:
    """Map a candidate to source-zone or retracement-band fields."""
    timeframe = str(candidate.setup_timeframe).upper()
    if candidate.idea == "standard_deviation":
        prefix = "" if timeframe == "M1" else f"{timeframe}_"
        return [
            (
                "standard_deviation_band",
                None,
                f"{prefix}standard_deviation_band_low",
                f"{prefix}standard_deviation_band_high",
            )
        ]
    if candidate.idea == "po3":
        po3_specs: list[tuple[str, str | None, str, str]] = [
            ("po3_ifvg", None, "po3_ifvg_low", "po3_ifvg_high")
        ]
        side = "bull" if int(candidate.direction) > 0 else "bear"
        for timeframe in TIMEFRAMES:
            for family in ("fvg", "ifvg"):
                prefix = "" if timeframe == "M1" and family == "ifvg" else f"{timeframe}_"
                stem = f"{family}_{side}"
                po3_specs.append(
                    (
                        f"po3:{timeframe}:{family}",
                        f"{prefix}{stem}_active",
                        f"{prefix}{stem}_low",
                        f"{prefix}{stem}_high",
                    )
                )
        return po3_specs
    families = _ZONE_FAMILIES.get(str(candidate.idea), ())
    source_side = "bull" if int(candidate.direction) > 0 else "bear"
    specs: list[tuple[str, str | None, str, str]] = []
    for family in families:
        prefix = "" if timeframe == "M1" and family in {"ob", "ifvg"} else f"{timeframe}_"
        stem = f"{family}_{source_side}"
        specs.append(
            (
                family,
                f"{prefix}{stem}_active",
                f"{prefix}{stem}_low",
                f"{prefix}{stem}_high",
            )
        )
    return specs


def _positive_feature(features: pd.DataFrame, column: str) -> np.ndarray[Any, Any]:
    """Return a finite-positive mask for one optional feature column."""
    if column not in features.columns:
        return np.zeros(len(features), dtype=bool)
    values = pd.to_numeric(features[column], errors="coerce").to_numpy(dtype=float)
    return cast(np.ndarray[Any, Any], np.isfinite(values) & (values > 0.0))


def _sha256_file(path: Path) -> str:
    """Hash a local input in bounded memory blocks."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _po3_timeframe_rows(
    features: pd.DataFrame, timeframe: str, direction: int
) -> np.ndarray[Any, Any]:
    """Mirror the active PO3 source-timeframe selection used by entry context."""
    prefix = "" if timeframe == "M1" else f"{timeframe}_"
    direction_column = f"{prefix}po3_distribution_direction"
    source_side = "bull" if direction > 0 else "bear"
    gap_column = f"{prefix}ifvg_{source_side}_active"
    direction_mask = np.zeros(len(features), dtype=bool)
    if direction_column in features.columns:
        values = pd.to_numeric(features[direction_column], errors="coerce").to_numpy(dtype=float)
        direction_mask = np.isfinite(values) & (values * direction > 0.0)
    return cast(np.ndarray[Any, Any], direction_mask | _positive_feature(features, gap_column))


def _candidate_geometry_summary(
    features: pd.DataFrame,
    candidate: Any,
    *,
    configured_support: bool,
) -> dict[str, Any]:
    """Summarize active bounds in price units and relative to close and ATR."""
    candidate_id = int(candidate.candidate_id)
    if candidate_id == NO_TRADE_ID:
        return {
            "candidate_id": candidate_id,
            "idea": "no_trade",
            "timeframe": "",
            "direction": 0,
            "configured_support": True,
            "active_training_rows": int(len(features)),
            "geometry_kind": "not_applicable",
            "geometry_contract": "not_applicable",
            "rows_with_valid_geometry": None,
            "rows_with_invalid_geometry_bounds": 0,
            "geometry_coverage_fraction": None,
            "median_geometry_width": None,
            "p95_geometry_width": None,
            "rows_with_atr_normalized_geometry": None,
            "atr_normalized_geometry_coverage_fraction": None,
            "median_geometry_width_atr": None,
            "p95_geometry_width_atr": None,
            "fraction_price_inside_geometry": None,
            "median_distance_to_geometry_atr": None,
            "p95_distance_to_geometry_atr": None,
        }

    active, _active_column = _active_mask(features, candidate_id)
    active_values = active.to_numpy(dtype=bool)
    reference_close = (
        pd.to_numeric(features["close"], errors="coerce").to_numpy(dtype=float)
        if "close" in features
        else None
    )
    atr = (
        pd.to_numeric(features["atr"], errors="coerce").to_numpy(dtype=float)
        if "atr" in features
        else None
    )
    geometry_counts = np.zeros(len(features), dtype=np.int16)
    invalid_counts = np.zeros(len(features), dtype=np.int16)
    widths: list[np.ndarray[Any, Any]] = []
    normalized_widths: list[np.ndarray[Any, Any]] = []
    normalized_distances: list[np.ndarray[Any, Any]] = []
    normalized_inside: list[np.ndarray[Any, Any]] = []
    normalized_rows = np.zeros(len(features), dtype=bool)
    found_contract = False
    special_zone_valid = np.zeros(len(features), dtype=bool)

    def record_valid_bounds(
        low: np.ndarray[Any, Any],
        high: np.ndarray[Any, Any],
        valid: np.ndarray[Any, Any],
    ) -> None:
        """Collect raw widths and, when possible, close/ATR-scaled geometry."""
        nonlocal normalized_rows
        widths.append(high[valid] - low[valid])
        if reference_close is None or atr is None:
            return
        scaled = valid & np.isfinite(reference_close) & np.isfinite(atr) & (atr > 0.0)
        if not np.any(scaled):
            return
        normalized_rows |= scaled
        normalized_widths.append((high[scaled] - low[scaled]) / atr[scaled])
        outside_distance = np.maximum(low[scaled] - reference_close[scaled], 0.0) + np.maximum(
            reference_close[scaled] - high[scaled], 0.0
        )
        normalized_distances.append(outside_distance / atr[scaled])
        normalized_inside.append(outside_distance == 0.0)

    for family, active_column, low_column, high_column in _geometry_specs(candidate):
        if family == "po3_ifvg":
            code_column = "po3_ifvg_confirmation_tf_code"
            if (
                code_column not in features.columns
                or low_column not in features.columns
                or high_column not in features.columns
            ):
                continue
            found_contract = True
            codes = pd.to_numeric(features[code_column], errors="coerce").to_numpy(dtype=float)
            low = pd.to_numeric(features[low_column], errors="coerce").to_numpy(dtype=float)
            high = pd.to_numeric(features[high_column], errors="coerce").to_numpy(dtype=float)
            special_zone_active = (
                active_values & np.isfinite(codes) & np.isin(codes, _PO3_TIMEFRAME_CODES)
            )
            special_zone_valid = (
                special_zone_active & np.isfinite(low) & np.isfinite(high) & (low <= high)
            )
            invalid_counts += (special_zone_active & ~special_zone_valid).astype(np.int16)
            geometry_counts += special_zone_valid.astype(np.int16)
            record_valid_bounds(low, high, special_zone_valid)
            continue
        if low_column not in features.columns or high_column not in features.columns:
            continue
        if active_column is None:
            zone_active = active_values.copy()
        else:
            if active_column not in features.columns:
                continue
            active_values_for_zone = pd.to_numeric(
                features[active_column], errors="coerce"
            ).to_numpy(dtype=float)
            zone_active = (
                active_values & np.isfinite(active_values_for_zone) & (active_values_for_zone > 0.0)
            )
        if family.startswith("po3:"):
            _, timeframe, _zone_family = family.split(":", maxsplit=2)
            zone_active &= ~special_zone_valid
            zone_active &= _po3_timeframe_rows(features, timeframe, int(candidate.direction))
        found_contract = True
        low = pd.to_numeric(features[low_column], errors="coerce").to_numpy(dtype=float)
        high = pd.to_numeric(features[high_column], errors="coerce").to_numpy(dtype=float)
        valid = zone_active & np.isfinite(low) & np.isfinite(high) & (low <= high)
        invalid = zone_active & ~valid
        geometry_counts += valid.astype(np.int16)
        invalid_counts += invalid.astype(np.int16)
        record_valid_bounds(low, high, valid)

    valid_geometry_rows = active_values & (geometry_counts > 0)
    invalid_geometry_rows = active_values & (invalid_counts > 0)
    candidate = TRADE_SETUP_CANDIDATES[candidate_id]
    if candidate.idea == "standard_deviation":
        geometry_kind = "retracement_band"
        contract = (
            "retracement_band_fields_available"
            if found_contract
            else "expected_retracement_band_fields_missing"
        )
    elif not _ZONE_FAMILIES.get(str(candidate.idea), ()) and candidate.idea != "po3":
        geometry_kind = "source_zone"
        contract = "no_price_geometry_fields_exposed_by_current_context"
    elif found_contract:
        geometry_kind = "source_zone"
        contract = "source_zone_bounds_available"
    else:
        geometry_kind = "source_zone"
        contract = "expected_source_zone_bounds_missing"
    active_count = int(active_values.sum())
    width_values = (
        np.concatenate([values for values in widths if values.size])
        if any(values.size for values in widths)
        else np.asarray([], dtype=float)
    )
    normalized_width_values = (
        np.concatenate([values for values in normalized_widths if values.size])
        if any(values.size for values in normalized_widths)
        else np.asarray([], dtype=float)
    )
    normalized_distance_values = (
        np.concatenate([values for values in normalized_distances if values.size])
        if any(values.size for values in normalized_distances)
        else np.asarray([], dtype=float)
    )
    normalized_inside_values = (
        np.concatenate([values for values in normalized_inside if values.size])
        if any(values.size for values in normalized_inside)
        else np.asarray([], dtype=bool)
    )
    normalization_available = reference_close is not None and atr is not None
    normalized_row_count = int(normalized_rows.sum())
    return {
        "candidate_id": candidate_id,
        "idea": str(candidate.idea),
        "timeframe": str(candidate.setup_timeframe),
        "direction": int(candidate.direction),
        "configured_support": bool(configured_support),
        "active_training_rows": active_count,
        "geometry_kind": geometry_kind,
        "geometry_contract": contract,
        "rows_with_valid_geometry": int(valid_geometry_rows.sum()) if found_contract else None,
        "rows_with_invalid_geometry_bounds": (
            int(invalid_geometry_rows.sum()) if found_contract else None
        ),
        "geometry_coverage_fraction": (
            float(valid_geometry_rows.sum() / active_count)
            if found_contract and active_count
            else None
        ),
        "median_geometry_width": float(np.median(width_values)) if width_values.size else None,
        "p95_geometry_width": float(np.quantile(width_values, 0.95)) if width_values.size else None,
        "rows_with_atr_normalized_geometry": (
            normalized_row_count if normalization_available else None
        ),
        "atr_normalized_geometry_coverage_fraction": (
            float(normalized_row_count / active_count)
            if normalization_available and active_count
            else None
        ),
        "median_geometry_width_atr": (
            float(np.median(normalized_width_values)) if normalized_width_values.size else None
        ),
        "p95_geometry_width_atr": (
            float(np.quantile(normalized_width_values, 0.95))
            if normalized_width_values.size
            else None
        ),
        "fraction_price_inside_geometry": (
            float(normalized_inside_values.mean()) if normalized_inside_values.size else None
        ),
        "median_distance_to_geometry_atr": (
            float(np.median(normalized_distance_values))
            if normalized_distance_values.size
            else None
        ),
        "p95_distance_to_geometry_atr": (
            float(np.quantile(normalized_distance_values, 0.95))
            if normalized_distance_values.size
            else None
        ),
    }


def build_report(
    cfg: DictConfig,
    output_dir: Path,
    *,
    config_path: Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Build a training-only source-zone availability packet."""
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing evidence packet: {output_dir}")
    data_manifest = (
        ROOT
        / "evidence/research/releases/negative-evidence-readiness/RAW_DATA_SHA256_MANIFEST.json"
    )
    manifest_data = json.loads(data_manifest.read_text(encoding="utf-8"))
    manifest_files = {entry["path"]: entry for entry in manifest_data["files"]}
    spec = cfg.data.datasets.training
    training_inputs: dict[str, str] = {}
    primary_symbol = str(cfg.data.primary)
    secondary_symbol = str(cfg.data.secondary)
    for symbol in (primary_symbol, secondary_symbol):
        selected = [spec.m1_files[symbol]]
        selected.extend(
            timeframe_files[symbol]
            for timeframe_files in spec.timeframe_files.values()
            if symbol in timeframe_files
        )
        for relative in selected:
            relative_path = (Path(str(spec.raw_dir)) / str(relative)).as_posix()
            entry = manifest_files.get(relative_path)
            if entry is None:
                raise ValueError(
                    f"training input is absent from local data manifest: {relative_path}"
                )
            input_path = ROOT / relative_path
            stat = input_path.stat()
            if stat.st_size != int(entry["size_bytes"]):
                raise ValueError(f"training input size differs from data manifest: {relative_path}")
            if abs(stat.st_mtime - pd.Timestamp(entry["mtime_utc"]).timestamp()) > 1.0:
                raise ValueError(
                    f"training input mtime differs from data manifest: {relative_path}"
                )
            actual_sha256 = _sha256_file(input_path)
            if actual_sha256 != str(entry["sha256"]):
                raise ValueError(
                    f"training input SHA-256 differs from data manifest: {relative_path}"
                )
            training_inputs[relative_path] = actual_sha256
    cfg.data.cache_dir = str(ROOT / "cache/trade_setup_opportunity_census")
    data = run_pipeline(cfg, datasets=["training"])
    train_start = str(cfg.data.split.train_start)
    train_end = str(cfg.data.split.train_end)
    primary = training_slice(data[primary_symbol], train_start, train_end)
    secondary = training_slice(data[secondary_symbol], train_start, train_end)
    if primary["M1"].empty or secondary["M1"].empty:
        raise ValueError("configured training-only M1 input is empty")
    features = build_features(
        primary["M1"],
        secondary["M1"],
        cfg=cfg,
        train_mask=pd.Series(True, index=primary["M1"].index, dtype=bool),
        timeframe_bars=primary,
        secondary_timeframe_bars=secondary,
    )
    if not features.index.equals(primary["M1"].index):
        raise ValueError("candidate geometry feature rows do not align to the M1 source bars")
    features = features.copy()
    features["close"] = pd.to_numeric(primary["M1"]["close"], errors="coerce")
    features["atr"] = calculate_atr(primary["M1"], int(cfg.features.atr_period))
    if not features.columns.is_unique:
        raise ValueError("candidate geometry support requires unique feature columns")

    support = {
        (candidate.idea, candidate.setup_timeframe): (
            candidate.idea is not None
            and candidate.setup_timeframe is not None
            and candidate_supported(cfg, candidate.idea, candidate.setup_timeframe)
        )
        for candidate in TRADE_SETUP_CANDIDATES
        if candidate.candidate_id != NO_TRADE_ID
    }
    rows = [
        _candidate_geometry_summary(
            features,
            candidate,
            configured_support=(
                True
                if candidate.candidate_id == NO_TRADE_ID
                else bool(support[(candidate.idea, candidate.setup_timeframe)])
            ),
        )
        for candidate in TRADE_SETUP_CANDIDATES
    ]
    table_path = output_dir / "candidate_price_geometry_support.csv"
    pd.DataFrame.from_records(rows).to_csv(table_path, index=False)
    resolved_config = OmegaConf.to_yaml(cfg, resolve=True)
    source_paths = (
        "scripts/research/analysis/features/candidate_geometry_support.py",
        "scripts/research/analysis/features/training_context.py",
        "scripts/research/analysis/features/entry_idea_opportunity_census.py",
        "features/context/entry_ideas.py",
        "features/context/swing_retracement.py",
        "features/context/trade_setup_candidates.py",
        "decisioning/trade_setup.py",
        "features/pipeline/feature_matrix_builder.py",
        "features/pipeline/feature_cache_identity.py",
        "market_data/loading/market_data_ingestion.py",
    )
    output_hashes = {table_path.name: hashlib.sha256(table_path.read_bytes()).hexdigest()}
    metadata: dict[str, Any] = {
        "status": "training_feature_source_availability_only",
        "schema_version": GEOMETRY_SUPPORT_SCHEMA_VERSION,
        "interpretation": (
            "Measures source-zone or standard-deviation retracement-band bounds on eligible "
            "training feature rows, plus width and distance scaled by the aligned M1 ATR. "
            "It does not provide proposed entry, stop, target, order TTL, fill, return, or policy evidence."
        ),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "config": (
            config_path.resolve().relative_to(ROOT.resolve()).as_posix()
            if config_path.resolve().is_relative_to(ROOT.resolve())
            else str(config_path.resolve())
        ),
        "resolved_config_sha256": hashlib.sha256(resolved_config.encode("utf-8")).hexdigest(),
        "local_data_manifest": str(data_manifest.relative_to(ROOT)),
        "local_data_manifest_sha256": hashlib.sha256(data_manifest.read_bytes()).hexdigest(),
        "training_period": {"start": train_start, "end_inclusive": train_end},
        "training_rows": int(len(features)),
        "primary_symbol": primary_symbol,
        "secondary_symbol": secondary_symbol,
        "training_input_sha256": training_inputs,
        "candidate_count": int(len(rows)),
        "source_timeframes": list(TIMEFRAMES),
        "source_hashes": {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source_paths
        },
        "outputs": output_hashes,
    }
    (output_dir / "geometry_support.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "README.md").write_text(
        "# Candidate price-geometry support\n\n"
        "This training-only feature audit measures whether active setup candidates "
        "have finite, ordered source-zone or standard-deviation retracement-band bounds. "
        "It does not produce candidate entry, stop, target, order lifetime, or "
        "execution geometry and is not policy or economic evidence.\n\n"
        "`candidate_price_geometry_support.csv` reports active rows, configured support, "
        "geometry kind, valid coverage, invalid bounds, and widths in instrument "
        "price units. It also reports geometry width and distance from current M1 close "
        "in current M1 ATR units, plus the fraction of valid source bounds containing "
        "the close. The close and ATR are joined from the same M1 source index. "
        "Standard-deviation candidates use their timeframe-specific "
        "retracement band. A family with no applicable geometry fields is marked "
        "explicitly instead of being counted as missing data. PO3 "
        "uses its direct zone projection when available and otherwise mirrors "
        "the existing timeframe-specific FVG/IFVG context fallback. "
        "See `geometry_support.json` for training period, source hashes, and "
        "output hash. Rebuild with `.venv/bin/python -m "
        "scripts.research.analysis.features.candidate_geometry_support` from "
        "the repository root.\n",
        encoding="utf-8",
    )
    output_hashes["README.md"] = hashlib.sha256((output_dir / "README.md").read_bytes()).hexdigest()
    (output_dir / "geometry_support.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    checksum_rows = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in sorted(output_dir.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name != "OUTPUT_SHA256SUMS"
    ]
    (output_dir / "OUTPUT_SHA256SUMS").write_text("\n".join(checksum_rows) + "\n", encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    cfg = load_config(config_path=config_path)
    cfg.features.entry_ideas.enabled = True
    print(
        json.dumps(
            build_report(cfg, args.output_dir, config_path=config_path),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
