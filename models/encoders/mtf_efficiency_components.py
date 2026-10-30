"""Shared, small helpers for the experimental efficient MTF encoders."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import torch
from torch import nn

from models.encoders.mtf import _MTF_STREAMS
from models.encoders.sequence_encoder_components import (
    ACCOUNT_EMB_DIM,
    AccountMLP,
    BaseFeaturesExtractor,
    _resolve_account_dim,
)

_TIMEFRAME_IDS = {
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


def observation_streams(observation_space: Any) -> tuple[tuple[str, str, int, int], ...]:
    """Return the complete ordered M1+HTF stream contract from a Dict space."""
    spaces_map = getattr(observation_space, "spaces", None)
    if not isinstance(spaces_map, Mapping):
        raise TypeError("efficient MTF encoders require a Dict observation space")
    streams: list[tuple[str, str, int, int]] = []
    for seq_key, mask_key in _MTF_STREAMS:
        if seq_key not in spaces_map or mask_key not in spaces_map:
            raise ValueError(f"efficient MTF encoders require {seq_key} and {mask_key}")
        shape = getattr(spaces_map[seq_key], "shape", None)
        mask_shape = getattr(spaces_map[mask_key], "shape", None)
        if shape is None or len(shape) != 2:
            raise TypeError(f"{seq_key} must have a (window, features) shape")
        if mask_shape != (int(shape[0]),):
            raise ValueError(f"{mask_key} must match the {seq_key} window")
        streams.append((seq_key, mask_key, int(shape[0]), int(shape[1])))
    if "account" not in spaces_map:
        raise ValueError("efficient MTF encoders require an account observation")
    return tuple(streams)


def batch_mask(mask: torch.Tensor, batch_size: int, timesteps: int) -> torch.Tensor:
    """Normalize an observation mask to a boolean ``(B,T)`` tensor."""
    if mask.ndim == 1:
        mask = mask.unsqueeze(0)
    if mask.shape[-1] != timesteps:
        raise ValueError(f"mask length {mask.shape[-1]} does not match window {timesteps}")
    if mask.shape[0] == 1 and batch_size > 1:
        mask = mask.expand(batch_size, -1)
    if mask.shape[0] != batch_size:
        raise ValueError("mask batch size does not match sequence batch size")
    return mask.to(dtype=torch.bool)


def latest_two_valid(
    values: torch.Tensor, mask: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Return latest, previous, and any-valid values without host synchronization."""
    batch, timesteps, _ = values.shape
    valid = batch_mask(mask, batch, timesteps).to(device=values.device)
    positions = torch.arange(timesteps, device=values.device).expand(batch, -1)
    last_positions = torch.where(valid, positions, -1)
    last_index = last_positions.max(dim=1).values
    has_last = last_index >= 0
    previous_positions = torch.where(valid & (positions < last_index[:, None]), positions, -1)
    previous_index = previous_positions.max(dim=1).values
    has_previous = previous_index >= 0
    last = values.gather(1, last_index.clamp_min(0)[:, None, None].expand(-1, 1, values.shape[-1]))
    previous = values.gather(
        1, previous_index.clamp_min(0)[:, None, None].expand(-1, 1, values.shape[-1])
    )
    last = last.squeeze(1) * has_last[:, None].to(values.dtype)
    previous = previous.squeeze(1) * has_previous[:, None].to(values.dtype)
    return last, previous, has_last


class MTFReasoningOutput(BaseFeaturesExtractor):
    """Common attention and account head for a fixed nine-stream MTF encoder."""

    def __init__(
        self,
        observation_space: Any,
        *,
        latent_dim: int,
        account_dim: int | None,
        attention_heads: int,
        feedforward_dim: int,
        dropout: float,
    ) -> None:
        if latent_dim % attention_heads:
            raise ValueError("latent_dim must be divisible by attention_heads")
        super().__init__(observation_space, features_dim=latent_dim + ACCOUNT_EMB_DIM)
        resolved_account_dim = _resolve_account_dim(observation_space, account_dim)
        self.latent_dim = latent_dim
        self.attention_heads = attention_heads
        self.feedforward_dim = feedforward_dim
        self.account_mlp = AccountMLP(resolved_account_dim)
        self.timeframe_embedding = nn.Embedding(len(_TIMEFRAME_IDS), latent_dim)
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
        self.register_buffer(
            "timeframe_ids",
            torch.tensor(tuple(_TIMEFRAME_IDS.values()), dtype=torch.long),
            persistent=True,
        )

    def finish(
        self, tokens: torch.Tensor, valid: torch.Tensor, account: torch.Tensor
    ) -> torch.Tensor:
        """Apply D-shaped timeframe attention, masked pooling, and account embedding."""
        if tokens.ndim != 3 or tokens.shape[1:] != (len(_TIMEFRAME_IDS), self.latent_dim):
            raise ValueError("MTF tokens must have shape (batch, 9, latent_dim)")
        if valid.shape != tokens.shape[:2]:
            raise ValueError("MTF validity mask must have shape (batch, 9)")
        # Transformer attention cannot accept a row with every token masked. Use a
        # neutral M1 placeholder only for those rows; no missing stream is exposed.
        empty = ~valid.any(dim=1)
        tokens = torch.where(empty[:, None, None], torch.zeros_like(tokens), tokens)
        valid = valid.clone()
        valid[:, 0] = valid[:, 0] | empty
        tokens = tokens + self.timeframe_embedding(self.timeframe_ids).unsqueeze(0)
        attended = self.cross_timeframe(tokens, src_key_padding_mask=~valid)
        weights = valid.to(dtype=attended.dtype).unsqueeze(-1)
        pooled = (attended * weights).sum(dim=1) / weights.sum(dim=1).clamp_min(1.0)
        market = cast(torch.Tensor, self.market_norm(pooled))
        return torch.cat((market, self.account_mlp(account)), dim=1)
