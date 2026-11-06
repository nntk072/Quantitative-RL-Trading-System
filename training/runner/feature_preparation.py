"""Fit-scope aware feature construction for date-split research runners."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from omegaconf import DictConfig

from features import build_features, feature_cache_path
from market_data.splits.definitions import make_train_mask


def build_split_scoped_features(
    primary: pd.DataFrame,
    *,
    cfg: DictConfig | None,
    train_end: str,
    train_start: str | None = None,
    secondary: pd.DataFrame | None = None,
    cache_dir: Path | str | None = None,
    symbol: str | None = None,
    force: bool = False,
) -> pd.DataFrame:
    """Build features with normalization fitted only on development rows.

    Args:
        primary: Primary market bars in chronological order.
        cfg: Resolved feature configuration.
        train_end: Inclusive last training date.
        train_start: Optional inclusive first training date.
        secondary: Optional secondary-symbol bars.
        cache_dir: Optional content-addressed feature-cache directory.
        symbol: Primary symbol, required when ``cache_dir`` is provided.
        force: Rebuild the cache when one is used.

    Returns:
        Feature rows aligned to ``primary``.
    """
    if not isinstance(primary.index, pd.DatetimeIndex):
        raise TypeError("split-scoped feature construction requires a DatetimeIndex")

    train_mask = make_train_mask(primary.index, train_end, train_start)
    cache_path = None
    if cache_dir is not None:
        if not symbol:
            raise ValueError("symbol is required when feature caching is enabled")
        cache_path = feature_cache_path(
            cache_dir,
            symbol,
            cfg,
            primary,
            train_mask=train_mask,
            secondary=secondary,
        )

    return build_features(
        primary,
        secondary=secondary,
        cfg=cfg,
        train_mask=train_mask,
        cache_path=cache_path,
        force=force,
    )
