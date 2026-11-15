# Action schemas and parameterization

**Status:** Wave B draft
**Use this when:** You need to map a policy output to named decisions, compare action layouts, or preserve action meaning in a checkpoint.

## Summary and use this when

An action schema names and versions the meaning and order of policy output
coordinates. Configuration flags can add, remove, or replace coordinates, and
different layouts can have the same width. Decoding belongs at the environment
boundary; the schema makes that interpretation explicit.

- Use this guide when changing an action coordinate or optional control.
- Use it when reading a checkpoint or action log whose vector width appears
  compatible but whose flags may differ.
- Use the [observation guide](observations-and-masks.md) for policy inputs and
  eligibility masks.

## Key terms

- [Action schema](../../glossary.md)
- [Observation schema](../../glossary.md)
- [Trade setup](../../glossary.md)

## Explanation

### The rule

`decisioning.actions.build_action_schema` builds the versioned
`overlay-action-v2` coordinate list. The base layout is `intensity`, `stop`,
`risk`, `target`, and `exit`. Optional direction is inserted first; stop-loss
and take-profit modes are appended before `exit`; multi-target mode replaces
`target` with three target selections; simplex sizing adds `z1` and `z2` and
requires multi-target mode.

When setup-conditioned actions are configured,
`build_action_schema_from_config` delegates to
`decisioning.trade_setup.build_trade_setup_action_schema`. That layout starts
with `trade_setup`, followed by stop/risk/target controls and optional
management modes. If entry execution is enabled, it adds
`entry_execution`, `limit_offset_atr`, and `limit_ttl_bars` and uses the
`trade-setup-entry-execution-action-v2` version.

The separate `discrete-trading-v1` schema names the 20 categorical choices:
`hold`, 18 long/short risk/reward combinations, and `exit`. Semantic identity
comes from version, key, flags, and ordered coordinates together; width alone
is not sufficient.

### Why it works this way

Policies emit arrays, while evaluation and live consumers need stable meanings.
Named schemas provide a backend-neutral description before an adapter turns an
action into the environment representation. This keeps action meaning
inspectable without importing a learning backend into `decisioning`.

For example, a one-coordinate direction control and a one-coordinate stop-mode
control can each add one element to the base layout. Both resulting vectors
have the same width but different semantics. Persisting the names and flags
lets checkpoint validation reject that false match.

### Failure modes

- Inferring a schema from width misidentifies same-width layouts.
- Reordering or repurposing a coordinate under an existing version makes old
  checkpoints ambiguous.
- Setting simplex coordinates without multiple targets is invalid.
- Enabling agent entry execution without setup-conditioned actions is rejected
  by the configuration builder.
- Reading `target` from a multi-target schema without using its index mapping
  can select the wrong target coordinate.
- Decoding entry-execution values outside their declared normalized/raw
  semantics changes order type or limit controls.
- Treating a policy action as an accepted order or fill confuses model output
  with later execution state.

## Worked example

The [action schema notebook](examples/action-schemas-and-parameterization.ipynb)
compares same-width layouts and prints a setup-conditioned schema with
multi-target and entry-execution controls. It uses no market data and makes no
claim about policy quality.

```{toctree}
:hidden:

examples/action-schemas-and-parameterization
```

See the [subject contract reference](../../reference/subjects/action-schemas-and-parameterization.md)
and canonical [action schema reference](../../reference/action_schemas.md) for
full coordinate details.

## Tasks

- Follow [add an action schema](../../how-to/add_action_schema.md) when a new
  action meaning is required.
- Use [schema versioning guidance](../../how-to/schema_version_change.md) when
  a serialized coordinate or mask contract changes.
- Read the [action schema reference](../../reference/action_schemas.md) before
  interpreting model artifacts or action logs.

## Contract

| Item | Contract | Source |
|---|---|---|
| Overlay version | `overlay-action-v2` for scalar strategy controls | `decisioning/actions.py` |
| Setup overlay version | `trade-setup-overlay-action-v1`; execution extension is `trade-setup-entry-execution-action-v2` | `decisioning/trade_setup.py` |
| Discrete version | `discrete-trading-v1`, exactly 20 named categories | `build_discrete_trading_action_schema` |
| Coordinate order | Ordered names plus flag values define the layout | `ActionSchema.to_dict` |
| Simplex | Requires multi-target mode and adds two allocation coordinates | `build_action_schema` |
| Entry execution | Raw `entry_execution < 0` selects market; zero or above selects limit | `TradeSetupActionSchema.to_dict` |
| Limit offset | Unit value maps to the configured ATR-offset interval | `TradeSetupActionSchema.to_dict` |
| Limit TTL | Unit value maps to an integer bar count in the configured interval | `TradeSetupActionSchema.to_dict` |
| Config selection | Setup actions, optional controls, multi-target, simplex, and entry execution resolve the active schema | `build_action_schema_from_config` |

## Verify

- `tests/unit/decisioning/test_action_schema_config.py` checks config-derived
  schema selection and invalid flag combinations.
- `tests/unit/decisioning/test_trade_setup_contract.py` checks setup category
  and action contract behavior.
- `tests/integration/test_action_schema_contract.py` checks that action
  diagnostics and environment decoding use the same schema indices.
- `tests/unit/models/test_action_schema_checkpoint.py` checks saved schema
  compatibility during model handling.
- Research evidence: no result about learned policy quality is claimed here.

## Limits and common mistakes

- An action schema records the selected output interface. It does not prove
  that a policy was trained with the claimed code or configuration; inspect
  checkpoint and run metadata.
- Environment decoding defines how coordinates become requests. Broker fills,
  costs, and risk approval are separate contracts.
- This guide names current source behavior; it does not recommend any action
  layout for a research comparison.
- The notebook is a deterministic schema demonstration, not trading evidence.

## Change checklist

Before changing a schema, write down the semantic meaning, bounds, order, flags,
invalid-action behavior, and serialized identifier. Find every producer and
consumer that builds, persists, decodes, logs, or validates the action.

- Keep schema construction in `decisioning`; keep policy-to-environment
  conversion at the adapter boundary.
- Compare ordered names as well as width for every supported configuration.
- Update the version if coordinate meanings, order, categories, or bounds
  change in a way that affects stored actions.
- Preserve compatibility through an explicit migration or fail-fast check.
- Test simplex without multi-target mode and entry-execution configuration
  without setup actions as rejected states.
- Exercise decode/log parity for multi-target coordinate aliases and each
  optional management flag.
- Keep discrete categories named and ordered; do not insert a category under
  the existing version without evaluating saved-model compatibility.

## Review procedure

Build schemas for the default layout, two same-width flag combinations, and
each setup-conditioned optional layout. Compare the complete serialized
metadata, then round-trip a representative normalized action through the
matching decoder and audit logger. Verify checkpoint validation compares
version, key, ordered coordinates, and flags. A deterministic fixture checks
contract mechanics only; it cannot establish policy performance or execution
quality.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `ml_engineer`
