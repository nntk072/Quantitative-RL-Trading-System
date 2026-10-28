# Variant C/D GH200 Throughput Audit — 2026-10-28

## Decision

The 100k production-path pilot cleared the requested 70 environment-steps/s threshold:
78.1 steps/s for C and 76.2 for D, with training callbacks enabled. This is a bounded
throughput result, not a 2M result or a complete end-to-end campaign measurement. No 2M
benchmark or full training was started.

The shorter 32,768-step production-path repeat measured 65.6 steps/s for C and 63.7 for
D, so the threshold has not been demonstrated consistently across pilot lengths. Using
the 100k run's measured core time and replay durations, 2M training plus scheduled
callbacks is estimated at about 6.1 hours for C and 6.2 hours for D, before full-calendar
selection, final evaluation, and report export. A 25% reserve on that lower bound is
about 7.6 and 7.8 hours. The current six-hour allocation therefore fails the complete-run
fit gate. The campaign remains **NO-GO for launch**; no 2M or full training run is
authorized in this work.

## Matched pilot setup

All paired probes used the same 2025 training bundle, seed 42, 8 logical environments,
256 steps/environment, 2,048 aggregate rollout transitions, batch size 512, 15 PPO
epochs, and their matched C/D configs. C and D ran concurrently, one trainer per GH200
node, in Slurm allocation `21242906`. Attempts 12–19 measured PPO-core probes with
`bundle/subproc`; attempts 20–21 called the production `SeedRunner.train_model()` path.
None of these pilots evaluated the test split.

The source baseline for the latest measurements was
`16001061f1524ee35dfabb755cf4901d53a9cfbf`. The only intended
policy difference remains the C/D thesis-conditioned execution treatment. The runtime
candidate changes cuDNN algorithm search only; it does not change data, observations,
actions, rewards, PPO geometry, or account rules.

## Throughput measurements

| Pilot | Steps | C seconds | C steps/s | D seconds | D steps/s | Scope |
|---|---:|---:|---:|---:|---:|---|
| Attempt 12 | 8,192 | 251.24 | 32.61 | 297.78 | 27.51 | Unprofiled baseline |
| Attempt 14 | 8,192 | 256.24 | 31.97 | 296.51 | 27.63 | Unprofiled; small encoder cleanup later reverted |
| Attempt 16 | 8,192 | 80.01 | 102.38 | 82.30 | 99.53 | Candidate used a temporary cuDNN-off pilot override |
| Attempt 19 | 32,768 | 354.50 | 92.43 | 395.16 | 82.92 | Unprofiled; actual YAML/runtime config path |
| Attempt 20 | 32,768 | 499.53 | 65.6 | 514.60 | 63.7 | Production path; best-prefix evaluation included |
| Attempt 21 | 100,352 | 1,283.14 | 78.1 | 1,316.36 | 76.2 | Production path; dashboard and best-prefix evaluations included |

Attempts 20 and 21 reused the same train/test bundle manifests and seed 42. Attempt 20
included one best-prefix evaluation per arm; attempt 21 included one dashboard replay and
one best-prefix evaluation per arm. The 100k request produced 100,352 transitions due to
rollout-boundary overshoot. Neither run evaluated the test split. Subtracting the measured
evaluation durations from attempt 21 gives approximate PPO-core rates of 115.3 steps/s
for C and 111.2 for D. These are derived from one paired run, not independent repeats.

Attempt 14 did not show a reliable gain from replacing the encoder's empty-row Python
branch with tensor logic and caching timeframe IDs. That trial was not promoted. Attempt
19 is the repeat at a longer horizon; both arms remained above 70 steps/s. It is one
32,768-step run per arm, so it does not yet satisfy the attached plan's three-repeat
promotion standard.

## Runtime diagnosis

Attempt 15 profiled the second PPO update after warmup. A profiled update is diagnostic
only and its wall time is not used for throughput estimates. It recorded about 6,600
cuDNN convolution calls and 6,600 convolution-backward calls per arm. These operators
accounted for most of the measured CPU-side update time; CUDA kernel time for the whole
update was about 1.5 seconds. The TCN executes nine timeframe branches with multiple
small causal convolutions each. The GH200 remained lightly utilized under the original
setting.

The profile also recorded roughly 39k–40k `aten::item` calls, but their total CPU time
was only about 0.11 seconds and CUDA time about 0.003 seconds. `aten::nonzero` was also a
small share. This does not support treating removal of isolated scalar checks as the
main throughput fix. The profile instead pointed to the cuDNN convolution path and its
variable input shapes. Turning autotuning off produced the large measured gain in
attempts 16 and 19. This is strong evidence for the runtime cause, but still needs
additional unprofiled repeats before being treated as a stable production rate.

## Implemented runtime setting

`config/base/default.yaml` keeps `compute.cudnn_benchmark: true` as the project default.
The matched C and D research overlays both set it to `false`. The training configuration
stage and `measure_ppo_throughput.py` now pass this YAML value into accelerator setup, so
benchmark and ordinary training use the same explicit setting. This preserves existing
configurations unless they opt in to the C/D overlay.

