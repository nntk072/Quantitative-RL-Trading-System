# GH200 Pipelined PPO Refactor: Current Status

**Updated:** 2026-10-29
**Implementation branch:** `codex/gh200-max-fps`
**Baseline commit:** `248d5b1eeeb5ae0a7817d049607e8eb8d99e28a6`
**Plan:** [`../GH200_FULL_RESOURCE_PIPELINED_PPO_REFACTOR_PLAN_2026-10-28.md`](../GH200_FULL_RESOURCE_PIPELINED_PPO_REFACTOR_PLAN_2026-10-28.md)

## Scope and preservation

This is bounded throughput and inference-path engineering, not a 2M training or economic benchmark. No 2M run has been launched. The user explicitly approved two GH200s on one node for separate GPU tasks and corrected the requested time limit to **6 hours**. Current allocation `21274446` uses that six-hour limit, 96 CPUs, 512 GiB host RAM, and two GH200s on `gpuarm1`, launched from the persistent `ppo-pipelined-wp0-submit-20261028` tmux session. `gpuarm2` is down. The main checkout and its untracked `campaign_worker_dispatch.log` remain untouched.

The previous C/D job was stopped at the user's direction. Its terminal attempt state is not a successful benchmark; its logs, manifest, and latest 750,000-step checkpoints were preserved. WP0/WP1 throughput outputs are retained by job and were not overwritten.

## WP0: high-throughput configuration and profile

The high-throughput E configuration is now a complete overlay resolved through the production CLI loader. It retains the MTF shared-TCN encoder, thesis-conditioned distribution and mask, strategy context, simulation settings, and callbacks. The effective diff against the E baseline is restricted to data source, environment count/shards, rollout geometry, minibatch, and requested environment count. The regression test checks the recursively resolved config and runtime identity.

The profiler reports CPU timing, CUDA-event phase durations, worker observation construction, parent stacking, process-tree CPU, coarse `nvidia-smi` telemetry, and sampled market decision-index reuse. It leaves SM-active cycles, occupancy, Tensor Core activity, DRAM bandwidth, separate IPC serialization/bytes, and detailed transfer totals unknown when those tools do not provide evidence. Coarse GPU utilization and CUDA-event time are not presented as those metrics.

## WP1: measured worker topology

The three warmed, unprofiled high-geometry 16-shard references measured **944.45 ± 29.19 PPO-core transitions/s** (sample mean and SD). Three comparable 64-subprocess repeats measured **1,096.43 ± 12.84 transitions/s**, a **16.09%** increase against that reference. Both used seed 42, the same bundle manifest (`d85e0dc8…`), 64 logical environments, and matching PPO geometry. This is throughput evidence only; the configuration is a separate learning protocol and has not been used for training.

The profile's sampled market decision-index reuse factor was p50 **11.73**, p95 **64**. This is a synchronization/reuse lead, not proof that the complete nine-stream market observations are byte-identical. The WP2 probe below groups only exact market sequence and mask bytes.

Results and raw JSONs are retained under [`measurements/`](measurements/), especially the per-job `wp0-job-21273908`, `wp0-job-21273983`, and `wp0-job-21274098` folders.

## WP2: exact market-row reuse

A narrow inference-only prototype now separates market token encoding from per-environment account embedding and offers `forward_with_market_groups`. It refuses training/gradient mode; regular encoder behavior remains the default. Unit tests compare grouped and full-batch outputs and verify that independent account rows remain intact.

The bounded A/B (job `21274446`) reset 64 environments from the pinned shared training bundle, then advanced them for 128 simulator steps using a freshly initialized stochastic policy. It hashes both complete rollout traces and initial policy state, groups only exact market-window/mask duplicates, and compares full-policy logits/probabilities, deterministic actions, values, log probabilities, entropy, and p50/p95 inference latency at the reset, midpoint, late, and terminal observations. One arm used each GPU. It performed no PPO updates, historical replay, checkpoint writes, or cache rebuild.

Both arms observed the same source, config, initial weights, initial observations, and full 128-step observation trace. Market sequences/masks had exactly one unique row among 64 environments at every sampled vector step (reuse factor p50/p95 64). Account rows were allowed to diverge: the unique account count was p50 61.5 and p95 64. Maximum absolute differences were `2.278e-4` for intermediate features and `9.695e-5` for values; masked thesis logits/probabilities, deterministic action, log probability, and entropy differences were all below `1e-6`. All outputs passed explicit per-output absolute tolerances plus `rtol=1e-5`.

