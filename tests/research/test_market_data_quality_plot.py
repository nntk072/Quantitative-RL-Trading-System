"""Tests for monthly tick quality summary calculations."""

from __future__ import annotations

from typing import Any

import pytest
from scripts.research.analysis.market_data.plot_market_data_quality_profile import (
    monthly_tick_quote_rows,
)


def _profile() -> dict[str, Any]:
    return {
        "schema": "qrl.market_data_quality_profile.v2",
        "inputs": [
            {
                "kind": "tick",
                "source_role": "training",
                "instrument": "US100.cash",
                "quality_counts_by_period": {
                    "month": {
                        "2025-01": {
                            "rows": 10,
                            "missing_or_nonfinite_bid_rows": 3,
                            "missing_or_nonfinite_ask_rows": 4,
                            "missing_or_nonfinite_bid_and_ask_rows": 1,
                        }
                    }
                },
            },
            {
                "kind": "bar",
                "source_role": "training",
                "instrument": "US100.cash",
                "quality_counts_by_period": {"month": {"2025-01": {"rows": 10}}},
            },
        ],
    }


def test_monthly_tick_quote_rows_uses_union_denominator_and_profile_identity() -> None:
    rows = monthly_tick_quote_rows(_profile(), "profile-hash")

    assert len(rows) == 1
    assert rows[0]["rows_with_any_missing_required_side"] == 6
    assert rows[0]["tick_rows"] == 10
    assert rows[0]["missing_required_side_fraction"] == pytest.approx(0.6)
    assert rows[0]["profile_sha256"] == "profile-hash"


def test_monthly_tick_quote_rows_rejects_inconsistent_counters() -> None:
    profile = _profile()
    profile["inputs"][0]["quality_counts_by_period"]["month"]["2025-01"][
        "missing_or_nonfinite_bid_and_ask_rows"
    ] = 5

    with pytest.raises(ValueError, match="invalid quote-side counts"):
        monthly_tick_quote_rows(profile, "profile-hash")
