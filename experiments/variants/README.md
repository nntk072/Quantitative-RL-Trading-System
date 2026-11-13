# Training variant resolution

This package resolves model and configuration factors into validated training
settings. It owns the configured model matrix and its available algorithms,
encoders, risk controls, and observation/action options.

This is distinct from the reusable **research component library** in
[`config/research/experiments.yaml`](../../config/research/experiments.yaml).
A research component is an implementation that a scientific experiment can
reuse; a training variant is the effective configuration passed to a model
runner. One experiment may select several training variants, and multiple
experiments may select the same implementation without duplicating code.

Neither catalog is a separate hyperparameter source. Effective settings,
source identity, model identity, and resolved configuration are frozen into
the run manifest. Preserve run provenance when changing how variants resolve.

The generated [model catalog](../../docs/model_variants.md) and
[`tests/unit/experiments/`](../../tests/unit/experiments/) cover the public
resolver and its compatibility contract.
