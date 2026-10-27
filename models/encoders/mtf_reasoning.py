"""Small cross-timeframe attention model over causal per-timeframe TCN tokens."""

from __future__ import annotations

from typing import Any

import torch
from torch import nn

from models.encoders.mtf import MTFEncoder


class MTFReasoningEncoder(MTFEncoder):
    """Preserve MTF's causal branches and add one learned cross-timeframe block."""

    def __init__(
        self,
        observation_space: Any,
        latent_dim: int = 128,
        channels: tuple[int, ...] = (128, 128, 256, 256),
        kernel_size: int = 3,
        dropout: float = 0.1,
        account_dim: int | None = None,
        attention_heads: int = 4,
        feedforward_dim: int = 256,
    ) -> None:
        if latent_dim % attention_heads:
            raise ValueError("latent_dim must be divisible by attention_heads")
        super().__init__(
            observation_space,
            latent_dim=latent_dim,
            channels=channels,
            kernel_size=kernel_size,
            dropout=dropout,
            account_dim=account_dim,
        )
        # The MTF concatenation projection is not used by this architecture.
        del self.fuse
        stream_order = {
            "seq": 0,
            "seq_m3": 1,
            "seq_m5": 2,
            "seq_m10": 3,
            "seq_m15": 4,
            "seq_m30": 5,
            "seq_h1": 6,
            "seq_h4": 7,
            "seq_d1": 8,
        }
        self._timeframe_ids = tuple(stream_order[seq_key] for seq_key, _ in self._keys)
        self.timeframe_embedding = nn.Embedding(len(stream_order), latent_dim)
        layer = nn.TransformerEncoderLayer(
            d_model=latent_dim,
            nhead=attention_heads,
            dim_feedforward=feedforward_dim,
            dropout=dropout,
            batch_first=True,
            norm_first=True,
        )
        self.cross_timeframe = nn.TransformerEncoder(layer, num_layers=1)
        self.market_norm = nn.LayerNorm(latent_dim)

    def forward(self, observations: dict[str, torch.Tensor]) -> torch.Tensor:
        tokens = torch.stack(
            [
                branch(observations[seq_key], observations[mask_key])
                for branch, (seq_key, mask_key) in zip(self.branches, self._keys, strict=True)
            ],
            dim=1,
        )
        valid = torch.stack(
            [observations[mask_key].sum(dim=1) > 0.0 for _, mask_key in self._keys],
            dim=1,
        )
        empty_rows = ~valid.any(dim=1)
        if bool(empty_rows.any()):
            valid = valid.clone()
            valid[empty_rows, 0] = True
        ids = torch.as_tensor(self._timeframe_ids, device=tokens.device, dtype=torch.long)
        tokens = tokens + self.timeframe_embedding(ids).unsqueeze(0)
        tokens = self.cross_timeframe(tokens, src_key_padding_mask=~valid)
        weights = valid.to(dtype=tokens.dtype).unsqueeze(-1)
        pooled = (tokens * weights).sum(dim=1) / weights.sum(dim=1).clamp_min(1.0)
        market = self.market_norm(pooled)
        return torch.cat((market, self.account_mlp(observations["account"])), dim=1)


__all__ = ["MTFReasoningEncoder"]
