"""Behavior contracts for the policy-agnostic episode runner."""

from __future__ import annotations

from typing import Any

import pytest

from evaluation.rollout.episode_rollout import run_episode


class _ScriptedEpisode:
    def __init__(self, steps: list[dict[str, Any]]) -> None:
        self.steps = iter(steps)
        self.initial_balance = 100.0
        self.trade_log: list[dict[str, Any]] = []
        self.breach_events: list[dict[str, Any]] = []
        self.all_sessions = {"session-1", "session-2"}
        self._entry_diag = {"opened": 1, "rejected_daily_loss": 1}
        self.actions: list[Any] = []

    def reset(self) -> tuple[str, dict[str, Any]]:
        return "initial", {}

    def step(self, action: Any) -> tuple[str, float, bool, bool, dict[str, Any]]:
        self.actions.append(action)
        step = next(self.steps)
        return "next", 0.0, step.pop("done", False), step.pop("truncated", False), step

    def entry_state_diagnostics(self) -> dict[str, float]:
        return {"entry_state_transitions": 2.0}


def test_run_episode_collects_equity_accounting_and_entry_diagnostics() -> None:
    env = _ScriptedEpisode(
        [
            {
                "equity": 100.0,
                "account_state_snapshot": {"session_id": 1, "equity": 100.0},
            },
            {
                "episode_equity": {"completed_data_split": True},
                "account_state_snapshot": "malformed snapshot is ignored",
                "done": True,
            },
        ]
    )

    metrics = run_episode(env, lambda _observation: 0, periods_per_year=2)

    assert env.actions == [0, 0]
    assert metrics.total_pnl == pytest.approx(0.0)
    assert metrics.periods_per_year == 2
    assert metrics.extras["entry_opened"] == 1.0
    assert metrics.extras["entry_attempts"] == 2.0
    assert metrics.extras["entry_rejection_rate"] == 0.5
    assert metrics.extras["entry_rejected_daily_loss"] == 1.0
    assert metrics.extras["entry_rejected_daily_loss_rate"] == 0.5
    assert metrics.extras["entry_state_transitions"] == 2.0


def test_run_episode_uses_equity_without_optional_environment_metadata() -> None:
    class MinimalEpisode:
        initial_balance = 100.0

        def reset(self) -> tuple[None, dict[str, Any]]:
            return None, {}

        def step(self, _action: Any) -> tuple[None, float, bool, bool, dict[str, Any]]:
            return None, 0.0, False, False, {"equity": 101.0}

    metrics = run_episode(MinimalEpisode(), lambda _observation: 0, max_steps=1)

    assert metrics.total_pnl == pytest.approx(1.0)
    assert metrics.breach_count == 0


def test_run_episode_rejects_empty_or_equity_free_rollouts() -> None:
    env = _ScriptedEpisode([{"done": True}])

    with pytest.raises(ValueError, match="equity curve is empty"):
        run_episode(env, lambda _observation: 0)

    with pytest.raises(ValueError, match="equity curve is empty"):
        run_episode(_ScriptedEpisode([]), lambda _observation: 0, max_steps=0)
