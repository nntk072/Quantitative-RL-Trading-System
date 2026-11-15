# Neural encoders and multitimeframe observations

**Status:** Wave D draft
**Use this when:** You need to trace named sequence and mask branches through reusable encoders before changing an architecture.

## Summary and use this when

Reusable encoders consume named observation tensors. The MTF encoder builds one causal temporal branch for every configured sequence, fuses the resulting vectors, and appends account-state embedding. Availability of a higher-timeframe bar is established before the encoder receives it; the encoder only respects the input masks and cannot repair upstream look-ahead.

- Start with the resolved configuration and the named input/output contracts.
- Follow one transition or fit path in source before interpreting a metric.
- Treat the linked notebook as a mechanics example using bundled synthetic data.

## Key terms

- [TCN](../../glossary.md)
- [Observation schema](../../glossary.md)
- [Action mask](../../glossary.md)
- [Availability time](../../glossary.md)
- [Lower/higher timeframe](../../glossary.md)

## Explanation

### Decision or learning boundary

Reusable encoders consume named observation tensors. The MTF encoder builds one causal temporal branch for every configured sequence, fuses the resulting vectors, and appends account-state embedding. Availability of a higher-timeframe bar is established before the encoder receives it; the encoder only respects the input masks and cannot repair upstream look-ahead.

The five source-backed contracts below identify where this subject crosses a
package boundary. Read them together: a policy output has meaning only under
the environment, schema, and run identity that produced it.

### 1. Architecture IDs resolve through a registry

The learning builder asks the registry for an encoder class. An unknown ID is an error rather than a silent substitute.

- Source: `models/factory/encoder_registry.py::encoder_for` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/models/test_mtf_encoder_registration.py`.
- Practical check: Record architecture ID in model provenance.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 2. MTF branches are named pairs

The base seq/seq_mask pair is followed by configured higher-timeframe seq_x/mask_x pairs. An existing sequence without its mask is rejected.

- Source: `models/encoders/mtf.py::_MTF_STREAMS` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/models/test_encoders.py`.
- Practical check: Keep each sequence and row mask together.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 3. The M1 stream is mandatory

A Dict observation space without the base seq stream fails. The encoder derives feature width from each sequence Box and creates one branch per present stream.

- Source: `models/encoders/mtf.py::MTFEncoder.__init__` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/models/test_encoders.py`.
- Practical check: Do not construct an MTF encoder from only HTF branches.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 4. Temporal branches encode valid suffixes

Valid lengths come from the row mask; _encode_valid_suffix sends valid sequence portions through causal temporal blocks and selects the final latent state.

- Source: `models/encoders/mtf.py::_CausalTCN.forward` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/models/test_mtf_efficient_encoders.py`.
- Practical check: Test padded, empty, and populated windows.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 5. Account state joins after timeframe fusion

Per-stream latents are concatenated and fused, then concatenated with account_mlp output. The policy head receives one combined feature vector.

- Source: `models/encoders/mtf.py::MTFEncoder.forward` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/models/test_encoders.py`.
- Practical check: Keep account coordinate identity and width with the checkpoint.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

## Worked example

The notebook demonstrates mask-aware extraction of the final valid row from fixed M1 and M5 arrays. It does not instantiate Torch or claim the numeric output equals a trained encoder.

Open the [Tier A notebook](examples/neural-encoders-and-multitimeframe.ipynb). It runs on CPU using
only deterministic values bundled in the cell. It neither trains nor evaluates
a market policy.

```{toctree}
:hidden:

examples/neural-encoders-and-multitimeframe
```

The [compact contract reference](../../reference/subjects/neural-encoders-and-multitimeframe.md) records
the exact source-facing obligations for maintainers.

## Tasks

- Inspect the named branches in the observation schema.
- Check source bar close time before using a higher-timeframe value.
- Keep mask polarity and sequence lengths aligned.
- Check registry ID and saved checkpoint architecture metadata.

## Contract

| Boundary | Required behavior | Source |
|---|---|---|
| Architecture IDs resolve through a registry | The learning builder asks the registry for an encoder class. | `models/factory/encoder_registry.py::encoder_for` |
| MTF branches are named pairs | The base seq/seq_mask pair is followed by configured higher-timeframe seq_x/mask_x pairs. | `models/encoders/mtf.py::_MTF_STREAMS` |
| The M1 stream is mandatory | A Dict observation space without the base seq stream fails. | `models/encoders/mtf.py::MTFEncoder.__init__` |
| Temporal branches encode valid suffixes | Valid lengths come from the row mask; _encode_valid_suffix sends valid sequence portions through causal temporal blocks and selects the final latent state. | `models/encoders/mtf.py::_CausalTCN.forward` |
| Account state joins after timeframe fusion | Per-stream latents are concatenated and fused, then concatenated with account_mlp output. | `models/encoders/mtf.py::MTFEncoder.forward` |

## Verify

For this subject, inspect the focused tests before changing a contract:

- `tests/unit/models/test_mtf_encoder_registration.py` — architecture ids resolve through a registry.
- `tests/unit/models/test_encoders.py` — mtf branches are named pairs.
- `tests/unit/models/test_encoders.py` — the m1 stream is mandatory.
- `tests/unit/models/test_mtf_efficient_encoders.py` — temporal branches encode valid suffixes.
- `tests/unit/models/test_encoders.py` — account state joins after timeframe fusion.

The notebook is a deterministic teaching check. A repository test is a
software check. Neither is an out-of-sample result or a claim of economic
performance. Keep those evidence categories separate in reports.

## Limits and common mistakes

- The notebook illustrates masks, not neural representation quality.
- Causal convolutions do not prevent an upstream availability error.
- No predictive or trading claim follows from an encoder shape check.

- Do not use a smoke run as evidence of a strategy effect.
- Do not select a model or threshold using the exposed 2026 reporting interval.
- Preserve invalid, negative, breached, no-trade, and incomplete outcomes.

## Change checklist

Before changing this behavior:

1. Inspect the named branches in the observation schema.
2. Check source bar close time before using a higher-timeframe value.
3. Keep mask polarity and sequence lengths aligned.
4. Check registry ID and saved checkpoint architecture metadata.
5. Update the relevant schema, caller, fixture, and focused test if the
   behavior or serialized meaning changes.
6. Record the source revision, resolved config, data identity, and artifact
   digest for any run used in a research claim.

## Review procedure

Read one source path and its directly connected test at the pinned revision.
Recheck any claim against the active checkout before relying on current behavior.
Use the notebook to inspect a tiny boundary case, then inspect actual run
artifacts separately if the question is about a trained policy. Record
mismatches rather than silently adapting a saved checkpoint or report.

## Maintainer note

- Verified source baseline: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Current dirty-source-only behavior is unverified by this page.
- Owner: `ml_engineer`.
- Notebook tier: A; synthetic, deterministic CPU example.
