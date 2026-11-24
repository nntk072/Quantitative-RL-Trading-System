"""USD high-impact release calendar: parse official iCalendar feeds and build a dated CSV.

Release times are published in advance, so a blackout built from them uses only
information known before each release (no outcome values are read). Each CSV row
carries its source file's SHA-256 and the retrieval date for provenance.

Sources: BEA (fetched by URL or read from a file) and BLS (read from a file that
was downloaded by hand, since bls.gov refuses scripted requests). The FOMC dates
come from the Federal Reserve calendar page; that page gives no statement time,
so FOMC rows use 14:00 America/New_York and are marked as assumed.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Headline releases only, matched on anchored patterns. Regional, state, county and
# annual-benchmark summaries are not matched, so they are never treated as headline releases.
_KEEP_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("NFP", re.compile(r"^Employment Situation(?! of)")),
    ("CPI", re.compile(r"(^|; )CPI$")),
    ("PPI", re.compile(r"^PPI$")),
    ("JOLTS", re.compile(r"^JOLTS$")),
    ("GDP", re.compile(r"^(GDP \(|Gross Domestic Product,)")),
    ("PCE", re.compile(r"^Personal Income and Outlays")),
)

FOMC_STATEMENT_DATES: tuple[date, ...] = (
    date(2025, 1, 29),
    date(2025, 3, 19),
    date(2025, 5, 7),
    date(2025, 6, 18),
    date(2025, 7, 30),
    date(2025, 9, 17),
    date(2025, 10, 29),
    date(2025, 12, 10),
    date(2026, 1, 28),
    date(2026, 3, 18),
    date(2026, 4, 29),
    date(2026, 6, 17),
    date(2026, 7, 29),
    date(2026, 9, 16),
    date(2026, 10, 28),
    date(2026, 12, 9),
)
FOMC_SOURCE = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
FOMC_STATEMENT_TIME = "14:00"


@dataclass(frozen=True)
class CalendarEvent:
    """One high-impact USD release."""

    utc_time: datetime
    category: str
    summary: str
    source: str
    source_sha256: str


def _unfold(text: str) -> list[str]:
    """Undo iCalendar line folding and split into logical content lines.

    Args:
        text: Raw iCalendar document text.

    Returns:
        Logical content lines, with folded continuations joined.
    """
    lines: list[str] = []
    for raw in text.splitlines():
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _unescape(value: str) -> str:
    """Decode the iCalendar text escapes used in SUMMARY values.

    Args:
        value: Escaped text from a content line.

    Returns:
        The unescaped text.
    """
    return value.replace("\\,", ",").replace("\\;", ";").replace("\\n", " ").replace("\\\\", "\\")


def _parse_dtstart(name_params: str, value: str) -> datetime:
    """Return the event start as an aware UTC datetime.

    Args:
        name_params: The property name and parameters, for example ``DTSTART;TZID=...``.
        value: The raw DTSTART value.

    Returns:
        The start time in UTC.

    Raises:
        ValueError: When the value has an unsupported format or no time zone.
    """
    match = re.fullmatch(r"(\d{8})T(\d{6})(Z?)", value)
    if match is None:
        raise ValueError(f"unsupported DTSTART value: {value!r}")
    naive = datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S")
    if match.group(3) == "Z":
        return naive.replace(tzinfo=UTC)
    tz_match = re.search(r"TZID=([^;:]+)", name_params)
    if tz_match is None:
        raise ValueError(f"DTSTART without UTC marker or TZID: {value!r}")
    return naive.replace(tzinfo=ZoneInfo(tz_match.group(1))).astimezone(UTC)


def parse_ics(text: str) -> list[tuple[datetime, str]]:
    """Return (UTC start, summary) for every VEVENT in an iCalendar document.

    Args:
        text: Raw iCalendar document text.

    Returns:
        One (start, summary) pair per complete VEVENT.
    """
    events: list[tuple[datetime, str]] = []
    start: datetime | None = None
    summary: str | None = None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            start, summary = None, None
        elif line == "END:VEVENT":
            if start is not None and summary is not None:
                events.append((start, summary))
        elif line.startswith("DTSTART"):
            name, _, value = line.partition(":")
            start = _parse_dtstart(name, value.strip())
        elif line.startswith("SUMMARY"):
            _, _, value = line.partition(":")
            summary = _unescape(value.strip())
    return events


def classify(summary: str) -> str | None:
    """Return the USD high-impact category for a release summary, or None to skip it.

    Args:
        summary: The release summary text.

    Returns:
        The category name, or None when the release is not kept.
    """
    for category, pattern in _KEEP_PATTERNS:
        if pattern.search(summary):
            return category
    return None


def _sha256(path: Path) -> str:
    """SHA-256 hex digest of a file's bytes.

    Args:
        path: File to hash.

    Returns:
        The hexadecimal digest.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def events_from_ics(path: Path, source: str) -> list[CalendarEvent]:
    """Parse one downloaded feed and keep its USD high-impact releases.

    Args:
        path: Downloaded iCalendar file.
        source: URL or label recorded as the provenance of each row.

    Returns:
        Calendar events for the kept releases.
    """
    digest = _sha256(path)
    rows: list[CalendarEvent] = []
    for start, summary in parse_ics(path.read_text(encoding="utf-8", errors="replace")):
        category = classify(summary)
        if category is not None:
            rows.append(CalendarEvent(start, category, summary, source, digest))
    return rows


