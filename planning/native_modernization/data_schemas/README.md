# DATA-SCHEMAS

Canonical Arrow/Parquet schemas, validators, migrations, the data manifest and the data-quality ledgers
for the market-data inputs. Scope: the tracked example export and the pre-2026 offline windows of the
local US100.cash MT5 exports. None of these outputs is a research dataset or scientific evidence.

## Files

| File | Role |
|---|---|
| `data_manifest.json` | Data manifest: source identities and checksums, ledger checksums, and the canonical schema catalog generated from code. |
| `build_data_manifest.py` | Writes `data_manifest.json`. Reads ledgers and present sources; reads no 2026 value. |
| `quality_ledger.json` | Data-quality ledger for the tracked example (2,880 M1 rows). |
| `quality_ledger_pre2026_m1.json` | Data-quality ledger for the pre-2026 M1 window. |
| `build_quality_ledger.py` | Generator for both M1 ledgers. |
| `tick_reconciliation_pre2026.json` | Tick/quote ledger, counts only. **Produced before the quote-event.v1 change; see Open items.** |
| `build_tick_reconciliation.py` | Generator for the tick ledger (bounded CPU allocation). |
| `timeframe_reconciliation_pre2026.json` | M3 to D1 exports compared with M1 resampled to the same local buckets. |
| `build_timeframe_reconciliation.py` | Generator for the timeframe ledger. |

Code: `market_data/arrow_schemas.py` (schemas, validators, `mt5_export_to_bars`),
`market_data/event_schemas.py` (normalized events, feature rows), `market_data/coverage.py` (grid, gaps,
calendar classification), `market_data/schema_migration.py` (migrations, corrections),
`market_data/reconciliation.py` (row-wise reconciliation, quarantine, round trips),
`market_data/tick_reconciliation.py`, `market_data/timeframe_reconciliation.py`, `market_data/export_window.py`.

Regenerate (sources are gitignored; pass the repository `data/` directory):

    .venv-x86/bin/python planning/native_modernization/data_schemas/build_quality_ledger.py
    .venv-x86/bin/python planning/native_modernization/data_schemas/build_quality_ledger.py \
        --source <data>/US100.cash_M1_202412300105_202610162349.csv --window-before 2026.01.01 \
        --out planning/native_modernization/data_schemas/quality_ledger_pre2026_m1.json \
        --parquet-dir logs/agents/data_scientist_engineer/2026-11-26_data_schemas
    .venv-x86/bin/python planning/native_modernization/data_schemas/build_timeframe_reconciliation.py \
        --data-dir <data> --window-before 2026.01.01 \
        --out planning/native_modernization/data_schemas/timeframe_reconciliation_pre2026.json
    .venv-x86/bin/python planning/native_modernization/data_schemas/build_data_manifest.py --data-dir <data>

## Canonical schema definitions

Field names, Arrow types and nullability are in `data_manifest.json` under `schemas.tables`, generated
from the code constants. The code is the authority; `tests/unit/market_data/test_data_schema_ledger.py`
checks the manifest against it.

| Table | Schema id | Purpose |
|---|---|---|
| `QUOTE_SCHEMA` | `quote-event.v1` | Source quotes: bid, ask, optional sizes, explicit `origin` tag. |
| `LEGACY_QUOTE_SCHEMA` | `market-event.v1` | Untagged quote layout written before `quote-event.v1`. Read only by the migration. |
| `BAR_SCHEMA` | `market-event.v1` | OHLC bars: open (`event_time`), `close_time`, `available_at`, optional volume. |
| `BAR_REVISED_SCHEMA` | `market-event.v2` | Bars with an integer correction `revision`. |
| `TRADE_SCHEMA` | `market-event.v1` | Trades: price, optional size. |
| `INSTRUMENT_SCHEMA` | `instrument-metadata.v1` | Contract size, price tick, lot step, currency, session calendar, validity interval. |
| `CALENDAR_SCHEMA` | `session-calendar.v1` | Half-open session intervals (`trading`, `early_close`, `closed`). |
| `NORMALIZED_EVENT_SCHEMA` | `normalized-event.v1` | One row per quote, trade or bar with a positional payload. |
| `FEATURE_ROW_SCHEMA` | `feature-row.v1` | One decision-clock row of a feature set: `values` is `list<float64 nullable>` in manifest order. |
| `QUARANTINE_SCHEMA` | none | Quarantine record: source row, reason, action taken. |

