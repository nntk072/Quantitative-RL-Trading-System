"""Session labels and eligibility masks over source-clock chart timestamps.

Configured consumers pass an exchange/session timezone and source-clock model.
Calls without those arguments preserve the legacy fixed-offset behavior.
"""

from __future__ import annotations

from typing import Literal, cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray

SessionName = Literal["asia", "london", "ny", "closed"]

_ASIA_START = "01:05"
_ASIA_END = "09:00"
_LONDON_END = "16:30"
_NY_END_DEFAULT = "23:00"
_NY_WINDOWS = {
    "America/New_York": ("18:05", "02:00", "09:30", "16:00"),
    "America/Chicago": ("17:05", "01:00", "08:30", "15:00"),
}


def session_reference_index(
    index: pd.DatetimeIndex,
    source_clock_model: str = "native",
) -> pd.DatetimeIndex:
    """Interpret source wall labels and return timezone-aware instants.

    Helsinki source labels discard the fixed-offset carrier and use IANA DST
    rules. Ambiguous and nonexistent labels fail closed because exports contain
    no fold marker. The legacy FTMO model remains for registered old runs.

    Args:
        index: Source timestamps whose wall labels need interpretation.
        source_clock_model: Registered interpretation for source wall labels.

    Returns:
        Index of timestamps interpreted as timezone-aware instants.
    """
    if source_clock_model == "native":
        return index
    if source_clock_model == "europe_helsinki":
        return index.tz_localize(None).tz_localize(
            "Europe/Helsinki", ambiguous="raise", nonexistent="raise"
        )
    if source_clock_model == "ftmo_mt5_us_dst":
        if index.tz is None:
            raise ValueError("the legacy FTMO source clock requires a timezone-aware index")
        new_york_wall = index.tz_localize(None) - pd.Timedelta(hours=7)
        return new_york_wall.tz_localize("America/New_York", ambiguous="raise", nonexistent="raise")
    raise ValueError(f"unsupported source clock model: {source_clock_model!r}")


def _session_windows(tz: str, ny_end: str | None) -> tuple[str, str, str, str]:
    """Return default Asia and NY session boundaries for a session timezone.

    Args:
        tz: IANA timezone used to select the session window defaults.
        ny_end: Optional configured NY close override.

    Returns:
        Asia open/close and NY open/close as ``HH:MM`` strings.
    """
    if tz in _NY_WINDOWS:
        asia_start, asia_end, ny_start, default_ny_end = _NY_WINDOWS[tz]
        return asia_start, asia_end, ny_start, ny_end or default_ny_end
    return _ASIA_START, _ASIA_END, _LONDON_END, ny_end or _NY_END_DEFAULT


def _inside_window(values: NDArray[np.object_], start: str, end: str) -> NDArray[np.bool_]:
    """Return which clock values fall inside a possibly overnight interval.

    Args:
        values: Clock values to test.
        start: Inclusive interval start as ``HH:MM``.
        end: Exclusive interval end as ``HH:MM``.

    Returns:
        Boolean mask aligned to ``values``.
    """
    start_t, end_t = _hhmm(start).time(), _hhmm(end).time()
    if start_t < end_t:
        return (values >= start_t) & (values < end_t)
    return (values >= start_t) | (values < end_t)


def _hhmm(value: str) -> pd.Timestamp:
    """Process the requested value.

    Args:
        value: Value to process.

    Returns:
        Result of process the requested value.
    """
    return pd.Timestamp(f"2000-01-01 {value}")


def get_session(
    timestamp: pd.Timestamp | str,
    tz: str = "Etc/GMT-3",
    ny_end: str | None = None,
    source_clock_model: str = "native",
) -> SessionName:
    """Return the broker-tz session label for a timestamp.

    Args:
        timestamp: Timestamp to classify (naive timestamps are localized to ``tz``).
        tz: Session timezone used when ``timestamp`` is naive.
        ny_end: Inclusive NY-session end as HH:MM.
        source_clock_model: Interpretation of source-index wall labels.

    Returns:
        Session label for the timestamp.
    """
    ts = pd.Timestamp(timestamp) if isinstance(timestamp, str) else timestamp
    source = pd.DatetimeIndex([ts])
    if source.tz is None and source_clock_model == "native":
        source = source.tz_localize(tz)
    ts = session_reference_index(source, source_clock_model).tz_convert(tz)[0]
    t = ts.time()
    asia_start, asia_end, ny_start, ny_end_value = _session_windows(tz, ny_end)
    if _inside_window(np.asarray([t]), asia_start, asia_end)[0]:
        return "asia"
    if _hhmm(asia_end).time() <= t < _hhmm(ny_start).time():
        return "london"
    if _hhmm(ny_start).time() <= t <= _hhmm(ny_end_value).time():
        return "ny"
    return "closed"


