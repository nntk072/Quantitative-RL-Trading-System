# Configuration · `configuration_loader`

This page contains 4 public callable records owned by `configuration.configuration_loader`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `apply_overrides`

**Kind:** function · **Status:** stable · **Owner:** `configuration.configuration_loader`

**Purpose:** Apply ``key=value`` string overrides on top of an already-merged ``cfg``.

**Exact API:** {py:obj}`configuration.configuration_loader.apply_overrides` · **Source:** [configuration/configuration_loader.py:81](../../../../configuration/configuration_loader.py#L81)

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

1. [production caller: `load_config`](../../../../configuration/configuration_loader.py#L39)

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

**Exact API:** {py:obj}`configuration.configuration_loader.load_config` · **Source:** [configuration/configuration_loader.py:18](../../../../configuration/configuration_loader.py#L18)

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

1. [test fixture: `test_tier0_baselines_share_resolved_inputs_but_separate_seeds`](../../../../tests/integration/evaluation/test_matched_setup_baselines.py#L87)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_tier0_baselines_share_resolved_inputs_but_separate_seeds(tmp_path: Path) -> None:
    cfg = load_config(
        [
            "env.strategy_actions=true",
            "env.trade_setup_actions=true",
            "costs.use_tick_execution=false",
            "evaluation.periods_per_year=100",
        ]
    )
    bars, features = _synthetic_inputs()

    outputs = evaluate_tier0_setup_baselines(
        cfg,
        bars,
# … caller assertions omitted …
```

2. [test fixture: `test_tier0_baselines_can_persist_an_independent_subset`](../../../../tests/integration/evaluation/test_matched_setup_baselines.py#L195)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_tier0_baselines_can_persist_an_independent_subset(tmp_path: Path) -> None:
    cfg = load_config(
        [
            "env.strategy_actions=true",
            "env.trade_setup_actions=true",
            "costs.use_tick_execution=false",
            "evaluation.periods_per_year=100",
        ]
    )
    bars, features = _synthetic_inputs()

    outputs = evaluate_tier0_setup_baselines(
        cfg,
        bars,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/configuration`
- Generated package reference: {doc}`../../generated/configuration/index`

## `load_config_overlay`

**Kind:** function · **Status:** stable · **Owner:** `configuration.configuration_loader`

**Purpose:** Load one YAML mapping and reject list/scalar roots before merging.

**Exact API:** {py:obj}`configuration.configuration_loader.load_config_overlay` · **Source:** [configuration/configuration_loader.py:42](../../../../configuration/configuration_loader.py#L42)

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

1. [production caller: `load_config`](../../../../configuration/configuration_loader.py#L33)

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

2. [production caller: `apply_overrides`](../../../../configuration/configuration_loader.py#L142)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    # Key-name validation above prevents accidental new leaves, but a known
    # leaf can still receive the wrong CLI type (for example,
    # ``ppo.learning_rate=fast``). Validate the completed effective config
    # against the same defaults schema used for YAML overlays before callers
    # use it to construct an environment or launch a run.
    schema_container = OmegaConf.to_container(load_config_overlay(_DEFAULT_CFG), resolve=False)
    config_container = OmegaConf.to_container(cfg, resolve=False)
    if not isinstance(schema_container, Mapping) or not isinstance(config_container, Mapping):
        raise ValueError("configuration schema and effective config roots must be mappings")
    reject_unknown_keys(
        cast(Mapping[str, Any], config_container),
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/configuration`
- Generated package reference: {doc}`../../generated/configuration/index`

## `merge_config_overlay`

**Kind:** function · **Status:** stable · **Owner:** `configuration.configuration_loader`

**Purpose:** Validate a partial config against ``base`` and merge it once.

**Exact API:** {py:obj}`configuration.configuration_loader.merge_config_overlay` · **Source:** [configuration/configuration_loader.py:57](../../../../configuration/configuration_loader.py#L57)

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
