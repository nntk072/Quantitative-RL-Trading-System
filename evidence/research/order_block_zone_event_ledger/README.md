# Training-only order-block zone event ledger

This packet records zone-specific retest confirmations and compares them with the existing scalar feature, which exposes only the current latest zone per direction.

- Instrument: US100.cash; training interval: 2024-12-30 through 2025-12-31; M1 rows: 351,432.
- Timeframes: M1, M3, M5, M10, M15, M30, H1, H4, D1; detector enabled in resolved config: False.
- Per-zone confirmations: 134,227; scalar retest pulses: 21,154; collision groups: 33,810.
- Per-zone confirmations not selected by the scalar view: 113,073; suppressed confirmations within same-row collision groups: 79,967.
- Counts describe the detector on current local training bars. They do not establish policy eligibility, publication timing, independent opportunities, or economic value.

## Files

- order_block_zone_retest_events.csv: one row per per-zone retest confirmation.
- order_block_retest_collisions.csv: same-timeframe, same-row, same-direction multi-zone confirmations.
- monthly_collision_summary.csv: monthly per-zone and scalar counts by timeframe and direction.
- resolved_config.yaml and event_ledger.json: configuration, source, and data identities.
