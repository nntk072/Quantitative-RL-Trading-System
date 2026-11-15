# Research analysis commands

This directory contains thin commands for repeatable research analysis. Reusable
behavior belongs in the owning Python package; commands should accept explicit
inputs and outputs and call those package APIs.

## Placement

- Feature investigations: `features/`
- Raw-data coverage and bar alignment: `market_data/`
- Observation and action contracts: `models/`
- Candidate, execution, and policy comparisons: `evaluation/`
- Provenance and result identity: `evidence/`

Put dates, run IDs, and dataset identities in generated manifests, not in
canonical command names. Prefer extending one parameterized command over adding
a one-run script. Do not duplicate feature construction, simulator behavior,
ledger calculations, or reporting logic in scripts.

## Current-source workflow

1. Identify the raw inputs using `evidence/research/data_identity/raw_data_manifest.json`.
2. Rebuild or verify the derived feature cache against the current source before
   using it. The retained v44 cache is a candidate and has not been certified
   compatible by the cleanup operation.
3. Run the relevant source, causality, quote-coverage, and execution checks with
   explicit output paths.
4. Record source/config/data hashes and period role with every regenerated
   artifact. Historical run outputs and data-derived evidence packets were
   removed during the 2026-11-15 clean restart.

Use the active
[research validation protocol](../../../docs/research/validation_protocol.md)
for scientific gates and the
[research methods](../../../docs/research/README.md) for claim boundaries.
