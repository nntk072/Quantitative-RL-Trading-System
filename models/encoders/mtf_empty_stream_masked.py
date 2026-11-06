"""Versioned MTF encoder that excludes entirely unavailable timeframe streams."""

from __future__ import annotations

import torch

from models.encoders.mtf import MTFEncoder


class MTFEmptyStreamMaskedV1Encoder(MTFEncoder):
    """Preserve MTFEncoder's parameters while zeroing unavailable stream tokens.

    The historical ``mtf`` architecture encodes an all-zero stream mask as one
    timestep because its shared length helper clamps empty masks to length one.
    This version applies an explicit stream-presence gate after each branch.
    Its parameter names and shapes match ``MTFEncoder`` so weights can be
    initialized from a legacy checkpoint, while the distinct architecture ID
    records the changed inference semantics.
    """

    encoder_provenance = {
        "encoder_id": "mtf_empty_stream_masked_v1",
        "stream_mask_semantics": "zero latent for streams with no valid timesteps",
        "parameter_schema": "mtf_v1",
    }

    def forward(self, observations: dict[str, torch.Tensor]) -> torch.Tensor:
        """Encode timeframe streams, excluding any stream with no valid rows.

        Args:
            observations: Sequence, validity-mask, and account tensors keyed by stream.

        Returns:
            Fused market latent concatenated with the encoded account state.
        """
        parts: list[torch.Tensor] = []
        for branch, (seq_key, mask_key) in zip(self.branches, self._keys, strict=True):
            latent = branch(observations[seq_key], observations[mask_key])
            present = (observations[mask_key].sum(dim=1) > 0.0).to(latent.dtype)
            parts.append(latent * present.unsqueeze(-1))
        latent = self.fuse(torch.cat(parts, dim=1))
        return torch.cat([latent, self.account_mlp(observations["account"])], dim=1)


__all__ = ["MTFEmptyStreamMaskedV1Encoder"]
