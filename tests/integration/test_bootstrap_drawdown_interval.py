from __future__ import annotations

import numpy as np
import pytest

from evaluation.metrics.bootstrap import metrics_with_ci


def test_bootstrap_drawdown_does_not_invent_loss_on_rising_equity() -> None:
    equity = np.linspace(100, 130, 30)
    ci = metrics_with_ci(np.asarray(equity, dtype=np.float64), np.array([1.0]), n_boot=80)[
        "max_drawdown"
    ]
    assert ci.estimate == pytest.approx(0.0)
    assert ci.upper == pytest.approx(0.0)
