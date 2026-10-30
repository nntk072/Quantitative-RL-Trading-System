# Repository Architecture Refactor Plan

## Goal

The repository itself is the architecture boundary. The target is a set of first-class top-level Python packages with clear responsibilities, explicit public APIs, and predictable dependency direction.

The refactor is not complete when large files are merely split into smaller files. It is complete when a developer can look at the repository root, choose the correct package, open that package's `__init__.py`, and understand:

- what the package owns;
- which symbols are safe to import;
- which neighboring package owns the next concern;
- which dependency directions are allowed;
- where tests for that package live.

All importable code packages and subpackages must contain `__init__.py`. Asset, evidence, generated-output, and command-only directories are not Python packages and should not receive placeholder `__init__.py` files.

The sequence is:

**repository inventory → package boundaries → public contracts → characterization tests → incremental migration → compatibility verification → removal of legacy layout**

Behavioral equivalence is the primary constraint. Architecture work must not silently alter feature causality, execution, risk, rewards, training, checkpoint compatibility, evaluation results, or experiment run reproducibility.

## Repository categories

The root should clearly separate six kinds of content.

### Domain and application packages

These are importable Python packages with `__init__.py` and stable public APIs:

- `configuration/`
- `artifacts/`
- `market_data/`
- `features/`
- `trading/`
- `simulation/`
- `models/`
- `training/`
- `evaluation/`
- `experiments/`
- `live/`
- `integrations/`
- `compute/`
- `orchestra/`

### Configuration assets

`config/` contains YAML, CSV schedules, experiment declarations, and experiment run configuration. It remains an asset directory rather than a Python package.

Python code that loads, validates, merges, hashes, and resolves shared configuration belongs to the top-level `configuration/` package. Domain packages own only domain-specific interpretation/validation layered on the resolved configuration.

### Data and generated artifacts

- `data/` stores raw and prepared market data.
- `cache/` stores disposable caches.
- `outputs/` stores run outputs and generated evidence.
- `logs/` stores runtime logs.
- `baseline/` stores baseline evidence and audit records.

These are not Python packages.

### Executable wrappers

`scripts/` contains command wrappers only. Reusable Python logic must live in one of the top-level packages.

A script should normally do only this:

1. parse command-line arguments;
2. call a package API;
3. convert failures to exit codes;
4. print or persist the result.

Tests and production packages should not import reusable logic from `scripts/`.

### Engineering and CI tooling

- `tools/` contains developer command wrappers.
- `ci-scripts/` contains CI entry scripts.
- `.github/` contains hosted CI configuration.
- `.agents/` contains agent guidance and architecture/domain maps.

These are repository tooling, not trading-domain packages.

### Documentation and tests

- `docs/` documents architecture, research protocol, operations, and evidence.
- `tests/` mirrors the top-level package architecture.
- package-level import and dependency tests live under `tests/architecture/`.

## Repository-root ownership matrix

The repository architecture includes code, declarative inputs, immutable evidence, disposable generated state, human documentation, and execution wrappers. A directory being non-importable does not make it architecture-free.

| Root area              | Architectural role                                                         | Owning logic                                                          | Write policy                                                                 | Source-of-truth rule                                        |
| ---------------------- | -------------------------------------------------------------------------- | --------------------------------------------------------------------- | ---------------------------------------------------------------------------- | ----------------------------------------------------------- |
| `config/`            | Declarative experiment/runtime inputs                                      | `configuration` plus domain validators                              | Human-authored or generated only through explicit config-generation commands | Versioned config plus resolved snapshot determine a run     |
| `data/`              | Market-data assets and curated partitions                                  | `market_data`                                                       | Data ingestion/preparation APIs only; scripts wrap them                      | Raw source identity and dataset manifest are authoritative  |
| `cache/`             | Disposable acceleration artifacts                                          | Owning producer package plus generic artifact primitives              | Atomic, identity-keyed, safe to rebuild                                      | Never the only copy of research evidence                    |
| `outputs/`           | Immutable run, experiment run, evaluation, CI, and research artifacts            | `artifacts` plus the package that defines each artifact's semantics | Structured run/artifact writers                                              | Manifest and provenance identify every result               |
| `logs/`              | Local/global runtime diagnostics that are not already colocated with a run | Runtime owner; shared conventions from `artifacts`                  | Append/rotate; no domain state stored only in logs                           | Logs support diagnosis, not scientific truth                |
| `baseline/`          | Curated, reviewed reference evidence                                       | Evaluation/verification code plus promotion workflow                  | Promote from validated outputs; do not write casually during runs            | Baseline manifest points to source artifacts and validation |
| `scripts/`           | Human/Slurm command entry points                                           | Owning top-level package                                              | Thin wrappers only                                                           | No reusable domain logic                                    |
| `tests/`             | Verification architecture                                                  | Mirrors package and lifecycle ownership                               | Test fixtures/results use isolated temp paths                                | Tests specify contracts and invariants                      |
| `docs/`              | Human architecture/research/operations knowledge                           | Relevant package/process owner                                        | Human-authored docs plus explicitly generated reports                        | Docs cite artifact IDs/manifests for numerical claims       |
| `tools/`             | Developer workstation helpers                                              | Engineering/toolchain layer                                           | Thin wrappers around standard tools/package APIs                             | No experiment or trading semantics                          |
| `ci-scripts/`        | CI command adapters                                                        | Engineering/toolchain layer                                           | Thin, deterministic wrappers                                                 | CI behavior remains inspectable from workflow + script      |
| `.github/workflows/` | Hosted CI orchestration                                                    | Engineering/toolchain layer                                           | Declarative workflow definitions                                             | Calls `ci-scripts/` or standard package commands          |

This ownership matrix is part of the target architecture. Refactoring is incomplete if Python packages are clean while generated data, reports, caches, and commands still write arbitrary files with undocumented identities.

## Configuration architecture

`config/` is a declarative asset tree. Parsing, merging, defaults, schema validation, compatibility rules, override handling, and resolved-config hashing belong to a new low-level `configuration/` package.

Target asset organization:

```text
config/
├── base/                 # canonical runtime defaults and shared fragments
├── features/             # feature-family profiles
├── policies/             # trading-policy profiles when useful
├── experiments/          # experiment/variant declarations
├── experiment_runs/            # concrete experiment run specifications
├── data/                 # symbols, sessions, source/partition declarations
├── models/               # model/architecture presets if they remain declarative
└── schemas/              # optional machine-readable config schemas
```

Migration should preserve existing config paths until callers move. Existing root YAML files may remain compatibility assets during the transition.

`configuration/` owns:

- deterministic merge order;
- unknown-key rejection and typo safety;
- explicit schema/version identifiers;
- path resolution relative to repository/runtime roots;
- environment/CLI override normalization;
- canonical serialization for hashing;
- resolved configuration snapshots stored with every run;
- compatibility migration when a released config schema changes and a concrete
  migration path is required. Do not keep a placeholder migration function that
  rejects every version transition.

Training, evaluation, experiments, live runtime, and compute code consume a resolved configuration object. They must not each implement their own YAML merge semantics.

A resolved run configuration is immutable after run creation. Reanalysis loads the saved snapshot first and may compare it with current source configuration, but it must never silently reinterpret a historical run using current defaults.

## Data architecture

`data/` is storage, while `market_data/` owns all logic that creates, validates, transforms, partitions, and identifies datasets.

The current tree contains full-period exports plus `data/training/`, `data/testing/`, examples, inferred session data, and derived arrays. The target separates lifecycle state explicitly:

```text
data/
├── raw/                  # source exports copied/linked without semantic transformation
├── curated/              # cleaned/aligned canonical market datasets
├── partitions/           # immutable train/validation/test or walk-forward views/manifests
├── reference/            # schedules/levels/reference assets derived from approved sources
├── examples/             # tiny tracked developer fixtures
└── manifests/            # dataset identities, hashes, ranges, source lineage, schema versions
```

Large physical files may stay in their existing locations during migration; the important first step is to give them a typed dataset identity and a manifest rather than moving terabytes for cosmetic reasons.

Every dataset-producing operation records at least:

- dataset ID and schema version;
- source file identities/hashes;
- symbol and timeframe;
- timezone/session semantics;
- inclusive/exclusive timestamp bounds;
- cleaning/resampling/alignment version;
- row count and key quality statistics;
- partition definition and leakage-sensitive boundaries;
- producer code/source revision when relevant.

Training and evaluation should accept a dataset identity or resolved dataset object rather than reconstructing meaning from a filename.

## Cache architecture

`cache/` is disposable and reproducible. It may improve runtime but must never become hidden scientific state.

Target namespaces should follow the producer and artifact type, for example:

```text
cache/
├── market_data/          # bar/tick normalization and lookup caches
├── features/             # feature matrices and higher-timeframe auxiliaries
├── simulation/           # shared environment bundles / memory-mapped arrays
├── evaluation/           # safe-to-recompute derived evaluation intermediates
└── manifests/            # optional cache inventory/index, never required for correctness
```

A cache key must be derived from all semantic inputs that can change its contents: source-data identity, relevant resolved config, schema/version, feature code/version or explicit algorithm version, partition identity, and any execution/session semantics that affect values.

Cache writers must use temporary files/directories followed by atomic promotion where practical. Partial caches are invalid. A cache entry must be validated before reuse. A stale or missing cache causes regeneration, not behavior change.

Feature caches, tick caches, and shared environment bundles keep their domain-specific identity logic in `features`, `market_data`, and `simulation`; generic path/manifest/atomic-write primitives may come from `artifacts`.

## Generated-artifact architecture

Generation logic is part of the architecture. A generated file is not adequately designed merely because its destination directory is documented.

Introduce a low-level `artifacts/` package for cross-cutting artifact mechanics:

```text
artifacts/
├── __init__.py
├── identity.py           # ArtifactId, content/source identity helpers
├── layout.py             # canonical run/experiment_run/evaluation path layouts
├── manifest.py           # common provenance envelope and schema/version fields
├── atomic.py             # atomic JSON/text/binary/directory promotion helpers
├── retention.py          # disposable/retained/promotable classifications
└── promotion.py          # validated output -> curated baseline/evidence transitions
```

Exact filenames may adjust, but these responsibilities need one owner.

`artifacts` owns storage/provenance mechanics, not domain content. For example, `training.artifacts` defines what a training manifest means, `evaluation.reporting` defines evaluation tables, and `experiments.runs` defines experiment run state. They call common artifact primitives instead of independently inventing directories and JSON-write patterns.

Domain packages own payload schemas and their validation. There is no global
mutable artifact-kind registry: the previous registry had no consumers and
would make validation depend on import-time registration order. Add a domain
validator at the artifact reader/writer boundary when an actual artifact kind
needs one.

Every generated artifact type must define:

1. producer package/API;
2. consumer package/API;
3. artifact kind and schema version;
4. semantic identity inputs;
5. canonical location/layout;
6. overwrite/immutability policy;
7. atomicity/completion marker policy;
8. validation before consumption;
9. retention class: disposable, run-retained, evidence-retained, or baseline-promotable;
10. provenance links to parent artifacts;
11. regeneration command/API;
12. compatibility policy for older artifact versions.

Direct ad-hoc `mkdir` + `write_text`/CSV/JSON/Parquet output remains acceptable only inside the owning writer implementation. Callers should request an artifact from an API rather than assemble path conventions themselves.

### Artifact lifecycle

Use an explicit lifecycle instead of treating generated files as anonymous filesystem state:

```text
DECLARED INPUT
    ↓ resolve + validate
RESOLVED CONFIG / DATASET IDENTITY
    ↓ generate
STAGING ARTIFACT
    ↓ validate + atomically promote
COMPLETE IMMUTABLE ARTIFACT
    ↓ consume / derive
DERIVED ARTIFACT
    ↓ verification gate
CURATED EVIDENCE / BASELINE
    ↓ cite
REPORT / THESIS / DEFENSE OUTPUT
```

Failed or interrupted generation leaves a staging/incomplete state that consumers reject. Completion must be represented structurally by an atomic promotion or explicit completion manifest, not inferred from “file exists”.

### Provenance graph

Artifacts form a directed provenance graph. A model checkpoint should identify the resolved config, dataset/partition, feature schema/cache identity, action/observation schema, seed, source revision, and parent checkpoint if resumed. Evaluation artifacts identify the checkpoint and evaluation dataset. Experiment run summaries identify their child runs. Baselines identify the validated source artifacts from which they were promoted.

This graph must be traversable without reading free-form logs.

## Outputs architecture

`outputs/` is the materialized artifact store for experiment execution. It should be organized by artifact semantics rather than by whichever script happened to create a folder.

Target logical namespaces:

```text
outputs/
├── runs/                 # individual training runs
├── experiment_runs/            # experiment run controllers, child-run refs, scheduler evidence
├── evaluation/           # checkpoint reanalysis and OOS evaluation packs
├── research/             # research audits and one-off validated analyses
├── ci/                   # CI/gate evidence intended to be retained locally
├── reports/              # generated report/figure packs
└── agent/                # agent execution state only when intentionally retained
```

Existing names such as experiment run, CI-gate, data-refresh, thesis-validation, and agent-state trees can migrate gradually. Do not rename active experiment run paths in place if that would break reproducibility.

A canonical training run layout should include a top-level manifest and typed children, for example:

```text
outputs/runs/<run-id>/
├── manifest.json
├── config/
│   ├── resolved.yaml
│   └── identity.json
├── model/
├── training/
├── evaluation/
├── diagnostics/
├── logs/
└── COMPLETE
```

Experiment run and evaluation layouts should likewise have explicit manifests instead of relying on filename conventions.

Run IDs are immutable identities. A resumed run either records lineage to its parent checkpoint/run or uses a clearly defined continuation identity; it must not silently overwrite the provenance of the original run.

## Logs architecture

Logs have two scopes:

- run-scoped logs belong inside the corresponding run/experiment_run/evaluation artifact tree;
- root `logs/` is reserved for local/global runtime services that have no containing artifact, such as local live/paper runtime logging.

Structured event/state needed for metrics or reproducibility belongs in typed JSON/CSV/Parquet artifacts, not only in text logs. Text logs may be rotated or archived without changing scientific results.

All logging setup should accept a run/artifact context carrying run ID, experiment run ID, seed, worker/job identity, and relevant source/config identity. This avoids detached log files whose experiment cannot be reconstructed.

## Baseline architecture

`baseline/` is curated evidence, not another output directory.

Baseline creation is a promotion workflow:

```text
validated output artifact
→ comparison/acceptance gate
→ baseline manifest
→ curated baseline files
```

A baseline manifest records source artifact IDs/paths, source revision, config/data/schema identities, validation commands, acceptance result, creation time, and the specific metrics/traces being frozen. The current `artifacts.promote_to_baseline` primitive requires an explicit validator and accepted validation record, validates a staged copy, and publishes a directory containing `payload/` plus `manifest.json` atomically; do not promote research evidence until the caller supplies complete lineage and acceptance provenance.

Normal training/evaluation runs never write directly into `baseline/`. A dedicated promotion API/command performs the copy/link plus manifest creation after validation. Updating a baseline is an explicit research decision visible in review.

## Scripts architecture

The existing script tree is large enough to require its own architecture. Script categories should map to the packages they invoke rather than becoming alternate implementations.

Target command groups:

```text
scripts/
├── data/                 # ingestion/preparation/cache commands -> market_data/features
├── train/                # training commands -> training
├── eval/                 # evaluation/report commands -> evaluation
├── experiments/          # experiment_run/variant commands -> experiments
├── compute/              # Slurm/allocation/runtime wrappers -> compute
├── research/             # reproducible analysis entry points -> package APIs
├── maintenance/          # migrations/cleanup/repair commands
└── tests/                # convenience launchers only; canonical tests live in tests/
```

Shell scripts remain appropriate for Slurm allocation, environment activation, and process supervision, but business logic, experiment run state transitions, data rules, and artifact schemas move into Python packages.

A script may choose arguments and destinations; it may not define a second version of the underlying algorithm.

## Tests architecture

Tests mirror both code ownership and lifecycle contracts.

In addition to package-oriented tests, add:

```text
tests/
├── architecture/         # imports, dependency rules, root ownership rules
├── contracts/            # config/data/artifact schema compatibility
├── fixtures/             # tiny deterministic tracked data/config/artifact fixtures
├── lifecycle/            # cache invalidation, atomic completion, provenance, promotion
└── ...                   # package-mirrored tests already defined below
```

Tests that generate files use `tmp_path` or an isolated test artifact root. They must not mutate repository `data/`, `cache/`, `outputs/`, `logs/`, or `baseline/` during ordinary CI.

Golden artifacts are intentionally small, versioned fixtures with an owning test and schema version. Large historical outputs are not test fixtures.

## Documentation architecture

`docs/` should distinguish stable architecture, decisions, operating procedures, research protocol, training guidance, and thesis evidence.

Target logical groups:

```text
docs/
├── architecture/         # package + repository lifecycle architecture
├── decisions/            # ADR-style durable design decisions
├── operations/           # Triton, deployment, environment, recovery runbooks
├── training/             # training/evaluation/experiment_run procedures
├── research/             # experiment protocol, reproducibility, methodology
├── thesis/               # thesis-specific evidence interpretation and handoffs
└── generated/            # optional reproducible generated docs, if truly needed
```

Generated numerical reports should normally live in `outputs/` and be linked/cited from docs. If a generated document is committed under `docs/generated/`, its generator, source artifact IDs, and regeneration command must be recorded.

Documentation may describe an artifact; it must not become the only location of machine-readable evidence.

## Tools and CI architecture

`tools/` is the canonical developer/CI engineering command surface. It owns repository checks such as `check`, `test`, `build`, `clean`, bootstrap helpers, and graph/dependency inspection. These wrappers may compose standard tools and package/test commands but must not encode experiment semantics.

`.github/workflows/` defines hosted-runner scheduling, permissions, caching, concurrency, timeouts, and artifact upload. It invokes the same named gates available locally rather than redefining Ruff, mypy, pytest, architecture checks, or build semantics inline.

`ci-scripts/` is transitional. The current directory duplicates commands already expressible through `tools/` and GitHub Actions. During Phase 9, migrate all generic wrappers to `tools/check` or direct package commands. Keep a CI-only script only when it performs irreducibly platform-specific glue; if no such script remains, delete `ci-scripts/` entirely.

Target dependency direction:

```text
.github/workflows ───────┐
local developer shell ──┼──> tools/check + stable console commands
Docker/nightly runner ──┘                 │
                                          ├──> tests / build tools
                                          └──> public package APIs

optional platform-only ci-scripts ───────> tools/check
```

Production packages must never import `scripts/`, `tools/`, workflow code, or CI adapters. CI-generated evidence uses the same artifact conventions as local gates where retention matters; ephemeral runner logs may remain CI-platform output.

## Command and CI execution architecture

Scripts, console commands, Docker, Slurm, developer tools, and GitHub Actions are one execution architecture. They may select arguments, resources, environment variables, scheduling, and output locations, but they must converge on the same package APIs. None of these outer layers may contain a second implementation of feature logic, trading rules, risk equations, training setup, evaluation semantics, experiment run state transitions, provenance rules, or artifact schemas.

Preferred direction:

    domain/application packages
        -> stable public APIs and package-owned CLI entry functions
        -> stable console commands
        -> scripts and developer-tool wrappers
        -> Docker / Slurm / GitHub Actions orchestration

### Stable commands and script lifecycle

Frequently used commands such as training, evaluation/reanalysis, experiment run execution/status, and data preparation should have stable console entry points backed by package-owned CLI functions. Internal module moves must not force users or Slurm launchers to learn new deep module paths.

Keep scripts for research-specific, maintenance, and platform-launch work when a permanent console command adds no value.

Target script groups:

    scripts/
      data/
      train/
      eval/
      experiments/
      compute/slurm/
      compute/local/
      research/
      maintenance/
      tests/

The current matrix and Triton groups should be migrated by responsibility. Experiment run behavior belongs to experiments. Slurm/resource behavior belongs to compute. Shell files that remain should be thin platform wrappers.

Every migrated script is classified as stable wrapper, temporary compatibility wrapper, frozen research record, or obsolete. Before removing or renaming one, search experiment run specifications, Docker Compose, workflows, tests, docs, run manifests, and saved launch commands.

A Python script is too large for the scripts layer when it owns reusable state machines, dataclasses, checkpoint selection, result aggregation, hashing/provenance, dataset rules, artifact schemas, or substantial reusable helpers. A shell script is too large when it owns scientific calculations, JSON state mutation, retry-state decisions, experiment run reconciliation, or long business-logic branches.

### Current CI audit

The current CI has useful coverage, but its command architecture is duplicated:

- GitHub workflows, ci-scripts, tools, Make targets, Docker Compose, and shell pipelines encode overlapping lint/type/test/build commands.
- Most ci-scripts are not called by the GitHub workflows, so local and hosted definitions can drift.
- the ordinary CI workflow executes the full test suite through several environment paths, including uv/venv and Docker, with substantial duplicate coverage;
- local tools/check and hosted type checking currently select different source scopes;
- documentation checks cover only a small root-level subset, and one formatting path can silently skip when its tool is absent;
- some Docker helper checks return success when Docker is unavailable, which is fine for optional convenience but invalid for a required gate;
- Docker Compose still contains legacy deep-module commands and historical script paths that must migrate with the package architecture;
- ordinary test containers mount repository data/cache/output/log roots even though normal CI should use isolated temporary roots;
- unit, integration, and slow markers are not yet a complete scheduling contract;
- GitHub CPU runners cannot validate Triton/GH200/Slurm behavior;
- release/image publication should remain only if a real runtime or reproducibility consumer needs it.

These are explicit refactor targets.

### One canonical gate vocabulary

Define each validation property once and invoke it everywhere through the same named gate. Recommended names:

    format
    lint
    types
    architecture
    contracts
    unit
    integration
    parity
    build
    docker-smoke
    training-smoke
    gpu
    triton
    full

The preferred local surface is tools/check with a gate argument. GitHub Actions should invoke the same gate semantics. ci-scripts should contain only hosted-runner/platform glue that cannot reasonably live in tools. If no such glue remains, remove ci-scripts rather than preserving duplicate wrappers.

A required gate may not silently pass because its required tool or capability is missing.

### Validation tiers

Tier A: fast developer and pull-request correctness.

- dependency/lock consistency;
- Ruff formatting and lint;
- mypy over every first-class package;
- architecture/public-import/dependency rules;
- config, artifact, lifecycle, and repository-hygiene contracts;
- fast unit tests;
- wheel/package build and import smoke.

Tier A must not depend on external market data, Docker, GPUs, or Triton.

Tier B: deterministic CPU integration and parity.

- integration tests using controlled tracked fixtures;
- environment/backtest execution parity;
- action/observation/checkpoint compatibility;
- data/feature causality and partition contracts practical on CPU;
- historical config/artifact read compatibility;
- selected command/script smoke tests in isolated temporary roots.

Do not run the identical full test collection repeatedly unless each execution validates a distinct environment contract.

Tier C: scheduled exhaustive validation.

- slow tests;
- larger deterministic integration/backtest suites;
- practical seed reproducibility checks;
- larger reanalysis/fixture checks;
- Docker build/runtime smoke if Docker remains supported.

Nightly is not a dumping ground for flaky tests.

Tier D: Triton/GPU/research-infrastructure validation.

Use Triton/GH200 when changes touch GPU execution, vectorized environments, shared bundles, training orchestration, checkpoint serialization, Slurm/experiment_run infrastructure, or resource-sensitive behavior. Include the applicable current-source provenance check, GPU import/device smoke, direct/bundle equivalence, short PPO/SAC/recurrent smoke training, checkpoint save/load/reanalysis, worker/resource geometry, experiment run dry-run/recovery, and one short training-to-evaluation-to-manifest path.

Tier D results are structured gate artifacts. Long jobs use the existing external watcher rather than repeated agent polling.

### Test scheduling contract

Normalize markers so package location describes ownership and markers describe execution requirements:

- unit: deterministic, isolated, fast;
- integration: crosses package or I/O boundaries using controlled fixtures;
- slow: expensive but platform-neutral;
- gpu: requires CUDA-capable execution;
- triton: requires Triton/Slurm/filesystem assumptions;
- research: validates a larger research/evidence protocol.

A test may have more than one marker. Unmarked tests should become a deliberate small exception rather than an accidental majority.

### Local/hosted parity and CI isolation

A developer must be able to reproduce a hosted failure with the same repository command, for example:

    ./tools/check fast
    ./tools/check unit
    ./tools/check integration
    ./tools/check full

