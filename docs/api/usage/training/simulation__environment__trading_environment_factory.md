# Training · `simulation.environment.trading_environment_factory`

This page contains 1 public callable records owned by `simulation.environment.trading_environment_factory`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `make_env`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Construct a configured trading environment and its feature/observation adapters.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.make_env` · **Source:** [simulation/environment/trading_environment_factory.py:538](../../../../simulation/environment/trading_environment_factory.py#L538)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars used by the simulation.
  features: Causal feature frame aligned with bars.
  cfg: Resolved run configuration.
  algo: Learning algorithm name used to select policy settings.
  reward: Reward implementation to construct.
  episodic: Whether episode boundaries reset account state.
  use_vae: Enable the configured VAE observation path.
  vae: Optional fitted VAE used by that path.
  pre_ny_by_date: Optional per-session pre-market context.
  obs_features_mmap: Optional memory-mapped observation feature file.
  tickbook: Optional tick-level execution data.
  arch: Optional encoder architecture identifier.
  ```

- **Returns:**

  ```text
  Configured Gymnasium trading environment.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = make_env(bars=..., features=..., cfg=..., algo=..., reward=..., episodic=..., use_vae=..., vae=..., pre_ny_by_date=..., obs_features_mmap=..., tickbook=..., arch=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`
