"""Multi-timeframe causal convolution encoder."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import torch
import torch.nn as nn

from models.encoders.sequence_encoder_components import (
    ACCOUNT_EMB_DIM,
    AccountMLP,
    BaseFeaturesExtractor,
    _encode_valid_suffix,
    _resolve_account_dim,
    _valid_lengths,
)
from models.encoders.tcn import _TemporalBlock

_AVAILABLE_MTF_TIMEFRAMES = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")

_MTF_STREAMS: tuple[tuple[str, str], ...] = (("seq", "seq_mask"),) + tuple(
    (f"seq_{timeframe.lower()}", f"mask_{timeframe.lower()}")
    for timeframe in _AVAILABLE_MTF_TIMEFRAMES
    if timeframe != "M1"
)


class _CausalTCN(nn.Module):
    """One causal TCN. The last valid step is projected to ``latent_dim``."""

    def __init__(
        self,
        n_features: int,
        latent_dim: int,
        channels: tuple[int, ...] = (128, 128, 256, 256),
        kernel_size: int = 3,
        dropout: float = 0.1,
    ) -> None:
        """Initialize _CausalTCN and its owned state.

        Args:
            n_features: Number of feature columns in each observation.
            latent_dim: Number of dimensions in the learned latent representation.
            channels: Items supplied for the channels, in input order.
            kernel_size: Number specifying the kernel size for this operation.
            dropout: Numeric value used for the dropout.
        """
        super().__init__()
        dilations = tuple(2**i for i in range(len(channels)))
        layers: list[nn.Module] = []
        for i, out_ch in enumerate(channels):
            in_ch = n_features if i == 0 else channels[i - 1]
            layers.append(_TemporalBlock(in_ch, out_ch, kernel_size, dilations[i], dropout))
        self.tcn = nn.Sequential(*layers)
        self.proj = nn.Linear(channels[-1], latent_dim)

    def forward(self, seq: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        """Encode each row's valid sequence suffix into its final latent state.

        Args:
            seq: Batched timeframe features with shape ``[batch, time, features]``.
            mask: Valid-timestep mask aligned with ``seq``.

        Returns:
            One ``latent_dim`` vector per batch row.
        """
        lengths = _valid_lengths(seq, {"seq_mask": mask})

        def _encode(valid: torch.Tensor) -> torch.Tensor:
            """Process _CausalTCN.

            Args:
                valid: Valid used by the operation described above.

            Returns:
                Result of process _CausalTCN.
            """
            hidden = self.tcn(valid.transpose(1, 2))
            return cast(torch.Tensor, self.proj(hidden[:, :, -1]))

        return _encode_valid_suffix(seq, lengths, _encode)


class MTFEncoder(BaseFeaturesExtractor):
    """One causal TCN per configured timeframe window, fused to one latent.

    The account embedding is unchanged, so ``features_dim`` stays 160 and the
    actor and critic are the same heads used by ``TCNEncoder``.
    """

    def __init__(
        self,
        observation_space: Any,
        latent_dim: int = 128,
        channels: tuple[int, ...] = (128, 128, 256, 256),
        kernel_size: int = 3,
        dropout: float = 0.1,
        account_dim: int | None = None,
    ) -> None:
        """Initialize MTFEncoder and its owned state.

        Args:
            observation_space: Observation space used by the operation described above.
            latent_dim: Number of dimensions in the learned latent representation.
            channels: Items supplied for the channels, in input order.
            kernel_size: Number specifying the kernel size for this operation.
            dropout: Numeric value used for the dropout.
            account_dim: Account dim used by the operation described above.
        """
        super().__init__(observation_space, features_dim=latent_dim + ACCOUNT_EMB_DIM)
        spaces_map = getattr(observation_space, "spaces", None)
        if not isinstance(spaces_map, Mapping):
            raise TypeError("MTFEncoder requires a Dict observation space")
        self.latent_dim = latent_dim
        self.channels = tuple(int(channel) for channel in channels)
        self.dilations = tuple(2**i for i in range(len(self.channels)))
        self.kernel_size = kernel_size
        resolved_account_dim = _resolve_account_dim(observation_space, account_dim)
        self.account_mlp = AccountMLP(resolved_account_dim)
        self._keys = tuple(pair for pair in _MTF_STREAMS if pair[0] in spaces_map)
        if not self._keys or self._keys[0][0] != "seq":
            raise ValueError("MTFEncoder requires the M1 'seq' observation stream")
        self.branches = nn.ModuleList()
        for seq_key, mask_key in self._keys:
            if mask_key not in spaces_map:
                raise ValueError(f"missing mask observation for {seq_key}: {mask_key}")
            box = spaces_map[seq_key]
            shape = getattr(box, "shape", None)
            if shape is None or len(shape) < 2:
                raise TypeError(f"{seq_key} must be a Box")
            n_features = int(shape[1])
            self.branches.append(
                _CausalTCN(n_features, latent_dim, self.channels, kernel_size, dropout)
            )
        width = latent_dim * len(self._keys)
        self.fuse = nn.Sequential(nn.LayerNorm(width), nn.Linear(width, latent_dim))

    def forward(self, observations: dict[str, torch.Tensor]) -> torch.Tensor:
        """Encode aligned timeframe streams and account state into policy features.

        Args:
            observations: Mapping of timeframe sequences, masks, and account values.

        Returns:
            Fused timeframe latent concatenated with the account embedding.
        """
        parts = [
            branch(observations[seq_key], observations[mask_key])
            for branch, (seq_key, mask_key) in zip(self.branches, self._keys, strict=True)
        ]
        latent = self.fuse(torch.cat(parts, dim=1))
        return torch.cat([latent, self.account_mlp(observations["account"])], dim=1)
