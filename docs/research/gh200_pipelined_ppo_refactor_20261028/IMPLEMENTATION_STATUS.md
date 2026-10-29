# GH200 Pipelined PPO Refactor: Current Status

**Updated:** 2026-10-29
**Implementation branch:** `codex/gh200-max-fps`
**Baseline commit:** `248d5b1eeeb5ae0a7817d049607e8eb8d99e28a6`
**Plan:** [`../GH200_FULL_RESOURCE_PIPELINED_PPO_REFACTOR_PLAN_2026-10-28.md`](../GH200_FULL_RESOURCE_PIPELINED_PPO_REFACTOR_PLAN_2026-10-28.md)

## Scope and preservation

This is bounded throughput and collector-feasibility work, not a 2M training or economic benchmark. No 2M run has been launched. The requested WP3 comparison completed in allocation `21274889` on `gpuarm1` with one GH200, 96 CPUs, 512 GiB host RAM, and the corrected ARM environment. Allocation `21274810` remains open with one GH200, 48 CPUs, and 256 GiB; it was too small for the required 64-env geometry, so the repository guard correctly stopped its smoke before training. The additional allocation brought the total to two GH200s on one node, within the approved cap; only one GPU ran the benchmark. `gpuarm2` is down. The main checkout and its untracked `campaign_worker_dispatch.log` remain untouched.

The first WP3 test command in `21274446` used a nonexistent branch-local `.venv/bin/python`; the activation shell's `errexit` released that allocation. No `scancel` was issued. The error and recovery are preserved in the WP3 measurement directories. The later undersized 256-GiB allocation `21274810` failed closed at the exact-geometry memory guard (`64` requested, `32` estimated capacity); no PPO run started there. The corrected `21274889` allocation satisfies the repository's 64-worker RAM tier.

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

## WP3: bounded cohort-pipeline feasibility

The user's WP3 request was a feasibility experiment, not permission for a production collector rewrite. The benchmark-only dispatcher splits each stock PPO policy forward into contiguous 32- or 16-env cohorts and sends each cohort's actions immediately. While cohort A's subprocesses step on CPU, the GPU infers cohort B. The stock SB3 collector, response ordering, reward/transition insertion, GAE, and update barrier remain in place.

Correctness smoke passed on the pinned E64 bundle: all **16,384/16,384** sampled thesis selections were valid under their observation masks; invalid selections and noncategorical thesis centers were zero; the raw actions matched PPO's rollout buffer exactly; all 256 vector-step responses retained 64 observation/reward/termination rows; rewards and GAE were finite; one policy version covered the full rollout; and PPO performed one update after the completed buffer. The full report and raw JSON/log evidence are under [`measurements/wp3-job-21274889/`](measurements/wp3-job-21274889/).

Three paired-seed, warmed PPO-core repeats included full rollout collection and PPO updates. Sequential 64 measured **1,166.44 ± 20.62 transitions/s**. The 2×32 prototype measured **919.51 ± 36.95/s**, **21.17% slower**. The optional 4×16 prototype measured **667.72 ± 14.55/s**, **42.76% slower**. Earlier CPU stepping overlapped later cohort inference for an average **46.44%** of 2×32 inference time and **41.76%** of 4×16 inference time, but smaller-batch inference and dispatch costs outweighed that overlap. This is repeatable negative throughput evidence against the ≥20% adoption criterion.

The explicit step-wait gap, worker-step latency, parent-side IPC counters/bytes/latency, and coarse GPU utilization are included in the report. Coarse GPU utilization is not SM-active time; Nsight occupancy/transfer/bandwidth metrics remain unknown.

## Remaining decisions

## Revised optimization priorities (user-directed, 2026-10-29)

The WP3 measurement changes the next-work order. Keep this as a staged
optimization sequence; do not treat the three lanes as one combined change.

| Priority | Work | Decision / acceptance evidence |
|---:|---|---|
| 1 | Compact observation transport | **Measured; no integration.** A lossless row-index prototype reduced parent receive bytes by 98.02% but reduced PPO-core throughput by 5.32% across three paired seeds. The 20% ROI gate was not met. |
| 2 | WP4 GPU policy/PPO optimization | **CUDA Graph policy-forward candidate measured.** Three matched full-batch repeats passed the benchmark's eager-output parity checks and improved PPO-core throughput 28.30% ± 1.13 pp. Production training/checkpoint integration is not validated. |
| 3 | WP5 PPO geometry | **Throughput-only screen complete.** 10 epochs gained 17.29%; 5 epochs gained 40.76%. These change optimizer budget; no learning-quality comparison was run, so neither is promoted. |
| Defer | WP3 cohort pipeline | Three repeats showed 2x32 at -21.17% and 4x16 at -42.76% versus sequential 64. Keep its feasibility prototype and evidence; no production collector rewrite. |
| Defer | Full GPU-native simulator | Too much engineering for the current evidence. Revisit only if compact transport and full-batch GPU optimization leave a measured, material bottleneck that this would address. |

The 7.87 GB figure is the cumulative parent-side receive-buffer total for the
profile interval, not a measurement of serialization CPU time or unique market
information. The WP2 exact-market inference experiment showed market-row reuse,
but did not test reducing worker-to-parent IPC bytes.

Initial attribution from the same profile's observation schema is promising:
each environment response contains 23,378 float32 values (93,512 raw bytes).
The explicitly per-environment `account` vector is only 24 bytes; the `seq`,
eight HTF streams and masks, and `thesis_mask` comprise 99.974% of raw array
bytes and are candidates for sharing when their source market index matches.
Across 81,984 receives, the arrays alone would be 7,666,487,808 bytes versus
the measured 7,870,044,191-byte transport total. This is a schema-based
estimate, not a measured wire breakdown or proof that all market fields match
on every step. WP2 found exact market-stream reuse in its sampled rollout. The
compact transport A/B below tested that prototype over the full bounded profile
and found no end-to-end benefit.

