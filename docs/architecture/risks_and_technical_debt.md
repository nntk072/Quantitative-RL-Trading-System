# Risks and technical debt

This page records architectural risk categories, not a live bug tracker.
Specific fixes belong in code issues and tests; research interpretations belong
in [`research/`](../research/README.md).

| Risk area | Failure mode | Required control |
|---|---|---|
| Serialized naming and checkpoints | A rename makes historical policy classes or schemas unreadable. | Keep explicit aliases/translations and deterministic inference parity tests. |
| Data and feature causality | Incomplete higher-timeframe or future-derived information leaks into decisions. | Timestamped alignment tests and train-only fitting checks. |
| Simulator/live difference | Historical fill assumptions are mistaken for broker behavior. | Separate adapter tests and explicit deployment limitations. |
| Configuration drift | Defaults, per-variant YAML, and runtime resolution disagree. | Resolve-and-record configuration; test override precedence. |
| Research evidence sprawl | Reports, snapshots, and plans look like current instructions. | Keep a curated index and classify machine evidence separately. |
| Throughput optimization | Larger/concurrent rollouts alter on-policy ordering or increase memory beyond capacity. | Measure PPO-core performance and validate transition/update semantics. |

See [checkpoint compatibility](../reference/checkpoint_compatibility.md),
[validation protocol](../thesis/validation_protocol.md), and
[operations](../operations/README.md) for the corresponding maintained
controls.
