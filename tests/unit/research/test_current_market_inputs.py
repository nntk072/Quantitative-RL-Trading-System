from __future__ import annotations

from pathlib import Path

from scripts.research.analysis.market_data.scan_local_market_data_quality import (
    _campaign_path_from_repository,
    _merge_period_quality,
    scan_csv,
)


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
    period = result["quality_counts_by_period"]["day"]["2025-01-02"]
    assert period["out_of_order_adjacent_timestamps"] == 1
    assert period["invalid_ohlc_rows"] == 1


def test_tick_audit_classifies_missing_quotes_and_timestamp_ties(tmp_path: Path) -> None:
    path = tmp_path / "US100.cash_ticks_fixture.csv"
    path.write_text(
        "<DATE>\t<TIME>\t<BID>\t<ASK>\t<LAST>\t<VOLUME>\t<FLAGS>\n"
        "2025.01.02\t10:00:00.001\t10\t11\t\t\t6\n"
        "2025.01.02\t10:00:00.001\t10\t11\t\t\t6\n"
        "2025.01.02\t10:00:00.001\t13\t12\t\t\t6\n"
        "2025.01.02\t10:00:00.002\t\t13\t\t\t4\n"
        "2025.01.02\t10:00:00.002\t14\t\t\t\t2\n",
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
    tick_day = result["quality_counts_by_period"]["day"]["2025-01-02"]
    assert tick_day["same_timestamp_identical_bid_ask_pairs"] == 1
    assert tick_day["same_timestamp_changed_bid_ask_pairs"] == 1
    assert tick_day["same_timestamp_pairs_with_missing_quote"] == 1
    assert result["flag_column_available"] is True
    assert result["flag_rows_accounted"] == 5
    assert result["flag_quote_side_counts"] == {
        "2": {
            "both_present": 0,
            "bid_missing_ask_present": 0,
            "ask_missing_bid_present": 1,
            "both_missing": 0,
        },
        "4": {
            "both_present": 0,
            "bid_missing_ask_present": 1,
            "ask_missing_bid_present": 0,
            "both_missing": 0,
        },
        "6": {
            "both_present": 3,
            "bid_missing_ask_present": 0,
            "ask_missing_bid_present": 0,
            "both_missing": 0,
        },
    }


def test_bar_quality_counts_cover_day_iso_week_month_and_chunk_boundaries(
    tmp_path: Path,
) -> None:
    """Period totals include malformed rows and keep source-clock boundaries stable."""
    path = tmp_path / "US100.cash_M1_period_fixture.csv"
    path.write_text(
        "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
        "2024.12.30\t23:59:00\t10\t12\t9\t11\t1\t0\t1\n"
        "2024.12.31\t00:00:00\t10\t9\t11\t10\t1\t0\t1\n"
        "2025.01.05\t00:00:00\t10\t12\t9\t11\t1\t0\t1\n"
        "2025.01.06\t00:00:00\t10\t12\t9\t\t1\t0\t1\n"
        "bad-date\t00:00:00\t10\t12\t9\t11\t1\t0\t1\n",
        encoding="utf-8",
    )

    result = scan_csv(
        path,
        chunksize=2,
        source_role="testing",
        instrument="US100.cash",
        timeframe="M1",
    )
    single_row_chunks = scan_csv(
        path,
        chunksize=1,
        source_role="testing",
        instrument="US100.cash",
        timeframe="M1",
    )
    periods = result["quality_counts_by_period"]

    assert (result["source_role"], result["instrument"], result["timeframe"]) == (
        "testing",
        "US100.cash",
        "M1",
    )
    assert result["period_key_time_basis"] == (
        "parsed source wall-clock; no timezone/session interpretation"
    )
    assert single_row_chunks["quality_counts_by_period"] == periods
    assert periods["day"]["2024-12-30"]["rows"] == 1
    assert periods["day"]["2024-12-31"]["invalid_ohlc_rows"] == 1
    assert periods["day"]["2025-01-05"]["rows"] == 1
    assert periods["day"]["2025-01-06"]["rows_with_nonfinite_or_missing_numeric"] == 1
    assert periods["day"]["unparsed_timestamp"]["timestamp_parse_failures"] == 1
    assert periods["week"]["2025-W01"]["rows"] == 3
    assert periods["week"]["2025-W02"]["rows"] == 1
    assert periods["month"]["2024-12"]["rows"] == 2
    assert periods["month"]["2025-01"]["rows"] == 2
    for granularity in ("day", "week", "month"):
        assert sum(item["rows"] for item in periods[granularity].values()) == 5
    assert periods["day"]["2025-01-05"]["gap_greater_than_60s"] == 1
    assert periods["day"]["2025-01-06"]["gap_greater_than_60s"] == 1


def test_quality_counts_merge_by_role_instrument_and_timeframe(tmp_path: Path) -> None:
    """Distinct files with matching dimensions combine into a stable source group."""
    records = []
    for suffix, date in (("a", "2025.01.02"), ("b", "2025.01.03")):
        path = tmp_path / f"US100.cash_M1_{suffix}.csv"
        path.write_text(
            f"<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\n{date}\t10:00:00\t10\t12\t9\t11\n",
            encoding="utf-8",
        )
        records.append(scan_csv(path, chunksize=1, source_role="training"))

    merged = _merge_period_quality(records)
    group = merged["training|US100.cash|M1"]

    assert group["rows"] == 2
    assert group["by_period"]["day"]["2025-01-02"]["rows"] == 1
    assert group["by_period"]["day"]["2025-01-03"]["rows"] == 1
    assert group["by_period"]["week"]["2025-W01"]["rows"] == 2
    assert group["by_period"]["month"]["2025-01"]["rows"] == 2


def test_campaign_path_keeps_logical_repository_path_without_resolving_symlinks(
    tmp_path: Path,
) -> None:
    campaign = Path("outputs/gpu_campaigns/campaign.json")

    logical_path, relative = _campaign_path_from_repository(campaign, root=tmp_path)

    assert logical_path == tmp_path / campaign
    assert relative == "outputs/gpu_campaigns/campaign.json"


def test_campaign_path_rejects_paths_outside_repository(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.json"

    try:
        _campaign_path_from_repository(outside, root=tmp_path)
    except ValueError as error:
        assert "is not in the subpath" in str(error)
    else:
        raise AssertionError("an external campaign path must be rejected")
