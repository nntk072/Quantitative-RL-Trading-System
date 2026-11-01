from __future__ import annotations

from pathlib import Path

from scripts.research.audits.audit_current_p6_market_inputs import scan_csv


def test_bar_audit_counts_invalid_ohlc_and_timestamp_order(tmp_path: Path) -> None:
    path = tmp_path / "US100.cash_M1_fixture.csv"
    path.write_text(
        "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
        "2025.01.02\t10:01:00\t10\t12\t9\t11\t1\t0\t1\n"
        "2025.01.02\t10:00:00\t10\t9\t11\t10\t1\t0\t1\n",
        encoding="utf-8",
    )

    result = scan_csv(path, chunksize=1)

    assert result["kind"] == "bar"
    assert result["row_count"] == 2
    assert result["out_of_order_adjacent_timestamps"] == 1
    assert result["invalid_ohlc_rows"] == 1
    assert len(result["_bar_minutes"]) == 2


def test_tick_audit_classifies_missing_quotes_and_timestamp_ties(tmp_path: Path) -> None:
    path = tmp_path / "US100.cash_ticks_fixture.csv"
    path.write_text(
        "<DATE>\t<TIME>\t<BID>\t<ASK>\t<LAST>\t<VOLUME>\t<FLAGS>\n"
        "2025.01.02\t10:00:00.001\t10\t11\t\t\t0\n"
        "2025.01.02\t10:00:00.001\t10\t11\t\t\t0\n"
        "2025.01.02\t10:00:00.001\t13\t12\t\t\t0\n"
        "2025.01.02\t10:00:00.002\t\t13\t\t\t0\n"
        "2025.01.02\t10:00:00.002\t14\t\t\t\t0\n",
        encoding="utf-8",
    )

    result = scan_csv(path, chunksize=2)

    assert result["kind"] == "tick"
    assert result["row_count"] == 5
    assert result["duplicate_adjacent_timestamps"] == 3
    assert result["rows_with_nonfinite_or_missing_numeric"] == 2
    assert result["missing_optional_last_rows"] == 5
    assert result["missing_optional_volume_rows"] == 5
    assert result["missing_or_nonfinite_bid_rows"] == 1
    assert result["missing_or_nonfinite_ask_rows"] == 1
    assert result["missing_or_nonfinite_bid_and_ask_rows"] == 0
    assert result["same_timestamp_identical_bid_ask_pairs"] == 1
    assert result["same_timestamp_changed_bid_ask_pairs"] == 1
    assert result["same_timestamp_pairs_with_missing_quote"] == 1
    assert result["inverted_quote_rows"] == 1
    assert result["observed_unique_quote_minutes"] == 1