GitHub workflow YAML should mainly provide runner setup, caching, permissions, concurrency, timeouts, and artifact upload. It should not independently redefine test/lint/type semantics.

Every ordinary CI job receives isolated temporary data, cache, output, log, and artifact roots. CI must not consume whatever happens to exist in a developer or research checkout. Tests needing data use small tracked fixtures or explicitly provisioned versioned test datasets.

### Workflow responsibilities

ci.yml owns required pull-request gates: nine semantic validation jobs, three independently visible assurance gates (`security-deps`, `security-secrets`, and `graph-quality`), and one `ci-success` aggregator. Keep the assurance gates separate until Phase 9 proves that combining them preserves failure visibility, required-job protection, and equivalent coverage.

nightly.yml owns Tier C.

GPU/Triton validation is a documented Tier D command or dispatch flow and must not be represented as validated by a CPU runner.

release.yml remains only if container/package publication is an intentional supported deliverable. For this research repository, if there is no deployment/reproducibility consumer, replace registry publication with build/install/reproducibility checks.

Use least-privilege workflow permissions, concurrency cancellation for superseded pull-request commits, explicit timeouts, lockfile-keyed dependency caches, and BuildKit/GitHub cache primitives for Docker rather than caching the Docker daemon directory as an ordinary file tree.

### Docker, Make, tools, and ci-scripts

Docker is an execution environment, not a second application architecture. Compose services invoke stable package/console commands. Separate runtime/dev/test/GPU images only when each validates a real supported property.

The Makefile may own dependency export/lock maintenance and concise aliases. It must not become another independent quality-gate implementation.

tools owns human-friendly repository engineering commands and the canonical gate surface.

ci-scripts contains only hosted-platform glue. Wrappers that merely repeat raw Ruff, mypy, or pytest commands should delegate to the canonical gate or be removed.

### CI acceptance criteria

CI architecture is complete when:

1. each required gate has one canonical definition and owner;
2. local and hosted executions share gate semantics;
3. redundant full-suite executions are removed unless they test distinct environment contracts;
4. every first-class root package is formatted, linted, typed, packaged, and import-tested as applicable;
5. architecture/config/artifact/lifecycle rules are continuously enforced;
6. CPU CI uses isolated data/artifact roots;
7. Triton/GPU behavior has an explicit Tier D gate;
8. Docker and release automation contain only current supported commands;
9. no required gate silently skips due to missing capability;
10. the final architecture migration passes Tier A, Tier B, applicable Tier D smoke validation, and the full repository gate before the single final commit.

## Repository state and retention policy

Every root area needs an explicit version-control/retention policy:

- source packages, config assets, scripts, tests, docs, tools, CI definitions, and curated baseline manifests are version controlled;
- raw/large data is normally external or ignored, with tracked manifests/examples where useful;
- caches are ignored and disposable;
- normal outputs/logs are ignored, with selected evidence promoted to a curated tracked location only through an explicit process;
- virtual environments and tool caches are ignored;
- generated files committed to source control require a declared generator and regeneration check.

The `.gitignore` rules are therefore part of repository architecture and should be tested/reviewed alongside directory ownership. They must not accidentally ignore importable source packages or tracked examples.

## Shared-code and duplication architecture

The repository should deliberately reuse common behavior, but it should not create a catch-all `utils/`, `common.py`, or `helpers.py` dumping ground. Shared functions need semantic ownership just like larger modules.

Use this promotion ladder:

```text
private helper in one module
        ↓ reused by sibling modules
subpackage-owned helper/module
        ↓ reused across subpackages in one domain
package public API
        ↓ truly domain-neutral and reused across several top-level packages
small foundational package with a precise responsibility
```

Do not promote a helper only because two functions have the same name or similar-looking code. Consolidation is correct only when inputs, outputs, error behavior, determinism, units, numerical tolerances, side effects, and compatibility requirements are the same.

### Shared primitive ownership

The current repository already contains several repeated helper patterns. Their target ownership should be explicit:

| Repeated concern                                    | Canonical owner                                                                                    | Examples of consumers                                    |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| file/content SHA-256, artifact fingerprints         | `artifacts.identity`                                                                             | experiment runs, thesis evidence, evaluation manifests, audits |
| atomic JSON/text/binary writes and safe replacement | `artifacts.atomic`                                                                               | training, evaluation, experiments, research generators   |
| artifact layout/path construction                   | `artifacts.layout`                                                                               | runs, experiment runs, evaluation packs, CI evidence           |
| canonical manifest/provenance envelope              | `artifacts.manifest`                                                                             | training/evaluation/experiments/baseline promotion       |
| canonical config serialization/hash                 | `configuration.hashing`                                                                          | training, experiment runs, evaluation reanalysis               |
| repository/config path resolution                   | `configuration.paths` when config-related; owning package otherwise                              | CLI/config/data resolution                               |
| CUDA/device and host-resource discovery             | `compute.environment`                                                                            | training setup, benchmarks, Slurm execution              |
| position sizing and risk capacity                   | `trading.risk`                                                                                   | simulation, evaluation, live/MT5 adapters                |
| action/observation schema conversion                | `simulation.contracts`                                                                           | models, training, evaluation                             |
| feature schema/cache identity                       | `features.pipeline`                                                                              | training, evaluation, cache builders                     |
| dataset hashing/partition identity                  | `market_data`                                                                                    | training, evaluation, feature cache identity             |
| plot/report semantic transforms                     | `evaluation.plotting.transforms` / `evaluation.reporting`                                      | static and interactive renderers                         |
| terminal/dashboard formatting                       | keep close to reporting/dashboard owners unless several unrelated packages need the exact renderer | training dashboard, evaluation diagnostics               |

The existing generic utility package should disappear as responsibilities migrate. For example, device/resource logic belongs to `compute.environment`, while terminal box-table rendering belongs with the reporting/dashboard layer that consumes it unless broader reuse proves necessary.

### No generic utility package by default

Do not add a top-level `utils/` merely to make imports shorter. A generic utility package tends to accumulate unrelated behavior, obscure ownership, and create dependency cycles.

A new foundational package is justified only when all of these are true:

1. the behavior is domain-neutral;
2. at least three independent top-level packages need it, or two packages need it and neither can reasonably own it;
3. the API can be described by one precise responsibility;
4. it has no upward dependency on trading, simulation, training, evaluation, experiments, or scripts;
5. moving it does not merge subtly different semantics;
6. tests can prove compatibility for every migrated caller.

`configuration` and `artifacts` already satisfy this role for most repository-wide concerns. Prefer extending those focused foundations over inventing `utils`.

### Duplication-removal workflow

For each candidate duplication:

1. locate all implementations and call sites;
2. compare signatures, accepted types, units, defaults, exceptions, side effects, ordering, determinism, and numerical behavior;
3. classify the behavior by semantic owner;
4. add characterization tests for each existing implementation when behavior is not already protected;
5. implement one canonical function behind the owning package API;
6. migrate callers one group at a time;
7. keep a compatibility shim only when historical imports or checkpoints require it;
8. run result-equivalence tests on representative real inputs;
9. delete the duplicate implementation after all callers migrate;
10. add an architecture test or lint rule when the duplicated pattern is important enough to prevent from returning.

### Result-equivalence requirement

When replacing several implementations with one shared function, "same result" includes more than the return value.

For pure deterministic functions, equivalence should cover:

- exact equality for discrete/state/schema/path outputs;
- bitwise equality where practical for hashes/serialization;
- configured `rtol`/`atol` for floating-point calculations;
- stable ordering for dictionaries, columns, events, and manifests where ordering is part of identity;
- identical exception types for invalid input when callers depend on them.

For stateful or I/O helpers, also verify:

- files produced and their schema;
- atomic/completion behavior;
- overwrite rules;
- side effects and logging contracts;
- deterministic provenance/identity fields;
- failure and recovery behavior.

A shared implementation must not silently change research results merely because its API looks cleaner.

### Duplicate-function inventory as an implementation aid

Before moving each package, the implementation agent should run an AST/search-based duplicate inventory for that package and its callers. The inventory is a review aid, not an automatic refactoring list. Generic names such as `main`, `reset`, `forward`, or `to_dict` usually represent different contracts and should not be merged automatically.

High-value current candidates include repeated SHA-256 helpers, JSON readers/writers, artifact writers, path/layout construction, resource/device resolution, position-sizing logic, and semantic plot transforms. Strategy methods with the same name should instead be consolidated through explicit interfaces/base classes only where their contracts are intentionally identical.

## Repository-wide ownership, functional naming, and placement architecture

The P7 filename is a concrete example that exposed this problem, not a
special-case cleanup target. The current canonical
`scripts/research/thesis/evidence/build_paired_seed_payload.py` has a
functional basename, but it contains roughly 368 lines of experiment run validation,
provenance checks, paired-payload construction, and CLI code. That is not a
thin script wrapper and it obscures the owning package. The target is the
package-owned API `evaluation/reanalysis/paired_seed_payload.py`, with the
`scripts/` file reduced to argument parsing, API invocation, and exit/report
handling. Keep frozen P7 experiment run parameters in a declarative experiment run input
and historical source identity in provenance snapshots, separate from
reusable payload logic. Preserve the exact
historical source bytes and hashes in the existing snapshot/provenance system;
do not make a P7-named active implementation or rewrite frozen evidence.

The adjacent paired-seed statistics implementation has the same layer problem:
`scripts/research/thesis/evidence/analyze_paired_seed_results.py` is about 402
lines, and its statistical API is imported by both the payload/stress-report
code and a test. Move the reusable calculation contract to
`evaluation/reanalysis/paired_seed_statistics.py`; keep only command-line
adaptation in `scripts/`, and place its tests under the evaluation test owner.
This second example makes the rule explicit: useful filenames do not make
script-owned reusable libraries architecturally sound.

This example is a placement and responsibility defect even though the current
basename says what the script builds. The broader audit must separately ask
whether each filename communicates its own behavior, whether its contents form
one responsibility, and whether that responsibility belongs in its current
package. A parent directory or phase label must not be needed to guess what a
reusable file does. Apply the same review to every active file and directory;
do not treat P7 cleanup as the goal.

Before broad code movement, build and maintain a repository architecture
inventory. For each tracked active file, record:

| Field | Required decision |
|---|---|
| Current path and kind | Source, test, config, command, documentation, fixture, generated output, evidence, or support file |
| Actual responsibility | What behavior or information the file owns, based on its contents and consumers |
| Canonical owner | The package or repository area responsible for its contract and lifecycle |
| Boundary assessment | Whether the content forms one cohesive responsibility or mixes unrelated concerns |
| Filename assessment | Functional, legitimate domain/protocol identity, historical identity, or misleading/generic/ordinal |
| Target disposition | Keep; rename; move; split by responsibility; merge after equivalence proof; retain as historical evidence; or retire |
| Consumers and compatibility | Imports, commands, configs, workflows, saved launchers, serialized references, and migration/expiry rule |
| Verification | Characterization/parity tests and searches required to prove the move is safe |

The inventory is a design tool, not a mass-rename instruction. Inspect content,
ownership, dependency direction, generated-file lifecycle, and consumers before
choosing a destination. For each source/config/test/command filename, a reviewer
who has not followed the task history should be able to infer its primary
responsibility from the filename itself; package context may refine that
meaning, but cannot rescue a placeholder such as `core.py`, `pipeline.py`, or
`build_p7_report.py`. Add a folder or package only when several files form a
cohesive domain with a clear public API and dependency direction. Keep a file in
place when its current owner is correct. Split mixed files only along real
responsibility boundaries; do not create numbered fragments or folders that
exist only to mirror plan phases. Consolidate duplicated code only after its
input/output contracts, error behavior, determinism, units, side effects, and
research semantics are shown to match.

The filename guard is only a regression check for known placeholder patterns.
It cannot prove that an unflagged name such as `runner.py`, `builder.py`,
`manager.py`, `report.py`, or `data.py` is meaningful in its actual context.
Review those names by reading the file and tracing its callers; record a
keep/rename/move/split decision with evidence. Do not add broad allowlists to
make the guard pass. A retained generic name needs a narrow rationale tied to
an established Python/framework convention or a demonstrated compatibility
contract, plus an owner and retirement condition where applicable.

Phase 0 owns the inventory and target map. No broad package-migration phase is
complete while an active file has no owner/disposition, while an unresolved
phase-only or generic filename is being treated as canonical, or while a move
has no consumer/compatibility plan. Each later phase updates the same ledger
for files it touches and closes its entries with focused verification. The
ledger must cover source, tests, fixtures, configs, docs, scripts, tools, CI,
Slurm launchers, evidence/report generators, and output/cache producers. Large
data and generated research outputs are classified by owner and retention
policy; their contents and established identities are not renamed for cosmetic
consistency.

The plan's file inventory is the canonical refactor ledger; do not create a
separate competing architecture plan. The ledger must include concrete
current-to-target paths for the P7 paired-seed builder above and for every
additional priority finding. It must not describe a target only as “move into
evaluation” or “rename to a meaningful name”: specify the module/API, the
thin command wrapper if one remains, active consumers to migrate, compatibility
disposition, and the focused verification. As the audit expands beyond
`scripts/`, add equivalent reviewed inventory sections for package modules,
tests, config assets, docs, CI/Slurm wrappers, and artifact/cache/output
producers. A file class is not audited merely because its directory appears in
the ownership matrix.

The current path-level ledger is
[`docs/architecture/repository_file_ownership_inventory.csv`](architecture/repository_file_ownership_inventory.csv).
Its completed Phase 0 snapshot records 1,564 active repository paths, plus its
own ledger row: 454 production Python files, 166 commands/tools, 278 tests and
fixtures, 155 configuration assets, 118 documentation files, 323
data/cache/output/evidence files, 32 agent-guidance files, 4 CI files, 29
repository-support files, 4 tracked data-mode symlinks, and the protected
`experiment_run_worker_dispatch.log`. It records owner, responsibility, filename
class, disposition, consumer/compatibility evidence, and verification
requirements. Twenty-eight paths tracked by the baseline commit are deleted in
the current migration and are therefore not counted as active; their source
remains available through Git history. The inventory is a dated state record;
it does not authorize staging, moving, rewriting, or cleaning user/runtime
data.

#### First source-reviewed generic-name inventory

The initial basename scan found 18 Python modules. The table records that first
scan and its candidate dispositions; the completed path-level ledger below is
the current record and supersedes stale source paths or preliminary decisions
in this snapshot. For later implementation, recheck the live import/call
surface, public API, serialized/checkpoint references, characterization
coverage, and target package boundary. Keep compatibility entries only where
the specific legacy consumer is demonstrated.

| Current path | Responsibility observed in source | Phase 0 disposition / target to verify |
|---|---|---|
| `artifacts/registry.py` | Artifact kind schema and validator registration | Current source and symbol search found no in-repository consumer; retire the speculative registry unless a dynamic/external consumer is demonstrated. |
| `configuration/loader.py` | Load shared YAML config with repository-relative default path | Rename to `configuration/configuration_loader.py`; preserve CLI override semantics and public imports. |
| `evaluation/reanalysis/runner.py` | Reanalyze a PPO checkpoint into a separate immutable run | Rename to `evaluation/reanalysis/checkpoint_reanalysis.py`; verify report-only/overwrite safety callers. |
| `evaluation/reporting/summary.py` | Multi-seed aggregation, report tables, and run summary construction | Inspect whether aggregation and rendering are distinct; split only if tests show separate contracts, otherwise rename to `evaluation/reporting/run_summary.py`. |
| `evaluation/rollout/runner.py` | Run policy-agnostic episodes and collect scores/trades/breaches | Rename to `evaluation/rollout/episode_rollout.py`; preserve rollout ordering and metrics. |
| `experiments/variants/runner.py` | Legacy ablation command facade | Put the reusable lifecycle in `experiments/variants/variant_ablation_runner.py`; own argument parsing and dispatch in `experiments/cli.py`; retain the old module facade until Phase 11 gates pass. |
| `features/pipeline/feature_matrix_builder.py` | Construct the causal feature matrix across configured timeframes | Renamed from `builder.py`; active callers migrated, the stable `features.pipeline.build_features` API is unchanged, and the feature/cache parity group passed. Generated code-graph outputs retain their historical source paths. |
| `features/pipeline/feature_cache_identity.py` | Feature-cache content identity and path construction | Renamed from `cache.py`; package exports, cache version, hash inputs, path construction, and sidecar behavior are unchanged. |
| `features/po3/config.py` | Compatibility exports for the former PO3 rules module | Check all consumers. Remove if unused; otherwise rename to a clearly marked `legacy_rules_compat.py` path where callers permit, or retain only the proven import shim with an expiry rule. |
| `integrations/mt5/adapters/data.py` | Abstract broker data-provider contract | Rename to `integrations/mt5/adapters/trading_data.py`; verify MT5 adapter imports and any plugin contract. |
| `models/encoders/common.py` | Forwarding exports for historical encoder checkpoint/import paths | Keep as a narrow compatibility shim only while checkpoint inventory proves it is needed; test symbol identity and define a removal condition. |
| `models/encoders/core.py` | Forwarding exports for split sequence encoder modules | Same checkpoint/import audit as `common.py`; remove or narrow after serialized-reference search and load tests. |
| `orchestra/report.py` | Assemble a final Markdown report from task state | Rename to `orchestra/task_report.py` or `orchestra/final_task_report.py` after checking whether it only renders or also assembles report data. |
| `simulation/backtest/event_driven_backtest.py` | Event-driven fills, stops/targets, equity marks, and backtest execution | Renamed from `engine.py`; external callers now use `simulation.backtest.run_backtest`. |
| `simulation/environment/trading_environment_factory.py` | Build train/evaluation environments from resolved config | Renamed from `factory.py`; train/evaluation construction is exposed through `simulation.environment`. |
| `trading/policy/config.py` | Resolve the shared selectable trading-policy configuration | Rename to `trading/policy/trading_policy_config.py`; retain configuration schema and fallback semantics. |
| `training/runner/training.py` | CLI entry point for PPO/SAC training | Rename to `training/runner/train_policy.py` or another source-backed action name; verify console and module entry points. |
| `training/setup/data.py` | Materialize training data and preflight tick execution coverage | Review as a likely mixed responsibility; consider separate `training_data_setup.py` and `tick_execution_preflight.py` only if callers/tests confirm independent owners. |

This first table is a dated source-review sample, not the live disposition list.
The completed ledger now covers the active repository paths and records exact
owners and decisions for the source boundary findings, tests, configs, docs,
commands, CI/Slurm surfaces, data aliases, and retained evidence. Later phases
must update this same ledger when a file moves or is retired.

The expanded source pass records additional current-path decisions in the
ledger. Phase 7 has moved the durable experiment run composition root to
`experiments/runs/execution.py`; internal callers use it, while
`experiments/runs/execution.py` remains a narrow compatibility adapter for
legacy launchers and public imports. `features/pipeline/context.py` mixes
reachable-R observation features, London ATR-distance assembly, and
walk-forward fold fitting; the ledger records exact destinations and stable
package exports. `simulation/backtest/cross_validation/backtrader_runner.py`
now owns the standalone Backtrader implementation. `main.py` forwards to it as
a thin compatibility command until the Phase 11 invocation-window review.
`training/artifacts/metrics.py` was renamed to
`training/artifacts/evaluation_result_writer.py` with its report schema
preserved and the Phase 5 writer tests passing. The experiment run allocation wrapper
that still names retired `trading/account/state.py` remains protected until its
supervisor/recovery contract is terminal; the ledger records its safe follow-up.
The PO3 `config.py`
and encoder `common.py`/`core.py` paths remain explicit compatibility decisions,
not automatic delete/rename candidates.

## Semantic naming and function-shape architecture

Architecture refactoring must improve names and function boundaries as well as file placement. A repository can remain difficult to understand after a directory split if modules, classes, functions, variables, phases, and generated artifacts keep vague or numbered names.

Names must communicate domain intent. Avoid placeholders such as `setting1`, `setting2`, `function1`, `function2`, `part1`, `part2`, `step1`, `step2`, `process_data`, `handle_item`, `do_work`, `misc`, or `common` when a more specific concept exists.

Numbering is acceptable only when the number is itself part of the domain or protocol, for example `tp1`, `tp2`, `tp3`, `M1`, `H1`, a documented migration phase, schema version `v3`, or `seed42`. It must not substitute for a missing concept name.

### Naming rules

Use names that state the action and the domain object. Prefer `approve_trade_risk()` over `process_risk()`, `compute_daily_loss_headroom()` over `calculate_value2()`, `apply_partial_take_profit()` over `handle_tp_part2()`, `resolve_repeated_payout_transition()` over `process_cycle()`, `build_observation_vector()` over `prepare_data()`, and `write_experiment_run_manifest()` over `save_json()` when experiment run semantics matter.

### Function-boundary rules

Do not preserve a large function by splitting it into meaningless numbered fragments such as `_step_part1()`, `_step_part2()`, or `_process_section_3()`. Each extracted function must represent one independently understandable responsibility with a meaningful input/output contract.

For orchestration code, decomposition should follow domain stages. For example, the simulation step flow should decompose around concepts such as `advance_market()`, `update_open_position()`, `apply_exit_rules()`, `evaluate_account_constraints()`, `resolve_payout_transition()`, `decode_policy_action()`, `evaluate_entry_intent()`, `execute_accepted_order()`, `update_reward_and_account_state()`, `build_observation_and_info()`, and `resolve_episode_end()`.

These exact names may adjust to the final implementation, but the extracted responsibilities must remain semantic rather than ordinal.

### Similar ideas require one vocabulary

When several modules describe the same concept, choose one canonical term and use it consistently across code, configuration, logs, metrics, tests, and documentation. Important examples include `requested_risk` / `approved_risk` / `executed_risk`, `daily_loss_headroom` versus `daily_loss_breach`, `account_floor` / `operating_equity` / `realized_balance` / `payout`, `dataset` / `partition` / `feature_schema` / `cache_identity`, `run` / `attempt` / `checkpoint` / `experiment run` / `evaluation`, `terminated` versus `truncated`, and `entry_intent` / `order` / `fill` / `position` / `exit`.

Do not keep parallel synonyms such as `job/run/trial` or `risk_cap/risk_budget/risk_limit` unless they intentionally represent different concepts and the distinction is documented.

### Rename when ownership changes

Moving code to a new package is an opportunity to correct misleading names. If an old name reflects its former container instead of its actual responsibility, rename it during migration and keep a compatibility alias only when external callers, historical imports, checkpoints, serialized metadata, or persisted artifact fields require one.

Renames must be behavior-preserving. Update imports, config keys where migration is intentional, tests, documentation, and artifact schemas together. Do not silently rename persisted fields used by historical analysis.

### Public API naming

Public APIs exposed through `__init__.py` must use stable domain names. Avoid temporary migration names such as `new_*`, `legacy2_*`, `refactor_*`, `tmp_*`, or arbitrary `v2_*` names unless versioning is part of the supported contract.

### Naming audit during refactor

For every moved responsibility, review the module/package name, public class/function names, key state variables and dataclass fields, config keys and schema fields, metric/log/event names, generated artifact filenames and manifest fields, test names/fixtures, and documentation terminology.

The goal is a consistent conceptual model that lets a developer follow one idea through configuration, runtime code, artifacts, tests, and reports without translating between arbitrary aliases.

#### Functional filenames across the repository

Apply this audit to **all** active files, not only the P7 example that surfaced the issue. A source, test, config, or command filename must tell a reader what responsibility it owns without requiring a thesis phase, work-package number, date, task history, or surrounding conversation to decode it. Prefer names such as `paired_seed_payload.py`, `build_paired_seed_payload.py`, `analyze_training_dynamics.py`, or `test_paired_seed_payload.py`; do not use `p7_build_report.py`, `wp3_pipeline.py`, `phase_4.py`, or equivalent labels as the primary functional name. The P7 implementation specifically must end with its reusable validation/payload behavior in the owning evaluation package and only its command adapter in `scripts/`.

Review tracked filenames repository-wide, including package modules, scripts, tests, configs, CI/Slurm entry points, generators, and reusable output builders. For each phase/ordinal-prefixed implementation file, record one disposition in the migration ledger: rename to its owning package and responsibility; classify it as a deliberate compatibility/provenance alias with its consumer and expiry condition; or retain it as an immutable historical experiment identity. A phase identifier may remain in an experiment run key, schema/protocol identifier, or frozen evidence path when it is part of that artifact's established identity, but it must not substitute for the functionality name of reusable code.

