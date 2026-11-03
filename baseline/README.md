# Baseline records

`baseline/` holds small, version-controlled empirical reference records that
have a current, reproducible interpretation. It is not the storage location for
generated checkpoints, per-run logs, caches, or full trade ledgers.

There are currently no promoted empirical result records in this directory.
The old smoke metrics and code audits were tied to an earlier repository
architecture and exposed report period, so they are not current baseline
evidence. Historical copies and SHA-256 records were retained outside the
repository. Tier 0 policy implementations live in
[`evaluation/rollout/random_eligible_setup.py`](../evaluation/rollout/random_eligible_setup.py);
their economic comparisons remain unmeasured until simulator parity gates
pass.

Each future empirical record must state its metric and resolved-configuration
identity and link to its generating code and evidence packet. Do not promote a
baseline until its execution semantics, period role, and uncertainty are
explicitly documented.

Generated and large evaluation artifacts belong with their experiment run.
See [artifact lifecycle](../artifacts/README.md) and
[reproducibility](../docs/concepts/reproducibility.md).
