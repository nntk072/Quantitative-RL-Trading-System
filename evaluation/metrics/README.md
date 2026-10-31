# Evaluation metrics

Metric functions summarize a chronological equity curve and trade ledger.
The core performance record is framework-neutral; specialized helpers cover
trade completion, return distributions, calibration, action diversity,
matched comparisons, cost/reward attribution, and leakage diagnostics.

Partial exits are fills within a position. Unless a question is specifically
about fills, trade statistics should aggregate realized legs once per
completed position and separately report open/incomplete positions. Metrics
must state units, annualization scale, costs, and sample size.

See the [metric reference](../../docs/reference/metrics.md) and
[`evaluation/README.md`](../README.md).