This also applies to files with no phase token. Names such as `misc.py`, `helpers.py`, `new_report.py`, `final2.yaml`, `test_everything.py`, `run_stuff.sh`, or a broadly named module in the wrong package are audit candidates, not acceptable defaults. Determine the file's actual behavior and ownership, then give it a precise functional name and put it beside the package/subsystem that owns that behavior. Split a file only when its contents represent distinct responsibilities; do not split mechanically into numbered fragments. Add a folder/package only when the grouped files form a cohesive domain boundary with a clear API and dependency direction.

Generic shared-module names (`common.py`, `core.py`, `base.py`, `utils.py`, `helpers.py`) require the same content-and-consumer review even when they are package-local. A shared module is acceptable only when its contents form one cohesive concept that the containing package owns; otherwise rename it by responsibility or split it across the actual owners. If an old import path must remain for checkpoint or external compatibility, make the functional module canonical, turn the old path into a narrow forwarding shim, document its concrete compatibility consumer and retirement condition, and test that it forwards to the canonical symbols.

When a historical manifest records the exact source path and hash, preserve that identity in a provenance mapping and immutable source snapshot. Move the canonical implementation to its functional owner and migrate all active callers. If one historical source file is split across multiple responsibilities, the provenance record must distinguish the immutable historical snapshot/hash from the one-or-many active replacement paths; no replacement module is expected to hash as the old combined file. Verify the snapshot bytes and test each replacement contract independently. Do not keep a misleading phase-named symlink/wrapper solely because an old report, manifest, or saved command records that historical path: preserve the original path as provenance metadata instead. Keep a live old-path alias only for a demonstrated external/public contract that cannot be migrated; it must be clearly isolated from the canonical package, tested, and have an expiry/removal condition. Do not rewrite frozen research manifests or regenerate evidence merely to make their historical path look current. If no supported external contract requires an alias, remove it after migrating callers.

The naming audit is complete only when an inventory of all active repository files—not only source/test/config/command paths—has a reviewed responsibility, owner, and disposition. Every active filename must communicate its behavior or domain, and every active file must live under the right owner. No unexplained phase-only, ordinal-only, generic, misleading, or misplaced name remains. A search result is not automatically a rename: experiment run IDs, named protocol stages, timeframe identifiers, schema versions, seeds, and frozen evidence remain governed by their own identity contracts.

The first concrete application is the thesis evidence tooling. Its current implementations are organized by operation under `scripts/research/thesis/evidence/` or `scripts/research/frozen-launches/`; immutable source copies live under `docs/thesis/evidence/source_snapshots/`:

| Historical path recorded in evidence | Canonical functional file | Historical-byte disposition |
|---|---|---|
| `scripts/research/thesis/p6_monthly_entry_exit_decomposition.py` | `scripts/research/thesis/evidence/analyze_monthly_trade_expectancy_and_exit_decomposition.py` | Alias removed; exact source retained in the snapshot manifest and immutable source file |
| `scripts/research/thesis/p6_training_dynamics_control.py` | `scripts/research/thesis/evidence/analyze_training_policy_dynamics_and_rule_control.py` | Alias removed; exact source retained in the snapshot manifest and immutable source file |
| `scripts/research/thesis/evidence/build_p7_paired_seed_payload.py` | `scripts/research/thesis/evidence/build_paired_seed_payload.py` | Alias removed; exact source retained in the snapshot manifest and immutable source file |
| `scripts/research/thesis/evidence/build_p7_tick_cost_stress_reports.py` | `scripts/research/thesis/evidence/build_tick_cost_stress_reports.py` | Alias removed; exact prior source retained in the snapshot manifest and immutable source file |
| `scripts/research/thesis/evidence/run_p7_tick_cost_stress_replay.py` | `scripts/research/thesis/evidence/replay_tick_cost_stress.py` | Alias removed; exact prior source retained in the snapshot manifest and immutable source file |
| `scripts/research/audits/run_p1_schedule_freeze_gate.sh` | `scripts/research/frozen-launches/freeze_tick_decision_schedule.sh` | Alias removed; frozen launcher retains the same bytes and mapped historical hash |
| `scripts/research/audits/run_p1_tick_fold_validation.sh` | `scripts/research/frozen-launches/validate_tick_fold_scope.sh` | Alias removed; frozen launcher retains the same bytes and mapped historical hash |
| `scripts/research/audits/run_p1_tick_quality_validation.sh` | `scripts/research/frozen-launches/validate_tick_data_quality.sh` | Alias removed; frozen launcher retains the same bytes and mapped historical hash |
| `scripts/research/audits/run_p3_checkpoint_recovery_smoke.sh` | `scripts/research/frozen-launches/smoke_test_checkpoint_recovery.sh` | Alias removed; frozen launcher retains the same bytes and mapped historical hash |
| `tests/test_wp02_accounting.py` | `tests/integration/test_position_fill_accounting.py` | Test is discovered by pytest and has no saved import contract |

Current migration state: the nine phase-named symlinks in the ledger were retired on 2026-10-30; their prior source bytes and hashes are recorded in immutable snapshots and provenance mappings. The active functional files in the table are canonical. The P1/P3 frozen launchers remain in the explicitly historical `scripts/research/frozen-launches/` area because their commands target the separate historical Aalto checkout; they are not current operational entry points. Preserve experiment run IDs, output directories, report schemas, and evidence filenames only when the phase label is part of the frozen research identity, not as a substitute for a functionality name. The repository-wide ownership/name/location inventory remains open and must assess files beyond this initial ledger.

The P1/P3 shell aliases are deliberately housed in `scripts/research/frozen-launches/`: their source still targets the historical `/scratch/work/nguyenl37/Aalto_MS_Thesis` checkout, old venvs, and dated artifacts. Treating those launchers as current audit entry points would direct work into a different checkout. Their contents remain intact; use the canonical current audit commands from the owning package and current Slurm helpers instead. `config/experiment_runs/variant_list_p6_entry_fsm.txt` remains a frozen experiment run input identity; P6 is useful there to identify the experiment, and the filename also describes its contents.

**Applied 2026-10-30:** the functional source names, frozen snapshots, compatibility aliases, and accounting-test path above are in place. The focused naming/accounting/paired-seed group passed 24 tests; full-tree Ruff formatting and lint passed; Mypy checked 806 source files; all five current evidence CLIs handled `--help`, all four frozen shell launchers passed `bash -n`, and `git diff --check` passed. Existing experiment_run/report outputs were not regenerated. This closes the first filename/ownership slice only; the remaining architecture phases below are still active work.

**Plan corrections 2026-10-30:** refreshed the measured hotspot inventory to current source paths and line counts; corrected the CI target description to retain the nine semantic jobs plus the three independently justified security/graph assurance gates; and corrected live cache/schema values and feature API paths in `docs/config.md`, `.agents/architecture.md`, and `.agents/domain_maps/features.md`. Historical audit reports and manifests with older versions were left unchanged.

**Validation update 2026-10-30:** the functional-name and operational-cache-documentation architecture guard passes; full-tree Ruff format/check passed, Mypy passed across 807 source files, and 48 focused architecture/naming/provenance/accounting tests passed on the existing GH200 allocation. No training, benchmark, or evidence regeneration was performed.

**Naming audit follow-up, 2026-10-30:** a broader search found `tests/test_wp_correctness.py`, which grouped four independent contracts under a work-package label: stop-action coordinate mapping, swing-based trailing stops, take-profit ordering, and bootstrap drawdown intervals. Split these into `tests/unit/models/test_stop_mode_action_mapping.py`, `tests/unit/simulation/test_environment/test_swing_trailing_stop.py`, `tests/unit/simulation/test_environment/test_take_profit_level_ordering.py`, and `tests/integration/test_bootstrap_drawdown_interval.py`; expanded the architecture guard so generic `_wp_` filenames are covered as well as numbered work-package names. The affected tests and filename guard passed (11 tests); full-tree Mypy then passed for 810 source files. This is another naming/ownership slice; Phase 0 and the repository refactor remain in progress.

**Documentation filename scope, 2026-10-30:** broadened the live filename guard to include active Markdown and JSON documentation outside frozen `docs/thesis/evidence/` and `docs/research/` output trees. The dated `docs/thesis/p1_checkpoint_full_split_budget_2026-10-16.json` is retained as a historical evidence identity. This extends the rule beyond source/config/script names while keeping generated evidence names immutable.

**Repository-wide phase-label scan, 2026-10-30:** a broad tracked-path search returned 105 lexical matches for `pN`, `wpN`, or `phaseN`. Fifteen were trade-plot filenames whose `_p<number>` suffix is a P&L value, not a phase label. The old `tests/test_wp_correctness.py` grouped unrelated checks and has now been split into functionally named model, environment, and evaluation tests. The remaining actual phase/work-package matches were triaged as evidence, experiment run identity/configuration, or compatibility source/launcher aliases. That lexical triage did not validate that filenames are meaningful or locations are correct, and the existence of a historical reference does not justify keeping an active phase-named command. The full naming/placement audit below remains required.

**Naming/placement plan update, 2026-10-30:** broaden the audit from phase-token cleanup to every active repository file and directory. Review actual responsibility and ownership for modules, tests, fixtures, configs, commands, tooling, docs, report/evidence generators, and artifact producers; rename and relocate misleading files and migrate active references. The canonical filename must describe what the file does, while phase/experiment_run identity belongs in configuration or artifact metadata. Preserve historical source hashes through functionally named immutable snapshots plus provenance mappings; retire P6/P7/P1/P3 active aliases unless an independently demonstrated public contract requires them. The earlier filename ledger and 105-token scan are inputs to this work, not its completion evidence.

**Functional-name and ownership clarification, 2026-10-30:** the active paired-seed builder has a descriptive filename, but its 368-line combination of frozen experiment run validation, provenance, payload assembly, and CLI remains in `scripts/`; this conflicts with the thin-wrapper boundary. Move the reusable payload contract to `evaluation/reanalysis/paired_seed_payload.py`, leave a narrow command adapter at the script path, and keep frozen P7 parameters in a declarative experiment run input and historical source identity in provenance snapshots. The adjacent 402-line paired-seed statistics file also exposes reusable analysis logic to another script and a test; move that API to `evaluation/reanalysis/paired_seed_statistics.py`, retain a thin CLI, and relocate the tests to the evaluation test owner. These are concrete Phase 0 inventory items and Phase 6 evaluation migration targets. The new naming/ownership review applies to all active files, including plausible but vague names (`runner.py`, `builder.py`, `manager.py`, `report.py`, `data.py`) that a phase-token or generic-basename regex cannot judge; these two examples do not imply the rest of the repository inventory is complete.

**Refactor continuation, 2026-10-30:** the current implementation turn has recorded the paired-seed module/CLI split as a migration target, not claimed it is implemented. Full-tree Ruff format, Ruff check, Mypy (814 source files), and `git diff --check` pass on the existing GH200 allocation; the scoped architecture, configuration-resolution, model/checkpoint, market-data, environment, backtest, cache-recovery, and Orchestra group passes 257 tests. The ownership/name/location inventory is still open. Continue by auditing file contents and callers, especially vague but unflagged filenames and code that violates its layer boundary; update the migration ledger with evidence and focused tests before each move.

**Source-reviewed name inventory, 2026-10-30:** the first native-node scan found 18 active Python modules with generic or compatibility-oriented basenames. The plan now records their observed responsibility and proposed disposition, including explicit target names for artifact-kind registration, configuration loading, checkpoint reanalysis, episode rollout, feature-matrix building/cache identity, the backtest engine, environment construction, policy config, and training CLI. Several rows require caller/checkpoint review before any move; `features/po3/config.py` and encoder forwarding modules are not blindly renamed. At this point the sample was not a full inventory and did not close Phase 0; the completed path-level review below supersedes that status. No source module was moved by this inventory update.

**Feature-matrix module naming, 2026-10-30:** renamed `features/pipeline/builder.py` to `features/pipeline/feature_matrix_builder.py` after tracing every active import, documentation reference, audit input path, and code-graph expectation. Kept the stable `features.pipeline.build_features` API unchanged; removed the old module path rather than adding a shim because no active import or serialized-class contract requires it. The scoped feature/cache/graph/data tests passed (300 tests), full-tree Ruff format/check passed, full-tree Mypy passed across 814 source files, and `git diff --check` passed. Existing generated code-graph outputs were left untouched and still contain their historical source path. The builder remains a large stage coordinator and is not yet decomposed; the wider inventory and Phase 0 remain open.

**Feature-cache module naming, 2026-10-30:** renamed `features/pipeline/cache.py` to `features/pipeline/feature_cache_identity.py` after tracing code and documentation imports. The stable `features` and `features.pipeline` exports remain unchanged; the version marker, hash payload, cache paths, and sidecar semantics are unchanged. The expanded focused feature/cache/graph/data/naming group passed (303 tests); full-tree Ruff format/check and Mypy passed across 814 source files; `git diff --check` passed. No cache contents were rebuilt or rewritten. This closes the specific basename finding, not the feature-pipeline decomposition or repository-wide inventory.

**Phase-label alias retirement, 2026-10-30:** removed nine active symlinks whose visible filenames identified P1/P3/P6/P7 rather than their responsibility. The four P1/P3 frozen launchers remain under `scripts/research/frozen-launches/`; P6/P7 implementations use functional names under their owning research areas. Exact bytes for all nine historical paths are mapped with SHA-256 in `docs/thesis/evidence/source_snapshots/manifest.json`; two P7 stress-tool snapshots were added because their current implementations have since changed. Frozen report/manifests remain unchanged and retain their historical source-path strings. Replaced the symlink-presence test with `tests/research/test_historical_source_mappings.py`, which validates path retirement, canonical file bytes, recorded P6/P7 evidence hashes, and current functional command help. The focused naming/source-mapping group passed 17 tests. The broader repository naming/ownership audit remains open.

**Phase 0 contract inventory, 2026-10-30:** the live test tree already has import/dependency/execution-surface checks under `tests/architecture/`; environment transition golden traces and bundle equivalence under `tests/unit/simulation/test_environment/`; broker/backtest accounting and quote-parity checks under `tests/integration/backtest/`; feature output/causality/cache-fit checks under `tests/unit/features/`; observation/action/checkpoint schema roundtrips under `tests/unit/models/` and `tests/unit/simulation/test_environment/`; and experiment run artifact/recovery checks under `tests/test_experiment_run_*.py` and `tests/test_triton_experiment_run_*.py`. At initial inventory, public version markers were bar cache `v3-native-timeframes`, tick cache `v3-validated-full-day`, feature cache `v33-timeframe-entry-ideas`, account observations `account-state-v1` / `account-state-v2` / `account-state-v3-repeated-payout`, legacy overlay actions `overlay-action-v2`, discrete actions `discrete-trading-v1`, and thesis candidate/observation/action schemas `thesis-candidate-v1` / `thesis-observation-v1` / `thesis-overlay-action-v1`; their definitions live in `market_data/loading/`, `features/pipeline/cache.py`, and `decisioning/`. The cache markers have since been migrated to bar/tick `v4-semantic-manifest`; the other listed schemas remain unchanged at this checkpoint. This records existing protection rather than a passing result for every suite. This first contract inventory left Phase 0 open; the completed inventory and verification recorded below close it.

**Execution-surface baseline, 2026-10-30:** `.github/workflows/ci.yml` has 13 jobs: `dependency-lock`; independent `security-deps` and `security-secrets`; `quality`, `architecture`, `graph-quality`, `contracts`, `unit`, and `build-smoke`; `integration` and `parity` (each after architecture/contracts/unit); `training-smoke` (after integration/parity/build); and the `ci-success` aggregator. `tools/check` is the shared local/CI dispatcher for `deps`, both security checks, `quality`, `architecture`, `graph-quality`, `contracts`, `unit`, `build`, `integration`, `parity`, `training-smoke`, and the GPU/Triton wrapper. Current pytest markers are only `slow`, `unit`, and `integration`; GPU, Triton, and research scheduling are not separately encoded as markers. Public console commands are `orchestra`, `thesis-data`, `thesis-train`, `thesis-evaluate`, `thesis-experiment-run`, and `thesis-compute`. Docker currently exposes `builder`, `runtime`, `dev`, and `test` image stages; Compose provides base/dev/dev-gpu/test/test-gpu services plus data discovery/preparation, baseline, train, backtest, lint/typecheck, and live/demo entry points. Slurm launch, supervision, and status scripts are under `scripts/compute/slurm/`, with experiment-run-specific launchers under its `experiment_runs/` directory. This is the frozen current surface to compare against the Phase 9 target; the absence of dedicated pytest execution markers is recorded as a migration gap, not silently treated as existing behavior. <!-- pragma: allowlist secret -->

**Artifact-foundation audit, 2026-10-30:** `artifacts/promotion.py` had no callers or tests and previously copied directly to the destination without executing a validation gate or persisting the supplied manifest. Replaced the incomplete operation with a typed validator result (`BaselineValidation`, containing a command and passed checks); it validates a staged file/tree copy, writes the baseline manifest and payload in a sibling temporary directory, and publishes the completed directory only after both are ready. It refuses non-promotable retention, incomplete validation, unsupported sources, and existing destinations without overwrite. Added the function and validation type to the `artifacts` public API and tests for successful file/tree promotion, manifest roundtrip, rejection, and no-overwrite behavior. This establishes the promotion primitive but does not close Phase 1: artifact-kind schemas, source lineage completeness, and integration with actual baseline workflows remain to be assessed before any real baseline is promoted.

**Validation update 2026-10-30:** after the filename split and artifact-promotion change, full-tree Ruff format/check passed, full-tree Mypy passed for 811 source files, and 69 focused architecture, naming/provenance, accounting, artifact-lifecycle, and behavior-characterization tests passed on the existing GH200 allocation. This is scoped implementation validation, not the final repository CI gate or full test suite.

**Artifact validation contract refinement, 2026-10-30:** the promotion validator now returns typed `BaselineValidation` evidence instead of accepting a caller-asserted `accepted=true` dictionary. A successful callback is therefore required before the manifest can record acceptance; command/check names are validated by the evidence type. Focused artifact checks passed (12 tests, scoped Mypy over the artifact package and promotion test). The final full-tree quality gate remains outstanding.

**Artifact layout migration, 2026-10-30:** training and evaluation run-directory construction now uses the shared `ArtifactLayout.timestamped_run()` API rather than keeping a path builder under evaluation and importing it from training. The timestamp format and no-directory-creation behavior are covered by a fixed-time test. The affected artifact/export/provenance tests passed (89 tests). This closes one Phase 1 extraction only; remaining writers, manifests, artifact kinds, and the repository-wide ownership/name/location inventory are still open.

**Shared-module naming migration, 2026-10-30:** canonical plot helpers moved from `evaluation/plotting/common.py` to `evaluation/plotting/plot_rendering.py`, whose responsibility is Matplotlib defaults, colors, and figure output. Sequence-encoder primitives moved from `models/encoders/common.py` to `models/encoders/sequence_encoder_components.py`; all in-repository encoder implementations now import the functional module. Efficient MTF components moved from `models/encoders/mtf_efficiency_common.py` to `models/encoders/mtf_efficiency_components.py`, preserving a narrow forwarding shim for serialized-module compatibility. Plotly helpers moved from `evaluation/plotting/interactive_common.py` to `evaluation/plotting/interactive_plot_rendering.py`, and internal callers were migrated. The old `models/encoders/common.py` forwarding shim remains for legacy checkpoint/import compatibility and has an identity test; inventory saved checkpoints before setting retirement conditions for either encoder shim. Expanded the active filename contract test to reject selected generic placeholder names and `*_common.py` names, with explicit exceptions only for those two shims. Encoder, checkpoint-migration, MTF, evaluation-plotting, and architecture filename tests passed (227 tests). Full-tree gates were still outstanding at this entry and were subsequently rerun as recorded below. This closes several concrete naming slices, not the repository-wide naming/placement audit.

**Learning/model naming cleanup, 2026-10-30:** renamed the single-purpose `learning/build.py` learner constructor to `learning/learner_factory.py`; `learning.__init__` remains the stable public entry point and internal consumers use it. Removed `models/base.py` after a repository Python-import search found no consumers; its abstract `Encoder`/`Policy` template duplicated no live model contract and carried stale implementation instructions. The supervised-reference tests passed (2 tests); the complete root-package and stale-documentation audit remains open. The old encoder `core.py` is still classified for a separate checkpoint-compatibility review rather than being renamed or deleted on filename evidence alone.

