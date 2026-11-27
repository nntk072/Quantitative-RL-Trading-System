from __future__ import annotations

import json
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from market_data import quality_audit
from market_data.quality_audit import (
    _campaign_path_from_repository,
    _merge_period_quality,
    build_report,
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


def test_tick_audit_counts_large_gap_across_chunk_boundary(tmp_path: Path) -> None:
    path = tmp_path / "US100.cash_ticks_gap.csv"
    path.write_text(
        "<DATE>\t<TIME>\t<BID>\t<ASK>\t<LAST>\t<VOLUME>\t<FLAGS>\n"
        "2025.01.02\t10:00:00.000\t10\t11\t\t\t6\n"
        "2025.01.02\t11:00:01.000\t10\t11\t\t\t6\n",
        encoding="utf-8",
    )

    result = scan_csv(path, chunksize=1)

    assert result["observed_gap_counts"] == {
        "greater_than_1s": 1,
        "greater_than_60s": 1,
        "greater_than_3600s": 1,
    }
    assert result["quality_counts_by_period"]["day"]["2025-01-02"]["gap_greater_than_3600s"] == 1


@pytest.mark.parametrize(("role", "expected"), [("train", "training"), ("test", "testing")])
def test_daily_audit_infers_date_only_layout_and_normalizes_legacy_role(
    tmp_path: Path, role: str, expected: str
) -> None:
    path = tmp_path / f"US500.cash_D1_{role}.csv"
    path.write_text(
        "<DATE>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\n2025.01.02\t10\t12\t9\t11\n",
        encoding="utf-8",
    )

    record = scan_csv(path, chunksize=1, source_role=role)

    assert record["source_role"] == expected
    assert record["timeframe"] == "D1"
    assert record["row_count"] == 1


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("<TIME>\t<CLOSE>\n10:00:00\t100\n", "missing DATE column"),
        ("<DATE>\t<OPEN>\t<CLOSE>\n2025.01.02\t10\t10\n", "unsupported market input columns"),
        (
            "<DATE>\t<TIME>\t<BID>\t<ASK>\n2025.01.02\t10:00:00.001\t10\t10.5\n",
            "unsupported tick columns",
        ),
    ],
)
def test_quality_scan_rejects_incomplete_source_schema(
    tmp_path: Path, contents: str, message: str
) -> None:
    path = tmp_path / "incomplete.csv"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        scan_csv(path, chunksize=1)


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


def test_build_report_verifies_manifest_hashes_and_quote_minute_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bar = tmp_path / "data/training/US100.cash_M1_fixture.csv"
    tick = tmp_path / "data/training/US100.cash_ticks_fixture.csv"
    calendar = tmp_path / "config/calendar.csv"
    bar.parent.mkdir(parents=True)
    calendar.parent.mkdir(parents=True)
    bar.write_text(
        "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\n"
        "2025.01.02\t10:00:00\t10\t12\t9\t11\n"
        "2025.01.02\t10:01:00\t11\t13\t10\t12\n",
        encoding="utf-8",
    )
    tick.write_text(
        "<DATE>\t<TIME>\t<BID>\t<ASK>\t<LAST>\t<VOLUME>\n"
        "2025.01.02\t10:00:00.001\t10\t11\t10.5\t1\n",
        encoding="utf-8",
    )
    calendar.write_text("session_date\n2025-01-02\n", encoding="utf-8")
    audit_module = tmp_path / "market_data/quality_audit.py"
    audit_module.parent.mkdir()
    shutil.copyfile(Path(quality_audit.__file__), audit_module)

    inputs = {
        "calendar:config/calendar.csv": quality_audit.sha256_file(calendar),
        "training:data/training/US100.cash_M1_fixture.csv": quality_audit.sha256_file(bar),
        "training:data/training/US100.cash_ticks_fixture.csv": "0" * 64,
        "training:data/training/missing.csv": "1" * 64,
    }
    campaign_path = tmp_path / "outputs/campaign.json"
    campaign_path.parent.mkdir()
    campaign_path.write_text(
        json.dumps({"fingerprint": "registered-campaign", "data_inputs": inputs}),
        encoding="utf-8",
    )
    monkeypatch.setattr(quality_audit, "ROOT", tmp_path)
    monkeypatch.setattr(quality_audit, "__file__", str(audit_module))
    monkeypatch.setattr(
        quality_audit,
        "_campaign_path_from_repository",
        lambda path: (tmp_path / path, path.as_posix()),
    )
    monkeypatch.setattr(subprocess, "check_output", lambda *_args, **_kwargs: "a" * 40)

    report = build_report(Path("outputs/campaign.json"), chunksize=1)

    assert report["schema"] == "qrl.market_data_quality_profile.v2"
    assert report["repository_head"] == "a" * 40
    assert report["all_inputs_present"] is False
    assert report["all_input_hashes_match"] is False
    assert report["input_count"] == 4
    assert report["m1_tick_minute_coverage"]["training:US100.cash"] == {
        "m1_bar_minutes": 2,
        "tick_quote_minutes": 1,
        "m1_minutes_with_at_least_one_tick": 1,
        "m1_minutes_without_ticks": 1,
        "coverage_fraction": 0.5,
        "interpretation": (
            "minute overlap only; no session calendar or within-minute execution chronology implied"
        ),
    }


