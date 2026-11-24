# Self-supervised learning

## Purpose

Prepare pre-New-York OHLCV sequences and load the VAE used by the
self-supervised feature path.

## Public API

`learning.self_supervised.vae_pre_ny` provides `build_pre_ny_by_date` and
`load_vae_from_checkpoint`.

## Invariants

- Sequence construction uses only the supplied minute bars and the documented
  broker-local 01:05–16:29 window.
- Each day's sequence is padded or truncated to the requested length and
  preserves the requested feature width.
- Checkpoint loading reads the configured model state; it does not fit the
  model on evaluation data.
