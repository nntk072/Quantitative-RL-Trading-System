# Selected-run maximum-loss event reconciliation

This packet adds an independent check of recorded hard maximum-loss events in
the four preserved A4 equity partitions. It reads each saved equity series,
metrics file, breach ledger, reanalysis manifest, and pinned source config. It
resolves the configured initial-equity allowance and compares recorded
`max_drawdown` events with the first saved equity sample below the resulting
initial-balance floor. Equality is allowed; the breach predicate is strict
below, matching the selected user rule for the initial-balance boundary.

All four saved report summaries match their metrics and chronology. The pinned
configs use a $100,000 initial balance, a $10,000 fixed hard maximum-loss
allowance, and therefore a $90,000 initial-equity floor. Three partitions have
a recorded maximum-loss event; each event is below that floor, matches a saved
equity value, and occurs at the first sampled crossing. A4A training has no
recorded event and no observed crossing.

| Partition | Event count | Event/equity timestamp match | Result |
|---|---:|---|---|
| A4A training | 0 | no event or crossing | no_events |
| A4B training | 1 | event bar time | matched |
| A4A testing | 1 | liquidation fill time | matched |
| A4B testing | 1 | event bar time | matched |

The breach ledger can store equity at either its event bar time or its
liquidation `fill_time`. The auditor checks both and requires the matching
saved timestamp to equal the first observed crossing. For A4A testing the event
bar sample precedes liquidation and is above the floor; the post-fill equity
matches the later sub-bar sample. This distinction avoids comparing post-fill
equity with the earlier event-bar mark.

The pinned source configs do not record `ftmo.max_drawdown_mode`. The audit
therefore verifies only the configured initial-equity floor. It does not infer
static, end-of-day ratcheting, or intraday trailing behavior from current
source defaults. Saved equity is sampled, so this is not a tick-complete
reconstruction. The historical runs also used their pinned legacy daily-loss
counter; this packet does not replay actions that would change under the
current full-evaluation failure rule. It does not establish live parity or
policy quality.

Reproduce each report from the corresponding run directory listed in
`run_metadata.json`:

```bash
.venv/bin/python scripts/research/analysis/evaluation/audit_recorded_equity_series.py \
  --run-dir <selected-run-split> \
  --output evidence/research/simulator_execution_parity/max_loss_event_reconciliation/<arm_split>.json
```

The report, pinned inputs, analyzer/test hashes, and execution context are
recorded in `run_metadata.json`. The focused test output is preserved in
`focused_tests.log`; checksums are in `SHA256SUMS` and `SOURCE_SHA256SUMS`.
