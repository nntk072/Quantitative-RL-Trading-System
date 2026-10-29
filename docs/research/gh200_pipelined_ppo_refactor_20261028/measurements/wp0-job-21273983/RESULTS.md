# GH200 Pipelined PPO WP0/WP1 Measurement Results

**Measurement directory:** `docs/research/gh200_pipelined_ppo_refactor_20261028/measurements/wp0-job-21273983`
**New measurement source SHA:** `92cc81a7fa8b0c9e1cbff06789c520b19b90613af8104f54b415221f0dd1dc77`
**New measurement working-tree patch identity SHA-256:** `65d35e78a5f148ae488ac2b281e9cdbc4124d9894421fc0f90947aec757d766f`
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
| e64-high-subproc64 | subproc | 64 | `[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]` | 1,088.39 | +15.24% | 18.24 | 11.87 |

## Profiled diagnostic run

This run is instrumented and is not compared as an unprofiled FPS repeat.

| Measurement | Observed |
|---|---:|
| PPO-core transitions/s | 904.95 |
| Warmup-excluded rollout + update sum | 36.21 s |
| Warmup-excluded PPO-core total | 36.21 s |
| Rollout seconds after warmup | 24.06 |
| PPO update seconds after warmup | 12.15 |
| All-rollout measured wall | 48.35 s |
| Unattributed training wall remainder | 0.24 s |
| Worker observation construction | 25.33 s across 65,648 calls |
| Final CUDA boundary wait | 0.00 s |
| Sampled coarse GPU utilization p50 / p95 | 6.00% / 89.00% |
| GPU memory used p95 | 14,546.00 MiB |
| Peak PyTorch allocated HBM | 12.12 GiB |
| SM-active / occupancy | UNKNOWN unless a supported Nsight metric was actually captured |
| H2D / D2H transfer totals | UNKNOWN in the Python summary; inspect the captured Nsight trace if available |
| DRAM bandwidth | UNKNOWN unless a supported Nsight metric was actually captured |
| Worker send/serialize time and IPC bytes | UNKNOWN as a separate component; `vec_step_wait` includes worker completion and IPC, while Nsight OS-runtime traces are retained when available |

### Phase CPU time

| Phase | Process-tree CPU seconds |
|---|---:|
| collect_rollouts | 234.26 |
| train | 25.71 |

### Worker step-time balance

Times sum each worker's serial environment `step()` calls. Parent `step_wait` also includes worker result serialization/IPC; the explicit host-method table separates parent stacking. These components are diagnostic and not all additive.

| Worker | Logical envs | Serial env-step seconds |
|---:|---:|---:|
| 0 | 4 | 15.75 |
| 1 | 4 | 13.76 |
| 2 | 4 | 10.64 |
| 3 | 4 | 10.52 |
| 4 | 4 | 10.98 |
| 5 | 4 | 15.27 |
| 6 | 4 | 13.74 |
| 7 | 4 | 10.92 |
| 8 | 4 | 10.75 |
| 9 | 4 | 13.80 |
| 10 | 4 | 13.88 |
| 11 | 4 | 10.67 |
| 12 | 4 | 10.66 |
| 13 | 4 | 11.18 |
| 14 | 4 | 10.86 |
| 15 | 4 | 13.77 |

### Instrumented host method time

These timings are diagnostic and nested phases must not be summed with their enclosing rollout/update wall time.

| Method/range | Samples | Total ms | p50 ms | p95 ms |
|---|---:|---:|---:|---:|
| backward | 240 | 3,922.97 | 15.25 | 18.22 |
| cuda_synchronize | 5 | 0.48 | 0.11 | 0.11 |
| gae | 4 | 5.33 | 1.29 | 1.51 |
| optimizer_step | 240 | 466.61 | 1.75 | 1.98 |
| parent_observation_stack | 1,025 | 1,308.08 | 1.21 | 2.12 |
| policy_evaluate_actions | 240 | 10,414.73 | 42.40 | 46.10 |
| policy_forward | 1,024 | 17,261.53 | 15.31 | 22.92 |
| rollout_buffer_add | 0 | 0.00 | unknown | unknown |
| vec_step_async | 1,024 | 347.41 | 0.33 | 0.48 |
| vec_step_wait | 1,024 | 28,272.24 | 25.53 | 48.59 |

### CUDA stream elapsed time

CUDA event duration includes stream gaps; it is not SM-active time.

| Phase | Samples | Total ms | p50 ms | p95 ms |
|---|---:|---:|---:|---:|
| collect_rollouts | 4 | 48,082.88 | 12,059.64 | 12,844.45 |
| train | 4 | 24,217.02 | 5,968.38 | 6,292.80 |

### Process/thread wait and CPU samples

| Phase | Samples | Busy cores | Runnable threads | Sleeping threads | Uninterruptible threads | Major faults | Top wait channels |
|---|---:|---:|---:|---:|---:|---:|---|
| ppo.backward | 9 | 1.51 | 1.0 | 22.0 | unknown | 3 | unix_stream_data_wait (144), futex_do_wait (18), poll_schedule_timeout.constprop.0 (18) |
| ppo.collect_rollouts | 1 | 5.15 | 1.0 | 21.0 | unknown | 10 | unix_stream_data_wait (16), poll_schedule_timeout.constprop.0 (2), futex_do_wait (1) |
| ppo.evaluate_actions | 9 | 1.30 | 1.0 | 21.9 | unknown | 2 | unix_stream_data_wait (144), poll_schedule_timeout.constprop.0 (18), futex_do_wait (17) |
| ppo.optimizer_step | 1 | 1.00 | unknown | 23.0 | unknown | 0 | unix_stream_data_wait (16), futex_do_wait (3), poll_schedule_timeout.constprop.0 (2) |
| ppo.policy_forward | 16 | 4.70 | 1.0 | 21.8 | 0.1 | 35 | unix_stream_data_wait (256), poll_schedule_timeout.constprop.0 (32), futex_do_wait (28) |
| ppo.train | 5 | 1.47 | 1.0 | 22.0 | unknown | 0 | unix_stream_data_wait (80), futex_do_wait (10), poll_schedule_timeout.constprop.0 (10) |
| ppo.vec_step_async | 1 | 4.91 | 1.0 | 22.0 | unknown | 3 | unix_stream_data_wait (16), poll_schedule_timeout.constprop.0 (2), futex_do_wait (2) |
| ppo.vec_step_wait | 26 | 4.62 | 11.2 | 11.6 | unknown | 150 | sock_alloc_send_pskb (96), unix_stream_data_wait (54), poll_schedule_timeout.constprop.0 (53) |

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
