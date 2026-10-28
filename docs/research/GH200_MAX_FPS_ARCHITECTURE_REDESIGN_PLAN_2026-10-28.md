# Codex / GH200 Maximum-Throughput Architecture Plan

**Status:** Planning only; no implementation, GPU work, Slurm actions, or authorization to start experiments.
**Authorization update (2026-10-28):** The user subsequently approved full implementation and benchmarking of this plan, including a separate branch/config and GPU probes. This later approval supersedes the initial planning-only status. The matched C/D successor `21267207` remains held until this redesign is complete. The C/D baseline checkout remains unchanged.
**Repository:** `nntk072/Quantitative-RL-Trading-System`
**Evidence baseline:** `main` at `3fbbb74fdbe581807df38c1feaab7307839506f5` (2026-10-28). Re-verify HEAD before implementation.
**Priority:** Minimize verified end-to-end wall-clock time to a valid, evaluated checkpoint, then improve sustained PPO-core steps/s.
**Important:** The already approved matched C/D 8-env benchmark remains frozen. All work below is a separately versioned optimization branch/config/probe until expressly approved. Do not disturb existing Slurm jobs, allocations, monitors, checkpoints, evidence or user-owned untracked files.

## 1. Verified evidence (do not replace with conjecture)

- Two 65,536-step 8-env PPO-core repeats, same bundle/geometry: D `81.90 +/- 2.41` transitions/s, E `209.16 +/- 1.01`, F `184.82 +/- 7.20`, G `199.11 +/- 9.95`. Core-only; no production callbacks.
- On E, 65,536-step average wall 314.04 s: rollout/framework 215.65 s, PPO updates 78.09 s, remainder ~20.30 s. Maximum if **all** but unchanged update time disappeared = `65536 / 78.09 = ~839 steps/s`. Not a hardware bound; changing geometry/optimizer removes this bound.
- On E, 8-observation forward median 10.88 ms; 512-observation forward+backward median 25.81 ms; ~394 kernel launches per 512-row forward. D: 44.71 ms, 278.16 ms, ~3,214 launches. These are encoder CUDA-event probe values, not end-to-end inference wall time.
- The old 3,813 steps/s A3 benchmark was a *different, smaller policy* using 64 envs and larger minibatches; it does not predict E/D performance.
- The original C/D code's nine-stream TCN and `_encode_valid_suffix` dominate profiled runtime. E already eliminates most independent TCN duplication.
- `learning/rl/rollout_buffer.py::_single_copy_add` calls `.cpu().numpy()` independently on `value` and `log_prob` each vector step; full observations stay in a NumPy rollout buffer and are copied into a CUDA buffer for PPO updates.
- `learning/rl/hybrid.py`: both thesis policy distributions have `bool(mask.any(dim=1).all())` within a CUDA hot path. D entropy uses dynamically-sized `self.mask.nonzero(...)`. E inherits D's thesis-conditioned distribution.
- `simulation/environment/observation_runtime.py::_get_observation` creates M1 and eight HTF windows every step. `simulation/environment/observations.py::closed_window` uses index search, column selection, `nan_to_num`, padding. Some static work is repeated across envs and across overlapping HTF intervals. Account state remains action-dependent and **cannot be cached as static**.
- `learning/rl/agent.py::build_vector_env` has SubprocVecEnv, DummyVecEnv and ShardedBundleVecEnv; `sharded_bundle` requires bundle data source and defaults to min(8, n_envs) physical shards. A 64-env/16-shard experiment must explicitly set `vector_shards: 16`.
- `learning/rl/agent.py::build_agent` interprets `cfg.ppo.n_steps` as aggregate transitions, dividing by n_envs for SB3. Therefore 64 envs + aggregate rollout 16,384 means 256 steps/env.
- Historical `torch.compile`/CUDA Graph attempt was blocked at setup by an unavailable C compiler on the ARM GPU-node toolchain. Recheck environment rather than assuming this is still true or claiming compilation fails for mathematical reasons.
- E callback-inclusive 2M planning (not a result): 2.77 h PPO core + 0.55 h dashboard evaluations + 1.06 h final replay allowance + 25% reserve = ~5.48 h. Evaluation costs will become relatively dominant if PPO accelerates.

