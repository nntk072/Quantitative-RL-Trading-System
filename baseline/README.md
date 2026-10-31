# Baseline records

`baseline/` holds small, version-controlled baseline records used as reference
inputs or expected metrics. It is not the storage location for generated
checkpoints, per-run logs, caches, or full trade ledgers.

Each record should state the metric/configuration identity it represents and
remain linked to its generating code or run evidence. Do not overwrite a
baseline merely because a later run looks better; update it only through an
explicit research or compatibility decision.

Generated and large evaluation artifacts belong with their experiment run.
See [artifact lifecycle](../artifacts/README.md) and
[reproducibility](../docs/concepts/reproducibility.md).
