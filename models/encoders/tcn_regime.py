"""TCN encoder with a separate compact completed-D1 regime context branch."""

from __future__ import annotations

from typing import Any

import torch
import torch.nn as nn

from decisioning.regime_observations import REGIME_FEATURES

from .tcn import TCNEncoder


class TCNRegimeEncoder(TCNEncoder):
    """Keep the established TCN/account path and fuse a masked D1 context MLP."""

    regime_embedding_dim = 16

    def __init__(self, observation_space: Any, **kwargs: Any) -> None:
        spaces_map = getattr(observation_space, "spaces", {})
        regime_space = spaces_map.get("regime")
        mask_space = spaces_map.get("regime_mask")
        if regime_space is None or mask_space is None:
            raise ValueError("tcn_regime requires regime and regime_mask observations")
        regime_shape = tuple(getattr(regime_space, "shape", ()))
        mask_shape = tuple(getattr(mask_space, "shape", ()))
        expected_shape = (len(REGIME_FEATURES),)
        if regime_shape != expected_shape or mask_shape != expected_shape:
            raise ValueError(
                f"tcn_regime expects D1 regime and mask shape {expected_shape}; "
                f"got {regime_shape} and {mask_shape}"
            )
        super().__init__(observation_space, **kwargs)
        self.regime_mlp = nn.Sequential(
            nn.Linear(2 * len(REGIME_FEATURES), 32),
            nn.LayerNorm(32),
            nn.SiLU(),
            nn.Linear(32, self.regime_embedding_dim),
        )
        self.features_dim += self.regime_embedding_dim

    def forward(self, observations: dict[str, torch.Tensor]) -> torch.Tensor:
        base = super().forward(observations)
        regime = observations["regime"]
        mask = observations["regime_mask"].to(dtype=regime.dtype)
        embedding = self.regime_mlp(torch.cat((regime, mask), dim=1))
        any_valid = (mask.sum(dim=1, keepdim=True) > 0).to(dtype=embedding.dtype)
        embedding = embedding * any_valid
        return torch.cat((base, embedding), dim=1)
