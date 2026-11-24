"""CUDA-graph feature replay must match the eager forward on fresh inputs."""

from __future__ import annotations

import pytest
import torch
from torch import nn

from learning.rl.feature_graph import FeatureGraphCache

pytestmark = pytest.mark.skipif(not torch.cuda.is_available(), reason="requires CUDA")


class _Extractor(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.linear = nn.Linear(5, 4)

    def forward(self, obs: dict[str, torch.Tensor]) -> torch.Tensor:
        return torch.tanh(self.linear(obs["x"])) + obs["y"]


def test_replay_matches_eager_on_fresh_inputs() -> None:
    torch.manual_seed(0)
    device = torch.device("cuda")
    extractor = _Extractor().to(device).eval()

    def eager(obs: dict[str, torch.Tensor], fe: nn.Module) -> torch.Tensor:
        result: torch.Tensor = fe(obs)
        return result

    cache = FeatureGraphCache(eager)
    first = {"x": torch.randn(8, 5, device=device), "y": torch.randn(8, 4, device=device)}
    second = {"x": torch.randn(8, 5, device=device), "y": torch.randn(8, 4, device=device)}
    with torch.no_grad():
        cache(first, extractor)  # capture
        replayed = cache(second, extractor)
        expected = extractor(second)
    assert torch.allclose(replayed, expected, atol=1e-6)


def test_each_batch_shape_gets_its_own_graph() -> None:
    torch.manual_seed(1)
    device = torch.device("cuda")
    extractor = _Extractor().to(device).eval()
    cache = FeatureGraphCache(lambda obs, fe: fe(obs))
    with torch.no_grad():
        for batch in (8, 3):
            obs = {
                "x": torch.randn(batch, 5, device=device),
                "y": torch.randn(batch, 4, device=device),
            }
            assert torch.allclose(cache(obs, extractor), extractor(obs), atol=1e-6)
    assert len(cache._captured) == 2
