"""PO3 phase and entry-context features."""

from __future__ import annotations

import numpy as np
import pandas as pd

OUTSIDE_SESSION_PHASE = -1


def build_po3_phase_features(
    index: pd.DatetimeIndex,
    session_start: str = "16:30",
    session_end: str = "23:00",
) -> pd.DataFrame:
    """PO3 (Power of 3) daily-cycle phase tag, causally time-derived.

    Maps each bar's time-of-day position inside the trading session onto the
    classic PO3 arc: accumulation (session open) → manipulation (middle) →
    distribution (session close). This is a function of the timestamp only,
    so it is identical across timeframes once aligned onto the M1 spine —
    computed once here rather than duplicated per TF.

    Returns a DataFrame indexed like ``index``. Its ``po3_phase`` column is -1
    outside the session and 0/1/2 for accumulation, manipulation, and
    distribution while active. Its ``session_progress`` column is the fraction
    of session elapsed, clipped to [0, 1]; the phase sentinel distinguishes
    clipped out-of-session values from active session boundaries.

    Args:
        index: Position or label identifying the requested item.
        session_start: Text or path value identifying the session start.
        session_end: Text or path value identifying the session end.

    Returns:
        DataFrame returned by ``build_po3_phase_features``.
    """
    tz = index.tz
    start_ts = pd.Timestamp(f"2000-01-01 {session_start}").tz_localize(tz)
    end_ts = pd.Timestamp(f"2000-01-01 {session_end}").tz_localize(tz)
    session_len = (end_ts - start_ts).total_seconds()
    if session_len <= 0.0:
        raise ValueError("session_end must be later than session_start")

    tod = np.asarray(index.hour * 3600 + index.minute * 60 + index.second, dtype=float)
    start_secs = start_ts.hour * 3600 + start_ts.minute * 60
    elapsed = tod - start_secs
    progress = pd.Series(np.clip(elapsed / session_len, 0.0, 1.0), index=index)
    phase_values = np.digitize(progress.to_numpy(), [1.0 / 3.0, 2.0 / 3.0]).astype(np.int8)
    outside_session = (elapsed < 0) | (elapsed > session_len)
    phase_values[outside_session] = OUTSIDE_SESSION_PHASE
    phase = pd.Series(phase_values, index=index, dtype="int8")
    return pd.DataFrame({"po3_phase": phase, "session_progress": progress})
