from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from features.context.entry_ideas import entry_idea_context
from simulation.entry_evidence import build_entry_evidence
from simulation.entry_state import EntryCandidate, EntryEvidence
from simulation.environment.diagnostics import new_debug_window, summarize_window, wiring_from_env
from trading.orders import manipulation_state
from trading.strategies import BaselineStrategy

from .entry_diagnostics import _REJECTION_COUNTERS
from .market_view import FeatureRow
from .mixin_base import RuntimeMixinBase


class DiagnosticsRuntimeMixin(RuntimeMixinBase):
    """Collect rollout diagnostics and derive entry evidence from feature rows."""

    _debug_window: dict[str, Any] | None

    def enable_debug_trace(self) -> None:
        """Start per-rollout counters and step-failure snapshots."""
        self._debug_trace = True
        self._debug_window = new_debug_window()

    def debug_flush(self) -> dict[str, Any]:
        """Return the counters since the last flush and start a new window.

        Returns:
            Mapping from ``str`` keys to ``Any`` values.
        """
        if not self._debug_trace or self._debug_window is None:
            return {}
        summary = summarize_window(self._debug_window)
        self._debug_window = new_debug_window()
        return summary

    def debug_wiring(self) -> dict[str, Any]:
        """Reward and risk settings this env was built with.

        Returns:
            Mapping from ``str`` keys to ``Any`` values.
        """
        return wiring_from_env(self)

    def _note_session_open(self, session_id: int, feat_row: FeatureRow | pd.Series) -> None:
        """Remember the first bar of this session and a post-open manip end.

        Args:
            session_id: Numeric value used for the session id.
            feat_row: Feature values for the current market bar.
        """
        self._session_open_idx.setdefault(session_id, self.step_idx)
        if float(feat_row.get("po3_manipulation_end", 0.0) or 0.0) > 0.0:
            self._ny_manip_confirmed.add(session_id)

    def _arm_po3_confirm(self, session_id: int) -> None:
        """Let Idea 1 use a side only after this session's manipulation ends.

        Args:
            session_id: Numeric value used for the session id.
        """
        if getattr(self.strategy, "name", "") != "po3_ifvg":
            return
        setattr(
            self.strategy,
            "_session_manip_confirmed",
            session_id in self._ny_manip_confirmed,
        )

    def _entry_action_requested(self, discrete_action: int) -> bool:
        """Interpret whether the decoded policy action requests entry execution.

        Args:
            discrete_action: Numeric value used for the discrete action.

        Returns:
            Whether entry action requested meets the requested condition.
        """
        if not self.strategy_actions:
            return discrete_action in (-1, 1)
        intensity = self._decision_action.get("intensity_u", float("nan"))
        return bool(np.isfinite(intensity) and intensity >= self.entry_intensity_threshold)

    def entry_evidence_context(self, feat_row: FeatureRow | pd.Series) -> EntryEvidence:
        """Translate shared strategy predicates into one causal evidence record.

        Args:
            feat_row: Current feature values used by strategy entry predicates.

        Returns:
            Entry evidence and source-event identities for the current bar.
        """
        return build_entry_evidence(
            strategy=self.strategy,
            feature_row=feat_row,
            bar=self.step_idx,
            candidate=(
                self.entry_state_machine.candidate
                if isinstance(self.strategy, BaselineStrategy)
                and self.entry_state_machine is not None
                else None
            ),
            bars_index=None if self.bars is None else self.bars.index,
            state_machine_enabled=self.entry_state_machine is not None,
        )

    def _lock_unconfirmed_side(
        self,
        discrete_action: int,
        feat_row: FeatureRow | pd.Series,
        risk_frac: float,
        *,
        entry_candidate: EntryCandidate | None = None,
    ) -> tuple[int, float]:
        """During an open manipulation, keep only the side the strategy already offers.

        A direction override, or a side invented when the strategy has none,
        becomes no trade. The strategy's own sweep or swing entry stays.

        Args:
            discrete_action: Numeric value used for the discrete action.
            feat_row: Feature values for the current market bar.
            risk_frac: Numeric value used for the risk frac.
            entry_candidate: Entry candidate used by the operation described above.

        Returns:
            Values returned by ``_lock_unconfirmed_side``, in the declared order.
        """
        if not self.strategy_actions or discrete_action == 0:
            return discrete_action, risk_frac
        if manipulation_state(feat_row) != "against":
            return discrete_action, risk_frac
            # PO3 manipulation state must not veto a separately active idea such as
            # an Order Block reaction, FVG retest, or swing retracement.
        if entry_idea_context(feat_row, discrete_action)["ideas"]:
            return discrete_action, risk_frac
        if (
            isinstance(self.strategy, BaselineStrategy)
            and entry_candidate is not None
            and discrete_action == entry_candidate.direction
        ):
            return discrete_action, risk_frac
        ctx = int(self.strategy.context_direction(feat_row))
        if discrete_action == ctx:
            return discrete_action, risk_frac
        self._reject("manipulation_unconfirmed")
        return 0, 0.0

    def _reject(self, reason: str) -> None:
        """Refuse an entry: bump its counter and stamp the reason, atomically.

        The mapping lives in :data:`_REJECTION_COUNTERS`. An unregistered
        reason raises ``KeyError`` here rather than silently producing a ratio
        or trade-log entry with no backing bucket.

        Args:
            reason: Text or path value identifying the reason.
        """
        self._entry_diag[_REJECTION_COUNTERS[reason]] += 1
        # A refusal that arrives after PPO requested an ARMED trigger counts as
        # a trigger refusal, so the arm->trigger conversion rate is measurable.
        if self._trigger_requested_this_step and self.entry_state_machine is not None:
            self.entry_state_machine.trigger_refused += 1
        self._entry_rejection_reason = reason
        self._entry_rejection_decision_id = self._current_decision_id

    def _in_open_blackout(self, session_id: int) -> bool:
        """Process open blackout.

        Args:
            session_id: Numeric value used for the session id.

        Returns:
            Whether in open blackout meets the requested condition.
        """
        if self.open_manipulation_bars <= 0:
            return False
        start = self._session_open_idx.get(session_id, self.step_idx)
        return bool((int(self.step_idx) - int(start)) < int(self.open_manipulation_bars))

    def _matched_entry_level(self, session_id: int, discrete_action: int) -> tuple[str | None, Any]:
        """Match an entry to the most recently crossed liquidity level.

        Args:
            session_id: Current trading session identifier.
            discrete_action: Signed action (+1 long, -1 short).

        Returns:
            Tuple of (level name or None, crossing time or None). Longs
            match high levels, shorts match low levels.
        """
        candidates = {
            name
            for (sid, name) in self._level_crosses
            if sid == session_id
            and (name.endswith("high") if discrete_action > 0 else name.endswith("low"))
        }
        if not candidates:
            return None, None
        latest_cross_time = max(self._level_crosses[(session_id, name)] for name in candidates)
        latest_name = min(
            name
            for name in candidates
            if self._level_crosses[(session_id, name)] == latest_cross_time
        )
        return latest_name, self._level_crosses[(session_id, latest_name)]

    def entry_state_diagnostics(self) -> dict[str, Any]:
        """Aggregate entry-state lifecycle counters for reporting.

        Reads the FSM's own counters (never infers them from feature data), so
        the reporting surface is owned by the object that owns the lifecycle.
        Returns an empty dict when the FSM is off (A3), so callers can merge
        unconditionally.

        Returns:
            Mapping from ``str`` keys to ``Any`` values.
        """
        machine = self.entry_state_machine
        if machine is None:
            return {}
        total_steps = max(1, int(self.episode_step_count))
        visits = dict(machine.visits)
        armed_bars = max(1, machine.armed_bars)
        return {
            "entry_state_machine": True,
            "entry_state_visits": visits,
            "entry_state_share": {
                state: round(count / total_steps, 6) for state, count in visits.items()
            },
            "candidate_created": int(machine.candidate_created),
            "candidate_expired": int(machine.candidate_expired),
            "candidate_invalidated": int(machine.candidate_invalidated),
            "trigger_requested": int(machine.trigger_requested),
            "trigger_refused": int(machine.trigger_refused),
            "entered": int(machine.entered),
            "closed": int(machine.closed),
            "armed_bars": int(machine.armed_bars),
            "arm_to_trigger_rate": round(machine.entered / armed_bars, 6),
            "trigger_refusal_rate": round(
                machine.trigger_refused / max(1, machine.trigger_requested), 6
            ),
        }
