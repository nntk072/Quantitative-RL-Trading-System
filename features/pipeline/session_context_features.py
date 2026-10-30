"""Session-relative distance features used by the feature matrix pipeline."""

from __future__ import annotations

import pandas as pd


def ensure_london_atr_distances(feat: pd.DataFrame, close: pd.Series) -> pd.DataFrame:
    """Add London ATR distances when the PD-context pair is absent.

    ``price_to_london_high_atr = (london_high - close) / atr_5``
    ``price_to_london_low_atr = (close - london_low) / atr_5``
    """
    if "ctx_london_high_dist_atr" in feat.columns and "ctx_london_low_dist_atr" in feat.columns:
        return feat
    needed = ("london_high", "london_low", "atr_5")
    if any(col not in feat.columns for col in needed):
        return feat
    atr5 = feat["atr_5"].where(feat["atr_5"] > 0)
    aligned_close = close.reindex(feat.index)
    feat = feat.copy()
    feat["price_to_london_high_atr"] = (feat["london_high"] - aligned_close) / atr5
    feat["price_to_london_low_atr"] = (aligned_close - feat["london_low"]) / atr5
    return feat
