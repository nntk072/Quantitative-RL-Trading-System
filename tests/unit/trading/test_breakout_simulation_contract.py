"""Forward simulation behavior for the multi-level breakout baseline."""

from __future__ import annotations

import numpy as np

from trading.baselines.breakout import MultiLevelBreakoutStrategy


def test_breakout_waits_for_levels_and_volume_then_holds_until_atr_stop() -> None:
    closes = np.asarray([10.0, 11.0, 12.0, 8.0, 7.0, 4.0])
    asian_high = np.asarray([np.nan, 10.0, 10.0, 10.0, 10.0, 10.0])
    asian_low = np.asarray([np.nan, 0.0, 0.0, 0.0, 0.0, 9.0])
    volume_spike = np.asarray([10.0, 0.5, 2.0, 2.0, 2.0, 2.0])
    atr = np.ones(6)

    actions = MultiLevelBreakoutStrategy._simulate(
        closes,
        asian_high,
        asian_low,
        volume_spike,
        atr,
        spike_thr=1.5,
        stop_mult=2.0,
        size=0.5,
    )

    # Missing levels and a weak volume bar stay flat; the long is held until
    # its stop is reached, then a valid opposite breakout may enter short.
    np.testing.assert_array_equal(actions, [0.0, 0.0, 0.5, 0.0, 0.0, -0.5])


def test_breakout_requires_a_strict_cross_and_stays_flat_when_volume_is_weak() -> None:
    actions = MultiLevelBreakoutStrategy._simulate(
        np.asarray([10.0, 11.0, -1.0]),
        np.asarray([10.0, 10.0, 10.0]),
        np.asarray([0.0, 0.0, 0.0]),
        np.asarray([2.0, 0.5, 0.5]),
        np.ones(3),
        spike_thr=1.5,
        stop_mult=2.0,
        size=1.0,
    )

    np.testing.assert_array_equal(actions, [0.0, 0.0, 0.0])