def ny_session_mask(
    index: pd.DatetimeIndex,
    start: str | None = None,
    end: str | None = None,
    *,
    session_tz: str | None = None,
    source_clock_model: str = "native",
) -> pd.Series:
    """Boolean mask of bars whose clock time falls in the tradable NY window.

    Args:
        index: Position or label identifying the requested item.
        start: Session start as HH:MM. Defaults to the selected exchange clock.
        end: Session end as HH:MM. Defaults to the selected exchange clock.
        session_tz: IANA timezone for boundaries; ``None`` preserves legacy behavior.
        source_clock_model: Interpretation of source-index wall labels.

    Returns:
        Result of boolean mask of bars whose clock time falls in the tradable NY window.
    """
    if session_tz is None:
        start_value, end_value = start or "16:30", end or "23:00"
        local = index
    else:
        local = session_reference_index(index, source_clock_model)
        if local.tz is None:
            if source_clock_model != "native":
                raise ValueError(
                    f"source clock {source_clock_model!r} requires a timezone-aware index"
                )
            local = local.tz_localize(session_tz)
        local = local.tz_convert(session_tz)
        _, _, default_start, default_end = _session_windows(session_tz, None)
        start_value, end_value = start or default_start, end or default_end
    start_t, end_t = _hhmm(start_value).time(), _hhmm(end_value).time()
    values = local.time
    if start_t <= end_t:
        mask = (values >= start_t) & (values <= end_t)
    else:
        mask = (values >= start_t) | (values <= end_t)
    return pd.Series(mask, index=index)


def add_session_labels(
    df: pd.DataFrame,
    tz: str = "Etc/GMT-3",
    ny_end: str | None = None,
    source_clock_model: str = "native",
) -> pd.DataFrame:
    """Add a ``session`` column (asia/london/ny/closed) using :func:`get_session`.

    Args:
        df: Input DataFrame supplying the rows used by this calculation.
        tz: Session timezone.
        ny_end: Inclusive NY-session end.
        source_clock_model: Interpretation of source-index wall labels.

    Returns:
        DataFrame returned by ``add_session_labels``.
    """
    df = df.copy()
    index = cast(pd.DatetimeIndex, df.index)
    source = index
    if source.tz is None and source_clock_model == "native":
        source = source.tz_localize(tz)
    local = session_reference_index(source, source_clock_model).tz_convert(tz)
    t = local.time
    asia_start, asia_end, ny_start, ny_end_value = _session_windows(tz, ny_end)
    labels = np.empty(len(index), dtype=object)
    labels[:] = "closed"
    labels[_inside_window(t, asia_start, asia_end)] = "asia"
    labels[(_hhmm(asia_end).time() <= t) & (t < _hhmm(ny_start).time())] = "london"
    labels[(_hhmm(ny_start).time() <= t) & (t <= _hhmm(ny_end_value).time())] = "ny"
    df["session"] = labels
    return df


def filter_session(
    df: pd.DataFrame,
    start: str | None = None,
    end: str | None = None,
    *,
    session_tz: str | None = None,
    source_clock_model: str = "native",
) -> pd.DataFrame:
    """Keep only bars inside the NY tradable window.

    This is an eligibility-mask helper. Do not apply it to the feature dataset.

    Args:
        df: Input DataFrame supplying the rows used by this calculation.
        start: Text or path value identifying the start.
        end: Text or path value identifying the end.
        session_tz: IANA timezone for session boundaries; ``None`` keeps legacy behavior.
        source_clock_model: Interpretation of source-index wall labels.

    Returns:
        DataFrame returned by ``filter_session``.
    """
    df = df.copy()
    index = cast(pd.DatetimeIndex, df.index)
    mask = ny_session_mask(
        index, start=start, end=end, session_tz=session_tz, source_clock_model=source_clock_model
    )
    return df.loc[mask]


def add_session_id(
    df: pd.DataFrame,
    *,
    session_tz: str | None = None,
    source_clock_model: str = "native",
) -> pd.DataFrame:
    """Add a ``session_id`` integer column: unique per calendar date.

    Args:
        df: Input DataFrame supplying the rows used by this calculation.
        session_tz: Timezone used to derive each row's calendar-session date.
        source_clock_model: Interpretation of source-index wall labels.

    Returns:
        DataFrame returned by ``add_session_id``.
    """
    df = df.copy()
    dates = cast(pd.DatetimeIndex, df.index)
    if session_tz is not None:
        dates = session_reference_index(dates, source_clock_model).tz_convert(session_tz)
    dates = dates.normalize()
    unique_dates = sorted(set(dates))
    date_to_id = {d: i for i, d in enumerate(unique_dates)}
    df["session_id"] = dates.map(date_to_id)
    return df
