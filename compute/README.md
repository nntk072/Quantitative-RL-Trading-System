# Compute

`compute/` detects runtime capabilities and describes resources needed by
training or evaluation workflows. Scheduler adapters are operational
interfaces; they do not define experiment semantics or silently change
training configuration.

| Area | Responsibility |
|---|---|
| `environment/` | Detect device/runtime capabilities and precision support. |
| `slurm/` | Represent and invoke supported scheduler workflows. |
| `contracts.py` | Shared resource/device values consumed by workflows. |
| `cli.py` | Compute diagnostics and command entry point. |

Resource availability and actual utilization are separate facts. A scheduled
GPU allocation does not establish that a process is using the GPU. Keep
allocation behavior governed by [Triton operations](../docs/operations/triton.md)
and the agent policy in `.agents/rules/triton-slurm.md`.

## Resource lifecycle

The environment capability layer inspects the active process and hardware;
resource contracts communicate requirements to workflow code; scheduler
adapters submit or observe allocation operations. These are separate facts:
an available device, a granted allocation, a running worker, and actual GPU
utilization must not be reported as the same state.

Keep scheduler-specific command details in the operational guide. A requested
resource shape must match measured CPU, host-memory, and accelerator use. Tests
under `tests/unit/compute/` validate detection and resource contracts; they do
not prove cluster availability or a remote job's utilization.

Scheduler adapter behavior is described in the local [Slurm guide](slurm/README.md).

## Purpose

Compute provides environment discovery, device selection, resource planning, and scheduler adapters for research workloads.

## Public API

Use the device and resource-planning interfaces and the Slurm helpers documented in the compute subpackages.

## Invariants

Match Python environments to node architecture, inspect live resources before allocation, and keep one research workload within its declared resource contract.
