# Matched C/D throughput readiness and gate review

**Status:** Matched C/D 100k pilots, complete train/report-only test replays, and a four-shard runtime comparison are complete. Attempt 38's instrumentation failed at serialization; the corrected attempt 39 saved both diagnostic checkpoints and measured no meaningful throughput gain from four-shard bundling. No 2M training was started.

**Repository:** `/scratch/work/nguyenl37/Quantitative-RL-Trading-System`

**Measured-run source:** `main`, `ce9c30472e9402b50d8ca84cf8f29704436e0d0a`

**Source baseline for the new profile:** `main` at `bb4cb6706d5d4d75a69c0a86b18a343c59a9e10a`; only this audit document changed for the final handoff. The untracked `campaign_worker_dispatch.log` is preserved and excluded.

**Allocations:** Slurm `21247526` (gpuarm1) and `21252045` (gpuarm2), one GH200 each. Keep their interactive shells and allocations intact after these runs.
**Purpose:** bounded 100k production-path pilots, train/test report replay, and pre-2M readiness. This is not a 2M benchmark or full training result.

## Decision

**2M decision: NO-GO on the current evidence.** Both C and D final 100k checkpoints were rejected by the deterministic train-prefix survival selector, and both full training replays later reached the account loss stop. A fresh 2M run was not started.

The earlier dashboard-enabled 100k runs (attempts 21, 25, and 26) cleared the 70 environment-steps/s threshold in both arms, with C 78.21–80.82 steps/s and D 75.33–79.79. The deferred-dashboard attempts 32 and 37 also passed the threshold. They differ by repeat: attempt 32 reached C 96.27/D 89.06 steps/s; attempt 37 reached C 85.65/D 86.69. Throughput passed, but the deferred-mode measurements show run-to-run variation and do not establish a stable 2M runtime estimate.

This is a throughput pass only. It does not establish 2M readiness. The saved best-checkpoint status is `NO_ACTIVE_CHECKPOINT` for both arms in attempts 32 and 37. Attempt 33 identified daily-loss and max-drawdown events as the deterministic callback rejection reason; its replays stopped after 5,293 of the planned 20,000 prefix bars. Attempt 35 then replayed the final checkpoints across the full train and report-only test splits, where both variants reached the account loss stop. **Do not scale this policy/config to 2M without resolving that survival failure and an explicit user decision.**

## Matched production-path repeats

Each run used seed 42, requested 100,000 transitions and completed 100,352 because of PPO rollout boundaries, 8 environments, 2,048 aggregate rollout transitions, batch size 512, 15 epochs, shared train/test bundle, and the matched C/D configs. Dashboard and best-prefix callbacks were enabled. Attempt 26 used the pushed `ce9c304` source; attempts 21 and 25 used the same policy/runtime source before the explicit `prior_every=100000` config key. Its value equals the pre-existing prior cadence, and the default behavior is unchanged.

| Attempt | C learn wall | C steps/s | D learn wall | D steps/s | Paired step wall |
|---|---:|---:|---:|---:|---:|
| 21 | 1,283.14 s | 78.21 | 1,316.36 s | 76.23 | 22:45 |
| 25 | 1,241.64 s | 80.82 | 1,332.13 s | 75.33 | 23:17 |
| 26 | 1,266.45 s | 79.24 | 1,257.63 s | 79.79 | 21:56 |
| **Mean** | **1,263.74 s** | **79.42** | **1,302.04 s** | **77.12** | — |

Across the three runs, sample standard deviation was 1.32 steps/s for C (CV 1.66%) and 2.36 for D (CV 3.06%). Every attempt included one dashboard prefix replay and one best-checkpoint prefix replay per arm. Attempt 26's evaluation events took about 3.3–3.5 minutes each.

## Learner and early-evaluation diagnostics

Attempts 25 and 26 each wrote 49 learner diagnostic rows per arm through step 100,352. All numeric values were finite; both arms recorded exactly zero invalid thesis selections. Final rollout diagnostics were consistent across attempts 25 and 26:

| Measure | C | D |
|---|---:|---:|
| Thesis entropy | 0.613 nats | 0.601 nats |
| No-trade rate | 67.48% | 49.90% |
| No-trade rate when eligible | 59.78% | 38.04% |
| Selected idea classes | 4 | 4 |
| Selected setup timeframes | 6 | 6 |
| Invalid thesis selections | 0 | 0 |
| Best-checkpoint status | NO_ACTIVE_CHECKPOINT | NO_ACTIVE_CHECKPOINT |

