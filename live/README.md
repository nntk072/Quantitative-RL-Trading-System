# Live runtime

`live/` applies broker-neutral decision and risk contracts to streaming or
paper-trading inputs. It owns runtime composition, strategy adaptation, and
live-safe state handling; broker-specific calls belong to `integrations/`.

The runtime should validate provider metadata and action schemas before
execution, preserve causal bar/tick ordering, apply configured risk controls,
and make failures observable. Historical simulation parity is a separate
claim that requires evidence; shared interfaces alone do not prove identical
fills.

See the [live guide](../docs/modules/live.md),
[live execution sequence](../docs/architecture/runtime/live_execution.md),
and [deployment boundary](../docs/operations/DEPLOYMENT.md).

## Runtime path

The runtime receives market updates, assembles the configured observation,
asks a decision provider for a schema-compatible action, translates that
action into an intent, applies local risk checks, and forwards eligible orders
through a broker-neutral strategy interface. The adapter layer communicates
with the external platform. Disconnects, stale data, rejected orders, partial
fills, and shutdown behavior must be observable and handled explicitly.

Historical replay, paper trading, and live submission are distinct modes.
Shared schemas do not guarantee identical timing or fills. Keep broker I/O out
of reusable decision and simulation packages. Tests are under
`tests/unit/live/` and broker adapter tests under the integration package;
never treat a mocked broker test as live connectivity evidence.
