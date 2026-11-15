# Research evidence status

## Clean restart status

Historical run outputs, logs, superseded caches, and data-derived research
packets were removed on 2026-11-15 to restart from the current implementation
and retained raw dataset. No historical A4A/A4B metric or old derived-dataset
finding is carried forward as a current result.

The repository currently retains the raw-data identity manifest at
[`evidence/research/data_identity/raw_data_manifest.json`](../../evidence/research/data_identity/raw_data_manifest.json).
That manifest establishes byte identity for the retained CSV files only. It
does not establish that the retained feature cache is compatible with the
current source, and it is not experimental evidence.

## Current scientific status

No refreshed data audit, simulator reconciliation, policy training, matched
baseline, or research result is asserted by this report. Those outputs must be
regenerated under the active
[research validation protocol](../research/validation_protocol.md), with their
source, configuration, data identity, period role, and artifact hashes recorded.