The stochastic 20k training-prefix dashboard replay was identical for attempts 25 and 26: C returned −10.294% over 228 trades (profit factor 0.722, maximum drawdown 12.82%); D returned −9.725% over 123 trades (profit factor 0.536, maximum drawdown 10.80%). These are training-prefix diagnostics, not full-year results or test results.

`BestCheckpointEvalCallback._run_eval()` marks a checkpoint inactive when it has fewer than one completed trade, any breach event, or nonfinite end equity. The current JSON stores only the combined status, so it cannot identify which condition applied. The separate stochastic monitor's trades do not answer that deterministic-selection question.

## Runtime and end-to-end estimate

GPU samples from attempts 20–21 showed median utilization around 9–10%, peaks 26–27%, and about 2 GB HBM use. Earlier profiling attributed much of update time to CPU-side dispatch for thousands of small variable-shape cuDNN convolutions; disabling cuDNN autotuning was the measured runtime change. These observations do not show GPU memory capacity as the bottleneck.

Using the three-repeat mean PPO-core time (`learn wall` minus dashboard and best-eval time), scaling the 100k cadence to 2M, budgeting 20 dashboard evaluations and one endpoint best-checkpoint evaluation gives about **5.94 hours for C** and **6.11 hours for D** of learning. This excludes preparation, checkpoint/report work, the required full 2025 replay, and report-only testing. The prior full 2025 replay took about 50.5 minutes per arm across 99,492 bars; the 2026 test split has 79,069 NY bars, but its replay duration has not been measured here. A six-hour allocation is not enough for a defensible end-to-end paired result. A 12-hour paired allocation appears plausible from current measurements, subject to resource headroom and the unresolved correctness/selection gate.

## Attempt 27: deterministic-selection reason diagnostic

The paired diagnostic step failed after 45 seconds and is preserved under `attempt27/`. It prepared the run and tried to read `runner.best_checkpoint_callback` before it exists. Source inspection showed that the callback is constructed inside `SeedRunner.train_model()`, after preparation; calling that method would train, so it must not be used for a replay-only diagnostic. The attempt created no `ppo_final` or `ppo_best` checkpoint and performed no training. Slurm step `21242906.27` is recorded `FAILED`, exit code 1. No retry was launched.

A corrected harness reconstructed the callback's environment factory directly from `RunAssets`/`EnvSpec` without calling `train_model()`. It ran on the existing allocation as step `21242906.28`, completed successfully in 3m36s, and trained no model. It evaluated only the deterministic training prefix; preparation loaded the shared test bundle, but no test result or test metric was consumed.

## Historical attempts and preserved evidence

- Attempts 21, 25, and 26, including checkpoints, JSON, logs, and GPU samples: `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt{21,25,26}/`.
- Failed diagnostic logs: `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt27/`.
- Earlier full 2025 replay and equity/trade ledgers: `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt23/`.
- The untracked repository file `campaign_worker_dispatch.log` remains untouched.
- Allocation `21242906` was preserved through its original work. The current allocations are listed at the top of this report; neither was canceled.
- Prior full-year replay of the 100k attempt-21 checkpoints failed the $10,000 max-loss survival gate for both C and D. That evidence remains report-only for this short pilot and is not a 2M result.

**Fresh 2M C/D training remains gated on user acceptance.** The newer attempt-32 checkpoints also fail deterministic train-prefix survival and the full-split replay reaches the max-loss stop. Before any future 2M run, decide whether to change the policy/config or explicitly accept a benchmark of the currently failing policy, then verify the end-to-end run fits the requested allocation with reserve. No 2M/full training has been started.

### Test replay runtime estimate (not measured)

Scaling the observed 2025 replay rate of 99,492 bars in 3,030.2 seconds to the 79,069-bar test split estimates about **2,408 seconds (40.1 minutes) per arm**. This is a linear bar-count estimate, not a timed test replay. With the slower 2M learning projection (D, 6.11 hours) and the observed 2025 replay duration (50.5 minutes), paired C/D training plus both chronological replays is approximately **7.62 hours wall time** if the arms/replays run in parallel on separate GPUs. A 25% reserve raises the planning estimate to **9.53 hours**, before setup, final report generation, checkpoint exports, and any unexpected delays. This supports planning around a 12-hour allocation; it does not clear the unresolved deterministic checkpoint-selection gate or authorize the 2M run.


