from pathlib import Path

import numpy as np
from scripts.research.audits.verify_survival_learning_signal_reachability import (
    build_report,
    terminal_gae,
)


def test_terminal_survival_reward_reaches_every_step() -> None:
    success = terminal_gae(np.array([0.0, 0.0, 1.0]))
    breach = terminal_gae(np.array([0.0, 0.0, -1.0]))
    assert success.tolist() == [1.0, 1.0, 1.0]
    assert breach.tolist() == [-1.0, -1.0, -1.0]


def test_current_conditioned_survival_config_has_nonzero_synthetic_ppo_gradient() -> None:
    root = Path(__file__).resolve().parents[3]
    report = build_report(
        root / "config/research/survival_trade_setup_mtf_conditioned.yaml",
        path_length=4,
    )
    assert report["status"] == "pass"
    assert report["success_policy_gradient_magnitude"] > 0.0
    assert report["breach_policy_gradient_magnitude"] > 0.0
