# Commands Reference — Quantitative-RL-Trading-System

> Agent-oriented examples. The canonical command catalog is
> [RUNNING_COMMANDS](../docs/operations/RUNNING_COMMANDS.md); CI policy
> lives in [ci-verification](rules/ci-verification.md).

## Setup

```bash
uv sync                                    # install all deps
uv sync --extra dev                        # include dev tooling
```

On ARM64/GH200, these package-manager commands require an ARM64 `uv`. If the
login-home `uv` is x86-64, run the repository helper with
`QRL_UV=/path/to/aarch64/uv ./tools/setup-venv`; use `.venv-arm/bin` directly
for Ruff, Mypy, and pytest.

Use `QRL_UV` to select a native package-manager binary when the host default
does not match the current architecture.

## Agent commit/push gate — blocking

**Required** before commit/push. Full-tree format/lint/types (`mypy .` — never
path-scoped mypy); **scoped** pytest only (see `.agents/rules/ci-verification.md`).
Do not run `pytest tests/ -v` unless asked.

```bash
.venv-arm/bin/ruff format --check .        # ARM/GH200
.venv-arm/bin/ruff check .
.venv-arm/bin/mypy .
.venv-arm/bin/pytest <relevant test paths> -q
```

Merge CI runs the named `./tools/check` gates plus the required-job aggregator.
Hosted CI runs the named `./tools/check` gates plus the required-job aggregator.

## Data Pipeline

```bash
qrl-data prepare                            # raw CSV → parquet → features
qrl-data prepare --force                    # ignore cache, reprocess
```

## Training

```bash
uv run qrl-train train --mvp              # MVP smoke test (30 days)
uv run qrl-train train                    # full training run
uv run qrl-train train --algo sac --arch gru
uv run qrl-train train --strategy po3_ifvg  # Idea 1 overlay
uv run qrl-train train --config config/features/full_po3_mtf.yaml
uv run qrl-train train --walk-forward --wf-splits 5 --purge-bars 60
uv run qrl-train backtest                # random policy backtest
uv run qrl-train baselines                 # baseline strategies
uv run python scripts/research/benchmarks/compare_encoders.py                     # encoder comparison
```

## Evaluation

```bash
uv run qrl-evaluate reanalyze --run outputs/<run_dir>
uv run python scripts/research/analysis/evaluation/report_g3.py --runs-dir outputs
```

## Testing

```bash
./tools/check full                           # complete local merge gate
.venv-x86/bin/pytest -m "not slow"               # local shortcut
.venv-x86/bin/pytest -m unit                     # unit tests only
.venv-x86/bin/pytest -m integration              # integration tests only
.venv-x86/bin/pytest tests/unit/features/ -q     # feature tests only
.venv-x86/bin/pytest tests/unit/simulation/test_environment/ -q         # env tests only
./tools/check unit
```

## Linting & Type Checking

```bash
.venv-arm/bin/ruff check .                   # ARM/GH200; full tree
.venv-arm/bin/ruff format .                  # ARM/GH200; full tree
.venv-arm/bin/ruff check --fix .             # ARM/GH200; auto-fix
.venv-arm/bin/mypy .                         # ARM/GH200; full tree
```

Use the architecture-matched virtual environment on other nodes (for example
`.venv-x86/bin/pytest` on x86_64). Do not launch checks through a mismatched
`uv` executable on ARM.

## Docker

```bash
make docker-build
make docker-build-test
make docker-test
make docker-lint
make docker-pipeline
```

## Dependency Management

```bash
make lock
make lock-export
make lock-check
make deps-check
```

## Config Overrides

```bash
qrl-data prepare data.cache_dir=my_cache env.obs_window=30
uv run qrl-train train training.max_days=60
```
