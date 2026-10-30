# Training Domain

## Primary Files

| File | Role |
|------|------|
| `training/runner/training.py` | Full RL training pipeline |
| `training/configuration/strategy_overlays.py` | Strategy overlay path lookup and validated merge |
| `training/runner/backtest.py` | Backtest runner entry point |
| `training/runner/setup_runtime.py` | Composition root for configuration, dataset, and run-asset preparation |
| `training/runner/stages.py` | Typed configuration, data, run-assets, and preparation stage results |
| `training/runner/seed_stages.py` | Typed prepared, trained, evaluated, and persisted seed handoffs |
| `training/runner/configuration_stage.py` | Resolve configuration and device policy |
| `training/runner/data_stage.py` | Prepare and split datasets/features for a training run |
| `training/runner/run_assets_stage.py` | Build run output, worker, and evaluation assets |
| `training/setup/learner.py` | Builds stable fit requests and selects the learner backend |
| `training/runner/seed_runtime.py` | Per-seed prepare/fit/evaluate/persist composition |
| `training/reporting/training_curves.py` | Static and interactive training progress plots |
| `training/artifacts/__init__.py` | Public API for run snapshots, logs, schemas, aggregation, and evaluation outputs |
| `training/artifacts/snapshots.py` | Immutable resolved YAML configuration snapshots |
| `training/artifacts/evaluation_result_writer.py` | Train/test evaluation JSON and Markdown writer |
| `learning/rl/agent.py` | PPO/SAC construction and composition with the encoder registry |
| `training/runner/baselines.py` | Baseline strategy runner |
| `learning/rl/callbacks.py` | SB3 rollout diagnostics, risk, checkpoint and stop callbacks |
| `learning/rl/auxiliary.py` | Auxiliary prediction-head rollout callback |
| `simulation/environment/trading_environment_factory.py` | Owns environment construction; `training/setup/environments.py` retains training-only policy and compatibility entry points |

## Key Symbols

| Symbol | File | Purpose |
|--------|------|---------|
| `main()` | `training/runner/training.py` | Full training pipeline entry |
| `make_env()` | `simulation/environment/__init__.py` | Public environment constructor |
| `strategy_from_cfg()` | `simulation/environment/trading_environment_factory.py` | Build (strategy, reward, weight) from config |
| `merge_strategy_config()` | `training/configuration/strategy_overlays.py` | Applies one strategy YAML through the shared configuration schema validator |
| `BestCheckpointEvalCallback` | `learning/rl/callbacks.py` | Eval-based checkpoint saving |
| `AuxiliaryTrainerCallback` | `learning/rl/auxiliary.py` | Auxiliary head training callback |
| `write_run_config_snapshot()` | `training/artifacts/snapshots.py` | Atomically write a resolved run configuration once and reject identity rewrites |
| `attach_run_log()` | `training/artifacts/logging.py` | Attach the run-local transcript to the training logger |

## CLI flags (`training/runner/training.py`)

| Flag | Purpose |
|------|---------|
| `--mvp` | 30-day smoke test |
| `--force` | Rebuild data/feature caches |
| `--algo ppo\|sac` | RL algorithm |
| `--arch tcn\|gru\|transformer` | Encoder architecture |
| `--reward dsr\|sweep` | Reward function |
| `--strategy baseline\|po3_ifvg\|distribution` | Strategy overlay |
| `--config PATH` | Base or feature variant YAML |
| `--walk-forward` | Purged walk-forward validation |
| `--wf-splits`, `--purge-bars`, `--embargo-bars` | Walk-forward params |
| `--wandb` | Weights & Biases logging |

## Direct Dependencies

- Data, features, simulation, the selected learner backend, and evaluation through composition roots
- `config/` (training config)
- `evaluation/rollout/trained_policy_rollout.py` (model evaluation)
- `evaluation/metrics/performance.py` (performance metrics)
- `evaluation/reporting/run_artifact_writer.py` (run artifact saving)

## Consumers (Callers)

