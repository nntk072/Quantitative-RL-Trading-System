# VAE pre-NY input validity

This packet measures the current local US100 M1 training period against the
VAE's pre-NY sequence builder and separately inspects the configured
`data/pre_ny_sequences.npy` training input. It is an input-contract audit, not a
VAE quality result or policy comparison.

## Measured result

- The current raw M1 source yields 260 production pre-NY sequences for
  2024-12-30 through 2025-12-31. All 260 are shaped `(186, 5)` and finite.
- The configured window from 01:05 through 16:29 contains 185 aligned M5
  labels (01:05 through 16:25). The configured sequence length is 186, so the
  production builder prepends at least one all-zero row to every day. Missing
  source rows add more leading zero padding: 393 padded rows across the 260
  sequences.
- Eight dates have incomplete M1 coverage in the expected pre-NY window, with
  760 expected M1 rows absent. Three dates are missing 133 expected M5 labels.
  The audit makes no external calendar claim about shortened or incomplete days.
- The configured `.npy` dataset contains 44 finite sequences shaped `(186, 5)`.
  All 44 have leading all-zero rows (228 total, maximum 185), consistent with
  padding. Without validity bits, the audit cannot rule out valid zero-valued
  rows. The file has no date/session identity to link those sequences to the
  current raw M1 source.
- The VAE reconstruction loss applies summed MSE to all positions without a
  validity mask. Its training script randomly splits the sequence array 70/15/15
  without date keys or an explicit split generator.

## Disposition

VAE input validity and training provenance are measured, but the VAE path fails
the current acceptance contract. Do not enable or promote the registered VAE
candidate: padding is indistinguishable from valid zero-valued data in the
current loss, the training array is not linked to dated source sessions, and
the random split does not establish chronological train-only fitting. A future
VAE path needs a versioned validity-mask contract, dated sequence provenance,
and chronological fitting before any policy training or economic comparison.

## Reproduction

Run from the repository root with the ARM/GH200 project environment:

```bash
.venv/bin/python scripts/research/analysis/features/audit_vae_pre_ny_sequence_validity.py \
  --input data/training/US100.cash_M1_202412300105_202610162349.csv \
  --config config/vae.yaml \
  --start-date 2024-12-30 \
  --end-date 2025-12-31 \
  --output evidence/research/vae_input_validity/vae_pre_ny_sequence_validity.json
```

The report preserves per-date coverage, produced sequence and padding counts,
dataset identity, source hashes, and the bounded claim scope. `INPUT_SHA256SUMS`,
`SOURCE_SHA256SUMS`, and `SHA256SUMS` verify the exact inputs, implementation,
and packet outputs.
