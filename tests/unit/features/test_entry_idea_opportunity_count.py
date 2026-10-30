from __future__ import annotations

import pandas as pd
from scripts.research.count_entry_idea_opportunities import count_opportunities


def test_po3_opportunity_count_uses_confirmed_entry_flags(tmp_path) -> None:
    cache_path = tmp_path / "features.parquet"
    pd.DataFrame(
        {
            "datetime": pd.date_range("2025-01-01", periods=3, freq="min", tz="UTC"),
            "entry_idea_po3_long": [0.0, 1.0, 1.0],
            "entry_idea_po3_short": [0.0, 0.0, 0.0],
            "entry_idea_long_count": [0.0, 1.0, 1.0],
            "entry_idea_short_count": [0.0, 0.0, 0.0],
            # Broad PO3 state is context and must not inflate entry counts.
            "po3_manipulation_active": [1.0, 1.0, 1.0],
            "po3_manipulation_direction": [1.0, -1.0, 1.0],
            "po3_distribution": [0.0, 0.0, 0.0],
        }
    ).to_parquet(cache_path, index=False)

    annual, detail = count_opportunities(cache_path)

    po3_year = annual.loc[annual["year"] == 2025].iloc[0]
    assert po3_year["po3_unique_bars"] == 2
    assert po3_year["po3_signal_episode_starts"] == 1
    assert po3_year["cache_entry_idea_rows_with_both_directions"] == 0

    po3_detail = detail.loc[(detail["year"] == 2025) & (detail["idea"] == "PO3")]
    assert po3_detail["timeframe"].tolist() == ["Any TF"]
    assert po3_detail["active_m1_bars"].tolist() == [2]
    assert po3_detail["episode_starts"].tolist() == [1]
