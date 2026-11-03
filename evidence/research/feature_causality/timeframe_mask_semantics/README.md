# Timeframe padding and validity-mask semantics

The initial focused audit passes 38 selected cases across M1/session-window
construction, closed timeframe windows, all nine sequence streams, the base
MTF reasoning encoder, and the three efficient reasoning encoders. A follow-up
versioned the legacy MTF empty-stream correction and passes a 66-test integration
batch covering encoder behavior, registration, checkpoint round-trip, env
construction, and catalog resolution. It verifies:

- left padding has a zero validity mask;
- an unavailable closed-candle window has an all-zero mask;
- a real candle whose feature values are all zero remains marked valid;
- current reasoning encoders ignore payload values when an HTF mask is empty;
- `mtf_empty_stream_masked_v1` ignores payloads for any stream with no valid rows;
- the historical `mtf` identifier still resolves to its original encoder, while
  the new encoder keeps identical parameter names and shapes for weight
  initialization and records the changed semantics under a distinct ID;
- masked padding cannot influence the tested encoder outputs, while earlier
  valid history can.

This is a timestep-mask audit, not a full warmup audit. In
`observation_runtime.py`, feature NaNs are converted to zero separately from
the candle-row mask, so a real candle row can have zero-filled warmup values
without a per-feature validity mask. That remains open in the broader Stage D
gate. The compatibility `mtf` encoder retains its historical all-empty branch
behavior for old checkpoints; new work can select the explicitly versioned
`mtf_empty_stream_masked_v1` architecture to zero unavailable stream tokens.
This correction does not add per-feature warmup masks or assert economic benefit.

The tests use synthetic inputs and current code. They prove encoder input-mask
behavior, registration, parameter-shape compatibility, and the selected PPO
checkpoint round-trip, not economic benefit or equivalence of a trained
historical policy under the corrected semantics. Exact output and current
source/test hashes are recorded in
`run_metadata.json` and `SHA256SUMS`.

Reproduce inside an existing ARM64/GH200 allocation using the commands in
`run_metadata.json`.
