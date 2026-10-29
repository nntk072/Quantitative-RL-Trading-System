# Codex Agent Plan — GH200 Full-Resource Pipelined PPO Refactor (Beyond 960 FPS)

**Task type:** Implementation plan and performance-engineering mandate; this document does not itself authorize new GPU allocations, modifying the existing C/D jobs, or full 2M campaigns.
**Repository:** `nntk072/Quantitative-RL-Trading-System`
**Starting branch:** `codex/gh200-max-fps`
**Verified HEAD:** `248d5b1eeeb5ae0a7817d049607e8eb8d99e28a6` (2026-10-28); recheck HEAD before implementation.
**Frozen comparison:** `main` at `3fbbb74fdbe581807df38c1feaab7307839506f5`, original C/D 8-env seed42 benchmark. Do not modify active/pending Slurm jobs, dependency `21267207`, monitors or artifacts.
**Primary objective:** **minimize time from a reproducible source/config/data snapshot to a scientifically valid, fully evaluated model**, not maximize utilization metrics. Optimize sustainable PPO-core FPS as a component of that objective.
**Stretch:** >=3,000 real PPO-core transitions/s on one GH200, with no change in trading semantics. The engineering milestone is >=1,500 then >=2,000 measured transitions/s; these are objectives, not promises. Retain a valid fallback and stop when measured return on engineering effort becomes poor.

## 0. Facts established in the pushed branch — distinguish memory capacity from compute utilization

Repository evidence:
- `docs/research/gh200_max_fps_architecture_redesign_20261028/RESULTS.md`
- `.../measurements/E64-high-baseline-repeat2.json` and `...-repeat3.json`
- `docs/research/variant_e_f_g_encoder_ablation.md`
- `learning/rl/agent.py`, `learning/rl/environment_adapter.py`, `learning/rl/rollout_buffer.py`, `learning/rl/hybrid.py`, `models/encoders/mtf_shared_tcn_reasoning.py`, `models/encoders/mtf_efficiency_common.py`, `simulation/environment/observation_runtime.py`, `simulation/environment/env.py`.

**Measured reference: E64 high geometry, not C/D.** 64 logical environments, 16 physical sharded workers (four envs stepped sequentially per worker), aggregate rollout 16,384 (256 per env), minibatch 4,096, 15 PPO epochs, one GH200 with 48 allocated CPUs and 256 GiB RAM, shared bundle, seed 42. Stable baseline repeats reached **962.23 and 960.37 PPO-core transitions/s**. For 229,376 measured transitions, baseline repeat 2 took **151.998 s in `collect_rollouts` + 86.381 s in `train` = 238.379 s**, so 63.8% rollout and 36.2% optimizer. A 3,000-FPS result on that same transition count must complete both stages in <=76.46 s: no single-phase fix suffices.

**Resource evidence:** process tree averaged ~3.35 utilized CPU cores / 48 (7.0% allocation); cgroup RAM after training ~8 GiB; peak torch-allocated HBM ~13.0 billion bytes / 153.3 billion installed (~8.5%). Neither value is proof of bandwidth or GPU SM saturation. **No E64 GPU SM-active, achieved FLOP/s, occupancy or HBM bandwidth time series is committed.** Earlier *eight-env* E/F/G profiler reports 10.6% mean sampled GPU utilization, which must NOT be called an E64 measurement. The CPU average hides phase peaks and possible single-thread critical paths. Inspect synchronized per-thread/process run/wait states.

**Negative results already established:** combined hotpath prototype (mask checks / value-logprob copies / action tensor construction) was reverted because effect was small/inconsistent; E8 reference fell from 222.3 ± 4.8 to 217.2 ± 5.7 FPS. At E64 high geometry, later unpatched repeats were ~960–962 FPS versus patch ~971–981 FPS. Avoid blind repetition. 64 separate subprocesses beat 16 sharded workers at the **fixed 2,048 aggregate** rollout (552.7 vs 521.2 FPS), but **64 subprocesses have not yet been compared at the high 16,384-aggregate geometry**. The ARM GPU node lacked `cc`, `gcc`, `clang`, `nvcc`, `ptxas`; no `torch.compile`/CUDA Graph result exists. No callback-inclusive E64 production wall clock or economic viability results exist.

