"""M1 TCN with latest causally available higher-timeframe state tokens."""

from __future__ import annotations

from typing import Any

import torch
from torch import nn

from models.encoders.mtf import _CausalTCN
from models.encoders.mtf_efficiency_components import (
    MTFReasoningOutput,
    batch_mask,
    latest_two_valid,
    observation_streams,
)


class M1TCNHTFSnapshotReasoningEncoder(MTFReasoningOutput):
    """Keep D's M1 TCN and encode only each HTF's latest valid feature row."""

    encoder_id = "mtf_m1_tcn_htf_snapshot_reasoning"

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
        adapter_dim: int = 32,
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
        self.shared_core = False
        self.m1_tcn = _CausalTCN(
            self.streams[0][3], latent_dim, tuple(channels), kernel_size, dropout
        )
        self.htf_adapters = nn.ModuleList(
            nn.Linear(feature_count, adapter_dim) for _, _, _, feature_count in self.streams[1:]
        )
        self.htf_snapshot = nn.Sequential(
            nn.Linear(adapter_dim, latent_dim),
            nn.LayerNorm(latent_dim),
            nn.SiLU(),
            nn.Linear(latent_dim, latent_dim),
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
            "htf_summary_type": "latest_valid_snapshot_shared_mlp",
        }

    def forward(self, observations: dict[str, torch.Tensor]) -> torch.Tensor:
        m1_key, m1_mask_key, _, _ = self.streams[0]
        m1_token = self.m1_tcn(observations[m1_key], observations[m1_mask_key])
        tokens = [m1_token]
        validity = [
            batch_mask(observations[m1_mask_key], m1_token.shape[0], observations[m1_key].shape[1])
            .to(m1_token.device)
            .any(dim=1)
        ]
        for adapter, (seq_key, mask_key, _, _) in zip(
            self.htf_adapters, self.streams[1:], strict=True
        ):
            seq = observations[seq_key]
            mask = batch_mask(observations[mask_key], seq.shape[0], seq.shape[1]).to(seq.device)
            valid_rows = mask.unsqueeze(-1)
            clean_seq = torch.where(valid_rows, seq, torch.zeros_like(seq))
            projected = adapter(clean_seq)
            projected = torch.where(valid_rows, projected, torch.zeros_like(projected))
            latest, _, has_values = latest_two_valid(projected, mask)
            tokens.append(self.htf_snapshot(latest))
            validity.append(has_values)
        token_tensor = torch.stack(tokens, dim=1)
        valid_tensor = torch.stack(validity, dim=1)
        return self.finish(token_tensor, valid_tensor, observations["account"])


__all__ = ["M1TCNHTFSnapshotReasoningEncoder"]
