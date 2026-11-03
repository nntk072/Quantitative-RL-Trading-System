from __future__ import annotations

import pytest

from trading.baselines.step_indexed_strategy import BaseStrategy


class _IndexedStrategy(BaseStrategy):
    def __init__(self) -> None:
        self.signals = [0.1, 0.2, -0.3, 0.4, -0.5]
        super().__init__(len(self.signals))

    def _signal(self, idx: int) -> float:
        return self.signals[idx]


def test_act_at_supports_sparse_environment_steps_without_state_drift() -> None:
    strategy = _IndexedStrategy()

    selected = [strategy.act_at(index) for index in (1, 4)]

    assert selected == [0.2, -0.5]
    assert strategy.act({}) == 0.1


@pytest.mark.parametrize("bar_index", [-1, 5])
def test_act_at_rejects_indices_outside_precomputed_signals(bar_index: int) -> None:
    with pytest.raises(IndexError, match="outside"):
        _IndexedStrategy().act_at(bar_index)


def test_act_at_rejects_non_integer_indices() -> None:
    with pytest.raises(TypeError, match="integer row index"):
        _IndexedStrategy().act_at(1.5)  # type: ignore[arg-type]
