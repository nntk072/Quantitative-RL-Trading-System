# Live runtime and infrastructure

The live runtime consumes broker-neutral strategy, decision, risk, and execution contracts. Broker integrations translate those contracts to vendor-specific data and order semantics. Compute modules describe device capabilities and scheduler adapters; they do not change trading semantics.

## Runtime boundary

A strategy receives normalized market/account context, asks its policy or decision provider for an intent, and passes that intent through configured risk controls before an adapter submits an order. The adapter is responsible for broker-specific symbol mapping, precision, order states, and error translation. Keep broker details behind `integrations/<broker>` so the policy and simulation paths remain testable without a live account.

Historical simulation and paper trading cannot guarantee live fills, latency, liquidity, reconnect behavior, or broker risk handling. Validate each adapter against its contract and report which behaviors were simulated versus observed. The curated [runtime API guide](../api/domains/runtime) links to generated live and broker references; the [engineering API guide](../api/domains/engineering) links to compute references.

## Operations boundary

Choose the compute environment to match the workload and architecture. Record device/runtime details with artifacts. For scheduled work, use the project Slurm helpers and preserve job identity, logs, and allocation state. A scheduler allocation demonstrates allocated resources; it does not by itself demonstrate utilization.

The [live execution architecture](../architecture/runtime/live_execution) traces the strategy boundary. Use [add a broker adapter](../how-to/add_broker_adapter) for extension steps, [deployment](../operations/DEPLOYMENT) for release operations, and the [operations index](../operations/README) for environment-specific guidance.
