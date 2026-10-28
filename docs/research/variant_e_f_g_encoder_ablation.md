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

- Implementation baseline: E/F/G code, configuration, registration, initial
  tests and evidence report landed on `main` at
  `44ec01129c0276abdce6a228f8bd20b693d7f721`, newer than the attached reference
  SHA. This handoff follow-up records the final readiness gaps and trace check.
  The active C/D throughput diagnostic is separate and must be preserved. The
  untracked `campaign_worker_dispatch.log` is user-owned and excluded from this
  work.
- Existing D implementation: `MTFReasoningEncoder` reuses the nine independent
  `_CausalTCN` branches, one four-head Transformer layer, masked pooling and the
  account embedding. D config resolves to `thesis_conditioned_v1`; C uses
  `thesis_hybrid_v1`.
- E/F/G implementation, config overlays and factory/worker/CLI registrations
  are committed at `44ec0112`. Follow-up trace coverage and readiness reporting
  are committed at `4b2e2cdf`; the baseline wording correction is at
  `4b3b8955`.
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

The resolved `resolved_config_yaml` captured in each attempt42 core-run JSON
was parsed and compared after excluding only `agent.arch`. D/E/F/G were
identical in every other resolved value, including data bundle/splits, action
schema, policy distribution, PPO geometry, reward, risk, execution, callbacks
and report settings. The resolved-config SHA-256 values are D
`fa7d49acbdd0e367be29147cbe8cbc4f94f3a4839ce44e6adb9f9577894f4565`, E
`7d15f4492769de29347ca5af0dbd888bc5cd61ad984f0932426cc73491a9a216`, F
`909681319291b83eae61b9927c2138024e62093b1d7c8e40b60c1493b399db54`, and G
`ee94f565624bfa28ec70f77e87cbc162e5f72d82bb1e6dfc6b7a182de1b7afe8`.

The isolated PPO-core matrix completed with two 65,536-step repeats per arm on
the same GH200, shared bundle, seed 42, 8 environments, aggregate rollout
2,048, batch 512, 15 epochs, and two warm-up rollouts excluded from the rate.
All runs used `SubprocVecEnv`, `DeviceDictRolloutBuffer`, and no production
callbacks. Exact per-run geometry, config, source, and bundle hashes are in the
scratch JSON records under
`/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt42/core/`.

| Arm | Encoder | Total policy params | Core steps/s, mean ± sample SD | Speedup vs D | Mean rollout s | Mean PPO update s | Mean core-run wall s | Peak GPU allocated | Peak cgroup RAM |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D | Independent nine-stream TCNs | 8,871,904 | 81.90 ± 2.41 | 1.00× | 480.34 | 270.20 | 791.96 | 1.11 GiB | 15.47 GiB |
| E | Shared TCN | 1,326,240 | 209.16 ± 1.01 | 2.55× | 215.65 | 78.09 | 314.04 | 1.60 GiB | 14.70 GiB |
| F | M1 TCN + history-aware HTF summaries | 1,433,312 | 184.82 ± 7.20 | 2.26× | 243.00 | 89.68 | 354.98 | 0.62 GiB | 14.71 GiB |
| G | M1 TCN + latest-valid HTF state | 1,425,120 | 199.11 ± 9.95 | 2.43× | 226.54 | 82.41 | 330.22 | 0.62 GiB | 14.69 GiB |

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

| Arm | PPO learn seconds | Prefix evaluation seconds | Prepare assets/model seconds | Train phase wall seconds | Best checkpoint status | Executed prefix trades | Prefix ending equity | NO_TRADE action rate | Thesis categories | Invalid thesis selections | Mean thesis entropy (nats) |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| D | 394.26 | 206.01 | 40.28 | 399.16 | No active checkpoint | 0 | Not reported | 53.8% | 20 | 0 | 0.631 |
| E | 197.13 | 95.02 | 40.93 | 202.03 | Active checkpoint available | 275 | $98,089.60 | 74.6% | 14 | 0 | 0.652 |
| F | 232.74 | 115.96 | 40.59 | 237.65 | Active checkpoint available | 201 | $102,253.41 | 65.4% | 15 | 0 | 0.641 |
| G | 218.57 | 107.55 | 40.95 | 223.47 | Active checkpoint available | 176 | $111,270.66 | 67.0% | 14 | 0 | 0.655 |

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
| D | Pass: original encoder and policy; checkpoint behavior retained | Pipeline completed, but no active best checkpoint and 0 executed trades in the short prefix; retain as a warning | Not established | **HOLD: 10.82-hour estimate lacks substantial 12-hour margin; opportunity/trade viability unresolved** |
| E | Pass: shared TCN, all nine streams, matched config, mask/gradient/save-load tests | Technically viable; 14 thesis categories, 275 executed trades and zero invalid selections in the short prefix | Not established | **HOLD: runtime estimate passes duration screening, but no 2M evidence and explicit Stage B GO required** |
| F | Pass: history-aware HTF summaries, matched config, mask/gradient/save-load tests | Technically viable; 15 thesis categories, 201 executed trades and zero invalid selections in the short prefix | Not established | **HOLD: runtime estimate passes duration screening, but no 2M evidence and explicit Stage B GO required** |
| G | Pass: latest-valid HTF snapshot semantics, matched config, mask/gradient/save-load tests | Technically viable; 14 thesis categories, 176 executed trades and zero invalid selections in the short prefix | Not established | **HOLD: runtime estimate passes duration screening, but no 2M evidence and explicit Stage B GO required** |

