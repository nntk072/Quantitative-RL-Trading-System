"""Input validation contracts for raw MT5 bar files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from market_data.loading.bars import load_bars


def test_bar_loader_accepts_normalized_header_and_keeps_valid_rows(tmp_path: Path) -> None:
    source = tmp_path / "normalized-header.tsv"
    source.write_text(
        "date\ttime\topen\thigh\tlow\tclose\ttickvol\tvol\tspread\n"
        "2025.01.01\t09:30:00\t100\t102\t99\t101\t10\t0\t0\n",
        encoding="utf-8-sig",
    )

    bars = load_bars(source)

    assert bars.index.tolist() == [pd.Timestamp("2025-01-01 09:30:00")]
    assert bars.loc[bars.index[0], "open"] == 100.0
    assert bars.loc[bars.index[0], "high"] == 102.0
    assert bars.loc[bars.index[0], "low"] == 99.0
    assert bars.loc[bars.index[0], "close"] == 101.0
    assert bars.attrs["source_diagnostics"] == {
        "out_of_order_rows": 0,
        "duplicate_rows": 0,
        "conflicting_duplicate_timestamps": 0,
    }


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("2025.01.01\t09:30:00\t100\t102\t99\t101\t10\t0\tnan", "invalid spread values"),
        ("2025.01.01\t09:30:00\t100\t102\t99\tinf\t10\t0\t0", "invalid OHLC rows"),
    ],
)
def test_bar_loader_rejects_nonfinite_spread_or_prices(
    tmp_path: Path, row: str, message: str
) -> None:
    source = tmp_path / "nonfinite.tsv"
    source.write_text(
        f"<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n{row}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        load_bars(source)
