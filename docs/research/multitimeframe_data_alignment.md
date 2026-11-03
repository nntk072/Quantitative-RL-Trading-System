# Configured multi-timeframe data alignment

## Scope and method

This local-data audit compares each configured native M3, M5, M10, M15, M30,
H1, H4, and D1 bar export with bars resampled from its paired M1 source for
US100 and US500. It covers the 2024-12-30 through 2025-12-31 development
period and the already exposed 2026-01-01 through 2026-10-16 reporting period.
The reporting period remains exploratory; it is not a fresh holdout.

For each split and symbol, the audit records source paths and SHA-256 hashes,
timestamp-set differences, OHLC/tick-volume/volume differences, native spread
comparisons against M1 mean and last-value aggregations, and the first M1 row
at or after each configured higher-timeframe close. M1 resampling uses
left-labeled, left-closed intervals: first open, maximum high, minimum low,
last close, summed tick volume and volume, and mean spread. Spread is reported
separately because its native aggregation meaning is not established by the
data files or this comparison.

## Results

| Period role | Native timeframe/symbol series | Native rows | Timestamp and OHLCV parity | Native spread differs from M1 mean | Native spread differs from M1 last | First M1 after close: exact / later / unavailable |
|---|---:|---:|---|---:|---:|---:|
| 2025 development | 15 | 532,350 | Exact on every row | 171,819 rows | 87,638 rows | 527,449 / 4,886 / 15 |
| 2026 exposed report | 15 | 423,018 | Exact on every row | 98,918 rows | 48,782 rows | 419,706 / 3,297 / 15 |

The 15 native series per period comprise seven US100 timeframes and eight
US500 timeframes. US100 D1 is configured as an M1-derived view in each split,
so the two D1 entries are recorded as `derived_only`, not as independent native
parity checks. The machine report contains 32 split/symbol/timeframe entries:
30 native comparisons and those two derived views.

For every native row, timestamps and open, high, low, close, tick volume, and
volume match the configured M1 aggregation within the audit's numeric
tolerance. Native spread differs from both the M1 mean and M1 last-value
references in all 30 native series. These are measured field differences;
they do not identify which spread aggregation is correct for this feed or show
that a feature or execution path used one of the alternatives.

The first-usable-M1 summary marks 15 final higher-timeframe rows per period as
having no later M1 observation. Later first-M1 timestamps are recorded, but
their gaps are not classified as market closures, missing data, or publication
latency. The configured schedule hash is retained in the report; its authority
for the feed's holidays, partial sessions, or unscheduled closures has not
been established. The largest measured first-M1 gaps are therefore not
interpreted as provider latency.

## Interpretation and limits

The bar audit supports timestamp and OHLCV resampling parity for the configured
native files. It does not establish the source clock or authoritative trading
calendar, explain the spread-field differences, validate tick chronology, or
prove that every feature family is prefix-causal. Tick missingness and
same-timestamp quote ordering remain separate data-quality gates. The exposed
2026 rows are included to characterize available local files only and must not
be used for model selection or confirmatory claims.

The source report is
[`configured_timeframe_parity.json`](../../evidence/research/releases/negative-evidence-readiness/configured_timeframe_parity.json).
Regenerate it with:

```bash
.venv-x86/bin/python scripts/research/analysis/market_data/compare_configured_timeframe_bars.py \
  --out evidence/research/releases/negative-evidence-readiness/configured_timeframe_parity.json
```

Pass `--config <repo-config.yaml>` to compare a different registered dataset
configuration; the report records the resolved config path and checksum.

## Reusable streaming quality profile

The domain-owned local input profiler also emits row and quality counts for
each source, grouped by source role, instrument, timeframe, and source period.
Its JSON schema is `qrl.market_data_quality_profile.v2`; the combined
`quality_counts_by_instrument_role_timeframe` section contains day, ISO-week
(Monday–Sunday), and month buckets, while each input record retains its own
period counts and file identity. Counters include parsed rows, timestamp
failures, non-finite or missing numeric rows, timestamp ordering/duplicate
events and observed gap thresholds; tick and bar records also include their
applicable quote or OHLC quality checks.

The profiler streams bounded CSV chunks and keeps period aggregates rather
than loading full exports into memory. Period labels use the parsed source
wall-clock fields: they do not convert through a timezone, DST rule, session
clock, or authoritative instrument calendar. Unparseable timestamps are
retained in an `unparsed_timestamp` bucket. Observed gaps are not automatically
classified as missing market bars. Aggregate order and keys are stable for the
same source bytes, campaign manifest, and code; only `created_at_utc` is an
audit-time field. Runtime duration is measured from the scheduler record, not
embedded in the report.

Regenerate the selected-campaign profile inside an approved CPU-node
allocation through a persistent login `tmux` session:

```bash
.venv-x86/bin/python scripts/research/analysis/market_data/scan_local_market_data_quality.py \
  --campaign outputs/gpu_campaigns/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1/campaign.json \
  --chunksize 500000 \
  --out evidence/research/releases/negative-evidence-readiness/local_market_data_quality.json
```

The command refuses to overwrite an existing report. The campaign role is
recorded as `training` or `testing`; instrument and timeframe are derived from
the local export name and remain descriptive labels, not independent source
authority.

The companion [monthly tick quote-side table](../../evidence/research/releases/negative-evidence-readiness/local_monthly_tick_quote_quality.csv)
and [figure](../../evidence/research/releases/negative-evidence-readiness/local_monthly_tick_quote_quality.png)
are generated from this profile by
`scripts/research/analysis/market_data/plot_market_data_quality_profile.py`.
They report the union of rows missing either required bid or ask side, divided
by the monthly tick-row count. The figure uses source-wall month labels and
describes local export quality; it does not establish quote availability at an
order arrival or classify sessions.

See also [data provenance and access](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/releases/negative-evidence-readiness/DATA_PROVENANCE_AND_ACCESS.md),
[time and validation concepts](../concepts/data_time_and_validation.md), and
[the validation protocol](validation_protocol.md).
