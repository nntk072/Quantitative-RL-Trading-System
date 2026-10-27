# Planning brief: make the matched C/D MTF benchmark runnable

## Decision requested

Review the repository's current matched Variant C/D 2M setup and give an implementation-ready plan to run both variants concurrently on **one GH200** while preserving a valid matched experiment. Focus on measured runtime, CPU/RAM headroom, and the lowest-risk throughput improvement. Do not propose a new model architecture or change the C/D treatment contrast.

The benchmark must not start until the runtime plan has a bounded, measured acceptance gate. A 2M run must fit the approved allocation window, and two concurrent runs must fit the node's CPU and host-memory limits without OOM or altering the 8-environment specification.

## Repository and experiment

- Work on `main`; baseline parent before this readiness change: `d0cfde3d871086ea0db381631c3025947a8185df`.
- The MTF thesis policy uses a causal multi-timeframe encoder and a masked 109-category primary thesis (idea, setup timeframe, direction).
- Variant C uses `thesis_hybrid_v1`: a shared market representation, masked thesis selection, and ordinary execution actor.
- Variant D uses `thesis_conditioned_v1`: the same thesis selection, with the execution actor conditioned on the selected thesis.
- Matched overlays: `config/research/thesis_mtf_reasoning_2m.yaml` and `config/research/thesis_mtf_reasoning_conditioned_2m.yaml`.
- Both specify 2,000,000 PPO timesteps, `n_envs=8`, `n_steps=2048`, batch size 512, 15 epochs, checkpoint interval 250,000, and the same observation/action schema, data, reward, simulator, and execution settings. Their intended policy-distribution difference is the C/D treatment.
- Both enable `features.include_strategy_state` and per-timeframe entry ideas. This is required by the configured PO3/IFVG strategy.
- At the time of the smoke, the effective data/vector path was the default `env.data_source=frames`, `env.vector_backend=subproc`. The repository also contains shared immutable environment bundles and a `sharded_bundle` vector backend. Inspect their actual behavior before recommending a switch.
- `docs/research/variant_d_benchmark_protocol.md` lists the policy and reporting acceptance gates.

## Work in this readiness change

The implementation adds exact masked conditional-entropy computation for Variant D, preserves completed-position thesis and SL/TP provenance, adds corrected eligibility-adjusted selection summaries and completed-trade performance by idea/timeframe, and writes thesis selection/performance heatmaps plus training activity/entropy figures. It also pins exact environment geometry for these research overlays and fixes evaluation to forward `thesis_actions` into `TradingEnv`.

Review these sources and tests in the repository rather than assuming this summary is complete:

- `learning/rl/hybrid.py`
- `evaluation/metrics/thesis_policy.py`
- `evaluation/reporting/export.py`
- `evaluation/reporting/thesis_plots.py`
- `evaluation/rollout/model.py`
- `training/runner/configuration_stage.py`
- `training/runner/seed_runtime.py`
- tests under `tests/test_models`, `tests/test_envs`, `tests/test_eval`, `tests/test_train`, plus `tests/test_rollout.py` and `tests/test_plots_export.py`.

## Observed smoke evidence (not a benchmark)

On 2026-10-27, one bounded Variant D smoke used seed 42, 384 PPO timesteps, 8 environments, batch 64, one epoch, and a two-day report-only test slice beginning 2026-10-15. This was solely an engineering smoke; it cannot support economic conclusions.

- PPO `learn()` took 213.154 seconds for 384 timesteps: approximately 1.8 environment timesteps/second.
- The two-day report-only evaluation took 31.618 seconds and recorded 36 trades, net PnL +$82.77, +0.08% return, 2.83% maximum drawdown, and survival. Treat these figures as noisy smoke output, not performance evidence.
- The checkpoint was saved as `ppo_final.zip`.
- The first smoke exposed a real evaluation-path bug: `thesis_actions` was present in shared evaluation kwargs but dropped before `TradingEnv` construction. The code now forwards it and has a regression test.
- A rerun passed training and the short test replay. The full 2025 in-sample replay was explicitly interrupted before completion to return the GPU to the requested quality gate; therefore no complete smoke train/test report exists.
- The smoke config used the production feature cache `f3291416492c78b3`, with 351,432 training bars, 2,730 test bars, 975 feature columns, and tick coverage of 99,492/99,492 training and 782/782 test decisions.
- A separate one-run actor microbenchmark compared C and D with all 109 thesis choices eligible (a worst-case mask): D forward and `evaluate_actions` calls were about 14–15% slower. Its PPO update-time comparison was too short/noisy to interpret. This is a limited actor-level measurement, not a full training-throughput comparison.

