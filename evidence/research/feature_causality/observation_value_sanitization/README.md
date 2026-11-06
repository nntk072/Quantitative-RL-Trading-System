# Observation value sanitization

The observation boundary previously called `numpy.nan_to_num` with only a NaN
replacement. NumPy therefore converted positive and negative infinity to the
largest finite `float32` magnitudes. A single invalid feature could dominate or
overflow a policy encoder.

A shared simulation-local helper now maps NaN, positive infinity, and negative
infinity to zero for the M1 sequence, completed higher-timeframe windows, and
both pre-NY VAE input paths. The change preserves observation keys, shapes,
temporal padding masks, and finite values. Focused regressions cover M1, MTF,
and VAE observations; 32 observation/schema tests pass, and scoped Ruff plus
`git diff --check` pass.

This prevents extreme invalid inputs. It does not provide per-feature
availability masks: zero-valued missing data can still collide with genuine
zero-valued features. That separate schema/model gate remains open. Exact output
and current production/test source hashes are included.
