"""Clock, session, and causality contracts for controlled local parity traces."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from research_tools.simulation.evaluation import (
    compare_simulator_local_session_account_trace as account_trace,
)
from research_tools.simulation.evaluation import compare_simulator_local_tick_trace as tick_trace
from research_tools.simulation.evaluation import (
    verify_simulator_local_session_account_trace as account_trace_verifier,
)

from artifacts.identity import file_sha256
from market_data.loading.ticks import TickBook

# Both development fixtures open at 16:30 Helsinki and 08:30 Chicago.
_DEVELOPMENT_SESSIONS = (("2025-01-06", "14:30"), ("2025-07-07", "13:30"))
_REPORT_ONLY_SESSION = ("2026-01-05", "14:30")


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("2025-03-10T16:32:00+03:00", "2025-03-10T08:32:00-05:00", True),
        ("2025-11-28T17:32:00+03:00", "2025-11-28T08:32:00-06:00", True),
        ("2025-03-10T16:32:00+03:00", "2025-03-10T08:33:00-05:00", False),
        ("2025-03-10T16:32:00", "2025-03-10T08:32:00-05:00", False),
    ],
)
def test_session_account_lifecycle_compares_timestamp_instants(
    left: str, right: str, expected: bool
) -> None:
    assert account_trace._same_instant(left, right) is expected
    assert account_trace_verifier._same_instant(left, right) is expected


def test_bar_fallback_session_account_trace_matches_swing_buffer_settings(
    trace_sources: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    bars, _ = trace_sources
    repository_bars = (
        account_trace.ROOT
        / "logs/agents/quantitative_trading_engineer"
        / (f"{tmp_path.name}_task13_account_trace_bars.csv")
    )
    repository_bars.parent.mkdir(parents=True, exist_ok=True)
    repository_bars.write_bytes(bars.read_bytes())

    try:
        report = account_trace.build_report(repository_bars, scenario="account_transition")
    finally:
        repository_bars.unlink(missing_ok=True)

    assert report["matched_execution_parameters"]["swing_buffer_pts"] == 0.0


@pytest.fixture
def trace_sources(tmp_path: Path) -> tuple[Path, Path]:
    """Write M1 bars and executable ticks in Helsinki wall time across both periods."""
    bars = tmp_path / "bars.csv"
    ticks = tmp_path / "ticks.csv"
    bar_rows = ["<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>"]
    tick_rows = ["<DATE>\t<TIME>\t<BID>\t<ASK>\t<LAST>\t<VOLUME>\t<FLAGS>"]
    for date, _ in (*_DEVELOPMENT_SESSIONS, _REPORT_ONLY_SESSION):
        for wall in pd.date_range(f"{date} 16:28", periods=10, freq="1min"):
            row_time = wall.strftime("%Y.%m.%d\t%H:%M:%S")
            bar_rows.append(f"{row_time}\t100\t101\t99\t100\t1\t0\t0")
            tick_rows.append(f"{row_time}.100\t100\t100.25\t0\t0\t0")
    bars.write_text("\n".join(bar_rows) + "\n", encoding="utf-8")
    ticks.write_text("\n".join(tick_rows) + "\n", encoding="utf-8")
    return bars, ticks


def _write_alignment(
    path: Path,
    ticks: Path,
    sessions: tuple[tuple[str, str], ...],
    *,
    entry_offsets: tuple[int, ...] = (2,),
    exit_offset: int = 5,
    source_timezone: str | None = "Europe/Helsinki",
) -> Path:
    """Write quote evidence whose UTC fills independently match the synthetic source rows."""
    events = []
    for day, utc_open in sessions:
        ny_open = pd.Timestamp(f"{day} {utc_open}", tz="UTC")
        for event_type, side, offset in (
            *(("open", "ask", offset) for offset in entry_offsets),
            ("close", "bid", exit_offset),
        ):
            order = ny_open + pd.Timedelta(minutes=offset)
            fill = order + pd.Timedelta(milliseconds=100)
            events.append(
                {
                    "event_type": event_type,
                    "direction": 1,
                    "required_quote_side": side,
                    "order_submission_time_utc": order.isoformat(),
                    "event_time_utc": fill.isoformat(),
                    "timestamp_group": {
                        "raw_rows_at_timestamp": 1,
                        "first_valid_quote_exists": True,
                        "source_timestamp_utc": fill.isoformat(),
                        "configured_grid_first_valid_bid": 100,
                        "configured_grid_first_valid_ask": 100.25,
                        "stable_parser_first_valid_bid": 100,
                        "stable_parser_first_valid_ask": 100.25,
                    },
                }
            )
    alignment = {
        "tick_source_sha256": file_sha256(ticks),
        "price_grid_application": {"increment": 0.25},
        "events": events,
    }
    if source_timezone is not None:
        alignment["source_timezone_used_for_timestamp_join"] = source_timezone
    path.write_text(json.dumps(alignment), encoding="utf-8")
    return path


def test_local_tick_trace_matches_winter_and_summer_ny_open_quotes(
    trace_sources: tuple[Path, Path], tmp_path: Path
) -> None:
    bars, ticks = trace_sources
    alignment = _write_alignment(tmp_path / "alignment.json", ticks, _DEVELOPMENT_SESSIONS)

    report = tick_trace.build_report(ticks, bars, alignment)

    assert report["trace_passed"] is True
    assert report["months_covered"] == ["2025-01", "2025-07"]
    assert [
        pair["replay"]["entry"]["environment"]["actual_tick_time"] for pair in report["trace_pairs"]
    ] == ["2025-01-06T14:32:00.100000+00:00", "2025-07-07T13:32:00.100000+00:00"]


def test_local_tick_trace_excludes_selectable_pairs_from_report_only_period(
    trace_sources: tuple[Path, Path], tmp_path: Path
) -> None:
    bars, ticks = trace_sources
    alignment = _write_alignment(
        tmp_path / "alignment.json", ticks, (*_DEVELOPMENT_SESSIONS, _REPORT_ONLY_SESSION)
    )

    report = tick_trace.build_report(ticks, bars, alignment)

    assert report["months_covered"] == ["2025-01", "2025-07"]
    with pytest.raises(ValueError, match="no monthly direction strata"):
        tick_trace.build_report(ticks, bars, alignment, start_month="2026-01")


def test_local_tick_trace_requires_ny_eligibility_on_decision_bar(
    trace_sources: tuple[Path, Path], tmp_path: Path
) -> None:
    bars, ticks = trace_sources
    alignment = _write_alignment(
        tmp_path / "alignment.json", ticks, _DEVELOPMENT_SESSIONS[:1], entry_offsets=(0, 1)
    )

    report = tick_trace.build_report(ticks, bars, alignment)

    replay = report["trace_pairs"][0]["replay"]
    assert replay["entry_order_time"] == "2025-01-06T08:31:00-06:00"
    for engine in ("environment", "backtest"):
        assert pd.Timestamp(replay["entry"][engine]["decision_bar_time"]) == pd.Timestamp(
            "2025-01-06T08:30:00-06:00"
        )


@pytest.mark.parametrize("source_timezone", ["Etc/GMT-3", None])
def test_local_tick_trace_rejects_unverified_alignment_clock(
    trace_sources: tuple[Path, Path], tmp_path: Path, source_timezone: str | None
) -> None:
    bars, ticks = trace_sources
    alignment = _write_alignment(
        tmp_path / "alignment.json", ticks, _DEVELOPMENT_SESSIONS, source_timezone=source_timezone
    )

    with pytest.raises(
        ValueError, match="quote-alignment timestamp join timezone.*Europe/Helsinki"
    ):
        tick_trace.build_report(ticks, bars, alignment)


def test_future_bar_high_does_not_change_an_earlier_entry_size() -> None:
    index = pd.date_range("2025-01-06 08:30", periods=8, freq="1min", tz="America/Chicago")
    bars = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}, index=index)
    orders = index[[2, 5]]
    book = TickBook(
        np.asarray([order.value + 100_000_000 for order in orders], dtype=np.int64),
        np.array([100.0, 101.0]),
        np.array([100.25, 101.25]),
    )

    def entry_sizes(source_bars: pd.DataFrame) -> tuple[float, float]:
        report = tick_trace.replay_local_tick_trace(
            tickbook=book,
            bars=source_bars,
            entry_order_time=orders[0],
            exit_order_time=orders[1],
            direction=1,
        )
        return (
            float(report["entry"]["environment"]["lots"]),
            float(report["entry"]["backtest"]["lots"]),
        )

    changed_bars = bars.copy()
    changed_bars.loc[index[6], "high"] = 250.0

    assert entry_sizes(changed_bars) == entry_sizes(bars)


def test_local_tick_trace_records_early_take_profit_as_failed_schedule(
    trace_sources: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bars, ticks = trace_sources
    bar_source = bars.read_text(encoding="utf-8")
    tick_source = ticks.read_text(encoding="utf-8")
    bars.write_text(
        bar_source.replace("2025.01.06\t16:33:00\t100\t101", "2025.01.06\t16:33:00\t100\t185"),
        encoding="utf-8",
    )
    ticks.write_text(
        tick_source.replace(
            "2025.01.06\t16:33:00.100\t100\t100.25", "2025.01.06\t16:33:00.100\t185\t185.25"
        ),
        encoding="utf-8",
    )
    alignment = _write_alignment(
        tmp_path / "alignment.json", ticks, _DEVELOPMENT_SESSIONS[:1], exit_offset=6
    )
    output = tmp_path / "local_trace.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compare_simulator_local_tick_trace.py",
            "--ticks-csv",
            str(ticks),
            "--bars-csv",
            str(bars),
            "--alignment-report",
            str(alignment),
            "--out",
            str(output),
        ],
    )

    with pytest.raises(SystemExit) as exit_status:
        tick_trace.main()

    assert exit_status.value.code == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["trace_passed"] is False
    assert report["trace_pair_count"] == 1
    replay = report["trace_pairs"][0]["replay"]
    assert replay["trace_passed"] is False
    assert replay["entry_order_time"] == "2025-01-06T08:32:00-06:00"
    assert replay["exit_order_time"] == "2025-01-06T08:36:00-06:00"
    actual_events = replay["schedule_miss"]["actual_events"]
    assert actual_events.keys() == {"environment", "backtest"}
    for events in actual_events.values():
        assert [event["type"] for event in events] == ["open", "tp_close"]
        assert pd.Timestamp(events[1]["fill_time"]) == pd.Timestamp("2025-01-06T08:33:00.100-06:00")
        assert events[1]["price"] == 185.0


def test_local_tick_account_trace_starts_at_ny_cash_open_in_both_seasons(
    trace_sources: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bars, ticks = trace_sources
    for directory in ("simulation", "market_data"):
        (tmp_path / directory).symlink_to(account_trace.ROOT / directory, target_is_directory=True)
    monkeypatch.setattr(account_trace, "ROOT", tmp_path)

    report = account_trace.build_report(bars, ticks_path=ticks)

    assert [session["first_bar"] for session in report["selected_sessions"]] == [
        "2025-01-06T08:30:00-06:00",
        "2025-07-07T08:30:00-05:00",
    ]
    assert report["trace_passed"] is True
