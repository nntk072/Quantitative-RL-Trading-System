# WP3 Cohort-Pipeline Feasibility

- Allocation/job: `wp3-job-21274889` on `gpuarm1`; see `allocation.txt`.
- Config: `config/research/thesis_mtf_shared_tcn_2m_high_throughput.yaml`, SHA-256 `64c825188b83151c0a8f571298a94c8c1d5a373bc9668e7b7adea407e18cc632`.
- Shared training bundle manifest SHA-256: `d85e0dc8fa241c66d4d727dd4be5d463fc58dbbbd53a43fd00d75100387b052e`.
- PPO geometry: 64 environments x 256 steps; batch 4096; 15 epochs.
- Scope: one bounded rollout-contract smoke; one profiled sequential baseline; three warmed PPO-core repeats per topology. No training campaign, checkpoint, or production collector change.

## Correctness and on-policy checks

| Check | Result |
|---|---|
| report present | PASS |
| runtime identity | PASS |
| 64 env geometry | PASS |
| single policy version per rollout | PASS |
| buffer full and gae finite | PASS |
| invalid thesis actions zero | PASS |
| action order in buffer | PASS |
| worker transition alignment | PASS |
| finite rewards and termination types | PASS |
| one update after rollout | PASS |
| finite ppo core rate | PASS |

The prototype leaves SB3's `collect_rollouts`, `step_wait` response ordering, callback sequence, rollout buffer insertion, GAE calculation, and PPO update in control. It dispatches each contiguous environment cohort immediately after that cohort's inference. The rollout smoke checks exact raw-action ordering in the PPO buffer, finite rewards and advantages, one policy version across the rollout, complete 256-step/64-env transition batches, boolean terminations, and masked thesis selections.

## Full PPO-core throughput

PPO-core FPS includes completed rollout collection **and** PPO updates; the first two rollouts per repeat are warmup and excluded. All topologies use paired seeds 42/43/44, the same bundle, 64 environments, 256 steps per environment, batch 4096, 15 epochs, and one GH200 at a time.

| Topology | Repeat FPS (42, 43, 44) | Mean +/- sample SD | Gain vs sequential |
|---|---:|---:|---:|
| Sequential 64-env SB3 collector | 1,184.53, 1,143.99, 1,170.81 | 1,166.44 +/- 20.62 | baseline |
| Pipelined 2 x 32 cohorts | 949.40, 930.93, 878.20 | 919.51 +/- 36.95 | -21.17% |
| Pipelined 4 x 16 cohorts | 670.10, 680.94, 652.13 | 667.72 +/- 14.55 | -42.76% |

## CPU/GPU and IPC profile

- Parent policy inference latency, p50/p95: 15.09/23.34 ms per 64-env batch.
- Parent `step_wait`, p50/p95: 14.51/17.66 ms; it is the collector's post-dispatch wait proxy, not a direct GPU idle or SM-active measurement.
- Sampled worker `TradingEnv.step`, p50/p95: 2.72/9.76 ms per worker step.
- Parent IPC calls: 81984 sends / 81984 receives; transport buffers 14829248 bytes sent / 7870044547 bytes received.
- IPC transport latency p50/p95: send 0.00/0.01 ms; receive 0.02/0.06 ms.
- Coarse GPU utilization p50/p95: 9.00%/88.00%.
- CPU/GPU cohort overlap is reported in each pipeline run as the measured fraction of later-cohort inference overlapped by earlier-cohort environment stepping. Nsight SM-active/occupancy was not measured unless the allocation log shows a successful supported trace.

### Measured CPU-step / later-inference overlap

| Pipeline topology | Per-repeat mean fraction (42, 43, 44) | Across-repeat mean |
|---|---:|---:|
| Pipelined 2 x 32 cohorts | 50.81%, 46.69%, 41.82% | 46.44% |
| Pipelined 4 x 16 cohorts | 41.78%, 43.39%, 40.11% | 41.76% |

## Decision

- **Pipelined 2 x 32 cohorts:** mean core gain -21.17%; seed-wise gains -19.85%, -18.62%, -24.99%. Does not meet the >=20% repeatable gain gate.
- **Pipelined 4 x 16 cohorts:** mean core gain -42.76%; seed-wise gains -43.43%, -40.48%, -44.30%. Does not meet the >=20% repeatable gain gate.

A result below the gate supports retaining this as a benchmark prototype and not adopting a production collector rewrite. A passing result justifies a separately reviewed implementation proposal; this feasibility experiment does not authorize a production integration.

## Evidence and limitations

- Raw timing JSON, case logs, allocation identity, runtime preflight, and focused test log are retained beside this report.
- IPC counters measure parent-side multiprocessing transport buffers and method time; they exclude child execution and pickle encode/decode CPU time.
- `step_wait` includes worker finish time and response IPC. Coarse `nvidia-smi` utilization is not a kernel-level GPU idle trace.
- The prototype is benchmark-only. It does not implement asynchronous environments, overlap PPO updates with collection, or relax the on-policy barrier.
