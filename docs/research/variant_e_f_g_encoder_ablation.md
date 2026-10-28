# Variants E/F/G: Efficient MTF Encoder Ablation

## Objective

Add three thesis-conditioned PPO encoder alternatives to Variant D while keeping
the policy distribution, PPO settings, feature/data path, reward, execution,
risk controls, action and observation schemas, split, and reporting protocol
fixed. Variant C remains the unconditioned policy control; it is not the
encoder control for E/F/G. The primary comparisons are D versus E/F/G.

This file tracks implementation and evidence for the attached 2026-10-28 plan.
Its 9e56efc baseline is a historical reference; the working checkout stays on
`main` at the newer baseline and is not reset. A passing encoder smoke or speed
probe is engineering evidence only, not economic evidence or approval for a
2M run.

## Variant matrix

| Arm | Policy | Encoder treatment | Information retained | Status |
|---|---|---|---|---|
| C | `thesis_hybrid_v1` | Existing nine independent TCNs + attention | Full nine-stream histories | Existing control |
| D | `thesis_conditioned_v1` | Existing nine independent TCNs + attention | Full nine-stream histories | Existing matched control |
| E | `thesis_conditioned_v1` | One shared-weight TCN; per-timeframe input adapters | Full nine-stream histories | Implemented; bounded correctness and throughput evidence complete |
| F | `thesis_conditioned_v1` | D-sized M1 TCN + shared lightweight HTF history summaries | M1 sequence and history-aware M3-D1 summaries | Implemented; bounded correctness and throughput evidence complete |
| G | `thesis_conditioned_v1` | D-sized M1 TCN + shared latest-valid HTF adapters | M1 sequence and latest causally available M3-D1 rows | Implemented; bounded correctness and throughput evidence complete |

All D/E/F/G encoders must produce the same 160-D extractor output (128-D market
representation plus the existing 32-D account embedding) and use the same
nine-token timeframe attention and thesis-conditioned actor/critic heads. The
109-category thesis mask, `NO_TRADE`, selected-thesis execution conditioning,
and stored-action PPO likelihood semantics remain unchanged.

## Frozen comparison contract

- M1 decision timeline; nine streams M1, M3, M5, M10, M15, M30, H1, H4 and D1.
- Matched geometry: seed 42, 8 logical environments, 2,048 aggregate rollout
  transitions (256 per environment), batch 512, 15 PPO epochs, and unchanged
  learning-rate/reward/risk/execution settings.
- Use one immutable data bundle for every arm. The current C/D diagnostic bundle
  is `e9d5a63f864394ddad5acfb73f184444a6293295e1bbeff6313d1bc5d842a28c`, with
  manifest SHA-256
  `d85e0dc8fa241c66d4d727dd4be5d463fc58dbbbd53a43fd00d75100387b052e`.
- Current C/D overlay hashes: C `fa27bb63debc77cf3461ff29e385b0d2fc80a7c121a7cc4a908ae9c10298b569`;
  D `d97017d8c354cdb5b24544359c50396f7a53096429f21c6f502d9325a9079f39`.
- The 2026 slice is already exposed and is descriptive/report-only. It must not
  select E/F/G. Use declared 2025 development/validation evidence for any later
  selection, and state limitations if no fresh confirmatory period exists.
- Attempt41's actual observation space has M1 shape `(60, 282)`, HTF widths 60
  with lengths M3=20, M5=24, M10=12, M15=16, M30=8, H1=12, H4=6, D1=5,
  account width 6, and a 109-entry thesis mask. Integration tests use these
  resolved shapes; focused encoder tests also use unequal synthetic feature
  widths to exercise timeframe-specific adapters.
- Do not reuse a D checkpoint under E/F/G. Each encoder has a distinct
  checkpoint/config lineage and must fail closed on architecture mismatch.
- Do not edit C/D semantics, caches, campaign evidence, checkpoints, or
  `campaign_worker_dispatch.log` as part of the encoder work.

Attempt41 hardware: one NVIDIA GH200 144 GiB HBM3e, one gpuarm1 allocation with
64 CPUs and 512 GiB host RAM. The same GPU and node were used for C and D.

## Implementation and evidence gates

1. Freeze and record current C/D configs, schemas, policy class, bundle identity,
   and active allocation. No architecture code changes until the active C/D
   runtime repeats finish.
2. Implement and test G first, F second, E third. Preserve causal right-aligned
   masks, padding invariance, all-invalid HTF neutrality, finite gradients, and
   exact 160-D output. E must contain one shared TCN instance; F must respond to
   valid earlier HTF history; G must be invariant to earlier HTF rows when its
   latest valid row is fixed.
