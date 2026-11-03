# Local market data quality

This packet records a current-byte quality scan of the inputs named by the
selected P6 campaign manifest and a native-versus-M1-derived timeframe
comparison under the repository's base data configuration. It contains no
raw market data and makes no strategy-performance, provider-rights, or
external-clock claim.

## Findings

The selected manifest names 39 local inputs totaling 8,162,529,858 bytes. All
39 paths were present and every observed SHA-256 matched the campaign
manifest. The scan covered 172,290,383 tick rows and 2,215,084 bar rows.

Across the four tick exports, 371,390 rows had one required quote side missing
or non-finite (136,547 bid-side and 234,843 ask-side rows; none lacked both
sides). The scan observed 329,471 adjacent timestamp ties: 328,918 groups with
a changed quote and 553 with a missing quote; none were identical-quote ties.
There were no timestamp parse failures, adjacent reversals, nonpositive or
inverted quotes, or zero-spread rows. Optional `LAST` and `VOLUME` fields were
empty in all tick rows; the available flag column accounted for every row.
These findings describe file contents and do not assert what the flags mean.
The bar inputs had no timestamp parse
failures, adjacent reversals, duplicate timestamps, missing/non-finite numeric
rows, invalid OHLC rows, negative volumes, or negative spreads.

M1/tick overlap was complete in the two report-role exports. In each
training-role export, 23 M1 minutes had no tick quote minute (351,432 and
349,973 M1 minutes respectively). Minute overlap does not establish
within-minute quote chronology.

The timeframe report contains 32 series rows. All 30 native series (15 per
campaign role) have exact timestamp and OHLCV parity with M1-derived bars:
532,350 common rows for `training` and 423,018 for `testing`, with no missing,
extra, or OHLCV-mismatched rows. US100 D1 is derived from M1 in both roles
(260 and 206 rows); those rows have no native US100 D1 comparison. Under the
configured close schedule, the first-M1 availability table records 527,449
exact-at-close rows, 5,145 later rows, and 16 rows without a later M1 row for
the training role; the report role records 419,706, 3,502, and 16 respectively.
Spread is reported separately and is not part of the OHLCV parity status.

The same report now compares observed M1 rows in each HTF interval with the
nominal one-minute grid, clipping an interval at the configured NY close where
applicable. Across the 32 symbol/timeframe/role series, 19,507 of 955,834 bars
had fewer observed M1 rows than grid slots; none had zero or more-than-expected
observed M1 rows.
All 932 D1 bars are partial against a 1,440-minute grid; these counts do not
classify market closures or schedule gaps as data loss. Nonempty partial bins
are retained by the resampler and become visible only at the nominal or
configured close boundary. A sparse-M1 integration case confirms the aggregate
does not appear on earlier M1 rows and first appears on the first observed row
at or after its close.

## Interpretation limits

- The campaign roles describe its input paths; they do not establish licensing
  or define the policy's effective date split. The 2026-01-01 through
  2026-10-16 report interval remains exposed exploratory evidence.
- Timestamps and monthly labels are parsed source-wall-clock values. Gap counts
  do not classify expected closures as missing data. The configured schedule
  and timestamp model are recorded for reproducibility, not asserted as
  authoritative.
- Quote-side carry-forward, timestamp ties, and the lack of within-tie order
  limit execution chronology claims. The 23-pair simulator trace is separate
  controlled-action evidence, not policy replay.
- The user excluded external provider, license, and authoritative-calendar
  research. This packet therefore makes no rights or external schedule claim.

## TickBook side carry-forward counts

The reusable `audit_tickbook_carry_forward.py` streams the four hash-verified
campaign tick inputs through the production `build_tick_book` implementation
and counts source-valid rows, rows made valid by side carry-forward, retained
rows, and exclusions. It records 171,918,993 raw valid two-sided quote rows;
371,390 rows become valid after carrying at least one side (136,547 bid-side
and 234,843 ask-side carry counts); all 172,290,383 source rows are retained
and none are dropped under this no-session-filter transform. Per-input raw and
post-transform row classes reconcile. The paired sides may come from separate
source rows, so these counts do not establish simultaneous quote availability
or within-timestamp chronology. Exact source, builder, config, per-file hashes,
and counters are in [`tickbook_carry_forward_audit.json`](tickbook_carry_forward_audit.json).

Reproduce inside the existing ARM/GH200 environment with:

```bash
PYTHONPATH=. .venv/bin/python -m scripts.research.analysis.market_data.audit_tickbook_carry_forward
```

## Artifacts

- [`local_market_data_quality.json`](local_market_data_quality.json): campaign
  input identities, byte hashes, structural counts, period aggregates, and
  tick/M1 minute overlap.
- [`configured_timeframe_parity.json`](configured_timeframe_parity.json):
  native/resampled timestamp and OHLCV comparisons, observed-versus-expected
  M1 source-row counts, and first-M1 availability under the configured
  schedule.
- [`monthly_tick_quote_quality.csv`](monthly_tick_quote_quality.csv) and
  [`monthly_tick_quote_quality.png`](monthly_tick_quote_quality.png): exact
  monthly denominators and fractions of tick rows missing either required
  quote side. The plot labels are parsed source-wall months.
- [`monthly_tick_quote_quality.provenance.json`](monthly_tick_quote_quality.provenance.json):
  profile, generator, CSV, and figure hashes.
- [`SHA256SUMS`](SHA256SUMS): packet output checksums.

## Reproduction

Run from the repository root on the same local inputs. The streaming scan is
I/O intensive; this run took about 21 minutes on one GH200 allocation.

```bash
PYTHONPATH=. .venv/bin/python -m scripts.research.analysis.market_data.scan_local_market_data_quality \
  --out evidence/research/market_data_quality/local_market_data_quality.json
PYTHONPATH=. .venv/bin/python -m scripts.research.analysis.market_data.compare_configured_timeframe_bars \
  --out evidence/research/market_data_quality/configured_timeframe_parity.json
PYTHONPATH=. .venv/bin/python -m scripts.research.analysis.market_data.plot_market_data_quality_profile \
  --profile evidence/research/market_data_quality/local_market_data_quality.json \
  --csv-out evidence/research/market_data_quality/monthly_tick_quote_quality.csv \
  --figure-out evidence/research/market_data_quality/monthly_tick_quote_quality.png
```

## Data dictionary and period tables

[`period_quality_counts.csv`](period_quality_counts.csv) contains day/week/month quality metrics by source role, instrument, and timeframe. [`configured_timeframe_coverage.csv`](configured_timeframe_coverage.csv) flattens the 32 configured parity/availability rows. [`configured_bar_source_coverage.png`](configured_bar_source_coverage.png) plots observed M1 source rows against nominal configured grid slots, without treating partial bars as data loss. [`local_data_dictionary.md`](local_data_dictionary.md) documents source fields, units and limits with synthetic examples. These tables reuse the current machine reports and do not reread or bundle raw market rows. Their source/output hashes are in [`quality_table_provenance.json`](quality_table_provenance.json).