These bounded pilots are not the sustained development-quality or robustness
gate. The 2026 slice is report-only, and no untouched confirmatory period is
claimed. E's faster core result does not make E the scientific winner. D's
zero executed trades in this short prefix is a material engineering warning;
the plan itself treats a short zero-trade pilot as a warning rather than a
scientific failure, so the longer matched run must report its opportunity
funnel and actual trades.

### Callback-inclusive 2M runtime planning estimate

This is a planning estimate from the 20,480-step attempt42 callback pilots, not
a full-run measurement. For each arm, estimated PPO time is
`(pilot PPO learn wall - one measured 5,293-decision prefix evaluation) ×
(2,000,000 / 20,480)`. Add two full-split replay allowances (train and
report-only test), each budgeted at 20 times the measured prefix evaluation,
then add 25% reserve for checkpoint, final artifact and timing variability.
The 20x replay factor is a conservative planning assumption; checkpoint and
report overhead were not directly measured at 2M. A 2M run has one terminal
best-checkpoint evaluation and 20 dashboard evaluations (`eval_every=100000`);
there is no 5M viability callback inside this run. The 20,480-step pilot ended
before its first dashboard interval. Each arm's actual dashboard evaluation
function was timed on the GH200 for one warm-up plus three measured 20,000-bar
calls. Python, NumPy, CPU Torch and CUDA RNG states were restored around each
call, matching the configured isolated dashboard behavior. The warm-up was
excluded from the median.

| Arm | Scaled PPO core | 20 dashboard calls | Two final replay allowances | With 25% reserve | Interpretation |
|---|---:|---:|---:|---:|---|
| D | 5.11 h | 1.26 h (median 226.03 s/call) | 2.29 h | 10.82 h | No substantial margin inside a 12-hour single-GH200 window; HOLD |
| E | 2.77 h | 0.55 h (median 99.84 s/call) | 1.06 h | 5.48 h | Runtime estimate only; explicit Stage B GO still required |
| F | 3.17 h | 0.71 h (median 128.72 s/call) | 1.29 h | 6.47 h | Runtime estimate only; explicit Stage B GO still required |
| G | 3.01 h | 0.62 h (median 111.74 s/call) | 1.20 h | 6.04 h | Runtime estimate only; explicit Stage B GO still required |

The prior 9.24/4.78/5.57/5.26-hour values excluded dashboard replays and are
superseded. The measured callback medians add 3.15 aggregate hours across 20
calls per arm. With the PPO core, two final replay allowances and 25% reserve,
the four-arm 2M matrix is **28.81 aggregate GH200-hours**. D by itself is
estimated at 10.82 hours with reserve and does not meet the plan's substantial-
margin speed gate within a 12-hour one-GH200 window. The raw per-repeat timings
and initial-policy dashboard summaries are at
`/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt54_efg_stage_a/dashboard/dashboard-callback-timing.json`.
Those initial-policy replay summaries are timing-harness diagnostics, not
trained-policy or benchmark results.

For transparency, each isolated replay of the initialized, untrained policy
produced the same summary within its arm. These are not training outcomes:

| Arm | Dashboard replay | Trades | Net return | Maximum drawdown |
|---|---:|---:|---:|---:|
| D | 226.03 s | 351 | -2.90% | 9.12% |
| E | 99.84 s | 351 | -2.89% | 9.12% |
| F | 128.72 s | 350 | -2.97% | 9.19% |
| G | 111.74 s | 352 | -3.04% | 9.26% |