3. Register the three encoder IDs, defaults, CLI choices, matched config
   overlays, architecture validation, and explicit provenance. Keep D and C
   checkpoint compatibility unchanged.
4. Verify model save/load identity and predictions, masked thesis action/log
   probability behavior, observation/action schemas, and same-action simulator
   trace parity. Run bounded learning smokes without costly production replay
   callbacks.
5. Measure encoder forward/backward latency and memory, then repeated exact
   geometry PPO-core probes on one GH200 with the same bundle. Separately measure
   callback-inclusive wall time and callback overhead; never extrapolate a tiny
   smoke as pure PPO throughput.
6. Report actual measurements, variability, resource headroom, bottlenecks,
   economic diagnostics when available, and a per-variant GO/NO-GO. Any 2M
   benchmark remains gated on correctness, runtime feasibility, repository
   campaign rules, and explicit user GO.

## Work status

- Baseline: checkout is `main` at `44ec01129c0276abdce6a228f8bd20b693d7f721`;
  it is newer than the attached reference SHA. E/F/G code, configuration,
  registration, tests, and this evidence report are included in that commit.
  The active C/D throughput diagnostic is separate and must be preserved. The
  untracked `campaign_worker_dispatch.log` is user-owned and excluded from this
  work.
- Existing D implementation: `MTFReasoningEncoder` reuses the nine independent
  `_CausalTCN` branches, one four-head Transformer layer, masked pooling and the
  account embedding. D config resolves to `thesis_conditioned_v1`; C uses
  `thesis_hybrid_v1`.
- E/F/G implementation and factory/worker/CLI registrations are local edits on
  this checkout; see the implementation status and results below.
- Active C/D runtime repeats used allocation `21247526` (one GH200 on gpuarm1).
  They are 20,480-step warmed diagnostic probes, not policy-quality training.
  Results are recorded in scratch under
  `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt41/`. No 2M E/F/G
  campaign has started.

### C/D context probe: warmed PPO core

Attempt41 used the same immutable bundle and exact geometry for all six runs;
each run completed 20,480 environment steps and excluded its first two rollout
cycles from the rate. Effective geometry assertions passed: 8 envs, 2,048
aggregate transitions per rollout, batch 512, 15 epochs, and 8 measured rollouts.

| Arm | Repeat 1 | Repeat 2 | Repeat 3 | Mean | Sample SD |
|---|---:|---:|---:|---:|---:|
| C | 86.88 | 90.71 | 88.09 | 88.56 | 1.96 |
| D | 84.06 | 81.22 | 88.66 | 84.65 | 3.75 |

Rates are warmed PPO core steps/s, with rollout and update phases timed. Across
the three repeats D was about 4.4% slower than C, small relative to run-to-run
variation; this does not identify an architecture effect because C and D differ
in policy factorization and both use the same encoder. Peak allocated GPU memory
was about 1.17 GiB for C and 1.18 GiB for D.

One additional run per arm enabled per-environment-step timing. C measured 3.13
ms mean CPU time per `env.step()` call (64.08 aggregate CPU seconds; 8.20 seconds
parallel critical-path lower bound), with 140.97 seconds in rollout/framework
and 74.25 seconds in PPO updates. D measured 3.00 ms (61.46 aggregate CPU
seconds; 8.13-second measured wall lower bound), with 148.23 seconds in
rollout/framework and 83.83 seconds in updates. Those instrumented probes
completed in 215.22 seconds for C and 232.06 seconds for D. They used roughly
1.20 CPU cores on average, about 4.2-4.3 GiB process-tree PSS, and 1.17-1.18
GiB peak allocated GPU memory. The GPU sampler collected 1,908 one-second
samples across attempt41: utilization averaged 10.85% and peaked at 24%; memory
use averaged 1.81 GiB and peaked at 1.94 GiB. These timings point to PPO
rollout/framework and
update work beyond `env.step()` as the larger measured time components; they do
not yet isolate policy-forward, vector IPC, or callback costs. The probe
excluded production callbacks, so its wall time is not an accepted-artifact ETA.

## Results

### Implementation status — 2026-10-28

