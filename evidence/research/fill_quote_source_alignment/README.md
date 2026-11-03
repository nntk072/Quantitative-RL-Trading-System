# Fill-to-tick quote source alignment

## Claim scope

The report aligns each tick-backed event in the selected treatment and control
fill ledgers to the corresponding timestamp group in the local US100 training
tick export. It reports missing required sides, whether the parser's first
valid quote carries a side, and whether quote values change within an exported
timestamp group.

The report does not infer sub-timestamp event order, establish the provider's
source clock or schedule, independently reconstruct or validate order arrival,
or prove the broker used a particular quote. It contains no raw market data
and makes no rights claim.

## Report and inputs

- Machine report: [`selected_campaign_fill_quote_alignment.json`](selected_campaign_fill_quote_alignment.json)
- Generator: [`analyze_fill_quote_source_alignment.py`](../../../scripts/research/analysis/market_data/analyze_fill_quote_source_alignment.py)
- Fixture coverage: [`test_fill_quote_source_alignment.py`](../../../tests/research/test_fill_quote_source_alignment.py)

The report stores SHA-256 values for both event ledgers, the tick input, and
the analysis tool. Both ledgers are scanned together so the large tick file is
read once. The configured `Etc/GMT-3` value is only the local conversion used
for timestamp matching; it is not an authoritative timezone claim.

The selected pair yielded 3,698 matched tick-backed events (1,812 entries,
1,886 exits) from 56,245,046 scanned tick rows. Sixteen events shared
timestamp groups with changed quote values. Eighty-seven events were in groups
with a missing required side; the parser's first valid quote carried that
side for all 87. Timestamp parsing had zero failures and the source stream had
zero out-of-order rows. These counts describe the exported source resolution,
not the exact executable quote at order arrival.

The report preserves the first stable-parser quote, carried-side source time
and age, and raw side ranges for each matched event. It also applies the
selected run's 0.25 price grid after side carry-forward. The recorded fill
price matches that configured-grid parser reconstruction for all 3,698 events;
without price-grid rounding, 667 match the raw stable-parser side price. This
is a parser reconstruction consistency result, not proof that the broker used
that quote: the treatment and control ledgers share position IDs, so direction
is resolved within `(event ledger source, position ID)`. Same-timestamp source
row order remains non-authoritative, and the report does not establish order
arrival chronology, provider clock, or exchange execution validity. It makes
no no-carry/next-valid-quote economic claim.

The same ledgers record order submission, execution order, arrival, and fill
timestamps for all 3,698 events. Every recorded fill is at or after arrival;
timestamp-derived order-to-arrival latency has median 14.881 ms and 95th
percentile 28.557 ms, while arrival-to-fill quote wait has median 127.216 ms,
95th percentile 332.372 ms, and maximum 9,268.604 ms. The selected configs
allow 30 ms randomized latency and up to 60,000 ms quote wait. For the 87
events whose required side was carried, its source update age at fill has
median 302 ms and maximum 981 ms. These are recorded-parser and ledger
consistency checks; they do not make same-timestamp row order authoritative or
establish an external clock.

## Carried-side position cohort

[`carried_quote_side_cohort.json`](carried_quote_side_cohort.json) enumerates
the 87 of 3,698 events (2.35%) whose required bid/ask side was absent from the
single raw row at the event timestamp and was supplied by parser carry-forward.
The carried side had a median source age of 302 ms and a maximum of 981 ms.
The events touch 39 A4A positions and 46 A4B positions. Their linked position
net PnL is descriptive of those positions; it is not attributed to the carried
quote and is not a counterfactual no-carry execution result. The analysis does
not change the selected campaign ledgers or replay policy decisions.

The cohort generator is
[`analyze_carried_quote_cohort.py`](../../../scripts/research/analysis/market_data/analyze_carried_quote_cohort.py).
Its output records hashes for the alignment report, fill ledgers, position
ledgers, and tick input. Current generator and report SHA-256 values are
`6ef4b288211f7ce3dd7785c6a6ee817b099d39f705bc5221e7151ae0ede01942` and
`8e9e57469debcd72abda28b7511fe91d35cde30ab0ebe18b5949fe3ec233281a`.

## Regeneration

To create a fresh scan, run from the repository root in a suitable CPU-node
allocation through a named persistent login tmux session. The scan streams the
tick export in bounded chunks and does not launch child Slurm steps.

```bash
.venv-x86/bin/python scripts/research/analysis/market_data/analyze_fill_quote_source_alignment.py \
  --events-csv outputs/gpu_campaigns/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1/reanalysis_daily_stop_semantics_20261024/ladder_a4a_entry_fsm_hidden_qgrid025/training/fills.csv \
  --events-csv outputs/gpu_campaigns/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1/reanalysis_daily_stop_semantics_20261024/ladder_a4b_entry_fsm_qgrid025/training/fills.csv \
  --ticks-csv data/training/US100.cash_202412300105_202610162349.csv \
  --source-timezone Etc/GMT-3 \
  --out evidence/research/fill_quote_source_alignment/selected_campaign_fill_quote_alignment.json
```

To refresh direction attribution, order-timing fields, and configured-grid
comparisons in the existing report after changing the analysis logic, use the
recorded tick scan and existing ledgers; this does not rescan the tick export:

```bash
.venv-x86/bin/python scripts/research/analysis/market_data/analyze_fill_quote_source_alignment.py \
  --regrid-existing-report evidence/research/fill_quote_source_alignment/selected_campaign_fill_quote_alignment.json \
  --events-csv outputs/gpu_campaigns/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1/reanalysis_daily_stop_semantics_20261024/ladder_a4a_entry_fsm_hidden_qgrid025/training/fills.csv \
  --events-csv outputs/gpu_campaigns/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1/reanalysis_daily_stop_semantics_20261024/ladder_a4b_entry_fsm_qgrid025/training/fills.csv \
  --source-timezone Etc/GMT-3 \
  --price-grid-increment 0.25 \
  --price-grid-config outputs/gpu_campaigns/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1/reanalysis_daily_stop_semantics_20261024/ladder_a4a_entry_fsm_hidden_qgrid025/config.yaml \
  --out evidence/research/fill_quote_source_alignment/selected_campaign_fill_quote_alignment.json
```

## Verification

```bash
.venv-x86/bin/python -m pytest tests/research/test_fill_quote_source_alignment.py -q
```