**Critical config defect:** `config/research/thesis_mtf_shared_tcn_2m_high_throughput.yaml` is a standalone fragment loaded against `config/base/default.yaml`. It is **NOT inherited from** `config/research/thesis_mtf_shared_tcn_2m.yaml`; if launched alone it resolves to default `agent.arch=tcn`, `ppo.policy_distribution=clamped_diagonal_gaussian`, `env.thesis_actions=false`, etc., instead of Variant E. Recorded successful high-geometry profiles loaded the ORIGINAL E config and passed runtime overrides. Fix this before training and add complete resolved-config equivalence tests.

## 1. Hard scientific invariants and explicit equivalence classes

- **Simulation parity (mandatory):** the same market timeline and split, 109-way eligible-thesis mask with always-eligible NO_TRADE, causal M1–D1 windows, action encoding/decoding, filled quotes and latency (tick/bar), risk and FTMO rules, SL/TP references (including allowed lower-timeframe TP), partial exits, stop state, reward, termination and chronological reports. Baseline `TradingEnv` remains the oracle.
- **Policy inference parity (for exact efficiency changes):** same trained weights, `eval()` mode, logits, deterministic action, masked probabilities, sampled-action distribution, values and log-probabilities within declared numeric tolerances. Inference-time reuse must not leak across policy-weight versions or training-mode dropout.
- **PPO math parity (for exact learner rewrites):** unchanged 15 epochs, same aggregate rollout/mini-batch schedule where claiming equivalence, complete GAE episode/truncation semantics, exact hierarchical entropy, correct gradients, advantage normalization and optimizer bookkeeping. Numerical equivalence may not imply bitwise identical stochastic trajectory; report tolerance and RNG differences.
- **Learning-protocol changes (separate treatment):** changes in `n_envs`, batch, rollout, epochs, critic/actor structure, replay order or asynchronous stale-policy training create a NEW training protocol. Compare on training-only 2025 development data; 2026 is already exposed and report-only. Never call changes equivalent or economically viable on the basis of FPS alone.
- Preserve each source, config, resolved-config, action schema, bundle manifest and checkpoint hash and document their provenance. Never overwrite C/D frozen evidence.

## 2. Design principle: feed the critical path rather than simply consume every available core

Current SB3 path is effectively GPU inference -> CPU environment step -> CPU observation assembly/IPC -> GPU inference, repeated for 256 vector steps, then GPU PPO `train()` while workers wait. The 16 shards step four envs each in a Python `for` loop. Setting OMP/BLAS to 48 on every worker would oversubscribe threads; blindly making 48 busy cores can worsen end-to-end time. Similarly, filling HBM with unused tensors increases memory occupancy without improving GPU utilization. A new pipeline should minimize idle intervals, repeated market work, CUDA synchronizations and GPU kernel launch count.

**Preferred target architecture:**

```
Immutable historical bundle (market features + causal window/eligibility indices)
       |                                   |
       +--> GPU-resident market store      +--> CPU reference market store
                 |                                         |
  keyed market encoder cache                        CPU execution workers
  (policy-version, bar-index)              32/48/64 workers or active cohorts
                 |                                         |
                 +---- batch broker / async queues <-------+
                           |         ^
              market representation + live account
                           |
              frozen-policy action/value inference GPU
                           |
              packed actions -> CPU simulator groups
                           |
              GPU-resident on-policy rollout + small CPU metadata
                           |
                strict end-of-rollout policy barrier
                           |
              optimized 15-epoch PPO learner on GPU
                           |
             policy version++ / invalidate representation cache
```

**Critical concurrency rule:** environment cohorts may execute CPU stepping concurrently with inference for *other cohorts* while all use the SAME frozen policy version. Do not perform an optimizer update that changes the acting policy while a batch from the old policy remains outstanding unless building a separately approved asynchronous importance-corrected algorithm. Full PPO optimization stays behind a collection barrier. Always preserve per-env chronological order and map each returned action to its originating observation/sequence number.

