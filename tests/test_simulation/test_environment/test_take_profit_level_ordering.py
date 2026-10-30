from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from simulation.environment.env import TradingEnv


@pytest.mark.parametrize("side,prices", [(1, (110.0, 110.0, 120.0)), (-1, (90.0, 90.0, 80.0))])
def test_take_profit_levels_are_strictly_ordered_without_duplicates(
    side: int, prices: tuple[float, ...]
) -> None:
    pos: Any = SimpleNamespace(
        direction=side,
        tp1_price=prices[0],
        tp2_price=prices[1],
        tp3_price=prices[2],
        entry_price=100.0,
        tp_hit_mask=0,
    )
    TradingEnv._reorder_tp_levels_safe(cast(Any, None), pos)
    remaining = [pos.tp1_price, pos.tp2_price, pos.tp3_price]
    active = [price for price in remaining if price is not None]
    assert len(active) >= 1
    assert all(
        active[i] < active[i + 1] if side == 1 else active[i] > active[i + 1]
        for i in range(len(active) - 1)
    )