The final rerun after preserving the normal encoder `finish()` path measured four observation snapshots with 100 full-policy calls each. Baseline inference measured **10.842 ms p50 / 11.476 ms p95** per 64-environment batch. Grouped inference measured **10.547 ms p50 / 10.914 ms p95**, a **1.028x (2.7%) p50 speedup**. This excludes grouping discovery and row-index construction; it also excludes simulator IPC and PPO collection/update time. The earlier run on the initial prototype measured a 12.0% inference-only p50 reduction, but the final implementation rerun did not reproduce that magnitude. The final measured gain is below the plan's >=20% sustained PPO-core or equivalent end-to-end ROI gate. Therefore the exact grouping method stays an opt-in inference prototype; no indexed-observation interface, collector rewrite, GPU-resident market store, or training integration is justified by this evidence.

The initial-reset-only A/B (preserved in `measurements/wp2-job-21274446/initial-reset-only/`) had shown 0.96x grouped p50 speed, which motivated the rollout extension. The final 128-step trace supersedes that reset-only estimate for reuse characterization but does not establish stable throughput benefit across trained checkpoints or full rollouts. The 12.0% result from the first valid rollout A/B is retained in `measurements/wp2-job-21274446/rollout-parity-valid-original-finish/`; the published final summary uses the rerun after restoring the default encoder hot path.

**Quality gates:** Ruff format, full-tree Ruff lint, full-tree Mypy (804 source files), and 32 focused tests passed on the final probe code in the active ARM/GH200 allocation. The first gate attempts exposed typing/import issues; those were corrected before the passing gate and successful measurement. Detailed outputs and failed first-attempt logs are preserved under [`measurements/wp2-job-21274446/`](measurements/wp2-job-21274446/).

## Remaining decisions

| Work package | State | Next evidence / stop rule |
|---|---|---|
| WP0 configuration/profile | Complete | Keep missing hardware/IPC metrics explicitly unknown. |
| WP1 worker topology | Measured, directional adoption candidate | Do not infer policy or economic quality from FPS. |
| WP2 exact market reuse | Bounded inference A/B complete; prototype only | No full collector/cache integration: final rerun measured 2.7% inference-only p50 gain, excluding grouping/IPC and below the >=20% full-core ROI bar. |
| WP3 pipelined collector / device-resident rollout | Deferred | Requires a demonstrated end-to-end bottleneck and material makespan ROI; no rewrite from intuition. |
| WP4 compile/CUDA graphs | Not tested | Toolchain was absent in the previous inventory; only revisit with supported tools and measured launch-bound evidence. |
| WP5 changed PPO geometry/update budget | Not launched | Separate learning-protocol decision and quality evidence required. |
| WP6 callback-inclusive end-to-end timing | Not ready | No suitable frozen E checkpoint has been verified; do not synthesize or retrain one for this bounded plan. |

## Final evidence summary

| Measure | Observed result | Interpretation |
|---|---:|---|
| Baseline E64 PPO-core throughput | 944.45 ± 29.19 transitions/s across three warmed repeats | 16-shard reference; no train/eval callbacks or year replay. |
| 64-subprocess topology | 1,096.43 ± 12.84 transitions/s across three comparable repeats | +16.09% against the reference mean; directional throughput evidence, no policy-quality conclusion. |
| Profiled rollout / update | 23.79 s / 12.14 s in the warmup-excluded core interval | Rollout is 66.2% and update 33.8% of that interval; phase instrumentation is diagnostic. |
| Coarse GPU utilization | p50 6%, p95 88% in the profiled run | Coarse `nvidia-smi` sampling only; SM-active and occupancy remain unknown. |
| GPU memory | 14.55 GiB p95 reported used; 12.12 GiB peak PyTorch allocated | Capacity observations, not evidence of bandwidth saturation. |
| WP2 grouped inference A/B | Final 1.028x p50 (2.7%); parity gates passed | Below the plan's >=20% integration threshold; keep prototype opt-in. |
| Callback-inclusive makespan / 2M campaign | Not measured / not run | No full training result or economic-performance claim. |
| Detailed kernel, transfer, SM-active, occupancy and DRAM bandwidth | UNKNOWN | Nsight was not run in this bounded scope; no inference from coarse utilization or allocated memory. |

The profiled host traces identify rollout and worker `step_wait` as the largest observed wall-time areas, with per-worker observation construction taking most of the worker-side measured CPU time; nested method timings are not additive. The phase samples show low process-wide CPU parallelism relative to the 96-core allocation and intermittent GPU utilization. Separate IPC bytes/serialization, exact transfer totals, and a kernel-level wait timeline were not measured, so the evidence does not justify a collector rewrite, GPU-resident market store, or compile/CUDA-graph change.

The six-hour allocation limit was honored; the bounded work finished well before that limit and the interactive allocation remains open for subsequent work. No 2M campaign was launched. Implementation, report, review, commit, and branch push are complete; the pushed branch is `codex/gh200-max-fps`.
