# QA for Triton, Slurm, hardware, and performance

**Status:** Five source claims verified at
`c0d982f94ab9df8b2a9ddd013d2ae9a562573529`, with the revised activation
path scoped to the working tree.

## Source claims

1. `compute/contracts.py::ResourceProfile` requires positive CPU, host
   memory bytes, and wall time, and an accelerator kind for a positive
   accelerator count. `JobSpec` rejects an empty command or working
   directory. `tests/unit/compute/test_compute_contracts.py` covers
   request validation and neutral submission.
2. `compute/environment/device.py::get_device` selects CUDA when
   available and CPU otherwise for automatic selection. Explicit values
   go directly to `torch.device`.
3. `compute/slurm/worker_resources.py::plan_worker_capacity` limits
   workers by the minimum of CPU, memory, and GPU capacity on each node.
   The synthetic inputs give CPU 7, host memory 2, and GPU 9. Missing
   host-memory information caps the memory estimate at one worker.
4. `cpu_mask_for_slot` slices the allocated-ID list and returns the
   hexadecimal mask and selected IDs. `tests/unit/compute/test_worker_resources.py`
   covers selection and rejection of out-of-allocation slices.
5. `compute/slurm/resources.py::sample` combines distinct process-tree,
   cgroup, and GPU measures. `tests/unit/compute/test_triton_resource_sampler.py`
   checks cgroup resolution, process time, and per-device output.
   The ARM environment is `.venv` at the pinned activation script and
   `.venv-arm` in the current script and runbook.

## Document and notebook checks

The revised hub has 155 lines and the title and ten required sections.
Thirteen local Markdown links across the hub and reference resolve. The
hidden notebook target resolves. The hub and reference now document the
fallback when GPU memory records are absent. The planner uses the
configured share ceiling for GH200 and one slot per requested GPU for
other types. Both descriptions agree with the pinned planner.

Static notebook checks accepted Python 3, Tier A, CPU, deterministic
bundled data, subject and owner, matching title and first heading,
under-60-seconds target, and forced MyST execution. Its single
assert-bearing cell has count 1, one saved result showing the two-worker
limit, and zero saved errors. Recorded cell time is 0.010 seconds.

## Evidence limit

The worker count is a calculation over synthetic inputs. QA inspected the
saved notebook without rerunning it. No scheduler state, live capacity,
accelerator utilization, or measured performance was checked.