The bar and trade layouts share `market-event.v1`, as recorded in the existing bar ledgers. The quote
layout does not, because it gained the `origin` field (see Migration).

## Time and identity contract

- Every event time is `timestamp[ns, tz=UTC]`. Arrow stores it as int64 nanoseconds since the epoch.
- The source clock is `Europe/Helsinki` for MT5 chart and tick exports (`SOURCE_CLOCK`, checked against
  `config/base/default.yaml` by a test). It is recorded in the manifest and in every ledger, not as a
  per-row column. The source label of each row is recoverable from the immutable source file at its
  `source_sequence` (0-based index into the export body), with the source sha256 in the ledger.
- Bars: `event_time` is the UTC open, `close_time` is open plus the timeframe, and `available_at` is
  `close_time`. An incomplete bar is never available.
- Quotes and trades: `available_at` equals `event_time` for tick exports. No latency is measured, so the
  field is not a claim about delivery time.
- Identity: `instrument_id` and `source_id` come from the converter constants and the registry, never
  from filenames. Each table carries `schema_id`, and the validators refuse any other id.
- `source_sequence` is the stable tie-breaker within an instrument.

## Quotes, missing values and synthetic data

- Missing values are null. Zero, NaN and infinity are never used as missing markers. A one-sided tick keeps
  an explicit null on the missing side.
- Every quote row in a market-data table carries `origin`: `observed` (from the source) or `ohlc_synthetic`
  (derived from bars). A null or unknown origin is a row defect.
- Outside the tables, the execution model derives an untagged quote from a bar. `CostModel.bar_quote` in
  `trading/execution/costs.py` returns bid = close and ask = close + spread. The backtest and environment fill
  quotes call it (`simulation/backtest/quotes.py`, `simulation/environment/fill_quote_runtime.py`). That output
  carries no origin tag. It is owned by the trading and simulation roles, so it is open item 9, not a change
  in this stream.
- A legacy quote table without `origin` is refused by `validate_quotes` until it is migrated.

## Validation rules

Each validator returns every violation with its row index and a reason. Schema errors (a missing column, a
mixed or unaccepted schema id, a feature width mismatch) raise `ValueError`. A row defect quarantines that
row and never stops the table.

| Rule | Where | Test |
|---|---|---|
| Null in a non-nullable field is a row defect, reported as such | all `validate_*` | `test_schema_contract_rules.py` |
| Duplicate key: every occurrence flagged, not only the second | quotes, trades, bars, normalized, features | `test_arrow_schemas.py`, `test_event_schemas.py` |
| Order: event time must not move backwards in source sequence (per instrument) | quotes, trades, bars, normalized | `test_schema_contract_rules.py` |
| Finite, positive prices; finite, non-negative sizes and volume | quotes, trades, bars, normalized, instruments | `test_schema_contract_rules.py` |
| `bid <= ask`, for both quote tables and normalized quotes | quotes, normalized | `test_arrow_schemas.py`, `test_schema_contract_rules.py` |
| OHLC bounds, `close_time > event_time`, `available_at >= close_time` | bars | `test_arrow_schemas.py` |
| `available_at >= event_time` | quotes, trades, normalized | `test_arrow_schemas.py` |
| Instrument: positive tick, lot step, contract size; three-letter currency; non-overlapping validity | instruments | `test_schema_contract_rules.py` |
| Calendar: `close > open`, known kind, no overlap per instrument | calendar | `test_arrow_schemas.py` |
| DST: nonexistent and ambiguous Helsinki labels quarantined with a reason | `mt5_export_to_bars`, ticks | `test_mt5_export_to_bars.py`, `test_reconciliation.py` |
| Timestamp unit: integer epoch values must fall within 1990 to 2100 UTC for the declared unit | `epoch_to_utc_ns` | `test_timestamp_units_and_grid_coverage.py` |
| Feature row: no information after `event_time`; no NaN or inf; content hash present; one feature set | feature rows | `test_event_schemas.py` |
| Coverage: grid off-grid rows, gaps with missing slots, calendar classification | `coverage.grid_report` | `test_timestamp_units_and_grid_coverage.py` |
| Chronology: strictly increasing event times across chunk boundaries (ticks) | `tick_reconciliation` | `test_tick_reconciliation.py` |

