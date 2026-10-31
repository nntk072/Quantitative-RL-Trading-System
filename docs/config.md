# Configuration

Configuration files are the human-authored inputs to runtime behavior. The
`configuration` package loads and validates them; domain packages define what
their keys mean. The resolved configuration recorded with a run is the
execution truth. A default file or catalog entry alone does not prove the
settings used by a checkpoint.

## Configuration sources

| Source | Purpose |
|---|---|
| `config/base/default.yaml` | Default sections for data, sessions, account, execution costs, risk, features, environment, learning algorithms, compute, and output. |
| `config/features/` | Feature-specific overlays. |
| `config/variants/` | Per-variant settings, including risk configuration. |
| `config/experiments.yaml` | Selectable variant matrix and comparison definitions. |
| `config/variant_catalog.yaml` | Classification metadata used to generate the reader-facing model catalog; it is not a runtime settings source. |
| `config/research/` and `config/experiment_runs/` | Named research/run inputs that preserve explicit experiment identity. |

The configuration schema rejects unknown or structurally incompatible
settings. Add a new key to its owning configuration section and consumer,
validate it, and add tests for defaults and overrides.

## Important setting groups

| Group | Typical settings |
|---|---|
| `data` | Source files, tick inputs, timezone, split dates, and cache locations. |
| `session` | Decision-window timezone and session boundaries. |
| `account`, `ftmo`, `risk` | Initial capital, hard account limits, sizing mode, and risk values. |
| `costs`, `execution` | Spread, quote source, tick execution, fill behavior, and latency. |
| `features` | Timeframes and optional technical/structure/context features. |
| `env` | Observation/action schema, windows, worker layout, reward, and environment behavior. |
| `encoder`, `agent`, `ppo`, `sac` | Model architecture, algorithm, and learning settings. |
| `quality_execution`, `quality_diagnostics` | Resource scaling and learning-quality diagnostics. |
| `training`, `evaluation`, `output` | Run budget, replay/report behavior, and artifact locations. |
| `live_risk_overrides` | Broker adapter risk settings, which require explicit parity review against simulation settings. |

Use the exact effective configuration saved beside the run when reporting
settings. Defaults may be overridden by a variant, experiment resolver, or
command-line option.

## Observation and action configuration

The base currently selects the discrete action interface and account-state-v1
observation schema unless a resolved variant changes those settings. Other
runs may enable continuous strategy overlays, setup-conditioned actions,
multiple-target coordinates, regime context, or multi-timeframe sequence
branches. Their exact dimensions and meanings are documented in
[observation schemas](reference/observation_schemas.md) and
[action schemas](reference/action_schemas.md).

A schema change can invalidate checkpoint compatibility even when tensor
width remains unchanged. Preserve schema metadata in run artifacts.

## Risk and execution configuration

Risk settings may be expressed as fixed dollar values, equity-relative values,
or a configured dollar band depending on the selected policy and variant.
Execution settings separately define costs and fill sources. Read the
resolved variant file and saved run configuration to determine the units and
effective thresholds. Do not infer them from a key name or a shared default.

Hard account guardrails are enforced by the account/environment path. Learned
risk penalties are an optimization signal and are not a replacement for the
hard checks. Live risk overrides are a separate adapter surface; parity is
not automatic.

## Feature and cache configuration

Feature overlays select which technical, session, structure, and entry-context
families are built. Timeframe lists and completion/alignment rules determine
what is available to a decision. Feature cache identity includes relevant
source data and resolved feature settings; a manual cache-version change by
itself is not sufficient to prove cache compatibility.

Build reusable caches before training where the workflow supports it. Record
the cache identity and input hashes with the run. See
[market data](../market_data/README.md), [features](../features/README.md), and
[reproducibility](concepts/reproducibility.md).

The implementation versions are useful invalidation inputs, but cache
compatibility also depends on source and resolved configuration hashes:

| Cache identity | Definition | Current version |
|---|---|---|
| `BAR_CACHE_VERSION` | `market_data/loading/market_data_ingestion.py` | `v4-semantic-manifest` |
| `FEATURE_CACHE_VERSION` | `features/pipeline/feature_cache_identity.py` | `v33-timeframe-entry-ideas` |
| `TICK_CACHE_VERSION` | `market_data/loading/ticks.py` | `v4-semantic-manifest` |

## Inspect a resolved run

1. Identify the configured variant and comparison definition.
2. Resolve the configuration using the repository's loader/experiment entry
   point.
3. Inspect the saved effective config and run manifest, including split,
   costs, risk, model, schemas, reward, seed, and training budget.
4. Confirm that the checkpoint metadata matches the observation and action
   schemas used during evaluation.

Installed commands are listed in the [CLI reference](reference/cli.md). The
[generated model catalog](model_variants.md) groups configured comparisons but
does not contain authoritative runtime settings.
