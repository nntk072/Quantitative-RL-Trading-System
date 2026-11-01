# Configuration · `configuration_loader`

This page contains 4 public callable records owned by `configuration.configuration_loader`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `apply_overrides`

**Kind:** function · **Status:** stable · **Owner:** `configuration.configuration_loader`

**Purpose:** Apply ``key=value`` string overrides on top of an already-merged ``cfg``.

**Exact API:** {py:obj}`configuration.configuration_loader.apply_overrides` · **Source:** [configuration/configuration_loader.py:80](../../../../configuration/configuration_loader.py#L80)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg (DictConfig): Config to mutate in place; returned for convenience.
  overrides (list[str], optional): ``key=value`` strings applied after the merge.
  ```

- **Returns:**

  ```text
  Result of apply ``key=value`` string overrides on top of an already-merged ``cfg``.
  ```

**Observed usage:**

1. [production caller: `load_config`](../../../../configuration/configuration_loader.py#L38)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def load_config(
    overrides: list[str] | None = None,
    config_path: str | Path | None = None,
) -> DictConfig:
    cfg_path = Path(config_path) if config_path else _DEFAULT_CFG
    base = load_config_overlay(_DEFAULT_CFG)
    extra = load_config_overlay(cfg_path) if config_path else OmegaConf.create()
    # Merge over default.yaml: works both for Chain B/F variant *fragments*
    # (config/features_*_mtf.yaml only override the features.* keys they set,
    # everything else comes from defaults) and for full standalone configs.
    cfg = merge_config_overlay(base, extra)
    return apply_overrides(cfg, overrides)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/configuration`
- Generated package reference: {doc}`../../generated/configuration/index`

## `load_config`

**Kind:** function · **Status:** stable · **Owner:** `configuration.configuration_loader`

**Purpose:** Load config from ``config_path`` (the root config/base/default.yaml when None), then apply overrides.

**Exact API:** {py:obj}`configuration.configuration_loader.load_config` · **Source:** [configuration/configuration_loader.py:17](../../../../configuration/configuration_loader.py#L17)

**Inputs and outputs:**

- **Args:**

  ```text
  overrides (list[str], optional): ``key=value`` string overrides applied on top of the loaded YAML.
  config_path (str | Path, optional): YAML config file to load instead of ``config/base/default.yaml``.
      Use this to select a full configuration or a partial feature overlay.
  ```

- **Returns:**

  ```text
  Merged configuration with the requested overrides applied.
  ```

**Observed usage:**

1. [test fixture: `test_mtf_reasoning_research_overlay_is_opt_in_and_complete`](../../../../tests/unit/simulation/test_environment/test_trade_setup_factory_config.py#L72)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_mtf_reasoning_research_overlay_is_opt_in_and_complete() -> None:
    config = load_config(config_path="config/research/trade_setup_mtf_reasoning.yaml")

    assert config.env.strategy_actions is True
    assert config.env.trade_setup_actions is True
    assert config.env.agent_direction_control is False
    assert config.features.include_strategy_state is True
    assert config.features.entry_ideas.enabled is True
    assert config.agent.arch == "mtf_reasoning"
    assert config.ppo.policy_distribution == "trade_setup_hybrid_v1"
    assert config.ppo.actor_arch == "shared"
```

2. [test fixture: `test_mtf_reasoning_conditioned_overlay_is_opt_in_and_complete`](../../../../tests/unit/simulation/test_environment/test_trade_setup_factory_config.py#L85)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_mtf_reasoning_conditioned_overlay_is_opt_in_and_complete() -> None:
    config = load_config(config_path="config/research/trade_setup_mtf_reasoning_conditioned.yaml")

    assert config.env.strategy_actions is True
    assert config.env.trade_setup_actions is True
    assert config.agent.arch == "mtf_reasoning"
    assert config.ppo.policy_distribution == "trade_setup_conditioned_v1"
    assert config.ppo.trade_setup_conditioned.embedding_dim == 32
    assert config.ppo.trade_setup_conditioned.execution_hidden_dim == 128
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/configuration`
- Generated package reference: {doc}`../../generated/configuration/index`

## `load_config_overlay`

**Kind:** function · **Status:** stable · **Owner:** `configuration.configuration_loader`

**Purpose:** Load one YAML mapping and reject list/scalar roots before merging.

**Exact API:** {py:obj}`configuration.configuration_loader.load_config_overlay` · **Source:** [configuration/configuration_loader.py:41](../../../../configuration/configuration_loader.py#L41)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Path to the input file or directory.
  ```

- **Returns:**

  ```text
  Result of load one YAML mapping and reject list/scalar roots before merging.
  ```

**Observed usage:**

1. [production caller: `load_config`](../../../../configuration/configuration_loader.py#L32)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def load_config(
    overrides: list[str] | None = None,
    config_path: str | Path | None = None,
) -> DictConfig:
    cfg_path = Path(config_path) if config_path else _DEFAULT_CFG
    base = load_config_overlay(_DEFAULT_CFG)
    extra = load_config_overlay(cfg_path) if config_path else OmegaConf.create()
    # Merge over default.yaml: works both for Chain B/F variant *fragments*
    # (config/features_*_mtf.yaml only override the features.* keys they set,
    # everything else comes from defaults) and for full standalone configs.
    cfg = merge_config_overlay(base, extra)
    return apply_overrides(cfg, overrides)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/configuration`
- Generated package reference: {doc}`../../generated/configuration/index`

## `merge_config_overlay`

**Kind:** function · **Status:** stable · **Owner:** `configuration.configuration_loader`

**Purpose:** Validate a partial config against ``base`` and merge it once.

**Exact API:** {py:obj}`configuration.configuration_loader.merge_config_overlay` · **Source:** [configuration/configuration_loader.py:56](../../../../configuration/configuration_loader.py#L56)

**Inputs and outputs:**

- **Args:**

  ```text
  base: Base used by the operation described above.
  overlay: Key-value data used for the overlay.
  ```

- **Returns:**

  ```text
  Result of validate a partial config against ``base`` and merge it once.
  ```

**Observed usage:**

1. [production caller: `load_config`](../../../../configuration/configuration_loader.py#L37)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def load_config(
    overrides: list[str] | None = None,
    config_path: str | Path | None = None,
) -> DictConfig:
    cfg_path = Path(config_path) if config_path else _DEFAULT_CFG
    base = load_config_overlay(_DEFAULT_CFG)
    extra = load_config_overlay(cfg_path) if config_path else OmegaConf.create()
    # Merge over default.yaml: works both for Chain B/F variant *fragments*
    # (config/features_*_mtf.yaml only override the features.* keys they set,
    # everything else comes from defaults) and for full standalone configs.
    cfg = merge_config_overlay(base, extra)
    return apply_overrides(cfg, overrides)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/configuration`
- Generated package reference: {doc}`../../generated/configuration/index`