The direct transport A/B used the same 64-subprocess topology and 81,920
transitions per run (two warmups plus three measured rollouts), with paired
seeds 42/43/44, the pinned bundle and identical PPO geometry. Hash validation
passed for every reconstructed market response in the 16,384-transition
correctness smoke. Timed parent receive bytes fell from **7.869 GB** to
**155.4 MB** on average (**-98.02%**), while measured PPO-core throughput
including rollouts and updates fell from **1,155.57 ± 9.83** to
**1,094.03 ± 10.12 transitions/s** (**-5.32%**, negative in all three seed
pairs). The parent rebuilds each unique market row and stacks observations;
that work outweighs transport savings in this path. Retain the prototype and
exactness tests, but do not integrate it into training. Detailed pickle CPU
time and link bandwidth remain unmeasured.

Full raw runs, the validation smoke and the generated report are retained in
[`measurements/compact-obs-job-21274889/`](measurements/compact-obs-job-21274889/).

| Work package | State | Next evidence / stop rule |
|---|---|---|
| WP0 configuration/profile | Complete | Keep missing hardware/IPC metrics explicitly unknown. |
| WP1 worker topology | Measured, directional adoption candidate | Do not infer policy or economic quality from FPS. |
| WP2 exact market reuse / compact transport | A/Bs complete; no training integration | Grouped inference gained 2.7% inference-only p50; compact transport cut IPC bytes 98.02% but lost 5.32% PPO-core throughput. Neither meets the >=20% full-core ROI bar. |
| WP3 cohort pipeline | Feasibility measured; production rewrite not recommended | Two-cohort and four-cohort pipelines were 21.17% and 42.76% slower than sequential 64 across three warmed paired seeds. Keep the prototype as evidence; do not implement the production collector under the current ROI gate. |
| WP4 GPU policy/PPO optimization | Bounded CUDA Graph probe passed; production integration deferred | Full 64-env inference batch and 4,096 PPO minibatch retained. Three paired repeats measured +28.30% ± 1.13 pp PPO-core speed with eager/compiled output parity. The change is benchmark-only; checkpoint and production campaign integration remain unverified. |
| WP5 changed PPO geometry/update budget | Throughput screen complete; quality gate open | Three seeds each at 10 and 5 epochs measured +17.29% and +40.76% speed over 15 epochs. These are new learning protocols. No financial-quality, survival, or sample-efficiency claim was measured. |
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
| WP3 sequential 64 core throughput | 1,166.44 ± 20.62 transitions/s | Three warmed paired-seed repeats; includes rollout collection and PPO updates. |
| WP3 2×32 pipelined core throughput | 919.51 ± 36.95 transitions/s (-21.17%) | Correctness smoke passed; negative ROI means no production collector rewrite. |
| WP3 4×16 pipelined core throughput | 667.72 ± 14.55 transitions/s (-42.76%) | Optional topology also slower; no adoption. |
| WP3 earlier-CPU-step / later-inference overlap | 46.44% for 2×32; 41.76% for 4×16 | Measured overlap exists but does not translate into PPO-core speedup. |
| WP4 CUDA Graph policy-forward A/B | 1,482.49 ± 0.58 transitions/s; +28.30% ± 1.13 pp paired | Three seeds; deterministic outputs match within `1e-5`; maximum observed entropy difference was 4.77e-6; mean compile warmup 10.91 s. Benchmark-only; not wired into production or checkpoint loading. |
| WP5 10 PPO epochs | 1,355.23 ± 20.87 transitions/s; +17.29% ± 2.25 pp paired | Throughput-only; 120 measured optimizer steps per run vs 180 at 15 epochs; learning quality not assessed. |
| WP5 5 PPO epochs | 1,626.52 ± 25.94 transitions/s; +40.76% ± 2.68 pp paired | Throughput-only; 60 measured optimizer steps per run vs 180 at 15 epochs; learning quality not assessed. |
| Callback-inclusive makespan / 2M campaign | Not measured / not run | No full training result or economic-performance claim. |
| Detailed kernel, transfer, SM-active, occupancy and DRAM bandwidth | UNKNOWN | Nsight was not run in this bounded scope; no inference from coarse utilization or allocated memory. |
| Final-tree quality gate | PASS | Full-tree Ruff format/lint, Mypy (812 source files), and 34 focused benchmark tests passed on the ARM GH200 environment. Logs are in `measurements/quality-gate-job-21274889/`. |

The profiled host traces identify rollout and worker `step_wait` as the largest observed wall-time areas, with per-worker observation construction taking most of the worker-side measured CPU time; nested method timings are not additive. WP3 measures parent-side transport buffers and CPU/GPU cohort overlap, but not pickle encode/decode CPU, SM-active utilization, occupancy, exact device transfers, or DRAM bandwidth. Despite measured overlap, both pipeline variants are slower end-to-end. Compact transport also loses end-to-end despite its byte reduction. CUDA Graphs improve the bounded policy-forward benchmark with output parity, but production integration, checkpoint save/load, and full campaign makespan remain unverified. Reduced epoch counts improve throughput while changing the optimizer budget; learning quality remains unmeasured.

Both six-hour allocations remain available at the latest scheduler check; no allocation was cancelled. No 2M campaign was launched. WP3 feasibility, compact transport, WP4 CUDA Graph, and WP5 geometry code and bounded evidence are ready for final diff review. Full-tree Ruff/Mypy and the required commit gate remain outstanding.
