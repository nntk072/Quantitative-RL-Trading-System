# Selected policy trade lifecycle

The retained selected seed-50 A4B training-partition record contains a
position-ID-linked path from policy decision through order submission and fill
to realized position exit. A reusable evaluator in
[`scripts/research/analysis/evaluation/summarize_policy_trade_lifecycle.py`](../../scripts/research/analysis/evaluation/summarize_policy_trade_lifecycle.py)
reconciles the saved CSVs without replaying the model or scanning market data.

## Recorded coverage

The report covers 53,629 decision/action rows, 1,678 fill events, and 825
completed positions from the 2025 training partition. All 825 positions have
linked fill events, matching fill counts, an opening fill matching the
position entry time, and close-fill net PnL matching the position total. The
recorded decision, order-submission, and fill timestamps are ordered for all
825 opens. Median recorded holding time is 636.317 seconds. Recorded exits
are 496 structural stops, 125 session-end closes, 122 structure TP3 exits,
and 82 EMA21 exits.

This is a recovery of recorded event lineage, not a new evaluation. The
associated 2026 holdout had already been inspected, so the result is
historical descriptive evidence and cannot be used as untouched confirmation.
The source tables do not identify candidate-detection and eligibility
transitions before policy decisions or contain per-position MFE/MAE columns.
A separate tick-based analysis derives bounded MFE/MAE summaries for the
recorded training positions; it does not establish authoritative feed
chronology or a feasible alternative exit. The report therefore does not
provide a complete failure-mechanism attribution or a causal claim. The
trade excursion evidence packet is at
`evidence/research/selected_policy_trade_lifecycle/trade_excursions/README.md`.

The machine report, source checksums, and exact reproduction command are in
`evidence/research/selected_policy_trade_lifecycle/`.
