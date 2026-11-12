# Codex subagent coordination

Use this rule with the role profiles in `.codex/agents/`. It coordinates work;
the repository's existing `AGENTS.md` and `.agents/rules/` remain authoritative
for architecture, implementation, tests, security, CI, and compute operations.

## Team shape

The Architect is the coordinator and owns study-protocol decisions, cross-
domain contracts, integration, and final acceptance. Configuration, Data, RL,
Risk, Experiment & Compute, and Evidence & Reporting Engineers own the domain
implementation boundaries below. The CI Gate Engineer owns CI/GitHub gate
diagnosis. The QA Engineer owns independent test design and assigned test-only
edits. The Independent Reviewer performs a read-only review after integration.
A Campaign Monitor may perform one scheduled read-only check per assignment.

Use at most **three concurrent agents total by default**: the root coordinator
and two subagents. Codex counts spawned-agent threads separately from the root,
so `.codex/config.toml` sets the cap to two. Scale to five agents total only
when the coordinator records at least four independent workstreams, disjoint
file/artifact ownership, and sufficient measured compute and shared resources.
On a host that supports five total agents, override the spawned-agent cap with
`codex -c agents.max_concurrent_threads_per_session=4`. Never exceed the active
host's actual concurrency limit. Do not spawn every role for each task. The
Architect remains the single integrator and does not delegate coordination
recursively unless the user explicitly asks.

## Task-specific reasoning effort

Do not pin `model_reasoning_effort` in individual role profiles or set a global
`agents.default_subagent_reasoning_effort`. The coordinator chooses effort for
each new task through the spawn-time `reasoning_effort` override. Omit a fixed
profile effort so the spawn-time choice can match the actual assignment.

| Task shape | Spawn effort | Examples |
|---|---|---|
| Simple retrieval or status | `low` | Read one manifest, list checks, inspect a bounded file set |
| Focused engineering | `medium` | Trace a scoped contract, draft a focused test plan, implement a bounded change |
| Multi-step diagnosis or safety-sensitive review | `high` | Root-cause a CI gate, assess risk/causality, review cross-domain behavior |
| Unusually difficult, high-impact uncertainty | `xhigh` | Use only when the extra depth can change a consequential decision |

Do not use `max` as a blanket setting. If the selected model does not support
the chosen effort, use a supported level or omit the override to use its model
default. A follow-up task keeps the agent's current reasoning setting; when a
materially different effort is needed, assign the override on a newly spawned
agent only if the work warrants a separate task. Do not create agents solely
to change effort.

Prefer parallel read-only investigation first. Start code writers in parallel
only when their owned files and outputs are disjoint. Run QA and independent
review after the relevant implementation is available; they may inspect the
same source, but only the assigned writer may edit production files.

## Responsibilities and file ownership

| Role | Owns | May edit | Must not take over |
|---|---|---|---|
| Architect | Cross-domain contracts, task decomposition, integration, final acceptance | Coordination and architecture documentation when assigned; integration changes only after naming a single owner | Domain implementation already assigned to a specialist; independent review sign-off |
| Configuration Engineer | Configuration loading, merge/override behavior, schemas, validation, canonical paths, and resolved configuration identity | `configuration/`, `config/`, and directly owned tests when assigned; domain specialists retain semantic ownership of their settings | Domain algorithms, experiment lifecycle, or changing a domain setting's meaning without its owner |
| Data Engineer | Market data ingestion, transforms/splits, feature production and causality | `market_data/`, `features/`, and tests directly owned by those packages when assigned | Environment risk/execution semantics, learner/policy code |
| RL Engineer | Observation/action policy interfaces, model encoders, learners, training orchestration | `decisioning/`, `models/`, `learning/`, `training/`, plus explicitly assigned observation/action files under `simulation/environment/` | Market-data source semantics, account ledger and risk enforcement |
| Risk Engineer | Account, order, execution, risk, simulator and backtest semantics | `trading/`, `simulation/backtest/`, and explicitly assigned execution/risk files under `simulation/environment/` | Feature generation, policy architecture or optimizer behavior |
| Experiment & Compute Engineer | Experiment definitions and run lifecycle, run orchestration/recovery, compute capacity, resource sizing, and Slurm adapter/safety mechanics | `experiments/`, `compute/`, and their directly owned tests when assigned | Scientific protocol or policy decisions; data, execution/risk, evaluation/inference semantics, or artifact/report meaning |
| Evidence & Reporting Engineer | Generic artifact provenance, ledger-based evaluation and inference, reproducible research tables/figures, and thesis Results/Discussion prose | `artifacts/`, `evaluation/`, assigned report builders, and assigned thesis/report output paths | Experiment scheduling/run lifecycle; source-data, feature, policy, execution/risk semantics; producer-specific metric/schema meaning; protocol changes or manuscript acceptance |
| CI Gate Engineer | GitHub Actions, dependency/static/required-check diagnosis and CI reproduction | Read-only by default; when explicitly assigned a fix, `.github/workflows/`, `tools/check*`, and CI-specific configuration/tests only | Application behavior, domain implementation, GitHub comments/PRs, reruns, merge, push, or ref updates without explicit authorization |
| QA Engineer | Independent behavior coverage and validation planning | Test files only, and only for an assigned contract; may run allowed checks | Production source, config semantics, or changing assertions to accommodate a failure |
| Independent Reviewer | Correctness, architecture, security and regression review | No files | Implementing fixes or approving its own changes |
| Campaign Monitor | One scheduled, read-only status check of an assigned live handle | No files; inspect only the state needed for the assigned check | Repeated polling, outcome analysis unless required and authorized, job/step creation or mutation, cancellation, and any training/evaluation work |

