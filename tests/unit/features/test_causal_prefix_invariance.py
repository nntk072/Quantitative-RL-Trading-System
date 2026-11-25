"""Causal prefix invariance of bar features on the tracked US100 M1 example (CAUSAL-FEATURE-GRAPH).

A feature that uses only past and current bars must produce, on a prefix of the bars, exactly the
values it produces on the full series at the same timestamps. Any dependence on later bars (a
centred window, a backward fill, a full-sample statistic) breaks this equality.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from features.technical.indicators import atr, realized_vol
from market_data.arrow_schemas import mt5_export_to_bars

REPO = Path(__file__).resolve().parents[3]
EXAMPLE = REPO / "data" / "examples" / "US100.cash_M1_202412300105_202501020334.csv"
PREFIX_LENGTHS = (1, 2, 15, 16, 100, 1440, 2000)


@pytest.fixture(scope="module")
def bars() -> pd.DataFrame:
    frame = pd.read_csv(EXAMPLE, sep="\t", dtype=str).rename(columns=lambda n: n.strip("<>"))
    table, problems = mt5_export_to_bars(frame, instrument_id="US100.cash", timeframe="M1")
    assert problems == []
    df: pd.DataFrame = table.select(["event_time", "open", "high", "low", "close"]).to_pandas()
    df.index = pd.DatetimeIndex(df.pop("event_time"))
    return df


@pytest.mark.parametrize("prefix", PREFIX_LENGTHS)
def test_atr_on_prefix_matches_full_series_exactly(bars: pd.DataFrame, prefix: int) -> None:
    full = atr(bars, period=14)
    part = atr(bars.iloc[:prefix], period=14)
    pd.testing.assert_series_equal(part, full.iloc[:prefix], check_exact=True)
    assert part.notna().all()


@pytest.mark.parametrize("prefix", PREFIX_LENGTHS)
def test_realized_vol_on_prefix_matches_full_series_exactly(
    bars: pd.DataFrame, prefix: int
) -> None:
    full = realized_vol(bars["close"], period=20)
    part = realized_vol(bars["close"].iloc[:prefix], period=20)
    pd.testing.assert_series_equal(part, full.iloc[:prefix], check_exact=True)