## 2. Define three distinct equivalence levels

**Level 1 — same simulator semantics (mandatory):** Same chronological data, exact causal visibility, feature normalization, 109-category thesis identity/masks, action encoding/decoding, fills, tick timing, spread/slippage, SL/TP, account/risk/FTMO limits, rewards, termination and reporting. For a fixed valid action sequence and seed, require exact discrete decisions, event provenance and tight tolerance for floating-point values/equity. Tests must exercise actual opens and exits in bar and tick modes, including partial exits, early-stop and daily-boundary cases.

**Level 2 — same model function (only for equivalence-preserving optimizations):** Same learned parameters and policy outputs on an identical observation/action batch, within defined FP32/BF16 tolerances, same masked categorical distribution, stored-action log probability, exact entropy and gradient equivalence. Grouped/fused execution and compilation can target this level, after tests. Different encoder weights or weight sharing cannot promise this.

**Level 3 — same learning trajectory (not guaranteed when changing n_envs, rollout, minibatch, epochs, RNG/callback timing):** Statistical or scientific parity must be demonstrated with paired seeds, fixed train-calendar development splits and identical risk conditions. Never call changing 8 to 64 envs 'behaviorally identical' without this distinction.

## 3. Work packages (ordered by expected benefit and risk)

### WP0 — Freeze baselines and build a truthful profiler (no code change to research baseline)

1. Read `AGENTS.md`, `.agents/rules/triton-slurm.md`, `docs/thesis/master_project_execution_plan.md` and relevant domain maps. Re-verify source and experiment hashes. Respect the approved active C/D launch and two-GH200 aggregate cap; never submit/cancel/alter jobs as part of this plan.
2. Keep **two metric scopes**: (i) warmup-excluded PPO-core transitions/s and (ii) cold-start end-to-end time until the exact reports, full-year train replay and report-only 2026 replay finish.
3. Benchmark baseline E at 8 envs, aggregate 2048, batch 512, epochs 15 with 3 repeats of 65,536 steps (or comparable long stable core run) on the same immutable bundle. Capture rollout, actor inference, update, vector-step IPC, observation-building, action transfers, `.cpu()` sync, entropy, device copy, CPU utilization, VRAM, compile state and kernel counts.
4. Record one experiment manifest per run: commit and dirty-patch SHA, binary/source compiler details, CUDA/PyTorch versions, resolved config hashes, bundle manifest, seed, exact PPO geometry, hardware, selected GPU and memory/CPU allocation. Record actual optimizer calls, not only epoch counts.
5. Avoid short Slurm jobs/steps; use an existing persistent allocation if authorized. These are engineering probes only; **do not** train 2M or change active scheduler jobs.

### WP1 — Low-risk existing-E hot-path improvements

