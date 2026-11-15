# Live, paper, and MetaTrader

**Status:** draft
**Use this when:** You are tracing live inference, confirming the broker boundary, or checking what the repository means by paper mode.

## Summary and use this when

The broker-neutral runtime adapts a model or decision provider to a
directional signal. The MetaTrader integration owns terminal login, market
data, trader calls, and robot behavior. Its shipped entry points support
paper operation on a compatible terminal host. Real-order paths are
guarded in source.

For operational procedures, use the [deployment runbook](../../operations/DEPLOYMENT.md)
and compare its descriptions with the current entry-point guards. For
runtime boundaries, see the [live execution sequence](../../architecture/runtime/live_execution.md).

## Key terms

- [Paper trading and live trading](../../glossary.md)
- [Observation schema and action schema](../../glossary.md)
- [Checkpoint](../../glossary.md)
- [Risk budget](../../glossary.md)
- [Lineage](../../glossary.md)

## Explanation

### The three root entry points

| Entry point | Workflow | Real-order gate |
|---|---|---|
| `live_trading_rl.py` | Single-symbol SB3 policy with a configurable secondary feature input | `RLRobot` requires a manager advertising training-equivalent account-loss guardrails. The manager constructed by this entry point reports that it lacks them. |
| `live_trading.py` | Multi-symbol rule-based strategies | Its delegated initializer raises before starting a real-order system. |
| `demo_trading.py` | Single-symbol crossover demo | Its delegated robot factory rejects real-order mode before connecting. |

Each has a `--once` option for a single cycle. Paper mode defaults on.
The flag expression treats only the stripped, case-insensitive value
`false` as a request for real-order mode. That request still encounters
the relevant guard. Paper runs may use a live terminal and read broker
market or account data.

### Checkpoint and inference inputs

The RL entry point reads `--model` or `RL_MODEL_PATH` and requires an
existing file. It accepts `--config` or `RL_CONFIG_PATH`. When the config
is omitted, the resolver looks for the run's saved `config.yaml` two
directory levels above the model file. The saved configuration determines
feature setup, observation schema, and risk configuration.

The adjacent `run_manifest.json` and `feature_normalization_state.json`
are required JSON objects. The manifest's config, normalization, and
feature-cache records must also be objects. The resolver verifies the saved
config and normalization state hashes against file contents and checks the
normalization schema and filename. It compares the cache-hash values in the
manifest and state by equality. That check passes when all three cache-hash
values are absent or null, since each lookup then returns `None`.

The RL adapter builds the live observation schema using resolved policy
settings and checks incoming provider schema metadata. The primary input
is an M1 source. The entry point uses its feature settings to determine
whether to wire a secondary M1 source for SMT. Broker symbol spelling
and the actual returned data need review on the intended terminal.

### Sizing, account state, and submission

The shipped robot checks position size and broker stop information before
requesting a new position. It refuses invalid or zero sizes and missing
or invalid stops. Paper handling logs intended opens and closes. The
terminal-facing trader is responsible for actual broker calls when an
authorized real-order path is available.

The live risk configuration checks positive sizing and polling parameters
and nonnegative configured execution costs. The USD sizing cap comes from
`ftmo.risk_sizing_limit_usd`, or `ftmo.risk_per_trade_limit` when the first
setting is absent or null. The loader returns `risk_per_symbol_usd_cap=None`
when both settings are absent or null. Check both position sizing and
account-loss enforcement when comparing training and broker behavior.

### Failure modes

- Moving only the checkpoint can leave its configuration, manifest, and
  feature normalization state unavailable.
- Providing data for a similarly named symbol can change bar history and
  feature values.
- A schema version or feature mismatch can prevent usable policy inference.
- A logged paper intent has no broker order ticket or confirmed fill.
- A mocked order call can verify adapter arguments and still leave broker
  connection and actual fills unmeasured.

## Worked example

The Tier A notebook implements a fixed strategy conforming to the
broker-neutral `LiveStrategy` protocol and consumes its typed directional
signal. It also resolves the live sizing cap from a synthetic training budget. It
runs without a terminal or robot.

```{toctree}
:hidden:

examples/live-paper-metatrader
```

## Tasks

- Read the [live status summary](../../operations/live-status.md) together
  with the source guards when checking the current implementation.
- Follow the [broker adapter guide](../../how-to/add_broker_adapter.md) for
  SDK boundaries, input mapping, and controlled test doubles.
- Review the [observation schema reference](../../reference/observation_schemas.md)
  and the [live and paper trading contract](../../reference/subjects/live-paper-metatrader.md)
  when investigating a startup issue.
- Use the [account and risk guide](../C_trading_risk_execution/account-state-risk-prop-constraints.md)
  for account floor, cap, and latch semantics in research.

## Contract

| Item | Contract | Source |
|---|---|---|
| Broker-neutral signal | `(symbol, LiveSignal)`, with buy, sell, hold, and none values | `live/runtime/contracts.py::LiveStrategy` |
| Saved config default | `model_path.resolve().parent.parent / "config.yaml"` | `live_trading_rl.py::resolve_run_config` |
| Normalization | Required files, schema and filename checks, config and state file hashes, and cache-hash equality | `live_trading_rl.py::resolve_feature_normalization_state` |
| Provider metadata | Input schema version matches the built live observation schema | `live/runtime/strategy.py::RLStrategyAdapter` |
| Exposure control | Live sizing settings and training per-trade cap validated together | `integrations/mt5/risk_configuration.py::load_live_risk_configuration` |
| RL real-order guard | Explicit capability check at robot construction | `integrations/mt5/robot/rl_robot.py::RLRobot` |
| Supplied risk manager | Training-equivalent account-loss guardrail capability is false | `integrations/mt5/domain/risk_manager.py::RiskManager` |

## Verify

- `tests/unit/live/test_live_entrypoint.py` covers model argument
  precedence, required saved config, hash links, and risk override validation.
- `tests/unit/live/test_rl_robot.py` covers default paper handling, no paper
  order calls, guardrail capability checks, and unsafe sizing or stop rejection.
- `tests/architecture/test_dependency_rules.py` checks that shared evaluation
  and live code stay broker-neutral.

## Limits and common mistakes

Paper logs describe signals and intended actions. A deployment record needs
the exact policy, resolved configuration, terminal/account context and
timestamps, and whatever independently observed order or execution evidence
is relevant to the claim. Broker behavior, risk parity, and profitability are
unmeasured in this guide.

Review initialization order when diagnosing a terminal connection.
The RL builder loads model, configuration, normalization, and risk settings,
then logs in and builds data sources before constructing the guarded robot.
Entering a command that later fails can still interact with the terminal.

## Change checklist

- Update the entry point, CLI documentation, and tests together when a
  configuration key or default changes.
- Keep broker SDK objects in the integration package and validate schema
  and config artifacts at their boundaries.
- Test paper behavior and rejected size, stop, and account-loss cases.
- Preserve the training-equivalent account-loss safety checks.
- Record any terminal validation separately with its actual scope.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `quantitative_trading_engineer`
