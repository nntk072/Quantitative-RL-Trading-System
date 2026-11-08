"""MT5 server-triggered SL/TP must not incur EA network latency."""

from __future__ import annotations

import numpy as np
import pandas as pd

from market_data.loading.ticks import TickBook, resolve_tick_exit


def _book() -> TickBook:
    times = pd.DatetimeIndex(
        [
            "2026-01-05T16:30:00.000Z",
            "2026-01-05T16:30:00.010Z",
            "2026-01-05T16:30:00.010Z",  # two changes sharing one millisecond
            "2026-01-05T16:30:00.040Z",
        ]
    )
    return TickBook(
        np.asarray(times.astype("int64"), dtype=np.int64),
        np.array([100.0, 98.0, 97.0, 101.0]),
        np.array([100.5, 98.5, 97.5, 101.5]),
    )


def test_server_side_protective_fill_at_first_trigger_without_network_latency() -> None:
    book = _book()
    hit = resolve_tick_exit(
        book,
        pd.Timestamp("2026-01-05T16:30:00Z"),
        1,
        99.0,
        102.0,
        np.random.default_rng(41),
        max_latency_ns_exclusive=30_000_000,
        server_side_protective=True,
    )
    assert hit is not None
    assert hit.kind == "sl"
    assert hit.quote.tick_time == pd.Timestamp("2026-01-05T16:30:00.010Z")
    assert hit.quote.bid == 98.0
    assert hit.quote.latency_ns == 0


def test_legacy_latency_stays_available_for_reproduction() -> None:
    book = _book()
    hit = resolve_tick_exit(
        book,
        pd.Timestamp("2026-01-05T16:30:00Z"),
        1,
        99.0,
        102.0,
        np.random.default_rng(41),
        max_latency_ns_exclusive=0,
        server_side_protective=False,
    )
    assert hit is not None
    assert hit.quote.bid == 98.0
