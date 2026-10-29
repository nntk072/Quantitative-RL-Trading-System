# GH200 Pipelined PPO WP0/WP1 Measurement Results

**Measurement directory:** `docs/research/gh200_pipelined_ppo_refactor_20261028/measurements/wp0-job-21274098`
**New measurement source SHA:** `92cc81a7fa8b0c9e1cbff06789c520b19b90613af8104f54b415221f0dd1dc77`
**New measurement working-tree patch identity SHA-256:** `1056afa9bc3386dff4b4aa3427ad4009e4e13825326b9628e8997473734d4dee`
**Historical baseline source commit(s):** `3fbbb74fdbe581807df38c1feaab7307839506f5`
**Historical baseline benchmark source SHA-256:** `8e3780324d1422ee83e049325be2d212ce65d8a3fda4f3daa5cd0d01a5c94f61`
**Bundle manifest SHA-256:** `d85e0dc8fa241c66d4d727dd4be5d463fc58dbbbd53a43fd00d75100387b052e`
**Policy:** mtf_shared_tcn_reasoning / PPO; seed 42; 64 envs; 16384 transitions/rollout; batch 4096; 15 epochs.

These are PPO-core measurements without production evaluation callbacks, checkpoint selection, or full train/test replay. They are throughput evidence, not trading-performance evidence.

The new profile/topology screen requested 131,072 environment steps and measured 65,536 after warmup. Each topology is a single short pass; treat differences as directional, not as a stable performance win.

## Unprofiled baseline repeats

| Repeat | Backend | Workers | Envs/worker | PPO-core steps/s | Rollout s | Update s | CPU cores used | GPU coarse utilization p50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| e64-high-baseline-repeat1 | sharded_bundle | 16 | `[4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4]` | 910.76 | 165.01 | 86.84 | 3.41 | unknown% |
| e64-high-baseline-repeat2 | sharded_bundle | 16 | `[4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4]` | 962.23 | 152.00 | 86.38 | 3.35 | unknown% |
| e64-high-baseline-repeat3 | sharded_bundle | 16 | `[4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4]` | 960.37 | 152.26 | 86.58 | 3.29 | unknown% |
| **Mean ± sample SD** | — | — | — | **944.45 ± 29.19** | — | — | — | — |

## Worker-topology screen

| Case | Backend | Workers | Envs/worker | PPO-core steps/s | Change vs baseline mean | Rollout s | Update s |
|---|---|---:|---:|---:|---:|---:|---:|
| e64-high-subproc64 | subproc | 64 | `[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]` | 1,089.65 | +15.37% | 18.24 | 11.84 |

## Profiled diagnostic run

This run is instrumented and is not compared as an unprofiled FPS repeat.

| Measurement | Observed |
|---|---:|
| PPO-core transitions/s | 911.96 |
| Warmup-excluded rollout + update sum | 35.93 s |
| Warmup-excluded PPO-core total | 35.93 s |
| Rollout seconds after warmup | 23.79 |
| PPO update seconds after warmup | 12.14 |
| All-rollout measured wall | 47.43 s |
| Unattributed training wall remainder | 0.23 s |
| Worker observation construction | 24.78 s across 65,653 calls |
| Final CUDA boundary wait | 0.00 s |
| Sampled coarse GPU utilization p50 / p95 | 6.00% / 88.00% |
| GPU memory used p95 | 14,546.00 MiB |
| Peak PyTorch allocated HBM | 12.12 GiB |
| SM-active / occupancy | UNKNOWN unless a supported Nsight metric was actually captured |
| H2D / D2H transfer totals | UNKNOWN in the Python summary; inspect the captured Nsight trace if available |
| DRAM bandwidth | UNKNOWN unless a supported Nsight metric was actually captured |
| Worker send/serialize time and IPC bytes | UNKNOWN as a separate component; `vec_step_wait` includes worker completion and IPC, while Nsight OS-runtime traces are retained when available |

### Phase CPU time

| Phase | Process-tree CPU seconds |
|---|---:|
| collect_rollouts | 232.37 |
| train | 25.98 |

### Worker step-time balance

Times sum each worker's serial environment `step()` calls. Parent `step_wait` also includes worker result serialization/IPC; the explicit host-method table separates parent stacking. These components are diagnostic and not all additive.

| Worker | Logical envs | Serial env-step seconds |
|---:|---:|---:|
| 0 | 4 | 10.26 |
| 1 | 4 | 10.45 |
| 2 | 4 | 10.67 |
| 3 | 4 | 10.24 |
| 4 | 4 | 10.88 |
| 5 | 4 | 14.48 |
| 6 | 4 | 10.52 |
| 7 | 4 | 15.24 |
| 8 | 4 | 10.80 |
| 9 | 4 | 12.14 |
| 10 | 4 | 10.54 |
| 11 | 4 | 15.44 |
| 12 | 4 | 11.81 |
| 13 | 4 | 14.09 |
| 14 | 4 | 14.99 |
| 15 | 4 | 12.91 |

