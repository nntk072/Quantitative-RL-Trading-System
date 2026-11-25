# DATA-SCHEMAS quality ledger

Scope: the tracked example export `data/examples/US100.cash_M1_202412300105_202501020334.csv`
(2024-12-30 01:05 to 2025-01-02 03:34 Helsinki). It is an engineering fixture for the
normalized-bar schema. It is not a research dataset and is not scientific evidence.

Files:

- `build_quality_ledger.py`: generator. Reads only the example above, converts it with
  `market_data.arrow_schemas.mt5_export_to_bars`, and writes `quality_ledger.json`.
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
