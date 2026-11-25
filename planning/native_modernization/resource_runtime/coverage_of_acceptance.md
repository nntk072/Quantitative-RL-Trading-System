# RESOURCE-RUNTIME: coverage of acceptance

Scope: offline part only (fakes, fixtures, no Slurm state change). Source of
requirements: `ARCHITECTURE_MODERNIZATION_PLAN.md` section 3, RESOURCE-RUNTIME,
and invariant INV-COMPUTE in section 0.1. Test paths are under
`tests/unit/compute/`. Every test named here was run; counts are from the final
run recorded at the end of this file.

## Acceptance items

| # | Acceptance text (abridged) | Offline coverage | Status | Cause if not fully covered |
|---|---|---|---|---|
| A1 | resource unit fixtures | `test_resource_inventory.py` (fake cgroup v2 tree, patched `sched_getaffinity`, fake `CUDA_VISIBLE_DEVICES`); `test_admission_control.py`; `test_worker_resources.py`; `test_worker_capacity_plan.py`; `test_triton_gh200_capacity.py` (fake `sinfo`/`scontrol`) | covered offline | none |
| A2 | no GPU request without a device | `test_admission_control.py::test_gpu_request_without_a_visible_device_is_refused`; `test_resource_inventory.py::test_sentinel_or_empty_cuda_visible_devices_expose_no_gpu`; `test_worker_dispatch_parsing.py::test_launch_rejects_gpu_request_without_slurm_device_binding`, `::test_launch_refuses_unresolved_gpu_device`, `::test_gpu_device_selection_handles_cpu_request_and_invalid_binding` | covered offline | the dispatcher does not call `ResourceAdmission` (see residual R2); the GPU refusal there comes from the launch-time device check |
| A3 | timeout / ready / cancel / manager completion tests from latest commit | `test_worker_dispatch_parsing.py::test_request_times_out_when_manager_never_becomes_ready` (ready timeout); `::test_request_signal_marks_pending_request_cancelled` (shim cancel); `::test_manager_cancels_running_worker_and_records_final_exit` (SIGTERM then SIGKILL after 60 s, owned pid only); `::test_manager_dispatches_requests_and_records_completion_or_launch_failure`; `test_worker_runtime_contracts.py::test_manager_never_launches_a_request_cancelled_before_it_was_claimed` (new, see D1) | covered offline; one defect found and fixed | online SIGTERM propagation through a real `srun --overlap` shim needs an allocation (see O1) |
| A4 | oversized request rejected | `test_admission_control.py::test_request_for_every_core_is_refused_because_headroom_is_reserved`, `::test_oversized_memory_request_reports_the_reserved_limit`, `::test_gpu_count_beyond_visible_devices_is_refused`, `::test_gpu_memory_request_above_usable_bytes_reports_the_best_device`, `::test_scratch_request_respects_scratch_headroom`, `::test_granted_cores_follow_the_cpu_quota_not_the_affinity_count`; existing `test_worker_resources.py::test_cpu_mask_rejects_a_slot_outside_the_allocation`; `test_worker_dispatch_parsing.py::test_more_than_one_gpu_per_node_is_refused`, `::test_cpu_mask_larger_than_the_step_envelope_is_refused` | covered for the library; dispatcher enforcement missing | residual R2 |
| A5 | no short-step fanout proven by launch topology and permitted `sacct` checks | offline: `test_worker_runtime_contracts.py::test_shim_waits_on_one_submitted_request_without_resubmitting` (one request per shim, fixed 1 s poll, no resubmission); `::test_compute_never_executes_a_state_changing_scheduler_command` (AST scan: no literal `sbatch`/`salloc`/`srun`/`scancel` argv executed in `compute/`) | partial | the launch topology of a real allocation and the `sacct` step count need a live allocation (O2) |
| A6 | bounded memory and CPU threads | `test_thread_limits.py` (all five native pool variables set to the granted count; torch intra=granted, inter=1); `test_worker_runtime_contracts.py::test_real_worker_gets_thread_limits_from_granted_cores_and_failure_keeps_state_and_log` (a real child inherits the granted count, not the requester's 64); CPU and RAM bounds in `test_resource_inventory.py` and `test_admission_control.py` | covered at dispatch; in-process torch application has no caller | residual R6 |
| A7 | sweep thread counts / concurrency within authorized allocation; report p95 usage and throughput | none offline | blocked | needs an authorized allocation and a benchmark run (O3) |
| A8 | never claim current GH200 inventory without live inspection | no inventory claim is made; all capacity numbers in tests are fixture values | not claimed | live read requires an allocation for the in-cgroup check (O1) |

## Implement items (relevant to offline work)

| Item | Offline coverage | Status |
|---|---|---|
| Inventory: `sched_getaffinity`, cgroup limits, current and peak usage, Slurm CPU/GPU binding, `CUDA_VISIBLE_DEVICES`, GPU memory, node-local disk | `test_resource_inventory.py` (all listed, including job-level vs step-level selection and tightest-ancestor limit) | covered offline; scratch path is caller-supplied, so "node-local" is a configuration choice not tested |
| No inferred capacity from host totals | `test_resource_inventory.py::test_missing_cgroup_reports_unknown_memory_and_never_substitutes_host_totals`; `test_admission_control.py::test_unknown_memory_limit_or_usage_refuses_memory_rather_than_using_host_ram`, `::test_scratch_request_without_a_measurement_is_refused` | partial: R3 |
| Admission control reserves headroom | `test_admission_control.py` (CPU, memory, GPU-memory fraction, scratch reserves; refused request reserves nothing); planner headroom in `test_worker_capacity_plan.py` | partial: R2 |
| Resource request per DAG task (cores, RAM, GPU/HBM, scratch, dependency, wall time, checkpoint margin) | `ResourceRequest` covers cores, RAM, GPUs, GPU memory, scratch bytes | partial: scratch bandwidth, dependency, wall time and checkpoint margin are not modelled here (EXECUTION-DAG owns dependency and timing) |
| Bounded thread pools (Rayon, Polars, OMP, MKL, OpenBLAS, PyTorch intra/inter) | `test_thread_limits.py`; `test_worker_runtime_contracts.py` real-child test | partial: R6 |
| Disjoint CPU sets | `test_worker_resources.py::test_cpu_mask_selects_the_requested_slot_from_allocated_ids` | covered |
| No scheduler request in a retry loop; bounded retries | `test_worker_runtime_contracts.py::test_failed_scheduler_query_is_issued_once_and_never_retried` (one `sinfo` call on failure); the shim test above. There is no retry code, so the configured bound is zero | covered; R1 is a related residual |
| Cancel only owned child workers; never `scancel` | `test_manager_cancels_running_worker_and_records_final_exit` (signals only the owned pid); the cancel-before-launch test; the AST scan | covered |
| Preserve job state and logs on worker failure | `test_worker_runtime_contracts.py::test_real_worker_gets_thread_limits_from_granted_cores_and_failure_keeps_state_and_log` (non-zero exit: result, completed request record and log all retained); `test_manager_dispatches_requests_and_records_completion_or_launch_failure` (launch failure keeps the completed record) | covered |
| NUMA locality, GH200 CPU/GPU memory placement, pinned vs pageable, page faults | none | online-only (O3) |
| One GPU and one learner first; concurrent learners only when measured | policy, not offline-testable | online-only (O3) |

## Defects found and fixed in this package

- D1. A request cancelled while still queued was launched anyway. The shim exits
  on cancel, so the child would run with no owner. The manager now checks the
  cancel marker before launch, closes the request with status 143 (128 +
  SIGTERM), and records it as completed. Test:
  `test_worker_runtime_contracts.py::test_manager_never_launches_a_request_cancelled_before_it_was_claimed`.
- D2. Child processes inherited the requester's `OMP_NUM_THREADS` and other
  thread variables. The dispatcher now sets all five native pool variables
  from the granted core count, overriding them. Test:
  `test_worker_runtime_contracts.py::test_real_worker_gets_thread_limits_from_granted_cores_and_failure_keeps_state_and_log`.
- Test adjustment (not a behaviour change): `test_manager_cancels_running_worker_and_records_final_exit`
  placed its cancel marker before launch, which only passed because of D1. The
  marker now appears at launch time, so the test still exercises a running
  worker, and its expected signal sequence is unchanged.

## Residual gaps (offline, not fixed here)

- R1. `_request` waits for its result with no deadline. If the manager dies, the
  shim blocks until the Slurm step ends. A deadline or heartbeat changes
  semantics for long workers, so this needs a policy decision.
- R2. The dispatcher does not run `ResourceAdmission`. Requests carry no RAM
  budget, and the manager has no release accounting for finished children.
  Enforcing RAM admission needs the request contract to carry a per-worker
  memory budget from the experiment runner. That is outside this package's edit scope.
- R3. `compute/environment/device.py::scale_training_cfg` falls back to
  `/proc/meminfo` MemAvailable when no cgroup or Slurm memory limit is visible.
  That is host-total inference. Failing closed would change local, non-cgroup
  runs, so it is left for a decision. `os.cpu_count()` in the same function is
  dead (the value is unused), so it is not changed.
- R4. `tests/architecture/test_documentation_contracts.py::test_generated_public_api_inventory_matches_source`
  fails at HEAD already, because `docs/reference/public_api.{json,md}` is stale.
  New public names in `compute/slurm` keep it stale. Regenerating needs a write
  under `docs/`, which is outside this package's scope.
- R5. `tests/architecture/test_project_identity.py::test_current_project_files_use_neutral_identity`
  fails at HEAD already: `planning/native_modernization/ARCHITECTURE_MODERNIZATION_PLAN.md`
  contains the word "research" seven times. Not touched here.
- R6. `apply_torch_threads` has no caller in `compute/`. The training entry point
  must call it at process start, before parallel work. That file is outside this package's scope.
- R7. cgroup v1 memory is not read by the new inventory, so it reports `None`
  and admission refuses memory. This fails closed; the cluster is cgroup v2.

## Online-only items and the allocation the lead must request

No allocation was requested or used. Nothing here ran `srun`, `sbatch`,
`salloc` or `scancel`.

- O1. Live inventory and the real signal path. Needs one GH200 interactive
  allocation of one GPU, 48 CPUs and 512G (the capacity-checker defaults),
  requested through `scripts/compute/slurm/attach_or_alloc.sh` with
  `SKIP_PICK=1 PARTITION=<current GH200 partition, confirmed by read-only sinfo> GPUS=1 CPUS=48 MEM=512G`.
  It needs explicit user authorization under `.agents/rules/triton-slurm.md`. Inside that
  allocation, run `read_inventory()` in the existing shell (no new step) and
  exercise the manager and shim with a fixture queue. This covers the
  shim-to-manager cancel path and the real `CUDA_VISIBLE_DEVICES` binding.
- O2. Launch topology and `sacct`. Same allocation: one manager per node, one
  shim step per worker, and read-only `sacct -j <job> --format=JobID,State,ElapsedRaw`
  to count steps.
- O3. Thread-count and concurrency sweep, p95 usage, throughput, NUMA and GH200
  placement, pinned vs pageable, page faults. Needs an authorized allocation and
  a benchmark run, both outside this offline work.

## Test commands and results

From the worktree, with `/scratch/work/nguyenl37/Quantitative-RL-Trading-System/.venv-x86/bin/python`:

- `python -m pytest tests/unit/compute -q`: 171 passed, exit 0 (118 at baseline, 53 new).
- `python -m pytest tests/architecture -q`: 67 passed, 2 failed, exit 1. Both failures
  are pre-existing at HEAD (R4 and R5). The docstring-audit test passes.
- `ruff format --check` on the 11 touched files: already formatted, exit 0.
- `ruff check` on the same files: passed, exit 0.
- `python -m mypy` on the five touched `compute/slurm` modules: no issues, exit 0.
- Not run: the full unit suite and full-tree mypy (login-node restriction).
