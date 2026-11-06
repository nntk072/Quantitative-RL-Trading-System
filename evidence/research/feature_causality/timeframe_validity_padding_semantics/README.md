# Timeframe validity and padding semantics

## Result

The current-source joined test batch passes 119/119 tests across six modules.
The tests cover the M1 sequence and all eight HTF sequences: M3, M5, M10, M15,
M30, H1, H4, and D1. They verify closed-window visibility, observed all-zero
rows versus temporal padding, missing/nonfinite per-feature channels, empty HTF
streams, masked-value invariance, validity-width acceptance by the registered
MTF encoders, and versioned checkpoint schema mismatch behavior.

## Interpretation

This is tensor-boundary behavior for the tested current source. Temporal masks
distinguish left-padding and unavailable HTF rows from observed rows. When
`env.feature_validity_channels` is enabled, a finite value of zero has validity
1, while a missing or nonfinite value that reaches observation construction
has sanitized value zero and validity 0. The default remains off, preserving
the existing observation and checkpoint schema.

The feature-validity channel is based on finiteness at the observation boundary.
An upstream feature producer that already replaces warmup with finite zero
cannot be distinguished from a genuine finite zero by this channel. Producer
warmup classification for each timeframe/feature remains open. No policy was
trained or evaluated with the opt-in validity channels. VAE validity,
causal/economic acceptance, and historical decision linkage are outside this
packet's claim.

## Reproduction

The exact six-module command and environment are recorded in
`run_metadata.json`; its captured output is `focused_tests.log`. Current
implementation and test hashes are listed in `SOURCE_SHA256SUMS`.
