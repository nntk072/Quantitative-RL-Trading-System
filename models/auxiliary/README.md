# Auxiliary model components

`models/auxiliary/` provides auxiliary neural heads and losses, including
return-prediction and variational-autoencoder components. These modules attach
additional representations or objectives to an encoder; they do not own the
RL algorithm or the training-run lifecycle.

Keep tensor shapes, device behavior, and any target construction explicit.
Focused checks are in `tests/unit/models/` and `tests/unit/learning/`.
