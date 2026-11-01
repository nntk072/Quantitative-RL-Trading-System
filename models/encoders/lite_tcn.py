"""Lightweight depthwise-separable temporal convolution encoder."""

from __future__ import annotations

from typing import Any, cast

import torch
import torch.nn as nn

from models.encoders.sequence_encoder_components import (
    ACCOUNT_EMB_DIM,
    AccountMLP,
    BaseFeaturesExtractor,
    Chomp1d,
    _encode_valid_suffix,
    _resolve_account_dim,
    _valid_lengths,
)


class _DepthwiseSeparableConv1d(nn.Module):
    """Causal temporal convolution with depthwise and pointwise factors."""

    def __init__(self, channels: int, kernel_size: int, dilation: int, dropout: float) -> None:
        """Initialize _DepthwiseSeparableConv1d and its owned state.

        Args:
            channels: Numeric value used for the channels.
            kernel_size: Number specifying the kernel size for this operation.
            dilation: Numeric value used for the dilation.
            dropout: Numeric value used for the dropout.
        """
        super().__init__()
        padding = (kernel_size - 1) * dilation
        self.depthwise = nn.Conv1d(
            channels,
            channels,
            kernel_size,
            padding=padding,
            dilation=dilation,
            groups=channels,
        )
        self.chomp = Chomp1d(padding)
        self.activation = nn.ReLU()
        self.dropout = nn.Dropout(dropout)
        self.pointwise = nn.Conv1d(channels, channels, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Apply depthwise causal filtering followed by channel mixing.

        Args:
            x: Channel-first sequence tensor with shape ``[batch, channels, time]``.

        Returns:
            Causally filtered tensor with the input time length and channel width.
        """
        x = self.depthwise(x)
        x = self.chomp(x)
        x = self.activation(x)
        x = self.dropout(x)
        return cast(torch.Tensor, self.pointwise(x))


class _LiteTemporalBlock(nn.Module):
    """Residual block with two depthwise-separable causal convolutions."""

    def __init__(self, channels: int, kernel_size: int, dilation: int, dropout: float) -> None:
        """Initialize _LiteTemporalBlock and its owned state.

        Args:
            channels: Numeric value used for the channels.
            kernel_size: Number specifying the kernel size for this operation.
            dilation: Numeric value used for the dilation.
            dropout: Numeric value used for the dropout.
        """
        super().__init__()
        self.temporal = nn.Sequential(
            _DepthwiseSeparableConv1d(channels, kernel_size, dilation, dropout),
            _DepthwiseSeparableConv1d(channels, kernel_size, dilation, dropout),
        )
        self.activation = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Add two causal temporal convolutions to the input residual.

        Args:
            x: Channel-first sequence tensor with shape ``[batch, channels, time]``.

        Returns:
            Activated residual features with the same shape as ``x``.
        """
        return cast(torch.Tensor, self.activation(x + self.temporal(x)))


class LiteTCNEncoder(BaseFeaturesExtractor):
    """Compact causal depthwise-separable TCN with the standard 160-wide output.

    The default three blocks use two kernel-3 convolutions at dilations 1, 4,
    and 10. This gives a 61-bar receptive field while preserving the normal
    128-value sequence latent and 32-value account embedding.
    """

    def __init__(
        self,
        observation_space: Any,
        seq_len: int = 60,
        n_features: int = 64,
        latent_dim: int = 128,
        channels: int = 96,
        dilations: tuple[int, ...] = (1, 4, 10),
        kernel_size: int = 3,
        dropout: float = 0.1,
        account_dim: int | None = None,
    ) -> None:
        """Initialize LiteTCNEncoder and its owned state.

        Args:
            observation_space: Observation space used by the operation described above.
            seq_len: Number of consecutive bars in each input sequence.
            n_features: Number of feature columns in each observation.
            latent_dim: Number of dimensions in the learned latent representation.
            channels: Numeric value used for the channels.
            dilations: Items supplied for the dilations, in input order.
            kernel_size: Number specifying the kernel size for this operation.
            dropout: Numeric value used for the dropout.
            account_dim: Account dim used by the operation described above.
        """
        super().__init__(observation_space, features_dim=latent_dim + ACCOUNT_EMB_DIM)
        if not dilations or any(dilation < 1 for dilation in dilations):
            raise ValueError("LiteTCN dilations must be a nonempty sequence of positive integers")
        if channels < 1 or kernel_size < 1:
            raise ValueError("LiteTCN channels and kernel_size must be positive")
        self.seq_len = seq_len
        self.n_features = n_features
        self.latent_dim = latent_dim
        self.channels = channels
        self.dilations = tuple(int(dilation) for dilation in dilations)
        self.kernel_size = kernel_size
        resolved_account_dim = _resolve_account_dim(observation_space, account_dim)
        self.account_mlp = AccountMLP(resolved_account_dim)
        self.input_proj = nn.Conv1d(n_features, channels, kernel_size=1)
        self.blocks = nn.ModuleList(
            _LiteTemporalBlock(channels, kernel_size, dilation, dropout)
            for dilation in self.dilations
        )
        self.proj = nn.Linear(channels, latent_dim)

    @property
    def receptive_field(self) -> int:
        """Return the number of input bars visible at a block's last timestep.

        Returns:
            Numeric result returned by ``receptive_field``.
        """
        return int(1 + 2 * (self.kernel_size - 1) * sum(self.dilations))

    def _encode_hidden(self, seq: torch.Tensor) -> torch.Tensor:
        """Return every causal hidden state as ``[batch, time, channels]``.

        Args:
            seq: Seq used by the operation described above.

        Returns:
            Result of return every causal hidden state as ``[batch, time, channels]``.
        """
        hidden = self.input_proj(seq.transpose(1, 2))
        for block in self.blocks:
            hidden = block(hidden)
        return cast(torch.Tensor, hidden.transpose(1, 2))

    def forward(self, observations: dict[str, torch.Tensor]) -> torch.Tensor:
        """Encode sequence and account observations with the lightweight temporal convolution.

        Args:
            observations: Mapping containing batched seq and account tensors, plus optional valid-length metadata.

        Returns:
            Concatenated latent sequence representation and account embedding.
        """
        seq = observations["seq"]
        account = observations["account"]
        lengths = _valid_lengths(seq, observations)

        def _encode(valid: torch.Tensor) -> torch.Tensor:
            """Process LiteTCNEncoder.

            Args:
                valid: Valid used by the operation described above.

            Returns:
                Result of process LiteTCNEncoder.
            """
            hidden = self._encode_hidden(valid)
            return cast(torch.Tensor, self.proj(hidden[:, -1, :]))

        latent = _encode_valid_suffix(seq, lengths, _encode)
        return torch.cat([latent, self.account_mlp(account)], dim=1)