### Attempt 28: deterministic best-checkpoint rejection reason

The deterministic prefix replays explain the `NO_ACTIVE_CHECKPOINT` status. Each run was configured for the 20,000-bar training prefix, but the evaluation environment stopped early at 5,293 M1 steps after daily-loss guardrail events; therefore these are partial-prefix survival diagnostics, not completed 20k-prefix results. Both policies traded and ended at finite equity, so neither zero trades nor nonfinite equity caused rejection.

| Variant | Steps before stop | Completed trades | Final equity | Minimum recorded equity | Daily-loss events | Callback result |
|---|---:|---:|---:|---:|---:|---|
| C | 5,293 / 20,000 | 139 | $90,504.14 | $90,063.56 | 2 (Dec 31, 2024; Jan 2, 2025) | Ineligible: survival failed |
| D | 5,293 / 20,000 | 316 | $93,730.33 | $92,753.23 | 2 (Dec 31, 2024; Jan 13, 2025) | Ineligible: survival failed |

The exact callback rule rejects any replay with a breach event. Here both replays recorded `daily_loss` events despite ending above the $90,000 account floor; these are daily-limit failures, not evidence that the static maximum-loss floor was crossed. The resulting `NO_ACTIVE_CHECKPOINT` is therefore explained by the configured train-prefix survival gate. Full JSON records, including times and event equity, are in `attempt28/C-best-eval-diagnostic.json` and `attempt28/D-best-eval-diagnostic.json`. No `ppo_best` checkpoint was produced by the diagnostic. The attempt28 setup directories do not constitute trained checkpoints.

### Deferred-dashboard pilot attempts 29–31

A small opt-in RNG-isolation guard was added around training-prefix dashboard evaluation so observer-only stochastic evaluation can restore Python, NumPy, Torch CPU, and available CUDA RNG states. The production default remains off. The callback already supports `eval_every=0`, which preserves the active-prior cadence while deferring the costly dashboard replay; the planned 100k C/D throughput pilot did not reach training.

Source review confirms the stochastic dashboard path reaches `SB3DecisionProvider.predict()` and calls the policy's `model.predict(..., deterministic=False)`; no explicit per-evaluator RNG generator is supplied on that path. The global-state guard covers those process RNGs. Attempts 36 and 37 subsequently verified the guard with dashboard tests on GH200 and ran paired deferred-dashboard pilots; the failures below are historical.

| Attempt | Outcome | Preserved cause |
|---|---|---|
| 29 | Failed after 1s; no gate checks beyond Ruff, no training | Ruff required `Iterator` from `collections.abc` (`UP035`). |
| 30 | Failed after 57s; no training | Full Ruff passed; full Mypy found untyped CUDA initialization calls and NumPy RNG-state index typing in the new test. |
| 31 | Failed after 55s; no training | Full Ruff and full Mypy passed. Focused dashboard tests: 18 passed, 1 failed because the test callback's `num_timesteps` remained 0; fixed in the working tree and later verified in attempts 36/37. |

These failures are preserved in `attempt29/`, `attempt30/`, and `attempt31/`; they produced no checkpoints. Their dashboard-delay estimate was later measured by attempts 32/37. The optional RNG-isolation code and tests are committed at `bb4cb67` after the full-tree quality gate passed.

### Remaining decisive-evidence gaps

The prior full-year replay artifacts in attempt 23 predate the thesis-decision report contract: their `thesis_policy_metrics` field is empty. Attempt 35 repaired reporting for the attempt-32 checkpoints and generated paired training plus report-only test traces. On those outputs, C/D recorded zero invalid thesis choices, zero semantic violations, zero measured structural SL/TP violations, four selected idea classes across nine timeframes, and D execution conditioning was active. The missing fields in attempt 23 remain **unmeasured**; the newer attempt-35 measurements do not retroactively fill them.

The current decisive blocker is economic survival, not report availability: both C and D failed the deterministic selection screen, then reached the account loss stop in full training replays. No eligible checkpoint exists. The focused RNG-isolation verification and portable train/test reporting are complete. A 2M run has not been started and still requires the user's acceptance.


### Deferred-dashboard counterfactual (historical estimate, superseded by attempts 32/37)

