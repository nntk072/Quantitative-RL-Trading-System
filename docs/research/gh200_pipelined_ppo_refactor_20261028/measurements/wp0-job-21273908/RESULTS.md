# GH200 Pipelined PPO WP0/WP1 Measurement Results

**Measurement directory:** `docs/research/gh200_pipelined_ppo_refactor_20261028/measurements/wp0-job-21273908`
**New measurement source SHA:** `92cc81a7fa8b0c9e1cbff06789c520b19b90613af8104f54b415221f0dd1dc77`
**New measurement working-tree patch identity SHA-256:** `26cd91d511df206295ee58c668a8db11c776e98827218414f10ff316f90cb441`
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
| e64-high-subproc64 | subproc | 64 | `[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]` | 1,111.24 | +17.66% | 17.79 | 11.70 |

## Profiled diagnostic run

This run is instrumented and is not compared as an unprofiled FPS repeat.

| Measurement | Observed |
|---|---:|
| PPO-core transitions/s | 921.55 |
| Warmup-excluded rollout + update sum | 35.56 s |
| Warmup-excluded PPO-core total | 35.56 s |
| Rollout seconds after warmup | 23.19 |
| PPO update seconds after warmup | 12.37 |
| All-rollout measured wall | 52.79 s |
| Unattributed training wall remainder | 0.30 s |
| Worker observation construction | 22.97 s across 65,649 calls |
| Final CUDA boundary wait | 0.00 s |
| Sampled coarse GPU utilization p50 / p95 | 6.00% / 88.00% |
| GPU memory used p95 | 14,548.00 MiB |
| Peak PyTorch allocated HBM | 12.12 GiB |
| SM-active / occupancy | UNKNOWN unless a supported Nsight metric was actually captured |
| H2D / D2H transfer totals | UNKNOWN in the Python summary; inspect the captured Nsight trace if available |
| DRAM bandwidth | UNKNOWN unless a supported Nsight metric was actually captured |
| Worker send/serialize time and IPC bytes | UNKNOWN as a separate component; `vec_step_wait` includes worker completion and IPC, while Nsight OS-runtime traces are retained when available |

### Phase CPU time

| Phase | Process-tree CPU seconds |
|---|---:|
| collect_rollouts | 220.29 |
| train | 25.93 |

### Worker step-time balance

Times sum each worker's serial environment `step()` calls. Parent `step_wait` also includes worker result serialization/IPC; the explicit host-method table separates parent stacking. These components are diagnostic and not all additive.

| Worker | Logical envs | Serial env-step seconds |
|---:|---:|---:|
| 0 | 4 | 15.07 |
| 1 | 4 | 10.44 |
| 2 | 4 | 10.66 |
| 3 | 4 | 10.45 |
| 4 | 4 | 10.48 |
| 5 | 4 | 10.56 |
| 6 | 4 | 10.51 |
| 7 | 4 | 10.93 |
| 8 | 4 | 10.63 |
| 9 | 4 | 10.35 |
| 10 | 4 | 10.44 |
| 11 | 4 | 10.64 |
| 12 | 4 | 14.57 |
| 13 | 4 | 14.30 |
| 14 | 4 | 11.09 |
| 15 | 4 | 11.15 |

### Instrumented host method time

These timings are diagnostic and nested phases must not be summed with their enclosing rollout/update wall time.

| Method/range | Samples | Total ms | p50 ms | p95 ms |
|---|---:|---:|---:|---:|
| backward | 240 | 4,055.31 | 15.53 | 19.73 |
| cuda_synchronize | 5 | 0.47 | 0.10 | 0.11 |
| gae | 4 | 5.54 | 1.34 | 1.55 |
| optimizer_step | 240 | 489.35 | 1.79 | 2.41 |
| parent_observation_stack | 1,025 | 1,366.02 | 1.23 | 2.18 |
| policy_evaluate_actions | 240 | 10,571.63 | 42.59 | 46.88 |
| policy_forward | 1,024 | 23,832.16 | 15.23 | 25.96 |
| rollout_buffer_add | 0 | 0.00 | unknown | unknown |
| vec_step_async | 1,024 | 354.02 | 0.33 | 0.49 |
| vec_step_wait | 1,024 | 26,057.81 | 23.88 | 46.32 |

### CUDA stream elapsed time

CUDA event duration includes stream gaps; it is not SM-active time.

| Phase | Samples | Total ms | p50 ms | p95 ms |
|---|---:|---:|---:|---:|
| collect_rollouts | 4 | 52,529.77 | 12,335.32 | 16,827.96 |
| train | 4 | 24,433.74 | 6,090.72 | 6,296.17 |

### Process/thread wait and CPU samples

| Phase | Samples | Busy cores | Runnable threads | Sleeping threads | Uninterruptible threads | Major faults | Top wait channels |
|---|---:|---:|---:|---:|---:|---:|---|
| env.parent_observation_stack | 1 | 4.19 | 3.0 | 19.0 | unknown | 6 | unix_stream_data_wait (13), poll_schedule_timeout.constprop.0 (2), futex_do_wait (1) |
| ppo.backward | 4 | 0.98 | 1.0 | 22.0 | unknown | 0 | unix_stream_data_wait (64), futex_do_wait (8), poll_schedule_timeout.constprop.0 (8) |
| ppo.evaluate_actions | 8 | 1.13 | 1.0 | 22.0 | unknown | 4 | unix_stream_data_wait (128), poll_schedule_timeout.constprop.0 (17), futex_do_wait (15) |
| ppo.policy_forward | 28 | 3.66 | 0.9 | 21.6 | 0.1 | 1,307 | unix_stream_data_wait (448), poll_schedule_timeout.constprop.0 (57), futex_do_wait (43) |
| ppo.train | 11 | 1.33 | 1.0 | 22.0 | unknown | 0 | unix_stream_data_wait (176), poll_schedule_timeout.constprop.0 (22), futex_do_wait (22) |
| ppo.vec_step_wait | 19 | 4.59 | 10.6 | 12.2 | unknown | 206 | unix_stream_data_wait (64), sock_alloc_send_pskb (57), poll_schedule_timeout.constprop.0 (38) |
| startup | 1 | 3.38 | 1.0 | 22.0 | unknown | 0 | unix_stream_data_wait (16), poll_schedule_timeout.constprop.0 (2), futex_do_wait (2) |

GPU telemetry samples: 75.
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
