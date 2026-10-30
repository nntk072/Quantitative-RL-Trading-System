"""End-to-end data pipeline: raw CSVs → cleaned parquet cache.

Usage
-----
    from market_data.loading import run_pipeline, build_tick_books
    dfs   = run_pipeline(cfg)
    ticks = build_tick_books(cfg)   # {symbol: TickBook | None}

Bar caches are versioned (``BAR_CACHE_VERSION``) so a full-day rebuild is not
silently skipped in favour of a stale NY-only parquet. Session filtering is
not applied to the feature dataset; ``session`` is an eligibility label.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
from omegaconf import DictConfig

from artifacts.identity import file_sha256
from market_data.cache.bars import (
    bar_cache_path,
    build_bar_cache_identity,
    load_bar_cache,
    write_bar_cache,
)
from market_data.loading.bars import load_bars
from market_data.transforms.cleaning import clean
from market_data.transforms.price_grid import (
    configured_price_grid_increment,
    price_grid_identity,
    quantize_bar_prices,
)
from market_data.transforms.resample import resample
from market_data.transforms.sessions import add_session_id, add_session_labels

log = logging.getLogger(__name__)

# The v4 cache uses semantic manifests and atomic parquet publication.
BAR_CACHE_VERSION = "v4-semantic-manifest"


def run_pipeline(
    cfg: DictConfig,
    force: bool = False,
    datasets: Sequence[str] | None = None,
) -> dict[str, dict[str, pd.DataFrame]]:
    """Load, resample, clean, label and cache all symbols / timeframes.

    Full-day M1 is kept for every timeframe. ``filter_session`` is not applied.

    Parameters
    ----------
    cfg:
        OmegaConf config (config/base/default.yaml).
    force:
        If True, ignore existing parquet cache and reprocess from CSV.
    """
    cache_dir = Path(cfg.data.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    tz = str(cfg.data.tz)
    ny_end = str(cfg.session.end)
    require_native_timeframes = bool(cfg.data.get("require_native_timeframes", False))
    derived_timeframes = cfg.data.get("derived_timeframes", {})
    timestamp_convention = str(cfg.data.get("bar_timestamp_convention", "open")).lower()
    grid_increment = configured_price_grid_increment(cfg)
    grid_identity = f":{price_grid_identity(grid_increment)}" if grid_increment is not None else ""
    if timestamp_convention != "open":
        raise ValueError(
            "timeframe close alignment currently requires open-stamped bars; "
            f"configured convention is {timestamp_convention!r}"
        )
    configured_sets = cfg.data.get("datasets")
    if configured_sets:
        dataset_specs = [
            (
                str(name),
                Path(str(spec.raw_dir)),
                spec.m1_files,
                spec.get("timeframe_files", {}),
            )
            for name, spec in configured_sets.items()
            if datasets is None or str(name) in datasets
        ]
        if datasets is not None:
            missing = set(datasets).difference(str(name) for name in configured_sets)
            if missing:
                raise ValueError(f"requested datasets are not configured: {sorted(missing)}")
    else:
        if datasets is not None and set(datasets) != {"all"}:
            raise ValueError("only the 'all' dataset is configured")
        dataset_specs = [("all", Path(str(cfg.data.raw_dir)), cfg.data.m1_files, {})]

    parts: dict[str, dict[str, list[pd.DataFrame]]] = {
        str(symbol): {str(tf): [] for tf in cfg.data.timeframes} for symbol in cfg.data.symbols
    }
    for dataset_name, root, m1_files, timeframe_files in dataset_specs:
        part_cache = cache_dir / dataset_name
        part_cache.mkdir(parents=True, exist_ok=True)
        for symbol in cfg.data.symbols:
            configured_m1 = timeframe_files.get("M1", {}).get(symbol)
            m1_path = root / str(configured_m1 or m1_files[symbol])
            m1_raw = quantize_bar_prices(load_bars(m1_path), grid_increment)
            source_hashes = {m1_path: file_sha256(m1_path)}

            def input_hash(path: Path) -> str:
                if path not in source_hashes:
                    source_hashes[path] = file_sha256(path)
                return source_hashes[path]

            m1_clean = clean(m1_raw, tz=tz)
            m1_full = add_session_labels(m1_clean, tz=tz, ny_end=ny_end)
            m1_full = add_session_id(m1_full)
            for tf in cfg.data.timeframes:
                tf = str(tf)
                cp = bar_cache_path(part_cache, str(symbol), tf, BAR_CACHE_VERSION)
                native_file = timeframe_files.get(tf, {}).get(symbol)
                if tf == "M1":
                    source_path = m1_path
                    source_identity = f"native:{input_hash(source_path)}{grid_identity}"
                elif native_file:
                    source_path = root / str(native_file)
                    if not source_path.is_file():
                        raise FileNotFoundError(
                            f"configured native {tf} source for {symbol} is missing: {source_path}"
                        )
                    source_identity = f"native:{input_hash(source_path)}{grid_identity}"
                else:
                    allowed_derived = [
                        str(value).upper() for value in derived_timeframes.get(symbol, [])
                    ]
                    if require_native_timeframes and tf not in allowed_derived:
                        raise FileNotFoundError(
                            f"native {tf} source for {symbol} is required but not configured; "
                            "declare an intentional M1-derived timeframe explicitly to proceed"
                        )
                    source_path = m1_path
                    source_identity = (
                        f"derived-from-M1:{input_hash(source_path)}:{tf}{grid_identity}"
                    )
                cache_identity = build_bar_cache_identity(
                    dataset_id=dataset_name,
                    symbol=str(symbol),
                    timeframe=tf,
                    source_identity=source_identity,
                    timezone=tz,
                    ny_session_end=ny_end,
                    timestamp_convention=timestamp_convention,
                    price_grid_identity=(
                        price_grid_identity(grid_increment) if grid_increment is not None else None
                    ),
                )
                cached_frame = None if force else load_bar_cache(cp, cache_identity)
                if cached_frame is not None:
                    df = cached_frame
                else:
                    if tf == "M1":
                        df = m1_full.copy()
                    elif native_file:
                        tf_raw = quantize_bar_prices(load_bars(source_path), grid_increment)
                        tf_clean = clean(tf_raw, tz=tz)
                        df = add_session_labels(tf_clean, tz=tz, ny_end=ny_end)
                        df = add_session_id(df)
                    else:
                        # Explicitly absent timeframe sources may be represented
                        # by a derived M1 aggregation. A configured source is
                        # never silently replaced when missing.
                        tf_bars = resample(m1_full, tf)  # type: ignore[arg-type]
                        tf_clean = clean(tf_bars, tz=tz)
                        df = add_session_labels(tf_clean, tz=tz, ny_end=ny_end)
                        df = add_session_id(df)
                    write_bar_cache(cp, df, cache_identity)
                parts[str(symbol)][str(tf)].append(df)

    result: dict[str, dict[str, pd.DataFrame]] = {}
    for symbol, timeframes in parts.items():
        result[symbol] = {}
        for tf, frames in timeframes.items():
            combined = pd.concat(frames).sort_index()
            if combined.index.has_duplicates:
                raise ValueError(f"overlapping {tf} rows in configured data splits for {symbol}")
            result[symbol][tf] = combined
    return result
