# Public contracts and compatibility surfaces

This page distinguishes the interfaces readers may rely on from internal
cross-package seams and historical compatibility hooks. It is intentionally
package-level; each contract's fields and semantics live in its dedicated
reference page.

## Stable domain contracts

| Contract area | Owner | What consumers rely on |
|---|---|---|
| Resolved settings | `configuration/` | Validated configuration values and deterministic configuration identity. |
| Data input | `market_data/` | Chronological bars/ticks, session/split meaning, and cache identity. |
| Feature matrix | `features/` | Named ordered causal features and fitted-statistics/cache identity. |
| Observation/action | `decisioning/` | Explicit schema versions, field order, and adapter-neutral decisions. |
| Account/order/position | `trading/` | Broker-neutral state and risk semantics consumed by simulation/live adapters. |
| Simulation transition | `simulation/contracts/` | Observation, reward, termination flags, and transition information. |
| Decision provider | `decisioning/contracts.py` | Schema-bound prediction without requiring a particular RL backend. |
| Artifact identity | `artifacts/` | Logical artifact kind/ID, manifest provenance, and shared storage behavior. |

## Package-level export inventory

The following are intentionally re-exported from package entry points or
dedicated public contract modules. They are the first place downstream code
should look; the local package guide describes their semantics. An export
does not remove the need to preserve its declared schema and version.

| Package | Primary public entry points | Classification |
|---|---|---|
| `configuration` | `load_config`, `apply_overrides`, `ConfigSchemaError`, `RepositoryPaths`, `config_sha256` | Stable configuration boundary |
| `artifacts` | `ArtifactId`, `ArtifactManifest`, `ArtifactLayout`, `artifact_id`, atomic writers | Stable identity/storage contracts |
| `market_data` | `load_bars`, `run_pipeline`, `TickBook`, `split_train_test`, `make_train_mask` | Stable prepared-input boundary |
| `features` | `build_features`, `InputSchema`, `InputView`, `feature_cache_path`, `feature_cache_content_hash` | Stable feature/schema boundary; cache version changes with feature semantics |
| `trading` | `AccountState`, `TradingPolicyConfig`, `resolve_trading_policy` | Stable broker-neutral domain boundary |
| `decisioning` | `ObservationSchema`, `ActionSchema`, `DecisionProvider`, `Decision`, action/observation builders | Stable versioned decision contract |
| `simulation` | `TradingEnv`, `SimulationTransition` | Stable environment and transition boundary |
| `learning` | `Learner`, `FitRequest`, `FitResult`, `build_learner` | Stable learner-composition boundary; algorithm internals remain backend-specific |
| `evaluation` | `evaluate_provider`, `run_episode`, `PerformanceMetrics`, `compute_metrics` | Stable rollout and reporting API; metric units are specified separately |
| `models` | No top-level model export; use the registered encoder factory and lightweight architecture IDs | Registry contract; individual architectures are checkpoint dependencies |
| `training` | Training CLI and runner composition interfaces | Workflow boundary; internal stages are implementation seams |
| `experiments` | Variant resolver, experiment-run CLI and run records | Configuration/workflow boundary; catalog labels are not runtime settings |
| `live` / `integrations` | Broker-neutral runtime and adapter interfaces | Stable boundary with vendor-specific implementations isolated in adapters |
| `compute` | Resource/device contracts and scheduler adapters | Shared operational contract; cluster inventory is not stable API |
| `orchestra` | `orchestra` command surface | Developer tooling, separate from trading/runtime API |

The precise Python exports are declared by each package's `__all__` or
contract module. Do not import underscore-prefixed helpers across domains.
Some packages intentionally have no broad root re-export; their documented
contract modules are the supported entry points.

Exact current observations and actions are in
[observation schemas](observation_schemas.md) and
[action schemas](action_schemas.md). Package-local `README.md` files explain
ownership and extension boundaries.

## Cross-package internal seams

Some modules are imported across package boundaries to compose workflows but
are not intended as broad end-user APIs. Their compatibility should be
reviewed when changing call signatures or data shapes. The executable
[architecture tests](../../tests/architecture/test_dependency_rules.py)
protect dependency direction and the explicitly public import surface.

## Compatibility surfaces

Serialized checkpoints, historical run configurations, and reports may
depend on import paths, schema names, category indices, feature ordering, or
artifact field names. The current setup-conditioned contract still includes
legacy `thesis*` identifiers. These are kept as wire-compatibility names until
an explicit translation is implemented and parity-tested.

Compatibility names are not canonical project terminology. New explanatory
documentation uses “trade setup”; persisted names must be quoted exactly when
describing historical artifacts.

## Experimental and research-specific interfaces

Optional encoders, reward modes, strategy overlays, and callback diagnostics
are not automatically stable APIs. The generated catalog shows configured
combinations; the source registry/factory and resolver determine selectable
combinations. Treat an experimental option as versioned whenever it affects
serialized policy input, output, or checkpoint construction.
