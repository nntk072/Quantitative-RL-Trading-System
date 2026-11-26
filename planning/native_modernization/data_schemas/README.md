# DATA-SCHEMAS quality ledger

Scope: the tracked example export `data/examples/US100.cash_M1_202412300105_202501020334.csv`
(2024-12-30 01:05 to 2025-01-02 03:34 Helsinki). It is an engineering fixture for the
normalized-bar schema. It is not a research dataset and is not scientific evidence.

Files:

- `build_quality_ledger.py`: generator. Converts an MT5 M1 export with
  `market_data.arrow_schemas.mt5_export_to_bars`, reconciles every source row with
  `market_data.reconciliation`, and writes a JSON ledger. Default input: the example above.
- `quality_ledger_pre2026_m1.json`: the same ledger for the pre-2026 window of the local M1 source
  (see below).
- `quality_ledger.json`: output. Source name and sha256, source and converted row counts,
  quarantined rows with reasons, gaps longer than one minute, first and last event time,
  schema version, and generator path.

The causal prefix-invariance check for CAUSAL-FEATURE-GRAPH lives in
`tests/unit/features/test_causal_prefix_invariance.py` and runs on the same example bars.

Regenerate with:

    .venv-x86/bin/python planning/native_modernization/data_schemas/build_quality_ledger.py

## Assumptions

- **Source clock.** The export's `<DATE>` and `<TIME>` are Helsinki wall-clock labels. This follows
  `config/base/default.yaml` (`data.timestamp_clock: "europe_helsinki"`). In code the clock is the
  constant `SOURCE_CLOCK = "Europe/Helsinki"` in `market_data/arrow_schemas.py`. That constant is
  not read from YAML yet, so it is a duplicated setting to reconcile before the config is treated as
  the single source of truth.
- **Bar timestamps.** Bars are stamped at the open (`data.bar_timestamp_convention: "open"`).
  `event_time` is the UTC open. `close_time` is open plus one minute for M1. `available_at` equals
  `close_time`, so no bar is visible before it closes.
- **Volume.** `<TICKVOL>` is used as `volume`. It is a tick count, not traded volume. `<VOL>`
  (zero in this file) and `<SPREAD>` are not carried into the bar schema.
- **Gaps.** A gap is a spacing above one minute between consecutive converted bar opens. The ledger
  lists gaps and does not classify them. The two gaps in this file (a daily break and a full-day
  closure on 2025-01-01) are expected from the instrument calendar, but classifying them belongs to
  the session schedule, not to this ledger.
- **Quarantine.** Rows that fail `validate_bars` or the DST local-time mapping are reported with a
  reason. Rows that are dropped from the table (DST gaps or overlaps) are marked
  `excluded_from_table`. Rows kept with a bar-rule violation are marked `retained_flagged`. This
  example has no quarantined rows.
- **Identity.** `instrument_id` is `US100.cash` and `source_id` is `mt5-export`. Identity comes from
  the instrument registry, not the filename.

## Pre-2026 window run

The owner-approved offline window is every M1 source row dated before `2026.01.01`. The local
source `data/US100.cash_M1_202412300105_202610162349.csv` is gitignored and is read-only input here.
Rows on or after the cutoff are never parsed, converted or checked; their line count is recorded
so the source line total reconciles. The 2026 reporting interval is not used for any result.

| Item | Value |
|---|---|
| Source sha256 | `4c46c6c9820cba15cea38487228d9c334467087b8bb109e3ffad7ca234d83f8c` |
| Body lines in file / in window / on or after cutoff | 630,787 / 351,432 / 279,355 |
| Converted bars / quarantined / reconciles | 351,432 / 0 / true |
| Independent oracle disagreements | 0 (event time, DST class, values) |
| Parquet round trip | 351,432 rows, schema and values equal |
| Gaps | 297 gaps, 176,973 missing bars (not classified; see the session schedule) |

Regenerate:

    .venv-x86/bin/python planning/native_modernization/data_schemas/build_quality_ledger.py \
        --source data/US100.cash_M1_202412300105_202610162349.csv --window-before 2026.01.01 \
        --out planning/native_modernization/data_schemas/quality_ledger_pre2026_m1.json \
        --parquet-dir logs/agents/data_scientist_engineer/2026-11-26_data_schemas

The Parquet files and `manifest.json` (sha256 of `bars.parquet` and `quarantine.parquet`) are in the
git-ignored logs tree, not tracked.

Finding: the source has no rows at all on the two Helsinki DST-switch Sundays (2025-03-30 and
2025-10-26), so the window has no nonexistent or ambiguous labels. The DST branch is exercised only
by the synthetic fixtures in `tests/unit/market_data/test_mt5_export_to_bars.py` and
`tests/unit/market_data/test_reconciliation.py`, not by source data.

## Higher-timeframe exports against resampled M1

`build_timeframe_reconciliation.py` writes `timeframe_reconciliation_pre2026.json`. It resamples the
pre-2026 M1 bars to each export's local wall-clock buckets (M3 to D1) and compares every export bar.
Counts and labels only. The window split is `market_data/export_window.py`, shared with the M1 ledger.

