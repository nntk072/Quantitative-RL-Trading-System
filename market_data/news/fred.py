"""FRED release-dates source for the USD news calendar (fills the BLS gap).

The BLS site refuses scripted downloads, but FRED's release-dates endpoint is a documented
API. It returns dates only, so each release gets its standard publication time in
America/New_York. Requires a free FRED API key in the environment variable FRED_API_KEY.

The FRED terms restrict storing or caching FRED content, so the raw response is kept only
as a local file for the calendar build and its SHA-256 is recorded. Check the current terms
before sharing the file.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

from market_data.news.calendar import CalendarEvent

ET = ZoneInfo("America/New_York")
FRED_RELEASE_DATES_URL = "https://api.stlouisfed.org/fred/release/dates"

# FRED release id -> (category, publication time in ET). Ids checked against FRED's releases
# list. PCE (54) is left out: BEA already provides it, and some BEA releases are at 10:00.
FRED_RELEASES: dict[int, tuple[str, time]] = {
    10: ("CPI", time(8, 30)),  # Consumer Price Index
    46: ("PPI", time(8, 30)),  # Producer Price Index
    50: ("NFP", time(8, 30)),  # Employment Situation
    53: ("GDP", time(8, 30)),  # Gross Domestic Product
    192: ("JOLTS", time(10, 0)),  # Job Openings and Labor Turnover Survey
}
FRED_SOURCE = "https://fred.stlouisfed.org/docs/api/fred/release_dates.html"


def fetch_release_dates(
    api_key: str,
    start: str,
    end: str,
    *,
    session: Any = requests,
) -> dict[str, Any]:
    """Return the FRED release-dates response for every configured release id.

    Args:
        api_key: FRED API key.
        start: First realtime date to request (YYYY-MM-DD).
        end: Last realtime date to request (YYYY-MM-DD).
        session: HTTP session with a ``get`` method; defaults to ``requests``.

    Returns:
        The combined response with a ``release_dates`` list.
    """
    combined: dict[str, Any] = {"release_dates": []}
    for release_id in FRED_RELEASES:
        response = session.get(
            FRED_RELEASE_DATES_URL,
            params={
                "api_key": api_key,
                "file_type": "json",
                "release_id": release_id,
                "realtime_start": start,
                "realtime_end": end,
                "include_release_dates_with_no_data": "true",
            },
            timeout=30,
        )
        response.raise_for_status()
        combined["release_dates"].extend(response.json().get("release_dates", []))
    return combined


def events_from_fred_json(path: Path, source: str = FRED_SOURCE) -> list[CalendarEvent]:
    """Convert a saved FRED release-dates response into calendar events.

    Args:
        path: Saved FRED JSON file.
        source: Provenance label recorded on every row.

    Returns:
        Calendar events for the configured release ids.
    """
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[CalendarEvent] = []
    for entry in payload.get("release_dates", []):
        release_id = int(entry["release_id"])
        if release_id not in FRED_RELEASES:
            continue
        category, at = FRED_RELEASES[release_id]
        day = datetime.strptime(entry["date"], "%Y-%m-%d").date()
        local = datetime.combine(day, at, tzinfo=ET)
        rows.append(
            CalendarEvent(
                local.astimezone(UTC),
                category,
                f"{entry.get('release_name', 'FRED release')} (FRED release {release_id})",
                source,
                digest,
            )
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    """Fetch FRED release dates to a local JSON file and return the exit code.

    Args:
        argv: Command-line arguments; ``sys.argv[1:]`` when None.

    Returns:
        Zero on success.

    Raises:
        SystemExit: When ``FRED_API_KEY`` is not set.
    """
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2025-01-01")
    parser.add_argument("--end", default="2026-12-31")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise SystemExit(
            "set FRED_API_KEY (free key from the St. Louis Fed) to fetch release dates"
        )
    payload = fetch_release_dates(api_key, args.start, args.end)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {len(payload['release_dates'])} FRED release dates to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