**Full-tree quality refresh, 2026-10-30:** on the existing `gpuarm1` aarch64 allocation, `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, and `.venv/bin/mypy .` all passed; Mypy checked 813 source files. The scoped architecture, encoder, MTF, plotting, checkpoint-migration, and supervised-reference tests passed in the preceding slices. This does not substitute for final scoped tests after later edits or the full final handoff review.

**Refactor validation refresh, 2026-10-30:** on the existing GH200 allocation, full-tree Ruff format check, Ruff lint, and Mypy passed (811 source files). The current focused naming, path-compatibility, fill-accounting, split behavior-contract, artifact-promotion, and artifact-store set passed (40 tests). One initial pytest invocation referenced a nonexistent directory and collected no tests; the corrected invocation used the actual artifact test modules and passed. This remains scoped validation, not the final CI gate.

**Atomic artifact-write consolidation, 2026-10-30:** the experiment run state store, training run-manifest writer, weekly experiment manifests, resolved-variant manifest, reanalysis outputs, Orchestra health/quota/task/cost state, per-seed training outputs, and evaluation reports/diagnostics had separate JSON or text replacement/write paths beside `artifacts.atomic`. They now delegate to the shared atomic file primitive while preserving each writer's JSON ordering, newline, and strict-versus-string-fallback behavior. The shared JSON writer keeps its historical string fallback for metadata callers and exposes strict mode explicitly. Added focused coverage for strict serialization failure preserving the prior file, legacy fallback behavior, experiment run state roundtrip, and Orchestra task/cost persistence. Baseline promotion also records a SHA-256 digest of the staged payload tree and rejects a validator that changes the staged bytes. No existing artifact was rewritten or promoted.

**Atomic-write validation, 2026-10-30:** full-tree Ruff format/lint and Mypy passed across 814 source files. The focused persistence/artifact, experiment run, manifest, walk-forward, training decomposition/smoke, Orchestra, architecture-name, and deterministic-reanalysis set passed 163 tests; the training smoke emitted the existing PyTorch nested-tensor warning. After extending the atomic-write change through evaluation exports, full-tree Ruff format/lint and Mypy passed again; all 24 architecture tests and 75 evaluation-reporting/export tests passed. Two existing pandas downcasting warnings appeared in plotting export tests. No benchmark or long training experiment run ran.

**Shared checksum ownership, 2026-10-30:** identical bounded-memory file SHA-256 loops existed in market-data cache identity, evaluation run manifests, reanalysis, Slurm recovery, and baseline-cache reporting. Moved the canonical file-content hash to `artifacts.identity.file_sha256` and exported it from `artifacts`; migrated package consumers while retaining the historical `evaluation.reporting.run_manifest.file_sha256` import as a re-export for existing callers. Market-data cache identity continues to own semantic cache IDs, not generic file hashing. The digest is byte-identical and accepts both string and `Path` inputs. Relevant artifact, run-manifest, reanalysis-provenance, historical-source, naming, and tick-cache tests passed: 120 tests in 7.25 seconds. Other script-local hash routines remain candidates only after their optional/error semantics and frozen-source role are compared.

**Validation update, 2026-10-30:** after retiring the phase-named aliases, adding the source snapshot map, and centralizing file SHA-256, full-tree Ruff format/check passed, full-tree Mypy passed for 812 files, and `git diff --check` passed. The combined artifact, manifest, reanalysis, historical-source, naming, tick-cache, Slurm recovery, and checkpoint-migration group passed 131 tests in 6.62 seconds. This validates these slices only. The architecture-wide file/owner inventory, cache/data producers beyond bars/ticks, remaining duplicate helpers, and migration phases are still open.

**Bar-cache semantic identity and atomicity, 2026-10-30:** bar-cache reuse now keys on partition, symbol, timeframe, raw source identity, timezone, NY session end, timestamp convention, and price-grid identity. Cache entries use a semantic manifest with row/index bounds and a payload size/mtime/inode completion check; parquet is first written to a same-directory temporary file and atomically replaced, then the manifest is atomically published. If manifest publication is interrupted after parquet replacement, the previous manifest cannot validate the new payload. Bumped the live cache path to `v4-semantic-manifest` so old sidecar-only caches are not consumed as completed entries. The full-period rebuild publisher now backs up, publishes, and reports cache companion manifests with their parquet files; experiment run prebuild rejects missing or malformed completion manifests. Added synthetic coverage for timezone/session-end invalidation, manifest identity rejection, corrupted/empty entries, and interrupted payload/manifest writes. No repository data/cache was rebuilt. Validation on the existing GH200 allocation: 36 scoped data/cache/architecture tests passed; full-tree Ruff format/check passed; Mypy passed for 816 source files.

**Tick-cache semantic identity and atomicity, 2026-10-30:** tick-cache reuse now keys on source path and content hash, timezone, session bounds, price-grid identity, and transform/cache version. A shared parquet-cache storage primitive writes parquet to a same-directory temporary file, atomically replaces the payload, and then publishes a completion manifest containing identity, ordered bounds, payload size, modification time, and inode. Readers reject legacy, empty, incomplete, reordered, payload-replaced, or identity-mismatched entries. Bumped the tick cache path to `v4-semantic-manifest`; the experiment run prebuilder and full-period publisher now require and preserve companion manifests. Added tests for source edits, timezone/session changes, price-grid separation, legacy-cache non-consumption, ordered-Series handling, empty-cache rejection, and interrupted payload/manifest publication. No repository data/cache was rebuilt. Final focused validation: 70 data, tick, session, prebuild, and filename-contract tests passed in 0.68 seconds. Full-tree Ruff format and lint passed; full-tree Mypy passed for 817 source files. This cache slice is validated; repository phases remain open.

**Variant configuration convergence, 2026-10-30:** the direct training CLI previously merged only selected ladder flags and strategy YAML, while experiment run launchers used `resolve_variant()` to apply registry defaults, reward mode, risk policy, generic `config_overrides`, full-PO3 feature settings, and the declared algorithm/encoder. A mismatched explicit strategy could also merge one strategy overlay before the variant selected another. The direct CLI now consumes the same resolved variant and applies its complete ordered override set once, followed by user CLI overrides; unset algorithm/encoder/VAE values come from the resolved variant. Removed the duplicate row-only registry loader from `training.configuration.variants`. Added tests for registry-default precedence, direct variant strategy selection, Q5 reward/config overrides, and parity with the resolver path. Scoped Ruff and Mypy passed; 90 variant-resolution, configuration, and training-CLI tests passed. This closes one configuration consistency defect, not the configuration-schema or broader Phase 1 acceptance work.

**Trading/feature/task-state naming migration, 2026-10-30:** replaced active generic `base.py`, `types.py`, and `state.py` modules with `strategy_contract.py`, `step_indexed_strategy.py`, `feature_row_contract.py`, `account_state.py`, `po3_phase_state.py`, and `task_state_store.py`, and migrated imports and domain maps. The filename guard now rejects those placeholder basenames repository-wide; the remaining encoder `core.py` and `common.py` paths are explicit serialization/import compatibility shims and the encoder re-export behavior is tested. Focused account, strategy, PO3, environment, backtest, encoder, Orchestra state/routing/pipeline, and filename-contract validation passed: 186 tests. Full-tree Ruff format/check and Mypy passed, with Mypy covering 813 files; `git diff --check` passed. The full repository inventory remains open.

**Runtime module ownership naming, 2026-10-30:** renamed `market_data/loading/pipeline.py` to `market_data/loading/market_data_ingestion.py`, `orchestra/models.py` to `orchestra/model_provider_registry.py`, and the Orchestra composition class to `orchestra/task_orchestration.py`. Split the mixed `training/setup/models.py` into `training/setup/model_state.py` (critic initialization and constrained-resume validation) and `training/setup/policy_diagnostics.py` (effective optimizer and architecture provenance). Updated active imports, CLI paths, documentation, and the filename guard; retained frozen evidence paths and hashes. Focused registry, training setup, market-data cache, ticks, recovery, Orchestra, account, backtest, and environment validation passed: 257 tests. Ruff format/lint passed on affected paths. Full-tree Mypy and the broader ownership inventory remain outstanding.

**Phase 0 inventory and characterization refresh, 2026-10-30:** added the
canonical path ledger and refreshed it to match the current checkout. The
active path set is exactly reconciled with the working tree: 1,529 tracked files
and symlinks plus 35 untracked nonignored files, including the 20,858-byte
protected `experiment_run_worker_dispatch.log`; all 454 production Python modules
parsed successfully, and the AST consumer map includes production code,
commands, tests, and repository support. The inventory now has an explicit
owner, responsibility, filename class, disposition, and verification path for
every active entry. It records the four normal/discretion symlinks as aliases
of the shared canonical data, without copying or rebuilding their targets.
Large and high-fanout source modules have source/caller-based keep/split/rename
decisions; all 278 tests/fixtures have a concrete future owner path; the 19
generic production-module names have explicit functional, compatibility, or
retirement decisions; and the active ordinal/phase filenames are classified as
experiment run identity or immutable evidence where their identifier is meaningful.
The verified command baseline is 13 CI jobs, 149 regular script files, and 9
script symlinks. Pytest declares `slow`, `unit`, and `integration` markers; the
plan's remaining marker/scheduling work stays in the CI phase.

The Phase 0 characterization batch passed **871 tests** in 60.66 seconds.
After the complete path review, `tests/architecture` passed **25 tests** in
5.36 seconds, the inventory completeness/required-field check passed, and
`git diff --check` passed. Full-tree Ruff format/check and Mypy had already
passed on the same source tree (Mypy: 814 source files); the latest changes
were inventory-only, so those gates were not needlessly repeated. The earlier
baseline schema and behavior characterization remains the reference for later
migrations. **Phase 0 is complete.** No training, benchmark, cache rebuild, or
research output mutation was performed. Validation remains inside allocation
`21296559` on `gpuarm1`; keep its persistent shell available for the ordered
implementation phases.

## Current structural problems

The issue is broader than file length. The table below is a live 2026-10-30 source scan; the prior `envs/`, `train/`, `eval/`, `backtest/`, and `quant_rl/` entries described an earlier tree and must not be used as current migration targets. Line count is a review signal, not by itself a mandate to split a module.

| Priority | Current area | Lines | Observed responsibility concentration |
|---|---|---:|---|
| P0 | `training/runner/seed_runtime.py` | 1,136 | `SeedRunner` prepares a run, trains, evaluates both splits, writes artifacts, and builds the result through one staged object. Review which stage boundaries are real package contracts before extracting. |
| P0 | `features/pipeline/feature_matrix_builder.py` | 802 | Feature entry point coordinates resampling, session schedule, training mask, multiple feature stages, and cache/schema behavior. Preserve causal alignment and cache identity while separating stage ownership; the functional rename alone does not close this decomposition item. |
| P0 | `simulation/environment/entry_execution_runtime.py` | 675 | One mixin owns entry quote resolution, level building, risk capacity, position open/close, and trade-event recording. Characterize accounting and transition behavior before moving code. |
| P1 | `scripts/research/thesis/evaluation/report_variant_details.py` | 2,781 | Report command combines input discovery, metric/config presentation, trade selection, chart generation, and output validation; package-owned reusable reporting logic is mixed with CLI orchestration. |
| P1 | `evaluation/plotting/order_chart.py` | 1,501 | Order-level preparation, zone/swing/retracement extraction, and both Matplotlib and Plotly drawing are in one module. Separate semantic overlay data from renderer adapters. |
| P1 | `scripts/research/thesis/evidence/verify_numerical_report.py` | 1,248 | Split metrics, policy, source, backend parity, provenance checks, and CLI verification are combined. Keep verifier behavior and historical schemas stable. |
| P1 | `scripts/research/thesis/exit_shadow_fixed_entry.py` | 1,233 | Replay setup, execution reconstruction, paired statistics, plotting, and report generation share a research command. Keep research-only semantics out of general evaluation APIs. |
| P1 | `scripts/dev/code_graph/graph_quality.py` | 1,173 | Graph extraction, config/call resolution, threshold verification, report generation, and CLI share a developer tool module. It is a distinct CI tool, not domain code. |
| P1 | `experiments/runs/execution.py` | 1,115 | Experiment run overrides and CLI lifecycle coexist with job snapshot/start orchestration while state, checkpoint, and reporting helpers already live in sibling modules. Identify remaining duplicate ownership before splitting. |
| P1 | `learning/rl/callbacks.py` | 1,113 | Progress, diagnostics, learned risk, evaluation/checkpoint, equity, and abort callbacks are defined in one module. Preserve callback state/resume contracts. |
| P1 | `evaluation/reporting/export.py` | 938 | Run-directory creation, split/trade outputs, chart configuration, and manifest writing share the export module. Keep atomicity and artifact identity intact. |
| P1 | `orchestra/task_orchestration.py` | 655 | A single task-orchestration class still coordinates workflow stages; compare its responsibilities with `orchestra/sessions.py` and stage modules before further extraction. |

These hotspots are migration inputs, not a complete rename list. The package ownership below determines the destination; Phase 0 records existing behavior, and later phases move one boundary at a time.

## Target repository layout

```text
Quantitative-RL-Trading-System/
├── configuration/
│   ├── __init__.py
│   ├── loader.py
│   ├── merge.py
│   ├── schema.py
│   ├── hashing.py
│   ├── paths.py
│   └── compatibility.py
│
├── artifacts/
│   ├── __init__.py
│   ├── identity.py
│   ├── layout.py
│   ├── manifest.py
│   ├── atomic.py
│   ├── registry.py
│   ├── retention.py
│   └── promotion.py
│
├── market_data/
│   ├── __init__.py
│   ├── loading/
│   │   ├── __init__.py
│   │   ├── bars.py
│   │   ├── ticks.py
│   │   └── datasets.py
│   ├── transforms/
│   │   ├── __init__.py
│   │   ├── align.py
│   │   ├── resample.py
│   │   ├── cleaning.py
│   │   └── sessions.py
│   ├── splits/
│   │   ├── __init__.py
│   │   ├── definitions.py
│   │   └── walkforward.py
│   └── cache/
│       ├── __init__.py
│       ├── identity.py
│       └── storage.py
│
├── features/
│   ├── __init__.py
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── builder.py
│   │   ├── context.py
│   │   ├── normalization.py
│   │   ├── schema.py
│   │   └── cache.py
│   ├── technical/
│   │   ├── __init__.py
│   │   ├── indicators.py
│   │   ├── swings.py
│   │   └── structure.py
│   ├── po3/
│   │   ├── __init__.py
│   │   ├── state.py
│   │   ├── fvg.py
│   │   ├── ifvg.py
│   │   └── entries.py
│   └── context/
│       ├── __init__.py
│       ├── liquidity.py
│       ├── session_levels.py
│       ├── premium_discount.py
│       └── policy_market.py
│
├── trading/
│   ├── __init__.py
│   ├── account/
│   │   ├── __init__.py
│   │   ├── state.py
│   │   ├── accounting.py
│   │   └── limits.py
│   ├── policy/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── legacy.py
│   │   └── repeated_payout.py
│   ├── risk/
│   │   ├── __init__.py
│   │   ├── budget.py
│   │   ├── sizing.py
│   │   └── execution_reserve.py
│   ├── orders/
│   │   ├── __init__.py
│   │   ├── intents.py
│   │   ├── entries.py
│   │   ├── stops.py
│   │   └── targets.py
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── costs.py
│   │   ├── quotes.py
│   │   ├── fills.py
│   │   └── latency.py
│   ├── positions/
│   │   ├── __init__.py
│   │   ├── state.py
│   │   ├── exits.py
│   │   ├── multi_tp.py
│   │   └── trailing.py
│   └── strategies/
│       ├── __init__.py
│       ├── base.py
│       ├── baseline.py
│       ├── po3_ifvg.py
│       └── distribution.py
│
├── simulation/
│   ├── __init__.py
│   ├── contracts/
│   │   ├── __init__.py
│   │   ├── actions.py
│   │   ├── observations.py
│   │   └── results.py
│   ├── environment/
│   │   ├── __init__.py
│   │   ├── env.py
│   │   ├── runtime.py
│   │   ├── reset.py
│   │   ├── step.py
│   │   ├── observations.py
│   │   ├── rewards.py
│   │   ├── sessions.py
│   │   └── diagnostics.py
│   ├── backtest/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── entries.py
│   │   ├── exits.py
│   │   ├── accounting.py
│   │   └── results.py
│   └── parity/
│       ├── __init__.py
│       ├── traces.py
│       └── assertions.py
│
├── models/
│   ├── __init__.py
│   ├── factory/
│   │   ├── __init__.py
│   │   └── encoder_registry.py
│   ├── encoders/
│   │   ├── __init__.py
│   │   ├── tcn.py
│   │   ├── gru.py
│   │   ├── transformer.py
│   │   └── mtf.py
│   └── auxiliary/
│       ├── __init__.py
│       ├── vae.py
│       └── heads.py
│
├── learning/
│   ├── __init__.py
│   ├── contracts.py
│   └── rl/
│       ├── agent.py
│       ├── ppo.py
│       ├── hybrid.py
│       ├── semantic.py
│       ├── callbacks.py
│       ├── checkpoint.py
│       └── rollout_buffer.py
│
├── training/
│   ├── __init__.py
│   ├── configuration/
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   ├── resolution.py
│   │   ├── strategy.py
│   │   └── policy.py
│   ├── setup/
│   │   ├── __init__.py
│   │   ├── data.py
│   │   ├── environments.py
│   │   ├── models.py
│   │   └── callbacks.py
│   ├── runner/
│   │   ├── __init__.py
│   │   ├── seed.py
│   │   └── training.py
│   ├── callbacks/
│   │   ├── __init__.py
│   │   ├── diagnostics.py
│   │   ├── risk.py
│   │   └── checkpoints.py
│   └── artifacts/
│       ├── __init__.py
│       ├── manifests.py
│       ├── evaluation_result_writer.py
│       └── aggregation.py
│
├── evaluation/
│   ├── __init__.py
│   ├── rollout/
│   │   ├── __init__.py
│   │   ├── runner.py
│   │   └── episode.py
│   ├── metrics/
│   │   ├── __init__.py
│   │   ├── performance.py
│   │   ├── distributions.py
│   │   ├── calibration.py
│   │   ├── bootstrap.py
│   │   └── temporal.py
│   ├── reanalysis/
│   │   ├── __init__.py
│   │   ├── inputs.py
│   │   ├── provenance.py
│   │   ├── data_rebuild.py
│   │   ├── schemas.py
│   │   └── runner.py
│   ├── reporting/
│   │   ├── __init__.py
│   │   ├── export.py
│   │   ├── events.py
│   │   ├── diagnostics.py
│   │   └── manifests.py
│   └── plotting/
│       ├── __init__.py
│       ├── transforms.py
│       ├── equity.py
│       ├── orders.py
│       ├── signals.py
│       ├── static.py
│       └── interactive.py
│
├── experiments/
│   ├── __init__.py
│   ├── variants/
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   └── resolution.py
│   ├── experiment_runs/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── state.py
│   │   ├── validation.py
│   │   ├── checkpoints.py
│   │   ├── workers.py
│   │   ├── execution.py
│   │   └── reporting.py
│   └── provenance/
│       ├── __init__.py
│       ├── source.py
│       └── artifacts.py
│
├── live/
│   ├── __init__.py
│   ├── runtime/
│   │   ├── __init__.py
│   │   ├── strategy.py
│   │   ├── risk.py
│   │   └── execution.py
│   └── paper/
│       ├── __init__.py
│       └── logger.py
│
├── integrations/
│   ├── __init__.py
│   └── mt5/
│       ├── __init__.py
│       ├── connection.py
│       ├── data.py
│       ├── trader.py
│       ├── risk.py
│       └── robot.py
│
├── compute/
│   ├── __init__.py
│   ├── slurm/
│   │   ├── __init__.py
│   │   ├── resources.py
│   │   ├── jobs.py
│   │   ├── sessions.py
│   │   └── experiment_run.py
│   └── environment/
│       ├── __init__.py
│       ├── runtime.py
│       └── identity.py
│
├── orchestra/
│   ├── __init__.py
│   ├── phases/
│   │   ├── __init__.py
│   │   ├── definitions.py
│   │   └── runner.py
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── invocations.py
│   │   └── subprocesses.py
│   ├── recovery/
│   │   ├── __init__.py
│   │   ├── state.py
│   │   └── resume.py
│   └── reporting/
│       ├── __init__.py
│       ├── health.py
│       └── status.py
│
├── config/                      # YAML/CSV assets, not a package
├── data/                        # market-data assets, not a package
├── cache/                       # generated cache, not a package
├── outputs/                     # generated experiment outputs, not a package
├── logs/                        # generated logs, not a package
├── baseline/                    # baseline evidence, not a package
├── scripts/                     # research, maintenance, and platform wrappers only
├── tests/
├── docs/
├── tools/
├── ci-scripts/                  # transitional; delete if no platform-only glue remains
└── pyproject.toml
```

The exact module filenames can adjust during migration when source-level dependencies reveal a cleaner boundary. The top-level package responsibilities and dependency direction should remain stable.

<!-- EXECUTION_BLUEPRINT_START -->
## Target execution architecture layouts

The target repository layout above describes ownership of code and state. The diagrams below describe **how humans, CI, Docker, Slurm/Triton, scripts, and package APIs execute that architecture**.

### Target scripts layout

Stable product/research operations should not require users to know deep Python module paths. Frequent supported operations move to package-owned CLI functions exposed through `pyproject.toml`. The steady-state `scripts/` tree is intentionally smaller:

```text
scripts/
├── compute/
│   └── slurm/                 # allocation, tmux/srun, login-node-safe wrappers only
├── research/
│   ├── audits/                # reproducible research/protocol audits
│   ├── benchmarks/            # performance/resource experiments
│   ├── experiment_runs/             # research-only experiment run analyses, not controllers
│   ├── strategy_checks/       # isolated thesis/strategy diagnostics
│   ├── thesis/
│   │   ├── evaluation/        # thesis-specific rescoring/figures
│   │   └── evidence/          # ledgers, indexes, report verification
│   └── frozen-launches/       # only launchers required to replay named historical evidence
├── maintenance/
│   ├── data-and-cache/        # explicit rebuild/repair operations
│   ├── artifacts/             # artifact migration/repair/promotion support
│   └── migrations/            # one-time schema/layout migrations with expiry criteria
└── compatibility/             # temporary forwarding wrappers; empty and removed in Phase 11
```

Steady state deliberately has no generic `matrix/`, `utility/`, `docker/`, `tests/`, `setup/`, or reusable `train/`/`eval/` implementation trees. Their reusable behavior moves to packages, engineering behavior moves to `tools/`, platform behavior moves under `scripts/compute/slurm/`, and declarative variant lists move to `config/`.

### Stable console-command surface

The exact executable prefix may be adjusted once during Phase 1, but the plan requires stable commands with these responsibilities:

```text
thesis-data       -> market_data.cli       # discover, prepare, validate, identify datasets
thesis-train      -> training.cli          # train/resume/benchmark supported training modes
thesis-evaluate   -> evaluation.cli        # evaluate, reanalyze, report, verify result packages
thesis-experiment-run   -> experiments.cli       # run, resume, status, summarize experiment runs
thesis-compute    -> compute.cli           # platform/resource inspection; no trading semantics
```

A command may have subcommands. The important contract is that Docker, Slurm wrappers, tests, docs, and users call these stable surfaces rather than deep implementation modules. Historical/frozen launchers may keep their original command text as evidence, but current launchers migrate.

### Current normal GitHub CI graph

The live `.github/workflows/ci.yml` was rechecked on 2026-10-30. It contains **13 jobs**: `dependency-lock`, `security-deps`, `security-secrets`, `quality`, `architecture`, `graph-quality`, `contracts`, `unit`, `build-smoke`, `integration`, `parity`, `training-smoke`, and `ci-success`. The checked-out graph is the baseline here; the target graph below is a proposal, not a description of current CI.

```text
PUSH / PULL REQUEST
└─ dependency-lock
   ├─ security-deps
   ├─ security-secrets
   ├─ quality
   ├─ architecture
   ├─ graph-quality
   ├─ contracts
   ├─ unit
   ├─ build-smoke
   ├─ integration    [architecture, contracts, unit]
   ├─ parity         [architecture, contracts, unit]
   ├─ training-smoke [integration, parity, build-smoke]
   └─ ci-success     [aggregates all 12 preceding gates]
```

The workflow has an explicit required-job aggregator and explicit architecture, contracts, parity, security, and graph-quality jobs. `graph-quality` separately installs the graph analyzer and checks graph-resolution thresholds. Keep these current facts separate from proposed target-graph simplification below.

### Target normal GitHub CI graph

Normal `ci.yml` contains **12 required validation jobs plus one final aggregator**: nine semantic validation jobs and three assurance gates. The nine semantic jobs are the stable architecture target; the assurance gates remain separate because they cover distinct security and graph-quality properties. Any later consolidation requires an explicit coverage-equivalence check and branch-protection review.

```text
PUSH / PULL REQUEST
└─ dependency-lock
   ├─ security-deps
   ├─ security-secrets
   ├─ quality
   ├─ architecture
   ├─ graph-quality
   ├─ contracts
   ├─ unit
   ├─ build-smoke
   ├─ integration    [architecture, contracts, unit]
   ├─ parity         [architecture, contracts, unit]
   ├─ training-smoke [integration, parity, build-smoke]
   └─ ci-success     [aggregates all 12 required validation/assurance gates]
```

Target job contracts:

| Job | Required property | Canonical local gate | Must not require |
|---|---|---|---|
| `dependency-lock` | lockfile/pin/project metadata consistency | `tools/check deps` | external data, Docker, GPU |
| `quality` | Ruff format + Ruff lint + mypy across every first-class package | `tools/check quality` | Docker/GPU |
| `architecture` | public imports, dependency direction, naming, script/entry-point ownership | `tools/check architecture` | research data |
| `contracts` | config/artifact/cache/lifecycle/schema/repository-hygiene contracts | `tools/check contracts` | mutable repository outputs |
| `unit` | deterministic isolated unit tests | `tools/check unit` | network, external datasets, GPU |
| `build-smoke` | wheel build, clean install/import, console-entry discovery | `tools/check build` | Docker/GPU |
| `integration` | deterministic cross-package/I/O behavior on fixtures | `tools/check integration` | mutable research checkout state |
| `parity` | execution/data/schema equivalence contracts | `tools/check parity` | GPU unless explicitly marked |
| `training-smoke` | tiny CPU training -> checkpoint -> evaluation/artifact roundtrip | `tools/check training-smoke` | thesis-scale data/runtime |
| `security-deps` | dependency vulnerability/policy audit | `tools/check security-deps` | GPU or mutable research outputs |
| `security-secrets` | tracked and baseline secret scan | `tools/check security-secrets` | external datasets or GPU |
| `graph-quality` | graph extraction and critical-edge resolution thresholds | `tools/check graph-quality` | training data or GPU |
| `ci-success` | required-job aggregation for branch protection | no separate logic | new checks of its own |

`security-deps`, `security-secrets`, `quality`, `architecture`, `graph-quality`, `contracts`, `unit`, and `build-smoke` may run in parallel after dependency consistency. `integration` and `parity` begin only after the structural/unit prerequisites they rely on. `training-smoke` is the final behavioral CPU gate. Branch protection targets only `ci-success`, while that aggregator depends on all twelve required validation and assurance gates.

### Current-to-target CI migration

| Live job(s), checked 2026-10-30 | Target | Decision |
|---|---|---|
| `dependency-lock` | `dependency-lock` | Already matches target; owns lock/pin consistency. |
| `quality` | `quality` | Already matches target; keep Ruff and full-tree Mypy together. |
| `architecture` | `architecture` | Already matches target; own import/dependency/naming/execution-surface checks. |
| `contracts` | `contracts` | Already matches target; own config/artifact/cache/lifecycle/repository contracts. |
| `unit` | `unit` | Already matches target; retain one canonical CPU unit gate unless another environment is a support contract. |
| `build-smoke` | `build-smoke` | Already matches target; build/install/import/entry-point smoke. |
| `integration`, `parity`, `training-smoke` | same named gates | Already match the semantic target and dependency order. |
| `security-deps`, `security-secrets` | independent assurance gates | Retain as visible required gates; their threat checks should not disappear into a generic quality or contract result. |
| `graph-quality` | independent assurance gate | Retain while it builds and verifies the repository graph with critical-resolution thresholds; consolidate only after architecture-gate equivalence and diagnostics are demonstrated. |
| Docker build/test jobs from the superseded 15-job graph | Tier C `docker-smoke` only if Docker remains a supported deliverable | Do not count these as live jobs; decide lifecycle in Phase 9 from actual package/runtime consumers. |

### Validation tier graph

```text
source change
    │
    ├── Tier A: fast CPU / every PR
    │      dependency-lock -> quality + architecture + contracts + unit + build-smoke
    │
    ├── Tier B: deterministic CPU / normal CI
    │      integration + parity -> training-smoke
    │
    ├── Tier C: scheduled/manual exhaustive
    │      slow + research-scale deterministic checks + docker-smoke + larger reanalysis
    │
    └── Tier D: Triton/GPU/Slurm
           gpu -> short accelerator training -> checkpoint/evaluation roundtrip
               -> resource/vector-env checks -> experiment run dry-run/resume/recovery
               -> structured Triton gate artifact