1. `learning/rl/hybrid.py`: Move per-row positive-thesis-mask assertions out of the rollout/gradient inner loop without losing validation; the NO_TRADE category must remain valid by construction. Retain a debug validation path. Compare exact actions, logits, log-probs, entropy and backprop on masks with 1, 2, many eligible IDs, and invalid-mask rejection.
2. Avoid repeated construction of fixed categorical class-center tensors and continuous-index tensors in `_pack`, `log_prob`, and `_class_ids`; register immutable module buffers on the correct device, with exact checkpoint backwards-compatibility and serialization tested.
3. `learning/rl/ppo.py`: Measure repeated in-place log_std clipping on every distribution build. If a faster alternative is warranted, prove no change to sampling/entropy bounds or optimizer semantics; do not simply remove clipping.
4. `models/encoders/mtf_shared_tcn_reasoning.py`: Profile list-of-HTF input projections, repeated padding/stacking and two shared TCN calls. Try preallocated contiguous workspace; optionally try grouped single-call kernels, but require full-shape and masked-padding numerical/gradient parity. **Do not** assume one full-length 9-stream batch is faster: it increases compute by padding HTFs to M1 length.
5. Profile `weight_norm` reparameterization in `_TemporalBlock`; consider parametrization caching during an entire shared-TCN forward if repeated materialization is confirmed and gradients match.
6. Independently measure D exact conditional entropy: dynamic `nonzero` is a synchronization lead, but do not approximate entropy or evaluate only sampled thesis if attempting strict mathematical equivalence. Keep the exact hierarchical objective.
7. For each change, perform A/B warmup-excluded PPO-core runs with unchanged E eight-env geometry. Reject options without reproducible end-to-end speedup or correct gradients.

### WP2 — 64-env scaling and PPO geometry screen, separate lineage

Use E (`thesis_conditioned_v1`) first, same immutable market bundle, seed(s) and simulator. Do **not** overwrite frozen C/D 8-env configs.

| Screen | Logical envs | Aggregate rollout | SB3 steps/env | Batch | Epochs | Purpose |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| E8 reference | 8 | 2048 | 256 | 512 | 15 | Measured architecture baseline |
| E16 fixed-aggregate | 16 | 2048 | 128 | 512 | 15 | Isolate vec batch effect |
| E32 fixed-aggregate | 32 | 2048 | 64 | 512 | 15 | Isolate vec batch effect |
| E64 fixed-aggregate | 64 | 2048 | 32 | 512 | 15 | Isolate vec batch effect |
| E64 high-throughput | 64 | 16384 | 256 | 4096 | 15 | Proposed separate PPO geometry |

- Compare physical shards `8`, `16`, `32` where allocation permits; use bundle-backed workers and same immutable bundle. Benchmark both Subproc and sharded only where a real resource/sample indicates benefit.
- Add capped 64-env CPU/RAM footprint and cold-start measurements. Do not use 64 copied frame workers.
- Preserve exactly the interpretation of `n_steps` as aggregate before SB3, and verify `model.n_steps * model.n_envs` on the initialized model. Verify actual PPO gradient update counts.
- Changing the number of envs and optimizer batch size changes policy training dynamics; preserve separate hashes and do **not** use the frozen C/D experimental label.
- Run short learning-stability screens after throughput, then longer development-period evidence on the 2025 train calendar; the already exposed 2026 period is report-only.

### WP3 — Train-side CUDA optimization (high return potential, moderate risk)

1. Check ARM64 toolchain in allocated shell: `command -v cc gcc clang`, compiler versions/modules, PyTorch/CUDA/Triton compatibility. Do not run installation or request a new job merely to diagnose; report a blocker if a compatible compiler cannot be provided.
2. Compile **only fixed-shape, tensor-only** pieces first (e.g. E encoder, action-head evaluation) using `torch.compile`, comparing `default` and `reduce-overhead` after warmup. Inspect `TORCH_LOGS=graph_breaks` and compile time. PyTorch CUDA Graphs only benefit graph-capturable segments; do not compile full mutable SB3+environment blindly.
3. Benchmark CUDA Graph capture for stable-shape encoder inference and minibatch update, separately. Maintain separate graphs for batch64 policy inference and batch4096 learner updates, with correct lifecycle for mutations/optimizer state. Avoid stale captured RNG, dropout states and invalid graph replay.
4. Inspect and reduce repeated small GPU indexing/scatter and `torch.distributions` Python object creation in hybrid actor/critic hot paths. Only fuse numerically equivalent operations; verify masked log-probs, categorical entropy and gradients.
5. Keep `ppo.rollout_buffer_on_device: true`: already implemented and shown beneficial. Do not recreate the existing completed-rollout GPU staging.
6. Record compiler warmup costs and total run savings; large compile-time overhead may outweigh speedup for a 2M run.

