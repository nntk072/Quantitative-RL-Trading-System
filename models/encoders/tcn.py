"""Causal temporal convolution encoders."""

from __future__ import annotations

from typing import Any, cast

import torch
import torch.nn as nn

from models.encoders.sequence_encoder_components import (
    ACCOUNT_DIM,
    ACCOUNT_EMB_DIM,
    AccountMLP,
    BaseFeaturesExtractor,
    Chomp1d,
    _encode_valid_suffix,
    _resolve_account_dim,
    _valid_lengths,
)


class _TemporalBlock(nn.Module):
    """Dilated causal conv block with residual connection and weight-norm."""

    def __init__(
        self,
        n_in: int,
        n_out: int,
        kernel_size: int,
        dilation: int,
        dropout: float,
    ) -> None:
        """Initialize _TemporalBlock and its owned state.

        Args:
            n_in: Numeric value used for the n in.
            n_out: Numeric value used for the n out.
            kernel_size: Number specifying the kernel size for this operation.
            dilation: Numeric value used for the dilation.
            dropout: Numeric value used for the dropout.
        """
        super().__init__()
        padding = (kernel_size - 1) * dilation
        self.net = nn.Sequential(
            nn.utils.parametrizations.weight_norm(
                nn.Conv1d(n_in, n_out, kernel_size, padding=padding, dilation=dilation)
            ),
            Chomp1d(padding),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.utils.parametrizations.weight_norm(
                nn.Conv1d(n_out, n_out, kernel_size, padding=padding, dilation=dilation)
            ),
            Chomp1d(padding),
            nn.ReLU(),
            nn.Dropout(dropout),
        )
        self.downsample = nn.Conv1d(n_in, n_out, 1) if n_in != n_out else None
        self.relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Apply the dilated causal stack and add its projected residual input.

        Args:
            x: Channel-first sequence tensor with shape ``[batch, channels, time]``.

        Returns:
            Residual features with the block's output channel width.
        """
        out = self.net(x)
        res = x if self.downsample is None else self.downsample(x)
        return cast(torch.Tensor, self.relu(out + res))


class LegacyTCNEncoderV1(BaseFeaturesExtractor):
    """Archived Sep-2026 TCN layout retained for explicit 4D checkpoint migration.

    This reproduces the pre-valid-window/account-embedding extractor: three
    convolution blocks and the normalized six-value account vector appended
    directly to the 128-value sequence latent. It is used only when loading a
    checkpoint declared as ``legacy4_no_exit_v1``.
    """

    def __init__(
        self,
        observation_space: Any,
        seq_len: int = 60,
        n_features: int = 64,
        latent_dim: int = 128,
        channels: tuple[int, ...] = (128, 128, 256),
        kernel_size: int = 3,
        dropout: float = 0.1,
    ) -> None:
        """Initialize LegacyTCNEncoderV1 and its owned state.

        Args:
            observation_space: Observation space used by the operation described above.
            seq_len: Number of consecutive bars in each input sequence.
            n_features: Number of feature columns in each observation.
            latent_dim: Number of dimensions in the learned latent representation.
            channels: Items supplied for the channels, in input order.
            kernel_size: Number specifying the kernel size for this operation.
            dropout: Numeric value used for the dropout.
        """
        account_space = getattr(observation_space, "spaces", {}).get("account")
        account_dim = int(account_space.shape[0]) if account_space is not None else ACCOUNT_DIM
        super().__init__(observation_space, features_dim=latent_dim + account_dim)
        self.seq_len = seq_len
        self.n_features = n_features
        self.latent_dim = latent_dim
        self.tcn = nn.Sequential(
            *(
                _TemporalBlock(
                    n_features if index == 0 else channels[index - 1],
                    out_channels,
                    kernel_size,
                    2**index,
                    dropout,
                )
                for index, out_channels in enumerate(channels)
            )
        )
        self.proj = nn.Linear(channels[-1], latent_dim)

    def forward(self, observations: dict[str, torch.Tensor]) -> torch.Tensor:
        """Encode the legacy sequence and account observation layout.

        Args:
            observations: Mapping containing batched seq and account tensors.

        Returns:
            Policy feature tensor in the checkpoint-compatible layout.
        """
        seq = observations["seq"]
        account = observations["account"]
        hidden = self.tcn(seq.transpose(1, 2))
        latent = cast(torch.Tensor, self.proj(hidden[:, :, -1]))
        return torch.cat((latent, account), dim=1)


class TCNEncoder(BaseFeaturesExtractor):
    """Dilated causal TCN that maps a sequence window to a latent vector.

    Receptive field with ``L`` levels, kernel ``k``, grows as
    ``2^0 + … + 2^{L-1}) * (k-1) + 1`` bars — easily covers T=60.

    Args:
        seq_len: Observation window length in bars.
        n_features: Number of input features per bar.
        latent_dim: Width of the encoded sequence representation.
        channels: Output width for each successive temporal convolution block.
        kernel_size: Width of each temporal convolution kernel.
        dropout: Dropout probability inside each temporal block.
        account_dim: Optional width of account inputs; inferred from the observation
            space when omitted.
    """

    def __init__(
        self,
        observation_space: Any,
        seq_len: int = 60,
        n_features: int = 64,
        latent_dim: int = 128,
        channels: tuple[int, ...] = (128, 128, 256, 256),
        kernel_size: int = 3,
        dropout: float = 0.1,
        account_dim: int | None = None,
    ) -> None:
        """Initialize TCNEncoder and its owned state.

        Args:
            observation_space: Observation space used by the operation described above.
            seq_len: Number of consecutive bars in each input sequence.
            n_features: Number of feature columns in each observation.
            latent_dim: Number of dimensions in the learned latent representation.
            channels: Items supplied for the channels, in input order.
            kernel_size: Number specifying the kernel size for this operation.
            dropout: Numeric value used for the dropout.
            account_dim: Account dim used by the operation described above.
        """
        super().__init__(observation_space, features_dim=latent_dim + ACCOUNT_EMB_DIM)
        self.seq_len = seq_len
        self.n_features = n_features
        self.latent_dim = latent_dim
        self.channels = tuple(int(channel) for channel in channels)
        self.kernel_size = kernel_size
        self.dilations = tuple(2**i for i in range(len(self.channels)))
        resolved_account_dim = _resolve_account_dim(observation_space, account_dim)
        self.account_mlp = AccountMLP(resolved_account_dim)

        tcn_layers: list[nn.Module] = []
        for i, out_ch in enumerate(self.channels):
            in_ch = n_features if i == 0 else self.channels[i - 1]
            tcn_layers.append(
                _TemporalBlock(in_ch, out_ch, kernel_size, self.dilations[i], dropout)
            )
        self.tcn = nn.Sequential(*tcn_layers)
        self.proj = nn.Linear(self.channels[-1], latent_dim)

    @property
    def receptive_field(self) -> int:
        """Bars visible at the last step. Two kernel-sized convs per dilation.

        Returns:
            Numeric result returned by ``receptive_field``.
        """
        return int(1 + 2 * (self.kernel_size - 1) * sum(self.dilations))

    def forward(self, observations: dict[str, torch.Tensor]) -> torch.Tensor:
        """Encode sequence and account observations with a temporal convolutional network.

        Args:
            observations: Mapping containing batched seq and account tensors, plus optional valid-length metadata.

        Returns:
            Concatenated latent sequence representation and account embedding.
        """
        seq = observations["seq"]  # [B, T, F]
        account = observations["account"]  # [B, A]
        lengths = _valid_lengths(seq, observations)

        def _encode(valid: torch.Tensor) -> torch.Tensor:
            """Process TCNEncoder.

            Args:
                valid: Valid used by the operation described above.

            Returns:
                Result of process TCNEncoder.
            """
            hidden = self.tcn(valid.transpose(1, 2))
            return cast(torch.Tensor, self.proj(hidden[:, :, -1]))

        latent = _encode_valid_suffix(seq, lengths, _encode)
        return torch.cat([latent, self.account_mlp(account)], dim=1)
