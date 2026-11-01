"""M1 TCN with lightweight history-aware higher-timeframe tokens."""

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


class M1TCNHTFLiteReasoningEncoder(MTFReasoningOutput):
    """Keep D's M1 TCN and summarize HTF history with a shared small MLP."""

    encoder_id = "mtf_m1_tcn_htf_lite_reasoning"

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
        """Initialize M1TCNHTFLiteReasoningEncoder and its owned state.

        Args:
            observation_space: Observation space used by the operation described above.
            latent_dim: Number of dimensions in the learned latent representation.
            channels: Items supplied for the channels, in input order.
            kernel_size: Number specifying the kernel size for this operation.
            dropout: Numeric value used for the dropout.
            account_dim: Account dim used by the operation described above.
            attention_heads: Numeric value used for the attention heads.
            feedforward_dim: Numeric value used for the feedforward dim.
            adapter_dim: Numeric value used for the adapter dim.
        """
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
        self.htf_summary = nn.Sequential(
            nn.Linear(adapter_dim * 3, latent_dim),
            nn.LayerNorm(latent_dim),
            nn.SiLU(),
            nn.Linear(latent_dim, latent_dim),
        )
        self.channels = tuple(channels)
        self.kernel_size = kernel_size

    @property
    def encoder_provenance(self) -> dict[str, Any]:
        """Return architecture identifiers and stream details used for checkpoint provenance.

        Returns:
            Mapping from ``str`` keys to ``Any`` values.
        """
        return {
            "encoder_id": self.encoder_id,
            "adapter_width": self.adapter_dim,
            "branch_count": self.branch_count,
            "shared_core": self.shared_core,
            "token_dim": self.latent_dim,
            "latent_dim": self.latent_dim,
            "attention_heads": self.attention_heads,
            "attention_feedforward_dim": self.feedforward_dim,
            "htf_summary_type": "latest_masked_mean_and_change_shared_mlp",
        }

    def forward(self, observations: dict[str, torch.Tensor]) -> torch.Tensor:
        """Encode M1 history with lightweight higher-timeframe context.

        Args:
            observations: Mapping of sequence, validity-mask, and account tensors.

        Returns:
            Fused policy feature tensor for the observation batch.
        """
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
            latest, previous, has_values = latest_two_valid(projected, mask)
            counts = mask.sum(dim=1, keepdim=True).clamp_min(1).to(projected.dtype)
            mean = projected.sum(dim=1) / counts
            summary = torch.cat((latest, mean, latest - previous), dim=-1)
            tokens.append(self.htf_summary(summary))
            validity.append(has_values)
        token_tensor = torch.stack(tokens, dim=1)
        valid_tensor = torch.stack(validity, dim=1)
        return self.finish(token_tensor, valid_tensor, observations["account"])


__all__ = ["M1TCNHTFLiteReasoningEncoder"]
