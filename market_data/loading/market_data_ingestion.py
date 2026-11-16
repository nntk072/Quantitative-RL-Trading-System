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
from typing import Any

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
from market_data.splits.definitions import inclusive_date_exclusive_end
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


def _preflight_bar_sources(
    dataset_specs: Sequence[tuple[str, Path, Any, Any, Any, Any]],
    symbols: Sequence[str],
    timeframes: Sequence[str],
    *,
    end_inclusive: str | None,
) -> None:
    """Reject raw chronology conflicts before the run publishes any bar cache.

    Args:
        dataset_specs: Dataset roots and per-symbol source file mappings.
        symbols: Symbols selected for this pipeline run.
        timeframes: Native timeframes selected for this pipeline run.
        end_inclusive: Optional last local calendar date to include.
    """
    source_indices: dict[tuple[str, str], list[pd.Index]] = {}
    for dataset_name, root, m1_files, timeframe_files, start_date, end_date in dataset_specs:
        source_start = pd.Timestamp(str(start_date)).normalize() if start_date else None
        if start_date and end_date and str(start_date) > str(end_date):
            raise ValueError(
                f"dataset {dataset_name!r} has start_date after end_date: {start_date} > {end_date}"
            )
        source_end_date = end_date
        if end_inclusive is not None and (
            source_end_date is None or str(end_inclusive) < str(source_end_date)
        ):
            source_end_date = end_inclusive
        raw_exclusive_end = (
            pd.Timestamp(str(source_end_date)).normalize() + pd.DateOffset(days=1)
            if source_end_date is not None
            else None
        )
        for symbol in symbols:
            configured_m1 = timeframe_files.get("M1", {}).get(symbol)
            paths = [("M1", root / str(configured_m1 or m1_files[symbol]))]
            paths.extend(
                (str(timeframe), root / str(native_file))
                for timeframe in timeframes
                if (native_file := timeframe_files.get(str(timeframe), {}).get(symbol))
            )
            seen_paths: set[Path] = set()
            for timeframe, path in paths:
                if path in seen_paths:
                    continue
                seen_paths.add(path)
                source = load_bars(
                    path,
                    start_inclusive=source_start,
                    end_exclusive=raw_exclusive_end,
                )
                diagnostics = source.attrs.get("source_diagnostics", {})
                if diagnostics.get("out_of_order_rows", 0) or diagnostics.get(
                    "conflicting_duplicate_timestamps", 0
                ):
                    raise ValueError(
                        f"rejected bar source {path}: chronology/duplicate diagnostics "
                        f"{diagnostics}"
                    )
                key = (symbol, timeframe)
                previous = source_indices.setdefault(key, [])
                if any(len(source.index.intersection(index)) for index in previous):
                    raise ValueError(
                        f"overlapping {timeframe} rows across configured data splits "
                        f"for {symbol}; rejected before cache publication"
                    )
                previous.append(source.index)