The directory table is a starting boundary, not a claim that every file in a
directory has only one concern. For shared files, the Architect names one
primary writer before work starts and assigns other specialists read-only
reviews or separate non-overlapping edits. In particular, split
`simulation/environment/` by the behavior owned by each file. A test follows
the source contract it verifies; QA may edit it only if the task explicitly
assigns the test file to QA. There is exactly one writer per file at a time.

Experiment run identity, recovery, scheduling, and checkpoint lineage belong
to Experiment & Compute. Evidence & Reporting is the sole owner of generic
`artifacts/` identity, manifests, atomic persistence, validation, retention,
and promotion, plus ledger interpretation, evaluation, inference, and report
content. Producer domains own the domain-specific meaning and schema of their
metrics and emitted records, and call the shared artifact API. Configuration
owns central configuration structure and identity; domain owners retain the
meaning of their semantic settings. If a task crosses these boundaries, the
Architect names one writer per shared file and records the handoff. The
Architect alone freezes or changes the study protocol and accepts scientific
claims or committee-facing manuscripts.

## Delegation brief and context budget

Each assignment includes only:

1. one outcome and acceptance check;
2. allowed and forbidden paths, including the single-writer owner;
3. relevant source symbols, tests, and applicable rule links;
4. dependencies, resource limits, and whether edits or read-only analysis are
   requested;
5. expected handoff format and the next dependency.

Do not forward the whole conversation or paste large source files. Point to
repository paths and concise line ranges. Ask each agent to inspect the
applicable `AGENTS.md`, domain map, and rules itself before editing. The
coordinator shares verified findings and decisions so other agents do not
repeat broad discovery. Keep handoffs to a concise summary: files/symbols
checked, finding or patch, exact checks and outcomes, unresolved dependency.

For research tasks, label planning, smoke, pilot, campaign, and report-period
evidence accurately. Never pass interim or unauthorized outcome data to a
worker whose task does not require it. Existing research gates and result
integrity rules remain in force. Preserve causal feature construction,
train-only normalization, purged/embargoed non-overlapping test folds, session
eligibility masks, content-hashed caches, aligned training/live risk, and
locked OOS separation. Use the active research execution plan as the operational
queue; freeze protocol and inference choices before outcome access. Keep run,
artifact, source, config, data, checkpoint, and report identities linked.

## Timed campaign monitoring

Before waiting on a live training, evaluation, or allocation stage, estimate
completion from measured throughput or prior stage duration and compare it with
the allocation limit. Assign at most one Campaign Monitor check at a time: plan
the next check about 30 minutes out when the milestone is farther away, or 15
minutes out when completion is expected within 30 minutes or an allocation
transition/output-verification boundary is near. Each monitor assignment is
one read-only check. If the same handle remains live, recalculate the next
milestone once before assigning another check. Use no tight polling loops and
no more than 10 planned checks for a stable stage. The 60-second maximum for
waiting on a new allocation remains governed by `triton-slurm.md`.

## Git and worktree protocol

- Inspect branch, `git status`, current `HEAD`, active runs, and applicable
  clean-tree guards before delegating. Preserve unrelated edits and outputs.
- Never start multiple writers in the same checkout. For parallel code edits,
  use one isolated Git worktree and task branch per writer, all based on the
  same verified commit. A reviewer uses a read-only checkout or reviews the
  final integrated diff.
