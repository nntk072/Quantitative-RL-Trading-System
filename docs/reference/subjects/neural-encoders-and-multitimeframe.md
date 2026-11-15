# Neural encoders and multitimeframe observations contract

This page records the subject-specific contract at source revision
`c0d982f94ab9df8b2a9ddd013d2ae9a562573529`. The generated API pages describe callable signatures;
the entries below record cross-package meaning and validation obligations.

## Contract table

| Contract | Exact obligation | Source and focused test |
|---|---|---|
| Architecture IDs resolve through a registry | The learning builder asks the registry for an encoder class. An unknown ID is an error rather than a silent substitute. | `models/factory/encoder_registry.py::encoder_for`; `tests/unit/models/test_mtf_encoder_registration.py` |
| MTF branches are named pairs | The base seq/seq_mask pair is followed by configured higher-timeframe seq_x/mask_x pairs. An existing sequence without its mask is rejected. | `models/encoders/mtf.py::_MTF_STREAMS`; `tests/unit/models/test_encoders.py` |
| The M1 stream is mandatory | A Dict observation space without the base seq stream fails. The encoder derives feature width from each sequence Box and creates one branch per present stream. | `models/encoders/mtf.py::MTFEncoder.__init__`; `tests/unit/models/test_encoders.py` |
| Temporal branches encode valid suffixes | Valid lengths come from the row mask; _encode_valid_suffix sends valid sequence portions through causal temporal blocks and selects the final latent state. | `models/encoders/mtf.py::_CausalTCN.forward`; `tests/unit/models/test_mtf_efficient_encoders.py` |
| Account state joins after timeframe fusion | Per-stream latents are concatenated and fused, then concatenated with account_mlp output. The policy head receives one combined feature vector. | `models/encoders/mtf.py::MTFEncoder.forward`; `tests/unit/models/test_encoders.py` |

## Compatibility and evidence

When behavior or serialized meaning changes, inspect the producer, the
consumer, saved metadata, and the focused test together. The resolved config
and artifact identity are necessary to interpret an actual run. A toy notebook
or source-level test does not establish market quality, policy performance,
or survival qualification.

The source anchors above were read from the pinned baseline. Dirty-source-only
behavior in the active checkout remains unverified. See the
[subject guide](../../subjects/D_learning/neural-encoders-and-multitimeframe.md) and
[Tier A notebook](../../subjects/D_learning/examples/neural-encoders-and-multitimeframe.ipynb).
