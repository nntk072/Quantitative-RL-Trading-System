# Triton, Slurm, hardware, and performance

**Status:** draft
**Use this when:** You need to choose a compute environment, read a scheduler status, or report measured runtime performance.

## Summary and use this when

Triton queues and governs shared compute. The repository provides
architecture-specific Python environments, resource and dispatch interfaces,
and a resource sampler. Use the current [Triton runbook](../../operations/triton.md)
for operating steps and the [hardware matrix](../../operations/hardware.md)
for environment selection.

Separate the workload description, allocation granted, worker state, and
measurements. Each answers a different question about where a job can run
and what it is doing.

## Key terms

- [Experiment run](../../glossary.md)
- [Rollout geometry](../../glossary.md)
- [Artifact](../../glossary.md)
- [Variant](../../glossary.md)

## Explanation

### Choose an environment from the execution host

Check the compute node's CPU architecture and backend before using Python.
The baseline activation script chooses `.venv` on ARM64,
`${X86_VENV:-<repo>/.venv-x86}` on non-AMD x86_64, and an MI210 environment
on x86_64 `gpu-amd`. For changes since the pinned baseline, consult the
current activation script and runbook together. The current runbook uses
`.venv-arm` on ARM64 and documents separate V100 and MI210 guidance.

Keep heavy training, evaluation, and feature/cache work inside an
appropriate compute allocation. Inspect and reuse a suitable allocation
first under the current Triton rules. Use the login shell for lightweight
inspection or launch. Persistent project storage is the place for logs,
checkpoints, and reports required after an allocation ends. Save durable
copies of evidence staged on temporary node-local storage.

### Interpret the resource request and the device

`ResourceProfile` describes CPU count, host memory, wall time, and optional
accelerator kind/count. `JobSpec` adds a command, working directory, and
environment. Configured accelerator kind and number describe a request.

`get_device` selects CUDA when available for automatic selection and CPU
otherwise. An explicit device string is interpreted by PyTorch. Device
resolution and detected capabilities describe the current process. Use a
real supported operation when validating accelerator functionality in a new
environment, following the [hardware matrix](../../operations/hardware.md).

The worker planner estimates concurrency from CPU, host memory and GPU limits.
It uses the minimum capacity across those resources on each node. Estimates
include configured reserves and a host-memory safety factor. When no GPU
memory data is available, the GPU capacity estimate is
`max_workers_per_gpu * gpus_per_node` for `gpu_type=gh200` (case-insensitive)
and `gpus_per_node` for other or unknown types. Treat planner outputs as
admission estimates for the supplied node data.

### Read observations at their own scope

| Observation | What it answers | Record with it |
|---|---|---|
| Scheduler job state | Whether an allocation is queued or active | Job ID, node, time, requested/granted resources |
| Worker/process state | Whether the expected workflow process is active | Worker identity, process or log observation, time |
| CPU and memory sample | Measured values at the sampler's process or cgroup scope | Scope, clock, units, peak vs. point sample |
| GPU sample | Device utilization/memory during the observation window | Device ID, sampling interval, worker and node context |
| Stage timing | Elapsed time in an instrumented part of a workload | Workload, method, warm-up, repeated runs |

The sampler includes process/descendant and cgroup measurements. Preserve
the measurement scope with a resource sample when comparing runs.
A job state of `RUNNING` and an observed throughput figure require
different evidence.

### Failure modes

- An architecture mismatch can make the interpreter or compiled dependency
  unusable even when an environment directory is present.
- Comparing scheduler memory limits to measured process memory mixes a
  resource bound with observed consumption.
- Comparing throughput after changing environment count, observation width
  or rollout geometry confounds differences in resource usage and workload.
- Losing the node-local filesystem can break evidence lineage even when
  the command completed successfully.

## Worked example

The Tier A notebook gives the real worker planner a synthetic allocation.
It checks the limiting resource and the number of worker slots.
The fixture has no scheduler, worker process, or accelerator.

```{toctree}
:hidden:

examples/triton-slurm-hardware-performance
```

## Tasks

- Read the [Triton runbook](../../operations/triton.md) for current session,
  storage, and resource procedures.
- Inspect the [compute module guide](../../modules/compute.md) for device,
  precision, and scheduler responsibilities.
- Read the [performance guide](../../operations/performance.md) before
  comparing data load, environment steps, learner updates, or artifact writes.
- Use the [compute and Slurm contract](../../reference/subjects/triton-slurm-hardware-performance.md)
  for request units and worker capacity constraints.

## Contract

| Item | Contract | Source |
|---|---|---|
| Resource request | Positive CPU, host-memory bytes and wall time seconds | `compute/contracts.py::ResourceProfile` |
| Job spec | Nonempty command and working directory | `compute/contracts.py::JobSpec` |
| Auto device | CUDA when available, CPU otherwise | `compute/environment/device.py::get_device` |
| Worker plan | CPU, host RAM, and device capacities are evaluated per node | `compute/slurm/worker_resources.py::plan_worker_capacity` |
| CPU assignment | Contiguous slice of allocated CPU ID list and a hex bitmask | `compute/slurm/worker_resources.py::cpu_mask_for_slot` |
| Resource sampling | Process tree, cgroup, and GPU readings have distinct scopes | `compute/slurm/resources.py::sample` |

## Verify

- `tests/unit/compute/test_compute_contracts.py` covers invalid requests,
  device capability records and backend-neutral submission contracts.
- `tests/unit/compute/test_worker_resources.py` covers CPU masking and
  worker command bindings on synthetic inputs.
- `tests/unit/compute/test_triton_resource_sampler.py` exercises cgroup
  lookup, CPU-time parsing and sampler fields with fixtures.
- `tests/unit/compute/test_triton_activate_venv.py` covers repository-local
  activation behavior.

## Limits and common mistakes

Current job availability, worker utilization and throughput require fresh
execution-host evidence. A tested resource calculation supports reasoning
about capacity for its inputs. Any performance comparison should record
source, data, device, host resources, runnable configuration, and stage
timings with units. Keep hardware timings separate from economic metrics.

## Change checklist

- Check environment naming against activation and setup scripts and update
  the current runbook if the dispatch behavior changes.
- Preserve unit and scope annotations when adding a resource measure.
- Check constrained memory, CPU slices, and device reservation cases.
- Retain the effective rollout geometry alongside performance measurements.
- Preserve measured reports outside temporary storage.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `resource_monitoring_engineer`
