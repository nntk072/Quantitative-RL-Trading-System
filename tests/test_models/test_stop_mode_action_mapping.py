from __future__ import annotations

import pytest

from learning.rl.ppo import mode_index


@pytest.mark.parametrize(
    ("width", "flags", "expected"),
    [
        (8, {"has_sl_mode": True, "has_multi_tp": True}, 1),
        (9, {"has_sl_mode": True, "has_tp_mode": True, "has_multi_tp": True}, 1),
        (
            11,
            {"has_sl_mode": True, "has_tp_mode": True, "has_multi_tp": True, "has_simplex": True},
            1,
        ),
        (
            12,
            {
                "has_direction": True,
                "has_sl_mode": True,
                "has_tp_mode": True,
                "has_multi_tp": True,
                "has_simplex": True,
            },
            2,
        ),
    ],
)
def test_stop_coordinate_uses_declared_action_flags(
    width: int, flags: dict[str, bool], expected: int
) -> None:
    assert mode_index("stop", width, **flags) == expected
