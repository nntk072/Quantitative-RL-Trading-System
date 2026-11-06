# Training · `artifacts.manifests`

This page contains 9 public callable records owned by `training.artifacts.manifests`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `action_schema_manifest`

**Kind:** function · **Status:** stable · **Owner:** `training.artifacts.manifests`

**Purpose:** Return declared coordinate names and flags, never infer from width.

**Exact API:** {py:obj}`training.artifacts.manifests.action_schema_manifest` · **Source:** [training/artifacts/manifests.py:160](../../../../training/artifacts/manifests.py#L160)

**Inputs and outputs:**

- **Args:**

  ```text
  env: Environment whose state is read or updated.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [test fixture: `test_build_agent_discrete_keeps_categorical_ent_coef`](../../../../tests/unit/models/test_ppo_log_std.py#L291)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_build_agent_discrete_keeps_categorical_ent_coef() -> None:
    from training.artifacts.manifests import action_schema_manifest

    env = make_env(continuous=False)
    model = build_agent(env, _ppo_cfg(), arch="tcn", algo="ppo")
    schema = build_discrete_trading_action_schema()
    assert model.ent_coef == pytest.approx(0.01)
    assert getattr(model.policy, "log_std", None) is None
    assert env.action_schema.to_dict() == schema.to_dict()
    assert getattr(model, "_action_schema") == schema.to_dict()
    assert action_schema_manifest(env) == schema.to_dict()
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`

## `action_space_width`

**Kind:** function · **Status:** stable · **Owner:** `training.artifacts.manifests`

**Purpose:** Return the action space width for logging.

**Exact API:** {py:obj}`training.artifacts.manifests.action_space_width` · **Source:** [training/artifacts/manifests.py:140](../../../../training/artifacts/manifests.py#L140)

**Inputs and outputs:**

- **Args:**

  ```text
  env: Environment whose state is read or updated.
  ```

- **Returns:**

  ```text
  Result of return the action space width for logging.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = action_space_width(env=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`

## `build_training_log`

**Kind:** function · **Status:** stable · **Owner:** `training.artifacts.manifests`

**Purpose:** Build the training_log.json dict from run results.

**Exact API:** {py:obj}`training.artifacts.manifests.build_training_log` · **Source:** [training/artifacts/manifests.py:38](../../../../training/artifacts/manifests.py#L38)

**Inputs and outputs:**

- **Args:**

  ```text
  seed: Random seed used to make sampling reproducible.
  mvp: Whether to enable or require the mvp.
  algo: Text or path value identifying the algo.
  arch: Text or path value identifying the arch.
  reward: Text or path value identifying the reward.
  timesteps: Numeric value used for the timesteps.
  train_bars: Market bar or price data used for build the training_log.json dict from run results.
  test_bars: Market bar or price data used for build the training_log.json dict from run results.
  test_m: Test m used by the operation described above.
  test_result: Key-value data used for the test result.
  environment_reward_mode: Text or path value identifying the environment reward mode.
  equity_log_growth_scale: Numeric value used for the equity log growth scale.
  train_result: Key-value data used for the train result.
  strategy: Strategy used to select or evaluate trades.
  strategy_actions: Whether to enable or require the strategy actions.
  action_space_width: Number specifying the action space width for this operation.
  observation_account_dim: Observation account dim used by the operation described above.
  observation_space_shapes: Items supplied for the observation space shapes, in input order.
  action_schema: Key-value data used for the action schema.
  observation_schema: Key-value data used for the observation schema.
  env_flags: Boolean or status values aligned with the input env flags.
  oos_role: Text or path value identifying the oos role.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = build_training_log(seed=..., mvp=..., algo=..., arch=..., reward=..., timesteps=..., train_bars=..., test_bars=..., test_m=..., test_result=..., environment_reward_mode=..., equity_log_growth_scale=..., train_result=..., strategy=..., strategy_actions=..., action_space_width=..., observation_account_dim=..., observation_space_shapes=..., action_schema=..., observation_schema=..., env_flags=..., oos_role=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`

## `entry_funnel_by_split`

**Kind:** function · **Status:** stable · **Owner:** `training.artifacts.manifests`

**Purpose:** Build separately labeled train and report-only test entry funnels.

**Exact API:** {py:obj}`training.artifacts.manifests.entry_funnel_by_split` · **Source:** [training/artifacts/manifests.py:14](../../../../training/artifacts/manifests.py#L14)

**Inputs and outputs:**

- **Args:**

  ```text
  train_result: Key-value data used for the train result.
  test_result: Key-value data used for the test result.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``dict[str, Any]`` values.
  ```

**Observed usage:**

1. [production caller: `aggregate_seed_results`](../../../../training/artifacts/aggregation.py#L182)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    aggregated["early_abort_reason"] = abort_reasons[0] if abort_reasons else ""
    aggregated["timesteps_completed"] = seed_results[-1]["model_num_timesteps"]

    first = seed_results[0]
    aggregated["entry_funnel_seed"] = int(first["seed"])
    aggregated["entry_funnel_by_split"] = entry_funnel_by_split(
        first.get("train_result"), first.get("test_result")
    )

    aggregated["oos_role"] = (
        "selection_acknowledged"
        if getattr(args, "allow_locked_oos_for_selection", False)
        else "final_report_only"
# … caller assertions omitted …
```

2. [production caller: `build_training_log`](../../../../training/artifacts/manifests.py#L123)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "test_fail_time": (
            str(test_result["fail_time"]) if test_result.get("fail_time") is not None else None
        ),
        "timestamp": datetime.now().isoformat(),
    }
    log_dict["entry_funnel_by_split"] = entry_funnel_by_split(train_result, test_result)
    if action_space_width is not None:
        log_dict["action_space_width"] = action_space_width
    if observation_account_dim is not None:
        log_dict["observation_account_dim"] = observation_account_dim
    if observation_space_shapes is not None:
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`

## `observation_account_dim`

**Kind:** function · **Status:** stable · **Owner:** `training.artifacts.manifests`

**Purpose:** Return the account observation dimension from the env's observation space.

**Exact API:** {py:obj}`training.artifacts.manifests.observation_account_dim` · **Source:** [training/artifacts/manifests.py:365](../../../../training/artifacts/manifests.py#L365)

**Inputs and outputs:**

- **Args:**

  ```text
  env: Environment whose state is read or updated.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``observation_account_dim``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = observation_account_dim(env=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`

## `observation_schema_manifest`

**Kind:** function · **Status:** stable · **Owner:** `training.artifacts.manifests`

**Purpose:** Return explicit account observation coordinate meanings.

**Exact API:** {py:obj}`training.artifacts.manifests.observation_schema_manifest` · **Source:** [training/artifacts/manifests.py:177](../../../../training/artifacts/manifests.py#L177)

**Inputs and outputs:**

- **Args:**

  ```text
  env: Environment whose state is read or updated.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [test fixture: `test_training_observation_manifest_records_trade_setup_mask_schema`](../../../../tests/unit/models/test_trade_setup_observation_schema.py#L37)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_training_observation_manifest_records_trade_setup_mask_schema() -> None:
    account_schema = SimpleNamespace(to_dict=lambda: {"version": "account-state-v1"})
    env = SimpleNamespace(
        observation_schema=account_schema,
        regime_observation_schema=None,
        trade_setup_observation_schema=trade_setup_observation_schema(),
    )

    manifest = observation_schema_manifest(env)

    assert manifest is not None
    assert manifest["version"] == "account-state-v1"
    assert manifest["trade_setup_observation"] == trade_setup_observation_schema()
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`

## `observation_space_shapes`

**Kind:** function · **Status:** stable · **Owner:** `training.artifacts.manifests`

**Purpose:** Return every observation branch shape for the run manifest.

**Exact API:** {py:obj}`training.artifacts.manifests.observation_space_shapes` · **Source:** [training/artifacts/manifests.py:383](../../../../training/artifacts/manifests.py#L383)

**Inputs and outputs:**

- **Args:**

  ```text
  env: Environment whose state is read or updated.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``list[int]`` values.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = observation_space_shapes(env=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`

## `sequence_feature_schema_manifest`

**Kind:** function · **Status:** stable · **Owner:** `training.artifacts.manifests`

**Purpose:** Return ordered model sequence coordinates from the effective environment.

**Exact API:** {py:obj}`training.artifacts.manifests.sequence_feature_schema_manifest` · **Source:** [training/artifacts/manifests.py:202](../../../../training/artifacts/manifests.py#L202)

**Inputs and outputs:**

- **Args:**

  ```text
  env: Environment whose state is read or updated.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = sequence_feature_schema_manifest(env=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`

## `training_protocol_manifest`

**Kind:** function · **Status:** stable · **Owner:** `training.artifacts.manifests`

**Purpose:** Persist the effective optimizer/reward/risk protocol for later reproduction.

**Exact API:** {py:obj}`training.artifacts.manifests.training_protocol_manifest` · **Source:** [training/artifacts/manifests.py:220](../../../../training/artifacts/manifests.py#L220)

**Inputs and outputs:**

- **Args:**

  ```text
  model: Model used for this operation.
  cfg: Run configuration used by this operation.
  args: Parsed command-line arguments for this operation.
  seed: Random seed used to make sampling reproducible.
  requested_steps: Number specifying the requested steps for this operation.
  algo: Text or path value identifying the algo.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [test fixture: `test_training_protocol_records_growth_scale`](../../../../tests/unit/training/test_sustainable_growth_variant_resolution.py#L159)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "ftmo": {},
            "constrained_rl": {"enabled": False},
        }
    )
    model = SimpleNamespace(n_envs=2, n_steps=4, num_timesteps=8, ent_coef=0.001)
    manifest = training_protocol_manifest(
        model=model,
        cfg=cfg,
        args=SimpleNamespace(reward="sweep", mvp=True, allow_locked_oos_for_selection=True),
        seed=50,
        requested_steps=8,
    )
    assert manifest["reward"]["mode"] == "equity_log_growth"
    assert manifest["reward"]["selector"] == "sweep"
    assert manifest["reward"]["equity_log_growth_scale"] == 25.0
    assert manifest["risk"]["eod_peak_trailing_dd_limit_usd"] == 10_000.0
    assert manifest["mvp_mode"] is True
# … caller assertions omitted …
```

2. [test fixture: `test_sac_training_protocol_uses_sac_fields_without_ppo_geometry`](../../../../tests/unit/training/test_sustainable_growth_variant_resolution.py#L195)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "constrained_rl": {"enabled": False},
        }
    )
    model = SimpleNamespace(n_envs=2, num_timesteps=8)

    manifest = training_protocol_manifest(
        model=model,
        cfg=cfg,
        args=SimpleNamespace(reward="dsr"),
        seed=50,
        requested_steps=8,
        algo="sac",
    )

    assert manifest["algorithm"] == "sac"
    assert manifest["sac"]["buffer_size"] == 64
    assert manifest["sac"]["entropy_coefficient"] == "auto"
    assert manifest["action_distribution"] == "squashed_diagonal_gaussian"
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`
