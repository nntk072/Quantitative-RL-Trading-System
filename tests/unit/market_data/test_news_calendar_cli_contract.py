"""News-calendar CLI combines local sources and respects optional feed flags."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from market_data.news import calendar, fred
from market_data.news.calendar import CalendarEvent


def _event(category: str, source: str) -> CalendarEvent:
    minute_offset = {"NFP": 3, "CPI": 2, "PCE": 1, "FOMC": 0}[category]
    return CalendarEvent(
        utc_time=datetime(2026, 1, 5, 13, 30, tzinfo=UTC) + timedelta(minutes=minute_offset),
        category=category,
        summary=f"{category} release",
        source=source,
        source_sha256=hashlib.sha256(category.encode("utf-8")).hexdigest(),
    )


def test_calendar_cli_combines_configured_sources_without_network(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    bea = tmp_path / "bea.ics"
    bls = tmp_path / "bls.ics"
    fred_json = tmp_path / "fred.json"
    output = tmp_path / "calendar.csv"
    bea.write_text("local fixture", encoding="utf-8")
    bls.write_text("local fixture", encoding="utf-8")
    fred_json.write_text("{}", encoding="utf-8")
    ics_calls: list[tuple[Path, str]] = []

    def fake_ics(path: Path, source: str) -> list[CalendarEvent]:
        ics_calls.append((path, source))
        return [_event("NFP" if path == bea else "CPI", source)]

    monkeypatch.setattr(calendar, "events_from_ics", fake_ics)
    monkeypatch.setattr(fred, "events_from_fred_json", lambda _path: [_event("PCE", "FRED")])
    monkeypatch.setattr(calendar, "fomc_events", lambda: [_event("FOMC", "Federal Reserve")])

    status = calendar.main(
        [
            "--bea-ics",
            str(bea),
            "--bls-ics",
            str(bls),
            "--fred-json",
            str(fred_json),
            "--out",
            str(output),
            "--retrieved-on",
            "2026-11-26",
        ]
    )

    assert status == 0
    assert [path for path, _ in ics_calls] == [bea, bls]
    rows = output.read_text(encoding="utf-8").splitlines()
    assert [row.split(",")[1] for row in rows[1:]] == ["FOMC", "PCE", "CPI", "NFP"]
    assert "wrote 4 USD high-impact events" in capsys.readouterr().out


def test_calendar_cli_does_not_read_optional_feeds_when_flags_are_absent(
    tmp_path: Path, monkeypatch
) -> None:
    bea = tmp_path / "bea.ics"
    output = tmp_path / "calendar.csv"
    bea.write_text("local fixture", encoding="utf-8")
    calls: list[Path] = []

    def read_ics(path: Path, _source: str) -> list[CalendarEvent]:
        calls.append(path)
        return [_event("NFP", "BEA")]

    monkeypatch.setattr(calendar, "events_from_ics", read_ics)
    monkeypatch.setattr(
        fred,
        "events_from_fred_json",
        lambda _path: (_ for _ in ()).throw(AssertionError("FRED feed was not configured")),
    )
    monkeypatch.setattr(calendar, "fomc_events", lambda: [])

    calendar.main(["--bea-ics", str(bea), "--out", str(output)])

    assert calls == [bea]
    assert len(output.read_text(encoding="utf-8").splitlines()) == 2
