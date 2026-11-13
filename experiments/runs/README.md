# Durable experiment runs

This package manages training-run identity, attempts, checkpoints, retry
safety, resume, and status reporting. It does not define the scientific
meaning of a variant or the simulator's execution rules.

The run manifest binds the selected configuration to source revision, data
and feature-cache identity, random seed, budget, and model settings. A retry
may reuse the run identity only when its fingerprint is unchanged; a changed
factor creates a different run. Recovery must validate checkpoint lineage
and previously recorded artifacts before continuing.

`experiments/research/execution.py` separately manages source-bound
research command bundles, including independent data and evaluation work.
Those records are consolidated by
`experiments/research/reporting.py` using explicit domain, experiment,
component, variant, seed, command, and artifact identities. Neither engine
should infer experimental meaning from a filename or directory suffix.

See [experiment framework](../README.md),
[reproducibility](../../docs/concepts/reproducibility.md), and
[run an experiment](../../docs/how-to/run_experiment.md).
