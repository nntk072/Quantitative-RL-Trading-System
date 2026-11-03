from __future__ import annotations

import pandas as pd
from scripts.research.analysis.features.standard_deviation_swing_ledger import (
    _swing_leg_ledger,
)


def test_swing_ledger_separates_leg_keys_from_availability_and_eligibility_episodes() -> None:
    index = pd.date_range("2025-01-01", periods=6, freq="min", tz="UTC")
    features = pd.DataFrame(
        {
            "standard_deviation_leg_valid": [1, 1, 0, 1, 1, 1],
            "standard_deviation_leg_direction": [1, 1, 0, 1, 1, 1],
            "standard_deviation_leg_start_time_ns": [100, 100, float("nan"), 100, 100, 100],
            "standard_deviation_leg_end_time_ns": [200, 200, float("nan"), 200, 200, 200],
            "entry_idea_standard_deviation_M1_long": [1, 1, 0, 0, 1, 1],
            "entry_idea_standard_deviation_M1_short": [0, 0, 0, 0, 0, 0],
            "M5_standard_deviation_leg_valid": [1, 1, 0, 0, 0, 0],
            "M5_standard_deviation_leg_direction": [1, 1, 0, 0, 0, 0],
            "M5_standard_deviation_leg_start_time_ns": [
                100,
                100,
                float("nan"),
                float("nan"),
                float("nan"),
                float("nan"),
            ],
            "M5_standard_deviation_leg_end_time_ns": [
                200,
                200,
                float("nan"),
                float("nan"),
                float("nan"),
                float("nan"),
            ],
            "entry_idea_standard_deviation_M5_long": [0, 1, 0, 0, 0, 0],
            "entry_idea_standard_deviation_M5_short": [0, 0, 0, 0, 0, 0],
        },
        index=index,
    )

    legs, groups, summary = _swing_leg_ledger(features, ["M1", "M5"])

    m1 = legs.loc[legs["timeframe"].eq("M1")].iloc[0]
    assert m1["available_rows"] == 5
    assert m1["availability_episodes"] == 2
    assert m1["eligible_rows"] == 4
    assert m1["eligibility_episodes"] == 2
    assert len(legs) == 2
    assert len(groups) == 1
    assert groups.iloc[0]["timeframe_count"] == 2
    assert summary["totals"] == {
        "source_leg_projection_rows": 2,
        "eligible_source_legs": 2,
        "source_legs_without_retracement": 0,
        "source_tuple_groups_across_timeframes": 1,
        "tuple_groups_on_multiple_timeframes": 1,
    }
