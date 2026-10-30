"""Train-fold-only feature fitting for chronological walk-forward evaluation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from omegaconf import DictConfig

from features.pipeline.feature_cache_identity import feature_cache_path


def build_walkforward_fold_features(
    primary: pd.DataFrame,
    secondary: pd.DataFrame | None,
    cfg: DictConfig,
    fold_train_bars: pd.DataFrame,
    fold_validation_bars: pd.DataFrame,
    cache_dir: Path | str,
    symbol: str,
) -> tuple[pd.DataFrame, pd.DataFrame, Path]:
    """Refit normalization on one fold with causal warm-up bars.

    Keep all historical bars through the fold's validation end as indicator
    context, but fit normalization only on the fold's train indices. Later
    folds and the locked evaluation period cannot influence this fitted state.
    """
    if (
        primary.empty
        or fold_train_bars.empty
        or fold_validation_bars.empty
        or not primary.index.is_unique
        or not primary.index.is_monotonic_increasing
    ):
        raise ValueError("Walk-forward requires nonempty, unique, ordered bars")
    train_index = fold_train_bars.index
    validation_index = fold_validation_bars.index
    if (
        not train_index.isin(primary.index).all()
        or not validation_index.isin(primary.index).all()
        or train_index.max() >= validation_index.min()
        or train_index.intersection(validation_index).size
    ):
        raise ValueError("Walk-forward train/validation indices must be ordered and disjoint")

    last_validation_bar = validation_index.max()
    context_primary = primary.loc[:last_validation_bar]
    context_secondary = secondary.loc[:last_validation_bar] if secondary is not None else None
    fold_mask = pd.Series(context_primary.index.isin(train_index), index=context_primary.index)
    cache = feature_cache_path(
        cache_dir,
        symbol,
        cfg,
        context_primary,
        train_mask=fold_mask,
        secondary=context_secondary,
        normalization_mode="frozen_fold",
    )
    from features import build_features

    features = build_features(
        context_primary,
        secondary=context_secondary,
        cfg=cfg,
        train_mask=fold_mask,
        cache_path=cache,
        normalization_mode="frozen_fold",
    )
    return features.loc[train_index], features.loc[validation_index], cache