```

Tier D is not represented as passed by GitHub-hosted CPU runners. It is executed on Triton/GPU infrastructure through `tools/check gpu` / `tools/check triton` plus thin Slurm wrappers. A future GitHub workflow may dispatch it only if a secure, intentional runner/bridge is introduced; the architecture does not assume one.

### Target CI / engineering layout

```text
.github/
└── workflows/
    ├── ci.yml                  # 9 semantic + 3 assurance gates; ci-success aggregator
    ├── nightly.yml             # Tier C slow/research/docker-smoke
    └── release.yml             # only if publishing remains an intentional deliverable

tools/
├── check                       # canonical named-gate dispatcher
├── test                        # targeted pytest convenience; delegates marker semantics
├── build                       # clean wheel/install/import verification
├── clean                       # safe generated-state cleanup
├── bootstrap                   # developer environment setup if still required
└── ...                         # graph/lint helper wrappers with one responsibility

ci-scripts/                     # transitional only
└── <platform-only glue>        # keep only if GitHub cannot express it cleanly; otherwise delete dir

pyproject.toml
├── project.scripts             # stable package-owned console commands
├── pytest markers              # unit/integration/slow/gpu/triton/research
├── Ruff scope                  # every first-class package + supported scripts/tests
└── mypy scope                  # every first-class package
```

The Makefile remains for lock export/maintenance and short aliases only. Docker Compose invokes stable commands. It does not own an independent test/training architecture.

### CLI/scripts/tools/Docker/Slurm/CI -> package API execution flow

```text
                         HUMAN / AUTOMATION
                                 │
         ┌──────────────┬────────┼──────────┬───────────────┐
         ▼              ▼        ▼          ▼               ▼
 stable console CLI   research  tools/check Docker       Slurm/Triton
                      scripts                 │               wrappers
         │              │        │           │               │
         └──────────────┴────────┴───────────┴───────────────┘
                                 │
                                 ▼
                        PUBLIC PACKAGE APIs
                                 │
      ┌──────────────┬───────────┼────────────┬──────────────┐
      ▼              ▼           ▼            ▼              ▼
 market_data/features trading simulation   training      evaluation
      │              │           │            │              │
      └──────────────┴───────────┴────────────┴──────────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
                experiments                 live
                    │                         │
                    ▼                         ▼
                  compute                integrations
                    │
                    ▼
          canonical artifact lifecycle
```

GitHub Actions is an outer scheduler for `tools/check`; Docker is an environment; Slurm is a resource scheduler. None owns domain algorithms.

### Migration phase dependency/order graph

The numbered phases remain the review/acceptance order, but the dependency graph explains what can be prepared in parallel without violating ownership:

```text
Phase 0  freeze contracts / inventory
   │
   ▼
Phase 1  configuration + artifacts + root API foundations
   │
   ├──────────────> Phase 4  market_data + features ───────┐
   │                                                       │
   ▼                                                       │
Phase 2  trading ─────> Phase 3 simulation ────────────────┤
                                                           ▼
                                                    Phase 5 models + training
                                                           │
                                                           ▼
                                                    Phase 6 evaluation
                                                           │
                                                           ▼
                                                    Phase 7 experiments + compute
                                                           │
Phase 2 trading ───────────────┐                            │
Phase 5 models/training ───────┼──> Phase 8 live/integrations
                               │                            │
                               └──────────────┬─────────────┘
                                              ▼
                                Phase 9 Orchestra + execution surfaces
                                              │
                                              ▼
                                Phase 10 repository-state normalization
                                              │
                                              ▼
                                Phase 11 remove compatibility + final verify
```

No phase may delete a legacy path before all producers, consumers, saved launch surfaces, tests, and historical-artifact readers that depend on it have migrated or received an explicit compatibility adapter.

<!-- EXECUTION_BLUEPRINT_END -->

## Package ownership

### `configuration`

Owns shared configuration loading, schema/version handling, deterministic merge/override resolution, validation, canonical serialization/hashing, and historical compatibility. It consumes assets from `config/` but is itself importable code.

It must remain independent of training/evaluation orchestration so the same resolved configuration semantics are usable by training, evaluation, experiments, live, and tooling.

### `artifacts`

Owns cross-cutting generated-artifact identity, layouts, manifests, atomic writes/promotions, retention metadata, and provenance links.

It does not define training metrics, evaluation statistics, feature values, or experiment run semantics; those remain with their domain packages.

### `market_data`

Owns bar/tick ingestion, market dataset identity, resampling/alignment, session labeling, split definitions, and bar/tick cache identity.

Does not own indicators, strategy semantics, risk, or model training.

### `features`

Owns causal feature construction, technical indicators, swings/structure, PO3/FVG/IFVG feature state, liquidity/session context, train-scoped normalization, feature schemas, and feature-cache identity.

Does not own order execution, trading account state, or model fitting.

### `trading`

Owns pure trading-domain rules and state: account state/accounting, selectable trading policies, risk budgets, sizing, orders, stops/targets, execution-cost/fill models, position state/management, and strategy semantics.

It must be usable by simulation, evaluation, and live paths without importing training code.

### `simulation`

Owns offline runtime mechanics: Gymnasium environment, action/observation/result contracts, reset/step sequencing, reward-input orchestration, sessions, standalone backtesting, and environment/backtest parity.

It depends on `trading`, `market_data`, and `features`.

### `models`

Owns model factories, encoders, PPO/SAC/recurrent policies, checkpoints, and auxiliary neural components.

### `training`

Owns model-fitting composition: configuration resolution, data/feature/environment/model setup, callbacks, one-seed training, checkpoint writing, manifests, and aggregation.

### `evaluation`

Is the single canonical evaluation package. It owns rollout, metrics, statistical analysis, checkpoint reanalysis, provenance, export, and plotting.

### `experiments`

Owns variant resolution, experiment run configuration/state, checkpoint discovery/resume, validation, worker construction, provenance, and experiment run reporting.

### `live`

Owns broker-neutral live/paper trading runtime.

### `integrations`

Owns external-system adapters. MT5-specific I/O, connections, data adapters, and order routing live under `integrations.mt5`.

### `compute`

Owns reusable compute-platform mechanics: Slurm resources/jobs/sessions, runtime environment identity, and experiment run compute dispatch.

### `orchestra`

Remains a separate top-level package for coding-agent orchestration and does not import thesis trading semantics.

## Public import model

The repository should teach its own architecture through imports.

Typical imports should look like:

```python
from market_data import TickBook, load_market_data
from features import build_features
from trading import AccountState, TradingPolicy
from trading.risk import RiskBudget, approve_risk
from simulation import TradingEnv
from simulation.backtest import run_backtest
from models import build_agent, load_checkpoint
from training import run_training
from evaluation import calculate_metrics, evaluate_model
from experiments import resolve_variant
from experiments.runs import run_experiment
from integrations.mt5 import MT5Connection, MT5Trader
```

A caller should not need to know which implementation file contains a stable domain contract.

## `__init__.py` contract

Every importable package and subpackage must have an intentional `__init__.py`.

Example:

```python
# trading/risk/__init__.py
"""Risk approval and position-sizing contracts."""

from .budget import RiskBudget, approve_risk
from .sizing import PositionSize, compute_position_size

__all__ = [
    "PositionSize",
    "RiskBudget",
    "approve_risk",
    "compute_position_size",
]
```

Rules:

1. Include a one- or two-sentence ownership docstring.
2. Re-export only stable symbols intended for callers.
3. Define `__all__` when it clarifies the supported API.
4. Do not place implementation logic in `__init__.py`.
5. Do not trigger model loading, file I/O, data loading, logging setup, or runtime initialization from package import.
6. Internal modules may import sibling implementation modules directly.
7. Cross-package callers should prefer the owning package API.
8. Deep imports are allowed only for explicitly public specialized contracts.
9. Package import tests must verify the supported surface.

## Dependency direction

Preferred dependency flow:

`configuration` and `artifacts` are foundational infrastructure. Domain packages may depend on them, but they must not depend upward on training, evaluation, experiments, live, or scripts.

```text
configuration ──────────────────────────────────────────────┐
artifacts ──────────────────────────────────────────────────┤
                                                            │
market_data ──────┐
                  ├──> features
                  │
                  └──────────────┐
                                 v
trading ───────────────────> simulation
                                 │
simulation contracts ───────> models
                                 │
market_data/features/trading ─> training
                                 │
models/simulation/trading ────> evaluation
                                 │
training/evaluation ──────────> experiments
                                 │
trading/models ───────────────> live
trading/live ─────────────────> integrations

compute <──── experiments/scripts
orchestra     independent engineering toolchain
```

Hard rules:

- `configuration` imports no training/evaluation/experiment/live orchestration.
- `artifacts` imports no domain-specific training/evaluation/experiment implementations.
- `market_data` never imports `features`, `trading`, `training`, or `evaluation`.
- `features` never imports `training`, `evaluation`, or live/broker code.
- `trading` never imports `training`, `evaluation`, `experiments`, or scripts.
- `simulation` never imports `training`, `evaluation`, or scripts.
- `models` may depend on simulation contracts but not on training orchestration.
- `training` composes upstream packages but must not become the owner of domain equations.
- `evaluation` consumes trained models and simulation/trading contracts; it never performs model fitting.
- `experiments` orchestrates runs but contains no trading equations or feature calculations.
- `live` is broker-neutral.
- `integrations` adapts external systems and must not duplicate trading policy/risk equations.
- production packages never import from `scripts`.
- reusable code never lives only inside `scripts`.
- `orchestra` remains outside the research dependency graph.

## Trading environment decomposition

The current environment class is the most urgent migration because it combines almost the entire simulator.

### `simulation.environment`

Owns the Gymnasium facade, constructor wiring, reset, top-level step ordering, observation/reward coordination, and info/result assembly.

Target: a comprehensible facade/runtime, with no single orchestration function above roughly 250 lines unless there is a strong reason.

### `simulation.contracts`

Owns action schemas, observation schemas, result/event interfaces, and compatibility metadata shared with models/checkpoints.

### `trading.risk`

Extract sizing equity, requested/approved risk, daily/account capacity, execution reserve, lot sizing, and risk diagnostics.

### `trading.positions`

Extract SL/TP evaluation, multi-TP partial closes, breakeven, trailing stop, TP progression, and position exits.

### `trading.orders`

Extract structural entry candidates, stop/target menus, selection repair, and order intents.

### `trading.execution`

Own deterministic fill/cost semantics shared by environment, backtest, and live adapters where behavior is truly identical.

After extraction, environment step sequencing should read as explicit stages:

```text
advance market
→ update open position
→ apply exits
→ enforce account constraints
→ process payout transition
→ decode action
→ evaluate entry
→ execute accepted order
→ update reward/account
→ build observation/info
→ resolve termination/truncation
```

## Training decomposition

The training entry point becomes a thin composition root.

Move responsibilities into:

- `training.configuration` for training-specific option interpretation only; shared YAML loading/merging/schema/hash behavior belongs to root `configuration`;
- `training.setup.observation_memmap` and `training.setup.tick_execution_preflight`;
- `training.setup.environments`;
- `training.setup.model_state` for value-head initialization and constrained resume validation;
- `training.setup.policy_diagnostics` for effective optimizer and architecture provenance reporting;
- `training.setup.callbacks`;
- `training.runner`;
- `training.artifacts`.

The CLI wrapper under `scripts/train/` calls `training.run_training()`.

## Feature-pipeline decomposition

`features` exposes one stable facade:

```python
from features import build_features
```

Internally:

```text
base indicators
→ session/context
→ higher-timeframe alignment
→ structure/liquidity
→ PO3/FVG/IFVG
→ strategy state
→ premium/discount context
→ train-scoped normalization
→ schema/order validation
→ cache persistence
```

Every stage documents required inputs, produced columns, configuration gate, decision-time availability, and cache-identity inputs.

## Backtest and environment parity

The backtest loop belongs under `simulation.backtest`.

Shared deterministic mechanics belong in `trading`. Orchestration can remain separate where lifecycle semantics differ.

Parity requirements include identical cost model, stop/TP semantics, multi-TP accounting, risk budget where configured identically, tick/bar fill contract, and explicit tests for intentional differences.

A dedicated `simulation.parity` package owns fixed traces and assertions.

## Evaluation unification

All reusable evaluation code moves into the single top-level `evaluation/` package.

Subpackages:

- `rollout`;
- `metrics`;
- `reanalysis`;
- `reporting`;
- `plotting`.

Static and interactive plots share semantic data transforms, not renderer-specific drawing code.

Old evaluation paths remain compatibility shims only during migration.

## Experiment run and experiment architecture

Reusable matrix/thesis experiment run logic moves into `experiments`.

`experiments.variants` owns variant resolution and registry.

`experiments.runs` owns experiment run lifecycle, checkpoint mapping, resume logic, run validation, worker commands, and experiment run summaries.

`experiments.provenance` owns source/artifact identity and reproducibility records.

Slurm mechanics belong to `compute.slurm`, not experiment-domain code.

## Live and MT5 architecture

Broker-neutral live logic moves into `live`.

Broker-specific implementation moves into `integrations.mt5`.

Boundary:

```text
trading policy/risk
        ↓
live runtime
        ↓
integration adapter
        ↓
external terminal/broker
```

## Script migration architecture

Scripts are not libraries.

Examples:

```text
scripts/train/run_training.py
    -> training.run_training()

scripts/eval/reanalyze.py
    -> evaluation.reanalysis.reanalyze_checkpoint()

experiments/runs/execution.py
    -> experiments.runs.run_experiment()

experiments/runs/status.py
    -> experiments.runs reporting + compute.slurm status
