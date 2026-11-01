# Live strategy runtime

`live/runtime/` defines broker-neutral market-data and strategy protocols and
adapts a trained policy to live observations. `RLStrategyAdapter` rebuilds
configured features, constructs the versioned observation, invokes a decision
provider, and exposes the resulting signal to an integration.

It does not own broker connectivity, order submission, or vendor-specific
account fields. Keep feature causality and observation schema parity aligned
with simulation and evaluation. Focused tests are in `tests/unit/live/` and
`tests/unit/integrations/`.
