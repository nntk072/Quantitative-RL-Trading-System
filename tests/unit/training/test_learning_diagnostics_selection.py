from __future__ import annotations

import pytest

from training.runner.seed_runtime import _learning_diagnostics_enabled


@pytest.mark.parametrize(
    ("algo", "quality", "trade_setup", "expected"),
    [
        ("ppo", True, False, True),
        ("ppo", False, True, True),
        ("ppo", False, False, False),
        ("sac", True, False, False),
        ("sac", False, True, False),
    ],
)
def test_learning_diagnostics_attach_only_to_supported_ppo_rollouts(
    algo: str, quality: bool, trade_setup: bool, expected: bool
) -> None:
    assert _learning_diagnostics_enabled(algo, quality, trade_setup) is expected