```

Do not add `__init__.py` throughout `scripts/` to legitimize reusable imports. Move reusable logic into a top-level package.

Steady-state script acceptance:

- no reusable experiment_run/data/training/evaluation implementation remains under `scripts/`;
- no generic `matrix/`, `utility/`, `docker/`, `tests/`, or `setup/` category survives solely for historical convenience;
- every retained research script declares the package APIs/artifacts it consumes and produces;
- every retained Slurm shell wrapper contains resource/environment orchestration only;
- every compatibility wrapper has an expiry condition and is removed in Phase 11;
- declarative variant/resource lists live under `config/`, not `scripts/`.

<!-- SCRIPT_LEDGER_START -->
## Current script migration ledger

The pre-refactor audit counted **152 regular files under `scripts/`**, excluding `__pycache__`; the earlier steady-state estimate of **116 files** was a target estimate, not a verified live count. A direct 2026-10-30 scan finds **149 regular files plus 9 compatibility symlinks**, excluding `__pycache__`. The ledger below is reconciled to those 158 live paths; removed obsolete paths are recorded in the progress note, not presented as current files. It records each retained wrapper's owner and disposition; moved package commands remain listed where their compatibility lifecycle matters.

| Current path | Target class | Target owner/location | Migration action |
|---|---|---|---|
| `scripts/research/benchmarks/measure_env_memory.py` | research command | `scripts/research/benchmarks/` | Keep thin; extract reusable benchmark/resource logic to owning packages. |
| `scripts/research/benchmarks/measure_ppo_throughput.py` | research command | `scripts/research/benchmarks/` | Keep thin; extract reusable benchmark/resource logic to owning packages. |
| `scripts/research/benchmarks/measure_shared_ppo_memory.py` | research command | `scripts/research/benchmarks/` | Keep thin; extract reusable benchmark/resource logic to owning packages. |
| `scripts/research/benchmarks/parse_stages_bench.py` | research command | `scripts/research/benchmarks/` | Keep thin; extract reusable benchmark/resource logic to owning packages. |
| `scripts/research/benchmarks/run_fps_probe.sh` | research command | `scripts/research/benchmarks/` | Keep thin; extract reusable benchmark/resource logic to owning packages. |
| `scripts/research/benchmarks/run_stages_benchmark.sh` | research command | `scripts/research/benchmarks/` | Keep thin; extract reusable benchmark/resource logic to owning packages. |
| `market_data/commands/discover.py` | compatibility wrapper | `market_data CLI + stable console command` | Move implementation to market_data; delete wrapper in Phase 11 after callers migrate. |
| `market_data/commands/prepare.py` | compatibility wrapper | `market_data CLI + stable console command` | Move implementation to market_data; delete wrapper in Phase 11 after callers migrate. |
| `scripts/research/thesis/evaluation/defense_figures.py` | research command | `scripts/research/thesis/evaluation/` | Keep reproducible analysis thin; consume evaluation artifacts/APIs. |
| `scripts/research/thesis/evaluation/deflated_sharpe_family.py` | research command | `scripts/research/thesis/evaluation/` | Keep reproducible analysis thin; consume evaluation artifacts/APIs. |
| `scripts/research/thesis/evaluation/probe_seed50_opens.py` | research command | `scripts/research/thesis/evaluation/` | Keep reproducible analysis thin; consume evaluation artifacts/APIs. |
| `scripts/research/thesis/evaluation/report_ablations.py` | research command | `scripts/research/thesis/evaluation/` | Keep reproducible analysis thin; consume evaluation artifacts/APIs. |
| `scripts/research/thesis/evaluation/report_g3.py` | research command | `scripts/research/thesis/evaluation/` | Keep reproducible analysis thin; consume evaluation artifacts/APIs. |
| `scripts/research/thesis/evaluation/run_baseline_eval.py` | compatibility wrapper | `evaluation CLI/public API` | Move reusable evaluation semantics to evaluation; retire deep script entry point. |
| `scripts/research/thesis/evaluation/score_rule_baselines.py` | compatibility wrapper | `evaluation CLI/public API` | Move reusable evaluation semantics to evaluation; retire deep script entry point. |
| `scripts/research/thesis/evaluation/test_oos.py` | compatibility wrapper | `evaluation CLI/public API` | Move reusable evaluation semantics to evaluation; retire deep script entry point. |
| `experiments/variants/runner.py` | compatibility wrapper | `experiments CLI/public API` | Lifecycle is owned by `variant_ablation_runner.py`; CLI parsing is stable in `experiments.cli`; retain the thin old import/module facade until Phase 11 gates pass. |
| `scripts/research/experiment_runs/analyze_experiment_runstime_scaling.py` | research command | `scripts/research/experiment_runs/` | Keep audit/report command thin; move reusable experiment_run/artifact logic to packages. |
| `scripts/research/experiment_runs/audit_experiment_run_checkpoint_loads.py` | research command | `scripts/research/experiment_runs/` | Keep audit/report command thin; move reusable experiment_run/artifact logic to packages. |
| `scripts/research/experiment_runs/audit_experiment_run_source_fidelity.py` | research command | `scripts/research/experiment_runs/` | Keep audit/report command thin; move reusable experiment_run/artifact logic to packages. |
| `scripts/research/experiment_runs/audit_real_market_bundle_parity.py` | research command | `scripts/research/experiment_runs/` | Keep audit/report command thin; move reusable experiment_run/artifact logic to packages. |
| `scripts/research/experiment_runs/audit_real_market_feature_prefix_causality.py` | research command | `scripts/research/experiment_runs/` | Keep audit/report command thin; move reusable experiment_run/artifact logic to packages. |
| `scripts/research/experiment_runs/audit_variant_spaces.py` | research command | `scripts/research/experiment_runs/` | Keep audit/report command thin; move reusable experiment_run/artifact logic to packages. |
| `experiments/runs/checkpoints.py` | compatibility wrapper | `experiments.provenance/public API` | Move lineage semantics into experiments; retain only command adapter during migration. |
| `experiments/runs/execution.py` | lifecycle service | `experiments CLI/public API` | Own the canonical experiment run composition root. |
| `scripts/maintenance/migrations/migrate_preflight_experiment_run.py` | maintenance command | `scripts/maintenance/migrations/` | Use package APIs and artifact transactions; keep only migration/repair orchestration. |
| `scripts/maintenance/data-and-cache/rebuild_named_prebuilt_feature_caches.py` | maintenance command | `scripts/maintenance/data-and-cache/` | Use package APIs and artifact transactions; keep only migration/repair orchestration. |
| `scripts/maintenance/data-and-cache/rebuild_prebuilt_baseline_cache.py` | maintenance command | `scripts/maintenance/data-and-cache/` | Use package APIs and artifact transactions; keep only migration/repair orchestration. |
| `scripts/maintenance/data-and-cache/rebuild_full_period_data_cache.py` | maintenance command | `scripts/maintenance/data-and-cache/` | Use market-data/features/artifact APIs; preserve immutable cache identity and provenance. |
| `config/experiment_runs/resource_profile_a0_variant_list.txt` | config asset | `config/experiments or config/experiment_runs` | Move declarative list out of scripts; update every launcher/config reference. |
| `scripts/compute/slurm/experiment_runs/run_18variant_matrix.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_18variant_matrix_gh200_tmux.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_18variant_matrix_tmux.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_2variant_node.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_18way_cpumask_allocation.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_18way_cpumask_supervisor.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_18way_finalization_allocation.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_18way_full_split_allocation.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_18way_full_split_supervisor.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_18way_migration_allocation.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_18way_migration_supervisor.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_18way_supervisor.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_18way_two_node_allocation.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_18way_two_node_supervisor.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_18way_vector_resume_allocation.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_18way_vector_resume_supervisor.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_3way_allocation.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_3way_prebuilt_allocation.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_3way_prebuilt_supervisor.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_3way_shared_bundle_n64_allocation.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_3way_shared_bundle_n64_supervisor.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_3way_supervisor.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_allocation.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_replacement_experiment_run_allocation.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_replacement_experiment_run_supervisor.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_rq1_pair_allocation.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_rq1_pair_supervisor.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/experiment_runs/run_rr_two_gpu_tmux.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `experiments/runs/reporting.py` | research command | `scripts/research/experiment_runs/` | Keep audit/report command thin; move reusable experiment_run/artifact logic to packages. |
| `experiments/runs/orchestration.py` | compatibility wrapper | `experiments CLI/public API` | Extract controller/state/orchestration into experiments; wrapper disappears after stable CLI adoption. |
| `scripts/compute/slurm/experiment_runs/validate_cpu_mask_experiment_run_gpu.sh` | platform/Slurm wrapper | `scripts/compute/slurm/experiment_runs/` | Keep shell wrapper thin; move experiment_run/resource decisions to experiments/compute. |
| `scripts/compute/slurm/verify_worker_cpu_affinity.py` | platform/Slurm wrapper | `scripts/compute/slurm/` | Move reusable resource inspection to compute; wrapper invokes it. |
| `scripts/research/audits/audit_candidate_holdout_archive_exposure.py` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `scripts/research/audits/audit_candidate_holdout_repository_exposure.py` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `scripts/research/audits/audit_missing_m1_tick_reconstruction.py` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `scripts/research/audits/audit_replacement_fold_fit.py` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `scripts/research/audits/audit_replacement_m1_quality.py` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `scripts/research/audits/audit_replacement_partition_integrity.py` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `scripts/research/audits/audit_replacement_schedule_shape.py` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `scripts/research/audits/audit_replacement_tick_quality.py` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `scripts/research/audits/audit_rq1_candidate_config.py` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `scripts/research/audits/audit_seed50_screen_report_recoverability.py` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `scripts/research/audits/audit_tick_cache_timeline.py` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `scripts/research/audits/audit_tick_execution_coverage.py` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `scripts/research/audits/audit_tick_tie_policy.py` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `scripts/research/audits/fingerprint_tick_decision_schedule.py` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `scripts/maintenance/data-and-cache/rebuild_full_period_data_cache.py` | maintenance command | `scripts/maintenance/data-and-cache/` | Use market_data/features/artifacts APIs; keep only explicit maintenance orchestration. |
| `scripts/research/audits/render_idea12_synthetic_figures.py` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `scripts/research/audits/run_18_feature_cache_mapping_gate.sh` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `scripts/maintenance/data-and-cache/run_18_feature_cache_rebuild.sh` | maintenance command | `scripts/maintenance/data-and-cache/` | Use market_data/features/artifacts APIs; keep only explicit maintenance orchestration. |
| `scripts/research/audits/run_candidate_holdout_archive_audit_gate.sh` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `scripts/maintenance/data-and-cache/run_full_period_data_and_feature_cache_rebuild.sh` | maintenance command | `scripts/maintenance/data-and-cache/` | Use market_data/features/artifacts APIs; keep only explicit maintenance orchestration. |
| `scripts/research/audits/run_observation_schema_gate.sh` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `scripts/research/frozen-launches/freeze_tick_decision_schedule.sh` | frozen historical launcher | `scripts/research/frozen-launches/` | Preserve the P1 launcher bytes and artifacts; its old audit path is a compatibility symlink, not a current check. |
| `scripts/research/frozen-launches/validate_tick_fold_scope.sh` | frozen historical launcher | `scripts/research/frozen-launches/` | Preserve the P1 launcher bytes and old architecture-specific environment; its former P1 path is an alias. |
| `scripts/research/frozen-launches/validate_tick_data_quality.sh` | frozen historical launcher | `scripts/research/frozen-launches/` | Preserve the P1 launcher bytes and historical full-suite protocol; its former P1 path is an alias. |
| `scripts/research/frozen-launches/smoke_test_checkpoint_recovery.sh` | frozen historical launcher | `scripts/research/frozen-launches/` | Preserve the P3 recovery-launch protocol; its former P3 path is an alias. |
| `scripts/research/audits/run_rq1_candidate_preflight_gate.sh` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `scripts/research/audits/run_tick_tie_policy_gate.sh` | research command | `scripts/research/audits/` | Preserve reproducible research gate; extract reusable validation primitives to owners. |
| `tools/setup-oasis-agents` | engineering wrapper | `tools/bootstrap or tools/orchestra helper` | Move developer setup out of research scripts; delete old path after docs/callers migrate. |
| `tools/setup-orchestra-view` | engineering wrapper | `tools/bootstrap or tools/orchestra helper` | Move developer setup out of research scripts; delete old path after docs/callers migrate. |
| `tools/setup-venv` | engineering wrapper | `tools/bootstrap or tools/orchestra helper` | Move developer setup out of research scripts; delete old path after docs/callers migrate. |
| `tools/setup-venv-mi210` | engineering wrapper | `tools/bootstrap or tools/orchestra helper` | Move developer setup out of research scripts; delete old path after docs/callers migrate. |
| `tools/setup-venv-x86` | engineering wrapper | `tools/bootstrap or tools/orchestra helper` | Move developer setup out of research scripts; delete old path after docs/callers migrate. |
| `scripts/research/strategy_checks/edge_harness.py` | research command | `scripts/research/strategy_checks/` | Keep experiment-specific analysis thin; move shared feature/evaluation logic to owners. |
| `scripts/research/strategy_checks/ema_tp_replay.py` | research command | `scripts/research/strategy_checks/` | Keep experiment-specific analysis thin; move shared feature/evaluation logic to owners. |
| `scripts/research/strategy_checks/entry_edge_check.py` | research command | `scripts/research/strategy_checks/` | Keep experiment-specific analysis thin; move shared feature/evaluation logic to owners. |
| `scripts/research/strategy_checks/eval_seed_variance.py` | research command | `scripts/research/strategy_checks/` | Keep experiment-specific analysis thin; move shared feature/evaluation logic to owners. |
| `scripts/research/strategy_checks/ifvg_chain_check.py` | research command | `scripts/research/strategy_checks/` | Keep experiment-specific analysis thin; move shared feature/evaluation logic to owners. |
| `scripts/research/strategy_checks/plot_ifvg_chain_trades.py` | research command | `scripts/research/strategy_checks/` | Keep experiment-specific analysis thin; move shared feature/evaluation logic to owners. |
| `scripts/research/strategy_checks/pre_ny_bias_check.py` | research command | `scripts/research/strategy_checks/` | Keep experiment-specific analysis thin; move shared feature/evaluation logic to owners. |
| `scripts/research/strategy_checks/sweep_displacement_check.py` | research command | `scripts/research/strategy_checks/` | Keep experiment-specific analysis thin; move shared feature/evaluation logic to owners. |
| `scripts/research/thesis/evidence/analyze_paired_seed_results.py` | research command | `scripts/research/thesis/evidence/` | Keep evidence assembly/verification reproducible; use canonical artifacts/evaluation APIs. |
| `scripts/research/thesis/evidence/audit_checkpoint_frame_bundle_parity.py` | research command | `scripts/research/thesis/evidence/` | Keep evidence assembly/verification reproducible; use canonical artifacts/evaluation APIs. |
| `scripts/research/thesis/evidence/build_experiment_run_evidence_index.py` | research command | `scripts/research/thesis/evidence/` | Keep evidence assembly/verification reproducible; use canonical artifacts/evaluation APIs. |
| `scripts/research/thesis/evidence/build_experiment_run_trial_ledger.py` | research command | `scripts/research/thesis/evidence/` | Keep evidence assembly/verification reproducible; use canonical artifacts/evaluation APIs. |
| `scripts/research/thesis/evidence/build_seed50_screen_finding_cards.py` | research command | `scripts/research/thesis/evidence/` | Keep evidence assembly/verification reproducible; use canonical artifacts/evaluation APIs. |
| `scripts/research/thesis/evidence/compare_deterministic_reanalysis.py` | research command | `scripts/research/thesis/evidence/` | Keep evidence assembly/verification reproducible; use canonical artifacts/evaluation APIs. |
| `scripts/research/thesis/evidence/reconcile_experiment_run_attempts.py` | research command | `scripts/research/thesis/evidence/` | Keep evidence assembly/verification reproducible; use canonical artifacts/evaluation APIs. |
| `scripts/research/thesis/evidence/verify_numerical_report.py` | research command | `scripts/research/thesis/evidence/` | Keep evidence assembly/verification reproducible; use canonical artifacts/evaluation APIs. |
| `scripts/research/thesis/evidence/verify_result_manifest.py` | research command | `scripts/research/thesis/evidence/` | Keep evidence assembly/verification reproducible; use canonical artifacts/evaluation APIs. |
| `scripts/research/benchmarks/compare_encoders.py` | research command | `scripts/research/benchmarks/` | Use training/evaluation APIs; preserve comparison protocol, not duplicate setup logic. |
| `training/runner/lstm_baseline.py` | compatibility wrapper | `training CLI/public API` | Move reusable training implementation to training; retire script entry point. |
| `scripts/research/frozen-launches/train_one_variant.sh` | research/platform wrapper | `scripts/research/frozen-launches or scripts/compute/slurm/` | Move semantics to config + training CLI; retain only if needed to replay a named experiment. |
| `scripts/research/frozen-launches/train_rr_idea1.sh` | research/platform wrapper | `scripts/research/frozen-launches or scripts/compute/slurm/` | Move semantics to config + training CLI; retain only if needed to replay a named experiment. |
| `scripts/research/frozen-launches/train_rr_idea2.sh` | research/platform wrapper | `scripts/research/frozen-launches or scripts/compute/slurm/` | Move semantics to config + training CLI; retain only if needed to replay a named experiment. |
| `training/runner/vae.py` | compatibility wrapper | `training CLI/public API` | Move reusable training implementation to training; retire script entry point. |
| `docs/operations/triton/README.md` | documentation | `docs/operations/triton/` | Move operational documentation to docs; keep command references current. |
| `scripts/compute/slurm/activate_venv.sh` | platform/Slurm wrapper | `scripts/compute/slurm/` | Keep allocation/shell mechanics thin; invoke compute/experiments APIs. |
| `scripts/compute/slurm/attach_or_alloc.sh` | platform/Slurm wrapper | `scripts/compute/slurm/` | Keep allocation/shell mechanics thin; invoke compute/experiments APIs. |
| `scripts/compute/slurm/experiment_run_allocation_wrapper.sh` | platform/Slurm wrapper | `scripts/compute/slurm/` | Keep allocation/shell mechanics thin; invoke compute/experiments APIs. |
| `scripts/compute/slurm/experiment_run_git_identity.sh` | platform/Slurm wrapper | `scripts/compute/slurm/` | Keep allocation/shell mechanics thin; invoke compute/experiments APIs. |
| `scripts/compute/slurm/experiment_run_recovery_supervisor.sh` | platform/Slurm wrapper | `scripts/compute/slurm/` | Keep allocation/shell mechanics thin; invoke compute/experiments APIs. |
| `scripts/compute/slurm/experiment_run_srun_gh200_guard.sh` | platform/Slurm wrapper | `scripts/compute/slurm/` | Keep allocation/shell mechanics thin; invoke compute/experiments APIs. |
| `scripts/compute/slurm/worker_bin/srun` | platform/Slurm wrapper | `scripts/compute/slurm/` | Keep allocation/shell mechanics thin; invoke compute/experiments APIs. |
| `compute/slurm/worker_dispatch.py` | compatibility wrapper | `compute CLI/public API` | Extract reusable Slurm/resource/recovery behavior to compute; keep thin adapter temporarily. |
| `compute/slurm/capacity.py` | compatibility wrapper | `compute CLI/public API` | Extract reusable Slurm/resource/recovery behavior to compute; keep thin adapter temporarily. |
| `scripts/compute/slurm/find_gpu_session.sh` | platform/Slurm wrapper | `scripts/compute/slurm/` | Keep allocation/shell mechanics thin; invoke compute/experiments APIs. |
| `market_data/commands/prebuild_experiment_run_cache.py` | compatibility wrapper | `market_data + experiments/compute API` | Move cache semantics to market_data/artifacts; orchestration to experiments/compute. |
| `experiments/runs/cache_failure_recovery.py` | lifecycle service | `experiments CLI/public API` | Own cache recovery and expose it through `thesis-experiment-run recover-cache`. |
| `scripts/research/frozen-launches/reexport_oct3_runs.sh` | frozen research wrapper | `scripts/research/frozen-launches/` | Retain only for provenance/replay if evidence still depends on it. |
| `experiments/runs/status.py` | compatibility wrapper | `experiments reporting CLI` | Move status model/reporting to experiments; retain login-node-safe wrapper if useful. |
| `compute/slurm/continuation.py` | compatibility wrapper | `compute CLI/public API` | Extract reusable Slurm/resource/recovery behavior to compute; keep thin adapter temporarily. |
| `scripts/compute/slurm/run_current_tree_gpu_ci.sh` | platform/Slurm wrapper | `scripts/compute/slurm/` | Keep allocation/shell mechanics thin; invoke compute/experiments APIs. |
| `compute/slurm/resources.py` | compatibility wrapper | `compute CLI/public API` | Extract reusable Slurm/resource/recovery behavior to compute; keep thin adapter temporarily. |
| `scripts/compute/slurm/status.sh` | platform/Slurm wrapper | `scripts/compute/slurm/` | Keep allocation/shell mechanics thin; invoke compute/experiments APIs. |
| `scripts/compute/slurm/two_trains_one_h200.sh` | platform/Slurm wrapper | `scripts/compute/slurm/` | Keep allocation/shell mechanics thin; invoke compute/experiments APIs. |
| `scripts/research/audits/leak_detectors.py` | research command | `scripts/research/audits/` | Extract reusable leakage checks to market_data/features/tests as appropriate. |
| `scripts/research/thesis/evaluation/rescore_sl_fill.py` | frozen research command | `scripts/research/thesis/evaluation/` | Preserve only as explicit historical rescore protocol using evaluation APIs. |
| `scripts/research/strategy_checks/verify_strategy_features.py` | research command | `scripts/research/strategy_checks/` | Use owning package APIs; remove generic utility category. |
| `config/experiment_runs/variant_list.txt` | config asset | `config/experiments or config/experiment_runs` | Move declarative list out of scripts; update every launcher/config reference. |
| `config/experiment_runs/variant_list_3_strategy_20261014.txt` | config asset | `config/experiments or config/experiment_runs` | Move declarative list out of scripts; update every launcher/config reference. |
| `config/experiment_runs/variant_list_rq1_entry_fsm.txt` | config asset | `config/experiments or config/experiment_runs` | Move declarative list out of scripts; update every launcher/config reference. |
| `scripts/compute/slurm/experiment_runs/run_dollar_band_q5_2m_continuous_allocation.sh` | experiment run allocation wrapper | `experiments + compute` | Keep resource and shell supervision only; preserve the named experiment's launch contract until its callers migrate. |
| `scripts/compute/slurm/experiment_runs/run_dollar_band_q5_2m_normal_allocation.sh` | experiment run allocation wrapper | `experiments + compute` | Keep resource and shell supervision only; preserve the named experiment's launch contract until its callers migrate. |
| `scripts/compute/slurm/experiment_runs/run_dollar_band_q5_2m_normal_supervisor.sh` | experiment run supervisor | `experiments + compute` | Keep recovery and allocation continuity explicit; do not replace a live supervisor during migration. |
| `scripts/compute/slurm/experiment_runs/run_dollar_band_q5_5m_allocation.sh` | experiment run allocation wrapper | `experiments + compute` | Keep resource and shell supervision only; preserve the named experiment's launch contract until its callers migrate. |
| `scripts/compute/slurm/experiment_runs/run_mtf_tcn_2m_allocation.sh` | experiment run allocation wrapper | `experiments + compute` | Keep resource and shell supervision only; preserve the named experiment's launch contract until its callers migrate. |
| `scripts/compute/slurm/experiment_runs/run_mtf_tcn_2m_supervisor.sh` | experiment run supervisor | `experiments + compute` | Keep recovery and allocation continuity explicit; do not replace a live supervisor during migration. |
| `scripts/compute/slurm/experiment_runs/run_sustainable_growth_eod_dd_allocation.sh` | experiment run allocation wrapper | `experiments + compute` | Keep resource and shell supervision only; preserve the named experiment's launch contract until its callers migrate. |
| `scripts/compute/slurm/experiment_runs/run_sustainable_growth_eod_dd_supervisor.sh` | experiment run supervisor | `experiments + compute` | Keep recovery and allocation continuity explicit; do not replace a live supervisor during migration. |
| `scripts/compute/slurm/experiment_runs/run_tcn_fullspan_n8_in_existing_allocation.sh` | in-allocation experiment run launcher | `experiments + compute` | Reuse the supplied allocation and keep resource-specific launch code in the Slurm boundary. |
| `scripts/compute/slurm/node_inventory.py` | resource inventory command | `compute` | Keep scheduler/node inspection behind the compute API and retain read-only behavior. |
| `scripts/data/setup_mode_dirs.sh` | data setup wrapper | `market_data` | Keep filesystem setup explicit and route dataset lifecycle through market-data ownership. |
| `scripts/dev/code_graph/graph_quality.py` | engineering quality command | `tools/check graph-quality` | Keep graph analysis outside trading packages; separate reusable graph engine from its gate CLI where justified. |
| `scripts/dev/security/dependency_audit.py` | dependency security command | `tools/check security-deps` | Keep the security finding schema and failure policy in the security owner. |
| `scripts/dev/security/secret_scan.py` | secret security command | `tools/check security-secrets` | Keep allowlist/baseline handling and redaction in the security owner. |
| `scripts/research/audits/audit_scripted_training_reachability.py` | research audit command | `training + experiments` | Preserve the audit protocol; move reusable reachability rules to their owning packages. |
| `scripts/research/audits/run_p1_schedule_freeze_gate.sh` | retired historical path | `scripts/research/frozen-launches/freeze_tick_decision_schedule.sh` | Alias removed; exact historical source hash is recorded in the snapshot manifest. |
| `scripts/research/audits/run_p1_tick_fold_validation.sh` | retired historical path | `scripts/research/frozen-launches/validate_tick_fold_scope.sh` | Alias removed; exact historical source hash is recorded in the snapshot manifest. |
| `scripts/research/audits/run_p1_tick_quality_validation.sh` | retired historical path | `scripts/research/frozen-launches/validate_tick_data_quality.sh` | Alias removed; exact historical source hash is recorded in the snapshot manifest. |
| `scripts/research/audits/run_p3_checkpoint_recovery_smoke.sh` | retired historical path | `scripts/research/frozen-launches/smoke_test_checkpoint_recovery.sh` | Alias removed; exact historical source hash is recorded in the snapshot manifest. |
| `scripts/research/count_entry_idea_opportunities.py` | research counter | `features + evaluation` | Keep the report command thin and consume the feature-owned entry-idea schema. |
| `scripts/research/plot_swing_order_block_preview.py` | research visualization | `evaluation/plotting` | Keep plotting reusable through evaluation; retain this command only as a thin preview entry point. |
| `scripts/research/thesis/evaluation/compare_experiment_run_summaries.py` | thesis analysis command | `evaluation + experiments` | Keep comparison logic on canonical experiment_run/evaluation records and outputs. |
| `scripts/research/thesis/evaluation/export_trade_observation.py` | thesis evidence command | `evaluation` | Export the versioned observation contract without reimplementing rollout semantics. |
| `scripts/research/thesis/evaluation/plot_stochastic_equity_ensemble.py` | thesis plotting command | `evaluation/plotting` | Keep stochastic-path summarization separate from the renderer and preserve its report protocol. |
| `scripts/research/thesis/evaluation/project_report_context.py` | report context builder | `evaluation/reporting` | Move reusable report-context assembly behind the reporting package API. |
| `scripts/research/thesis/evaluation/project_report_markdown.py` | report renderer | `evaluation/reporting` | Keep Markdown presentation separate from report data and artifact identity. |
| `scripts/research/thesis/evaluation/report_train_test_figures.py` | thesis plotting command | `evaluation/plotting` | Use shared evaluation figure data and preserve train/test split labels. |
| `scripts/research/thesis/evaluation/report_variant_details.py` | thesis report command | `evaluation/reporting` | Split data assembly, metrics, trade examples, renderers, and validation by ownership before extracting shared APIs. |
| `scripts/research/thesis/evidence/analyze_exit_outcomes.py` | thesis evidence command | `evaluation` | Keep exit classification/statistics reusable in evaluation and the CLI thin. |
| `scripts/research/thesis/evidence/analyze_monthly_trade_expectancy_and_exit_decomposition.py` | thesis evidence command | `evaluation` | Preserve historical report schema and source snapshot while keeping the canonical command functional. |
| `scripts/research/thesis/evidence/analyze_training_policy_dynamics_and_rule_control.py` | thesis evidence command | `evaluation` | Preserve historical report schema and source snapshot while keeping the canonical command functional. |
| `scripts/research/thesis/evidence/build_p7_paired_seed_payload.py` | retired historical path | `scripts/research/thesis/evidence/build_paired_seed_payload.py` | Preserve exact historical source bytes and hash in `docs/thesis/evidence/source_snapshots/manifest.json`. |
| `scripts/research/thesis/evidence/build_p7_tick_cost_stress_reports.py` | retired historical path | `scripts/research/thesis/evidence/build_tick_cost_stress_reports.py` | Preserve exact historical source bytes and hash in the snapshot manifest. |
| `scripts/research/thesis/evidence/build_paired_seed_payload.py` | mixed report builder and CLI | `evaluation/reanalysis/paired_seed_payload.py` plus thin script adapter | Move lineage validation and payload construction into the evaluation API; load frozen experiment run parameters declaratively; retain historical source identity in provenance snapshots. |
| `scripts/research/thesis/evidence/build_tick_cost_stress_reports.py` | thesis evidence command | `evaluation + artifacts` | Keep report generation separate from stress replay and use immutable report identity. |
| `scripts/research/thesis/evidence/replay_tick_cost_stress.py` | thesis replay command | `evaluation` | Keep deterministic replay orchestration on reusable evaluation/execution contracts. |
| `scripts/research/thesis/evidence/analyze_paired_seed_results.py` | mixed statistical library and CLI | `evaluation/reanalysis/paired_seed_statistics.py` plus thin script adapter | Move paired inference functions into the evaluation package; migrate script/test imports and place characterization tests under `tests/integration/`. |
| `scripts/research/thesis/evidence/run_p7_tick_cost_stress_replay.py` | retired historical path | `scripts/research/thesis/evidence/replay_tick_cost_stress.py` | Preserve exact historical source bytes and hash in the snapshot manifest. |
| `scripts/research/thesis/exit_shadow_fixed_entry.py` | thesis replay command | `evaluation` | Preserve the fixed-entry research protocol; split replay, statistics, and report rendering by ownership. |
| `scripts/research/thesis/p6_monthly_entry_exit_decomposition.py` | retired historical path | `scripts/research/thesis/evidence/analyze_monthly_trade_expectancy_and_exit_decomposition.py` | Preserve exact historical source bytes and hash in the snapshot manifest. |
| `scripts/research/thesis/p6_training_dynamics_control.py` | retired historical path | `scripts/research/thesis/evidence/analyze_training_policy_dynamics_and_rule_control.py` | Preserve exact historical source bytes and hash in the snapshot manifest. |
| `scripts/research/thesis/regime_attribution.py` | thesis analysis command | `evaluation` | Keep regime attribution tied to explicit evaluation periods and artifact provenance. |
| `scripts/research/thesis/verify_d1_source_normalization.py` | thesis verification command | `market_data + features` | Preserve the source-timeframe normalization contract and route reusable checks to data/feature owners. |

<!-- SCRIPT_LEDGER_END -->

## Tests architecture

Tests mirror package ownership:

```text
tests/
├── architecture/
│   ├── test_public_imports.py
│   ├── test_dependency_rules.py
│   ├── test_no_scripts_imports.py
│   └── test_legacy_imports.py
├── market_data/
├── features/
├── trading/
├── simulation/
├── models/
├── training/
├── evaluation/
├── experiments/
├── live/
├── integrations/
├── compute/
└── orchestra/
```

## Architecture tests

Before large migrations, add lightweight repository architecture checks.

### Public import tests

Verify the stable imports shown above.

### Dependency-rule tests

Use an AST-based repository check initially to detect forbidden imports. Examples include features importing training, trading importing evaluation, production code importing scripts, and models importing training orchestration.

### Root-ownership tests

Add checks for forbidden production writes into `baseline/`, scripts containing reusable package imports in the wrong direction, and package code importing command wrappers.

### Configuration contract tests

Verify unknown-key rejection, deterministic merges, canonical hashes, historical snapshot loading, and schema migration behavior.

### Artifact lifecycle tests

Verify atomic completion, rejection of incomplete artifacts, manifest/schema validation, provenance parent links, immutability/overwrite policy, and baseline promotion gates.

### Cache identity tests

Mutating any semantic cache input must change the cache identity. Non-semantic runtime changes must not invalidate caches unnecessarily.

### Repository hygiene tests

Verify tracked generated files have declared producers where required, ordinary tests do not write to repository artifact roots, and ignore rules do not hide source packages or tracked examples.

### Shared-helper ownership tests

Add focused checks for high-value primitives that must have one implementation. At minimum, prohibit new ad-hoc file-hashing and atomic-artifact-writing helpers outside their canonical owners once migration is complete. Use allowlists during transition and reduce them monotonically.

Do not enforce a blanket "no duplicate function names" rule; interface methods and conventional entry points legitimately share names.

### Equivalence tests for consolidated helpers

Every consolidation that can affect research behavior needs before/after parity tests at the owning boundary. For hashes/serialization this should normally be exact. For numerical functions use explicitly documented tolerances. For stateful functions compare resulting state/events/artifacts, not only return values.

### Semantic naming tests

Add lightweight architecture checks for clearly non-semantic numbered placeholders in newly migrated code, such as `function1`, `part2`, `setting3`, or `step_4`. Maintain a narrow allowlist for legitimate domain numbering such as take-profit levels, timeframes, seeds, schema versions, and explicitly documented migration phases.

Do not enforce naming mechanically beyond obvious placeholder patterns. Code review remains responsible for judging whether a name communicates the underlying domain concept.

### Vocabulary consistency checks

Where names are part of machine-readable contracts, add schema/tests that protect canonical terminology across configuration, runtime state, metrics, manifests, and reports. Historical field aliases may remain only through explicit compatibility adapters.

### Execution-surface drift tests

Verify that stable wrappers resolve to existing package APIs, Docker/console entry points refer to supported commands, and production packages never import scripts, tools, or CI wrappers.

