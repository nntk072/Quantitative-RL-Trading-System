# Experiment design

An experiment compares declared alternatives to answer a research question.
A run is one execution of a resolved configuration and seed; a comparison
family defines the control, treatment, matched factors, and measured outcomes.

Before training, specify:

- the question and the one factor that differs;
- data identity and chronological period roles;
- algorithm, encoder, observation/action schemas, and reward;
- account limits, execution costs, rollout/update geometry, budget, and seeds;
- training diagnostics and evaluation outcomes that determine interpretation.

Training reward or throughput is not a substitute for frozen-checkpoint
replay. If multiple settings change together, the result may describe the
combined configuration but cannot isolate their individual effects. Exposed
test periods remain exploratory rather than confirmatory.

The generated [variant catalog](../model_variants.md) is classification
metadata. Resolved settings remain in configuration and run records.
