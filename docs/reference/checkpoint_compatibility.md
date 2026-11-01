# Checkpoint compatibility

A checkpoint is a serialized policy plus assumptions about its construction
and inputs. Loading weights successfully does not prove that an evaluation
environment supplies the same feature order, observation meaning, or action
decoder.

## Compatibility information to verify

| Contract | Why it matters |
|---|---|
| Algorithm and policy class | Determines parameter structure and distribution behavior. |
| Encoder identifier/class and constructor settings | Determines interpretation and shape of input branches. |
| Observation schema/version/coordinates | Defines input meaning, not only tensor width. |
| Action schema/version/coordinate order | Defines output interpretation and category ordering. |
| Feature names/order and normalization identity | Determines which information each input coordinate represents. |
| Resolved configuration and run/data identity | Reconstructs the execution and training assumptions. |

The code validates action and observation metadata in its supported load paths.
Missing metadata is accepted only by an explicitly documented loader path; it
must not silently be inferred for a new schema.

## Safe migration

1. Identify the exact serialized class path and schema metadata without
   rewriting the checkpoint.
2. Load the original with the architecture and dependency versions that wrote it.
3. Translate old metadata into the canonical in-memory contract explicitly.
4. Compare deterministic inference outputs on a fixed observation fixture.
5. Keep the original artifact and record migration provenance.

Do not rename an import path or schema string in place if serialized runs
depend on it. Retained setup-conditioned checkpoints use the current
trade-setup schema; see the
[trade-setup concept](../concepts/trade_setups.md).

## Code navigation

Schema manifests are created in `training/artifacts/`; validation and legacy
adapters live in `learning/rl/agent.py` and `learning/rl/checkpoint.py`.