### CI-definition consistency tests

Validate the architectural pieces most likely to drift: canonical named gates exist, workflow references resolve, required tools do not silently skip, and every first-class package root is included by lint/type/build configuration. Do not unit-test workflow YAML line by line.

### Legacy-import budget

Track remaining imports from the legacy monolithic package mechanically.

The budget must decrease phase by phase and reach zero before that package is removed.

The architecture plan intentionally does not encode its package name.

## Packaging and tooling changes

Repository-root packages require project-tooling changes.

### Build configuration

The wheel/build configuration must include every new top-level package, including `configuration` and `artifacts`, rather than a single monolithic application package plus Orchestra.

### Ruff

Update source roots, first-party package declarations, and import sorting expectations.

### Mypy

Update checked package roots so strict typing covers every top-level package. Avoid namespace-package ambiguity; every importable code package has `__init__.py`.

### Pytest

Keep `tests/` as the root and mirror the package structure.

### Console entry points

Move frequent supported commands to project console entry points backed by package-owned CLI functions. Research, maintenance, and Slurm wrappers remain under scripts when they are not stable user-facing commands.

Console commands, scripts, Docker Compose, Slurm wrappers, and CI must converge on the same package APIs.

### Quality-gate entry points

Provide one canonical local gate surface, preferably tools/check, with named fast/unit/integration/full and platform-specific gate selections. GitHub workflows and thin CI adapters invoke this surface instead of duplicating raw lint/type/test command definitions.

### Documentation

Update `README.md`, `docs/architecture.md`, `.agents/architecture.md`, domain maps, and running-command documentation.

## Migration phases

### Phase 0 — Freeze behavior and define contracts — COMPLETE

- Record current CI baseline.
- Record current script/CI command surfaces, test markers, Docker/Slurm entry points, and duplicated or platform-specific gates.
- Build the repository-wide ownership/name/location inventory defined above before broad moves. Include every active tracked file and directory across source, tests, configs, docs, commands, tooling, CI, research evidence tooling, and artifact/cache/output producers. Record a target disposition and consumer/compatibility evidence for every item; distinguish active code from frozen evidence, domain identifiers, generated artifacts, and user/runtime data.
- Publish the target ownership map and dependency direction from the inventory. For each proposed package/folder, state the cohesive domain it owns, its public API, allowed dependencies, and why an existing package is insufficient. Do not create placeholder packages or move files to satisfy a diagram.
- Resolve priority misnamed/misplaced files from the inventory before declaring a subsystem migration complete. Keep a rolling list of remaining files, with an explicit reason for every retained generic or ordinal name.
- Freeze the checked 2026-10-30 baseline: 13 CI jobs (12 required gates plus aggregator) and 149 regular script files plus 9 compatibility symlinks, excluding `__pycache__`. Historical counts are not current migration inputs.
- Add architecture import/dependency tests.
- Add characterization tests for environment, backtest, features, training setup, evaluation, and experiment run behavior.
- Record checkpoint/action/observation/feature schemas.
- Make no production behavior changes.

**Phase 0 acceptance:** the inventory has no unreviewed active paths; each path
has an owner, responsibility, naming category, and disposition; proposed new
packages have an explicit domain/API/dependency rationale; high-risk moves have
characterization coverage or a documented gap and safe sequencing; and
historical/public compatibility is separated from canonical source naming.
This is not satisfied by a grep for `p7`, `wp`, `phase`, or generic words alone.

### Phase 1 — Create root package and lifecycle foundations — COMPLETE

Introduce the first needed package shells and `__init__.py` APIs. Establish `configuration` and `artifacts` first because later packages depend on consistent config/provenance/output mechanics.

Then create the initial domain surfaces for `trading`, `simulation`, `market_data`, and `features`. Define the root ownership/retention rules for `config/`, `data/`, `cache/`, `outputs/`, `logs/`, and `baseline/` before migrating writers.

Do not create empty target directories just to match the diagram.

**Phase 1 implementation record (2026-10-30):** the initial package surfaces
and root ownership rules were present and are retained without empty shells.
Configuration YAML loading now has one recursive, type-aware overlay validator
used by default, strategy, feature, live, and strategy-aware research paths.
The strategy path map and merge behavior live in
`training/configuration/strategy_overlays.py`. Artifact manifests validate
their common identity envelope, and baseline promotion requires a parent
artifact identity and source revision before validation or publication. The
unused `ArtifactStore`, global artifact-kind registry, duplicate generic
`deep_merge`, and no-op config compatibility stub were removed after import
and symbol searches showed no production consumers. Domain-specific schema
validation remains with each domain writer/reader.

Phase 1 tests passed: 175 affected tests; full-tree Ruff format, Ruff checks,
and Mypy passed on GH200. The only emitted warnings were the existing
Transformer nested-tensor warnings. No training, benchmark, or data/cache
generation ran.

### Phase 2 — Extract pure trading contracts — COMPLETE

Move account, policy, risk, orders, costs, and deterministic execution primitives into `trading`.

Acceptance: legacy and repeated-payout behavior unchanged; risk boundary tests pass; no duplicate domain formulas.

**Phase 2 implementation record (2026-10-30):** centralized deterministic
quote construction and stop-gap behavior in `trading.execution.quotes`, and
reused shared stop-risk, execution-reserve sizing, equity risk-budget, and
account EOD drawdown calculations from simulation and backtest consumers.
Order timeframe ranking and reporting provenance now share one parser while
preserving the established empty timeframe label for session-level plot notes.
Simulation and cross-validation consumers import trading APIs from their
package boundaries; removed artifact-store references in domain maps were
updated to the current identity, manifest, atomic-write, and promotion APIs.

The phase gate passed full-tree Ruff format, Ruff lint, and Mypy on GH200, plus
1,029 targeted architecture, order, risk, feature, environment, backtest,
evaluation, artifact, and checkpoint tests. The suite emitted 131 warnings;
no test failed. No training, benchmark, or cache/data operation ran.

### Phase 3 — Split simulation runtime — COMPLETE

Move environment mechanics and backtest orchestration into `simulation`.

Acceptance: environment golden traces, backtest parity, action/observation schemas, tick execution, multi-TP, EOD, guardrails, and payout behavior match.

**Phase 3 implementation record (2026-10-30):** moved backtest accounting,
policy actions, protective/account events, and terminal liquidation out of the
backtest state/settings module into `simulation/backtest/accounting.py`,
`policy_actions.py`, and `protective_events.py`. The event-driven backtest
remains the composition root. Environment entry orchestration now delegates
order-level construction, risk-capacity approval, position initialization,
and entry-ledger recording to focused runtime mixins; episode reset is owned
by `EpisodeRuntimeMixin`. Preserved the public `TradingEnv` and `run_backtest`
interfaces and left the cross-validation `main.py` as a tested compatibility
adapter for the named `backtrader_runner.py` implementation.

Phase 3 validation passed on the active GH200 allocation: full-tree Ruff
format/check, full-tree Mypy (818 source files), and 566 architecture,
environment, backtest, repeated-payout, and strategy-integration tests. The
test batch emitted three existing Transformer nested-tensor warnings. No
training, benchmark, cache generation, or data mutation ran.

### Phase 4 — Split market-data and feature pipelines — COMPLETE

Move data ingestion/transforms/splits to `market_data` and feature stages to `features`.

At the same time, migrate dataset manifests and cache identities so data/cache layout is produced through package APIs rather than filename conventions.

Acceptance: feature values/order, causal-prefix tests, split identities, and cache hashes match for unchanged semantics.

**Phase 4 implementation record (2026-10-30):** separated configured tick-book
assembly into `market_data/loading/tick_book_pipeline.py`, moved the date-specific
session-close loader to `market_data/transforms/session_schedule.py`, and
extracted shared source-timeframe, resampling, raw-FVG, and training-mask inputs
to `features/pipeline/feature_build_inputs.py`. Bar-cache path construction is
now a named cache API, and simulation, training, evaluation, research scripts,
and tests use the public loading/transforms APIs. The unused standalone
`DatasetManifest` skeleton was removed: atomic per-cache manifests already
carry source identity, schema, symbol/timeframe, partition, timezone/session
semantics, row count, bounds, and file-completion data; a second unconsumed
manifest schema would duplicate that source of truth.

The entry-idea feature builder now constructs its multi-hot columns in one
frame assembly instead of repeatedly inserting columns. Existing feature and
entry-idea tests preserve the output contract, and the prior pandas
fragmentation warnings no longer appear in this gate.

Phase 4 validation passed on the active GH200 allocation: full-tree Ruff
format/check, full-tree Mypy, and 379 architecture, market-data, feature,
tick-cache, prebuild-cache, and session-integration tests. No training,
benchmark, cache generation, or data mutation ran.

**Phase 4 completion addendum, 2026-10-30:** the remaining shared context
module was decomposed by responsibility: causal reachable-R features now live
with reachability context, London-relative ATR distances have a named session
feature module, and fold-scoped normalization/building has a dedicated
walk-forward fitting module. The stable `features` and `features.pipeline`
exports remain unchanged; the former mixed `features.pipeline.context` module
was retired after active callers were moved. The consolidated feature and
environment-bundle batch passed 268 tests, and Ruff formatting/lint passed on
the changed source files. The first run exposed that the dirty-tree rewrite of
`tests/conftest.py` had dropped the shared `m1_bars` and `dict_obs_space`
fixtures; both were restored alongside the execution-marker hook before the
passing batch. Full-tree Mypy and final repository gates remain in the single
post-implementation validation batch.

### Phase 5 — Split models and training — COMPLETE

Move reusable encoder registration and architectures to `models`; keep
Stable-Baselines3 policy adapters and PPO/SAC construction in `learning`.
Keep training lifecycle composition and artifact writing in `training`.

Move run-directory creation, resolved-config snapshots, checkpoint manifests,
diagnostics, and training logs behind the artifact layout/provenance APIs.

Acceptance: existing commands work through wrappers, seeds match, checkpoints load, manifests match.

**Phase 5 implementation and gate, 2026-10-30:** encoder-name resolution now
lives in `models.factory.encoder_registry`; `learning.rl.agent` remains the
PPO/SAC composition layer. Inspection and the dependency gate showed that the
custom PPO policies inherit Stable-Baselines3 policy/distribution classes, so
they correctly remain under `learning/rl` rather than introducing a framework
dependency into `models`. Training now exposes public run-artifact APIs for
immutable resolved configuration snapshots, run-local logging, manifest
schemas, multi-seed aggregation, and evaluation result writing. Run creation
uses `ArtifactLayout`; evaluation reports use atomic replacement and preserve
their established JSON field order and serialization behavior. Fixed the
per-seed metadata helper/local-variable shadowing that could fail while
building the final training log. The `metrics.py` artifact writer was renamed
to `evaluation_result_writer.py` to state its output role.

The existing `evaluation.reporting.run_manifest` schema remains the canonical
compatibility surface for reanalysis in this phase; Phase 6 will consolidate
that schema with evaluation provenance writers before any legacy path is
retired.

The full-tree gate passed: Ruff format/check and Mypy on 825 source files;
281 focused architecture, model/checkpoint, seed, training-artifact, run
manifest, and command smoke tests passed. Same-seed rollout reproducibility
passed. The gate did not run an experiment run, benchmark, cache build, or mutate
training data. The known PyTorch nested-tensor warnings remain informational.

**Phase 5 completion addendum, 2026-10-30:** removed the mixed
`training.setup.data` module and assigned read-only observation-array
materialization to `training.setup.observation_memmap` and NY tick-coverage
planning to `training.setup.tick_execution_preflight`. Cross-package helpers
now have public responsibility names, and training, research audits, and
resource-analysis tools import their owning modules directly. Renamed the
walk-forward orchestration module to `training.runner.walk_forward_validation`
and updated its composition caller and architecture/source-contract checks.
The consolidated batch passed 65 relevant feature-fit, tick-preflight,
environment-bundle, training-composition, and dependency-contract tests. Ruff
formatting/lint passed on all changed Python files. One initial dependency test
found a stale path in the training domain map; the map and related operational
references were migrated, and its exact path-ownership regression test then
passed. No training run was started. Full-tree Mypy and final repository gates
remain in the post-implementation batch.

### Phase 6 — Consolidate evaluation — COMPLETE

Move rollout, metrics, reanalysis, reporting, and plotting into `evaluation`.

Consolidate evaluation artifact schemas/writers so reanalysis, reports, plots, and numerical evidence share one manifest lineage.

Acceptance: fixed checkpoint reanalysis remains numerically unchanged and only one canonical reusable evaluation package remains.

**Phase 6 implementation and gate record, 2026-10-30:** rollout code now
lives in `evaluation/rollout/trained_policy_rollout.py` and
`evaluation/rollout/episode_rollout.py`; summary aggregation is in
`evaluation/reporting/run_summary.py`; checkpoint replay is in
`evaluation/reanalysis/checkpoint_reanalysis.py`; and run output assembly is in
`evaluation/reporting/run_artifact_writer.py`. Fill and position table
reconstruction is owned by `trade_event_export.py`. The canonical
`evaluation_manifest.json` writer links training/reanalysis parent manifests
and hashes each split's metrics, equity, trade, fill, position, and thesis
decision tables. Training curves now belong to `training/reporting/`. Per-trade
chart geometry and Matplotlib/Plotly renderers are separate modules. Proven old
rollout, report, reanalysis, and chart-regeneration imports remain narrow
runtime-forwarding wrappers for compatibility and will be reconsidered during
Phase 11. The old `evaluation.plotting.training_plots` path was retired because
its forwarding dependency would reverse the evaluation/training boundary and
no active in-repository caller required that path.

The consolidated gate passed full-tree Ruff format/check and full-tree Mypy
across 837 source files; 206 focused architecture, rollout, reanalysis, report,
chart, manifest, training-curve, reproducibility, and command tests passed. The focused
suite reported three existing pandas deprecation warnings. No full test suite,
training run, benchmark, cache build, or data mutation was performed. The code movement preserves the existing rollout and report contracts, and the
remaining wrapper identity plus deterministic seed and chart/report tests passed;
the former training-plot wrapper was retired to preserve dependency direction. A
new full-year saved-checkpoint reanalysis was not run as part of this architecture
phase.

### Phase 7 — Extract experiments and experiment runs — COMPLETE

Experiment run workflow and provenance remain in `experiments`; generic Slurm worker
resource sampling and dispatch live in `compute.slurm`; experiment run paths and
atomic writes use shared `artifacts` services. The workflow composition root is
`experiments/runs/execution.py`. The former execution, experiment run
resource, and compute resume paths remain narrow compatibility adapters where
existing launchers or CLI consumers depend on them. Cache-failure recovery is
owned by `experiments/runs/cache_failure_recovery.py`.

Experiment run storage naming and checkpoint/worker/report lineage retain their
existing external layout. The focused contracts for artifact layouts, fake
worker-controller integration, resource dispatch, checkpoint migration,
recovery, and experiment run status passed together: 125 tests. Full-tree Ruff
format/check and Mypy passed across 840 files. No experiment run, training run,
benchmark, data rebuild, or cache mutation was performed in this phase.

**Phase 7 completion addendum, 2026-10-30:** the ablation lifecycle now lives
in `experiments/variants/variant_ablation_runner.py` behind a typed request
contract; argument parsing and root dispatch live in `experiments/cli.py`.
`experiments/variants/runner.py` remains a thin compatibility import and module
entry point. Named-cache rebuild parsing is also owned by the stable
`thesis-experiment-run rebuild-named-cache` command, while the former module command
forwards to it. Added parser/dispatch tests without invoking training or
writing caches. The combined focused batch passed 36 tests; Ruff format/check
passed on all changed Python files. One initial architecture check identified
the new ablation lifecycle as a five-domain composition root; its explicit
budget now reflects those real dependencies, and the exact fan-out check
passed. Full-tree Mypy and final repository gates remain in the
post-implementation batch.

### Phase 8 — Separate live runtime and integrations — COMPLETE

Broker-neutral inference contracts and policy adaptation remain under `live`;
MT5 data, order, account, and robot implementations remain under
`integrations.mt5`. The integration package now has a lazy top-level API, so
importing the package does not require the vendor MT5 module. A single validated
risk-configuration reader supplies RL live sizing and the risk manager's
defaults. Both RL and rule-based MT5 robots now refuse entries when risk sizing
fails or returns no valid volume; neither substitutes a fixed lot. Closing a
long uses the bid and closing a short uses the ask.

The full-tree Ruff format/check and Mypy gate passed across 842 files. The
combined live/architecture contract suite passed 86 tests, covering paper-mode
order suppression, risk settings, invalid sizing/configuration, provider and
secondary-symbol wiring, package import boundaries, and bid/ask close prices.
No live orders were sent. No training, benchmark, cache rebuild, or data change
was performed.

### Phase 9 — Refactor Orchestra and engineering execution surfaces — COMPLETE

Split Orchestra phases/execution/recovery/reporting behind its package API.

Establish the canonical quality-gate surface, migrate GitHub workflows to named gates, normalize test markers, eliminate duplicate CI command definitions, and migrate Docker/Slurm/script entry points to stable package APIs.

Acceptance: normal `ci.yml` matches the nine semantic gates plus three explicitly justified assurance gates and `ci-success`; local and hosted CPU gates share semantics; `ci-scripts/` contains only proven platform glue or is deleted; the checked 149-file/9-symlink script ledger has no unresolved entry; stable operations use console/package APIs; Tier D Triton/GPU validation is documented and runnable; no required gate silently skips; stale *ordinary operational* command paths are removed. Identity-bound launchers, supervisors, and frozen experiment run commands remain protected exceptions while their run or recovery contract is active; record each exact path and retirement condition rather than rewriting a live command and changing experiment run identity.

**Phase 9 implementation and consolidated gate (2026-10-30):** Orchestra now
delegates verification to one `./tools/check full` command. The dispatcher
rejects skipped as well as failed required checks. The named pytest execution
markers (`unit`, `integration`, `slow`, `gpu`, `triton`, and `research`) are
declared centrally and assigned consistently; unit, integration, research,
and slow selectors are disjoint where required. Nightly invokes the shared
research and slow gates without repeating integration/backtest coverage that
normal CI already owns. Release validation uses the canonical full gate and
BuildKit's GitHub cache instead of caching `/var/lib/docker`.

The consolidated check passed on GH200 allocation `21298263`: full-tree Ruff
format (`843` files), Ruff lint, and Mypy (`843` source files); `56` focused
Orchestra/architecture tests passed; marker-specific collection found `3`
GPU tests in the selected actor/encoder files; and full test collection found
`2,413` tests. Collection is not reported as test execution. A reconciliation
of the canonical inventory against the current filesystem found `1,594`
existing paths represented in `1,601` ledger rows, including seven entries
that explicitly record retired/deleted paths; no current path was missing. The
checked
script baseline remains `149` regular files and `9` tracked historical
compatibility symlink entries; the physical `scripts/` tree contains no
symlinks, and `ci-scripts/` is absent. The ledger retains their exact
dispositions. We preserved active fingerprint-bound invocation paths in
`scripts/compute/slurm/two_trains_one_h200.sh`, the two dollar-band Q5
experiment run allocation scripts
`scripts/compute/slurm/experiment_runs/run_dollar_band_q5_2m_continuous_allocation.sh`
and `scripts/compute/slurm/experiment_runs/run_dollar_band_q5_5m_allocation.sh`,
`scripts/compute/slurm/worker_bin/srun`, and their
`training.runner.training` / `compute.slurm.worker_dispatch` module targets.
These paths can be migrated or retired only after the corresponding
supervisor and run-recovery contracts are terminal. No training, benchmark,
experiment run, cache build, or data mutation ran. The ledger includes the Phase 9
marker-contract test and shared timeframe-order module. Command references in
the agent, Orchestra, README, and operations guides now use the
architecture-matched test tools; outdated full-suite duration and generic
training command examples were removed. The dated Phase 0 baseline count is
retained as historical evidence; the reconciled live count above is current as
of this phase gate.

**Final execution-surface correction (2026-10-30):** the ARM developer and
GPU paths now select the repository's `.venv/bin/python` automatically, while
x86 selects `.venv-x86`; `tools/check` skips `uv sync` when an architecture-
matched project interpreter is active. Generic environment setup helpers and
the current-tree GPU gate resolve this checkout from their own location, with
`TRITON_REPO` retained as an explicit override. The final GH200 gate passed
full-tree Ruff format and lint, Mypy across 845 source files, and the package
build/import smoke through the selected project Python (sdist and wheel both
built). The dependency-lock/export gate also passed using a native ARM64 `uv`
0.13.6 supplied through `THESIS_UV`; all pip pin files match `uv.lock`. The
consolidated focused batch passed 152 architecture, artifact, Orchestra,
compatibility, experiment run, encoder, and checkpoint-persistence tests. Current
inventory reconciliation is 1,603 unique ledger rows, 1,596 paths present,
and seven explicitly retired paths. All 1,517 tracked paths present in this
worktree have inventory rows; none are unlisted. This supersedes the earlier
Phase 9 gate totals above.

The final canonical `contracts` and `parity` gates also passed, with 78 and 65
tests respectively. These are additional scoped gate results, not a claim that
the full hosted CI workflow or its training-smoke job ran.

### Phase 10 — Normalize repository support architecture — COMPLETE

After domain writers have moved, normalize `config/`, `data/`, `cache/`, `outputs/`, `logs/`, `baseline/`, `scripts/`, `tests/`, `docs/`, `tools/`, and `ci-scripts/` around the ownership rules above.

This phase is not a cosmetic directory shuffle. Migrate generators/consumers first, add compatibility path resolution where needed, verify historical run reanalysis, then retire obsolete layouts.

Acceptance: no production caller depends on an undocumented generated path; every retained artifact class has an owner/schema/provenance rule; scripts and CI are thin; test writes are isolated; baseline promotion is explicit.

**Phase 10 implementation and gate (2026-10-30):** the repository-wide
ownership inventory now has a unique row for each of 1,603 recorded paths,
including every active tracked path and explicit retired-path records. Required
owner, responsibility, disposition, boundary, compatibility, and verification
fields are populated for every row. `ArtifactLayout` validates run, experiment run,
and evaluation path components and resolves recorded experiment run paths without
allowing directory escape. Root ignore rules keep normal/discretion partition
contents, generated caches, run outputs, and logs out of Git while preserving
the tracked examples and split-root README files. Docker `test` and `test-gpu`
services expose only read-only config/docs/example inputs and place outputs,
models, caches, and logs on container-local temporary filesystems; an
architecture contract checks this policy without running Docker or touching
user data. Existing explicit baseline-promotion identity validation remains
the promotion gate.

Validation passed on the existing GH200 allocation: full-tree Ruff format,
full-tree Ruff lint, full-tree Mypy (845 source files), package build/import,
the dependency-lock/export gate with native ARM64 `uv`, and 152 focused
architecture, artifact, Orchestra, compatibility, experiment run, encoder, and
checkpoint-persistence tests. The canonical `contracts` and `parity` gates
passed 78 and 65 tests, respectively. The storage contracts were run against
an isolated temporary Git repository. Docker runtime execution, training,
benchmarks, cache builds, and data mutation were not part of this gate.

A final current-worktree reconciliation compared every present tracked and
non-ignored untracked path with the ownership ledger: 1,596 present paths,
seven explicitly retired ledger entries, and zero present paths missing from
the ledger. Ignored raw data, caches, outputs, logs, and the protected dispatch
log were not treated as source inventory entries.

**Phase 8–10 implementation follow-through (2026-10-30):** a source-to-plan
audit found several migrations still missing despite the earlier phase labels.
The single-symbol and rule-based multi-symbol applications now live in
`integrations/mt5/cli/single_symbol_demo.py` and
`integrations/mt5/cli/multi_symbol_trading.py`; the root scripts remain thin
compatibility entrypoints. Both documented `--once` commands now run exactly
one cycle and exit. Multi-symbol YAML resolution is repository-root-relative,
and configured symbol candidates retain declaration order while duplicates
are removed deterministically.

The stable Orchestra command surface remains `orchestra.cli:main`, composed
from `orchestra/commands/task_lifecycle.py` and
`orchestra/commands/status.py`. This preserves all 13 command names while
removing duplicated output and setup statements from the former monolithic
module. Relative imports now resolve from their canonical package.