Attempt 26 measured dashboard-prefix replay at 210.42s for C and 198.14s for D per 100,352-step production run. If `training.dashboard.eval_every=0` removes those observer-only replays while retaining the deterministic best-prefix selection, the 100k `learn()` wall estimates become 1,056.02s for C and 1,059.50s for D. These correspond to about 95.0 and 94.7 production steps/s, respectively; the existing measured rates were 79.24 and 79.79 steps/s. This is arithmetic subtraction from attempt 26, not an observed deferred-mode run.

Across 20 dashboard intervals, the measured per-event durations imply 4,208s saved for C and 3,963s for D (about 1.17h and 1.10h). Subtracting those from the previous 2M learning projections gives about 4.77h for C and 5.01h for D, with the deterministic best-prefix evaluation retained. Adding the measured 2025 replay and linearly estimated report-only test replay gives about 6.52h paired wall time if the arms/replays run in parallel, or 8.15h with a 25% reserve, before setup and exports. Attempts 32 and 37 later measured deferred-mode 100k throughput; this arithmetic remains a superseded estimate and does not authorize a 2M campaign.

### Attempt 32: deferred-dashboard throughput pilot, observed

Attempt 32 ran on the existing two-GH200 allocation `21242906` as one paired step (`21242906.32`, 20:34 elapsed). Before training, each node passed full-tree `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, and `.venv/bin/mypy .`; each also passed the 34 focused dashboard, hybrid-policy, and thesis-diagnostic tests. One synthetic plot test emitted a Matplotlib identical-y-limits warning. Both arms used seed 42, the matched C/D 2M configs, 8 environments, 2,048 aggregate rollout steps, batch 512, 15 epochs, and 100,000 requested steps; PPO completed 100,352 steps.

| Measure | C | D |
|---|---:|---:|
| PPO learner wall | 1,042.41 s | 1,126.75 s |
| Observed learner throughput | 96.27 steps/s | 89.06 steps/s |
| Model-training wall, including one best-prefix evaluation | 1,047.51 s | 1,131.58 s |
| Deterministic best-prefix evaluations | 1 (202.45 s) | 1 (211.78 s) |
| Stochastic dashboard evaluations | 0 | 0 |
| `ppo_final` checkpoint | saved (103 MB) | saved (103 MB) |
| Best-checkpoint status | `NO_ACTIVE_CHECKPOINT` | `NO_ACTIVE_CHECKPOINT` |

The deferred dashboard setting therefore produced a real throughput improvement over attempts 25/26: C improved from 79.24 to 96.27 steps/s (+21.5%), and D from 79.79 to 89.06 (+11.6%). This is a single repeat, so it does not replace the earlier repeated-rate variance estimate. GPU samples averaged 11.8% utilization for C and 11.2% for D, with peaks of 28% and 26%; peak HBM use was about 2.0 GiB on each node. This is consistent with the earlier low-utilization profile and does not indicate GPU-memory pressure.

The final rollout diagnostics were finite. C's terminal rollout showed 0.613 nats thesis entropy, 67.48% NO_TRADE (59.78% when eligible), four selected ideas, six selected timeframes, and zero invalid selections. D showed 0.601 nats, 49.90% NO_TRADE (38.04% when eligible), four ideas, six timeframes, and zero invalid selections. These are terminal training-rollout statistics, not full-period replay metrics. C selected 666 trade theses in the terminal rollout (15 IFVG retest, 70 unretested IFVG, 99 PO3, 482 standard deviation); D selected 1,026 (16, 152, 65, and 793 respectively).

Both manifests recorded complete tick coverage: 99,492/99,492 train bars and 79,069/79,069 test bars. The test bundle was loaded but not evaluated. The 100k run produced no eligible best checkpoint; `ppo_final` is retained only as an exploratory diagnostic checkpoint.

### Attempt 33: attempt 32 checkpoint-selection reason

The deterministic 20,000-bar selection-prefix replay for each attempt 32 final checkpoint stopped at 5,293 bars. Both policies were active and produced finite account equity, but hard risk events made the callback reject them:

| Variant | Completed trades | Final equity | Minimum equity | Breach events | Callback result |
|---|---:|---:|---:|---|---|
| C | 140 | $90,106.70 | $90,022.02 | 2 daily-loss; 1 max-drawdown (Jan 15, 2025) | Ineligible: survival failed |
| D | 324 | $93,539.13 | $92,530.13 | 2 daily-loss (Dec 31, 2024; Jan 13, 2025) | Ineligible: survival failed |

This directly explains `NO_ACTIVE_CHECKPOINT` for the attempt 32 checkpoints: neither was rejected for inactivity, nonfinite equity, or a missing checkpoint. C reached the max-drawdown guardrail after the two daily-loss events; D's evaluated prefix ended on its second daily-loss event. These prefix results do not establish full-year training or test behavior. Diagnostic JSON and logs are preserved in `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt33/`.

### Revised 2M projection from attempt 32 (estimate, not a run)

Attempt 32 is the first measured pilot with dashboard replays disabled and the best-prefix selector retained. Scaling its measured learner-plus-best-eval time to twenty 100k intervals gives an approximate 5.83 hours for C and 6.28 hours for D, before full chronological replay, bundle/model setup, and report exports. A full 2025 replay previously took about 50.5 minutes per arm; the 79,069-bar 2026 report-only replay is estimated at 40.1 minutes per arm. On two GPUs, parallel 2M learning plus sequential per-arm split replays is roughly 7.8 hours before setup/exports; 25% reserve makes it about 9.8 hours. These projections are not measured, and 2M remains unauthorized pending user acceptance and resolution of the failed survival-selection gate.

### Attempts 34–35: full split replay and report export for attempt 32 checkpoints

Attempt 34's replay completed both splits but initially omitted `train_metrics`/`test_metrics` when calling the exporter, so it produced no usable plot or ledger export. Attempt 35 corrected the replay harness and reran the same attempt 32 final checkpoints, writing progress JSON immediately after each split and exporting full reports. This was an export-harness correction, **not a retraining run**. The source checkpoint SHA, configs, and bundle manifests remain those recorded by attempt 32. Every bar in each split was replayed; reports and ledgers are under `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt35/{C,D}/report/{training,testing}/`.

| Variant | Split | Net PnL | Return | Trades | Win rate | Profit factor | Max drawdown | Breaches | Full split survived |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| C | Train 2024-12-30–2025 | −$10,138.51 | −10.14% | 337 | 45.10% | 0.795 | 11.22% | 5 | No |
| C | Test 2026, report-only | −$10,225.65 | −10.23% | 284 | 44.72% | 0.745 | 13.73% | 2 | No |
| D | Train 2024-12-30–2025 | −$9,959.15 | −9.96% | 1,016 | 43.70% | 0.928 | 20.89% | 8 | No |
| D | Test 2026, report-only | −$10,036.93 | −10.04% | 336 | 39.29% | 0.810 | 15.40% | 4 | No |

Both policies fail the account-survival screen during training, so neither is a viable candidate for a larger run on the current policy/config. The near −10% terminal losses reflect reaching the hard account floor; they should not be read as unconstrained full-year returns. D has materially more trades than C and lower NO_TRADE when a thesis is eligible, but did not improve net survival or profitability. D's thesis-conditioned execution flag is active on both splits; C's is off as designed. Both report four selected idea classes across nine setup timeframes, zero invalid thesis selections, zero semantic violations, and zero measured SL/TP structural violations. Mean thesis entropy is C 0.562/0.551 nats (train/test) and D 0.582/0.607 nats. NO_TRADE is C 73.7%/74.8% and D 55.0%/54.2%; conditional NO_TRADE on eligible thesis steps is C 63.0%/65.3% and D 36.7%/37.0%.

These observations answer the architecture gates: both policies trade; thesis selection is non-degenerate across ideas/timeframes; invalid selections and measured structural violations are exactly zero; train/test policy diagnostics are broadly similar; and D produces thesis-dependent execution. The economic gate fails for both: training expectancy/return remains negative, and both encounter the max-loss stop. The 2026 split is exposed/report-only and is not confirmatory evidence.

Portable split summaries, thesis diagnostics, and figures are committed under [`docs/research/gh200_cd_benchmark_20261028/`](gh200_cd_benchmark_20261028/). Per-bar decision traces and raw trade ledgers remain in the preserved scratch reports under Attempt 35; the portable report intentionally keeps selected figures and aggregate diagnostics small enough for the source repository.

| Variant/split | Equity | Drawdown | Monthly PnL | Thesis choices | Thesis performance |
|---|---|---|---|---|---|
| C training | [plot](gh200_cd_benchmark_20261028/C/training/equity.png) | [plot](gh200_cd_benchmark_20261028/C/training/drawdown.png) | [plot](gh200_cd_benchmark_20261028/C/training/monthly_heatmap.png) | [plot](gh200_cd_benchmark_20261028/C/training/thesis_selection_heatmap.png) | [plot](gh200_cd_benchmark_20261028/C/training/thesis_performance_heatmap.png) |
| C testing | [plot](gh200_cd_benchmark_20261028/C/testing/equity.png) | [plot](gh200_cd_benchmark_20261028/C/testing/drawdown.png) | [plot](gh200_cd_benchmark_20261028/C/testing/monthly_heatmap.png) | [plot](gh200_cd_benchmark_20261028/C/testing/thesis_selection_heatmap.png) | [plot](gh200_cd_benchmark_20261028/C/testing/thesis_performance_heatmap.png) |
| D training | [plot](gh200_cd_benchmark_20261028/D/training/equity.png) | [plot](gh200_cd_benchmark_20261028/D/training/drawdown.png) | [plot](gh200_cd_benchmark_20261028/D/training/monthly_heatmap.png) | [plot](gh200_cd_benchmark_20261028/D/training/thesis_selection_heatmap.png) | [plot](gh200_cd_benchmark_20261028/D/training/thesis_performance_heatmap.png) |
| D testing | [plot](gh200_cd_benchmark_20261028/D/testing/equity.png) | [plot](gh200_cd_benchmark_20261028/D/testing/drawdown.png) | [plot](gh200_cd_benchmark_20261028/D/testing/monthly_heatmap.png) | [plot](gh200_cd_benchmark_20261028/D/testing/thesis_selection_heatmap.png) | [plot](gh200_cd_benchmark_20261028/D/testing/thesis_performance_heatmap.png) |

Attempt 36 used the second approved GH200 allocation (`21252045`, gpuarm2) to rerun `tests/test_train/test_dashboard.py` with the ARM-native `.venv`; **19 tests passed in 16.75s**. The process ran in the existing allocation shell. No extra diagnostic `srun` step was created. This verifies the dashboard RNG-isolation unit coverage on the compute architecture used for the paired pilot.

### Attempt 37: matched deferred-dashboard 100k repeat (complete)

After Attempt 35 finished, one fresh seed-42 100k repeat of each arm was started concurrently inside the already-existing gpuarm1/gpuarm2 allocation shells. It used the matched C/D configs, existing content-addressed train/test bundles, 8 environments, 2,048 aggregate rollout steps, batch size 512, 15 PPO epochs, `eval_every=0`, and `isolate_eval_rng=true`; 100,000 requested steps produced 100,352 rollout-aligned steps. It was a bounded throughput/reproducibility pilot only. It did not include a second full train/test replay and did not start the 2M run.

| Measure | C | D |
|---|---:|---:|
| PPO `learn()` wall | 1,171.61 s | 1,157.54 s |
| Effective throughput | 85.65 steps/s | 86.69 steps/s |
| Model-training wall, including one deterministic best-prefix evaluation | 1,176.85 s | 1,162.69 s |
| Best-prefix evaluation | 1 (233.60 s) | 1 (215.51 s) |
| Dashboard evaluations | 0 | 0 |
| `ppo_final` checkpoint | saved (exploratory) | saved (exploratory) |
| Best-checkpoint status | `NO_ACTIVE_CHECKPOINT` | `NO_ACTIVE_CHECKPOINT` |

Both arms pass the 70 steps/s throughput screen. Compared with attempt 32, the repeat was 11.0% slower for C and 2.7% slower for D, so the deferred-mode estimate has visible run-to-run variance. The per-second GH200 sampler observed mean GPU utilization of 10.2% (peak 26%) for C and 10.8% (peak 28%) for D; mean HBM use was 1.84/1.86 GiB, peaking at about 1.95 GiB per node. The GPUs were not near compute or memory saturation during these pilots. This is observational evidence, not a full hardware bottleneck analysis.

Both checkpoints again failed the deterministic training-prefix survival selector. The new run adds throughput and repeatability evidence, not an eligible model. Detailed JSON, logs, config identities, and raw GPU samples are preserved in `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt37/`.

### Attempt 38: matched C/D PPO phase profile (instrumentation failure)

Both arms reached 100,352 steps with the same seed/config/bundle and recorded finite training diagnostics. However, adding timing wrappers as instance attributes made PPO's final model serialization attempt to pickle worker-process authentication state; both `ppo_final.zip` files are zero bytes and the phase JSON was not written. These runs are instrumentation failures, not eligible checkpoints or benchmark candidates. Logs, diagnostics, and hardware samples are preserved in `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt38/`.

Partial hardware trace before the failure: average GPU utilization was about 9–10% (peaks 25–26%); peak GPU memory was about 1.94 GiB. The job cgroups reached about 32.5–33.8 GiB host memory, while the highest-CPU Python process averaged roughly 89–92% of one core. This suggests the learner was waiting on CPU-side rollout work, but does not isolate environment stepping from policy inference or vector-worker IPC. A replacement profile uses class-level method wrappers that do not add state to the serialized PPO instance.

### Attempt 39: C/D four-shard bundle backend comparison (complete)

Attempt 39 repeats seed 42, the matched C/D configs, the same content-addressed bundle, 8 logical environments, 2,048 aggregate rollout steps, batch 512, 15 PPO epochs, 100,000 requested steps, deferred dashboard evaluation, and deterministic best-prefix selection. The only runtime intervention is `env.vector_backend=sharded_bundle` with four worker shards; class-level wrappers time `collect_rollouts()`, `PPO.train()`, and best-prefix evaluation without changing PPO instance serialization. Before C started, the existing seeded sharded-bundle trace/order parity test passed on gpuarm1. Both arms reached 100,352 steps, saved ~103 MiB diagnostic checkpoints, and had `NO_ACTIVE_CHECKPOINT` status. This is a bounded throughput diagnosis, not a candidate benchmark or 2M run.

| Measurement | C | D |
|---|---:|---:|
| PPO learn wall | 1,175.58 s | 1,151.09 s |
| Throughput | 85.36 steps/s | 87.18 steps/s |
| Rollout collection incl. best-prefix evaluation | 881.48 s | 853.61 s |
| Rollout collection excluding best-prefix evaluation | 660.32 s | 641.41 s |
| PPO optimizer updates | 293.22 s | 296.67 s |
| Deterministic best-prefix evaluation | 221.17 s | 212.21 s |
| Other PPO learn overhead | 0.88 s | 0.82 s |
| Learn-time change vs attempt 37 subprocess backend | +0.34% | −0.56% |

Four-shard bundling did not materially improve throughput: C was about four seconds slower and D about seven seconds faster than attempt 37, both within observed run-to-run variation. Rollout collection excluding the selector was the largest phase (about 56% of PPO learn time), optimizer updates used about 25%, and the selector about 18–19%. Mean GPU utilization was 10.4% for C and 10.9% for D (peaks 26%/28%); GPU memory averaged 1.85 GiB and peaked at 1.94/1.95 GiB. Job-cgroup peak host memory was 32.5/33.0 GiB. Average cgroup CPU use was 1.14/1.09 cores; the top Python process averaged about 90% of one core. These measurements point away from GPU saturation and show no benefit from reducing eight worker pipes to four shards. The exact environment-step versus inference/IPC split remains unmeasured; no further backend change is justified by this comparison.

Full JSON, per-call timings, logs, checkpoints, and raw samples are preserved in `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt39/`.

### Final repository verification

The implementation commit `bb4cb67` passed full-tree ARM-native Ruff format, Ruff lint, and Mypy, plus 19 dashboard tests. The final gate was repeated on gpuarm1 after the benchmark: Ruff format checked 794 files; Ruff lint and Mypy passed (794 source files); the relevant VecEnv and dashboard tests passed (25 tests, 13.82 s); `git diff --check` passed. Attempt 39 separately passed the seeded sharded-bundle trace/order parity test (1 test, 4.81 s) before training. No full repository pytest suite was run. The audit and benchmark evidence are ready for the single requested commit/push.

### Handoff

The RNG-isolated optional dashboard evaluation is implemented, defaults off, and verified on GH200. The report export gap is repaired in the attempt 35 replay harness, and complete C/D train plus report-only test reports exist. Architecture/correctness diagnostics pass for both policies, including exact-zero invalid thesis and measured structural violations; Variant D execution conditioning is active. Economic survival fails for both, and all 100k best-checkpoint selectors remain inactive. Throughput exceeds the screening threshold but varies by repeat. The current plan therefore ends at bounded evidence and a **no-go for 2M on this policy/config**; preserving the failed result is the scientifically defensible outcome.
