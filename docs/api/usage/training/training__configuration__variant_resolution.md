# Training · `configuration.variant_resolution`

This page contains 2 public callable records owned by `training.configuration.variant_resolution`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `resolve_variant`

**Kind:** function · **Status:** stable · **Owner:** `training.configuration.variant_resolution`

**Purpose:** Resolve one variant into a fully explicit, validated configuration.

**Exact API:** {py:obj}`training.configuration.variant_resolution.resolve_variant` · **Source:** [training/configuration/variant_resolution.py:137](../../../../training/configuration/variant_resolution.py#L137)

**Inputs and outputs:**

- **Args:**

  ```text
  name: Name used to identify the requested file, artifact, or item.
  experiments_path: Path or filename identifying the experiments.
  steps: Number of environment or optimization steps to run.
  seeds: Items supplied for the seeds, in input order.
  vae_path: Path or filename identifying the vae.
  config_overrides: Items supplied for the config overrides, in input order.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [test fixture: `test_resolved_reasoning_treatment_uses_canonical_trade_setup_contract`](../../../../tests/unit/simulation/test_environment/test_trade_setup_factory_config.py#L115)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_resolved_reasoning_treatment_uses_canonical_trade_setup_contract() -> None:
    from training.configuration.variant_resolution import resolve_variant

    resolved = resolve_variant("rq_mtf_treatment_reasoning")

    overrides = set(resolved["overrides"])
    assert "env.trade_setup_actions=true" in overrides
    assert "ppo.policy_distribution=trade_setup_hybrid_v1" in overrides
```

2. [test fixture: `test_equity_log_growth_is_a_resolvable_variant_reward`](../../../../tests/unit/training/test_sustainable_growth_variant_resolution.py#L31)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                ],
            }
        ),
        encoding="utf-8",
    )
    resolved = resolve_variant("growth_probe", experiments_path=path)
    assert resolved["reward_mode"] == "equity_log_growth"
    assert "env.reward_mode=equity_log_growth" in resolved["overrides"]
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`

## `train_args`

**Kind:** function · **Status:** stable · **Owner:** `training.configuration.variant_resolution`

**Purpose:** Arguments for ``python -m training.runner.training`` for one seed.

**Exact API:** {py:obj}`training.configuration.variant_resolution.train_args` · **Source:** [training/configuration/variant_resolution.py:260](../../../../training/configuration/variant_resolution.py#L260)

**Inputs and outputs:**

- **Args:**

  ```text
  resolved: Key-value data used for the resolved.
  seed: Random seed used to make sampling reproducible.
  ```

- **Returns:**

  ```text
  Values returned by ``train_args``, in the declared order.
  ```

**Observed usage:**

1. [test fixture: `test_strategy_rungs_use_strategy_flag_not_name_override`](../../../../tests/unit/training/test_variant_resolver.py#L139)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_strategy_rungs_use_strategy_flag_not_name_override() -> None:
    resolved = resolve_variant("ladder_a0_flat_dist")
    assert resolved["strategy"] == "distribution"
    assert "strategy.name" not in _overrides_by_key(resolved)
    args = train_args(resolved, 42)
    assert args[args.index("--strategy") + 1] == "distribution"
```

2. [test fixture: `test_controls_run_declared_algo_and_arch`](../../../../tests/unit/training/test_variant_resolver.py#L148)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_controls_run_declared_algo_and_arch() -> None:
    sac = resolve_variant("ablation_sac_agent")
    assert (sac["algo"], sac["arch"]) == ("sac", "gru")
    transformer = resolve_variant("ablation_transformer_encoder")
    assert transformer["arch"] == "transformer"
    args = train_args(sac, 42)
    assert args[args.index("--algo") + 1] == "sac"
    assert args[args.index("--arch") + 1] == "gru"
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`