The user's direction to finish this plan covers the remaining Stage A work;
it is not treated as automatic Stage B approval. The attached plan requires
explicit GO after the readiness gates, and these short results do not establish
policy quality. Do not extend the results into a multi-seed quality claim.

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
| Final gate with all-HTF-masked regression (142 tests) | `../attempt53_efg_all_masked_gate.log` | `14c018a909cce41e925ba416332a373431403d560cb39b6b970606ed1eb629cb` |
| Fixed-action D/E/F/G simulator trace test | `../attempt45_parity_test2.log` | `6e4849227aa7f82a80ede312f18e734362f15eb50a9cd196447f003ad6ffbfbb` |
| Direct 20,000-bar dashboard callback timings | `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt54_efg_stage_a/dashboard/dashboard-callback-timing.json` | `f0f26ff6a62285756424397b426044be884d9d892ae467864bea449c657bb365` |
| Synthetic actual-fill parity rerun | `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt54_efg_stage_a/actual_fill_parity_rerun.log` | `4ba8c0096c98e1865b84407e829c489b3a83b0a2414443096f25b3fb8a68211d` |
| Fixed-action D/E/F/G bar and tick fill parity test (2 passed) | `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt55_cprofile/efg_tick_fill_parity.log` | `c5b0048eae18b8683bcf3191403e3515edd31c99cc8b81024ac36fe209fa601d` |
| Latest full-tree quality gate (142 focused tests) | `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt54_efg_stage_a/quality-gate.log` | `87187c3979dd97285ccc4b54d1752bb6fa9da9d050a42fd8e0ce6ec53caedd7d` |
| Attempt56 full-tree Ruff/Mypy and focused factory gate (12 passed) | `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt56/quality-gate2.log` | `2bb90132d60cd9450b8d0d28a090fc13f13f8a8fae45441e3893f8e51564f872` |

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
Mypy passed all 800 source files, and the scoped suite passed 142 tests. The
added all-masked HTF test checks that E/F/G return finite, identical features
when all eight HTF streams are masked, regardless of their masked payloads.
The rerun log is `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt53_efg_all_masked_gate.log`.
The original trace test used the same fixed ten-step eligible PO3/M1-long
selection followed by ten NO_TRADE actions across D/E/F/G, comparing
observations, rewards, termination flags and info; it did not exercise an
executed fill. The fixed-action simulator parity test now creates valid swing
stop/target references and runs with tick execution both disabled and enabled.
Across D/E/F/G it verifies identical observations and transition outputs,
actual `bar_open` and `tick` entry fills, the filled quote and thesis identity,
position fields, account balance/equity, and the equity curve (`2 passed`). The
tick case uses one shared deterministic TickBook with zero randomized latency;
it verifies tick entry-fill parity, not a tick stop/target exit. GitHub Actions for
`44ec01129c0276abdce6a228f8bd20b693d7f721` reported 15/15 checks passed.

The later attempt56 full-tree gate passed on ARM GH200: Ruff format found all
800 files formatted, Ruff lint passed, Mypy passed all 800 source files, and
the focused factory/parity file passed 12 tests in 6.65 seconds. Mypy initially
flagged the generic DataFrame index type in the new TickBook fixture; the test
now constructs a typed `DatetimeIndex` before timezone conversion. The complete
gate output is retained at
`/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt56/quality-gate2.log`.

### Stage A gate status

The implementation and bounded encoder/core screens are complete. The actual-
fill parity gate is closed for both the bar-open and deterministic TickBook
entry-fill fixtures. The dashboard
timing and callback-inclusive runtime estimate gates are also closed with the
measurements above. No 2M trained-policy evidence exists: Stage B remains
gated because D fails the substantial-margin single-GH200 runtime check, and
the plan requires explicit user GO before any 2M E/F/G campaign.

The timer harness prepared each 2M run configuration and model to construct the
production-equivalent evaluation provider and dashboard inputs, then directly
invoked only the dashboard evaluation function. It never called `model.learn`,
made no training-step progress, and wrote no training checkpoint. The setup
log's “Training PPO for 2000000 timesteps” line is emitted during preparation
and is not evidence of a training run.

No 2M E/F/G benchmark was started, and the present request is not treated as
automatic approval for one. Stage B requires these checks, an allocation plan
that passes the runtime gate, and explicit user GO. Current Slurm inventory
at 18:16 EET showed both gpuarm1 GH200s allocated: Stage A job `21264865`
held one GPU, 48 CPUs and 256 GiB host RAM through 23:07 EET; another user's
job `21261802` held the second GPU, 8 CPUs and 64 GiB. gpuarm2 was
`DOWN+NOT_RESPONDING` and not schedulable. The 2M experiment remains pending
rather than silently changing callback cadence or starting a partial matrix.
