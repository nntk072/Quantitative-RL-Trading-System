# Product entry points contract

**Status:** draft
**Source of truth:** `pyproject.toml`; `market_data/cli.py`; `training/cli.py`; `evaluation/cli.py`; `experiments/cli.py`; `compute/cli.py`

## Distribution and commands

The distribution is `quantitative-rl-trading-system`. It declares Python
`>=3.12`. The console scripts and their dispatch surfaces are:

| Executable | Target | First-token commands |
|---|---|---|
| `qrl-data` | `market_data.cli:main` | `prepare`, `discover`, `prebuild-experiment-run-cache` |
| `qrl-train` | `training.cli:main` | `train`, `backtest`, `baselines`, `lstm-baseline`, `vae` |
| `qrl-evaluate` | `evaluation.cli:main` | `reanalyze` |
| `qrl-experiment` | `experiments.cli:main` | `run`, `status`, `summarize`, `checkpoint-map`, `recover-cache`, `rebuild-named-cache`, `variants`, `catalog` |
| `qrl-compute` | `compute.cli:main` | `capacity`, `resources`, `continuation`, `worker` |
| `orchestra` | `orchestra.cli:main` | See the [Orchestra guide](../../modules/orchestra.md) |

`qrl-train` selects training without a recognized first-token command and
passes the original argument list to the training parser in that case. The
other `qrl-*` scripts use a required command choice parsed by argparse.
See the [command reference](../../operations/RUNNING_COMMANDS.md) for discovery
and bounded verification.

## Settings and artifacts

- `config/base/default.yaml` owns canonical runtime defaults. Use the
  [configuration guide](../../config.md) for load and override behavior.
- CLI targets own workflow-specific argument validation and outputs. Follow
  the workflow's saved configuration and artifact identity for reproduction.
- MT5 scripts use separate root entry points and host requirements. Read the
  [live and paper trading contract](live-paper-metatrader.md).
