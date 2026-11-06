# Versioned sequence feature-validity channels

`env.feature_validity_channels` is a default-off observation option for M1 and
completed higher-timeframe sequence inputs. When enabled, each sequence stores
all sanitized values followed by one finite-value indicator per feature.
Therefore a genuine zero is represented as `(value=0, valid=1)`, while a
missing or nonfinite value is `(value=0, valid=0)`. Timestep padding remains
zero in both channel blocks and the existing temporal mask is unchanged.

Default-off input keys, shapes, and the legacy values-only feature schema remain
unchanged. Enabled checkpoints identify a distinct schema version; reanalysis
fails closed when the configured and saved schemas differ. The environment,
configuration, schema, and training-artifact batch passed 79 tests. A separate
inference-only batch passed all four registered MTF encoders with widened
inputs; no model training or weight updates were performed. Scoped Ruff and
`git diff --check` pass on the existing GH200 allocation. The exact validation
outputs and current implementation/test source hashes are included.

This is representation infrastructure only. No policy was trained or evaluated
with these channels. VAE context remains on its separate schema, and no
economic, causal-profile, or historical-action-linkage claim follows from this
packet.
