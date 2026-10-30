"""Shared-weight TCN alternative for nine-stream MTF reasoning."""

from __future__ import annotations

from typing import Any, cast

import torch
from torch import nn
from torch.nn import functional as F

from models.encoders.mtf_efficiency_components import (
    MTFReasoningOutput,
    batch_mask,
    observation_streams,
)
from models.encoders.tcn import _TemporalBlock


class _SharedTCNCore(nn.Module):
    """One temporal core applied to the M1 and grouped HTF batches."""

    def __init__(
        self,
        input_dim: int,
        latent_dim: int,
        channels: tuple[int, ...],
        kernel_size: int,
        dropout: float,
    ) -> None:
        super().__init__()
        if not channels:
            raise ValueError("channels must contain at least one width")
        self.channels = tuple(channels)
        self.tcn = nn.Sequential(
            *(
                _TemporalBlock(
                    input_dim if index == 0 else self.channels[index - 1],
                    out_channels,
                    kernel_size,
                    2**index,
                    dropout,
                )
                for index, out_channels in enumerate(self.channels)
            )
        )
        self.proj = nn.Linear(self.channels[-1], latent_dim)

    def forward(self, seq: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        hidden = seq.transpose(1, 2)
        valid = mask.to(device=hidden.device, dtype=hidden.dtype).unsqueeze(1)
        # Keep convolution biases from creating artificial pre-history state in
        # left padding that later causal blocks could otherwise consume.
        for block in self.tcn:
            hidden = block(hidden)
            hidden = hidden * valid
        return cast(torch.Tensor, self.proj(hidden[:, :, -1]))


class SharedTCNMTFReasoningEncoder(MTFReasoningOutput):
    """One shared causal TCN processes all nine timeframe streams."""

    encoder_id = "mtf_shared_tcn_reasoning"

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
        adapter_dim: int = 64,
    ) -> None:
        if adapter_dim < 1:
            raise ValueError("adapter_dim must be positive")
        super().__init__(
            observation_space,
            latent_dim=latent_dim,
            account_dim=account_dim,
            attention_heads=attention_heads,
            feedforward_dim=feedforward_dim,
            dropout=dropout,
        )
        self.streams = observation_streams(observation_space)
        self.adapter_dim = adapter_dim
        self.branch_count = len(self.streams)
        self.shared_core = True
        self.adapters = nn.ModuleList(
            nn.Linear(feature_count, adapter_dim) for _, _, _, feature_count in self.streams
        )
        self.temporal_core = _SharedTCNCore(
            adapter_dim, latent_dim, tuple(channels), kernel_size, dropout
        )
        self.channels = tuple(channels)
        self.kernel_size = kernel_size

    @property
    def encoder_provenance(self) -> dict[str, Any]:
        return {
            "encoder_id": self.encoder_id,
            "adapter_width": self.adapter_dim,
            "branch_count": self.branch_count,
            "shared_core": self.shared_core,
            "token_dim": self.latent_dim,
            "latent_dim": self.latent_dim,
            "attention_heads": self.attention_heads,
            "attention_feedforward_dim": self.feedforward_dim,
            "htf_summary_type": "shared_causal_tcn",
        }

    def forward(self, observations: dict[str, torch.Tensor]) -> torch.Tensor:
        adapted: list[torch.Tensor] = []
        masks: list[torch.Tensor] = []
        for adapter, (seq_key, mask_key, _, _) in zip(self.adapters, self.streams, strict=True):
            seq = observations[seq_key]
            mask = batch_mask(observations[mask_key], seq.shape[0], seq.shape[1]).to(seq.device)
            # Mask both input values and adapter bias so left padding is a stable neutral value.
            valid_rows = mask.unsqueeze(-1)
            clean_seq = torch.where(valid_rows, seq, torch.zeros_like(seq))
            values = adapter(clean_seq)
            values = torch.where(valid_rows, values, torch.zeros_like(values))
            adapted.append(values)
            masks.append(mask)

        m1_token = self.temporal_core(adapted[0], masks[0])
        htf_values = adapted[1:]
        htf_masks = masks[1:]
        max_length = max(value.shape[1] for value in htf_values)
        padded_values = [
            F.pad(value, (0, 0, max_length - value.shape[1], 0)) for value in htf_values
        ]
        padded_masks = [
            F.pad(mask, (max_length - mask.shape[1], 0), value=False) for mask in htf_masks
        ]
        batch_size = m1_token.shape[0]
        grouped_values = torch.stack(padded_values, dim=1).reshape(
            batch_size * len(htf_values), max_length, self.adapter_dim
        )
        grouped_masks = torch.stack(padded_masks, dim=1).reshape(
            batch_size * len(htf_masks), max_length
        )
        grouped_tokens = self.temporal_core(grouped_values, grouped_masks).reshape(
            batch_size, len(htf_values), self.latent_dim
        )
        tokens = torch.cat((m1_token[:, None, :], grouped_tokens), dim=1)
        valid = torch.stack([mask.any(dim=1) for mask in masks], dim=1)
        return self.finish(tokens, valid, observations["account"])


__all__ = ["SharedTCNMTFReasoningEncoder"]
