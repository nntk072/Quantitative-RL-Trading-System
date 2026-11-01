# Simulation and live/paper parity

The live runtime and historical simulator share broker-neutral trading
contracts, but they do not execute in the same market. A parity review compares
semantics at each boundary and records unavoidable differences.

| Boundary | Simulation | Paper/live path | Parity question |
|---|---|---|---|
| Data time | Historical bars/ticks with source timestamps and configured session calendar | Broker feed and MT5 adapter timestamps/quotes | Are timezone, symbol, completed-bar, and missing-data rules aligned? |
| Decision schema | Versioned observation/action schemas | Provider adapter consumes schema-bound decision input | Does adapter metadata match the checkpoint schema and feature order? |
| Risk | Environment/account guardrails and simulated sizing | Live risk manager, broker constraints, and account values | Are daily/max/trailing limits and units aligned? |
| Execution | Configured bar/tick quote, spread, latency, and slippage model | Broker order semantics, fill policy, spread, and actual latency | Which assumptions have a measured live analogue, and which remain modeled? |
| Position management | Deterministic configured stop/target/partial-close path | Broker/robot state, asynchronous fills, and reconnect logic | Are updates idempotent and reconciled after partial fills or restart? |
| Evidence | Manifest, ledgers, reports, and frozen inputs | Operational logs, broker receipts, versioned config, and account records | Can every decision be tied to input, policy version, and executed order? |

Shared interfaces do not prove economic parity. Before promotion, compare
decision outputs and risk decisions on matched snapshots, then exercise paper
reconciliation, rejects, partial fills, reconnect/recovery, and kill controls.
Historical backtest success is not permission to send real orders.

See [deployment boundaries](../operations/DEPLOYMENT.md),
[live runtime guide](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/live/runtime/README.md),
[MetaTrader integration](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/integrations/mt5/README.md), and
[execution costs](execution_and_costs.md).
