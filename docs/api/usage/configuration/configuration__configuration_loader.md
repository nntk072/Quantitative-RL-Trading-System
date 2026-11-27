# Configuration · `configuration_loader`

This page contains 4 public callable records owned by `configuration.configuration_loader`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `apply_overrides`

**Kind:** function · **Status:** stable · **Owner:** `configuration.configuration_loader`

**Purpose:** Apply ``key=value`` string overrides on top of an already-merged ``cfg``.

**Exact API:** {py:obj}`configuration.configuration_loader.apply_overrides` · **Source:** [configuration/configuration_loader.py:95](../../../../configuration/configuration_loader.py#L95)

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

1. [test fixture: `test_configuration_override_rejects_non_mapping_default_schema`](../../../../tests/unit/configuration/test_configuration_helpers.py#L58)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_configuration_override_rejects_non_mapping_default_schema(monkeypatch) -> None:
    import configuration.configuration_loader as loader

    monkeypatch.setattr(loader, "_load_default_config", lambda: OmegaConf.create([]))
    config = OmegaConf.create({"ppo": {"learning_rate": 0.001}})

    with pytest.raises(ValueError, match="schema and effective config roots must be mappings"):
        apply_overrides(config, ["ppo.learning_rate=0.01"])
```

2. [production caller: `load_config`](../../../../configuration/configuration_loader.py#L51)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def load_config(
    overrides: list[str] | None = None,
    config_path: str | Path | None = None,
) -> DictConfig:
    cfg_path = Path(config_path) if config_path else None
    base = _load_default_config()
    extra = load_config_overlay(cfg_path) if cfg_path is not None else OmegaConf.create()
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

**Exact API:** {py:obj}`configuration.configuration_loader.load_config` · **Source:** [configuration/configuration_loader.py:30](../../../../configuration/configuration_loader.py#L30)

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

**Exact API:** {py:obj}`configuration.configuration_loader.load_config_overlay` · **Source:** [configuration/configuration_loader.py:54](../../../../configuration/configuration_loader.py#L54)

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

1. [test fixture: `test_configuration_overlay_and_override_reject_invalid_roots`](../../../../tests/unit/configuration/test_configuration_helpers.py#L38)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_configuration_overlay_and_override_reject_invalid_roots(tmp_path) -> None:
    scalar = tmp_path / "scalar.yaml"
    scalar.write_text("- one\n", encoding="utf-8")
    with pytest.raises(ValueError, match="overlay root must be a mapping"):
        load_config_overlay(scalar)

    with pytest.raises(ValueError, match="base and overlay roots must be mappings"):
        merge_config_overlay(OmegaConf.create([]), {})  # type: ignore[arg-type]
```

2. [production caller: `_load_default_config`](../../../../configuration/configuration_loader.py#L24)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def _load_default_config() -> DictConfig:
    checkout_default = Path(__file__).resolve().parents[1] / "config" / "base" / "default.yaml"
    if checkout_default.is_file():
        return load_config_overlay(checkout_default)
    packaged_default = files("configuration").joinpath("_resources", "default.yaml")
    with as_file(packaged_default) as default_path:
        return load_config_overlay(default_path)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/configuration`
- Generated package reference: {doc}`../../generated/configuration/index`

## `merge_config_overlay`

**Kind:** function · **Status:** stable · **Owner:** `configuration.configuration_loader`

**Purpose:** Validate a partial config against ``base`` and merge it once.

**Exact API:** {py:obj}`configuration.configuration_loader.merge_config_overlay` · **Source:** [configuration/configuration_loader.py:69](../../../../configuration/configuration_loader.py#L69)

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

1. [test fixture: `test_configuration_overlay_and_override_reject_invalid_roots`](../../../../tests/unit/configuration/test_configuration_helpers.py#L41)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_configuration_overlay_and_override_reject_invalid_roots(tmp_path) -> None:
    scalar = tmp_path / "scalar.yaml"
    scalar.write_text("- one\n", encoding="utf-8")
    with pytest.raises(ValueError, match="overlay root must be a mapping"):
        load_config_overlay(scalar)

    with pytest.raises(ValueError, match="base and overlay roots must be mappings"):
        merge_config_overlay(OmegaConf.create([]), {})  # type: ignore[arg-type]
```

2. [production caller: `load_config`](../../../../configuration/configuration_loader.py#L50)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def load_config(
    overrides: list[str] | None = None,
    config_path: str | Path | None = None,
) -> DictConfig:
    cfg_path = Path(config_path) if config_path else None
    base = _load_default_config()
    extra = load_config_overlay(cfg_path) if cfg_path is not None else OmegaConf.create()
    # Merge over default.yaml: works both for Chain B/F variant *fragments*
    # (config/features_*_mtf.yaml only override the features.* keys they set,
    # everything else comes from defaults) and for full standalone configs.
    cfg = merge_config_overlay(base, extra)
    return apply_overrides(cfg, overrides)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/configuration`
- Generated package reference: {doc}`../../generated/configuration/index`