## 3. WP0 — Correct config and define measurable performance anatomy (required before redesign)

1. Recheck branch HEAD; read `AGENTS.md`, `.agents/rules/triton-slurm.md`, and latest benchmark results. Do not create/alter allocations or jobs during code implementation; respect 2-GH200 aggregate cap, no short Slurm steps, existing allocation/monitor preservation. Benchmark only on permitted existing allocation, or request explicit allocation approval separately.
2. Fix `config/research/thesis_mtf_shared_tcn_2m_high_throughput.yaml`: make it a complete independent E overlay copied from the proven E baseline, with only `env.n_envs=64`, `env.data_source=bundle`, backend/shards, `ppo.n_steps=16384`, `ppo.batch_size=4096`, and `quality_execution.requested_n_envs=64` changed. Preserve agent ID, conditioned distribution, thesis actions, MTF and strategy context, feature options, risk, reward, execution, training split, callback cadence and `compute.cudnn_benchmark=false`. Alternatively implement explicit inherited overlay syntax with tests; do not invent inheritance in a loader that lacks it.
3. Add a config diff test: resolve baseline E and high E via exactly the production CLI loader; recursively compare fields, assert *only* documented geometry/backend changes; instantiate a model + actual vector env and assert 64 envs, model `n_steps=256`, aggregate 16,384, 4096 batch, 15 epochs, `ThesisConditioned...Policy`, 109 thesis categories and same simulator contracts.
4. Extend `scripts/research/benchmarks/measure_ppo_throughput.py` with lightweight NVTX ranges and phase timers, not unbounded profiling: device inference forward, env dispatch, worker step, worker wait/serialize, worker observation construction, parent observation stack, H2D/D2H copies, mask sync, buffer.add, GAE, per-minibatch forward/backward/optimizer, true CUDA wait, callbacks, checkpoint and replay. Use CUDA events and explicit sync only at measurement boundaries, not every iteration in the production path. Record p50/p95 per-vector-step latency and unique decision indices per batch. Compare measured phase sum with wall time (avoid double counting).
5. If installed and permitted, collect Nsight Systems (`nsys`) GPU timeline with CUDA/NVTX/OS runtime and NVIDIA GPU performance metrics. Use `nvidia-smi`/NVML sampling as a secondary coarse source. Measure SM Active, SM Occupancy, Tensor Core activity, DRAM throughput and PCIe/NVLink transfers if tools permit. `ncu` metrics may require administrator privileges; never change cluster permissions. If not available, explicitly mark metrics UNKNOWN; do not infer utilization from `memory.used`.
6. Record per-process/thread CPU busy/wait, total process CPU-seconds, CPU affinity, effective allocated CPU quota, context switches, IPC bytes, CPU run queue, RAM pressure/faults and bandwidth where supported. Sample *during rollout* and *during updates* separately: average 3.35/48 is not a phase-specific diagnosis.
7. Reuse the three committed, warmed E64 high-geometry baseline runs when their seed, bundle, and resolved geometry match. The current artifacts already meet that condition. Run one short instrumented phase profile and one 64-subprocess comparison, each capped at 65,536 requested steps (four rollouts, two excluded as warmup). The two fresh cases total 131,072 requested steps. Skip a separate Nsight rerun to keep the resource check short; use the profile's coarse GPU telemetry and mark SM-active/transfer metrics UNKNOWN. Treat the single topology comparison as directional only; do not adopt a performance change without adequate repeats and a material end-to-end gain. Keep profiled and unprofiled runs separate. Give every new output source/config/manifest hashes and clean/dirty patch identity.

**Gate:** accurate wall-time attribution, reported actual GPU utilization or explicit inability to measure, and correct E64 config. No blanket architecture rewrite before this gate.

## 4. WP1 — Use existing CPU parallelism first: 16 vs 32 vs 48 vs 64 workers

