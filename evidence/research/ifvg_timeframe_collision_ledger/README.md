# Training-only IFVG timeframe collision ledger

This packet compares each configured source timeframe's per-zone IFVG confirmations with the existing merged scalar feature. It preserves the source-timeframe order used by the feature pipeline.

- Primary instrument: `US100.cash`; training dates: 2024-12-30 through 2025-12-31 inclusive.
- Source merge order: `M1, M3, M5, M10, M15, M30, H1, H4, D1`.
- Configured derived source timeframes: `D1`.
- Per-zone detector events: 105,451; visible by the end of the primary M1 index: 105,449.
- Source-scalar events: 86,629; merged-scalar events: 78,709.
- Same-availability-row/direction collision groups: 18,734; visible detector events suppressed by the merged scalar: 26,740.
- These are detector-event counts, not logical setup counts, policy proposals, trades, or economic opportunities.
- MTF availability follows `timeframe_close_times` and the configured session close map; external feed publication time and calendar authority are not asserted.

## Files

- `ifvg_timeframe_event_ledger.csv`: one row per source-gap confirmation, including its source selection and merged-scalar selection.
- `ifvg_timeframe_collisions.csv`: same-side confirmations mapped to the same M1 availability row.
- `event_ledger.json`: config, source, local-input, and scope identities.
- `OUTPUT_SHA256SUMS`: SHA-256 for every packet file except the checksum file itself.

Reproduce from the repository root with:

```bash
.venv-x86/bin/python -m scripts.research.analysis.features.ifvg_timeframe_collision_ledger
```
