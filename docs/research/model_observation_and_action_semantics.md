# Model observation and action semantics

This page describes what the configured trade-setup PPO receives and emits.
It is a source-and-configuration audit of the existing architecture, not
evidence that a setup has positive expectancy or that an action is executable
at a candidate-specific price.

## Candidate catalog and eligibility

[`decisioning/trade_setup.py`](../../decisioning/trade_setup.py) defines six
idea families across nine timeframes and two directions: 108 setup IDs plus
`NO_TRADE`. The environment adds a 109-element `trade_setup_mask`. The
no-trade element is always enabled; each setup element is enabled when its
mapped feature value at the decision row is finite and positive. The mask is
an eligibility signal, not a per-candidate price forecast.

For the selected overlay, the training-only opportunity census records 24
configuration-supported categories and 84 unsupported categories across
351,432 training decisions. Candidate and month/regime denominators and their
overlap caveats are in the
[opportunity census packet](https://github.com/nntk072/Quantitative-RL-Trading-System/tree/main/evidence/research/trade_setup_opportunity_census).
Support is highly uneven: supported candidate episode starts range from 3 for
long D1 standard-deviation signals to 24,413 for long M1 unretested-IFVG
signals. Episode starts are feature-state transitions, not independent trades.
This census counts feature contexts; it does not count hypothetical fills or
independent economic outcomes, and sparse categories do not support separately
trained candidate models.

## Historical observation streams

The `mtf_reasoning` encoder receives the environment's historical sequence
streams and account vector. Tensor feature widths depend on the resolved
feature configuration and data; they must be read from a run's observation
space or manifest, not inferred from this page. The configured window lengths
are:

| Stream | Window rows | Observation key | Mask key |
|---|---:|---|---|
| M1 | 60 | `seq` | `seq_mask` |
| M3 | 20 | `seq_m3` | `mask_m3` |
| M5 | 24 | `seq_m5` | `mask_m5` |
| M10 | 12 | `seq_m10` | `mask_m10` |
| M15 | 16 | `seq_m15` | `mask_m15` |
| M30 | 8 | `seq_m30` | `mask_m30` |
| H1 | 12 | `seq_h1` | `mask_h1` |
| H4 | 6 | `seq_h4` | `mask_h4` |
| D1 | 5 | `seq_d1` | `mask_d1` |

M1 history is session-scoped when session IDs are available. Higher-timeframe
windows use the last closed feature runs visible at the decision row, with
padding masks. Each available stream is encoded by a causal TCN. The reasoning
encoder adds timeframe embeddings, applies one cross-timeframe transformer
block, pools valid timeframe tokens, and appends the account embedding. The
default MTF reasoning latent is 128 market values plus a 32-value account
embedding. Actual available-stream count and input widths belong to each run's
resolved observation schema.

## Action and conditioning

The C overlay enables trade-setup and strategy actions and selects
`trade_setup_hybrid_v1`; its setup logits, continuous execution coordinates,
and auxiliary categorical execution logits share the policy latent. The
selected setup is an action category constrained by the current mask.
With the base action settings resolved by this overlay, the policy emits a
six-coordinate `Box` action (`[batch, 6]`):

| Coordinate | Policy representation |
|---|---|
| `trade_setup` | 109 categorical choices, including `NO_TRADE`, masked by eligibility |
| `stop` | continuous normalized choice decoded by environment rules |
| `risk` | continuous normalized choice decoded by environment rules |
| `target` | continuous normalized choice decoded by environment rules |
| `sl_mode` | four categorical mode choices |
| `exit` | two categorical mode choices |

The separate conditioned overlay uses
`trade_setup_conditioned_v1`: it selects the setup from the market latent, then
concatenates the selected setup's 32-value embedding with that latent for the
execution heads. The setup head emits 109 logits; execution coordinates still
use the same six-coordinate action schema. This is categorical conditioning. The embedding does not
encode a proposed entry quote/offset, a stop or target price, fill waiting
period, or candidate-specific path. The action schema's continuous stop/risk/
target coordinates are decoded by environment rules; they are not price-level
candidate forecasts.

## Evidentiary boundary

This audit establishes the source-defined catalog, mask construction, stream
windows, encoder composition, and two policy-factorization choices. It does
not establish source-event timestamps or signal lifetime, actual tensor widths
for every run, candidate-level fill probability or return, or correct
price-specific geometry. Those remain separate gates in
[feature causality and availability](feature_causality_and_availability.md),
the data contract, and execution-parity evidence. Keep the existing model as a
benchmark control; do not train a new challenger until those gates and a
matched comparison design pass.

## Recorded run-level shapes

The existing MTF run manifests and training logs record actual tensor sizes,
which are more specific than config window lengths. One MTF run records an M1
stream of `[60, 160]`, plus M3–D1 streams with 71 columns and row counts
`20, 24, 12, 16, 8, 12, 6, 5`. A separate MTF reasoning run records M1
`[60, 322]`, M3–D1 streams with 91 columns at those same configured row
counts, and a 109-element `thesis_mask` under
`thesis-overlay-action-v1`, which has 11 continuous action coordinates. This
is a distinct overlay/action contract from the configured C/D
`trade_setup_mask` policy; its 109-element width does not
establish the selected setup-policy schema. The MTF reasoning screen itself
had one seed and all three variants failed training survival and full-period
exposed test survival; it is descriptive negative architecture evidence, not
a ranking. These observations do not establish source-event times or
candidate price geometry.

The older selected matched-policy artifacts record a single M1 `[60, 746]`
stream and a 12-coordinate action schema. Their account observation vectors
are recorded as widths 6 and 10. The four additional coordinates are the
one-hot entry-state observation, which is the declared A4A/A4B treatment:
the preserved resolved configs differ only in `env.entry_state_observation`
(`false` for A4A, `true` for A4B). This is a single-factor visibility
contrast, not an unexplained configuration mismatch or an input-identical
comparison. It remains one seed and both arms failed the recorded risk gate,
so it does not establish a robust or deployable benefit.

The [run-artifact inventory](https://github.com/nntk072/Quantitative-RL-Trading-System/tree/main/evidence/research/model_observation_and_action_semantics)
preserves the source manifest/log hashes and recorded checkpoint references.
Across its declared roots it found no per-decision selected-setup trace and no
trace carrying proposed entry, stop, target, and order-expiry geometry. The
historical 100k replay likewise did not preserve per-decision setup choices.
This absence is limited to the inspected artifacts; it does not prove that a
trace was never stored elsewhere.
