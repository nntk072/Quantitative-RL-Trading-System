"""Tests for the PPO/SAC transition record contract."""

from __future__ import annotations

import numpy as np
import pytest

from learning.rl.transition_contract import TransitionRecord


def _record(**overrides: object) -> TransitionRecord:
    values: dict[str, object] = {
        "policy_version_id": "policy:ppo-contract-fixture-v1",
        "executed_action": np.array([0.25, -0.5, 0.0], dtype=np.float32),
        "log_prob": -1.5,
        "old_value": 0.2,
        "setup_mask": np.array([True, False, True]),
        "setup_class": 2,
        "terminated": False,
        "truncated": False,
        "terminal_observation": None,
        "recurrent_state": None,
    }
    values.update(overrides)
    return TransitionRecord(**values)  # type: ignore[arg-type]


def test_valid_open_transition_is_accepted() -> None:
    record = _record()
    assert record.setup_class == 2


def test_valid_terminal_and_truncated_transitions_require_the_terminal_observation() -> None:
    terminal_obs = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    _record(terminated=True, terminal_observation=terminal_obs)
    _record(truncated=True, terminal_observation=terminal_obs)
    with pytest.raises(ValueError, match="terminal observation"):
        _record(terminated=True)
    with pytest.raises(ValueError, match="terminal observation"):
        _record(truncated=True)
    with pytest.raises(ValueError, match="only allowed on ended"):
        _record(terminal_observation=terminal_obs)


def test_terminated_and_truncated_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="both terminated and truncated"):
        _record(
            terminated=True,
            truncated=True,
            terminal_observation=np.zeros(3, dtype=np.float32),
        )


def test_executed_setup_must_be_eligible_under_its_mask() -> None:
    with pytest.raises(ValueError, match="not eligible"):
        _record(setup_class=1)


def test_mask_polarity_and_presence_are_enforced() -> None:
    with pytest.raises(ValueError, match="boolean"):
        _record(setup_mask=np.array([1.0, 0.0, 1.0]))
    with pytest.raises(ValueError, match="at least one category"):
        _record(setup_mask=np.array([False, False, False]), setup_class=0)
    with pytest.raises(ValueError, match="provided together"):
        _record(setup_class=None)
    with pytest.raises(ValueError, match="outside the setup mask"):
        _record(setup_class=7)


def test_masked_or_impossible_log_probability_is_rejected() -> None:
    # A masked category surfaces as a huge negative finite log-prob, so reject
    # sentinels by requiring the stored value to be finite and the class eligible.
    with pytest.raises(ValueError, match="finite"):
        _record(log_prob=float("-inf"))
    with pytest.raises(ValueError, match="finite"):
        _record(log_prob=float("nan"))


def test_action_and_value_must_be_finite_and_policy_version_present() -> None:
    with pytest.raises(ValueError, match="finite"):
        _record(executed_action=np.array([np.nan, 0.0, 0.0], dtype=np.float32))
    with pytest.raises(ValueError, match="1-D"):
        _record(executed_action=np.zeros((2, 3), dtype=np.float32))
    with pytest.raises(ValueError, match="old_value"):
        _record(old_value=float("inf"))
    with pytest.raises(ValueError, match="policy_version_id"):
        _record(policy_version_id="  ")
