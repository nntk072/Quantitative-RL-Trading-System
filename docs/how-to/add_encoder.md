# Add an encoder

An encoder maps the declared observation into a learned representation. It
does not choose the learning algorithm, action meaning, or trading rules.

1. Check the [registered model catalog](../model_variants.md) and
   [model architecture](../architecture/model_and_policy_architecture.md) for
   an existing implementation that fits.
2. Define required observation keys, tensor shapes, sequence ordering, mask
   handling, device behavior, and checkpoint constructor parameters.
3. Implement the encoder in `models/encoders/` and register its identifier in
   the lightweight architecture registry used during config resolution.
4. Ensure the model factory supports the same identifier; add shape, padding,
   finite-output, gradient, and save/load tests as applicable.
5. Add the encoder to a configured variant only when the algorithm/policy
   combination is implemented and tested. A registered ID alone is not proof
   of a selectable agent.
6. Update the model guide and generated catalog inputs, then verify catalog
   freshness.

Preserve old constructor names or add an explicit migration path when existing
checkpoints depend on them.
