# Curated API examples

This page gives short entry-point examples. Exact accepted fields and
compatibility rules remain in the linked domain reference and generated
AutoAPI.

## Load and validate configuration

```python
from configuration.configuration_loader import load_config

cfg = load_config("config/base/default.yaml")
```

Use the [configuration API](../api/domains/configuration.md) and
[configuration reference](configuration.md) for supported overrides and
validation behavior.

## Build and validate action schemas

```python
from decisioning.actions import build_action_schema

schema = build_action_schema()
manifest = schema.to_dict()
```

Schema flags alter action coordinates and checkpoint compatibility. See the
[trading API](../api/domains/trading.md) and
[action schema reference](action_schemas.md).

## Construct a feature cache

Use the project CLI and configuration path for ordinary runs; call lower-level
builders only when you can preserve the same input and fit-scope contracts.
The [data API](../api/domains/data.md),
[feature-cache how-to](../how-to/build_feature_cache.md), and
[cache identity reference](cache_and_schema_versions.md) describe those
boundaries.

## Build an agent

`learning.rl.agent.build_agent` accepts an environment and full OmegaConf
configuration. It selects PPO or SAC and a registered encoder, then stores
schema metadata on the model. SAC requires a continuous Box action space;
masked trade-setup distributions are PPO-only. See the
[models/learning API](../api/domains/models.md),
[agent builder](../../learning/rl/agent.py), and
[foundation guide](../learn/foundations.md).

## Read a transition

The public environment follows Gymnasium's `(observation, reward, terminated,
truncated, info)` step contract through its transition adapter. `info` carries
diagnostics and account/reporting fields; consult the exact
[transition API](../api/domains/runtime.md) and
[environment step map](../architecture/runtime/environment_step.md).
