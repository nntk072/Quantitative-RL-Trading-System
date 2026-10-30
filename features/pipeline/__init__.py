"""Causal feature assembly, observation selection, normalization, and cache identity."""

from features.context.reachability import attach_reachable_r

from .feature_cache_identity import (
    FEATURE_CACHE_VERSION,
    feature_cache_content_hash,
    feature_cache_path,
)
from .feature_matrix_builder import build_features
from .normalization import rolling_zscore
from .schema import OBS_RAW_PRICE_COLUMNS, select_legacy_obs_columns, select_obs_columns
from .session_context_features import ensure_london_atr_distances
from .walkforward_feature_fitting import build_walkforward_fold_features

__all__ = [
    "FEATURE_CACHE_VERSION",
    "OBS_RAW_PRICE_COLUMNS",
    "attach_reachable_r",
    "build_features",
    "build_walkforward_fold_features",
    "ensure_london_atr_distances",
    "feature_cache_content_hash",
    "feature_cache_path",
    "rolling_zscore",
    "select_legacy_obs_columns",
    "select_obs_columns",
]
