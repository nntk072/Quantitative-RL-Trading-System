"""Versioned slow-regime observation coordinates used by regime-aware policies."""

from __future__ import annotations

import hashlib
import json
from typing import Any

REGIME_FEATURE_VERSION = "completed-d1-technical-v1"
REGIME_FEATURES: tuple[str, ...] = (
    "D1_ret_5",
    "D1_ret_30",
    "D1_ema_21_dist",
    "D1_ema_50_dist",
    "D1_ema_200_dist",
    "D1_adx",
    "D1_realized_vol",
)
REGIME_MASK_SEMANTICS = "per_feature_finite_value_is_1; missing_value_is_0_and_zero_filled"
REGIME_NORMALIZATION_SEMANTICS = (
    "selected D1 technical features normalized on source index with train-only statistics"
)


def regime_observation_schema() -> dict[str, Any]:
    """Return stable names and semantics for the compact D1 context vector."""
    payload = {
        "version": "slow-regime-observation-v1",
        "feature_version": REGIME_FEATURE_VERSION,
        "features": list(REGIME_FEATURES),
        "mask_coordinates": [f"valid:{name}" for name in REGIME_FEATURES],
        "mask_semantics": REGIME_MASK_SEMANTICS,
        "normalization_semantics": REGIME_NORMALIZATION_SEMANTICS,
        "availability": "last completed D1 feature value causally aligned to the M1 decision row",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["feature_hash"] = hashlib.sha256(canonical).hexdigest()
    return payload