def test_build_report_omits_tick_coverage_without_matching_m1_bars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tick = tmp_path / "data/testing/US500.cash_ticks_fixture.csv"
    tick.parent.mkdir(parents=True)
    tick.write_text(
        "<DATE>\t<TIME>\t<BID>\t<ASK>\t<LAST>\t<VOLUME>\n"
        "2025.01.02\t10:00:00.001\t10\t11\t10.5\t1\n",
        encoding="utf-8",
    )
    audit_module = tmp_path / "market_data/quality_audit.py"
    audit_module.parent.mkdir()
    shutil.copyfile(Path(quality_audit.__file__), audit_module)
    campaign_path = tmp_path / "outputs/campaign.json"
    campaign_path.parent.mkdir()
    campaign_path.write_text(
        json.dumps(
            {
                "fingerprint": "tick-only-campaign",
                "data_inputs": {
                    "testing:data/testing/US500.cash_ticks_fixture.csv": quality_audit.sha256_file(
                        tick
                    )
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(quality_audit, "ROOT", tmp_path)
    monkeypatch.setattr(quality_audit, "__file__", str(audit_module))
    monkeypatch.setattr(
        quality_audit,
        "_campaign_path_from_repository",
        lambda path: (tmp_path / path, path.as_posix()),
    )
    monkeypatch.setattr(subprocess, "check_output", lambda *_args, **_kwargs: "a" * 40)

    report = build_report(Path("outputs/campaign.json"), chunksize=1)

    assert report["input_count"] == 1
    assert report["m1_tick_minute_coverage"] == {}


def test_quality_audit_module_entrypoint_dispatches_help(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["quality-audit", "--help"])

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(Path(quality_audit.__file__).resolve()), run_name="__main__")

    assert exit_info.value.code == 0
    assert "usage:" in capsys.readouterr().out


def test_quality_audit_cli_refuses_to_overwrite_existing_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "existing.json"
    output.write_text("prior report", encoding="utf-8")
    monkeypatch.setattr(quality_audit, "ROOT", tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["quality-audit", "--campaign", "missing.json", "--out", "existing.json"]
    )

    with pytest.raises(FileExistsError, match="refusing to overwrite existing evidence"):
        quality_audit.main()

    assert output.read_text(encoding="utf-8") == "prior report"


def test_quality_audit_cli_writes_report_to_new_nested_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "reports" / "nested" / "quality.json"
    report = {
        "input_count": 1,
        "input_bytes_scanned": 12,
        "all_inputs_present": True,
        "all_input_hashes_match": True,
    }
    monkeypatch.setattr(quality_audit, "ROOT", tmp_path)
    monkeypatch.setattr(quality_audit, "build_report", lambda *_args, **_kwargs: report)
    monkeypatch.setattr(
        sys,
        "argv",
        ["quality-audit", "--campaign", "campaign.json", "--out", "reports/nested/quality.json"],
    )

    quality_audit.main()

    assert json.loads(output.read_text(encoding="utf-8")) == report
