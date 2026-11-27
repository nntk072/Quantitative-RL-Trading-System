from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest

from simulation.environment.diagnostics.errors import (
    DebugStepError,
    jsonable,
    new_debug_window,
    note_debug_step,
    summarize_window,
    wiring_from_env,
)
from simulation.environment.diagnostics.runtime import DiagnosticsRuntimeMixin
from simulation.environment.entry_diagnostics import _empty_entry_diag
from simulation.environment.rewards import DSRReward, PnLReward


def _note(
    window: dict[str, Any],
    *,
    reward: float,
    reward_parts: dict[str, float],
    opened: bool = False,
    entered: bool = False,
    risk_frac: float = 0.0,
    close_reason: str = "",
) -> None:
    note_debug_step(
        window,
        reward=reward,
        reward_parts=reward_parts,
        opened=opened,
        entered=entered,
        risk_frac=risk_frac,
        close_reason=close_reason,
        action=np.asarray([1, 0.25]),
        position=opened,
        position_direction=1 if opened else 0,
    )


def test_window_summary_tracks_reward_parts_and_step_events() -> None:
    window = new_debug_window()
    _note(
        window,
        reward=1.0,
        reward_parts={"strategy": 0.5, "soft_daily": -0.1},
        opened=True,
        entered=True,
        risk_frac=0.02,
        close_reason="structure_sl",
    )
    _note(
        window,
        reward=0.0,
        reward_parts={"strategy": 0.2, "soft_daily": -0.1, "soft_year": -0.2},
        entered=True,
        risk_frac=0.03,
        close_reason="structure_tp",
    )
    _note(
        window,
        reward=-1.0,
        reward_parts={"breach": -1.0, "soft_year": -0.1},
        close_reason="other",
    )

    summary = summarize_window(window)

    assert summary["n"] == 3
    assert summary["parts"] == {
        "strategy": 0.7,
        "soft_daily": -0.2,
        "soft_year": -0.30000000000000004,
        "breach": -1.0,
    }
    assert summary["opens"] == 1
    assert summary["shape_on_open"] == 1
    assert summary["shape_on_hold"] == 1
    assert summary["breach_events"] == 1
    assert summary["entries"] == 2
    assert summary["risk_sum"] == pytest.approx(0.05)
    assert summary["soft_daily_nz"] == 2
    assert summary["soft_daily_repeat"] == 1
    assert summary["soft_year_nz"] == 2
    assert summary["soft_year_repeat"] == 1
    assert summary["closes"] == 3
    assert summary["structure_sl"] == 1
    assert summary["structure_tp"] == 1
    assert summary["nonzero"] == pytest.approx(2 / 3)
    assert 0.0 <= summary["spike_share"] <= 1.0


@pytest.mark.parametrize("reward", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_reward_raises_snapshot_without_mutating_window(reward: float) -> None:
    window = new_debug_window()
    snapshot_action = {np.int64(2): (np.float32(0.5), np.float64(np.inf))}

    with pytest.raises(DebugStepError, match="non-finite reward") as caught:
        note_debug_step(
            window,
            reward=reward,
            reward_parts={"pnl": 3.0},
            opened=True,
            entered=True,
            risk_frac=0.02,
            close_reason="structure_sl",
            action=snapshot_action,
            position=True,
            position_direction=1,
        )

    assert caught.value.snapshot == {
        "action": {"2": [0.5, None]},
        "reward": None,
        "reward_parts": {"pnl": 3.0},
        "position": True,
        "position_direction": 1,
    }
    assert summarize_window(window) == summarize_window(new_debug_window())


def test_jsonable_converts_nested_numpy_values_and_non_finite_numbers() -> None:
    result = jsonable(
        {
            np.int64(4): (np.asarray([1, np.nan]), [np.float32(np.inf), float("-inf")]),
            "integer": np.int32(7),
        }
    )

    assert result == {"4": [[1.0, None], [None, None]], "integer": 7}


def test_wiring_from_env_uses_pnl_reward_and_composite_base_settings() -> None:
    pnl_reward = PnLReward(dsr_weight=0.4, breach_penalty=-3.0)
    pnl_env = SimpleNamespace(
        reward_fn=pnl_reward,
        reward_mode="pnl",
        episodic=True,
        risk_floor=0.01,
        risk_frac_range=(0.01, 0.05),
    )
    pnl_wiring = wiring_from_env(pnl_env)
    assert pnl_wiring == {
        "reward_mode": "pnl",
        "episodic": True,
        "breach_penalty": -3.0,
        "eval_breach_penalty": -10.0,
        "composite_dsr_weight": 0.4,
        "pnl_dsr_weight": 0.4,
        "strategy_weight": 0.0,
        "risk_floor": 0.01,
        "risk_frac_range": [0.01, 0.05],
    }

    base_reward = DSRReward(breach_penalty=-2.0)
    composite_env = SimpleNamespace(
        reward_fn=SimpleNamespace(_dsr_fn=base_reward, dsr_weight=0.6, strategy_weight=0.2)
    )
    composite_wiring = wiring_from_env(composite_env)
    assert composite_wiring["breach_penalty"] == -2.0
    assert composite_wiring["composite_dsr_weight"] == 0.6
    assert composite_wiring["pnl_dsr_weight"] == 0.0
    assert composite_wiring["strategy_weight"] == 0.2
    assert composite_wiring["risk_frac_range"] == []


def test_environment_debug_runtime_flushes_and_resets_window() -> None:
    env = SimpleNamespace(
        reward_fn=PnLReward(breach_penalty=-4.0),
        reward_mode="pnl",
        episodic=False,
        risk_floor=0.02,
        risk_frac_range=(0.02, 0.04),
    )
    runtime_env = cast(Any, env)
    DiagnosticsRuntimeMixin.enable_debug_trace(runtime_env)
    _note(env._debug_window, reward=2.0, reward_parts={"pnl": 2.0})

    wiring = DiagnosticsRuntimeMixin.debug_wiring(runtime_env)
    summary = DiagnosticsRuntimeMixin.debug_flush(runtime_env)

    assert wiring["breach_penalty"] == -4.0
    assert wiring["risk_frac_range"] == [0.02, 0.04]
    assert summary["n"] == 1
    assert summary["parts"] == {"pnl": 2.0}
    assert DiagnosticsRuntimeMixin.debug_flush(runtime_env)["n"] == 0

    disabled = cast(Any, SimpleNamespace(_debug_trace=False, _debug_window=None))
    assert DiagnosticsRuntimeMixin.debug_flush(disabled) == {}


def test_unconfirmed_manipulation_rejects_policy_side_override_and_records_reason() -> None:
    env = cast(Any, object.__new__(DiagnosticsRuntimeMixin))
    env.strategy_actions = True
    env.strategy = SimpleNamespace(context_direction=lambda _row: 0)
    env.entry_state_machine = None
    env._entry_diag = _empty_entry_diag()
    env._trigger_requested_this_step = False
    env._current_decision_id = "decision-7"
    env._entry_rejection_reason = None
    env._entry_rejection_decision_id = None

    action, risk_frac = DiagnosticsRuntimeMixin._lock_unconfirmed_side(
        env, 1, pd.Series({"po3_manipulation_active": 1.0}), 0.02
    )

    assert (action, risk_frac) == (0, 0.0)
    assert env._entry_diag["rejected_manipulation"] == 1
    assert env._entry_rejection_reason == "manipulation_unconfirmed"
    assert env._entry_rejection_decision_id == "decision-7"