- A worktree starts from committed history; it does not contain another
  checkout's uncommitted changes. Do not move, stash, reset, clean, or copy
  dirty work to make parallelism easier. If the needed baseline is dirty, keep
  implementation serial in the authorized checkout or wait for a clean,
  explicitly prepared base.
- Do not let workers independently rebase, merge, push, or alter the shared
  branch. Each writer reports its commit or diff on its task branch. The
  coordinator integrates changes in dependency order, resolves conflicts,
  and reruns affected checks. Push only with explicit user authorization.
- Do not create a worktree just for read-only exploration when a source
  checkout is available. Keep generated caches, datasets, checkpoints, logs,
  and research outputs out of Git worktrees unless the task explicitly owns
  them.

## Concurrency and shared resources

Before dispatch, draw the dependency order and identify shared mutable
resources: files, caches, artifact roots, databases, checkpoint paths, GPU
allocations, Slurm jobs, and persistent services. Parallelize independent
reads freely; serialize writes to shared resources. Use unique output roots
for concurrent evaluations and never let two tasks update the same cache or
checkpoint.

All agents inherit the parent session's permissions, tools, credentials, and
MCP connections. The TOML role profiles provide behavioral boundaries, not
filesystem or command sandboxes. The coordinator must assign worktrees and
review diffs to enforce ownership. Treat the Independent Reviewer as read-only
by instruction and workflow; do not claim Codex TOML technically prevents it
from writing.

The CI Gate Engineer uses connected GitHub read operations to inspect commit
checks, workflow runs, jobs, and logs. For local changes, select checks from
the diff and repository rules; at commit/push time run the required full-tree
format/lint/type gates and scoped pytest. Do not run `./tools/check full` for
every edit; use it only when explicitly requested, in Orchestra phase 9, or
when reproducing a complete hosted failure. Do not comment, create or update
PRs, rerun/cancel workflows, merge, push, or move refs without explicit user
authorization. If CI failure is rooted in application code, report the exact
commit, workflow/run/job, failing step, evidence, and smallest reproduction to
the owning domain specialist instead of taking over the product fix.

Resource allocation, experiment run, polling, and cancellation behavior is
governed by `.agents/rules/triton-slurm.md`. The Experiment & Compute Engineer
owns technical operations only within that rule and the active research plan;
standing allocation authorization is not permission to change experiment
scope. A delegated agent may inspect an existing run when assigned, but must
not create overlapping jobs, modify or cancel jobs, overwrite outputs, or
launch work outside those rules.

## Completion handoff

The coordinator accepts a work item only after the owner reports:

- source and tests inspected;
- exact files changed (or confirmed read-only);
- behavior and failure contract addressed;
- checks actually run and their results;
- conflicts, assumptions, or dependencies still open.

The QA Engineer reports test coverage gaps separately from implementation
findings. The Independent Reviewer reports prioritized findings with source
locations and does not modify files. The coordinator resolves every blocking
finding, checks the integrated diff, then follows the existing testing, CI,
security, and Git rules. Do not report aggregate success by adding partial
checks that do not cover the required gate.

## Adoption and validation

The repository layout is:

```text
.agents/rules/agent-coordination.md   coordination and ownership source of truth
.agents/rules/README.md              rule index and activation map
.codex/config.toml                   project agent enablement and default concurrency cap
.codex/agents/                       one TOML profile per specialist role
.codex/README.md                     setup notes and validation checklist
```

After the files are available in a trusted project and a fresh Codex session
has loaded them, validate in this order:

1. Parse `.codex/config.toml` and every `.codex/agents/*.toml`; verify each
   profile has `name`, `description`, and `developer_instructions`, and names
   are unique.
2. Ask the Architect to report the ownership boundaries and default concurrency
   from this rule without editing files. Confirm the project cap is two spawned
   agents plus the root (three total); use a four-thread override only on a host
   that supports five total and for a task meeting the scaling criteria.
3. Assign each domain specialist and the CI Gate Engineer one short read-only
   mapping task; verify each returns a bounded handoff with concrete repository
   paths and no edits.
4. Ask QA for a focused test plan on a small, known contract; verify it does
   not propose production changes. Ask the Independent Reviewer to review a
   stable diff and verify the review is read-only and finding-led. Use a
   Campaign Monitor only for a concrete scheduled check on a live handle.
5. For the first multi-writer task, start with no more than three total agents,
   isolated worktrees, and disjoint path ownership. Raise to five total only after
   recording the independent workstreams and resource check in the task brief.

If the Codex client does not load project profiles or configuration, check
project trust and the installed client version against the official Codex
custom-agent documentation. Do not work around a loading failure by copying
project rules into global instructions or duplicating this coordination rule.