Validators read whole columns with NumPy and pandas, not row loops, except the calendar, the instrument
overlap sweep and the normalized-event payload rules. The tick converter still runs per chunk in Python.

## Quarantine, duplicates, corrections

- Rows that fail a rule are reported with a reason. A row that cannot be converted to a UTC instant is
  excluded from the table and kept in the quarantine record with its source date, time and reason.
- Duplicate quotes are not merged or dropped. Exact repeats are a policy point that the tick ledger does not
  yet count (see Open items).
- A corrected bar is never overwritten. `append_correction` appends it as the next `revision` for the same
  `(instrument_id, event_time)`; the earlier rows remain. `latest_revision` gives the current view.
- Nothing is repaired silently. A dropped or corrected row is always named in a ledger or a quarantine
  record.

## Gaps and coverage

- `coverage.grid_report` lists every gap longer than one grid step, its missing slots, and off-grid rows.
- A gap is classified only against a session calendar the caller supplies, and only when that calendar
  covers the whole missing interval:
  - `calendar_closed`: covered, and no trading session overlaps it;
  - `unexplained`: covered, and a trading session overlaps it;
  - `unclassified`: no calendar, or the calendar does not cover it.
- No authoritative US100.cash calendar is in the repository. `config/README.md` states that
  `config/ny_session_schedule.csv` is not asserted to be one, so every gap in the current ledgers is
  `unclassified`. This is the blocker for gap classification (see Open items).

## Schema versions and migration

- `market_data.arrow_schemas.SUPPORTED_SCHEMA_IDS` lists the ids this package reads: `market-event.v1`,
  `market-event.v2`, `quote-event.v1`, `session-calendar.v1`, `instrument-metadata.v1`,
  `normalized-event.v1` and `feature-row.v1`.
- `require_schema_id(table, accepted=...)` fails closed on an unknown id, a mixed table, or an id the caller
  does not accept. A reader that cannot interpret a newer id passes a narrower `accepted` set.
- Two explicit migrations, each reading one old id and writing one new id, refusing invalid input:
  - `migrate_bars_v1_to_v2`: `market-event.v1` bars to `market-event.v2`, revision 0 on every row.
  - `migrate_quotes_v1_to_quote_v1`: legacy quotes to `quote-event.v1`, every row tagged `observed`, because
    no legacy row could have been tagged synthetic. The migration refuses a table already in the new layout,
    a bar table passed as quotes, and any legacy row that fails the quote rules.
- Any change to a field's type, nullability or meaning requires a new schema id. An additive change still
  needs one if an older reader would misread the table. A new id ships with its converter, a migration or a
  refusal test, and a regenerated manifest.
- Old ledgers keep the id they were written with and are not rewritten.

## Round trips

- Every Parquet write is read back with PyArrow and with Polars. `polars>=2.2` is declared in `pyproject.toml`.
  The ledgers record `polars_values_equal`. The normalized-event and feature round-trip test uses
  `importorskip`, so a venv without Polars would skip it rather than fail. `.venv-x86` has Polars.
- The M1 reconciliation runs on `bars.parquet` read back from disk when `--parquet-dir` is given.

## Evidence

### Tracked example (`quality_ledger.json`)

2,880 source rows, 2,880 converted, 0 quarantined, reconciles. Two gaps, 1,590 missing minutes, both
`unclassified`. Regenerates exactly (`test_committed_example_ledger_regenerates_exactly`).

### Pre-2026 M1 window (`quality_ledger_pre2026_m1.json`)

| Item | Value |
|---|---|
| Source sha256 | `4c46c6c9820cba15cea38487228d9c334467087b8bb109e3ffad7ca234d83f8c` (recomputed and matched) |
| Body lines / in window / on or after cutoff | 630,787 / 351,432 / 279,355 |
| Converted / quarantined / reconciles | 351,432 / 0 / true (read back from `bars.parquet`) |
| Oracle disagreements (event time, DST class, values) | 0 |
| Parquet round trip | PyArrow and Polars equal |
| Gaps | 297 gaps, 176,973 missing minutes, all `unclassified` |
| Off-grid bars, duplicate event times | 0, 0 |

The source has no rows on the two Helsinki DST-switch Sundays (2025-03-30, 2025-10-26), so the window has no
nonexistent or ambiguous labels. The DST branch is covered by the synthetic fixtures in
`tests/unit/market_data/test_mt5_export_to_bars.py` and `test_reconciliation.py`.

