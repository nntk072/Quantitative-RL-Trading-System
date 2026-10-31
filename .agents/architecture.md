# Architecture Map — Quantitative-RL-Trading-System

> Agent navigation map. The authoritative narrative is [docs/architecture.md](../docs/architecture.md).

The detailed path ownership ledger is maintained in
[`architecture/repository_file_ownership_inventory.csv`](architecture/repository_file_ownership_inventory.csv).

## Dependency Graph

```text
configuration/ → market_data/ → features/ → simulation/
                                             ↑       ↓
                               trading/ ──────┘  learning/ ← models/
                                      decisioning/ ─┘
                                                  ↓
                                         training/ → evaluation/
                                              ↑          ↓
                                      experiments/   artifacts/
                                           ↑
                                        compute/

live/ → integrations/mt5/
orchestra/ → repository/CI orchestration
```

## Root Package Ownership

| Package | Owns |
|---|---|
| `configuration/` | config loading, overrides, repository paths |
| `market_data/` | ingestion, transforms, splits, data caches |
| `features/` | technical/context/PO3 features and feature-cache identity |
| `trading/` | account, execution, orders, risk, strategies, baselines |
| `simulation/` | Gym environment contracts/runtime and event-driven backtest |
| `decisioning/` | versioned observation/action schemas and backend-neutral inference contract |
| `models/` | reusable encoders, encoder registry, and auxiliary neural components |
| `learning/` | PPO/SAC fitting backends, SB3 policy adapters, rollout adapters, and checkpoint loading |
| `training/` | setup, callbacks, runners, training artifacts |
| `evaluation/` | rollout, metrics, reanalysis, reporting, plotting |
| `experiments/` | variant/experiment_run orchestration and provenance |
| `artifacts/` | shared artifact identity, manifests, storage, and lifecycle mechanics |
| `live/` | broker-neutral live runtime |
| `integrations/mt5/` | Lazily loaded MetaTrader-specific adapters and domain integration |
| `compute/` | cluster/environment/Slurm implementation |
| `orchestra/` | engineering workflow orchestration |

## Stable Commands

```text
orchestra
thesis-data
thesis-train
thesis-evaluate
thesis-experiment-run
thesis-compute
```

Use package APIs or these command surfaces. `scripts/` includes command entry points plus thesis-specific evidence builders and audits; some existing scripts hold substantial logic and are not general-purpose APIs. Put new shared behavior in its owning package, and keep new CLI wrappers thin.

## Cache Versioning

| Constant | File | Current value |
|---|---|---|
| `BAR_CACHE_VERSION` | `market_data/loading/market_data_ingestion.py` | `v4-semantic-manifest` |
| `TICK_CACHE_VERSION` | `market_data/loading/ticks.py` | `v4-semantic-manifest` |
| `FEATURE_CACHE_VERSION` | `features/pipeline/feature_cache_identity.py` | `v33-timeframe-entry-ideas` |

Cache identity must remain causal and include fit scope/configuration inputs that affect generated content.

## Core Scientific Invariants

1. Train-only normalization and causal feature construction.
2. Locked OOS separation plus purged/embargoed walk-forward where configured.
3. Training, evaluation, and backtest execution/risk semantics remain aligned.
4. Checkpoint, seed, dataset, config, cache, and source provenance remain reproducible.
5. Live broker integrations stay outside simulation/training domain ownership.