E/F/G are implemented and registered as encoder-only alternatives to D. Their
overlays resolve to D's settings except for the agent architecture ID. Separate
architecture defaults do not change PPO or policy settings. The tests cover
shared-core identity, nine streams, per-timeframe adapters, causal masking
behavior, padding invariance including nonfinite padded values, F's use of
earlier valid HTF history, G's latest-valid-only behavior, finite gradients,
masked thesis selection, stored-action log-probability, save/load identity,
and architecture mismatch rejection. The focused GH200 encoder/model suite
passed 65 tests. The follow-up MTF factory, bundle-worker, and variant resolver
suite passed 42 tests.

The isolated PPO-core matrix completed with two 65,536-step repeats per arm on
the same GH200, shared bundle, seed 42, 8 environments, aggregate rollout
2,048, batch 512, 15 epochs, and two warm-up rollouts excluded from the rate.
All runs used `SubprocVecEnv`, `DeviceDictRolloutBuffer`, and no production
callbacks. Exact per-run geometry, config, source, and bundle hashes are in the
scratch JSON records under
`/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt42/core/`.

| Arm | Encoder | Total policy params | Core steps/s, mean ± sample SD | Speedup vs D | Mean run seconds | Peak GPU allocated | Peak cgroup RAM |
|---|---|---:|---:|---:|---:|---:|---:|
| D | Independent nine-stream TCNs | 8,871,904 | 81.90 ± 2.41 | 1.00× | 791.96 | 1.11 GiB | 15.47 GiB |
| E | Shared TCN | 1,326,240 | 209.16 ± 1.01 | 2.55× | 314.04 | 1.60 GiB | 14.70 GiB |
| F | M1 TCN + history-aware HTF summaries | 1,433,312 | 184.82 ± 7.20 | 2.26× | 354.98 | 0.62 GiB | 14.71 GiB |
| G | M1 TCN + latest-valid HTF state | 1,425,120 | 199.11 ± 9.95 | 2.43× | 330.22 | 0.62 GiB | 14.69 GiB |

The repeated throughput measurement favors E, followed by G and F. The repeats
are engineering measurements, not independent statistical samples. E's
parameter count is about 85% lower than D's, but its peak allocated GPU memory
was higher (1.60 vs 1.11 GiB); all four had ample headroom on the 144-GiB GH200.

### Encoder microbenchmark

The encoder-only probe used 512 real observations sampled over the 2025
training bundle (sample timestamps 2024-12-31 10:25 through 2025-12-31 10:25).
Observation shapes were M1 `(60, 282)`, each HTF `(window, 60)` with the
configured M3-D1 windows, account width 6, and thesis mask width 109. Available
thesis candidates had p10/median/p90 counts of 1/2/4. The same BF16 autocast,
`high` matmul precision, warm-up, and CUDA-event measurement protocol were used
for every arm.

| Arm | Encoder params | Forward p50 at batch 8 | Forward + backward p50 at batch 512 | Batch-512 forward + backward p95 | Peak allocated at batch 512 | CUDA kernel launches, one forward at batch 512 |
|---|---:|---:|---:|---:|---:|---:|
| D | 8,667,712 | 44.71 ms | 278.16 ms | 308.21 ms | 0.88 GiB | 3,214 |
| E | 1,122,048 | 10.88 ms | 25.81 ms | 41.55 ms | 1.41 GiB | 394 |
| F | 1,229,120 | 13.60 ms | 192.19 ms | 214.58 ms | 0.45 GiB | 2,231 |
| G | 1,220,928 | 12.88 ms | 187.25 ms | 210.89 ms | 0.45 GiB | 2,143 |

E has the lowest measured latency and kernel count, including at the largest
tested batch. Its high-batch activation memory is higher than D/F/G, which is
an explicit tradeoff. This per-encoder ratio must not be extrapolated directly
to full-run wall time.

### Callback-inclusive bounded learning pilots

Each arm used the production preparation/callback/checkpoint path with 20,480
training steps, then one 2025 prefix evaluation. The same 8-env, 2,048-step
aggregate rollouts, batch 512, 15 epochs, seed 42, and bundle manifest were
used. These short pilots do not establish policy quality or long-horizon
survival.

| Arm | PPO learn seconds | Prefix evaluation seconds | Prepare assets/model seconds | Train phase wall seconds | Best checkpoint status | Prefix ending equity | NO_TRADE action rate | Distinct thesis categories | Invalid thesis selections | Mean thesis entropy (nats) |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| D | 394.26 | 206.01 | 40.28 | 399.16 | No active checkpoint | Not reported | 53.8% | 20 | 0 | 0.631 |
| E | 197.13 | 95.02 | 40.93 | 202.03 | Active checkpoint available | $98,089.60 | 74.6% | 14 | 0 | 0.652 |
| F | 232.74 | 115.96 | 40.59 | 237.65 | Active checkpoint available | $102,253.41 | 65.4% | 15 | 0 | 0.641 |
| G | 218.57 | 107.55 | 40.95 | 223.47 | Active checkpoint available | $111,270.66 | 67.0% | 14 | 0 | 0.655 |

