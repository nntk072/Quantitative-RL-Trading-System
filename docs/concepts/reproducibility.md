# Reproducibility

Reproducibility means that a reader can reconstruct which inputs, settings,
code, model, execution assumptions, and evaluation period produced a result.
It does not mean that stochastic training will produce bit-identical weights
on every device.

A durable run record should identify:

1. source revision and resolved configuration;
2. dataset and feature-cache identity;
3. seeds and deterministic/stochastic action mode;
4. algorithm, encoder, observation/action schemas, and reward;
5. training budget and recovery events;
6. costs, quote/fill rules, account limits, and evaluation period;
7. checkpoint identity and ledger/report artifacts.

Reanalysis should operate on preserved ledgers and manifests where possible,
not silently regenerate different inputs. Missing provenance lowers the
strength of a claim; it must not be filled with guessed values.

See the [artifact guide](../modules/artifacts.md), and
[checkpoint reference](../reference/checkpoint_compatibility.md).
