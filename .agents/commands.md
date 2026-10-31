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
`QRL_UV=/path/to/aarch64/uv ./tools/setup-venv`; use `.venv/bin` directly
for Ruff, Mypy, and pytest.

`THESIS_UV` remains a deprecated fallback for existing node setups; new
commands and automation must use `QRL_UV`.

## Agent commit/push gate — blocking

**Required** before commit/push. Full-tree format/lint/types (`mypy .` — never
path-scoped mypy); **scoped** pytest only (see `.agents/rules/ci-verification.md`).
Do not run `pytest tests/ -v` unless asked.

```bash
.venv/bin/ruff format --check .            # ARM/GH200
.venv/bin/ruff check .
.venv/bin/mypy .
.venv/bin/pytest <relevant test paths> -q
```

Merge CI runs the named `./tools/check` gates plus the required-job aggregator.
Orchestra phase 9 runs their serial equivalent with `./tools/check full`.

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
uv run python scripts/research/thesis/evaluation/report_g3.py --runs-dir outputs
```

## Testing

```bash
./tools/check full                           # complete local merge gate
.venv/bin/pytest -m "not slow"               # local shortcut
.venv/bin/pytest -m unit                     # unit tests only
.venv/bin/pytest -m integration              # integration tests only
.venv/bin/pytest tests/unit/features/ -q     # feature tests only
.venv/bin/pytest tests/unit/simulation/test_environment/ -q         # env tests only
.venv/bin/pytest tests/unit/orchestra/ -q    # orchestra tests
./tools/check unit
```

## Linting & Type Checking

```bash
.venv/bin/ruff check .                       # ARM/GH200; full tree
.venv/bin/ruff format .                      # ARM/GH200; full tree
.venv/bin/ruff check --fix .                 # ARM/GH200; auto-fix
.venv/bin/mypy .                             # ARM/GH200; full tree
```

Use the architecture-matched virtual environment on other nodes (for example
`.venv-x86/bin/pytest` on x86_64). Do not launch checks through a mismatched
`uv` executable on ARM.

## Orchestra

```bash
orchestra doctor                             # Tier-0 health check
orchestra run "task description"             # full pipeline (verify runs ./tools/check full)
```

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
