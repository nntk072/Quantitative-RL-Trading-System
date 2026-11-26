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

## Schema migration policy

- `market_data.arrow_schemas.SUPPORTED_SCHEMA_IDS` lists the ids this reader accepts (`market-event.v1`).
- Readers call `require_schema_id`, which fails closed on an unknown id or a table that mixes ids.
- Any change to a field's type, nullability or meaning requires a new schema id. An additive change
  still needs a new id if an older reader would misread the table.
- A new id ships with its converter, a test that reads the old and new ids, and a regenerated ledger.
  Old ledgers keep their id and are not rewritten.

## Not covered yet (DATA-SCHEMAS remains open)

- The tick/quote source (about 6 GB, `data/US100.cash_202412300105_202610162349.csv`) is not
  reconciled. Parsing it is heavy compute, so it needs an allocation or a lead decision, not the login host.
- Higher-timeframe MT5 exports (M3 to D1) are not reconciled against resampled M1 bars.
- The Polars round trip is not run because Polars is not installed in `.venv-x86`.
- Normalized event and feature-row schemas are not defined. Feature rows belong to CAUSAL-FEATURE-GRAPH.
- `SOURCE_CLOCK` is still a code constant; a test keeps it equal to `config/base/default.yaml`.