### Instrumented host method time

These timings are diagnostic and nested phases must not be summed with their enclosing rollout/update wall time.

| Method/range | Samples | Total ms | p50 ms | p95 ms |
|---|---:|---:|---:|---:|
| backward | 240 | 4,269.79 | 16.09 | 20.58 |
| cuda_synchronize | 5 | 0.45 | 0.10 | 0.11 |
| gae | 4 | 5.68 | 1.39 | 1.60 |
| optimizer_step | 240 | 467.39 | 1.73 | 2.24 |
| parent_observation_stack | 1,025 | 1,316.82 | 1.22 | 2.06 |
| policy_evaluate_actions | 240 | 10,521.27 | 42.78 | 46.77 |
| policy_forward | 1,024 | 17,168.13 | 15.60 | 23.22 |
| rollout_buffer_add | 0 | 0.00 | unknown | unknown |
| vec_step_async | 1,024 | 345.48 | 0.32 | 0.48 |
| vec_step_wait | 1,024 | 27,429.69 | 24.41 | 48.40 |

### CUDA stream elapsed time

CUDA event duration includes stream gaps; it is not SM-active time.

| Phase | Samples | Total ms | p50 ms | p95 ms |
|---|---:|---:|---:|---:|
| collect_rollouts | 4 | 47,183.26 | 11,738.38 | 12,646.39 |
| train | 4 | 24,534.75 | 6,007.23 | 6,469.23 |

### Process/thread wait and CPU samples

| Phase | Samples | Busy cores | Runnable threads | Sleeping threads | Uninterruptible threads | Major faults | Top wait channels |
|---|---:|---:|---:|---:|---:|---:|---|
| ppo.backward | 11 | 1.25 | 1.0 | 22.0 | unknown | 1 | unix_stream_data_wait (176), futex_do_wait (22), poll_schedule_timeout.constprop.0 (22) |
| ppo.evaluate_actions | 4 | 1.00 | 1.0 | 22.0 | unknown | 0 | unix_stream_data_wait (64), poll_schedule_timeout.constprop.0 (8), futex_do_wait (8) |
| ppo.optimizer_step | 1 | 1.01 | 1.0 | 22.0 | unknown | 0 | unix_stream_data_wait (16), futex_do_wait (2), poll_schedule_timeout.constprop.0 (2) |
| ppo.policy_forward | 20 | 4.31 | 1.0 | 21.9 | unknown | 32 | unix_stream_data_wait (320), poll_schedule_timeout.constprop.0 (41), futex_do_wait (38) |
| ppo.train | 6 | 1.13 | 1.0 | 22.0 | unknown | 0 | unix_stream_data_wait (96), poll_schedule_timeout.constprop.0 (12), futex_do_wait (12) |
| ppo.vec_step_wait | 24 | 5.19 | 10.0 | 12.6 | unknown | 116 | unix_stream_data_wait (97), sock_alloc_send_pskb (70), poll_schedule_timeout.constprop.0 (49) |
| startup | 1 | 1.02 | 1.0 | 22.0 | unknown | 0 | unix_stream_data_wait (16), poll_schedule_timeout.constprop.0 (2), futex_do_wait (2) |

GPU telemetry samples: 70.
utilization.gpu is coarse device utilization, not SM-active or occupancy; memory.used is capacity usage, not DRAM bandwidth.

## Nsight Systems evidence

- Profile status: `nsys=not run in the short measurement scope; SM-active and detailed transfer metrics remain UNKNOWN`
- Raw trace: unavailable.
- Kernel and memory-copy statistics: unavailable.

SM-active cycles, occupancy, Tensor Core activity, and DRAM bandwidth remain UNKNOWN unless the captured Nsight data explicitly reports those metrics. A kernel-duration or memory-copy summary alone does not establish those utilization measures.

## Interpretation limits

- The three baseline repeats define the unprofiled reference. The profiler case is diagnostic and excluded from that mean.
- A topology winner is only a throughput candidate; this benchmark does not establish identical PPO learning trajectories or policy quality.
- Coarse `nvidia-smi utilization.gpu` is not SM occupancy or active-cycle percentage. CUDA event elapsed time includes stream gaps.
- Full training callbacks, checkpointing, train-year replay, report-only test replay, and end-to-end makespan are outside this PPO-core probe.
- Any absent metric remains UNKNOWN. Do not infer occupancy or memory bandwidth from allocated/reserved HBM.
