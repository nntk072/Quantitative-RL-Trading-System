# Model and encoder architectures

An encoder maps the observation branches declared by the environment into a
feature vector for a policy and, where used, a value head. The encoder does not
choose PPO or SAC, define the policy distribution, interpret an action, or
specify a reward. Those are separate choices recorded by a run configuration.

## Registered encoders

The IDs below come from `models/architecture_ids.py` and are resolved by
`models/factory/encoder_registry.py`. The generated
[variant catalog](../model_variants.md) reports which algorithm and encoder
pairs are selectable in the current experiment matrix; registration alone does
not make a combination a configured experiment.

| ID | Implementation | Inputs and temporal handling | Output and architecture | Current catalog status |
|---|---|---|---|---|
| `tcn` | `models.encoders.tcn.TCNEncoder` | `seq: (B,T,F)`, `seq_mask` or valid lengths, and `account: (B,A)`; left padding is excluded when lengths are supplied. | Causal dilated temporal blocks; last valid sequence state is projected to `latent_dim`, then concatenated with the account embedding. Defaults: 4 blocks, widths 128/128/256/256, kernel 3, latent 128. | PPO and SAC variants. |
| `lite_tcn` | `models.encoders.lite_tcn.LiteTCNEncoder` | Same single-sequence and account branches as `tcn`. | Depthwise-separable causal blocks with default dilations 1/4/10; latent 128 plus account embedding. | Registered; no selectable matrix variant currently. |
| `tcn_regime` | `models.encoders.tcn_regime.TCNRegimeEncoder` | `seq`, `account`, plus `regime` and `regime_mask`; the regime branch contains the configured completed-D1 coordinates. | Extends the TCN output with a 16-value masked regime embedding. An all-invalid regime mask produces a zero regime embedding. | PPO variant. |
| `gru` | `models.encoders.gru.GRUEncoder` | `seq`, optional valid-length metadata, and `account`. Default sequence length is 128. | Two-layer unidirectional GRU by default; the last valid hidden state is projected to 128 values and joined with the account embedding. | PPO and SAC variants. |
| `transformer` | `models.encoders.transformer.TransformerEncoder` | `seq`, optional valid-length metadata, and `account`. | Transformer encoder with an upper-triangular future mask; the final valid token is projected to the latent width and joined with account features. Defaults: width 128, 4 heads, 2 layers. | PPO variant. |
| `mtf` | `models.encoders.mtf.MTFEncoder` | M1 `seq` plus any declared timeframe sequence/mask pairs and `account`. | A causal TCN branch processes each stream; projected branch outputs are concatenated, normalized, and fused to one latent, then joined with the account embedding. | PPO variant. |
| `mtf_reasoning` | `models.encoders.mtf_reasoning.MTFReasoningEncoder` | Same available sequence/mask streams as `mtf`. | Causal TCN tokens receive timeframe embeddings and pass through one cross-timeframe Transformer block. Invalid streams are excluded from attention pooling. | PPO variant. |
| `mtf_shared_tcn_reasoning` | `models.encoders.mtf_shared_tcn_reasoning.SharedTCNMTFReasoningEncoder` | Requires all nine M1/M3/M5/M10/M15/M30/H1/H4/D1 sequence and mask pairs, plus account state. | Per-stream feature adapters feed one shared causal TCN. M1 and higher-timeframe tokens are pooled with masked cross-timeframe attention. Encoder provenance records the stream map and architecture settings. | Registered; no selectable matrix variant currently. |
| `mtf_m1_tcn_htf_lite_reasoning` | `models.encoders.mtf_m1_htf_lite_reasoning.M1TCNHTFLiteReasoningEncoder` | Requires the same nine streams, masks, and account state. | A dedicated M1 TCN is combined with per-HTF latest-valid state, masked mean, and latest-minus-previous summaries, then cross-timeframe attention. | Registered; no selectable matrix variant currently. |
| `mtf_m1_tcn_htf_snapshot_reasoning` | `models.encoders.mtf_m1_htf_snapshot_reasoning.M1TCNHTFSnapshotReasoningEncoder` | Requires the same nine streams, masks, and account state. | A dedicated M1 TCN is combined with one latest-valid snapshot token per available higher timeframe, then cross-timeframe attention. | Registered; no selectable matrix variant currently. |

The normal single-stream output width is `latent_dim + ACCOUNT_EMB_DIM` (160
with the default 128-value latent and 32-value account embedding).
`tcn_regime` adds its 16-value regime embedding. These widths are implementation
details; resolved observation/action schemas and checkpoint metadata remain the
compatibility contract.

## Model concepts and compatibility

Keep these concepts distinct:

| Concept | Meaning | Owner |
|---|---|---|
| Encoder | Maps observation tensors to latent policy features. | `models/encoders/`, `models/factory/` |
| Algorithm | Optimizer/update family such as PPO or SAC. | `learning/rl/` |
| Policy and distribution | Maps latent features to action probabilities or parameters. | `learning/rl/`, policy/distribution modules |
| Observation schema | Names, order, shape, dtype, mask, and meaning of inputs. | `decisioning/`, `simulation/environment/` |
| Action schema | Ordered outputs and their semantic decoding. | `decisioning/` |
| Reward | Training objective computed by the environment. | `simulation/`, `training/` |
| Variant | Resolved algorithm, encoder, schemas, reward, strategy, and risk settings for an experiment. | `experiments/variants/` |

`LegacyTCNEncoderV1` is a checkpoint-loading implementation selected by
legacy metadata; it is not one of the current architecture IDs. Preserve
`models/encoders/core.py` as a compatibility export while retained checkpoints
refer to that module path. Schema or constructor changes require compatibility
metadata and deterministic load/action parity checks; tensor width alone is
not sufficient.

## Configuration, devices, and evidence

The default encoder is selected by `agent.arch`; per-encoder parameters live in
`config/base/default.yaml` and experiment overlays. The generated
[configuration reference](configuration.md) lists the actual defaults.
Architecture-specific training benchmarks and their scope are recorded in the
[encoder comparison](../research/encoder_architecture_comparison.md); those
measurements do not establish comparative trading performance.

Torch device and precision selection belongs to `compute/` and the training
runtime, not to an encoder ID. Validate the exact observation schema, forward
shape, masks, gradients, serialization, and device/dtype behavior with the
focused tests in `tests/unit/models/` and the policy integration tests in
`tests/unit/learning/`.