## Measured resource evidence

Slurm allocation `21239541` on `gpuarm1` requested 1 GH200 (144 GB HBM), 16 CPUs, 128 GB host RAM, and 12 hours. During the run, Slurm reported peak host RSS 119,098,420 KiB (about 113.6 GiB, 89% of the allocation), peak GPU memory 1,178 MiB, and peak GPU utilization 13%. The one-second inspection step `21239541.1` failed with exit 126 because an x86 `rg` executable was invoked on ARM; no further diagnostic steps should be created. Preserve the allocation and existing tmux session; never use `scancel`.

At the observed 1.8 steps/second, straight-line 2M training is about 12.9 days per variant. One 2M run within 12 hours needs about 46.3 steps/second, roughly 26 times the measured smoke rate. Two concurrent variants need at least that rate per variant and substantially more aggregate CPU/memory headroom. The current 16-CPU/128-GB frame-backed allocation is not evidence that this is feasible; its RAM peak is already close to the limit. This extrapolation is a warning estimate from a tiny pilot, not a promised campaign runtime.

The full-split 2025 smoke replay was stopped by explicit user direction. It is not running now. The allocation remains active for quality gates. The untracked `campaign_worker_dispatch.log` is user data and must remain untouched and uncommitted.

Both C and D use a masked probabilistic thesis selection. D additionally conditions the execution actor on the sampled thesis. Do not attribute the full D smoke runtime to probability sampling without a matched C/D throughput measurement; the observed low GPU utilization and high host-RAM use suggest the environment/data path also needs investigation.

## Questions for the planning agent

1. Trace the actual PPO collection path and identify why the 384-step MTF run takes 213 seconds. Separate environment stepping, process/IPC overhead, MTF policy inference, PPO updates, and cache/data-loading costs. State which are measured and which are hypotheses.
2. Compare the existing `frames`/`subproc` path with the repository's shared-bundle and `sharded_bundle` path. Can the immutable train/test bundle be built once and reused safely by both C and D? Identify any cache-key or concurrent-build race risks.
3. Recommend the smallest configuration or implementation change that improves throughput without changing C/D semantics. Keep `n_envs=8`, action/observation schemas, rollout geometry, and data/simulator identity fixed unless the plan explicitly labels a new experiment.
4. Assess whether two 8-env runs can safely share one GH200. Give required CPU, host RAM, and GPU-memory headroom based on repository behavior and measured evidence. The target is one GPU, not two separate GPU allocations.
5. Define a bounded throughput acceptance pilot with exact steps, duration, measured `steps/sec`, resource limits, and a pass/fail threshold. It must establish a realistic 2M ETA for each arm and the pair before either 2M campaign starts.
6. Confirm the minimum output checks for both arms: finite PPO diagnostics and reloadable checkpoints; trade activity and thesis entropy; selection across ideas/timeframes; exactly zero invalid thesis selections and structural SL/TP violations; train/test reports and plots; and separate interpretation of the exposed 2026 report-only slice.
7. List unresolved blockers and the exact source/tests needed to close each one. Do not infer success from the smoke's two-day PnL.

## Constraints

- Preserve the existing C/D architecture and matched policy contrast.
- Do not launch a 2M/20M campaign as part of planning or while throughput remains unverified.
- Do not create another branch/worktree, duplicate campaigns, or another GH200 allocation to split C from D.
- Keep allocation supervision alive; do not cancel Slurm jobs. Follow `.agents/rules/triton-slurm.md` and the CPU/RAM/GPU inventory requirement before any new allocation request.
- Keep raw output, caches, checkpoints, and `campaign_worker_dispatch.log` out of Git unless explicitly requested.
- Return a concrete recommendation and an evidence-gated execution sequence, not a generic architecture review.