### WP4 — GPU-resident rollout data and single synchronization per vector step (larger rewrite)

Current `DeviceDictRolloutBuffer` still collects market observations, values and log-probs in CPU NumPy storage, then stages the full rollout to CUDA only for updates. This architecture constrains throughput.

1. Prototype a versioned **GPU-backed rollout storage** holding (a) environment actions needed for CPU `TradingEnv.step`, (b) log-probs/values on device, (c) rewards/dones and GAE inputs with exact chronology, and (d) training observations or immutable indices on device. Keep exact PPO sampling/GAE math and data-order contract.
2. Transfer the **one necessary action packet** GPU -> CPU for the batch of environments once per VecEnv step, rather than separately synchronizing `values`, `log_prob` and other tensors. Preserve sampled action coordinates and probabilistic log-prob fidelity; store value/logprob on GPU. Add a reference implementation and compare with SB3 on synthetic deterministic env for identical seeds/tensors under numeric tolerance.
3. If performing GAE on device, verify bootstrapping across episode boundaries/truncation and time-limit semantics against current SB3 reference; compare advantage and return arrays, update gradients, and optimizer steps.
4. Keep CPU simulator state first; do not port risk/execution to GPU before proving market observation/data transfer are significant.
5. If GPU pipeline is too complex or yields little improvement, retain WP1-WP3 and stop here.

### WP5 — Static-market observation index/cache architecture (larger rewrite, trading semantics preserved)

Market history, completed HTF windows, valid masks and precomputed thesis-eligibility flags are independent of the policy's actions in the historical replay. Account state, open positions, risk and fills are not.

1. Add an immutable, versioned market-window store keyed by `(bundle identity, decision bar, session, feature schema)`. Precompute the exact M1 session-limited window and M3-D1 *closed* HTF windows/masks once, or store compact index tables into a device-resident feature matrix. Never recompute indicators from the future.
2. Replace repeated CPU NumPy window-building and multi-process full-window copying with a lightweight worker response containing `bar_index`, dynamic `account`, dynamic order information if relevant, and the recorded thesis mask. Let the learner reconstruct the **identical** market tensor values on GPU by index lookup/gather; preserve old observation interface via compatibility adapter when needed.
3. Distinguish learner's static market arrays from dynamic per-environment account state. Verify handling of all resets, day/session boundaries, missing/invalid bars, partial HTF candles, NaN-padding, different initial observations and timestamp alignment.
4. Estimate GPU memory explicitly; do not materialize redundant full windows unless memory/IO profiling supports it. The shape reported in the repo implies ~92 KB of M1+HTF float32 market features per decision row before masks; 99,492 rows fully materialized are ~9.2 GB, whereas a compact feature matrix + index tables can be much smaller.
5. Keep CPU reference engine and generate exact A/B observation traces for 2025, including the 99,492 decision bars and 2026 report-only stage. Test matching action/reward/equity/fill/risk results with fixed action sequences and both bar/tick execution.
6. If GPU-index + host CPU step is still the bottleneck, profile a batched CPU environment state-of-arrays path before any GPU simulator port.

### WP6 — Last-resort GPU-native environment (highest risk)

Only if WP1-WP5 leave environment execution >30% of wall time and a multi-fold gain is realistic, build a vectorized `TradingEnv` state-of-arrays engine on CPU (NumPy/Numba/C++ as validated). Port to CUDA only with exhaustive simulator semantics tests: fills and latency, tick-only behavior, SL/TP and partial exits, risk and daily loss, historical session/DST logic, stochastic reproducibility, forced closes, violation accounting, empty/sparse thesis masks, and full-year equity. Any algorithmic difference requires a new environment version; do not mislabel as the same system.

### WP7 — Evaluation/report acceleration (separate end-to-end bottleneck)

