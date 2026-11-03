# Selected policy trade lifecycle

This evidence packet reconciles the selected seed-50 policy's recorded
decisions, fill events, and completed positions by `position_id` across the
preserved 2025 training and previously inspected 2026 report partitions. The
2026 interval had already been inspected, so these reports are descriptive
historical evidence and cannot serve as untouched confirmation.

The reusable evaluator is
[`summarize_policy_trade_lifecycle.py`](../../../scripts/research/analysis/evaluation/summarize_policy_trade_lifecycle.py).
Run it against any compatible report directory with:

```bash
python scripts/research/analysis/evaluation/summarize_policy_trade_lifecycle.py \
  --run-dir <directory-containing-trades-fills-positions-csv> \
  --output-dir evidence/research/selected_policy_trade_lifecycle
```

The generated JSON and Markdown summarize event counts, timestamp ordering,
fill-to-position links, per-position and aggregate PnL reconciliation, holding
duration, and exit reasons. When every position is complete and no payout rows
exist, the report also checks that initial balance plus position net PnL equals
final equity; cases with payouts are explicitly left incomparable by that
identity. The selected training ledger matches all three aggregate values
within floating-point tolerance. The report also shows the gap between logged `decision_time` and
`order_submission_time`. For all 825 selected A4B training opens, this gap is
60 seconds; the resolved configuration declares open-stamped bars, while the
environment records `signal_time` at the current bar end. This is consistent
with a bar-label versus completed-bar availability boundary, not a measured
agent/network delay. The available trace does not record model inference
completion time, so exact decision latency remains unknown. Tick fills occur
after submission in the retained ledger. Source and output hashes are recorded in
[`evidence_manifest.json`](evidence_manifest.json).

The current environment event writer now records the completed-bar action time
as `decision_time` and keeps the source row label separately as
`decision_bar_time`; order-submit, open, and trade-setup records use the same
bar-end time as `signal_time` and `order_submission_time`. Focused regression
tests cover this contract. The historical selected run remains unchanged and
retains its 60-second logged gap; it is not rewritten as new evidence.

The source-ledger reconciliation does not validate candidate
detection/eligibility before the logged action, establish authoritative tick
chronology or executable quote availability, or identify causal loss
mechanisms. A separate [trade excursion packet](trade_excursions/README.md)
derives descriptive, timestamp-bounded MFE/MAE from the current configured
TickBook. The 2025 partition is training-period evidence, not untouched OOS
evidence.

## Paired training-ledger reconciliation

The preserved A4A and A4B training reanalysis ledgers have separate generated
reports in [`a4a_training/`](a4a_training/)
and [`a4b_training/`](a4b_training/). These are descriptive reconstructions of
the recorded decision, fill, and position tables; they are not new policy
replays. Their input and report checksums are recorded independently in each
arm's `evidence_manifest.json`.

| Training arm | Decision rows | Positions with linked fill events | Unlinked fill position IDs | Close-fill net PnL reconciles to position | Position PnL reconciles to metrics and ending equity |
|---|---:|---:|---:|---|---|
| A4A | 49,271 | 987 / 987 | 0 | 987 / 987 | Matched; differences below $0.000000001 |
| A4B | 53,629 | 825 / 825 | 0 | 825 / 825 | Matched; differences below $0.000000001 |

All recorded opens, complete positions, fill counts, and final close timestamps
match by `position_id` in both reports. The report also finds a 60-second
recorded decision-to-submission gap for every open in both arms. This is
consistent with the known bar-label versus completed-bar boundary and is not
measured model-inference or network latency. Neither arm's source tables
contain MFE/MAE columns; those measures are derived in the separate excursion
packet. The chain still does not join candidate proposal and eligibility to
the selected action; it therefore improves position/fill reconciliation
without resolving the entry/FSM cause of the historical loss.

To regenerate the paired reports from the retained local archive, run the
summarizer once per arm with its `training` directory as `--run-dir` and the
matching arm subdirectory here as `--output-dir`. The exact paths and source
hashes used for this build are in those generated manifests.

## Paired report-period ledger reconciliation

The saved `testing` partitions were also summarized from their recorded CSVs.
Their manifests explicitly mark the associated holdout as previously
inspected. These are report-only, descriptive ledger checks; no checkpoint
replay, fresh policy evaluation, or economic-comparison claim is made.

| Report arm | Positions with linked fill events | Unlinked fill position IDs | Close-fill net PnL reconciles | Position PnL reconciles to metrics and ending equity | Integrity |
|---|---:|---:|---|---|---|
| A4A | 203 / 203 | 0 | 203 / 203 | Matched; difference below $0.000000001 | Matched |
| A4B | 203 / 203 | 0 | 203 / 203 | Matched; difference below $0.000000001 | Matched |

The ending account equities are $89,998.38 for A4A and $89,632.06 for A4B.
The reports verify accounting consistency in the preserved files; they do not
alter the recorded survival-gate failures or make 2026 untouched evidence.
Inputs and report outputs are hashed in the arm-specific `evidence_manifest.json`
files under [`a4a_testing/`](a4a_testing/) and
[`a4b_testing/`](a4b_testing/).
