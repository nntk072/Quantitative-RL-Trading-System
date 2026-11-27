"""Fail-closed admission rules for the VAE research candidate."""

from __future__ import annotations

VAE_NO_GO_REASON = (
    "VAE training and policy use are blocked by the current evidence contract: "
    "the configured sequence file has no session dates, leading padding has no "
    "validity mask, and its random split does not establish chronological "
    "train-only fitting. See evidence/research/vae_input_validity/README.md. "
    "Reopen this path only after dated sequence provenance, validity-masked "
    "reconstruction, and chronological fitting are implemented and verified."
)


def require_vae_candidate_admissible(enabled: bool) -> None:
    """Reject VAE use until its dated, validity-masked evidence contract passes.

    Args:
        enabled: Whether the caller requests VAE pretraining or policy use.

    Raises:
        ValueError: If the caller enables the currently unqualified VAE path.
    """
    if enabled:
        raise ValueError(VAE_NO_GO_REASON)


__all__ = ["VAE_NO_GO_REASON", "require_vae_candidate_admissible"]
