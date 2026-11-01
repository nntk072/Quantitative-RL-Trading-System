# Runtime APIs

Live strategy interfaces and broker-specific integrations are separated so policy logic can remain broker-neutral. The strategy consumes declared context and emits an intent; risk and execution contracts validate that intent; an integration translates it to vendor-specific orders and events.

## Lifecycle and stability boundary

Keep public strategy/provider contracts independent of broker SDK types. Adapters own symbol mapping, precision, order lifecycle, reconnect/error translation, and broker-specific risk constraints. Validate adapter behavior against contract tests and state explicitly where live behavior differs from simulation. Do not treat a paper or historical fill as proof of live execution equivalence.

## Entry points

Use [live and infrastructure](../../framework/live_and_infrastructure) for system boundaries and [add a broker adapter](../../how-to/add_broker_adapter) for implementation. Generated references: {doc}`live <../generated/live/index>` and {doc}`integrations <../generated/integrations/index>`.