1. Reuse the existing 16-shard E64 high-geometry baseline and compare one short 64-subprocess run at the same logical env count, rollout, batch, epochs, seed and bundle. The prior fixed-aggregate result favored 64 subprocesses by 6%, but does not predict high-geometry behavior. The short comparison is directional; do not claim or adopt a winner from one pass.
2. The 32/48-shard sweep is deferred to a separately justified repeat because the current objective is a minimal measurement, not an exhaustive worker search. Existing runs already establish that 16 shards are a valid lower-RAM option. `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1` remain set; pin affinity only if future measurements show a benefit.
3. Measure per-worker busy time and serial fraction in `learning/rl/environment_adapter.py::_shard_worker`: each shard loops over four envs serially. Separate time spent calculating state, constructing 9 market windows, serializing observations and waiting on GPU inference.
4. If >10% core speedup or materially lower rollout p95 without correctness regressions, select the winning topology. Keep the rest intact. Do not use more CPU worker count to intentionally consume cores when latency or memory costs outweigh gains.

## 5. WP2 — Highest-potential exact redesign: market-index observations and reusable market encoding

This is the recommended large refactor **if profiler proves repeated market inference/observation transfer is material**.

1. Split `_get_observation` into (a) static market content: exact 9 windows/masks, session-scoped M1, completed HTF alignment, static 109-way thesis eligibility; (b) dynamic account state. Store immutable market feature matrix and compact causal index tables keyed by bundle identity, bar index, schema and session. Precompute only where cost/size warrants. Start with a static feature matrix + index tables rather than materializing ~9.2 GB of repeated full windows.
2. Add an *opt-in* `IndexObservation` interface for the custom collector: market decision bar index, live normalized account, permitted static thesis mask index, per-env timestep and termination metadata. Keep the existing full Gymnasium observation interface intact for reference tests, evaluation compatibility and fallback.
3. Stage feature matrix/index tables once on GH200 (or use efficiently pinned host staging if full GPU residency is slower). The parent collector reconstitutes identical float32/BF16 input arrays on device using causal `gather`. Avoid repeated worker-to-parent IPC of 9 large windows on every vector step. Never cache positions, account equity, risk limits or action-dependent state.
4. **Deduplicate market-only encoder inference**: source confirms `MTFReasoningOutput.finish()` computes 128-D market embedding independent of the account's separate 32-D AccountMLP. During rollout, encoder is in `eval()` and policy weights are frozen. Collect the unique bar indices from the cohort, compute market embedding once per distinct index, then expand/gather to every account-specific actor and critic input. Key cache by (policy version, bar index, data bundle/schema) and invalidate at each optimizer update. Do not cache during dropout-enabled gradient training; encoder activations/gradients change per optimizer step.
5. Quantify actual duplicate rate: distribution of unique bar indices per 64-env vector step and cache hit ratio over a rollout, including reset and account-breach divergence. Same reset starting index does NOT prove all envs remain synchronized throughout the year. Require a measured median market reuse factor (e.g., >=4) or positive measured speed gain before retaining complexity.
6. Preserve fixed-action traces exactly: old full observation vs new indexed representation at session open/close, HTF rollover, sparse missing masks and partial days; compare all nine windows, masks, selected thesis, action logits, value predictions, fills/quotes, equity, rewards and violation records. Test 2025 full-calendar indexed equality with reference when feasible and representative 2026 report-only samples. Any mismatch is a stop.
7. Implement memory-bounded cache eviction, invalidation, rollout version tagging, reproducible deterministic seed handling and metrics. Benchmark the parts individually: (a) indexed static gathering, (b) unique-index encoder inference, (c) combined path. Reject the combined rewrite if it does not produce >=20% sustained PPO-core improvement or meaningful callback-inclusive wall savings.

**Watchout:** eager full-year embedding precompute once at run start is WRONG for a trainable encoder: weights change. Per-rollout caching or per-frozen-checkpoint evaluation precomputation is valid.

## 6. WP3 — Concurrent cohort actor/learner, on-policy barrier and GPU-owned storage

