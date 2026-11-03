# Standard-deviation swing-leg projection ledger

This training-only packet counts the selected producer's latest confirmed swing-leg projections and the contiguous candidate eligibility spans attached to each source leg.

- Training window: 2024-12-30 through 2025-12-31; primary symbol: `US100.cash`.
- Source timeframes: M1, M3, M5, M10, M15, M30, H1, H4, D1.
- Source leg projections: 59,057; with at least one retracement eligibility row: 36,008.
- Exact source-key groups appear on multiple timeframes: 1,346; these are key matches, not proof of shared logical events.
- A source leg is keyed by direction and the ordered source pivot times. Availability is the first M1 feature row carrying that valid leg key.
- Eligibility episodes count contiguous rows for one candidate/leg; they are not separate orders or trades.
- The producer exposes only its latest confirmed swing pair; overlapping latent legs are not represented.
- Timestamp keys inherit float64 subsecond precision limits and do not establish feed publication time.
- No report-period rows, policy actions, checkpoint loads, environment steps, or economic outcomes are used.

## Files

- `swing_leg_eligibility_ledger.csv`: one row per timeframe/source-leg/direction projection.
- `cross_timeframe_swing_leg_key_groups.csv`: exact source-time-key matches across timeframes.
- `ledger.json`: input, config, source, scope, and count metadata.
- `resolved_config.yaml`: resolved selected configuration.
- `OUTPUT_SHA256SUMS`: output checksums.

Reproduce on a compatible Triton allocation with the repository's active environment:

```bash
.venv/bin/python -m scripts.research.analysis.features.standard_deviation_swing_ledger
```
