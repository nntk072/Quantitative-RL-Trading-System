"""Tests for the account-vector normalization in TradingEnv.

The ``seq`` features are z-scored at build time so they sit at ~O(1).
The legacy ``account`` vector embedded raw equity (~1e5) and open PnL,
which dominated the policy's MLP heads and made the time-series signal
effectively invisible. ``normalize_account=True`` (default) rescales the
account vector to the same order of magnitude.
"""

from __future__ import annotations

import numpy as np

from simulation.environment.env import TradingEnv
from tests.unit.simulation.test_environment._account_fixtures import _make_bars, _make_features


def test_normalized_account_has_unit_magnitude() -> None:
    """When normalize_account=True, all account dims should be O(1)."""
    bars = _make_bars()
    features = _make_features(bars)
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        initial_balance=100_000.0,
        normalize_account=True,
    )
    obs, _ = env.reset(seed=0)
    acc = obs["account"]
    assert np.all(np.abs(acc) < 10.0), (
        f"Normalized account should be O(1), got max abs = {np.abs(acc).max()}"
    )
    # At reset, equity == initial_balance → norm_equity == log(1) == 0.
    assert acc[0] == 0.0


def test_unnormalized_account_carries_raw_equity() -> None:
    """When normalize_account=False, equity is the raw USD value."""
    bars = _make_bars()
    features = _make_features(bars)
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        initial_balance=100_000.0,
        normalize_account=False,
    )
    obs, _ = env.reset(seed=0)
    acc = obs["account"]
    # Raw equity is 1e5, which would dominate the z-scored seq features.
    assert acc[0] == 100_000.0
    # The vector must still carry raw values (no silent normalization).
    assert acc.shape == (6,)


def test_normalization_default_is_on() -> None:
    """Default behavior must include normalization — it's a strict upgrade
    and the prior off-by-default would silently degrade the policy.
    """
    bars = _make_bars()
    features = _make_features(bars)
    env = TradingEnv(bars=bars, features=features, obs_window=10, initial_balance=100_000.0)
    obs, _ = env.reset(seed=0)
    # The default normalized equity is log(1)=0, not 1e5.
    assert obs["account"][0] == 0.0