- `thesis-train` console entry point (`training/cli.py`)
- `scripts/research/benchmarks/compare_encoders.py` (encoder comparison)

## Tests

| Test File | Covers |
|-----------|--------|
| `tests/test_training/test_training_smoke.py` | Training smoke test |
| `tests/test_training/test_sac_smoke.py` | SAC training smoke |
| `tests/test_training/test_train_rl_decomposition.py` | Training decomposition |
| `tests/test_training/test_baseline_policies.py` | Baseline policies |
| `tests/test_training/test_best_checkpoint_callback.py` | Checkpoint callback |
| `tests/test_training/test_auxiliary_training.py` | Auxiliary training |
| `tests/test_training/test_seed_reproducibility.py` | Seed reproducibility |

## Training Pipeline

```
1. load_config() → cfg
2. run_pipeline(cfg) → bars
3. build_features(bars, cfg, train_mask) → features (fit scope enters the cache identity)
4. split_train_test(bars, features, cfg) → train/test
5. make_env(train_bars, train_feat, cfg) → env
6. build_agent(env, cfg, arch, algo) → model
7. model.learn(total_timesteps=...) → trained model
8. evaluate_model(model, test_bars, test_feat) → results
9. calculate_metrics(equity, trades) → metrics
10. save_run(run_dir, results, metrics) → artifacts
```

Walk-forward folds rebuild features through `build_walkforward_fold_features`:
causal bars through the fold validation end provide indicator context, while
`frozen_fold` normalization is fitted only on that fold's training indices.
Per-seed training manifests record exact train/test bar and feature hashes,
split boundaries, action schema, feature-cache identity, checkpoint digest,
runtime, and execution/metric protocols. These records are emitted by the
training path and are covered by helper tests; no full campaign artifact is
implied by the documentation.

Run directories come from `artifacts.layout.ArtifactLayout`. Training stores a
resolved `config.yaml` once through `training.artifacts.write_run_config_snapshot`,
attaches `train.log` through the public run-log API, and writes evaluation
summaries atomically while preserving their established report schema. Run
identity metadata, policy checkpoint code, and optimizer hooks remain owned by
their respective artifact, learning, and training packages.

## Config Overrides

## Change Map

| Task | Axis | Start file | Contract and focused test | Expected scope | Keep unchanged |
|---|---|---|---|---|---|
| Change run preparation | workflow stage | `training/runner/setup_runtime.py` | typed preparation stages; `tests/test_training/test_training_smoke.py` | one preparation stage and focused test | learner algorithm and evaluation metric meaning |
| Change seed fitting | learner workflow | `training/runner/seed_runtime.py` | `Learner.fit()` and typed seed stages; `tests/test_training/test_train_rl_decomposition.py` | one lifecycle phase and contract tests | campaign state and market-data source identity |

## Axis of Change

- **Axis:** run preparation, learner selection, fitting/evaluation sequencing, and persistence workflow.
- **Owner:** `training/` composes run stages; `learning/` fits; simulation owns environment construction.
- **Stable boundary:** `TrainingPreparation` groups configuration, data, and run-assets stages; seed workflow uses `Learner.fit()` and records its content-addressed fit result.
- **Expected edit radius:** one workflow stage and its focused tests; changing environment behavior belongs in `simulation/`.
- **Must not depend on:** storage identity semantics or scheduler implementation details.

```bash
uv run thesis-train train --mvp --seed=42
uv run thesis-train train --algo sac --arch gru
uv run thesis-train train --strategy po3_ifvg
uv run thesis-train train --config config/features/full_po3_mtf.yaml
uv run thesis-train train --walk-forward --wf-splits 5 --purge-bars 60
```
## Verified Source Paths

- `training/runner/training.py`
- `training/runner/seed_runtime.py`
- `training/runner/setup_runtime.py`
- `training/runner/stages.py`
- `training/runner/seed_stages.py`
- `training/runner/configuration_stage.py`
- `training/runner/data_stage.py`
- `training/runner/run_assets_stage.py`
- `training/runner/walk_forward_validation.py`
- `training/setup/learner.py`
