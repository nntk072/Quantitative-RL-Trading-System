"""News and spike guard: a per-bar mask of bars where new entries are blocked.

A bar is blocked when either:
- it falls inside the scheduled-release blackout (default 5 minutes before and after each
  USD high-impact release), or
- a spike occurred: the close moved more than ``spike_atr_multiple`` times a session baseline
  ATR within ``spike_window_bars`` bars, and the bar is not inside the NY open manipulation
  window (manipulation is traded, so it is not treated as news).

Causality: the spike move uses only closes up to the bar, and the baseline for a bar uses only
ATR from earlier sessions of the same session label at the same bar offset within its session
(a rolling median that excludes the current session). Release times come from a schedule
published in advance.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class NewsGuardConfig:
    """Settings for the news and spike guard, from ``execution.news_spike_guard``."""

    calendar_path: Path
    blackout_minutes_before: int = 5
    blackout_minutes_after: int = 5
    spike_window_bars: int = 5
    spike_atr_multiple: float = 2.0
    baseline_lookback_sessions: int = 20
    exempt_open_manipulation: bool = True


def load_release_times(calendar_path: Path) -> list[datetime]:
    """Release times (UTC) from a calendar CSV written by ``market_data.news.calendar``.

    Args:
        calendar_path: Calendar CSV path.

    Returns:
        Release times as timezone-aware UTC datetimes.
    """
    frame = pd.read_csv(calendar_path, usecols=["utc_time"])
    return [
        datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        for value in frame["utc_time"]
    ]


def session_baseline_atr(
    atr: np.ndarray[Any, Any],
    session_ids: np.ndarray[Any, Any],
    session_labels: np.ndarray[Any, Any],
    lookback_sessions: int,
) -> np.ndarray[Any, Any]:
    """Median ATR over earlier sessions with the same label at the same bar offset.

    The baseline for a bar excludes its own session, so it is causal. Bars with no earlier
    history get NaN, which makes the spike test false for them.

    Args:
        atr: ATR value per bar.
        session_ids: Session identifier per bar.
        session_labels: Session label per bar (for example ``ny`` or ``london``).
        lookback_sessions: Number of earlier sessions in the rolling median.

    Returns:
        Baseline ATR per bar, NaN where there is no earlier history.
    """
    frame = pd.DataFrame(
        {
            "atr": np.asarray(atr, dtype=float),
            "session_id": np.asarray(session_ids),
            "label": np.asarray(session_labels).astype(str),
        }
    )
    frame["offset"] = frame.groupby("session_id").cumcount()
    frame["pos"] = np.arange(len(frame))
    baseline = np.full(len(frame), np.nan)
    for (_label, _offset), group in frame.groupby(["label", "offset"], sort=False):
        ordered = group.sort_values("session_id", kind="stable")
        prior = (
            ordered["atr"].shift(1).rolling(lookback_sessions, min_periods=1).median().to_numpy()
        )
        baseline[ordered["pos"].to_numpy()] = prior
    return baseline


def news_block_mask(
    bar_times: Sequence[datetime],
    close: np.ndarray[Any, Any],
    atr: np.ndarray[Any, Any],
    session_ids: np.ndarray[Any, Any],
    session_labels: np.ndarray[Any, Any],
    release_times: Sequence[datetime],
    config: NewsGuardConfig,
    *,
    open_manipulation_bars: int,
) -> np.ndarray[Any, Any]:
    """Boolean mask over bars: True where new entries are blocked.

    Args:
        bar_times: Bar start times.
        close: Close price per bar.
        atr: ATR per bar, used as the spike baseline source.
        session_ids: Session identifier per bar.
        session_labels: Session label per bar.
        release_times: Scheduled release times (UTC).
        config: Guard settings.
        open_manipulation_bars: Number of bars at the start of each NY session that are exempt
            from the spike rule when ``config.exempt_open_manipulation`` is set.

    Returns:
        Boolean mask, True where new entries are blocked.
    """
    times = np.array([pd.Timestamp(t).timestamp() for t in bar_times], dtype=float)
    releases = np.sort(np.array([pd.Timestamp(t).timestamp() for t in release_times], dtype=float))
    before = config.blackout_minutes_before * 60.0
    after = config.blackout_minutes_after * 60.0
    lo = np.searchsorted(releases, times - after, side="left")
    hi = np.searchsorted(releases, times + before, side="right")
    blackout = hi > lo

    close = np.asarray(close, dtype=float)
    window = config.spike_window_bars
    move = np.full(len(close), np.nan)
    if window < len(close):
        move[window:] = np.abs(close[window:] - close[:-window])
    baseline = session_baseline_atr(
        atr, session_ids, session_labels, config.baseline_lookback_sessions
    )
    with np.errstate(invalid="ignore"):
        spike = move > config.spike_atr_multiple * baseline

    labels = np.asarray(session_labels).astype(str)
    offsets = pd.Series(np.asarray(session_ids)).groupby(np.asarray(session_ids)).cumcount()
    exempt = np.zeros(len(close), dtype=bool)
    if config.exempt_open_manipulation:
        exempt = (labels == "ny") & (offsets.to_numpy() < open_manipulation_bars)
    return np.asarray(blackout | (spike & ~exempt), dtype=bool)


_REPO_ROOT = Path(__file__).resolve().parents[2]


def news_guard_config(block: Mapping[str, Any] | None) -> NewsGuardConfig | None:
    """Build the guard from ``execution.news_spike_guard``; None when the guard is disabled.

    Args:
        block: The ``execution.news_spike_guard`` config mapping, or None.

    Returns:
        The guard settings, or None when the guard is disabled or absent.
    """
    if block is None or not bool(block.get("enabled", False)):
        return None
    calendar = Path(str(block["calendar_path"]))
    if not calendar.is_absolute():
        calendar = _REPO_ROOT / calendar
    return NewsGuardConfig(
        calendar_path=calendar,
        blackout_minutes_before=int(block["blackout_minutes_before"]),
        blackout_minutes_after=int(block["blackout_minutes_after"]),
        spike_window_bars=int(block["spike_window_bars"]),
        spike_atr_multiple=float(block["spike_atr_multiple"]),
        baseline_lookback_sessions=int(block["baseline_lookback_sessions"]),
        exempt_open_manipulation=bool(block["exempt_open_manipulation"]),
    )


def causal_atr5(high: Any, low: Any, close: Any) -> np.ndarray[Any, Any]:
    """5-bar average true range from past bars only (used when no ``atr_5`` feature exists).

    shortcut: a plain 5-bar mean of true range, not the bundle's atr_5 definition; upgrade if
    the guard must match the bundle exactly.

    Args:
        high: High price per bar.
        low: Low price per bar.
        close: Close price per bar.

    Returns:
        Rolling 5-bar mean of true range, one value per bar.
    """
    high_s = pd.Series(np.asarray(high, dtype=float))
    low_s = pd.Series(np.asarray(low, dtype=float))
    prev_close = pd.Series(np.asarray(close, dtype=float)).shift(1)
    true_range = pd.concat(
        [high_s - low_s, (high_s - prev_close).abs(), (low_s - prev_close).abs()], axis=1
    ).max(axis=1)
    return true_range.rolling(5, min_periods=1).mean().to_numpy(dtype=float)