def run_pipeline(
    cfg: DictConfig,
    force: bool = False,
    datasets: Sequence[str] | None = None,
    end_inclusive: str | None = None,
) -> dict[str, dict[str, pd.DataFrame]]:
    """Load, resample, clean, label and cache all symbols / timeframes.

    Full-day M1 is kept for every timeframe. ``filter_session`` is not applied.

    Args:
        cfg: OmegaConf config (config/base/default.yaml).
        force: If True, ignore existing parquet cache and reprocess from CSV.
        datasets: Optional configured dataset names to process; None selects all datasets.
        end_inclusive: Optional last local calendar date returned to the caller.

    Returns:
        Mapping from ``str`` keys to ``dict[str, pd.DataFrame]`` values.
    """
    cache_dir = Path(cfg.data.cache_dir)
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
                spec.get("start_date"),
                spec.get("end_date"),
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
        dataset_specs = [("all", Path(str(cfg.data.raw_dir)), cfg.data.m1_files, {}, None, None)]

    _preflight_bar_sources(
        dataset_specs,
        [str(symbol) for symbol in cfg.data.symbols],
        [str(timeframe) for timeframe in cfg.data.timeframes],
        end_inclusive=end_inclusive,
    )

    parts: dict[str, dict[str, list[pd.DataFrame]]] = {
        str(symbol): {str(tf): [] for tf in cfg.data.timeframes} for symbol in cfg.data.symbols
    }
    exclusive_end = (
        inclusive_date_exclusive_end(end_inclusive, tz) if end_inclusive is not None else None
    )
    if exclusive_end is None:
        cache_dir.mkdir(parents=True, exist_ok=True)
    for dataset_name, root, m1_files, timeframe_files, start_date, end_date in dataset_specs:
        part_cache = cache_dir / dataset_name
        if exclusive_end is None:
            part_cache.mkdir(parents=True, exist_ok=True)
        for symbol in cfg.data.symbols:
            configured_m1 = timeframe_files.get("M1", {}).get(symbol)
            m1_path = root / str(configured_m1 or m1_files[symbol])
            source_start = pd.Timestamp(str(start_date)).normalize() if start_date else None
            configured_end = pd.Timestamp(str(end_date)).normalize() if end_date else None
            if (
                source_start is not None
                and configured_end is not None
                and source_start > configured_end
            ):
                raise ValueError(
                    f"dataset {dataset_name!r} has start_date after end_date: "
                    f"{source_start.date()} > {configured_end.date()}"
                )
            source_end_date = end_date
            if end_inclusive is not None and (
                source_end_date is None or str(end_inclusive) < str(source_end_date)
            ):
                source_end_date = end_inclusive
            raw_exclusive_end = (
                pd.Timestamp(str(source_end_date)).normalize() + pd.DateOffset(days=1)
                if source_end_date is not None
                else None
            )
            m1_raw = quantize_bar_prices(
                load_bars(m1_path, start_inclusive=source_start, end_exclusive=raw_exclusive_end),
                grid_increment,
            )
            source_hashes = {} if exclusive_end is not None else {m1_path: file_sha256(m1_path)}
            if m1_raw.empty:
                for timeframe in cfg.data.timeframes:
                    parts[str(symbol)][str(timeframe)].append(
                        pd.DataFrame(index=pd.DatetimeIndex([], tz=tz, name="datetime"))
                    )
                continue

            def input_hash(path: Path) -> str:
                """Return a memoized content hash for a source file.

                Args:
                    path: Raw market-data file to fingerprint.

                Returns:
                    SHA-256 digest used in the cache identity.
                """
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
                cache_identity = None
                source_path = m1_path
                if tf != "M1" and native_file:
                    source_path = root / str(native_file)
                    if not source_path.is_file():
                        raise FileNotFoundError(
                            f"configured native {tf} source for {symbol} is missing: {source_path}"
                        )
                elif tf != "M1":
                    allowed_derived = [
                        str(value).upper() for value in derived_timeframes.get(symbol, [])
                    ]
                    if require_native_timeframes and tf not in allowed_derived:
                        raise FileNotFoundError(
                            f"native {tf} source for {symbol} is required but not configured; "
                            "declare an intentional M1-derived timeframe explicitly to proceed"
                        )
                if exclusive_end is None:
                    if tf == "M1":
                        source_identity = f"native:{input_hash(source_path)}{grid_identity}"
                    elif native_file:
                        source_identity = f"native:{input_hash(source_path)}{grid_identity}"
                    else:
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
                        start_inclusive=str(start_date) if start_date else None,
                        end_inclusive=str(source_end_date) if source_end_date else None,
                        price_grid_identity=(
                            price_grid_identity(grid_increment)
                            if grid_increment is not None
                            else None
                        ),
                    )
                cached_frame = (
                    None if force or cache_identity is None else load_bar_cache(cp, cache_identity)
                )
                if cached_frame is not None:
                    df = cached_frame
                else:
                    if tf == "M1":
                        df = m1_full.copy()
                    elif native_file:
                        tf_raw = quantize_bar_prices(
                            load_bars(
                                source_path,
                                start_inclusive=source_start,
                                end_exclusive=raw_exclusive_end,
                            ),
                            grid_increment,
                        )
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
                    if end_inclusive is None:
                        if cache_identity is None:
                            raise AssertionError("full-span bar processing requires cache identity")
                        write_bar_cache(cp, df, cache_identity)
                if exclusive_end is not None:
                    df = df.loc[df.index < exclusive_end]
                parts[str(symbol)][str(tf)].append(df)

    result: dict[str, dict[str, pd.DataFrame]] = {}
    for symbol, timeframes in parts.items():
        result[symbol] = {}
        for tf, frames in timeframes.items():
            combined = pd.concat(frames).sort_index()
            if combined.index.has_duplicates:
                raise ValueError(f"overlapping {tf} rows in configured data splits for {symbol}")
            diagnostic_keys = (
                "out_of_order_rows",
                "duplicate_rows",
                "conflicting_duplicate_timestamps",
            )
            combined.attrs["source_diagnostics"] = {
                key: sum(
                    int(frame.attrs.get("source_diagnostics", {}).get(key, 0)) for frame in frames
                )
                for key in diagnostic_keys
            }
            result[symbol][tf] = combined
    return result
