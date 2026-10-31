"""Dependency-light identifiers for policy encoder architectures.

This module intentionally contains no model imports so launch-time config
resolution can validate architecture names before Torch is initialized.
"""

ENCODER_ARCHITECTURE_IDS: tuple[str, ...] = (
    "tcn",
    "tcn_regime",
    "lite_tcn",
    "gru",
    "transformer",
    "mtf",
    "mtf_reasoning",
    "mtf_shared_tcn_reasoning",
    "mtf_m1_tcn_htf_lite_reasoning",
    "mtf_m1_tcn_htf_snapshot_reasoning",
)

__all__ = ["ENCODER_ARCHITECTURE_IDS"]
