# Engineering APIs

Compute capability discovery, resource profiles, scheduler adapters, and orchestration support repeatable development and operations. These APIs report or coordinate infrastructure; research code remains responsible for identifying the actual workload and recording evidence.

## Contracts and lifecycle

Resolve a device profile before selecting a backend, then keep architecture-specific runtime dependencies matched to the target node. Scheduler adapters should preserve job identifiers, resource requests, and terminal state. Do not infer GPU use from allocation state alone: record workload-side utilization when a claim depends on it. Orchestra's health and phase gates report validation state and should identify which canonical checks ran.

## Entry points and extension

Use the [operations guide](../../operations/README) for supported environments and [Triton operations](../../operations/triton) for architecture and scheduler details. New adapters should implement the shared capability/scheduler contracts and have deterministic tests that do not require a live allocation. Generated references: {doc}`compute <../generated/compute/index>` and {doc}`orchestra <../generated/orchestra/index>`.
