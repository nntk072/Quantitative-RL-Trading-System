# Current-source A4 checkpoint input schema disposition

## Result

The A4A checkpoint was not evaluated by current source. Replay stopped at the
sequence-feature schema guard before policy inference, so this packet contains
no current-source trade or performance result. A4B was not attempted after the
A4A guard failure.

The saved run manifest and checkpoint both declare a sequence input width of
746. Current source selects 724 coordinates from the reconstructed training
feature frame. The saved schema contains 23 structural raw fields, including
price levels, that the current observation selector removes from the normalized
policy sequence;
the current selector also excludes `datetime`, which is absent from the saved
schema. The current selector's ordered feature hash therefore differs. This is
a real checkpoint-input contract change, not a stop-menu setting that can be
overridden without changing model inputs.

## Decision

Do not bypass the sequence guard or reinsert raw structural price levels into
the current policy observation path. The current implementation excludes those
raw fields before model normalization. A faithful historical replay is already
available from the pinned training source in
[`../README.md`](../README.md); it remains the authority for the bounded
historical checkpoint result. Current-source same-policy replay is a bounded
no-go because the checkpoint's input coordinates do not match the current
policy contract. Full-ledger repeatability remains open and is not claimed by
this disposition.

## Reproduction and evidence

The A4A attempt used the saved run config, manifest, and checkpoint, the
reconstructed train-only feature snapshot, stochastic actions with seed 50,
and the current reanalysis CLI. It used the existing GH200 allocation and
stopped before rollout at the sequence-schema validation. The attempt log and
the schema-width/coordinate diagnostic are retained beside this README.

The feature snapshot file SHA-256 is
`e9e68584b2360d368c46f15432b82e1acb33913ce36fac660000ead65179ef0b`; its
assembled training-frame digest remains
`696cff0bef5ecea1b3d872d645752a28bc40fb8a862ee641084b903e89419717`. These
identify the training frame only. They do not establish full-cache bytes,
testing-feature identity, or complete raw-tick identity.
