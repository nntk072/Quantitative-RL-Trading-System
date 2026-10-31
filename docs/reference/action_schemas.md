# Action schemas

An action is a policy output plus a versioned interpretation contract. It is
not itself an order or a fill. The environment first decodes the action into a
trading intent, then validates eligibility, risk, and execution constraints.

## Supported forms

| Form | Typical role | Contract |
|---|---|---|
| Discrete | Legacy menu of holds, entries, and exits | A stable named category set; current trading menu contains 20 actions. |
| Scalar continuous | Minimal continuous-control adapters | One bounded scalar; meaning is declared by its provider. |
| Strategy overlay | Continuous controls for an established strategy action | A flag-derived, ordered coordinate schema with version `overlay-action-v2`. |
| Setup-conditioned overlay | Select a categorical setup plus continuous execution controls | Legacy serialized version `thesis-overlay-action-v1`; category mask and category ordering are part of the schema. |

## Discrete action menu

`discrete-trading-v1` contains 20 categories: `hold`, 18 combinations of
long/short × low/mid/high risk × low/mid/high reward-to-risk setting, and
`exit`. Indices are generated in this order. Do not hard-code an assumed
category index when a schema is available; use the category name.

## Continuous strategy overlay

The default coordinate order is:

```text
intensity, stop, risk, target, exit
```

Feature flags add coordinates without changing the meaning of existing
coordinates:

| Enabled option | Added coordinate(s) |
|---|---|
| Direction | `direction` is inserted first. |
| Stop management | `sl_mode` is appended before `exit`. |
| Target management | `tp_mode` is appended before `exit`. |
| Multiple targets | Replace `target` with `tp1_sel`, `tp2_sel`, `tp3_sel`. |
| Simplex partial sizing | Add `z1`, `z2` after the target selections. Requires multiple targets. |

The schema key identifies common combinations (for example, `5`, `8`, `10`,
`11`, or `12`) and falls back to a flag encoding for other supported
combinations. The key and ordered coordinate list should be stored together.

Coordinate values are normalized policy outputs. Their conversion into
direction, size/risk, stop selection, target selection, partial allocation,
and management behavior is defined by the configured decoder and catalogs.
Changing a decoder mapping changes action semantics even if the vector width
stays the same; such a change requires a schema/version update and parity
tests.

## Setup-conditioned overlay

This action form replaces a separate direction coordinate with one categorical
setup coordinate. Its current serialized name is `thesis`, and the action
schema is `thesis-overlay-action-v1`. The remaining optional coordinates are
the selected stop, risk, target(s), management modes, partial fractions, and
exit decision, according to configuration.

The categorical setup encodes one exact tuple:

```text
(entry idea, setup timeframe, direction)
```

The current catalog has six entry ideas, nine setup timeframes, two
directions, and one explicit no-trade category (109 categories total). The
eligibility mask is applied before selection and during PPO action evaluation;
invalid categories must have zero probability. See the
[trade-setup concept](../concepts/trade_setups.md).

## Schema and compatibility rules

1. Store schema version and ordered coordinate names with model artifacts.
2. Validate semantic metadata on checkpoint load; matching vector width is not enough.
3. Do not reorder or repurpose a coordinate under an existing version.
4. Treat historical `thesis*` values as serialized compatibility identifiers until an explicit migration is implemented.
5. Test decode/encode parity, masks, no-trade behavior, and every supported optional layout.

## Decision-provider boundary

Backend-neutral code represents outputs as a named `Decision` with an
`ActionSchemaRef`. Provider adapters convert that representation to the
environment's expected Gym action. This allows evaluation and live strategy
adapters to validate action meaning without importing PPO internals.

## Code navigation

The action contract is defined in `decisioning/actions.py` and
`decisioning/trade_setup.py`; `decisioning/thesis.py` is a legacy import shim.
Backend-neutral decision values are in `decisioning/contracts.py`. Environment interpretation is composed in
`simulation/environment/action_runtime.py` and related entry/position
components.
