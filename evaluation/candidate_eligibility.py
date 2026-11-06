"""Static session and fill-bar eligibility checks for candidate proposals."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class CandidateActionEligibility:
    """Policy-action eligibility and the configured entry fill bar."""

    eligible: bool
    reason: str
    fill_position: int | None
    fill_time: str | None
    session_close_time: str | None = None


class CandidateActionEligibilityIndex:
    """Precomputed O(1) session/fill eligibility for many candidate rows."""

    def __init__(
        self,
        index: pd.DatetimeIndex,
        session_labels: pd.Series,
        *,
        session_ids: pd.Series | None = None,
        fill_latency_bars: int = 0,
        open_manipulation_bars: int = 0,
        block_overnight: bool = True,
        session_step_minutes: int = 1,
    ) -> None:
        """Index session boundaries and possible fill positions once.

        Args:
            index: Sorted, unique timestamps for the complete bar series.
            session_labels: Session eligibility label for each bar.
            session_ids: Optional session identity aligned to the bar index.
            fill_latency_bars: Additional bars before a market order can fill.
            open_manipulation_bars: Number of opening bars blocked from entry.
            block_overnight: Whether fills crossing the session boundary are rejected.
            session_step_minutes: Duration represented by one bar, in minutes.
        """
        if not index.is_unique or not index.is_monotonic_increasing:
            raise ValueError("candidate eligibility requires a sorted unique bar index")
        if len(session_labels) != len(index):
            raise ValueError("session_labels must align with the complete bar index")
        if session_ids is not None and len(session_ids) != len(index):
            raise ValueError("session_ids must align with the complete bar index")
        if isinstance(fill_latency_bars, bool) or fill_latency_bars < 0:
            raise ValueError("fill_latency_bars must be a non-negative integer")
        if int(fill_latency_bars) != fill_latency_bars:
            raise ValueError("fill_latency_bars must be a non-negative integer")
        if isinstance(open_manipulation_bars, bool) or open_manipulation_bars < 0:
            raise ValueError("open_manipulation_bars must be non-negative")
        if isinstance(session_step_minutes, bool) or session_step_minutes <= 0:
            raise ValueError("session_step_minutes must be positive")

        self.index = index
        self.labels = session_labels.astype(str).to_numpy()
        self.session_ids = (
            pd.DatetimeIndex(index).normalize().to_numpy(dtype="datetime64[ns]").view("i8")
            if session_ids is None
            else session_ids.to_numpy()
        )
        self.fill_latency_bars = int(fill_latency_bars)
        self.open_manipulation_bars = int(open_manipulation_bars)
        self.block_overnight = bool(block_overnight)
        self.session_step_minutes = int(session_step_minutes)
        self.ny_positions = np.flatnonzero(self.labels == "ny")
        self.ny_position_by_row = np.full(len(index), -1, dtype=np.int64)
        self.ny_position_by_row[self.ny_positions] = np.arange(
            self.ny_positions.size, dtype=np.int64
        )
        self.session_open_position: dict[object, int] = {}
        self.session_last_position: dict[object, int] = {}
        for row in self.ny_positions:
            session_id = self.session_ids[int(row)]
            self.session_open_position.setdefault(session_id, int(row))
            self.session_last_position[session_id] = int(row)

    def classify(self, position: int) -> CandidateActionEligibility:
        """Classify one row and resolve its fill bar under the configured gates.

        Args:
            position: Row position in the indexed bar series.

        Returns:
            Eligibility status, reason, fill bar, and session close timestamp.
        """
        if isinstance(position, bool) or not 0 <= int(position) < len(self.index):
            raise ValueError("position is outside the bar index")
        row = int(position)
        if self.labels[row] != "ny":
            return CandidateActionEligibility(False, "off_session", None, None)

        session_id = self.session_ids[row]
        session_open_position = self.session_open_position[session_id]
        session_close_time = (
            pd.Timestamp(self.index[self.session_last_position[session_id]])
            + pd.Timedelta(minutes=self.session_step_minutes)
        ).isoformat()
        if row - session_open_position < self.open_manipulation_bars:
            return CandidateActionEligibility(
                False, "open_blackout", None, None, session_close_time
            )

        latency = self.fill_latency_bars
        if latency == 0:
            fill_position = row + 1
            if fill_position >= len(self.index):
                return CandidateActionEligibility(
                    False, "missing_fill_bar", None, None, session_close_time
                )
        else:
            ny_position = int(self.ny_position_by_row[row])
            target_ny_position = ny_position + 1 + latency
            if target_ny_position >= self.ny_positions.size:
                return CandidateActionEligibility(
                    False, "missing_fill_bar", None, None, session_close_time
                )
            fill_position = int(self.ny_positions[target_ny_position])

        fill_label = self.labels[fill_position]
        fill_session = self.session_ids[fill_position]
        if (self.block_overnight or latency > 0) and fill_label != "ny":
            return CandidateActionEligibility(
                False, "fill_bar_off_session", None, None, session_close_time
            )
        if self.block_overnight and fill_session != session_id:
            return CandidateActionEligibility(
                False, "overnight_boundary", None, None, session_close_time
            )
        if self.block_overnight:
            fill_ny_position = int(self.ny_position_by_row[fill_position])
            next_ny_position = fill_ny_position + 1
            if next_ny_position >= self.ny_positions.size:
                return CandidateActionEligibility(
                    False, "overnight_boundary", None, None, session_close_time
                )
            next_position = int(self.ny_positions[next_ny_position])
            if self.session_ids[next_position] != session_id:
                return CandidateActionEligibility(
                    False, "overnight_boundary", None, None, session_close_time
                )

        return CandidateActionEligibility(
            eligible=True,
            reason="eligible",
            fill_position=fill_position,
            fill_time=pd.Timestamp(self.index[fill_position]).isoformat(),
            session_close_time=session_close_time,
        )


def classify_candidate_action_eligibility(
    index: pd.DatetimeIndex,
    session_labels: pd.Series,
    position: int,
    *,
    session_ids: pd.Series | None = None,
    fill_latency_bars: int = 0,
    open_manipulation_bars: int = 0,
    block_overnight: bool = True,
    session_step_minutes: int = 1,
) -> CandidateActionEligibility:
    """Mirror the environment's NY step, open blackout, and fill-bar gates.

    Feature rows remain untouched. This helper classifies whether a candidate
    row can produce an entry action and identifies the market bar used for its
    configured fill latency.

    Args:
        index: Sorted, unique timestamps for the full bar series.
        session_labels: Session label for each indexed bar.
        position: Candidate decision row position.
        session_ids: Optional per-bar session identities.
        fill_latency_bars: Additional bars before the market fill.
        open_manipulation_bars: Opening blackout length in bars.
        block_overnight: Whether entries crossing session boundaries are rejected.
        session_step_minutes: Duration represented by each bar.

    Returns:
        Classification and resolved fill-bar information for the candidate.
    """
    eligibility = CandidateActionEligibilityIndex(
        index,
        session_labels,
        session_ids=session_ids,
        fill_latency_bars=fill_latency_bars,
        open_manipulation_bars=open_manipulation_bars,
        block_overnight=block_overnight,
        session_step_minutes=session_step_minutes,
    )
    return eligibility.classify(position)


__all__ = [
    "CandidateActionEligibility",
    "CandidateActionEligibilityIndex",
    "classify_candidate_action_eligibility",
]