Each prefix evaluation made 5,293 decisions; 69.5% of decisions had at least one
eligible thesis and the p50/p95 eligible-candidate counts were 2/5. Every arm
selected multiple categories and made zero invalid thesis selections in this
pilot. D/E/F/G end equities and checkpoint status are diagnostics from one
short, exposed 2025 evaluation, not comparable holdout returns or selection
evidence. D's callback produced no active best checkpoint; do not infer a
trading-policy failure from this abbreviated pilot.

The first E startup attempt exposed an architecture-routing omission: the
environment factory and bundle worker did not classify the new encoders as MTF
consumers. That registration was corrected and covered by tests; the failed
startup log is retained separately. An initial profiling attempt also stored
a bound `predict` method on the model instance, which made its checkpoint
unpicklable during callback save. The profiler was corrected to instrument the
class method without changing model state. Subsequent D/E/F/G callbacks saved
successfully; this was a measurement-wrapper issue, not a backend checkpoint
defect.

The measured `prepare_data_and_assets_seconds` was about 33.3–33.9 seconds and
model preparation about 7.0 seconds per arm. Across the isolated core matrix,
the GPU sampler recorded 2,869 samples while the GPU had over 500 MiB in use;
utilization averaged 10.6%, peaked at 45%, and memory averaged 1,845 MiB with
a 2,612-MiB peak. The PPO process averaged about 1.2–1.5 CPU cores out of the
64 allocated. Rollout/framework overhead exceeded update time for every arm,
so this probe does not indicate GPU saturation as the only or dominant
bottleneck. The source hash for core probes was
`8e3780324d1422ee83e049325be2d212ce65d8a3fda4f3daa5cd0d01a5c94f61`; all
core runs used bundle manifest SHA-256
`d85e0dc8fa241c66d4d727dd4be5d463fc58dbbbd53a43fd00d75100387b052e`. The
callback pilot training/evaluation wrapper recorded source patch hash
`fffd69cac6cb0455170dcc8257ee5dddb676344b72523ce922c2d9285cf46d1f` and the
same bundle manifest.

The core and bounded pilots are complete engineering evidence. E is the
strongest throughput candidate in this screen, but no 2M run was started. A
2M benchmark remains gated on the full plan's semantic/simulator checks,
development-quality review, runtime feasibility using callback-inclusive
measurements, and explicit user authorization. No result here establishes
economic improvement, multi-seed robustness, or OOS generalization; 2026 was
not used to select a variant.

### Per-variant gate disposition

| Arm | Encoder/config/checkpoint gates | Bounded policy screen | Economic/robustness gate | 2M disposition |
|---|---|---|---|---|
| D | Pass: original encoder and policy; checkpoint behavior retained | Technically viable, but this 20,480-step pilot produced no active best checkpoint | Not established | **NO-GO pending explicit authorization and full-run review** |
| E | Pass: shared TCN, all nine streams, matched config, mask/gradient/save-load tests | Technically viable; 14 thesis categories and zero invalid selections in the short prefix | Not established | **NO-GO pending explicit authorization and full-run review** |
| F | Pass: history-aware HTF summaries, matched config, mask/gradient/save-load tests | Technically viable; 15 thesis categories and zero invalid selections in the short prefix | Not established | **NO-GO pending explicit authorization and full-run review** |
| G | Pass: latest-valid HTF snapshot semantics, matched config, mask/gradient/save-load tests | Technically viable; 14 thesis categories and zero invalid selections in the short prefix | Not established | **NO-GO pending explicit authorization and full-run review** |

These bounded pilots are not the sustained development-quality or robustness
gate. The 2026 slice is report-only, and no untouched confirmatory period is
claimed. E's faster core result does not make E the scientific winner.

### Callback-inclusive 2M runtime planning estimate

This is a planning estimate from the 20,480-step attempt42 callback pilots, not
a full-run measurement. For each arm, estimated PPO time is
`(pilot PPO learn wall - one measured 5,293-decision prefix evaluation) ×
(2,000,000 / 20,480)`. Add two full-split replay allowances (train and
report-only test), each budgeted at 20 times the measured prefix evaluation,
then add 25% reserve for checkpoint, final artifact and timing variability.
The 20x replay factor is a conservative planning assumption; checkpoint and
report overhead were not directly measured at 2M. The 2M callback frequency is
one best-checkpoint evaluation at the terminal 2M step; no 5M viability callback
falls inside this run.

