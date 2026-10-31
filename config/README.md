# Configuration

`config/` contains version-controlled behavior settings, model-variant
definitions, experiment matrices, and data-mode selections. It is the source of
runtime choices; documentation should explain these choices without copying
their full values into prose.

## Areas

| Path | Owns |
|---|---|
| `base/` | Default configuration and shared defaults |
| `features/` | Named feature and observation profiles |
| `variants/` | Per-variant settings, including risk configuration |
| `experiments.yaml` | Selectable experiment matrix and run defaults |
| `variant_catalog.yaml` | Reader-facing classification metadata for generated catalog |
| `data_modes/` | Data-source and cache mode selection |
| `experiment_runs/` | Declarative run selections and operational run inputs |
| `research/` | Research-specific settings kept separate from global defaults |

## Resolution rules

Configuration is loaded and validated through `configuration/`; a workflow
should not merge YAML independently. Resolve the effective settings for the
specific variant before comparing or launching it. The generated model catalog
contains explanatory metadata only; runtime values remain in canonical
configuration files.

When adding a setting, define its default and validation behavior, locate every
consumer, preserve compatibility where serialized runs rely on the old key,
and update the package guide and relevant reference. A cache-affecting setting
must participate in cache identity.

See [configuration concepts and resolution](../docs/config.md),
[variant catalog](../docs/model_variants.md), and the
[configuration package guide](../configuration/README.md).
