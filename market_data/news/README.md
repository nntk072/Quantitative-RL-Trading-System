# Market-data news

USD high-impact release calendar and the news and spike guard used by the
simulator and backtest to block new entries and cancel resting limits.

| Module | Role |
|---|---|
| `calendar.py` | Parse iCalendar feeds (BEA, and BLS by hand), add FOMC statement dates, write a CSV with source hashes and retrieval dates. |
| `fred.py` | Fetch FRED release dates with a key from `FRED_API_KEY`. FRED content is not cached in the repository. |
| `guard.py` | Build the per-bar block mask from release blackouts and 5-bar spikes against a causal session baseline. |

## Public API

`market_data.news` exports `CalendarEvent`, `NewsGuardConfig`, `blackout_mask`,
`causal_atr5`, `classify`, `events_from_ics`, `fomc_events`,
`load_release_times`, `news_block_mask` and `news_guard_config`.

## Invariants

- Causal: a bar's block decision uses only earlier bars and the published release schedule.
- The session baseline for a bar excludes its own session.
- New entries are blocked in a blackout, and resting limits are cancelled, both for the
  same bar.
- The committed calendar (`data/news/usd_high_impact_calendar.csv`) covers BEA and FOMC
  only. NFP, CPI, PPI and JOLTS need BLS or FRED-derived dates, which are not committed.