1. Time the canonical 20 dashboard calls, best-prefix ranking and final train/report-only split replays separately. Do not treat PPO-core FPS as end-to-end throughput.
2. Optimize identical neural-policy inference for chronological replay using the same static market cache or compiled actor; amortize encoding where causally safe. Do not alter model predictions, checkpoint-selection logic, data split or RNG isolation without a new, versioned line of evidence.
3. If deferring dashboard evaluation, mark it as a new training protocol: the current dashboard's `prior_every`, callback RNG behavior and model-selection semantics must be preserved or explicitly changed. Train-only 2025 for selection; 2026 is exposed report-only.
4. Export final immutable event ledgers, thesis-policy diagnostics and checkpoint manifests. Measure total time to complete them all, not merely `learn()` duration.

## 4. Targets, not predictions

- **Gate 1:** ≥250-300 *measured* PPO-core steps/s for optimized E without changing eight-env geometry (a stretch from 209; reject if quality/math regress).
- **Gate 2:** ≥500 steps/s at 32/64 envs with development-policy sanity, correct resource usage and no critical regression.
- **Gate 3:** ≥1,000 sustained steps/s with enlarged geometry, compiled/fused inference and updates as indicated by profiling.
- **Stretch:** ≥3,000 steps/s requires a full 65,536-transition run in ≤21.85 seconds including all PPO updates; 64 envs and the current E update pipeline alone will not guarantee it. At that point demand an explicit end-to-end wall-time and quality report.
- Do not lower epochs to gain FPS under a strict matched comparison. For a separately labeled experiment, 15→10→5 epochs is an optional additional throughput/learning-quality sweep, not an equivalence-preserving change.

Illustrative *optimistic arithmetic only*: if E's current 215.65-second rollout time fell 8x at 64 envs while its current 78.09-second update time and 20.30-second remainder remained unchanged, `65,536 / (26.96 + 78.09 + 20.30) ≈ 523 steps/s`. Batch64 inference is not free, so this is **not** a forecast. If, additionally, PPO update time fell 4x, the corresponding illustration is ~981 steps/s. Reaching 3,000 needs qualitatively more reduction.

## 5. Acceptance checklist

- Source/config/data/seed and measurement scope fully recorded; benchmark three repeats with warmup excluded; GPU CPU, RAM and I/O time accounting complete.
- Numerical: no NaN/Inf; log-prob and entropy preserve exact masked categorical semantics; deterministic/stochastic seeds and RNG restoration; gradients and policy parameter shape passed.
- Causality: no lookahead, no future HTF candle, no untrained-normalizer leakage.
- Simulator: fixed-action bar and tick tests show identical fills, SL/TP, account and risk, including exits, partial fills, daily boundaries and breach conditions.
- Policy: no invalid thesis choices; NO_TRADE conditioned on availability, thesis entropy, selection diversity, trading activity and learning stability all recorded; full train-calendar survival and economic outcomes reported honestly.
- Report: 2026 is **report-only**; do not select architecture on exposed 2026 data. Record all episode/callback end-to-end costs and checksum every final checkpoint.
- Resource: no new short Slurm steps, no overlapping GPU requests, no changes to user's active C/D jobs/monitor. Stop before expensive experiments without separate approval.
- If a profiler says a proposed rewrite cannot materially improve critical-path wall time, reject it rather than implementing for theoretical elegance.

## 6. Final deliverables for Codex

1. Measurement manifest, matched baseline data and prioritized bottleneck table with **measured** CPU/GPU wall times.
2. Separate architecture/throughput configs with preserved C/D references and full training lineage.
3. Incremental commits and full-tree Ruff format/lint/Mypy + focused pytest gates per `AGENTS.md`.
4. Numeric/simulator/rollout/checkpoint parity report.
5. GH200 FPS matrix (8/16/32/64 envs, fixed and enlarged rollout) and real critical-path 2M ETA including evaluation.
6. GO/NO-GO recommendation with observed quality risks and remaining implementation work; do not automatically launch production training.
