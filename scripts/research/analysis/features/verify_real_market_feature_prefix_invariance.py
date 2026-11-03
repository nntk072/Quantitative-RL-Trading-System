#!/usr/bin/env python3
"""Check real-market feature prefix invariance at frozen train/OOS cutoffs.

Rebuild the full feature matrix from configured raw M1 files, then rebuild
prefixes ending at selected timestamps. If future bars affect any earlier
feature, the prefix and full matrices diverge before that cutoff.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.metadata
import json
import os
import platform
from functools import cache
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
from omegaconf import DictConfig, OmegaConf
from scripts.research.analysis.features.build_feature_configuration_inventory import (
    load_profile_config,
)

from configuration import apply_overrides, load_config
from configuration.paths import repository_root
from features import (
    FEATURE_CACHE_VERSION,
    build_features,
    feature_cache_content_hash,
)
from market_data.loading.bars import load_bars
from market_data.splits.definitions import (
    get_split_config,
    get_train_start_config,
    make_train_mask,
)
from market_data.transforms.cleaning import clean
from market_data.transforms.price_grid import configured_price_grid_increment, quantize_bar_prices
from market_data.transforms.sessions import add_session_id, add_session_labels
from training.configuration.strategy_overlays import merge_strategy_config
from training.configuration.variant_resolution import resolve_variant

ROOT = repository_root(__file__)
DEFAULT_VARIANT_FILE = ROOT / "config" / "experiment_runs" / "variant_list.txt"
DEFAULT_CUTOFFS = (
    "2025-12-15 12:37:00",
    "2026-03-09 12:37:00",
    "2026-06-15 12:37:00",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


AUDIT_SCRIPT_SHA256 = sha256_file(Path(__file__).resolve())


def load_market_bars(
    cfg: Any,
    symbol: str,
    dataset_name: str = "training",
    raw_cache: dict[Path, pd.DataFrame] | None = None,
) -> tuple[pd.DataFrame, Path]:
    source = configured_m1_path(cfg, symbol, dataset_name)
    if raw_cache is not None and source in raw_cache:
        raw = raw_cache[source]
    else:
        raw = load_bars(source)
        if raw_cache is not None:
            raw_cache[source] = raw
    raw = quantize_bar_prices(raw, configured_price_grid_increment(cfg))
    bars = clean(raw, tz=str(cfg.data.tz))
    bars = add_session_labels(bars, tz=str(cfg.data.tz), ny_end=str(cfg.session.end))
    bars = add_session_id(bars)
    return bars, source


def load_all_market_bars(
    cfg: Any, symbol: str, raw_cache: dict[Path, pd.DataFrame] | None = None
) -> tuple[pd.DataFrame, list[Path], list[dict[str, Any]]]:
    """Load and join the configured training and testing M1 exports."""
    split_bars: list[pd.DataFrame] = []
    paths: list[Path] = []
    split_metadata: list[dict[str, Any]] = []
    for dataset_name in ("training", "testing"):
        bars, source = load_market_bars(cfg, symbol, dataset_name, raw_cache)
        if bars.empty:
            raise ValueError(f"{dataset_name} M1 export is empty for {symbol}")
        split_bars.append(bars)
        paths.append(source)
        split_metadata.append(
            {
                "dataset": dataset_name,
                "path": str(source.relative_to(ROOT)),
                "rows": len(bars),
                "start": bars.index[0].isoformat(),
                "end": bars.index[-1].isoformat(),
            }
        )

    combined = pd.concat(split_bars).sort_index()
    if not combined.index.is_unique or not combined.index.is_monotonic_increasing:
        raise ValueError(f"training/testing M1 indexes overlap or are unordered for {symbol}")
    return combined, paths, split_metadata


def configured_m1_path(cfg: Any, symbol: str, dataset_name: str = "training") -> Path:
    """Resolve one configured local M1 export by dataset role and symbol."""
    datasets = cfg.data.get("datasets")
    if datasets:
        dataset = datasets.get(dataset_name)
        if dataset is None:
            raise ValueError(f"feature-prefix audit requires a configured {dataset_name} dataset")
        raw_dir = Path(str(dataset.raw_dir))
        m1_files = dataset.get("m1_files", {})
    else:
        if dataset_name != "training":
            raise ValueError(f"feature-prefix audit requires a configured {dataset_name} dataset")
        raw_dir = Path(str(cfg.data.raw_dir))
        m1_files = cfg.data.get("m1_files", {})
    filename = m1_files.get(symbol)
    if not filename:
        raise KeyError(f"no configured training M1 file for {symbol}")
    return (ROOT / raw_dir / str(filename)).resolve()


def compare_prefix(
    reference: pd.DataFrame,
    candidate: pd.DataFrame,
    cutoff: pd.Timestamp,
) -> dict[str, Any]:
    expected = reference.loc[:cutoff]
    if not expected.index.equals(candidate.index):
        return {
            "cutoff": cutoff.isoformat(),
            "passed": False,
            "reason": "prefix indexes differ",
            "reference_rows": len(expected),
            "prefix_rows": len(candidate),
        }
    if list(expected.columns) != list(candidate.columns):
        return {
            "cutoff": cutoff.isoformat(),
            "passed": False,
            "reason": "feature columns differ",
            "reference_columns": len(expected.columns),
            "prefix_columns": len(candidate.columns),
        }

    changed_features: list[dict[str, Any]] = []
    max_abs_delta = 0.0
    compared_values = 0
    for column in expected.columns:
        left = pd.to_numeric(expected[column], errors="coerce").to_numpy(dtype=np.float64)
        right = pd.to_numeric(candidate[column], errors="coerce").to_numpy(dtype=np.float64)
        left_nan = np.isnan(left)
        right_nan = np.isnan(right)
        nan_mismatch = left_nan != right_nan
        finite = np.isfinite(left) & np.isfinite(right)
        close = np.ones(len(left), dtype=bool)
        close[finite] = np.isclose(left[finite], right[finite], rtol=1e-10, atol=1e-12)
        nonfinite = ~finite
        close[nonfinite] = left[nonfinite] == right[nonfinite]
        close[left_nan & right_nan] = True
        compared_values += int(len(left))
        if finite.any():
            delta = np.abs(left[finite] - right[finite])
            column_max = float(delta.max(initial=0.0))
            max_abs_delta = max(max_abs_delta, column_max)
        else:
            column_max = 0.0
        mismatch = np.flatnonzero(~close)
        if len(mismatch):
            first = int(mismatch[0])
            changed_features.append(
                {
                    "feature": str(column),
                    "mismatch_rows": int(len(mismatch)),
                    "first_timestamp": expected.index[first].isoformat(),
                    "max_abs_delta": column_max,
                    "nan_mask_mismatches": int(nan_mismatch.sum()),
                }
            )
    return {
        "cutoff": cutoff.isoformat(),
        "passed": not changed_features,
        "rows": len(expected),
        "features": len(expected.columns),
        "compared_values": compared_values,
        "max_abs_delta": max_abs_delta,
        "changed_feature_count": len(changed_features),
        "changed_features": changed_features[:100],
    }


def resolve_cutoffs(cutoff_texts: list[str], index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    """Resolve cutoffs to the source timezone and require later rows to compare."""
    if index.empty:
        raise ValueError("feature-prefix audit source index is empty")
    cutoffs: list[pd.Timestamp] = []
    for cutoff_text in cutoff_texts:
        cutoff = pd.Timestamp(cutoff_text)
        if cutoff.tzinfo is None:
            cutoff = cutoff.tz_localize(index.tz)
        else:
            cutoff = cutoff.tz_convert(index.tz)
        if cutoff <= index[0] or cutoff >= index[-1]:
            raise ValueError(
                f"cutoff {cutoff.isoformat()} must be inside loaded data range "
                f"({index[0].isoformat()}, {index[-1].isoformat()}) "
                "with later rows available for comparison"
            )
        cutoffs.append(cutoff)
    return cutoffs


def config_for_variant(name: str) -> tuple[Any, dict[str, Any]]:
    resolved = resolve_variant(name)
    cfg: DictConfig = load_config(config_path=ROOT / str(resolved["base_config"]))
    cfg = merge_strategy_config(cfg, str(resolved["strategy"]))
    cfg = apply_overrides(cfg, list(resolved["overrides"]))
    return cfg, resolved


@cache
def _cached_input_sha256(path: str, _size: int, _mtime_ns: int) -> str:
    """Hash one configured input version once while profiles are grouped."""
    return sha256_file(Path(path))


def configured_m1_input_hashes(cfg: Any) -> dict[str, str]:
    """Return content identities for the M1 inputs used by full/prefix builds."""
    symbols = [
        str(value)
        for value in (
            OmegaConf.select(cfg, "data.primary"),
            OmegaConf.select(cfg, "data.secondary"),
        )
        if value
    ]
    identities: dict[str, str] = {}
    for dataset_name in ("training", "testing"):
        for symbol in symbols:
            path = configured_m1_path(cfg, symbol, dataset_name)
            stat = path.stat()
            identities[f"{dataset_name}/{symbol}"] = _cached_input_sha256(
                str(path), stat.st_size, stat.st_mtime_ns
            )
    return identities


def configured_training_mask(index: pd.DatetimeIndex, cfg: Any) -> pd.Series:
    """Build the same configured fit interval used by the training pipeline."""
    train_end, _ = get_split_config(cfg)
    return make_train_mask(index, train_end, get_train_start_config(cfg))


def feature_config_key(cfg: Any) -> str:
    def selected_value(path: str) -> Any:
        value = OmegaConf.select(cfg, path)
        return OmegaConf.to_container(value, resolve=True) if OmegaConf.is_config(value) else value

    payload = {
        "features": OmegaConf.to_container(cfg.features, resolve=True),
        "fit_interval": {
            "train_start": get_train_start_config(cfg),
            "train_end": get_split_config(cfg)[0],
        },
        "m1_input_sha256": configured_m1_input_hashes(cfg),
        "strategy.ifvg": selected_value("strategy.ifvg"),
        "data": {
            "tz": str(OmegaConf.select(cfg, "data.tz")),
            "timestamp_clock": str(OmegaConf.select(cfg, "data.timestamp_clock")),
            "session_schedule_file": str(OmegaConf.select(cfg, "data.session_schedule_file")),
            "price_discretization": selected_value("data.price_discretization"),
        },
        "costs.point_size": str(OmegaConf.select(cfg, "costs.point_size")),
        "session": {
            "tz": str(OmegaConf.select(cfg, "session.tz")),
            "start": str(OmegaConf.select(cfg, "session.start")),
            "end": str(OmegaConf.select(cfg, "session.end")),
        },
        "strategy.session.timezone": str(OmegaConf.select(cfg, "strategy.session.timezone")),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def load_inventory_profiles(path: Path) -> tuple[list[tuple[str, Any, dict[str, Any]]], str]:
    """Resolve every inventoried feature profile and verify its tree identity."""
    payload = path.read_bytes()
    inventory = json.loads(payload)
    if inventory.get("inventory_version") != "feature-configuration-inventory-v1":
        raise ValueError("unsupported feature configuration inventory version")
    profiles: list[tuple[str, Any, dict[str, Any]]] = []
    for item in inventory.get("profiles", []):
        profile_id = str(item["profile_id"])
        cfg = load_profile_config(profile_id)
        feature_tree = OmegaConf.to_container(cfg.features, resolve=True)
        encoded = json.dumps(feature_tree, sort_keys=True, separators=(",", ":")).encode()
        feature_hash = hashlib.sha256(encoded).hexdigest()
        if feature_hash != str(item["feature_config_sha256"]):
            raise ValueError(
                f"resolved feature tree differs from inventory for {profile_id}: "
                f"{feature_hash} != {item['feature_config_sha256']}"
            )
        profiles.append(
            (
                profile_id,
                cfg,
                {
                    "profile_kind": str(item["profile_kind"]),
                    "feature_config_sha256": feature_hash,
                    "source_sha256": str(item["source_sha256"]),
                    "source_paths": item["source_paths"],
                },
            )
        )
    if not profiles:
        raise ValueError("feature configuration inventory has no profiles")
    return profiles, hashlib.sha256(payload).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant-file", type=Path, default=DEFAULT_VARIANT_FILE)
    parser.add_argument(
        "--profile-inventory",
        type=Path,
        help="resolve every profile in a generated feature configuration inventory",
    )
    parser.add_argument("--cutoffs", nargs="+", default=list(DEFAULT_CUTOFFS))
    parser.add_argument(
        "--profile-group-shard",
        help="process one stable shard of effective feature-builder groups as INDEX/COUNT",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="JSON report path, relative to the repository when not absolute",
    )
    args = parser.parse_args()

    inventory_path: Path | None = None
    inventory_hash: str | None = None
    if args.profile_inventory:
        inventory_path = args.profile_inventory
        if not inventory_path.is_absolute():
            inventory_path = ROOT / inventory_path
        variant_configs, inventory_hash = load_inventory_profiles(inventory_path)
    else:
        variant_names = [
            line.strip()
            for line in args.variant_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if not variant_names:
            raise ValueError("variant list is empty")
        variant_configs = [(name, *config_for_variant(name)) for name in variant_names]
    feature_groups: dict[str, list[tuple[str, Any, dict[str, Any]]]] = {}
    for name, variant_cfg, resolved in variant_configs:
        feature_groups.setdefault(feature_config_key(variant_cfg), []).append(
            (name, variant_cfg, resolved)
        )
    shard_index: int | None = None
    shard_count: int | None = None
    if args.profile_group_shard is not None:
        try:
            raw_index, raw_count = args.profile_group_shard.split("/", maxsplit=1)
            shard_index, shard_count = int(raw_index), int(raw_count)
        except (ValueError, TypeError) as exc:
            raise ValueError("--profile-group-shard must be INDEX/COUNT") from exc
        if shard_count <= 0 or shard_index < 0 or shard_index >= shard_count:
            raise ValueError("profile group shard index must be in [0, COUNT)")
        ordered_keys = sorted(feature_groups)
        selected_keys = [
            key for index, key in enumerate(ordered_keys) if index % shard_count == shard_index
        ]
        if not selected_keys:
            raise ValueError(
                f"shard {shard_index}/{shard_count} has no feature-builder groups "
                f"(available={len(ordered_keys)})"
            )
        feature_groups = {key: feature_groups[key] for key in selected_keys}
    cfg = load_config() if inventory_path is not None else variant_configs[0][1]
    primary_symbol = str(cfg.data.primary)
    secondary_symbol = str(cfg.data.secondary)
    raw_cache: dict[Path, pd.DataFrame] = {}
    input_paths: set[Path] = set()
    group_results: list[dict[str, Any]] = []
    first_profile_data: dict[str, Any] | None = None
    for group_key, group in feature_groups.items():
        representative, group_cfg, resolved = group[0]
        if (
            str(group_cfg.data.primary) != primary_symbol
            or str(group_cfg.data.secondary) != secondary_symbol
        ):
            raise ValueError(f"profile {representative} uses different configured symbols")
        primary, primary_paths, primary_splits = load_all_market_bars(
            group_cfg, primary_symbol, raw_cache
        )
        secondary, secondary_paths, secondary_splits = load_all_market_bars(
            group_cfg, secondary_symbol, raw_cache
        )
        input_paths.update(primary_paths)
        input_paths.update(secondary_paths)
        train_end, test_start = get_split_config(group_cfg)
        train_start = get_train_start_config(group_cfg)
        primary_index = cast(pd.DatetimeIndex, primary.index)
        cutoff_timestamps = resolve_cutoffs(args.cutoffs, primary_index)
        train_mask = configured_training_mask(primary_index, group_cfg)
        if first_profile_data is None:
            first_profile_data = {
                "rows": len(primary),
                "start": primary.index[0].isoformat(),
                "end": primary.index[-1].isoformat(),
                "train_end": train_end,
                "train_start": train_start,
                "test_start": test_start,
            }
        feature_hash = feature_cache_content_hash(
            group_cfg, primary, train_mask=train_mask, secondary=secondary
        )
        grid_increment = configured_price_grid_increment(group_cfg)
        schedule_value = OmegaConf.select(group_cfg, "data.session_schedule_file")
        schedule_path = Path(str(schedule_value)).expanduser() if schedule_value else None
        if schedule_path is not None and not schedule_path.is_absolute():
            schedule_path = ROOT / schedule_path
        schedule_hash = (
            sha256_file(schedule_path)
            if schedule_path is not None and schedule_path.is_file()
            else None
        )
        print(
            f"building profile={representative} variants={[item[0] for item in group]} "
            f"rows={len(primary)} price_grid={grid_increment} "
            f"features={FEATURE_CACHE_VERSION} hash={feature_hash}",
            flush=True,
        )
        reference = build_features(
            primary,
            secondary=secondary,
            cfg=group_cfg,
            train_mask=train_mask,
            force=True,
        )
        if not reference.index.equals(primary.index):
            raise RuntimeError(f"full feature reference for {representative} is misaligned")

        cutoff_results: list[dict[str, Any]] = []
        for cutoff in cutoff_timestamps:
            prefix_primary = primary.loc[:cutoff]
            prefix_secondary = secondary.loc[:cutoff]
            if prefix_primary.empty:
                raise ValueError(f"cutoff precedes source data: {cutoff}")
            prefix_index = cast(pd.DatetimeIndex, prefix_primary.index)
            prefix_mask = configured_training_mask(prefix_index, group_cfg)
            print(
                f"rebuilding profile={representative} prefix cutoff={cutoff.isoformat()} "
                f"rows={len(prefix_primary)}",
                flush=True,
            )
            prefix = build_features(
                prefix_primary,
                secondary=prefix_secondary,
                cfg=group_cfg,
                train_mask=prefix_mask,
                force=True,
            )
            cutoff_results.append(compare_prefix(reference, prefix, cutoff))
            del prefix, prefix_primary, prefix_secondary, prefix_mask
            gc.collect()
        group_results.append(
            {
                "profile_id": group_key,
                "representative_variant": representative,
                "profile_ids": [item[0] for item in group],
                "base_config": resolved.get("base_config"),
                "feature_profile": resolved.get("feature_profile"),
                "price_grid_increment": grid_increment,
                "fit_interval": {"train_start": train_start, "train_end": train_end},
                "m1_input_sha256": configured_m1_input_hashes(group_cfg),
                "session_schedule_file": str(schedule_value) if schedule_value else None,
                "session_schedule_sha256": schedule_hash,
                "input_splits": {
                    primary_symbol: primary_splits,
                    secondary_symbol: secondary_splits,
                },
                "profile_sources": {
                    source["path"]: source["sha256"]
                    for item in group
                    for source in item[2].get("source_paths", [])
                },
                "profile_kinds": sorted(
                    {str(item[2].get("profile_kind", "legacy_variant")) for item in group}
                ),
                "inventory_feature_config_hashes": sorted(
                    {
                        str(item[2]["feature_config_sha256"])
                        for item in group
                        if item[2].get("feature_config_sha256")
                    }
                ),
                "feature_content_hash": feature_hash,
                "feature_columns": [str(column) for column in reference.columns],
                "cutoffs": cutoff_results,
                "summary": {
                    "passed": sum(bool(item["passed"]) for item in cutoff_results),
                    "failed": sum(not bool(item["passed"]) for item in cutoff_results),
                    "cutoffs": len(cutoff_results),
                },
            }
        )
        del reference
        del primary, secondary, train_mask
        gc.collect()

    if first_profile_data is None:
        raise RuntimeError("no feature configuration groups were evaluated")

    feature_sources = sorted(
        path
        for group in (ROOT / "features", ROOT / "market_data")
        for path in group.rglob("*.py")
        if path.is_file()
    )
    feature_sources.extend(
        path
        for path in (
            ROOT / "config" / "base" / "default.yaml",
            ROOT / "configuration" / "configuration_loader.py",
            ROOT / "configuration" / "schema.py",
            ROOT / "configuration" / "loader.py",
            ROOT / "training" / "configuration" / "strategy_overlays.py",
            ROOT / "training" / "configuration" / "variant_resolution.py",
            ROOT / "config" / "experiments.yaml",
            ROOT / "config" / "2_po3_ifvg.yaml",
            ROOT / "config" / "3_distribution.yaml",
            ROOT / "config" / "features" / "full_po3_mtf.yaml",
            args.variant_file.resolve() if inventory_path is None else inventory_path,
        )
        if path.is_file()
    )
    feature_sources = sorted(set(feature_sources))
    all_cutoffs = [item for group in group_results for item in group["cutoffs"]]
    config_paths = sorted(
        {
            str((ROOT / str(item[2]["base_config"])).relative_to(ROOT))
            for item in variant_configs
            if item[2].get("base_config")
        }
    )
    report = {
        "audit": "real_market_feature_prefix_invariance",
        "base_configs": config_paths,
        "resolved_variants": (
            [] if inventory_path is not None else [name for name, _, _ in variant_configs]
        ),
        "resolved_profiles": (
            [name for name, _, _ in variant_configs] if inventory_path is not None else []
        ),
        "profile_inventory_sha256": inventory_hash,
        "profile_inventory_mode": inventory_path is not None,
        "profile_group_shard": (
            None
            if shard_index is None or shard_count is None
            else {
                "index": shard_index,
                "count": shard_count,
                "selected_groups": len(group_results),
            }
        ),
        "feature_version": FEATURE_CACHE_VERSION,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": {
                package: importlib.metadata.version(package)
                for package in ("numpy", "pandas", "omegaconf")
            },
            "slurm_job_id": os.getenv("SLURM_JOB_ID"),
        },
        "profile_groups": group_results,
        **first_profile_data,
        "input_files": {
            str(path.relative_to(ROOT)): sha256_file(path) for path in sorted(input_paths)
        },
        "source_hashes": {
            str(path.relative_to(ROOT)): sha256_file(path) for path in feature_sources
        },
        "audit_script_sha256": AUDIT_SCRIPT_SHA256,
        "cutoffs": all_cutoffs,
        "summary": {
            "passed": sum(bool(item["passed"]) for item in all_cutoffs),
            "failed": sum(not bool(item["passed"]) for item in all_cutoffs),
            "cutoffs": len(all_cutoffs),
            "feature_profiles": len(group_results),
        },
        "scope_note": (
            "Prefix invariance at the listed real-market cutoffs; it tests whether later bars alter "
            "feature values up to each cutoff. It does not by itself prove every execution, label, "
            "or model-selection path is leakage-free."
        ),
    }
    output = args.out if args.out.is_absolute() else ROOT / args.out
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"report={output} summary={report['summary']}", flush=True)
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
