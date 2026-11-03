from __future__ import annotations

import pandas as pd
from scripts.research.analysis.features.ifvg_zone_event_ledger import (
    _collision_table,
    _monthly_summary,
    _validate_scalar_projection,
)

from features.po3.fvg_detection import detect_fvg
from features.po3.ifvg_detection import (
    detect_ifvg_confirmation,
    detect_ifvg_confirmation_events,
)


def _two_same_row_bullish_confirmations() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "high": [100.0, 100.5, 101.2, 103.0, 103.0, 104.5],
            "low": [99.0, 99.5, 101.0, 100.8, 99.0, 103.5],
            "close": [99.5, 100.0, 101.1, 100.9, 99.5, 104.0],
        },
        index=pd.date_range("2025-01-31 23:57", periods=6, freq="min", tz="UTC"),
    )


def test_zone_ledger_reconciles_scalar_selection_and_monthly_suppression() -> None:
    bars = _two_same_row_bullish_confirmations()
    fvg = detect_fvg(bars)
    scalar = detect_ifvg_confirmation(bars, fvg)
    ledger = detect_ifvg_confirmation_events(bars, fvg)

    _validate_scalar_projection(ledger, scalar)
    collisions = _collision_table(ledger, bars)
    monthly = _monthly_summary(ledger, bars)

    assert len(ledger) == 2
    assert len(collisions) == 1
    assert collisions.loc[0, "confirmation_month"] == "2025-02"
    assert collisions.loc[0, "per_zone_confirmation_count"] == 2
    assert collisions.loc[0, "suppressed_per_zone_confirmations"] == 1
    assert collisions.loc[0, "selected_source_origin_bar"] == 3
    assert monthly["per_zone_confirmations"].sum() == 2
    assert monthly["scalar_confirmation_pulses"].sum() == 1
    assert monthly["suppressed_per_zone_confirmations"].sum() == 1
    assert monthly.loc[monthly["confirmation_month"].eq("2025-02"), "collision_rows"].sum() == 1
