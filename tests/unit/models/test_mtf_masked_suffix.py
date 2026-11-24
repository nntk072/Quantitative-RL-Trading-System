"""MTF encoders must treat each row as its own valid suffix, including empty windows."""

from __future__ import annotations

import numpy as np
import torch
from gymnasium import spaces

from models.encoders.mtf import MTFEncoder
from models.encoders.mtf_reasoning import MTFReasoningEncoder


def _space() -> spaces.Dict:
    return spaces.Dict(
        {
            "seq": spaces.Box(low=-1.0, high=1.0, shape=(8, 3), dtype=np.float32),
            "seq_mask": spaces.Box(low=0.0, high=1.0, shape=(8,), dtype=np.float32),
            "seq_m5": spaces.Box(low=-1.0, high=1.0, shape=(6, 2), dtype=np.float32),
            "mask_m5": spaces.Box(low=0.0, high=1.0, shape=(6,), dtype=np.float32),
            "seq_h1": spaces.Box(low=-1.0, high=1.0, shape=(4, 1), dtype=np.float32),
            "mask_h1": spaces.Box(low=0.0, high=1.0, shape=(4,), dtype=np.float32),
            "account": spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32),
        }
    )


def _trailing_mask(lengths: tuple[int, ...], timesteps: int) -> torch.Tensor:
    mask = torch.zeros(len(lengths), timesteps)
    for row, length in enumerate(lengths):
        if length:
            mask[row, timesteps - length :] = 1.0
    return mask


def _observations() -> dict[str, torch.Tensor]:
    # Row 0 full, row 1 partial, row 2 has no valid step in any stream.
    return {
        "seq": torch.randn(3, 8, 3),
        "seq_mask": _trailing_mask((8, 3, 0), 8),
        "seq_m5": torch.randn(3, 6, 2),
        "mask_m5": _trailing_mask((6, 6, 0), 6),
        "seq_h1": torch.randn(3, 4, 1),
        "mask_h1": _trailing_mask((4, 0, 0), 4),
        "account": torch.randn(3, 6),
    }


def test_reasoning_batch_matches_each_row_alone() -> None:
    torch.manual_seed(2)
    encoder = MTFReasoningEncoder(
        _space(), latent_dim=128, channels=(8, 8), dropout=0.0, account_dim=6
    ).eval()
    obs = _observations()
    with torch.no_grad():
        batched = encoder(obs)
        for row in range(3):
            alone = encoder({k: v[row : row + 1] for k, v in obs.items()})
            assert torch.allclose(batched[row : row + 1], alone, atol=1e-5), row


def test_plain_mtf_batch_matches_each_row_alone() -> None:
    torch.manual_seed(4)
    encoder = MTFEncoder(_space(), latent_dim=128, channels=(8, 8), dropout=0.0, account_dim=6)
    encoder.eval()
    obs = _observations()
    with torch.no_grad():
        batched = encoder(obs)
        for row in range(3):
            alone = encoder({k: v[row : row + 1] for k, v in obs.items()})
            assert torch.allclose(batched[row : row + 1], alone, atol=1e-5), row
