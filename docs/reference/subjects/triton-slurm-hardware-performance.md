# Compute and Slurm contract

**Status:** draft
**Source of truth:** `compute/contracts.py`; `compute/environment/device.py`; `compute/cli.py`; `compute/slurm/worker_resources.py`; `compute/slurm/resources.py`

## Requests and capabilities

| Surface | Inputs and outputs |
|---|---|
| `ResourceProfile` | Positive CPU count, host bytes and wall time seconds. Accelerator count defaults to zero and must be nonnegative. A nonzero count requires a kind. |
| `JobSpec` | Nonempty command tuple and working-directory string, a resource profile, and string environment mapping. |
| `ExecutionBackend.submit` | Consumes a job spec and returns a backend identifier string. |
| `DeviceCapabilities` | Architecture, accelerator kind/count/memory bytes, BF16 support and optional backend, name, or compute capability. |
| `get_device` | Empty/`None` or case-insensitive `auto` selects CUDA if available, otherwise CPU. Explicit strings pass through `torch.device`; invalid values raise `ValueError` when parsing fails. |
| `qrl-compute` | Dispatches `capacity`, `resources`, `continuation`, or `worker`. |

## Worker plan

`plan_worker_capacity` accepts `n_envs` in `{4, 8, 16, 32, 64}`,
per-node resource records, a data source and positive GPU count per node.
CPU worker minimum is `max(2, ceil(n_envs / 2))`. The node capacity is the
minimum of CPU, host-memory, and GPU estimates after the respective reserves.
With unknown host-memory limit the estimate admits at most one worker per
node. If the node reports no GPU memory records, the GPU capacity estimate
is `max_workers_per_gpu * gpus_per_node` when the lowercased `gpu_type` is
`gh200`, or `gpus_per_node` for other or unknown types. The return mapping
contains total workers, minimum worker CPU count, planning settings, and
per-node capacities and GPU slots.

`cpu_mask_for_slot` takes an ordered list of allocated CPU IDs, a
nonnegative slot and a positive count. It returns a hexadecimal bitmask and
the selected IDs, and rejects an incomplete slice.

## Measurement scope

Use the [Triton runbook](../../operations/triton.md) for active environment
selection and operational rules. Consult the [performance guide](../../operations/performance.md)
when specifying sampling windows and timing stages. Time-scope and sample
source must accompany any utilization value.