| Timeframe | Export bars | Matched | Export-only | Resampled-only | Any field mismatch |
|---|---|---|---|---|---|
| M3 | 117,424 | 117,424 | 0 | 0 | 0 |
| M5 | 70,308 | 70,308 | 0 | 0 | 0 |
| M10 | 35,292 | 35,292 | 0 | 0 | 0 |
| M15 | 23,694 | 23,694 | 0 | 0 | 0 |
| M30 | 11,852 | 11,852 | 0 | 0 | 0 |
| H1 | 5,929 | 5,929 | 0 | 0 | 0 |
| H4 | 1,552 | 1,552 | 0 | 0 | 0 |
| D1 | 260 | 260 | 0 | 0 | 0 |

Every bucket agrees on open, high, low, close and tick volume. The first bucket of each export opens
before the first M1 bar in the window, so it is partial at the window edge; it is counted
(`window_edge_partial_matched`). This is evidence that the MT5 higher-timeframe exports agree with the M1
source over the pre-2026 window. It is not independent of the broker feed, so it does not prove the feed.

## Normalized event and feature-row schemas

`market_data/event_schemas.py` defines two Arrow schemas with validators and tests.

- `NORMALIZED_EVENT_SCHEMA` (`normalized-event.v1`): one row per quote, trade or completed bar, with a
  common header (`event_time`, `available_at`, `source_sequence`, identities) and a positional payload
  (`value_a` to `value_d`, `size`). A field that does not apply is null. A one-sided quote stays in the
  quote table, not here.
- `FEATURE_ROW_SCHEMA` (`feature-row.v1`): one decision-clock row per feature set, with
  `values: list<float64 nullable>` in manifest order. A null is missing (warm-up or no data); NaN and
  infinity are refused. `available_at` must not be later than `event_time`, so a feature cannot use
  information from after its decision time. A table whose row width differs from the manifest is a
  schema error and is rejected outright.

## Parquet round trip with Polars

Every Parquet write in this package is read back with PyArrow and with Polars (Polars 2.2.0 in
`.venv-x86`). The M1 ledgers record `polars_values_equal`. The normalized-event and feature-row tests
round-trip through both readers. The Polars test uses `importorskip`, so a venv without Polars skips it
rather than failing. Polars is not in `pyproject.toml` or `uv.lock`.

## Correction and revision policy

- Source files are immutable. A converted table records the source sha256 and row counts.
- Duplicate quotes are not merged or removed. Exact repeats are reported, not dropped.
- A corrected bar is never overwritten. `market_data.schema_migration.append_correction` appends it as the
  next `revision` for the same `(instrument_id, event_time)`; the earlier rows stay. `latest_revision` gives
  the current view. Corrections are covered by `tests/unit/market_data/test_schema_migration.py`.
- Rows that fail a rule are excluded from the table and kept in the quarantine record with a reason.
  Nothing is repaired silently.

## Schema migration policy

- `market_data.arrow_schemas.SUPPORTED_SCHEMA_IDS` lists the ids this package supports:
  `market-event.v1`, `market-event.v2`, `normalized-event.v1` and `feature-row.v1`.
- `require_schema_id(table, accepted=...)` fails closed on an unknown id, a table that mixes ids, or an id
  outside `accepted`. A reader that cannot interpret a newer id passes a narrower `accepted` set and is refused.
- `market-event.v2` adds an integer `revision` to bars. It is produced only by
  `market_data.schema_migration.migrate_bars_v1_to_v2`, which reads only v1, writes only v2 with revision 0
  on every row, and refuses invalid v1 bars. The migration test covers this with a second schema id on a
  fixture: v2 is refused by v1 readers, and a v2 table is refused as migration input.
- Any change to a field's type, nullability or meaning requires a new schema id. An additive change
  still needs a new id if an older reader would misread the table.
- A new id ships with its converter, a test that reads the old and new ids, and a regenerated ledger.
  Old ledgers keep their id and are not rewritten.

## Tick/quote export

`market_data/tick_reconciliation.py` converts and reconciles the tick export (about 6 GB, gitignored) over
the pre-2026 window. It runs as one bounded CPU allocation (`build_tick_reconciliation.py`). Each row
lands once in the quote table or the quarantine record. Each kept row's UTC instant is checked against
a zoneinfo oracle on whole seconds, plus its milliseconds. One-sided ticks keep an explicit null. Crossed
quotes, DST labels, empty FLAGS and non-numeric fields are quarantined with a reason.

Result (`tick_reconciliation_pre2026.json`, Slurm job 21871047, batch-skl, exit 0): 56,245,046 window
rows; 56,245,046 converted; 0 quarantined; 0 unexplained; 0 oracle event, DST and value mismatches;
strictly ordered; 261 gaps over one hour (largest about 73 hours, weekend and holiday closures); 29 Parquet
parts, each read back equal with PyArrow and Polars. The 78,798,505 lines dated 2026 or later were counted
by label only. The Parquet parts and manifest are in the git-ignored logs tree.

## Limits (recorded, not blockers)

- The source has no rows on the two DST-switch Sundays (2025-03-30 and 2025-10-26). The DST branch is
  covered by synthetic tests only.
- The 2026 reporting interval is never parsed or used. Lines dated 2026 are counted by label only.
- Gaps (297 in the pre-2026 M1 window, 176,973 missing bars) are not classified against the session schedule.
- `SOURCE_CLOCK` is still a code constant; a test keeps it equal to `config/base/default.yaml`.
