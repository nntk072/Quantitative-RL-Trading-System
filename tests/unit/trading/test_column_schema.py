from __future__ import annotations

import pandas as pd

from trading.column_schema import suffix_columns


def test_suffix_columns_caches_matches_by_schema_and_suffixes() -> None:
    columns = pd.Index(
        [
            "sweep_low_level",
            "M15_sweep_low_level",
            "M15_sweep_low_level_extra",
            "ifvg_bull_low",
            "M5_ifvg_bull_low",
        ]
    )

    first = suffix_columns(columns, ("sweep_low_level", "ifvg_bull_low"))

    assert first == (
        "sweep_low_level",
        "M15_sweep_low_level",
        "ifvg_bull_low",
        "M5_ifvg_bull_low",
    )
    assert suffix_columns(columns, ("sweep_low_level", "ifvg_bull_low")) is first
    assert suffix_columns(columns, ("sweep_low_level",)) == (
        "sweep_low_level",
        "M15_sweep_low_level",
    )


def test_suffix_columns_does_not_reuse_matches_for_a_different_schema_object() -> None:
    columns = pd.Index(["M5_fvg_bear_low", "M15_fvg_bear_low"])
    other_columns = pd.Index(["M5_fvg_bear_low", "M15_fvg_bear_low"])

    first = suffix_columns(columns, ("fvg_bear_low",))
    second = suffix_columns(other_columns, ("fvg_bear_low",))

    assert first == second == ("M5_fvg_bear_low", "M15_fvg_bear_low")
    assert second is not first
