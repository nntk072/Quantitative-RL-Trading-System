from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from market_data.loading.bars import load_bars
from market_data.transforms.cleaning import clean


def test_load_bars_accepts_date_only_daily_export(tmp_path: Path) -> None:
    path = tmp_path / "daily.tsv"
    path.write_text(
        "<DATE>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
        "2025.01.02\t10\t12\t9\t11\t100\t0\t2\n",
        encoding="utf-8",
    )

    bars = load_bars(path)

    assert bars.index.tolist() == [pd.Timestamp("2025-01-02 00:00:00")]
    assert bars.iloc[0]["close"] == 11
    assert bars.iloc[0]["spread"] == 2


def test_load_bars_keeps_intraday_time_from_export(tmp_path: Path) -> None:
    path = tmp_path / "minute.tsv"
    path.write_text(
        "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
        "2025.01.02\t09:31:00\t10\t12\t9\t11\t100\t0\t2\n",
        encoding="utf-8",
    )

    bars = load_bars(path)

    assert bars.index.tolist() == [pd.Timestamp("2025-01-02 09:31:00")]


@pytest.mark.parametrize(
    "ohlc",
    [
        ("nan", "12", "9", "11"),
        ("10", "inf", "9", "11"),
        ("10", "12", "9", "-inf"),
        ("10", "8", "9", "11"),
        ("10", "12", "11", "9"),
    ],
)
def test_load_bars_rejects_nonfinite_or_impossible_ohlc(
    tmp_path: Path, ohlc: tuple[str, str, str, str]
) -> None:
    path = tmp_path / "invalid.tsv"
    path.write_text(
        "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
        f"2025.01.02\t09:31:00\t{ohlc[0]}\t{ohlc[1]}\t{ohlc[2]}\t{ohlc[3]}\t100\t0\t2\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid OHLC"):
        load_bars(path)


@pytest.mark.parametrize("spread", ["inf", "-inf", "nan", "-1"])
def test_load_bars_rejects_invalid_spread(tmp_path: Path, spread: str) -> None:
    path = tmp_path / "invalid_spread.tsv"
    path.write_text(
        "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
        f"2025.01.02\t09:31:00\t10\t12\t9\t11\t100\t0\t{spread}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid spread"):
        load_bars(path)


def test_load_bars_rejects_missing_timestamp_in_source(tmp_path: Path) -> None:
    path = tmp_path / "missing_time.tsv"
    path.write_text(
        "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
        "2025.01.01\t09:31:00\t10\t12\t9\t11\t100\t0\t2\n"
        "2025.01.02\t\t10\t12\t9\t11\t100\t0\t2\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid bar timestamps"):
        load_bars(path, end_exclusive=pd.Timestamp("2025-01-02"))


def test_load_bars_records_raw_order_and_conflicting_duplicate_diagnostics(
    tmp_path: Path,
) -> None:
    path = tmp_path / "unordered.tsv"
    path.write_text(
        "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
        "2025.01.02\t09:32:00\t10\t12\t9\t11\t100\t0\t2\n"
        "2025.01.02\t09:31:00\t10\t12\t9\t11\t100\t0\t2\n"
        "2025.01.02\t09:31:00\t10\t13\t9\t11\t100\t0\t2\n",
        encoding="utf-8",
    )

    bars = load_bars(path)

    assert bars.index.is_monotonic_increasing
    assert bars.attrs["source_diagnostics"] == {
        "out_of_order_rows": 1,
        "duplicate_rows": 1,
        "conflicting_duplicate_timestamps": 1,
    }
    assert clean(bars).attrs["source_diagnostics"] == bars.attrs["source_diagnostics"]


def test_load_bars_validates_only_rows_in_requested_window(tmp_path: Path) -> None:
    path = tmp_path / "bounded.tsv"
    path.write_text(
        "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
        "2025.01.01\t09:31:00\t10\t8\t9\t11\t100\t0\t2\n"
        "2025.01.02\t09:31:00\t10\t12\t9\t11\t100\t0\t2\n",
        encoding="utf-8",
    )

    bars = load_bars(
        path,
        start_inclusive=pd.Timestamp("2025-01-02"),
        end_exclusive=pd.Timestamp("2025-01-03"),
    )

    assert bars.index.tolist() == [pd.Timestamp("2025-01-02 09:31:00")]
