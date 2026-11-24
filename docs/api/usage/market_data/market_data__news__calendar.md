# Market data · `news.calendar`

This page contains 5 public callable records owned by `market_data.news.calendar`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `CalendarEvent`

**Kind:** class · **Status:** stable · **Owner:** `market_data.news.calendar`

**Purpose:** One high-impact USD release.

**Exact API:** {py:obj}`market_data.news.calendar.CalendarEvent` · **Source:** [market_data/news/calendar.py:60](../../../../market_data/news/calendar.py#L60)

**Observed usage:**

1. [production caller: `events_from_ics`](../../../../market_data/news/calendar.py#L194)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def events_from_ics(path: Path, source: str) -> list[CalendarEvent]:
    digest = _sha256(path)
    rows: list[CalendarEvent] = []
    for start, summary in parse_ics(path.read_text(encoding="utf-8", errors="replace")):
        category = classify(summary)
        if category is not None:
            rows.append(CalendarEvent(start, category, summary, source, digest))
    return rows
```

2. [production caller: `fomc_events`](../../../../market_data/news/calendar.py#L212)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def fomc_events(statement_time: str = FOMC_STATEMENT_TIME) -> list[CalendarEvent]:
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
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `blackout_mask`

**Kind:** function · **Status:** stable · **Owner:** `market_data.news.calendar`

**Purpose:** True for each bar whose start falls within the blackout window of any release.

**Exact API:** {py:obj}`market_data.news.calendar.blackout_mask` · **Source:** [market_data/news/calendar.py:255](../../../../market_data/news/calendar.py#L255)

**Inputs and outputs:**

- **Args:**

  ```text
  bar_times: Bar start times, timezone-aware.
  release_times: Scheduled release times, timezone-aware.
  minutes_before: Blackout length before each release, in minutes.
  minutes_after: Blackout length after each release, in minutes.
  ```

- **Returns:**

  ```text
  One flag per bar, True when the bar is blacked out.
  ```

**Observed usage:**

1. [test fixture: `test_blackout_window_is_inclusive_and_uses_bar_start`](../../../../tests/unit/market_data/test_news_calendar.py#L84)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_blackout_window_is_inclusive_and_uses_bar_start() -> None:
    release = datetime(2025, 2, 7, 13, 30, tzinfo=UTC)
    bars = [
        datetime(2025, 2, 7, 13, 24, tzinfo=UTC),  # 6 min before: outside
        datetime(2025, 2, 7, 13, 25, tzinfo=UTC),  # exactly 5 min before: inside
        datetime(2025, 2, 7, 13, 30, tzinfo=UTC),  # at release: inside
        datetime(2025, 2, 7, 13, 35, tzinfo=UTC),  # exactly 5 min after: inside
        datetime(2025, 2, 7, 13, 36, tzinfo=UTC),  # 6 min after: outside
    ]

    mask = blackout_mask(bars, [release], minutes_before=5, minutes_after=5)

    assert mask == [False, True, True, True, False]
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `classify`

**Kind:** function · **Status:** stable · **Owner:** `market_data.news.calendar`

**Purpose:** Return the USD high-impact category for a release summary, or None to skip it.

**Exact API:** {py:obj}`market_data.news.calendar.classify` · **Source:** [market_data/news/calendar.py:152](../../../../market_data/news/calendar.py#L152)

**Inputs and outputs:**

- **Args:**

  ```text
  summary: The release summary text.
  ```

- **Returns:**

  ```text
  The category name, or None when the release is not kept.
  ```

**Observed usage:**

1. [test fixture: `test_classify_keeps_headline_releases_only`](../../../../tests/unit/market_data/test_news_calendar.py#L44)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_classify_keeps_headline_releases_only() -> None:
    assert classify("Employment Situation") == "NFP"
    assert classify("Real Earnings; CPI") == "CPI"
    assert classify("PPI") == "PPI"
    assert classify("JOLTS") == "JOLTS"
    assert classify("GDP (Advance Estimate), Q4 and Year 2025") == "GDP"
    assert classify("Personal Income and Outlays, December 2024") == "PCE"
    assert classify("Employment Situation of Veterans") is None
    assert classify("State JOLTS") is None
    assert classify("Real Earnings") is None
    assert classify("GDP by State and Personal Income by State") is None
```

2. [production caller: `events_from_ics`](../../../../market_data/news/calendar.py#L192)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def events_from_ics(path: Path, source: str) -> list[CalendarEvent]:
    digest = _sha256(path)
    rows: list[CalendarEvent] = []
    for start, summary in parse_ics(path.read_text(encoding="utf-8", errors="replace")):
        category = classify(summary)
        if category is not None:
            rows.append(CalendarEvent(start, category, summary, source, digest))
    return rows
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `events_from_ics`

**Kind:** function · **Status:** stable · **Owner:** `market_data.news.calendar`

**Purpose:** Parse one downloaded feed and keep its USD high-impact releases.

**Exact API:** {py:obj}`market_data.news.calendar.events_from_ics` · **Source:** [market_data/news/calendar.py:179](../../../../market_data/news/calendar.py#L179)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Downloaded iCalendar file.
  source: URL or label recorded as the provenance of each row.
  ```

- **Returns:**

  ```text
  Calendar events for the kept releases.
  ```

**Observed usage:**

1. [test fixture: `test_events_from_ics_records_source_hash`](../../../../tests/unit/market_data/test_news_calendar.py#L60)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_events_from_ics_records_source_hash(tmp_path: Path) -> None:
    path = tmp_path / "feed.ics"
    path.write_text(SAMPLE_ICS, encoding="utf-8")

    rows = events_from_ics(path, "test-source")

    assert [row.category for row in rows] == ["NFP", "GDP"]
    assert all(len(row.source_sha256) == 64 for row in rows)
```

2. [production caller: `main`](../../../../market_data/news/calendar.py#L320)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
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
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `fomc_events`

**Kind:** function · **Status:** stable · **Owner:** `market_data.news.calendar`

**Purpose:** FOMC statement rows at ``statement_time`` ET, marked by their assumed time in the summary.

**Exact API:** {py:obj}`market_data.news.calendar.fomc_events` · **Source:** [market_data/news/calendar.py:198](../../../../market_data/news/calendar.py#L198)

**Inputs and outputs:**

- **Args:**

  ```text
  statement_time: Assumed statement time as ``HH:MM`` in America/New_York.
  ```

- **Returns:**

  ```text
  One calendar event per FOMC statement date.
  ```

**Observed usage:**

1. [test fixture: `test_fomc_statement_time_follows_daylight_saving`](../../../../tests/unit/market_data/test_news_calendar.py#L67)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_fomc_statement_time_follows_daylight_saving() -> None:
    rows = {row.utc_time.date(): row.utc_time for row in fomc_events()}

    # 14:00 New York time is 19:00 UTC in winter and 18:00 UTC in summer.
    assert rows[datetime(2025, 1, 29).date()] == datetime(2025, 1, 29, 19, tzinfo=UTC)
    assert rows[datetime(2025, 6, 18).date()] == datetime(2025, 6, 18, 18, tzinfo=UTC)
```

2. [test fixture: `test_write_calendar_sorts_rows_and_records_provenance`](../../../../tests/unit/market_data/test_news_calendar.py#L90)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_write_calendar_sorts_rows_and_records_provenance(tmp_path: Path) -> None:
    events = fomc_events()[:2]
    out = tmp_path / "calendar.csv"

    count = write_calendar(list(reversed(events)), out, "2026-11-23")

    lines = out.read_text(encoding="utf-8").splitlines()
    assert count == 2
    assert lines[0].startswith("utc_time,category,summary")
    assert lines[1].startswith("2025-01-29T19:00:00Z,FOMC")
    assert lines[1].endswith(",2026-11-23")
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
