"""Focused simulation transition service."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from decisioning.observation_state import ENTRY_STATE_DIM, entry_state_one_hot
from features.context.trade_setup_candidates import trade_setup_event_identity_record
from simulation.environment.diagnostics import note_debug_step
from simulation.environment.episode_equity import assess_train_equity
from simulation.environment.rewards import SurvivalReward

from .mixin_base import RuntimeMixinBase


class StepEndRuntimeMixin(RuntimeMixinBase):
    """Resolve pending orders, transition completion, and episode accounting."""

    _pending_entry_order: dict[str, Any] | None
    _opened_this_step: bool
    episode_step_count: int
    _ep_reward_sum: float

    def _resolve_step_end(
        self,
        action: int | float | np.ndarray[Any, Any],
        discrete_action: int,
        risk_frac: float,
        entry_machine: Any,
        valuation_time: Any,
        close_reason: str,
        reward: float,
        reward_parts: dict[str, float],
        obs: dict[str, np.ndarray[Any, Any]],
        info: dict[str, Any],
        done: bool,
        truncated: bool,
    ) -> tuple[dict[str, np.ndarray[Any, Any]], float, bool, bool, dict[str, Any]]:
        """Resolve step end.

        Args:
            action: Action to apply to the current state.
            discrete_action: Numeric value used for the discrete action.
            risk_frac: Numeric value used for the risk frac.
            entry_machine: Entry machine used by the operation described above.
            valuation_time: Valuation time used by the operation described above.
            close_reason: Text or path value identifying the close reason.
            reward: Numeric value used for the reward.
            reward_parts: Key-value data used for the reward parts.
            obs: Key-value data used for the obs.
            info: Key-value data used for the info.
            done: Whether to enable or require the done.
            truncated: Whether to enable or require the truncated.

        Returns:
            Whether resolve step end meets the requested condition.
        """
        self._advance_ny_step()
        if entry_machine is not None and entry_machine.state == "IN_POSITION":
            if self.position is None:
                entry_machine.mark_closed()
                info["entry_state"] = entry_machine.state
                if self.entry_state_observation:
                    entry_start = self.observation_schema.width - ENTRY_STATE_DIM
                    obs["account"][entry_start:] = np.asarray(
                        entry_state_one_hot(entry_machine.state), dtype=np.float32
                    )
        if self._ny_pos < len(self._ny_indices) and self.step_idx < self._n_bars:
            obs = self._get_observation()
        self.episode_step_count += 1

        # Data end is normally a truncation; survival training treats it as the
        # terminal outcome because no later split data is available to bootstrap.
        completed_data_split = self._ny_pos >= len(self._ny_indices)
        if self.reward_mode == "survival":
            survival_reward = self.reward_fn
            if not isinstance(survival_reward, SurvivalReward):
                raise RuntimeError(
                    "survival reward mode was initialized with a non-survival reward"
                )
            breached = bool(self.breach_log)
            if completed_data_split or breached:
                done = True
                truncated = False
            reward = survival_reward(
                breached=breached,
                completed_data_split=completed_data_split,
            )
            reward_parts = dict(survival_reward.last_parts)
            info["reward_parts"] = reward_parts
        elif completed_data_split and not done:
            truncated = True

            # Apply max_episode_steps truncation last so it overrides
            # data-end signals consistently. Do not convert a year-fail
            # (terminated) into a pure truncation when the cap also fires.
        if self.max_episode_steps is not None and self.episode_step_count >= self.max_episode_steps:
            truncated = True

        if (done or truncated) and self._pending_entry_order is not None:
            pending = self._pending_entry_order
            self._pending_entry_order = None
            selected = pending.get("selected", {})
            selected_setup = selected.get("_selected_trade_setup")
            self.trade_log.append(
                {
                    "type": "order_cancel",
                    "decision_id": str(pending.get("decision_id", "")),
                    "order_id": pending.get("order_id"),
                    "order_type": pending.get("order_type", "market"),
                    "trade_setup_candidate_id": (
                        None if selected_setup is None else int(selected_setup.candidate_id)
                    ),
                    **trade_setup_event_identity_record(
                        selected.get("_selected_trade_setup_event_identity")
                    ),
                    "reason": (
                        "episode_ended_before_limit_expiry"
                        if pending.get("order_type") == "limit"
                        else "episode_ended_before_scheduled_fill"
                    ),
                    "decision_time": pending["decision_time"],
                    "decision_bar_time": pending["decision_bar_time"],
                    "order_submission_time": pending["order_submission_time"],
                    "expiry_time": pending.get("expiry_time"),
                    "limit_price": pending.get("limit_price"),
                    "time": valuation_time,
                    "fill_time": None,
                    "bar": self.step_idx,
                }
            )

        if self._debug_trace and self._debug_window is not None:
            note_debug_step(
                self._debug_window,
                reward=float(reward),
                reward_parts=reward_parts,
                opened=bool(self._opened_this_step),
                entered=discrete_action in (1, -1),
                risk_frac=float(risk_frac),
                close_reason=close_reason,
                action=action,
                position=self.position is not None,
                position_direction=0 if self.position is None else int(self.position.direction),
            )

        self._ep_reward_sum += float(reward)
        if done or truncated:
            n_trades = len([t for t in self.trade_log if t.get("type") == "open"])
            gate = assess_train_equity(
                pd.Series(self.equity_curve, dtype=float),
                initial=float(self._ep_start_equity),
                breached=bool(self.breach_log),
                peak_trailing_dd_limit=float(self.peak_trailing_dd_limit),
                peak_eod_trailing_dd_limit_usd=float(self._peak_eod_trailing_dd_limit_usd),
                max_peak_eod_trailing_dd_usd=float(self.account.max_peak_eod_drawdown_usd),
            )
            if done:
                if self.repeated_payout_policy and self.cycle_successes > 0 and not self.breach_log:
                    episode_end_reason = "payout_success"
                elif (
                    self.reward_mode == "survival" and completed_data_split and not self.breach_log
                ):
                    episode_end_reason = "data_end_survived"
                else:
                    episode_end_reason = "risk_breach" if self.breach_log else "terminated"
            elif completed_data_split:
                episode_end_reason = "data_end"
            elif self.max_episode_steps is not None and (
                self.episode_step_count >= self.max_episode_steps
            ):
                episode_end_reason = "max_episode_steps"
            else:
                episode_end_reason = "truncated"
            info["episode_equity"] = {
                "end_equity": float(self.account.equity),
                "start_equity": float(self._ep_start_equity),
                "reward_sum": float(self._ep_reward_sum),
                "n_trades": int(n_trades),
                "episode_steps": int(self.episode_step_count),
                "completed_data_split": bool(completed_data_split),
                "episode_end_reason": episode_end_reason,
                "breach_reason": str(self.breach_log[-1]) if self.breach_log else "",
                "slope": float(gate["slope"]),
                "max_peak_trailing_dd": float(gate["max_peak_trailing_dd"]),
                "peak_trailing_dd_limit": float(self.peak_trailing_dd_limit),
                "max_peak_eod_trailing_dd_usd": float(self.account.max_peak_eod_drawdown_usd),
                "peak_eod_trailing_dd_limit_usd": float(self._peak_eod_trailing_dd_limit_usd),
            }

        return obs, float(reward), done, truncated, info


__all__ = ["StepEndRuntimeMixin"]
