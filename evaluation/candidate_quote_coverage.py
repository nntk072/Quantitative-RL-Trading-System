"""Conservative minute-level quote coverage for conditional proposal replay."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class CandidateQuoteCoverage:
    """Dense source-minute coverage index with first-gap lookup."""

    timezone: str
    first_minute: pd.Timestamp
    complete_minutes: np.ndarray[Any, Any]
    incomplete_prefix: np.ndarray[Any, Any]

    @classmethod
    def from_csv(cls, path: str | Path, *, timezone: str) -> CandidateQuoteCoverage:
        """Load an audit CSV whose index is naive source-wall-clock minute.

        Args:
            path: Audit CSV containing minute-level quote completeness.
            timezone: Source timezone used to interpret the naive index.

        Returns:
            Dense minute coverage index for interval gap lookups.
        """
        frame = pd.read_csv(path, parse_dates=[0])
        if frame.empty or "quote_complete" not in frame:
            raise ValueError("quote coverage CSV must contain rows and quote_complete")
        minute_index = pd.DatetimeIndex(frame.iloc[:, 0])
        if minute_index.tz is not None:
            raise ValueError("quote coverage index must be naive source wall-clock")
        if not minute_index.is_unique or not minute_index.is_monotonic_increasing:
            raise ValueError("quote coverage minutes must be sorted and unique")
        if not minute_index.equals(minute_index.floor("min")):
            raise ValueError("quote coverage timestamps must align to whole minutes")
        first = minute_index[0]
        last = minute_index[-1]
        dense_index = pd.date_range(first, last, freq="min")
        values = np.zeros(len(dense_index), dtype=bool)
        offsets = ((minute_index - first) / pd.Timedelta(minutes=1)).to_numpy(dtype=np.int64)
        values[offsets] = frame["quote_complete"].astype(bool).to_numpy()
        prefix = np.concatenate(([0], np.cumsum(~values, dtype=np.int64)))
        return cls(timezone, first, values, prefix)

    def first_incomplete_minute(
        self, start: str | pd.Timestamp, end: str | pd.Timestamp
    ) -> pd.Timestamp | None:
        """Return the first uncovered/invalid UTC minute in ``[start, end)``.

        Args:
            start: Inclusive timezone-aware start of the coverage interval.
            end: Exclusive timezone-aware end of the coverage interval.

        Returns:
            First uncovered minute in UTC, or ``None`` when the interval is complete.
        """
        start_utc = pd.Timestamp(start)
        end_utc = pd.Timestamp(end)
        if start_utc.tz is None or end_utc.tz is None:
            raise ValueError("coverage interval bounds must be timezone-aware")
        start_utc = start_utc.tz_convert("UTC")
        end_utc = end_utc.tz_convert("UTC")
        if end_utc <= start_utc:
            return None
        local_start = start_utc.tz_convert(self.timezone).tz_localize(None).floor("min")
        local_end = end_utc.tz_convert(self.timezone).tz_localize(None).ceil("min")
        left = int((local_start - self.first_minute) / pd.Timedelta(minutes=1))
        right = int((local_end - self.first_minute) / pd.Timedelta(minutes=1))
        if left < 0:
            return start_utc
        extends_past_coverage = right > len(self.complete_minutes)
        if right > len(self.complete_minutes):
            right = len(self.complete_minutes)
        if left >= len(self.complete_minutes):
            return start_utc
        if right > left and self.incomplete_prefix[right] != self.incomplete_prefix[left]:
            local_offset = left + int(np.flatnonzero(~self.complete_minutes[left:right])[0])
        elif extends_past_coverage:
            local_offset = len(self.complete_minutes)
        else:
            return None
        first_incomplete = self.first_minute + pd.Timedelta(minutes=local_offset)
        return max(first_incomplete.tz_localize(self.timezone).tz_convert("UTC"), start_utc)


__all__ = ["CandidateQuoteCoverage"]
