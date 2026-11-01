# Configuration recipes

The single base source is `config/base/default.yaml`; experiment variants and
explicit overlays are layered on top. Always inspect the resolved config that
was saved with the run. The generated [configuration reference](../reference/configuration.md)
is the exact key/default inventory.

## Use the default smoke path

```bash
qrl-train train --help
qrl-train train --mvp
```

This checks software wiring and is not a research result. On shared compute,
follow the [operations guide](../operations/README.md) and use the matching
architecture venv.

## Choose a supported algorithm/encoder pair

Set the training algorithm and encoder using the supported runner/config
surfaces, then check the [model catalog](../model_variants.md). The agent
builder requires SAC actions to use continuous `Box`; trade-setup categorical
actions require PPO's supported masked distributions. MTF encoders require
MTF observations, and `tcn_regime` requires the regime branch.

## Enable causal multi-timeframe features

Choose source timeframes in feature configuration and the observation MTF
options together. Preserve completed-bar alignment, per-timeframe window
lengths, and validity masks. Inspect the output schema and cache identity before
training. See [MTF feature tutorial](../learn/tutorials/advanced/multi_timeframe_features.ipynb)
and [causality](../concepts/causality.md).

## Enable a research-only constrained objective

Review the optional `constrained_rl` keys in the reference and method
description before changing a run. Keep hard account guardrails enabled and
unchanged when isolating the dual objective. Record the cost definition and
budget with the run; see [constrained RL](../concepts/constrained_rl.md).

## Change safely

For a comparison, change one declared factor and keep data, seed protocol,
action schema, rollout geometry, execution costs, and evaluation path matched.
For a checkpoint-compatible schema change, follow the
[schema version guide](schema_version_change.md).
