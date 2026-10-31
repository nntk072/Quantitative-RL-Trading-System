# Integrations

`integrations/` adapts external execution and data systems to broker-neutral
contracts. The current integration is MetaTrader-specific. Keep vendor
objects, constants, and network/session behavior inside this boundary; do not
let broker SDK types leak into the simulation or decisioning core.

An adapter maps external quotes, positions, orders, and events into shared
domain contracts. It must handle unavailable connections, rejected orders,
partial fills, and unit/timezone conversion explicitly. Paper/live operation
requires its own deployment checks and should not be inferred from backtest
success.

See the [integration guide](../docs/modules/integrations.md),
[broker-adapter how-to](../docs/how-to/add_broker_adapter.md), and
[live runtime guide](../live/README.md).
The [MetaTrader guide](mt5/README.md) documents the current adapter components
and their order boundary.

## Adapter responsibilities

An adapter translates credentials/session state, quote and bar timestamps,
symbol metadata, order requests, broker responses, position snapshots, and
execution events. Normalize units and timezone at the boundary; keep vendor
types out of domain contracts. A returned order acknowledgement is not
necessarily a fill, and a local position snapshot can lag the broker.

## Extension and verification

Implement the shared broker/data interfaces and make connection lifecycle,
retry rules, idempotency, and unsupported order features explicit. Use a fake
or sandbox for deterministic tests of rejections, timeouts, partial fills,
reconnect, and duplicate submissions. Focused tests are under
`tests/unit/live/`; deployment checks are separate from unit-test evidence.