The full-tree gate passed on the GH200 ARM environment for the preceding runtime change:
Ruff format, Ruff check, and Mypy over the full tree; 66 focused tests passed across
encoder, accelerator setup, and matched-benchmark config tests. Attempt 19 also reached 32,768
transitions in each arm, saved/reloaded both checkpoints, retained finite PPO diagnostics
and gradients, selected four idea classes across eight setup timeframes, recorded zero
invalid thesis selections, and passed the structural gate with zero blocking violations.

These are training-engineering checks only. Attempt 19 did not evaluate the 2026 test
period or establish economic viability, generalization, or Variant D's learned
thesis-dependent execution quality.

## How this uses the throughput plan

- **WP0:** retain the exact matched configs, seed, shared bundle, rollout geometry, and
  measured PPO-core timing. Do not mix profiled time with throughput.
- **WP3:** profile after warmup and optimize the measured high-cost path. The current
  evidence favors variable-shape cuDNN convolution autotuning over scalar-check removal.
- **WP2:** the full 2025 training-split replay has now been measured. It takes about
  50.5 minutes per arm. The production dashboard and best-prefix callbacks also remain
  costly; decoupling their cadence from the active-prior controller is the next useful
  runtime investigation.
- **WP4:** defer until environment/IPC timings show that they are material; measured PPO
  update time dominated these runs.
- **WP5:** no PPO geometry, objective, entropy approximation, or architecture changes
  were made. Keep those as separate experiment lineages if considered later.

The plan's 500/1,000 steps/s figures are optimization targets, not the immediate launch
gate. The immediate user gate is 70 steps/s per arm. Attempt 21 clears it with callbacks,
while attempt 20 does not; this rate is not yet repeatable across run lengths. Neither
result substitutes for full-period evaluation timing or allocation headroom.

## Additional production-path evidence

The 100k smoke produced no active best checkpoint in either arm: the train-prefix
selection replay had no qualifying completed trade. This is not an economic-failure
finding from a 2M run, but these pilots cannot provide a selected candidate checkpoint or
establish performance. Training diagnostics remained finite; each arm selected four
idea classes across four observed timeframes, and invalid thesis selections were zero.
These are bounded policy/engineering diagnostics only.

In attempt 21 each evaluation callback took about 3.3–3.6 minutes, or approximately
6.9 minutes combined per arm. Attempt 23 then replayed all 99,492 NY-session bars in the
2025 training split for each unselected 100k checkpoint. The replay took 3,046 seconds
for C and 3,030 seconds for D. Both policies breached the $10,000 max-loss limit (C on
January 16, D on February 26) and made no further position opens, although the chronological
replay continued through year-end. Their net results were −$9,996 and −$9,973 respectively;
this is a training-split failure of the 100k checkpoints, not a 2M result. See the
[full replay report](variant_cd_100k_full_train_replay_20261028.md) and its equity figure.

Adding the 50-minute replay to the existing 6.1–6.2 hour 2M training lower bound makes
the currently approved six-hour paired allocation unfit even before report-only
evaluation and the required time reserve. Defer online monitoring only as an explicitly
recorded matched C/D schedule; it does not repair the negative economic result by itself.

## Slurm and artifact notes

No allocation was canceled. The active allocation was reused, and attempt logs, profiles,
checkpoints, health JSON, and GPU samples remain under:

`/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt12` through `attempt23`.

The untracked repository file `campaign_worker_dispatch.log` was preserved. Earlier
format/type-check failures and short validation commands are recorded in their per-attempt
logs; the attempt 19–21 training steps ran for 7–23 minutes. All artifacts remain
available, and no allocation was canceled.

The commit-candidate gate passed on `gpuarm1` (aarch64): full-tree Ruff format check,
full-tree Ruff lint, full-tree Mypy (`794` source files), and the 10 focused benchmark
tests. Slurm step `21242906.22` completed successfully in 8 seconds, below the required
120-second minimum. This was an operational violation; its log is retained at
`attempt22/commit_gate.log`. The subsequent paired replay step `21242906.23` completed in
50m54s and produced the C/D 2025 equity and trade ledgers under `attempt23`.

## Reproduction artifacts

- Baseline unprofiled pilot: `attempt12/C-pilot.json`, `attempt12/D-pilot.json`.
- Warm operator profiles: `attempt15/C-warm-update-profile.txt`,
  `attempt15/D-warm-update-profile.txt`.
- cuDNN-off screening run: `attempt16/C-pilot.json`, `attempt16/D-pilot.json`.
- Config-path repeat and final validation: `attempt19/C-pilot.json`,
  `attempt19/D-pilot.json`, `attempt19/ci_gate.log`, `attempt19/srun.log`.
- Production callback runs: `attempt20/C-production-callback.json`,
  `attempt20/D-production-callback.json`, `attempt21/C-production-callback.json`,
  `attempt21/D-production-callback.json`, with per-arm GPU samples and launch logs.
- Full 2025 training-split replay: `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt23/{C,D}/training_replay.json`,
  `training_equity.csv`, and `training_trades.csv`.

## Next decision point

**NO-GO for 2M on the current six-hour paired allocation.** The 32k production repeat
measured below the 70 steps/s gate, while the 100k repeat cleared it once; the rate is not
repeatable. Full training-split replay also costs about 50 minutes and both 100k
checkpoints fail the max-loss survival gate. Do not start 2M/full training from this
evidence. Preserve 2026 as report-only and apply the attached plan's WP2 evaluation
decoupling work before estimating the next campaign again.
