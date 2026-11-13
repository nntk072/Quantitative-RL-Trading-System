# Quantitative RL Trading System — Contributor and Agent Guide

This repository provides configurable research, simulation, training, evaluation,
and broker integration for reinforcement-learning trading policies on US100 and
US500. The production packages define behavior; research configuration selects
interventions. Do not duplicate behavior in experiment scripts.

## Project boundaries

| Package | Responsibility |
|---|---|
| `configuration/` | Load and validate effective configuration |
| `market_data/` | Ingestion, time alignment, caching, and data identity |
| `features/` | Causal indicators and structured market context |
| `decisioning/` | Observation, action, and policy-provider contracts |
| `trading/` | Broker-neutral account, orders, execution, and risk |
| `simulation/` | Environment transitions and event-driven backtests |
| `models/`, `learning/` | Model encoders, policy construction, and checkpoint adapters |
| `training/`, `evaluation/` | Training, deterministic replay, and numerical reporting |
| `experiments/` | Research catalog, experiment assemblies, execution, recovery, and results |
| `artifacts/` | Atomic persistence, hashes, and provenance |
| `compute/` | Hardware capabilities and scheduler adapters |
| `live/`, `integrations/` | Live strategy runtime and broker-specific adapters |
| `orchestra/` | Contributor orchestration and repository checks |

The generated package dependency graph is
[`docs/architecture/dependency_model.md`](docs/architecture/dependency_model.md).
Follow the architecture tests when a diagram and source disagree.

## Research extension contract

The research catalog is `config/research/experiments.yaml`. A scientific
experiment references reusable component implementations and optionally defines
named assemblies of variants. Shared execution writes source-bound manifests.
The consolidated research outputs are `results.json` (records),
`results.csv` (wide form), and `metrics.csv` (one metric per observation).
Do not create a new runner, report parser, or result schema for every experiment.

Start with [research workflow](docs/research/workflow.md) for the command
interface, [research methods](docs/research/README.md) for scientific
interpretation, and [historical evidence](docs/research/historical_evidence.md)
for the provenance of prior work. Historical material is not current evidence
merely because it remains in the repository. Run configurations and frozen
manifests, not report filenames, determine experimental identity.

## Scientific invariants

- Features must not incorporate future observations. Higher-timeframe features
  only become available after the corresponding bar closes.
- Normalization is fit on training data. Evaluation must not refit on holdouts.
- Purged walk-forward partitions must preserve purge, embargo, and disjoint
  evaluation periods.
- Session flags are eligibility masks, not permission to drop historical bars.
- `config/base/default.yaml` and validated overrides determine runtime settings.
- Feature-cache identities include a content hash, not just a manual version.
- Simulator and live broker risk contracts must remain compatible.
- Locked out-of-sample evidence is for final reporting, never tuning.
- Source, data, model, run, and artifact identities must be preserved across
  retries and resume; failures and unknown outcomes cannot be silently recast
  as successes.

Refer to `docs/research/validation_protocol.md` and the prospective research
protocol for the exact scientific constraints.

## Verification

Install the project dependencies with `uv sync --extra dev`. The canonical
checks are defined in `tools/check` and run in
[`.github/workflows/ci.yml`](.github/workflows/ci.yml).

```bash
./tools/check quality       # full-tree Ruff format, Ruff lint, and Mypy
./tools/check architecture  # package and repository contracts
./tools/check contracts     # cross-package behavioral contracts
./tools/check unit          # deterministic unit tests
./tools/check integration   # controlled integration tests
./tools/check docs          # generated docs, API, examples, and Sphinx
./tools/check full          # all required repository checks
```

Run focused tests while developing, but require the full-tree quality checks
and applicable CI jobs before calling a change complete. Do not bypass a failed
check by relaxing Ruff/Mypy scope or rewriting assertions around a defect.

## Agent extension environment

The agent-specific infrastructure in `.agents/`, `.claude/`, and `.codex/`
is intentionally retained for customers who want automated maintenance or new
research components. These are adapters to shared repository contracts, not
separate implementations of the trading system. Role names and delegation are
defined in `.agents/rules/agent-coordination.md`.

For implementation guidance see `.agents/rules/README.md`, CI and commit
rules under `.agents/rules/`, and package maps under `.agents/domain_maps/`.
Do not publish temporary agent task queues or scratch execution plans as
product documentation.

Compute scheduling is site-specific. Before using Triton/Slurm, read
`.agents/rules/triton-slurm.md` and `docs/operations/triton.md`, inspect
the active allocation, and respect the current user's resource authorization.
Do not cancel or replace unrelated allocations, launch scheduler work from
transient sessions, or infer available resources from static examples.

## Code and documentation style

Choose domain names that describe an observable behavior, contract, artifact,
or scientific comparison. Avoid chronological labels such as `part_1`,
`step_2`, or `version_3` unless an external protocol or persisted schema
requires them. Keep compatibility names where removing them would invalidate
historical checkpoints or records.

Comments and docstrings should explain constraints, units, numerical
assumptions, trade-offs, data lineage, or surprising behavior. Do not narrate
what a clear statement of code already says. Prefer one maintained reference
per concept, and link to it rather than copying entire explanations into
multiple READMEs. Update code, test expectations, configuration, generated
documentation, and public command examples together.
