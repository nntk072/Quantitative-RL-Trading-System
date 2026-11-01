# Configuration API

Configuration is the canonical source for user-visible run behavior. The `configuration/` domain loads the base YAML, applies explicit overrides, validates the resolved tree, and exposes typed access to downstream owners.

## Contract and lifecycle

A run should have one resolved configuration snapshot. Load and validate it before preparing data or constructing the environment; persist the resolved form with the run manifest. Downstream code should read configured values through the configuration object (`cfg.<path>`), not maintain a parallel default in a CLI or helper. Validation errors should name the key and expected constraint so bad runs fail before expensive work begins.

When adding a setting, add it to the canonical YAML, document its type/default/meaning, and test both accepted and rejected values. Treat renames and semantic changes as compatibility changes because old experiment manifests may contain the previous key.

## Example

Load the canonical configuration and apply a typed CLI-style override before constructing the run:

```python
from configuration.configuration_loader import load_config

cfg = load_config(overrides=["training.mode=mvp"])
print(cfg.training.mode)
```

## Entry points

The loader and schema are the supported entry path. Generated API documents signatures and validation helpers; the [configuration guide](../../modules/configuration) explains project conventions and the [configuration reference](../../reference/configuration) lists the tree. For complete run provenance, see [training and experiments](../../framework/training_and_experiments).

{doc}`Generated configuration API <../generated/configuration/index>`
