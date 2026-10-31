"""Resolve stable architecture names to reusable sequence encoder classes."""

from __future__ import annotations

from typing import Any

from models.architecture_ids import ENCODER_ARCHITECTURE_IDS
from models.encoders import (
    GRUEncoder,
    LiteTCNEncoder,
    M1TCNHTFLiteReasoningEncoder,
    M1TCNHTFSnapshotReasoningEncoder,
    MTFEncoder,
    MTFReasoningEncoder,
    SharedTCNMTFReasoningEncoder,
    TCNEncoder,
    TCNRegimeEncoder,
    TransformerEncoder,
)

ENCODER_TYPES: dict[str, type[Any]] = {
    "tcn": TCNEncoder,
    "tcn_regime": TCNRegimeEncoder,
    "transformer": TransformerEncoder,
    "gru": GRUEncoder,
    "mtf": MTFEncoder,
    "mtf_reasoning": MTFReasoningEncoder,
    "lite_tcn": LiteTCNEncoder,
    "mtf_shared_tcn_reasoning": SharedTCNMTFReasoningEncoder,
    "mtf_m1_tcn_htf_lite_reasoning": M1TCNHTFLiteReasoningEncoder,
    "mtf_m1_tcn_htf_snapshot_reasoning": M1TCNHTFSnapshotReasoningEncoder,
}

if set(ENCODER_TYPES) != set(ENCODER_ARCHITECTURE_IDS):
    raise RuntimeError("encoder implementation registry differs from architecture identifiers")


def encoder_for(architecture: str) -> type[Any]:
    """Resolve a declared encoder ID, failing closed for unknown names."""
    try:
        return ENCODER_TYPES[architecture]
    except KeyError as exc:
        raise ValueError(f"unknown encoder architecture: {architecture!r}") from exc


__all__ = ["ENCODER_TYPES", "encoder_for"]
