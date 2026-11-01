# Position helpers

`trading/positions/` contains broker-neutral calculations for managing open
position targets, including ordering remaining take-profit levels after a
target is completed.

Keep target ordering and partial-close semantics explicit. Broker-specific
position fields belong in `integrations/`; simulator fill behavior belongs in
`simulation/`. Focused tests are in `tests/unit/trading/` and
`tests/unit/simulation/`.