Build only after WP2 reveals pipeline idle gaps or data movement as dominant remaining costs.

1. Implement worker processes as persistent cohorts with bounded producer/consumer queues, sequence IDs, policy-version IDs and deterministic action routing. Use nonblocking requests so GPU can infer cohort B while CPU steps cohort A. The learner assembles batches from ready cohorts; use a configurable batching cap and short latency deadline to balance GPU batch size vs queue wait. Preserve each env's order, episode resets and complete rollout accounting.
2. Provide a *strict barrier*: accumulate the same required transition count under the same policy version, finish outstanding CPU actions, complete GAE, then execute 15 PPO epochs; thereafter atomically increment policy version and clear market cache. No stale-policy update overlap. New actor concurrency may change the order of RNG draws, so distinguish policy-function parity from bitwise trajectory equality; explicitly test reproducibility and seed behavior.
3. Specialize the learner to consume indexed observations and `account` vectors directly, with GPU-resident action, log-prob, value, return, advantage and static-index storage. A single packed action transfer per cohort to the CPU simulator is required. Stage rewards/dones in batches. Preserve truncation bootstrap and the reference SB3 GAE math, including update-time learning rate schedule and optimizer state.
4. Initially keep SB3 PPO as the reference oracle. Test a small fixed synthetic rollout, compare stored actions, log-probs, values, advantages, returns, minibatch gradients, approximate KL, entropy, clip fraction and optimizer updates. Use finite tolerances and report any changed stochastic ordering. A custom PPO collector/training loop may be required; do not misrepresent this as a trivial buffer swap.
5. Benchmark queue wait, policy inference batch occupancy, GPU idle gaps, worker busy/wait and core throughput. Reject if worker/queue overhead overwhelms benefits. Consider pinned host memory and double buffers, but do not presume host->GPU transfer is dominant until measured.
6. Optimize for minimum total wall time; do not force artificial 100% CPU busy. During GPU PPO epochs, safely preprocess next static market indices or finish non-GPU checkpoint serialization, **but do not collect new policy actions under old weights and call them on-policy**.

## 7. WP4 — Drive GPU computation efficiently, not just GPU memory usage

1. Provision a supported ARM64 C/C++ compiler and PyTorch-compatible Triton/Inductor toolchain via approved cluster modules or isolated node-local environment. The benchmark proves toolchain missing on the recorded node, not that `torch.compile` is inherently slow. No unapproved system-wide installation; do not modify active C/D checkout or Slurm allocation.
2. Profile GPU kernel launches, `.item()`/`bool(mask.any(...))` syncs, tensor creations and `self.mask.nonzero(as_tuple=True)` dynamic-shape entropy in `learning/rl/hybrid.py`. Capture p50/p95 GPU-inference and 4,096-batch update time. Distinguish GPU-active time from CPU kernel-dispatch gaps.
3. Compile static-shape tensor-only encoder / actor / critic; try `torch.compile` default, `reduce-overhead`, and supported CUDA graph capture with fixed inference batch sizes (cohorts can pad to a known maximum and mask, only after parity). `TORCH_LOGS=graph_breaks,perf_hints`. Monitor compilation overhead, graph breaks, memory addresses/lifetime, dropout/RNG, dynamic mask semantics, and BF16/FP32 drift. Select only net-positive A/B results including warm-up amortization over a 2M run.
4. For exact conditioned entropy, replace dynamic sparse `nonzero` only if an **exact** differentiable alternative is confirmed faster. Candidate: fixed-size eligible-ID lists with padding and overflow fallback that covers EVERY valid candidate; masked expected-conditional entropy must use true thesis probabilities, without dropped categories. Never approximate entropy or retain only the selected thesis in a purported equivalent baseline.
5. Evaluate `torch.nn.utils.parametrize.cached()` around shared TCN weight normalization only if profiling confirms parameter-materialization overhead; verify gradients and checkpoint compatibility. Avoid inventing additional TCN branches.
6. Benchmark minibatch sizes 4,096 / 8,192 / 16,384 and only **separately versioned new PPO geometry** for any training-condition change; compare update rate AND quality. Do not state different minibatches produce identical learning trajectory. Keep exact 15 epochs in the equivalence lane.
7. If CPU dispatch remains dominant, optimize the entire fixed-shape PPO minibatch operation (forward, exact distribution, losses, backward, clipping and optimizer) as one coarse compiled region only where supported; verify gradients, RNG and optimizer-state behavior. This is more consequential than isolated scalar-copy edits.

