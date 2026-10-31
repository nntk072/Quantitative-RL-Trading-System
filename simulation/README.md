# Simulation

`simulation/` turns a trading decision and market observation into account
state changes. It contains two related but separate execution paths: the
Gymnasium environment used for RL interaction and an event-driven backtest
engine for replaying trading strategies.

## Responsibilities

- Apply actions to a simulated account in chronological market order.
- Resolve entry and exit fills using configured bar or tick execution.
- Enforce account guardrails and record positions, costs, equity, and trades.
- Return rewards and observations to a learner through a framework-neutral
  transition contract and a Gymnasium adapter.
- Replay broker-neutral trading strategies through a separate event-driven
  backtest.

The package does not define PPO or SAC, own reusable neural networks, build
market features, or connect to a broker. Those responsibilities belong to
`learning/`, `models/`, `features/`, and `integrations/` respectively.

## Components

| Area | Role |
|---|---|
| [`environment/`](environment/README.md) | RL state machine, action/observation handling, simulated fills, risk, reward, and accounting |
| [`contracts/`](contracts/README.md) | Backend-neutral simulator transition value |
| [`backtest/`](backtest/README.md) | Event-driven replay for strategy decisions and protective events |

The dependency direction is verified in the
[package dependency model](../docs/architecture/dependency_model.md):
simulation can use trading domain and feature contracts, but it cannot depend
on neural model internals.

## Distinct runtime surfaces

`TradingEnv` presents `reset()` and Gymnasium's five-value `step()` interface.
Its `transition()` method returns `SimulationTransition`, which carries the
same observation, reward, termination flags, and info without requiring a
Gymnasium consumer. The event-driven backtest has a separate engine and event
accounting; results from the two surfaces should not be assumed equivalent
without a matched execution configuration and parity evidence.

## Inputs and outputs

The environment receives timestamped bars, a feature matrix aligned to those
bars, account/risk/execution configuration, and optionally tick quotes and
pre-session market context. It emits structured observations, scalar reward,
termination/truncation flags, and diagnostic information. Run artifacts record
the trade log and equity path for later evaluation and reporting.

## Tests and limits

Behavior is covered across `tests/unit/simulation/`, `tests/integration/`, and
`tests/architecture/`. Simulation validates the configured historical
execution model; it cannot prove that future market behavior or broker fills
will match the replay.

## Related guides

- [System architecture](../docs/architecture/README.md)
- [Trading contracts](../trading/README.md)
- [Data and feature preparation](../market_data/README.md) and
  [features](../features/README.md)
- [Evaluation](../evaluation/README.md)
