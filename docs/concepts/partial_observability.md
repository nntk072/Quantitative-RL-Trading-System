# Partial observability in trading

## Why an observation is not the market state

The market's next move is not fully determined by the features visible to a
policy. A finite bar window omits latent order flow, participant intent, and
many exogenous causes. Even a perfectly implemented feature set therefore
defines a partially observed decision problem, rather than exposing a complete
state.

The repository supplies a time window plus account/position state and optional
regime or eligibility branches. A sequence encoder can summarize dependencies
inside that window; it cannot infer the missing future or make a feature
causal. Masks identify valid sequence values and eligible categories. Do not
replace an invalid masked value with a meaningful zero without retaining the
mask.

## A practical model

Let \(x_t\) denote the hidden market state and \(o_t\) the observation. The
policy acts on \(o_t\) (and its encoded history), not directly on \(x_t\):

\[
x_t\rightarrow o_t\rightarrow a_t\rightarrow x_{t+1},\qquad
o_{t+1}\sim O(\cdot\mid x_{t+1}).
\]

For this project, the observation construction is explicit and schema-bound.
The agent builder validates optional schema metadata when loading compatible
checkpoints. More input dimensions alone do not establish better information:
features must be causal, fit only on the permitted training data, and have
documented units and validity.

## What sequence models contribute

TCNs, GRUs, Transformers, and multi-timeframe encoders are alternative ways to
compress observed histories. They change inductive bias and compute, not the
information boundary. A TCN uses causal convolutions; a GRU updates a recurrent
hidden state; a Transformer uses attention over a finite input window; an MTF
encoder fuses aligned windows from several timeframes. Architecture choice is
an experimental factor and must not be selected using locked OOS results.

See [sequence model foundations](sequence_models.md),
[causality](causality.md), and the
[observation contract](../reference/observation_schemas.md).

## Limitations to state in a result

- An observation schema describes supplied inputs, not complete state.
- A mask records validity or eligibility; it does not prove that a signal is
  useful.
- A learned representation can exploit artifacts in the training distribution.
- Historical evaluation does not prove performance under future market,
  broker, or execution conditions.