## 8. WP5 — Further algorithmic throughput lane ONLY if acceptable quality survives

1. After exact-pipeline enhancements, screen 64 and 128 logical envs with matched per-env horizon where possible; verify host limits, worker/shard selection, GPU inference batch size and changes in sample correlation. 64 envs observing the same 2025 market do not represent 64 independent market datasets.
2. Optional 15 -> 10 -> 5 PPO epoch study, with unchanged total transitions and declared optimizer budget. Epoch reduction can substantially reduce wall time, but changes the update rule and may degrade survival and policy quality. Label a new algorithmic treatment, NOT the same-policy optimization.
3. Optional 4,096 -> 8,192 or 16,384 minibatch study and rollout changes, comparing learning stability and sample efficiency. Avoid cherry-picking on exposed 2026. Do not select speed winners purely by FPS.
4. Multi-GH200: for two nodes, independent seeds/variants or separately scheduled evaluation are natural throughput scaling uses; model/data-parallel training of a ~1.3M-param policy may be network/synchronization dominated. Require empirical speedup and obey existing user resource caps. Do not touch C/D GPU jobs without separate approval.
5. A fundamentally new compact encoder or frozen encoder is a new architecture/learning experiment. It may yield more FPS but cannot be called the exact same policy behavior. Keep it a separate branch/config and quality gate.

## 9. WP6 — Evaluation must stop dominating the complete experiment

1. Record callback-inclusive end-to-end breakdown: training startup, 20 dashboard 20k-bar calls, best-prefix ranking, checkpoints, training-calendar 2025 replay, exposed 2026 report-only replay and artifact export. Existing 0.55h dashboard + 1.06h final-replay allowances for E were eight-env planning estimates, not measured E64 facts.
2. For each *frozen checkpoint*, encode the static M1–D1 2025 market representations in large batches on GPU once per checkpoint, with causal index/mask exactness. Then use GPU market-token lookup + per-step live account MLP/action head while CPU simulator processes the chronological events. A frozen checkpoint's market representation does NOT depend on the account; do not precompute actions because those depend on account and risk.
3. Where many evaluators reuse the exact same checkpoint, share its immutable market embeddings across dashboard prefix and split replay. Invalidate on checkpoint version change. Batch precompute only once per model version when cost savings beat setup overhead.
4. Keep the dashboard's `_apply_prior_interval` effect on training intact; it is coupled to behavior. Never silently defer, remove or alter prior activation merely to speed reporting. If evaluation schedule changes, record a new research protocol and validate RNG/model-selection consequences.
5. Same checkpoint, seed, action mode, train-only ranking, report-only 2026, trade ledger, stop/target and risk metrics must reproduce reference within declared tolerance. Export full report even if training FPS is high.
6. Report true makespan and GPU-hours consumed, not just model.learn throughput; reject an 'improvement' that speeds core PPO but slows required evaluations.

## 10. Quantitative targets, attribution and acceptance

For measured 229,376 transitions, stable E64 `rollout=151.998s`, `update=86.381s`, total 238.379s => **962.23 FPS**. The following time budgets are *required totals*, not claims of feasibility:

| Target | Total allowed | One illustrative phase budget (rollout / update) | Core time for 2M |
|---|---:|---:|---:|
| 1,500 FPS | <=152.92 s | 95 s / 57.9 s | 22m 13s |
| 2,000 FPS | <=114.69 s | 68 s / 46.7 s | 16m 40s |
| 3,000 FPS | <=76.46 s | 45 s / 31.46 s | 11m 07s |

