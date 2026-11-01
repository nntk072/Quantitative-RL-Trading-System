# Training artifacts

`training/artifacts/` writes and aggregates per-run outputs. It records
configuration snapshots, training and evaluation manifests, schema metadata,
logs, per-seed artifacts, and summary reports.

Artifact identity must retain the effective configuration, source/data
identity, seed, and action/observation schemas needed for reproducibility and
checkpoint recovery. Keep writes in the shared artifact and run-lifecycle
contracts where possible. Focused tests are in `tests/unit/training/` and
`tests/unit/artifacts/`.
