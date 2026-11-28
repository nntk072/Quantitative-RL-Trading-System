from __future__ import annotations

from collections.abc import Hashable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

import market_data.news.guard as news_guard
from market_data.news.guard import (
    NewsGuardConfig,
    load_release_times,
    news_block_mask,
    news_guard_config,
    session_baseline_atr,
)

START = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)


def _sessions(n_sessions: int, bars_per_session: int, label: str = "london"):
    times, ids, labels = [], [], []
    for s in range(n_sessions):
        base = START + timedelta(days=s)
        for k in range(bars_per_session):
            times.append(base + timedelta(minutes=k))
            ids.append(s)
            labels.append(label)
    return times, np.array(ids), np.array(labels)


def _config(**overrides: Any) -> NewsGuardConfig:
    values: dict[str, Any] = {
        "calendar_path": Path("unused.csv"),
        "spike_window_bars": 2,
        "spike_atr_multiple": 2.0,
        "baseline_lookback_sessions": 5,
    }
    values.update(overrides)
    return NewsGuardConfig(**values)


def test_baseline_uses_only_earlier_sessions_at_same_offset() -> None:
    times, ids, labels = _sessions(3, 4)
    atr = np.concatenate([(s + 1) * np.array([1.0, 2.0, 3.0, 4.0]) for s in range(3)])

    baseline = session_baseline_atr(atr, ids, labels, lookback_sessions=5)

    # First session has no history; the second sees only the first; the third sees the first two.
    assert np.isnan(baseline[0:4]).all()
    assert list(baseline[4:8]) == [1.0, 2.0, 3.0, 4.0]
    assert list(baseline[8:12]) == [1.5, 3.0, 4.5, 6.0]


def test_spike_blocks_new_entries_outside_ny_open_window() -> None:
    times, ids, labels = _sessions(2, 6)
    atr = np.full(12, 1.0)
    close = np.full(12, 100.0)
    close[10] = 105.0  # a 5-point move in bar 10 of session 1, versus a 1.0 baseline

    mask = news_block_mask(
        times,
        close,
        atr,
        ids,
        labels,
        release_times=[],
        config=_config(),
        open_manipulation_bars=0,
    )

    assert mask[10]
    assert not mask[0:6].any()


def test_ny_open_manipulation_is_not_treated_as_news() -> None:
    times, ids, labels = _sessions(2, 6, label="ny")
    atr = np.full(12, 1.0)
    close = np.full(12, 100.0)
    close[10] = 105.0

    mask = news_block_mask(
        times,
        close,
        atr,
        ids,
        labels,
        release_times=[],
        config=_config(),
        open_manipulation_bars=3,
    )

    # Bar 10 is at offset 4 of its NY session, outside the 3-bar open window, so it blocks.
    assert mask[10]
    exempt = news_block_mask(
        times,
        close,
        atr,
        ids,
        labels,
        release_times=[],
        config=_config(),
        open_manipulation_bars=6,
    )
    assert not exempt[10]


def test_scheduled_release_blackout_is_inclusive() -> None:
    times, ids, labels = _sessions(1, 10)
    atr = np.full(10, 1.0)
    close = np.full(10, 100.0)
    # Release at minute 7: bar 0 is 7 minutes before (outside), bar 2 is exactly 5 minutes
    # before (inside, inclusive), and bar 9 is 2 minutes before (inside).
    release = [START + timedelta(minutes=7)]

    mask = news_block_mask(
        times,
        close,
        atr,
        ids,
        labels,
        release_times=release,
        config=_config(),
        open_manipulation_bars=0,
    )

    assert not mask[0]
    assert mask[2]
    assert mask[9]


def test_mask_does_not_depend_on_future_bars() -> None:
    times, ids, labels = _sessions(3, 8)
    atr = np.full(24, 1.0)
    close = np.linspace(100.0, 101.0, 24)
    base = news_block_mask(times, close, atr, ids, labels, [], _config(), open_manipulation_bars=0)
    changed = close.copy()
    changed[20:] += 50.0  # alter only the last bars

    after = news_block_mask(
        times, changed, atr, ids, labels, [], _config(), open_manipulation_bars=0
    )

    assert (base[:20] == after[:20]).all()


def test_cached_news_mask_reuses_read_only_result_for_identical_bundle_key() -> None:
    times, ids, labels = _sessions(3, 6)
    atr = np.full(18, 1.0)
    close = np.full(18, 100.0)
    close[16] = 105.0
    config = _config()
    cache_key: Hashable = ("test-bundle-news-mask", config, tuple())
    cache_mask = getattr(news_guard, "cached_news_block_mask", None)
    assert callable(cache_mask)

    first = cache_mask(
        cache_key,
        times,
        close,
        atr,
        ids,
        labels,
        release_times=(),
        config=config,
        open_manipulation_bars=0,
    )
    second = cache_mask(
        cache_key,
        times,
        close,
        atr,
        ids,
        labels,
        release_times=(),
        config=config,
        open_manipulation_bars=0,
    )

    np.testing.assert_array_equal(
        first, news_block_mask(times, close, atr, ids, labels, (), config, open_manipulation_bars=0)
    )
    assert first is second
    assert not first.flags.writeable


def test_cached_news_mask_key_separates_guard_semantics() -> None:
    times, ids, labels = _sessions(3, 6, label="ny")
    atr = np.full(18, 1.0)
    close = np.full(18, 100.0)
    close[16] = 105.0
    cache_mask = getattr(news_guard, "cached_news_block_mask", None)
    assert callable(cache_mask)

    blocked = cache_mask(
        ("test-bundle-open-0",),
        times,
        close,
        atr,
        ids,
        labels,
        release_times=(),
        config=_config(),
        open_manipulation_bars=0,
    )
    exempt = cache_mask(
        ("test-bundle-open-20",),
        times,
        close,
        atr,
        ids,
        labels,
        release_times=(),
        config=_config(),
        open_manipulation_bars=20,
    )

    assert blocked[16]
    assert not exempt[16]
    assert blocked is not exempt


def test_load_release_times_reads_utc_column(tmp_path: Path) -> None:
    path = tmp_path / "calendar.csv"
    path.write_text(
        "utc_time,category,summary,source,source_sha256,retrieved_on\n"
        "2025-02-07T13:30:00Z,NFP,Employment Situation,x,y,2026-11-23\n",
        encoding="utf-8",
    )

    assert load_release_times(path) == [datetime(2025, 2, 7, 13, 30, tzinfo=UTC)]


def test_news_guard_config_is_optional_and_resolves_relative_calendar_path() -> None:
    assert news_guard_config(None) is None
    assert news_guard_config({"enabled": False}) is None

    config = news_guard_config(
        {
            "enabled": True,
            "calendar_path": "config/calendar.csv",
            "blackout_minutes_before": 4,
            "blackout_minutes_after": 6,
            "spike_window_bars": 3,
            "spike_atr_multiple": 2.5,
            "baseline_lookback_sessions": 8,
            "exempt_open_manipulation": False,
        }
    )

    assert config is not None
    assert config.calendar_path.name == "calendar.csv"
    assert config.calendar_path.is_absolute()
    assert config.blackout_minutes_before == 4
    assert config.blackout_minutes_after == 6
    assert config.spike_window_bars == 3
    assert config.spike_atr_multiple == 2.5
    assert config.baseline_lookback_sessions == 8
    assert config.exempt_open_manipulation is False
