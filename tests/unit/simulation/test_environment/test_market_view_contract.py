from __future__ import annotations

import numpy as np
import pytest

from simulation.environment.market_view import BarView, FeatureRow


def test_bar_view_matches_series_lookup_and_optional_spread_contract() -> None:
    bar = BarView(open=1.0, high=3.0, low=0.5, close=2.0, spread=0.25)

    assert {name: bar[name] for name in bar.index} == {
        "open": 1.0,
        "high": 3.0,
        "low": 0.5,
        "close": 2.0,
        "spread": 0.25,
    }
    assert bar.get("unknown", -1.0) == -1.0
    with pytest.raises(KeyError, match="unknown"):
        _ = bar["unknown"]
    assert "spread" not in BarView(open=1.0, high=2.0, low=0.0, close=1.0).index


def test_feature_row_supports_lookup_membership_iteration_and_defaults() -> None:
    row = FeatureRow(np.asarray([0.25, 0.75]), {"signal": 0, "strength": 1}, decision_at_ms=12)

    assert row["signal"] == pytest.approx(0.25)
    assert row.get("strength") == pytest.approx(0.75)
    assert row.get("missing", -1.0) == -1.0
    assert "signal" in row
    assert "missing" not in row
    assert list(row) == ["signal", "strength"]
    assert row.index == {"signal": 0, "strength": 1}
    assert row.decision_at_ms == 12
