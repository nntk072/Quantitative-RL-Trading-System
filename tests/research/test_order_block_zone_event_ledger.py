from __future__ import annotations

import pandas as pd
from scripts.research.analysis.features.order_block_zone_event_ledger import (
    _collision_table,
    _monthly_summary,
    _retest_event_counts,
    _validate_scalar_projection,
)


def test_collision_summary_counts_suppressed_per_zone_events() -> None:
    times = pd.date_range("2025-02-01", periods=4, freq="1min", tz="UTC")
    bars = pd.DataFrame(index=times)
    ledger = pd.DataFrame(
        [
            {
                "timeframe": "M1",
                "confirmation_month": "2025-02",
                "zone_id": 1,
                "side": "bull",
                "confirmation_bar": 2,
                "confirmation_time_ns": times[2].value,
                "source_origin_bar": 0,
                "source_origin_time_ns": times[0].value,
                "zone_low": 99.0,
                "zone_high": 101.0,
                "selected_by_scalar": False,
            },
            {
                "timeframe": "M1",
                "confirmation_month": "2025-02",
                "zone_id": 2,
                "side": "bull",
                "confirmation_bar": 2,
                "confirmation_time_ns": times[2].value,
                "source_origin_bar": 1,
                "source_origin_time_ns": times[1].value,
                "zone_low": 100.0,
                "zone_high": 102.0,
                "selected_by_scalar": True,
            },
            {
                "timeframe": "M1",
                "confirmation_month": "2025-02",
                "zone_id": 3,
                "side": "bull",
                "confirmation_bar": 3,
                "confirmation_time_ns": times[3].value,
                "source_origin_bar": 0,
                "source_origin_time_ns": times[0].value,
                "zone_low": 99.0,
                "zone_high": 101.0,
                "selected_by_scalar": False,
            },
            {
                "timeframe": "M1",
                "confirmation_month": "2025-02",
                "zone_id": 4,
                "side": "bull",
                "confirmation_bar": 3,
                "confirmation_time_ns": times[3].value,
                "source_origin_bar": 1,
                "source_origin_time_ns": times[1].value,
                "zone_low": 100.0,
                "zone_high": 102.0,
                "selected_by_scalar": False,
            },
        ]
    )

    collisions = _collision_table(ledger, {"M1": bars})
    monthly = _monthly_summary(ledger, collisions)

    assert len(collisions) == 2
    assert collisions.loc[0, "per_zone_confirmation_count"] == 2
    assert collisions.loc[0, "suppressed_per_zone_confirmations"] == 1
    assert collisions.loc[0, "selected_zone_id"] == 2
    assert collisions.loc[1, "suppressed_per_zone_confirmations"] == 2
    assert pd.isna(collisions.loc[1, "selected_zone_id"])
    assert monthly.loc[0, "per_zone_confirmations"] == 4
    assert monthly.loc[0, "scalar_confirmation_pulses"] == 1
    assert monthly.loc[0, "suppressed_per_zone_confirmations"] == 3
    assert monthly.loc[0, "collision_rows"] == 2


def test_event_counts_separate_unselected_events_from_collision_suppression() -> None:
    ledger = pd.DataFrame(
        {
            "selected_by_scalar": [True, False, False, False],
        }
    )
    collisions = pd.DataFrame(
        {
            "suppressed_per_zone_confirmations": [1, 2],
        }
    )

    counts = _retest_event_counts(ledger, {"M1": 1}, collisions)

    assert counts == {
        "per_zone_retest_event_count": 4,
        "scalar_retest_pulse_count": 1,
        "not_selected_by_scalar_retest_event_count": 3,
        "collision_suppressed_per_zone_event_count": 3,
        "collision_group_count": 2,
    }


def test_selected_zone_ledger_reconciles_scalar_retest_and_origin() -> None:
    times = pd.date_range("2025-02-01", periods=4, freq="1min", tz="UTC")
    scalar = pd.DataFrame(
        {
            "ob_bull_retest": [0.0, 0.0, 1.0, 0.0],
            "ob_bull_origin_time_ms": [
                float("nan"),
                float("nan"),
                times[0].value / 1e6,
                float("nan"),
            ],
            "ob_bear_retest": [0.0, 0.0, 0.0, 0.0],
            "ob_bear_origin_time_ms": [float("nan")] * 4,
        },
        index=times,
    )
    ledger = pd.DataFrame(
        [
            {
                "side": "bull",
                "selected_by_scalar": True,
                "confirmation_bar": 2,
                "source_origin_time_ns": times[0].value,
            }
        ]
    )

    _validate_scalar_projection(ledger, scalar)