These required reductions are significant: the 3,000-FPS illustrative budget needs rollout improvement **3.38×** and PPO-update improvement **2.75×** relative to baseline repeat 2. It may prove infeasible at identical 15-epoch PPO math on this model. If so, report the measured roofline/critical path; do not misrepresent a different 5-epoch learner as an exact 15-epoch speedup.

**Work-package adoption:** use three warmed repeats at exact production geometry, compare mean ± sample SD, require >=10–15% reproducible PPO-core improvement OR comparable verified end-to-end savings, correct numerical semantics, and no new non-finite/invalid-thesis failures. For expensive rewrites demand >=20–30% sustained gain and a positive makespan ROI. Reject optimizations failing scope parity even when faster.

**Policy-quality gate:** finite PPO diagnostics and correct checkpoint roundtrip; 109-way eligibility mask, zero invalid thesis selections, no structural SL/TP errors (lower-TF TP is valid), thesis diversity and eligible NO_TRADE rate, train-2025 completed trades, profit factor, max drawdown, risk breaches and account survival; 2026 report-only; no assertion of profitability from short throughput probes. Keep distinct metrics for simulation correctness vs survival vs economic failure.

**Operational gate:** full-tree `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `.venv/bin/mypy .` and scoped `pytest` per `AGENTS.md`; no change to C/D hashes, active Slurm job `21264865`, pending `21267207`, persistent monitor, or external scratch launch files. No short new Slurm jobs/steps, no `scancel`, no overlapping GPU allocations; no 2M training without separate explicit GO.

## 11. Expected agent deliverables

1. A concise benchmark-first report containing **actual E64 SM/GPU utilization measurement**, full CPU process/thread wait decomposition, GPU kernel/transfer timeline and ranked wall-clock bottlenecks. Unknown metrics explicitly recorded, not invented.
2. Config fix and regression proof for true E64 thesis-conditioned identity.
3. A working fast-path `IndexObservation`/market-store implementation behind an opt-in feature flag, if justified by measured ROI, with reference parity and memory report; safe fallback to legacy.
4. A working on-policy, pipelined multi-cohort actor/learner only if its strict PPO barriers, timing and tests prove beneficial. Otherwise preserve the simpler faster solution.
5. Individual A/B reports for alternative workers, shared market cache, compilations, rollout data handling, optimizer changes and evaluation. Track adoption/rejection with proof, not intuition.
6. Correct C/D lineage protection and independently versioned E64 artifacts. Source+resolved-config+bundle+checkpoint manifests.
7. A final table: baseline and best **end-to-end result time**, PPO-core FPS, rollout vs update seconds, true SM/CPU utilization, HBM/RAM, numerical parity, training-quality status, and any remaining bottleneck with next best ROI.
8. Stop and request explicit authorization before a full 2M research run or any resource change; completing bounded engineering tests does not establish economic viability.

## Sources

- https://github.com/nntk072/Quantitative-RL-Trading-System/tree/codex/gh200-max-fps
- https://github.com/nntk072/Quantitative-RL-Trading-System/blob/248d5b1/docs/research/gh200_max_fps_architecture_redesign_20261028/RESULTS.md
- https://github.com/nntk072/Quantitative-RL-Trading-System/blob/248d5b1/docs/research/gh200_max_fps_architecture_redesign_20261028/measurements/E64-high-baseline-repeat2.json
- https://github.com/nntk072/Quantitative-RL-Trading-System/blob/248d5b1/learning/rl/environment_adapter.py
- https://github.com/nntk072/Quantitative-RL-Trading-System/blob/248d5b1/models/encoders/mtf_efficiency_common.py
- https://github.com/nntk072/Quantitative-RL-Trading-System/blob/248d5b1/learning/rl/hybrid.py
- https://docs.nvidia.com/nsight-systems/AnalysisGuide/
- https://docs.pytorch.org/docs/stable/generated/torch.compile
- https://docs.nvidia.com/dl-cuda-graph/latest/troubleshooting/performance-issues.html
