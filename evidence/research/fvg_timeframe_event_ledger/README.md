# Training-only FVG timeframe event ledger

This packet records per-zone FVG retest confirmations on each configured source timeframe and compares them with that timeframe's scalar feature projection. The feature matrix keeps each timeframe as a separate block.

- Primary instrument: `US100.cash`; training dates: 2024-12-30 through 2025-12-31 inclusive.
- Source timeframes: `M1, M3, M5, M10, M15, M30, H1, H4, D1`; derived: `D1`.
- Per-zone confirmations: 49,780; visible by the end of the M1 spine: 49,780.
- Source scalar retest pulses: 46,285; same-timeframe collision groups: 3,262; visible zone retests not represented by a scalar: 3,495.
- Retest buffer: enabled `True` at fraction `0.1`.
- These are detector-event counts, not logical setup counts, policy actions, trades, or economic results.

## Files

- `fvg_timeframe_event_ledger.csv`: one row per source-zone retest confirmation and its M1 availability boundary.
- `fvg_timeframe_collisions.csv`: same-timeframe/source-row/direction groups with multiple zone confirmations.
- `event_ledger.json`: config, source, input, and scope identities.
- `OUTPUT_SHA256SUMS`: SHA-256 for every packet file except the checksum file itself.

Reproduce from the repository root with:

```bash
.venv-x86/bin/python -m scripts.research.analysis.features.fvg_timeframe_event_ledger
```
