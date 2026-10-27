# Variant C/D GH200 Throughput Audit — 2026-10-28

## Decision

The warmed C/D pilot now clears the requested 70 environment-steps/s threshold with
`torch.backends.cudnn.benchmark` disabled. This is a bounded training-throughput result,
not a 2M result or an end-to-end campaign estimate. No 2M benchmark or full training was
started.

The measured PPO-core rates imply about 6.01 hours for 2M steps in C and 6.70 hours in D.
Those linear estimates omit production callback evaluation, model selection, final replay,
and report export. With a 25% reserve they become 7.51 and 8.37 hours before those tasks.
The current six-hour allocation therefore does not meet the complete-run fit gate. The
campaign remains **NO-GO for launch** until repeated throughput and end-to-end time are
measured and an adequate allocation is available.

## Matched pilot setup

Both arms used the same 2025 training bundle, seed 42, 8 logical environments, 256
steps/environment, 2,048 aggregate rollout transitions, batch size 512, 15 PPO epochs,
and their matched C/D configs. C and D ran concurrently, one trainer per GH200 node, in
Slurm allocation `21242906`. The run used `bundle/subproc`; production dashboard,
selection, full-calendar replay, and test evaluation were not enabled.

The source baseline was `9e56efc7fbe2e6696d6266fc11a1544d221918f6`. The only intended
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

The full-tree gate passed on the GH200 ARM environment for this change: Ruff format,
Ruff check, and Mypy over the full tree; 66 focused tests passed across encoder,
accelerator setup, and matched-benchmark config tests. Attempt 19 also reached 32,768
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
- **WP2:** still required before a campaign ETA is final. Production callbacks and final
  evaluations were excluded from these pilots; measure their time separately.
- **WP4:** defer until environment/IPC timings show that they are material; measured PPO
  update time dominated these runs.
- **WP5:** no PPO geometry, objective, entropy approximation, or architecture changes
  were made. Keep those as separate experiment lineages if considered later.

The plan's 500/1,000 steps/s figures are optimization targets, not the immediate launch
gate. The immediate user gate is 70 steps/s per arm, and passing that core-rate check does
not substitute for repeatability, production callback timing, evaluation time, or
allocation headroom.

## Slurm and artifact notes

No allocation was canceled. The active allocation was reused, and all attempt logs,
profiles, checkpoints, health JSON, and GPU samples remain under:

`/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt12` through `attempt19`.

The untracked repository file `campaign_worker_dispatch.log` was preserved. During this
work, three validation steps unexpectedly finished under the repository's 120-second
minimum: attempt 14 stopped at an initial Ruff format failure (1 second), attempt 15's
full-tree checks completed in 8 seconds, and attempt 18's 8,192-step fast pilot completed
in 1 minute 57 seconds. Their logs are preserved. After the attempt 18 duration was
diagnosed, attempt 19 was a separate 32,768-step config-path validation and ran for seven
minutes. No further Slurm steps were started after attempt 19.

## Reproduction artifacts

- Baseline unprofiled pilot: `attempt12/C-pilot.json`, `attempt12/D-pilot.json`.
- Warm operator profiles: `attempt15/C-warm-update-profile.txt`,
  `attempt15/D-warm-update-profile.txt`.
- cuDNN-off screening run: `attempt16/C-pilot.json`, `attempt16/D-pilot.json`.
- Config-path repeat and final validation: `attempt19/C-pilot.json`,
  `attempt19/D-pilot.json`, `attempt19/ci_gate.log`, `attempt19/srun.log`.

## Next decision point

The throughput candidate has passed a bounded paired repeat, not a full campaign gate.
Before any 2M run, obtain additional unprofiled C/D repeats and measure the production
callback, checkpoint-selection, full-period evaluation, and export path. Keep 2026
report-only. Do not infer a trading-performance result from these throughput pilots.