def fomc_events(statement_time: str = FOMC_STATEMENT_TIME) -> list[CalendarEvent]:
    """FOMC statement rows at ``statement_time`` ET, marked by their assumed time in the summary.

    Args:
        statement_time: Assumed statement time as ``HH:MM`` in America/New_York.

    Returns:
        One calendar event per FOMC statement date.
    """
    hour, minute = (int(part) for part in statement_time.split(":"))
    rows: list[CalendarEvent] = []
    for day in FOMC_STATEMENT_DATES:
        local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=ET)
        rows.append(
            CalendarEvent(
                local.astimezone(UTC),
                "FOMC",
                f"FOMC statement (time assumed {statement_time} ET)",
                FOMC_SOURCE,
                "",
            )
        )
    return rows


def write_calendar(events: Iterable[CalendarEvent], out: Path, retrieved_on: str) -> int:
    """Write events sorted by time as CSV.

    Args:
        events: Events to write.
        out: CSV path; parent directories are created.
        retrieved_on: Retrieval date recorded on every row.

    Returns:
        The number of rows written.
    """
    rows = sorted(events, key=lambda event: event.utc_time)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["utc_time", "category", "summary", "source", "source_sha256", "retrieved_on"]
        )
        for event in rows:
            writer.writerow(
                [
                    event.utc_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    event.category,
                    event.summary,
                    event.source,
                    event.source_sha256,
                    retrieved_on,
                ]
            )
    return len(rows)


def blackout_mask(
    bar_times: Iterable[datetime],
    release_times: Iterable[datetime],
    *,
    minutes_before: int,
    minutes_after: int,
) -> list[bool]:
    """True for each bar whose start falls within the blackout window of any release.

    Uses only the release schedule, which is published in advance.

    Args:
        bar_times: Bar start times, timezone-aware.
        release_times: Scheduled release times, timezone-aware.
        minutes_before: Blackout length before each release, in minutes.
        minutes_after: Blackout length after each release, in minutes.

    Returns:
        One flag per bar, True when the bar is blacked out.
    """
    from bisect import bisect_left, bisect_right

    releases = sorted(release_times)
    before = minutes_before * 60
    after = minutes_after * 60
    mask: list[bool] = []
    for bar in bar_times:
        ts = bar.timestamp()
        lo = bisect_left(releases, datetime.fromtimestamp(ts - after, UTC))
        hi = bisect_right(releases, datetime.fromtimestamp(ts + before, UTC))
        mask.append(hi > lo)
    return mask


def main(argv: list[str] | None = None) -> int:
    """Build the USD calendar CSV from the given sources and return the exit code.

    Args:
        argv: Command-line arguments; ``sys.argv[1:]`` when None.

    Returns:
        Zero on success.
    """
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bea-ics", type=Path, required=True)
    parser.add_argument(
        "--fred-json",
        type=Path,
        default=None,
        help="Saved FRED release-dates response (market_data.news.fred), used for the BLS releases.",
    )
    parser.add_argument(
        "--bls-ics",
        type=Path,
        default=None,
        help="BLS calendar downloaded by hand from bls.gov (scripted access is refused).",
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--retrieved-on", default=date.today().isoformat())
    args = parser.parse_args(argv)
    from market_data.news.fred import events_from_fred_json

    events = [
        *events_from_ics(
            args.bea_ics, "https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics"
        ),
        *(
            events_from_ics(args.bls_ics, "https://www.bls.gov/schedule/news_release/bls.ics")
            if args.bls_ics is not None
            else []
        ),
        *(events_from_fred_json(args.fred_json) if args.fred_json is not None else []),
        *fomc_events(),
    ]
    count = write_calendar(events, args.out, args.retrieved_on)
    print(f"wrote {count} USD high-impact events to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
