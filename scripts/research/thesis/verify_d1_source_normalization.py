#!/usr/bin/env python3
"""Rebuild the matched D1-normalized cache and measure entry-time availability."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
from omegaconf import DictConfig, OmegaConf

from features import build_features, feature_cache_path
from market_data.loading.pipeline import BAR_CACHE_VERSION
from market_data.splits.definitions import (
    get_split_config,
    get_train_start_config,
    make_train_mask,
)

TECHNICAL_COLUMNS = (
    "D1_ret_5",
    "D1_ret_30",
    "D1_ema_21_dist",
    "D1_ema_50_dist",
    "D1_ema_200_dist",
    "D1_adx",
    "D1_realized_vol",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_timeframes(
    cache_root: Path, symbol: str, timeframes: list[str]
) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for timeframe in timeframes:
        parts = []
        filename = f"{symbol}_{timeframe}_{BAR_CACHE_VERSION}.parquet"
        for split in ("training", "testing"):
            path = cache_root / split / filename
            if path.is_file():
                parts.append(pd.read_parquet(path))
        if not parts:
            raise FileNotFoundError(
                f"no cached bars found for {symbol} {timeframe} under {cache_root}"
            )
        combined = pd.concat(parts).sort_index()
        if combined.index.has_duplicates:
            raise ValueError(f"duplicate timestamps in {symbol} {timeframe} cache")
        frames[timeframe] = combined
    return frames


def _availability(
    feature_cache: Path, entries: pd.DataFrame, feature_columns: tuple[str, ...]
) -> dict[str, dict[str, int]]:
    available = pd.read_parquet(feature_cache, columns=list(feature_columns))
    index = pd.DatetimeIndex(available.index).tz_convert("UTC")
    query = pd.DatetimeIndex(pd.to_datetime(entries["decision_time"], utc=True, errors="coerce"))
    positions = index.get_indexer(query)
    valid_positions = positions >= 0
    safe_positions = positions.clip(min=0)
    result: dict[str, dict[str, int]] = {}
    for column in feature_columns:
        values = pd.to_numeric(available[column], errors="coerce").to_numpy()
        finite = valid_positions & pd.notna(values[safe_positions])
        result[column] = {
            "finite_at_entries": int(finite.sum()),
            "entry_count": int(len(entries)),
            "unique_finite_values": int(pd.Series(values[safe_positions][finite]).nunique()),
        }
    return result


def verify(run_dir: Path, output_path: Path) -> dict[str, Any]:
    config_path = run_dir / "config.yaml"
    manifest_path = run_dir / "run_manifest.json"
    trades_path = run_dir / "training" / "trades.csv"
    cfg = OmegaConf.load(config_path)
    if not isinstance(cfg, DictConfig):
        raise TypeError(f"expected a mapping config, got {type(cfg).__name__}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cache_root = Path(str(cfg.data.cache_dir))
    if not cache_root.is_absolute():
        cache_root = Path.cwd() / cache_root
    primary = str(cfg.data.primary)
    secondary = str(cfg.data.secondary)
    timeframes = [str(tf) for tf in cfg.data.timeframes]
    primary_frames = _load_timeframes(cache_root, primary, timeframes)
    secondary_frames = _load_timeframes(cache_root, secondary, timeframes)
    primary_m1 = primary_frames["M1"]
    train_end, _test_start = get_split_config(cfg)
    train_start = get_train_start_config(cfg)
    train_mask = make_train_mask(pd.DatetimeIndex(primary_m1.index), train_end, train_start)

    baseline_cache = Path(str(manifest["feature_cache"]["path"]))
    if not baseline_cache.is_absolute():
        baseline_cache = Path.cwd() / baseline_cache
    cfg.features.normalize_d1_technical_on_source = True
    treatment_cache = feature_cache_path(
        cache_root,
        primary,
        cfg,
        primary_m1,
        train_mask=train_mask,
        secondary=secondary_frames["M1"],
        timeframe_bars=primary_frames,
        secondary_timeframe_bars=secondary_frames,
    )
    build_features(
        primary_m1,
        secondary=secondary_frames["M1"],
        cfg=cfg,
        train_mask=train_mask,
        cache_path=treatment_cache,
        timeframe_bars=primary_frames,
        secondary_timeframe_bars=secondary_frames,
    )

    trades = pd.read_csv(trades_path, usecols=["type", "position_id", "decision_time"])
    entries = trades.loc[trades["type"].eq("open")].drop_duplicates("position_id", keep="first")
    if entries["decision_time"].isna().any():
        raise ValueError("open events contain missing decision timestamps")
    baseline = _availability(baseline_cache, entries, TECHNICAL_COLUMNS)
    treatment = _availability(treatment_cache, entries, TECHNICAL_COLUMNS)
    result = {
        "run_dir": str(run_dir.resolve()),
        "manifest_sha256": _sha256(manifest_path),
        "entry_ledger_sha256": _sha256(trades_path),
        "entry_count": int(len(entries)),
        "baseline_feature_cache": str(baseline_cache.resolve()),
        "baseline_feature_cache_sha256": _sha256(baseline_cache),
        "treatment_feature_cache": str(treatment_cache.resolve()),
        "treatment_feature_cache_sha256": _sha256(treatment_cache),
        "treatment_cache_hash_sidecar": Path(str(treatment_cache) + ".hash")
        .read_text(encoding="utf-8")
        .strip(),
        "normalization_policy": "D1 technical features normalized on completed D1 source bars using the M1 training-mask boundary, then causally aligned to M1",
        "baseline_availability": baseline,
        "treatment_availability": treatment,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.run_dir, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