| Arm | Scaled PPO learning | Two replay allowances | With 25% reserve | Interpretation |
|---|---:|---:|---:|---|
| D | 5.11 h | 2.29 h | 9.24 h | Fits a single 12 h one-GH200 window only if observed throughput holds; modest headroom remains |
| E | 2.77 h | 1.06 h | 4.78 h | Runtime appears feasible for one arm; training quality remains unknown |
| F | 3.17 h | 1.29 h | 5.57 h | Runtime appears feasible for one arm; training quality remains unknown |
| G | 3.01 h | 1.20 h | 5.26 h | Runtime appears feasible for one arm; training quality remains unknown |

These rows cannot be added into one 12-hour single-GH200 campaign: the four-arm
matrix is estimated at about 24.9 aggregate GH200-hours including reserve.
Allocation shape, campaign ordering and user GO must be settled before Stage B.
Do not use this estimate as proof that the matched multi-arm campaign fits the
current task's resource limit.

### Raw evidence inventory

Raw profiling and test artifacts remain outside Git in
`/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt42/`:

| Evidence | Path | SHA-256 |
|---|---|---|
| Repeated D/E/F/G PPO-core summary | `core/core-summary.jsonl` | `034dd7aaba6d65a0d25dd267f34b72c3afa27c0d028b3477e528ce0e1ae7e210` |
| Encoder microbenchmark, including per-run values | `microbench/encoder_microbench.json` | `eaf330a1c10e77d0f7e740d71e1313f6158879e454976aa28a320804e0abb5da` |
| D callback pilot profile | `e2e/D-phase-profile.json` | `a647c02de08d8780898b07b1791f379d595abec62579cbee9476cdd71161d66d` |
| E callback pilot profile | `e2e/E-phase-profile.json` | `12a0d454297a9201ce1b9c83cb149e3111f424d657266e931d7d47b1292dddcf` |
| F callback pilot profile | `e2e/F-phase-profile.json` | `fd9c1d9dc48e26e38656b05fdd84987529d4372d72d8dee8bb28e3aa645aec5c` |
| G callback pilot profile | `e2e/G-phase-profile.json` | `dcf6e938852d516f0abe7c7e210bc1a8ae3e714c5d2a2b487a19b93dc79ffbfc` |
| Full-tree format/lint/type gate | `full-quality-gate-final2.log` | `fc966fb4d632b015d91243d41e5165f68588d286a5bc173357566a96b5b7eb40` |
| Focused integration test gate (138 tests before the added fixed-action regression) | `final-quality-gate2.log` | `244c227b5484790da805194ddca74d0349a843c8f57f75bda6252daf1de9b516` |
| Final format/lint/type and focused test gate | `../attempt47_commit_gate.log` | `5ec9824604985c81492e181f46021ce46ee19e4e081329809bc77302442f9acd` |
| Fixed-action D/E/F/G simulator trace test | `../attempt45_parity_test2.log` | `6e4849227aa7f82a80ede312f18e734362f15eb50a9cd196447f003ad6ffbfbb` |

The two repeated core-run JSON files per arm are in `core/{D,E,F,G}-r{1,2}.json`;
GPU utilization samples are in `core/gpu-samples.csv`; encoder latency inputs
and raw results are in `microbench/real_train_observations.npz` and
`microbench/encoder_microbench.json`; callback-inclusive process, cgroup and
GPU samples are in `e2e/{D,E,F,G}-{process,cgroup,gpu}-samples.csv`. These
records include source/config/bundle identities and were produced on the
existing GH200 allocation. The repository report links these paths without
adding large run artifacts to Git.

### Final verification

On the existing GH200 allocation, full-tree Ruff format and lint checks passed,
Mypy passed all 800 source files, and the scoped encoder/environment/bundle/
checkpoint/resolver suite passed 139 tests. The new trace test used the same
fixed ten-step eligible PO3/M1-long selection followed by ten NO_TRADE actions
across D/E/F/G, comparing observations, rewards, termination flags and info.
It confirms environment trace parity for an eligible thesis action; the
synthetic fixture does not require or claim a successful fill. GitHub Actions
for `44ec01129c0276abdce6a228f8bd20b693d7f721` reported 15/15 checks passed.
No 2M or 20M campaign was started.
