# Trading API

Trading contracts define account state, orders, positions, risk approval, execution, and transition behavior. Decisioning defines the versioned observation/action interface, while `TradingEnv` composes those contracts into a Gymnasium step lifecycle.

## Transition and ownership

An action is an intent request, not an order fill. The environment advances the market and protects existing positions according to its transition ordering, decodes and validates the new intent, applies risk and execution rules, updates account state, computes reward, and returns the next observation plus diagnostic `info`. The `info` mapping is the supported observable diagnostics interface; underscore-prefixed environment attributes are implementation details.

Order geometry (entry, stop, target) and sizing are separate decisions. The risk contract determines permitted exposure from the geometry and account limits. Execution adds modeled costs and fill behavior. Simulation results describe this model, not a broker guarantee.

## Example

The supported Gymnasium interface returns the next observation, reward, both episode-end flags, and transition diagnostics:

```python
observation, reward, terminated, truncated, info = env.step(action)
print(info["equity"], info["position"], info["entry_rejected_total"])
```

Use the public `info` mapping for diagnostics; do not depend on underscore-prefixed environment attributes.

## Extension and compatibility

Use versioned observation/action schemas when policy-facing semantics change. Add tests at contract boundaries: invalid intents, risk rejection, fills, stop/target ordering, accounting, and transition equivalence. Preserve live/training risk alignment when changing limits.

Read [trading and simulation](../../framework/trading_and_simulation), [risk and account limits](../../concepts/risk_and_account_limits), [action schemas](../../reference/action_schemas), and [one environment step](../../learn/tutorials/04_environment.ipynb). Generated references: {doc}`trading <../generated/trading/index>`, {doc}`decisioning <../generated/decisioning/index>`, and {doc}`simulation <../generated/simulation/index>`.