The Phase 10 test-path ledger migrations are applied in a batch. Test imports,
Mypy module overrides, command examples, and test execution markers follow the
new paths. The two structure suites have distinct names, the merged integration
package marker retains its former suite descriptions, and tests that load
repository scripts resolve from the checkout root rather than their former
directory depth. The inventory contains 1,615 unique records and covers all
active tracked paths.

The consolidated validation ran on GH200 allocation `21299073`: full-tree
Ruff format and lint passed; full-tree Mypy passed for 854 source files; the
whole test tree collected 2,432 tests; and the affected feature, market-data,
simulation, training-boundary, experiment, live-app, Orchestra, trading, and
architecture tests passed (**672 passed, 3 warnings**). The warnings are the
existing Transformer nested-tensor and Python `forkpty` notices. The complete
test suite was collected but not executed. No training, benchmark, cache build,
data mutation, or broker operation was performed. The allocation and persistent
shell remain available for follow-up work.

### Phase 11 — Remove redundant compatibility layout — COMPLETE

Retire a compatibility module only after the repository-wide import and
invocation audit, public-import tests, repository gate, fixed-checkpoint
reanalysis, and experiment run dry-run pass. Do not break an active launcher or a
serialized checkpoint class path to make the alias count zero. Such paths are
supported compatibility contracts, not duplicate implementations; record
their owner and concrete consumer in this plan. The goal is zero *unreviewed
or implementation-bearing* compatibility modules.

Then remove compatibility forwarding modules and update build/lint/type-check configuration and architecture docs.

**Phase 11 readiness audit (2026-10-30):** the import and invocation review
confirms that compatibility paths remain observable contracts. Evaluation
forwarders have explicit canonical-module tests; frozen reanalysis launchers
still invoke `evaluation.reanalysis.runner`; `compute/cli.py` still exposes the
resume subcommand through `compute.slurm.resume`; and experiment run execution has
current CLI, migration, checkpoint, test, and research-script consumers.
Encoder import shims also preserve serialized Stable-Baselines3 class paths;
the repository inventory still requires an archive-load inventory before
those paths can be retired. No wrapper or shim was removed based on a
repository-only search.

The focused Phase 11 readiness batch passed 52 tests covering evaluation
forwarders, encoder imports, experiment run policy overrides, experiment run execution,
cache recovery, and continuation. It emitted nine existing Transformer
nested-tensor warnings. Four additional checkpoint persistence tests passed:
legacy-module resolution, legacy action-layout adaptation, and SB3 save/load
for continuous and discrete action schemas; these create and load temporary
synthetic checkpoints and do not train. an experiment run dry-run validated two
development variants at 1,000 configured steps each, printed the resolved
2,000-step plan, and created no output directory. The same consolidation also
verified wheel/sdist builds and package imports through the
architecture-selected interpreter; `tools/check build` no longer depends on
the login-home `uv` executable when a matched project Python is selected.

Phase 11 remains gated, not complete. The plan requires full CI, a smoke
training run, checkpoint reanalysis, and an experiment run dry-run before removals.
The dry-run and synthetic checkpoint persistence checks passed. A real
checkpoint reanalysis is recorded below, but it does not establish numerical
parity because the source run predates material policy changes. Full CI and a
smoke training run were not run; the active repository goal forbids training
and benchmarks, and the local agent gate runs scoped tests rather than the full
suite. Preserve the remaining wrappers until the required gates establish that
the compatibility contracts are preserved.

**Fixed-checkpoint replay gate attempt (2026-10-30):** the canonical
`evaluation.reanalysis.checkpoint_reanalysis` command was invoked against the
preserved `replacement18_seed50` checkpoint using its saved config and the
explicit preserved feature cache. It failed closed before data loading because
the checkpoint/manifest stop-menu schema lists `M5`, `M15`, and `H1`, while the
current schema builder resolves all eight configured HTF stop timeframes
(`M3` through `D1`). The saved encoder windows are only M5/M15/H1. This is a
real historical-policy compatibility mismatch; bypassing the guard or
replaying that checkpoint under the current broader stop menu would change
action semantics and invalidate the comparison. No evaluation output directory
or cache was created. Keep the mismatch and command log at
`outputs/agent_state/architecture_refactor_checkpoint_reanalysis_20261030.run.log`;
do not remove the compatibility path or treat this failed replay as evidence
of numerical parity.

**Matched-schema checkpoint replay (2026-10-30):** a newer preserved
`sustainable_growth_ppo_dsr` checkpoint matched the current all-eight-timeframe
stop schema and was replayed with its saved config, exact v31 feature cache,
stochastic actions, and seed 50. Dataset/cache parity and checkpoint hash
validation passed. The 2025 training split and report-only 2026 test split
completed; the output is
`outputs/agent_state/architecture_refactor_checkpoint_reanalysis_20261030_matched/`.
Current-code replay versus the source run's saved results was:

| Split | Source return / drawdown / trades / breaches | Replay return / drawdown / trades / breaches |
|---|---:|---:|
| 2025 training | -10.34% / 12.80% / 646 / 3 | -10.14% / 19.01% / 892 / 1 |
| 2026 report-only test | -10.03% / 11.43% / 284 / 1 | +10.28% / 13.48% / 995 / 0 |

This is not a valid architecture-only parity comparison: the source manifest
records code commit `d2dba446`, while the current checkout is at `3fbbb74` and
includes later MTF/entry-policy changes as well as the in-progress refactor.
The replay proves the current checkpoint loader and evaluation path complete
on a schema-compatible saved model; the metric divergence means behavior
preservation is unverified and no compatibility wrapper can be retired on this
evidence. The 2026 split was previously inspected and remains report-only.

The replay reused the feature cache with SHA-256
`095720d14f1db1849ce5b4cba501523c8e6abd143c5484f9b8dd9c5de78d38b5` and
generated absent tick-book caches for the training and testing partitions
under `cache/data_modes/normal/train_test_2025_2026_v31/`. Preserve those
derived caches. The source CSVs and feature cache were not changed. No model
training or benchmark ran.

**Phase 11 validation update (2026-10-30):** the plan-mandated full local gate
was run on the existing GH200 allocation with architecture-matched tools. The
complete log is
`outputs/agent_state/repository_refactor_full_ci_final4_20261030.run.log`.
Dependency-lock export/check, both security gates, full-tree Ruff format/lint,
full-tree Mypy (854 source files), architecture tests (43), graph quality,
contracts (78), unit tests (2,054 passed; 388 deselected), package build/import
smoke, integration tests (315), execution-parity tests (65), and synthetic PPO
and SAC smoke tests (12) all passed. The smoke phase used only its small
synthetic test fixtures; no thesis experiment run, market-data training, or benchmark
was started. The suite emitted existing Transformer nested-tensor notices and
synthetic metric/report warnings; no test failed.

The graph-quality gate now builds against the live checkout using a disposable
Git index. Deleted tracked paths are excluded, new Python/shell files are
included as intent-to-add, and the user's real index remains untouched. The
audit recognizes calls on imported external classes by their class import, so
`Path.resolve()` or a plotting API method cannot be attributed to an unrelated
same-named project function. It reports its resolution summary without
overwriting the saved graph reports. The final graph contained 1,083 scanned
files; internal resolution was 81.18% (11,239/13,844), critical-path
resolution was 72.05% (1,449/2,011), and source/config verification passed.

The full suite also found and fixed stale test-root calculations left by the
file moves. Affected Triton, experiment-run-policy, experiment-run-controller,
worker-dispatch, and result-manifest tests now resolve repository assets from
the repository root; all 33 directly affected tests passed before the final
full run. The ARM security audit helpers also honor `THESIS_UV`, and Tornado is
pinned to 6.6 in the lock and exported pin files after the dependency audit
identified advisories against 6.5.9.

Phase 11 is still **gated, not complete**. The fixed-checkpoint replay against
the current refactor completed for a schema-compatible checkpoint, but its
saved source run predates policy and MTF behavior changes; the material metric
divergence above means it cannot establish architecture-only behavioral
parity. The older replacement18 checkpoint also has a stop-menu schema
mismatch and correctly fails closed. The compatibility import/launcher
inventory has not yet been extended to a complete archive-load inventory.
Therefore no compatibility wrappers, frozen launchers, or serialized class
shims were removed. Retiring them without a source-matched checkpoint parity
result and archive-load inventory would violate the plan's preservation gate.
No training experiment run, full benchmark, data/cache rebuild, commit, or push was
performed.

**Phase 1 artifact-foundation closeout (2026-10-30):** the remaining artifact
schema and baseline questions were reconciled against the live producer and
consumer APIs. There is deliberately no global kind registry: training owns
the versioned run-manifest schema (including source revision, resolved-config
digest, exact train/test data and feature identities, split, policy schemas,
seed, checkpoint digest, and training protocol); evaluation owns the
`evaluation-artifacts-v1` parent and numerical-artifact hashes; experiment runs own
their experiment-run-state schema, source snapshot, fingerprint, and child-run
lineage; and market-data/features own semantic cache manifests. The common
`artifacts` package supplies identity/hash, path layout, atomic writes,
retention, and validated-promotion mechanics without duplicating those domain
payload schemas. Their writer/reader contracts and import boundaries passed
the full gate above.

The source review found no active production writer that promotes new results
into `baseline/`; its existing files are curated historical evidence. No
current result satisfies a new baseline-acceptance decision, so wiring an
automatic promotion into training/evaluation would violate the rule that
normal runs never write there. `promote_to_baseline` remains an explicit,
tested API requiring a reviewed validator and parent/source identity; no real
baseline was changed. On this evidence Phase 1 is complete. The Phase 11
checkpoint/archive compatibility gate remains separate and open.

**Checkpoint archive inventory and safe shim retirement (2026-10-30):** added
`scripts/maintenance/artifacts/inventory_checkpoint_serialized_classes.py` and
its fixture test, then scanned saved model artifacts beneath `outputs/` on the
existing GH200 allocation. The inventory covered 2,175 checkpoint ZIPs; all
had readable bounded metadata and none required pickle/cloudpickle or tensor
loading. Exactly one archive serializes `models.encoders.core.TCNEncoder`:
`outputs/smoke_runs/full_pipeline_100k_20261020/runs/20261020_120337_411250_rl_train_seed50_tcn/model/ppo_final.zip`.
No saved checkpoint referenced `models.encoders.common` or
`models.encoders.mtf_efficiency_common`, and source/test/config/launcher search
found no remaining consumer after migration. Those two forwarding shims and
their identity test were retired; their canonical implementations remain in
`sequence_encoder_components.py` and `mtf_efficiency_components.py`. The
`models.encoders.core` path remains because the preserved checkpoint requires
it, and its identity/load coverage remains in place. The machine-readable
inventory is `outputs/agent_state/checkpoint_serialized_class_inventory_20261030.json`.

The inventory tool, encoder import tests, filename contracts, and repository
ownership/storage contracts passed their focused batch (36 passed). Phase 11
is still **gated, not complete**: the single retained checkpoint reference
requires `models.encoders.core`, and the source/current full-year checkpoint
replay remains materially different after policy changes. No compatibility
path was removed beyond the two for which the complete archive and import
inventory found no users. No archived checkpoint, model tensor, or research
result was modified.

**Phase 11 checkpoint parity and safe retirement closeout (2026-10-30):** the
interim status above was superseded by a source-matched replay. The same saved
`sustainable_growth_ppo_dsr` checkpoint (SHA-256
`c9d4e2ab7eca3ad8ab90d4513f2adceb128fcddf267963c58d7ef1ebac3a233e`), v31
feature cache (SHA-256
`095720d14f1db1849ce5b4cba501523c8e6abd143c5484f9b8dd9c5de78d38b5`), seed
50, stochastic policy actions, execution seed 50, zero tick-fill slippage, and
chronological split were replayed first from baseline source `3fbbb74`, then
from the refactored checkout. Both replays loaded the existing tick caches.
The 2025 training and report-only 2026 evaluation equity CSVs and metric JSONs
are byte-identical across the two outputs:

| Split | Net return | Max drawdown | Trades | Expectancy | Profit factor | Breaches |
|---|---:|---:|---:|---:|---:|---:|
| 2025 training | -10.1364% | 19.0126% | 892 | -$11.3637 | 0.9123 | 1 |
| 2026 report-only | +10.2791% | 13.4818% | 995 | +$10.3308 | 1.0809 | 0 |

The complete position and fill ledgers also match in trade selection, action
values, references, prices, timing, fills, and PnL. The sole field difference
is the timeframe label for 36 training and 41 test stop references named
`yesterday_high` or `yesterday_low`: the baseline fallback mislabeled these
calendar-level references as M1, while the refactored source correctly labels
them D1. Stop prices and all execution/equity results are unchanged. This is a
metadata correction, not a policy or execution change. The comparison outputs
are `outputs/agent_state/architecture_refactor_checkpoint_reanalysis_baseline_3fbbb74/`
and `outputs/agent_state/architecture_refactor_checkpoint_reanalysis_20261030_matched/`;
the baseline replay log is
`outputs/agent_state/architecture_refactor_checkpoint_reanalysis_baseline_3fbbb74.run.log`.

After the replay, the import/invocation and checkpoint inventories allowed
safe retirement of seven redundant forwarding modules:
`evaluation.plotting.replot_orders`, `evaluation.reporting.export`,
`evaluation.reporting.summary`, `evaluation.rollout.model`,
`evaluation.rollout.runner`, `experiments.variants.runner`, and
`features.po3.config`. Their callers and documentation now use the owning
modules. The historical evaluation import test was reduced to the one adapter
used by frozen reanalysis launchers, and tests now import the canonical
ablation lifecycle. Keep the remaining adapters with demonstrated contracts:
`evaluation.reanalysis.runner` is invoked by frozen research launchers;
`experiments.runs.execution` is called directly by retained Slurm launch
scripts; `compute.slurm.resume` owns the existing compute CLI command; and
`models.encoders.core.TCNEncoder` is referenced by one of the 2,175 inventoried
saved checkpoints. They contain no competing domain implementation. The
remaining compatibility dispositions are recorded in the path inventory and
script migration ledger.

The final GH200 validation passed: full-tree Ruff format (847 files), Ruff
lint, and Mypy (847 source files), plus 65 focused reanalysis, experiment CLI,
report export, PO3, and architecture filename tests. Two existing pandas
deprecation warnings were emitted. The prior consolidated full repository
gate remains recorded above. No model training, research benchmark, experiment run,
data/cache rebuild, commit, or push was run for this closeout. The approved
allocation `21301784` remains running in its persistent tmux shell for reuse.
With source-matched numerical parity and only supported compatibility
contracts retained, Phase 11 and the ordered refactor plan are complete.

The post-retirement full gate passed on the same GH200 allocation; its log is
`outputs/agent_state/repository_refactor_full_ci_final6_20261030.run.log`.
Dependency lock/export and both security checks passed; full-tree Ruff format,
Ruff lint, and Mypy passed (854 source files); architecture (43), graph
quality (17 plus live graph verification), contracts (78), unit (2,054 passed;
388 deselected), package build/import, integration (315), execution parity
(65), and synthetic PPO/SAC smoke (12) all passed. No Slurm job was submitted
or cancelled.

## Trading-policy and repeated-payout invariants

Architecture refactoring must preserve:

- selectable legacy policy;
- repeated-payout policy;
- $100,000 operating balance;
- $110,000 realized-balance payout target;
- $90,000 static account floor;
- fixed-session $5,000 daily-loss constraint;
- disabled account-level trailing drawdown in repeated-payout mode;
- 0-0.90% continuous agent risk;
- zero risk as a valid no-trade action;
- requested versus approved/executed risk diagnostics;
- execution-reserve-aware sizing;
- flat realized payout trigger;
- cumulative payout accounting;
- chronological continuation across evaluation cycles;
- single-cycle training behavior.

Equations and state transitions belong in `trading`; environment sequencing belongs in `simulation`.

## Cross-cutting research invariants

No architecture phase may weaken:

- causal features;
- train-only normalization;
- locked OOS separation;
- purged walk-forward behavior;
- session eligibility semantics;
- cache identity/versioning;
- train/evaluation/backtest execution parity;
- checkpoint reproducibility;
- deterministic provenance;
- experiment seed identity.

## Size and complexity guidance

Architecture is package-first, but size remains a warning signal.

- aim for cohesive modules usually below roughly 800 lines;
- investigate functions above roughly 150 lines;
- orchestration functions above roughly 250 lines should usually be decomposed;
- avoid classes above roughly 1,000 lines unless intentionally declarative;
- prefer 3-10 cohesive modules in a subpackage over one monolith;
- avoid one-function micro-modules unless they are genuine boundary abstractions;
- keep `__init__.py` small.

These are review heuristics, not automatic rewrite rules.

## Commit strategy

Implement the refactor in the ordered phases above, but land the completed architecture refactor as **one final commit** after all required validation passes.

During implementation, use the phases as working checkpoints for reasoning, testing, and rollback discipline. Do not create a chain of architecture commits solely because the plan has multiple phases.

Before the final commit:

1. complete every planned ownership move;
2. remove temporary compatibility shims that are no longer required;
3. run the architecture import/dependency checks;
4. run scoped parity tests for every moved subsystem;
5. run the full repository CI gate;
6. run synthetic smoke/contract tests and fixed-checkpoint reanalysis where
   required; run a real model-training smoke only when the active goal
   authorizes training;
7. inspect the final diff for semantic drift and unrelated dirty-tree changes;
8. stage only the architecture-refactor files and intended compatibility updates.

Use one detailed commit message that describes the repository-wide package architecture, major ownership moves, compatibility guarantees, and validation performed.

## Agent execution guidance

For each phase, an implementation agent should:

1. read this plan;
2. inspect the owning package's `__init__.py`;
3. inspect only the source methods and callers involved in the move;
4. inventory every config/data/cache/output/log/baseline path read or written by those callers;
5. identify the producer, consumer, identity inputs, schema, completion rule, and retention class for generated artifacts;
6. inventory duplicated helpers/functions in the affected ownership boundary and decide whether each stays local, moves to the owning package, or becomes a shared primitive;
7. write equivalence/characterization tests before replacing duplicated behavior;
8. perform a semantic naming audit for moved modules, functions, state fields, config keys, metrics, artifacts, tests, and docs; replace ordinal/placeholder names with domain names where compatibility allows;
8a. audit filenames across every active repository area, explicitly disposition phase/ordinal-prefixed files, and preserve only provenance- or public-contract-backed aliases with a test and expiry condition;
9. verify that extracted functions represent meaningful responsibilities rather than numbered fragments;
10. audit every execution surface that invokes the moved responsibility: console commands, Python scripts, shell/Slurm wrappers, tools, Docker, GitHub workflows, and saved experiment run commands;
11. migrate those callers to one stable package API or gate command and remove duplicated orchestration logic;
12. add missing characterization tests first;
13. create the target package/subpackage with `__init__.py`;
14. move one coherent responsibility;
15. expose the intended public API;
16. add a forwarding compatibility import if required;
17. migrate direct callers;
18. run scoped parity tests;
19. run architecture import/dependency tests;
20. inspect the diff for semantic drift;
21. run the repository commit gate;
22. update architecture/domain documentation.

The agent should not redesign the entire repository during every phase.

## Definition of done

The repository-wide architecture refactor is complete when:

- repository-root packages express the domain architecture directly;
- repository-root asset/generated directories have explicit ownership, lifecycle, and retention rules;
- shared configuration resolution has one implementation and historical resolved configs remain interpretable;
- generated artifacts have typed identities, manifests, provenance links, completion semantics, and regeneration paths;
- datasets and partitions are identified by manifests rather than inferred only from filenames;
- caches are disposable, validated, identity-keyed, and never the sole source of research evidence;
- run/experiment_run/evaluation outputs are immutable artifact trees with canonical manifests;
- run-scoped logs are colocated with their owning artifacts and scientific state is not log-only;
- baselines can only be created through an explicit validated promotion workflow;
- scripts, tools, and CI wrappers contain no duplicate domain algorithms;
- stable console commands, scripts, Docker, Slurm, tools, and CI converge on the same package APIs;
- one canonical validation-gate vocabulary is shared by local development and hosted CI;
- normal `ci.yml` contains the nine target semantic jobs (`dependency-lock`, `quality`, `architecture`, `contracts`, `unit`, `build-smoke`, `integration`, `parity`, `training-smoke`), the three independently justified assurance gates (`security-deps`, `security-secrets`, `graph-quality`), and the `ci-success` aggregator; any consolidation is backed by coverage-equivalence and branch-protection evidence;
- every current script has a resolved migration-ledger disposition and no generic script category survives without a defined steady-state role;
- `ci-scripts/` is removed if no irreducible platform-only glue remains;
- hosted CI avoids redundant full-suite execution unless each run validates a distinct environment contract;
- test markers form a scheduling contract for unit, integration, slow, GPU, Triton, and research validation;
- CPU CI uses isolated data/artifact roots and cannot consume developer caches or outputs accidentally;
- Triton/GPU validation is explicit for resource-sensitive training and experiment run behavior;
- Docker/release automation exists only for supported reproducibility/runtime needs and has no stale command paths;
- high-value shared primitives have one semantic owner and one canonical implementation;
- no catch-all utility package becomes a dependency dumping ground;
- every duplicate-function replacement with research impact has explicit result-equivalence coverage;
- public names express domain intent and avoid ordinal/placeholder naming except where the number is part of the domain contract;
- every active repository file has a reviewed functional name, correct owner/location, and recorded disposition; this includes tests, configs, commands, tooling, documentation, report generators, and artifact producers, not only Python source and `scripts/`;
- phase/work-package identifiers do not appear in active filenames as substitutes for behavior names; any required historical identity is preserved in metadata/source snapshots, and every remaining live alias has a demonstrated external contract, test, owner, and expiry condition;
- old active references to renamed paths are migrated across imports, configs, console entry points, workflows, Slurm scripts, docs, and tests, and a repository search confirms only the intended historical provenance remains;
- phase-prefixed thesis evidence source identities remain hash-verifiable through immutable snapshots and provenance mappings, without making phase-prefixed commands the canonical implementation;
- extracted functions represent meaningful responsibilities rather than `part1`/`part2` decomposition;
- canonical vocabulary is consistent across code, config, state, metrics, artifacts, tests, and documentation;
- ordinary tests never mutate repository data/cache/output/log/baseline roots;
- generated documentation/evidence records its generator and source artifacts;
- every importable package/subpackage has an intentional `__init__.py`;
- public imports are obvious and protected by tests;
- the trading environment is a thin simulation facade rather than a mechanics container;
- trading equations and state transitions have one owning package;
- training coordinates services instead of owning upstream domain behavior;
- feature construction is a named causal pipeline;
- evaluation has one canonical package;
- experiment run logic is reusable package code rather than script internals;
- live logic is broker-neutral and external systems are isolated under integrations;
- scripts are command wrappers rather than libraries;
- build, lint, type-check, and test configuration recognize the root packages;
- architecture docs and the actual directory tree agree;
- no implementation-bearing or unreviewed compatibility imports remain;
  preserved paths must have a named owner and a demonstrated frozen-launcher,
  public CLI, or serialized-checkpoint contract;
- deterministic parity, checkpoint loading, synthetic training smoke tests,
  and OOS reanalysis remain valid; real training is a separately authorized
  research activity, not an architecture-refactor gate;
- a developer can identify where to import and where to modify a concern by reading the repository tree and package `__init__.py` files.

## Implementation record — 2026-10-30

The repository refactor and behavior-based test reorganization are implemented on
`main`. The migration ledger and immutable source archive preserve renamed-path
provenance. Historical thesis and research evidence files were kept byte-for-byte;
the result-manifest reader accepts both the preserved legacy ledger identity and
the current experiment-run identity.

Tests now live under `tests/unit/`, `tests/integration/`, `tests/research/`, and
`tests/architecture/`. Test names describe observable code behavior or contracts,
not plan phases, work packages, or suite categories. Adapter-identity checks were
removed where they duplicated no behavior guarantee. The ownership inventory is
checked against the active repository file set, and path migrations are checked
against archived source hashes. The user-owned `campaign_worker_dispatch.log`
remains untracked and unchanged.

The required full gate completed successfully in the existing GH200 allocation;
no training was run for this refactor. Results were: Ruff format and lint passed;
Mypy passed for 860 source files; 46 architecture tests, 17 graph-quality tests,
78 contract tests, 2,079 unit tests, 242 integration tests, 74 parity tests, and
12 training-smoke tests passed. Dependency lock/export, dependency-security,
secret scanning, package build/import, and `git diff --check` also passed. The
captured gate log is `outputs/agent_state/repository_refactor_full_current_20261030.log`.
