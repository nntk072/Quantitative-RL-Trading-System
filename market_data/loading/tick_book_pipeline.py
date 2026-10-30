"""Build and join configured tick-book partitions for market-data datasets."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from omegaconf import DictConfig

from market_data.loading.ticks import TICK_CACHE_VERSION, TickBook, build_tick_book
from market_data.transforms.price_grid import (
    configured_price_grid_increment,
    tick_cache_filename,
)

log = logging.getLogger(__name__)


def build_tick_books(
    cfg: DictConfig,
    force: bool = False,
    symbols: Sequence[str] | None = None,
    datasets: Sequence[str] | None = None,
) -> dict[str, TickBook | None]:
    """Build (or load from cache) a ``TickBook`` for each selected symbol.

    By default, include every configured symbol. ``symbols`` narrows the load
    when a caller only consumes a subset, avoiding unnecessary large tick
    arrays. Returns ``{symbol: TickBook | None}``, where ``None`` means the
    tick file was not configured or does not exist. Ticks are stored for the
    full day so overnight replay can quote skipped bars.
    """
    configured_symbols = [str(sym) for sym in cfg.data.symbols]
    selected_symbols = (
        configured_symbols if symbols is None else list(dict.fromkeys(str(sym) for sym in symbols))
    )
    unknown_symbols = set(selected_symbols).difference(configured_symbols)
    if unknown_symbols:
        raise ValueError(f"requested tick symbols are not configured: {sorted(unknown_symbols)}")

    try:
        use_ticks = bool(cfg.costs.use_tick_execution)
    except Exception:
        use_ticks = True

    result: dict[str, TickBook | None] = {}

    if not use_ticks:
        log.info("Tick execution disabled (costs.use_tick_execution=false)")
        for sym in selected_symbols:
            result[sym] = None
        return result

    cache_dir = Path(cfg.data.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    configured_sets = cfg.data.get("datasets")
    if configured_sets:
        tick_sources = [
            (
                str(name),
                Path(str(spec.raw_dir)),
                dict(spec.get("tick_files", {})),
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
        tick_sources = [
            (
                "all",
                Path(str(cfg.data.raw_dir)),
                dict(cfg.data.get("tick_files", {})),
            )
        ]

    grid_increment = configured_price_grid_increment(cfg)
    for sym in selected_symbols:
        books: list[TickBook] = []
        for dataset_name, raw_dir, tick_files in tick_sources:
            tick_file = tick_files.get(sym)
            if not tick_file:
                log.warning("No %s tick file configured for %s", dataset_name, sym)
                continue
            tick_path = raw_dir / str(tick_file)
            if not tick_path.exists():
                log.warning("Tick file not found: %s", tick_path)
                continue
            cache_scope = str(dataset_name) if configured_sets else ""
            cache_p = (
                cache_dir
                / cache_scope
                / tick_cache_filename(sym, grid_increment, TICK_CACHE_VERSION)
            )
            cache_p.parent.mkdir(parents=True, exist_ok=True)
            try:
                book = build_tick_book(
                    path=tick_path,
                    tz=cfg.data.tz,
                    session_start=None,
                    session_end=None,
                    cache_path=cache_p,
                    force=force,
                    price_grid_increment=grid_increment,
                )
                if book is not None and len(book) > 0:
                    books.append(book)
            except Exception as exc:  # noqa: BLE001
                log.warning("Failed to build TickBook for %s: %s", tick_path, exc)
                result[sym] = None
                books = []
                break
        if books:
            if any(books[i]._ts[-1] >= books[i + 1]._ts[0] for i in range(len(books) - 1)):
                raise ValueError(
                    f"configured tick partitions overlap or are out of order for {sym}"
                )
            import numpy as np

            combined_book = TickBook(
                np.concatenate([book._ts for book in books]),
                np.concatenate([book._bid for book in books]),
                np.concatenate([book._ask for book in books]),
            )
            result[sym] = combined_book
            log.info(
                "TickBook ready: %s (%d ticks, %d partitions)", sym, len(combined_book), len(books)
            )
        elif sym not in result:
            log.warning("No usable tick partitions for %s — using bar-spread fallback", sym)
            result[sym] = None

    return result
