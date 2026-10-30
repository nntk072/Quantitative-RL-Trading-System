from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from simulation.environment.env import TradingEnv


@pytest.mark.parametrize(
    ("side", "swing_low", "swing_high", "expected"),
    [(1, 98.0, 110.0, 97.5), (-1, 90.0, 102.0, 102.5)],
)
def test_trailing_stop_uses_protective_confirmed_swing(
    side: int, swing_low: float, swing_high: float, expected: float
) -> None:
    stub_env: Any = SimpleNamespace(sl_buffer_pts=0.5, _finite=lambda row, key: row.get(key))
    pos: Any = SimpleNamespace(
        sl_mode="trailing", direction=side, sl_price=95.0 if side == 1 else 105.0
    )
    TradingEnv._apply_trailing_stop(
        stub_env,
        pos,
        cast(Any, {"last_swing_low": swing_low, "last_swing_high": swing_high}),
    )
    assert pos.sl_price == pytest.approx(expected)