### Higher-timeframe exports (`timeframe_reconciliation_pre2026.json`)

Regenerated with the current code; byte-identical to the prior ledger. Every export bar matches the
resampled M1 bucket on open, high, low, close and tick volume:

| Timeframe | Export bars | Matched | Export-only | Resampled-only | Field mismatches |
|---|---|---|---|---|---|
| M3 | 117,424 | 117,424 | 0 | 0 | 0 |
| M5 | 70,308 | 70,308 | 0 | 0 | 0 |
| M10 | 35,292 | 35,292 | 0 | 0 | 0 |
| M15 | 23,694 | 23,694 | 0 | 0 | 0 |
| M30 | 11,852 | 11,852 | 0 | 0 | 0 |
| H1 | 5,929 | 5,929 | 0 | 0 | 0 |
| H4 | 1,552 | 1,552 | 0 | 0 | 0 |
| D1 | 260 | 260 | 0 | 0 | 0 |

The first bucket of each export opens before the first M1 bar in the window and is counted as
`window_edge_partial_matched`. This agreement is not independent of the broker feed.

### Tick/quote export (`tick_reconciliation_pre2026.json`): prior revision, not current

The ledger's full-window run (Slurm job 21871047, exit 0) reported 56,245,046 window rows, 0 quarantined,
0 unexplained, 0 oracle and value mismatches, strictly ordered, 261 gaps over one hour, and 29 Parquet parts
read back equal. It was produced by the code before the `quote-event.v1` change, so it is **not** evidence
for the current schema. A bounded smoke run of the current converter on the first 200,000 pre-cutoff rows
converted all of them with zero quarantine and zero mismatches. That smoke run is engineering evidence only;
it is not a window result.

## Open items

Each item names the exact external need.

1. **Tick evidence under the current schema.** Re-run `build_tick_reconciliation.py` over the full pre-cutoff
   window with the current code. This needs one bounded CPU allocation (about 56M rows, 29 parts). The
   resource operator must approve it. Until then the tick ledger is stale for `quote-event.v1`.
2. **Authoritative US100.cash session calendar.** Gap classification needs a broker or venue calendar of
   trading sessions and closures, supplied as `session-calendar.v1`. Without it, all 297 M1 gaps stay
   `unclassified`. The owner or the data provider must supply it.
3. **Exact tick repeats.** The tick ledger does not count exact repeats (same instant, bid, ask and flags) as
   the policy requires. Adding this needs the tick re-run in item 1.
4. **Whole-file identity reads.** The source checksums and post-cutoff line counts read the full files,
   including 2026 bytes, because a whole-file sha256 is the raw identity. No 2026 value is parsed or
   reported. The lead should confirm this is acceptable for the reporting interval, or accept an identity
   that does not read the exposed interval.
5. **Polars in the lock file.** `pyproject.toml` declares Polars; this stream did not update `uv.lock`.
6. **Instrument registry.** `instrument-metadata.v1` has a schema and a validator, but the repository holds no
   registry export for US100.cash or US500.cash (contract size, price tick, lot step, currency, validity
   intervals). The owner or the broker must supply it before any instrument row can be written.
7. **Integer-epoch sources.** `epoch_to_utc_ns` refuses implausible values for a declared unit. The MT5 converters
   parse wall-clock text, not epochs, so no current converter calls it. It is ready for a source that writes epochs.
8. **Tick Parquet reconciliation from disk.** The tick converter reconciles each in-memory chunk and then reads
   every written part back for an equality check. It does not re-reconcile the parts from disk as the M1 ledger does.

9. **Untagged bar-derived quote in the execution model.** Reproducer:
   `CostModel(spread_points=0.6).bar_quote(close=20000.0)` returns `(20000.0, 20000.6)` with no origin. The
   trading role should return a tagged `ohlc_synthetic` quote or route it through `quote-event.v1`, and the
   simulation role should record the tag on fills. This stream does not edit `trading/execution`.

## Limits

- The source has no rows on the two DST-switch Sundays, so the DST branch is covered only by synthetic fixtures.
- `SOURCE_CLOCK` is a code constant, checked against `config/base/default.yaml` by a test.
- Duplicate-tick counting and the calendar-based gap classification are not implemented in the tick ledger.
