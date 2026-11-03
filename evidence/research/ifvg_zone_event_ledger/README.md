# Training-only IFVG zone event ledger

This packet records every source FVG that independently satisfies the configured IFVG confirmation rule. It compares that per-zone ledger with the existing scalar feature, which selects the newest matching source gap per row and direction.

- Primary instrument: `US100.cash`; source timeframe: `M1`.
- Training dates: 2024-12-30 through 2025-12-31 inclusive; rows: 351,432.
- Per-zone confirmations: 72,561; scalar confirmation pulses: 56,349.
- Same-row/direction collision groups: 13,136; additional per-zone confirmations suppressed by scalar projection: 16,212.
- Collision groups by direction: bearish: 6,217 groups, 7,641 suppressed; bullish: 6,919 groups, 8,571 suppressed.
- Collision group sizes (source gaps per row/direction): 2 zones: 10,606 rows, 3 zones: 2,070 rows, 4 zones: 387 rows, 5 zones: 60 rows, 6 zones: 13 rows.
- IFVG close-through threshold: 0.1; inverse opposing gap: False; buffer enabled: True.
- The selected flag marks the newest source gap under the production detector's source-time order. Ledger rows describe detector events, not policy proposals, trades, or independent economic opportunities.
- Source bars and date labels use the current local training data loaded through the configured pipeline.

## Files

- `ifvg_zone_event_ledger.csv`: one row per per-zone confirmation, with formation, pass-through, confirmation, geometry, and scalar-selection provenance.
- `ifvg_confirmation_collisions.csv`: only row/direction groups with more than one confirmed source gap.
- `monthly_collision_summary.csv`: monthly per-zone confirmations, scalar pulses, suppressed events, and collision rows.
- `event_ledger.json`: data/config/source identities and scope.
- `OUTPUT_SHA256SUMS`: SHA-256 for every packet file except the checksum file itself.

Reproduce from the repository root with:

```bash
.venv-x86/bin/python -m scripts.research.analysis.features.ifvg_zone_event_ledger
```
