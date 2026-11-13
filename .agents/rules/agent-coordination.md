---
trigger: model_decision
description: "Use when delegating to specialists or coordinating parallel agents, shared files, worktrees, reviews, CI ownership, or timed monitoring."
---

# Cross-platform agent coordination

This file is the canonical role, ownership, delegation, and concurrency contract.
Platform-specific agent files are adapters that point back here; they must not
redefine role ownership. `AGENTS.md` and the remaining `.agents/rules/` stay
authoritative for repository-wide architecture and engineering requirements.

## Team shape

The Architect is the coordinator and owns study-protocol decisions, cross-
domain contracts, integration, and final acceptance. The ML, Data Scientist,
Quantitative Trading, Evidence & Reporting, CI Operation, and Resource
Monitoring Engineers own the domain boundaries below. QA owns assigned
test-only work; the Independent Reviewer performs read-only review.

Use only the canonical role identities listed below. The spawn task name must
be the role name in snake_case; put task-specific scope in the assignment, not
in the identity. Reuse the same role agent across assignments. Never name an
agent after a task, file, failure, or temporary workstream. Use the role IDs
`architect`, `ml_engineer`, `data_scientist_engineer`,
`quantitative_trading_engineer`, `evidence_reporting_engineer`,
`ci_operation_engineer`, `resource_monitoring_engineer`, `qa_engineer`, and
`independent_reviewer`. Add or remove a role
only with user acceptance and by updating this rule and its profile.

Use at most **three concurrent agents total by default**: the root coordinator
and two subagents. Platform adapters should enforce that cap where supported;
otherwise, the coordinator tracks it explicitly. Scale to five agents total
only when the coordinator records at least four independent workstreams,
disjoint file/artifact ownership, and sufficient measured compute and shared
resources. Never exceed the active host's actual concurrency limit. Do not
spawn every role for each task. The Architect remains the single integrator and
does not delegate coordination recursively unless the user explicitly asks.

Codex-specific concurrency: `.codex/config.toml` sets two spawned agents plus
the root. On a host that supports five total agents, use
`codex -c agents.max_concurrent_threads_per_session=4` only after documenting
the scaling criteria above.

## Task-specific reasoning effort

Codex-specific reasoning effort: do not pin `model_reasoning_effort` in role
profiles or set a global `agents.default_subagent_reasoning_effort`. Choose
effort for each new assignment through the spawn-time `reasoning_effort`
override. Other platforms use their supported per-invocation model controls;
do not create duplicate profiles solely to vary effort.

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
| ML Engineer | Configuration infrastructure/schema wiring, observation/action and model contracts, learners/training, experiment lifecycle, measured training throughput and experimental compute design | `configuration/`, `config/`, `decisioning/`, `models/`, `learning/`, `training/`, `experiments/`, `compute/`, and assigned tests; coordinate one writer for shared files | Domain meaning of trading/data settings, account/risk semantics, scientific protocol or evaluation claims, live resource allocation or host/environment operations |
| Data Scientist Engineer | Market-data ingestion, transforms/splits, feature pipelines/cache identity, causality/availability and data-quality analysis | `market_data/`, `features/`, and directly owned tests when assigned | Trading interpretation of features, account/execution semantics, learner/policy code |
| Quantitative Trading Engineer | Account, order, execution, risk, simulator/backtest plus trading concepts, strategy/baseline definitions, market structure and technical-feature specifications | `trading/`, `simulation/backtest/`, explicitly assigned execution/risk files under `simulation/environment/`, and trading-domain tests; can review feature semantics across domains | Owning data-pipeline implementation, policy/optimizer implementation, or changing scientific protocol without the Architect |
| Evidence & Reporting Engineer | Generic artifact provenance, ledger-based evaluation/inference, reproducible research reports, and documentation process/build quality | `artifacts/`, `evaluation/`, documentation structure/build/inventory tooling, assigned report builders and report output paths | Experiment lifecycle; source-data, feature, policy, execution/risk semantics; producer metric/schema meaning; protocol changes or acceptance of scientific claims |
| CI Operation Engineer | Change-to-commit workflow under repository rules: choose/run local checks, observe GitHub CI, diagnose/fix CI issues or delegate source failures to the owner, coordinate fixes, verify, and commit when assigned | `.github/workflows/`, `tools/check*`, CI tests/config; may coordinate domain-owned edits but does not write them | Changing application behavior outside CI ownership; GitHub comments/PRs, workflow reruns/cancellation, merge, push, or ref updates without explicit authorization |
| Resource Monitoring Engineer | Triton and local Linux resource operations: live CPU/GPU/RAM/disk inventory, bounded authorized allocations, environment/package setup, disposable-cache cleanup, resource telemetry, and scheduled job/allocation polling | Read-only resource and status inspection; run approved environment/setup commands; remove only inspected, disposable generated files under repository retention rules; edit resource-operation helpers only when explicitly assigned; keep logs in its canonical ignored task folder | Model/training design, experiment outcomes, source/config/checkpoint/log/research-output deletion, Slurm cancellation, application-code changes, or commit/CI ownership |
| QA Engineer | Independent behavior coverage and validation planning | Test files only, and only for an assigned contract; may run allowed checks | Production source, config semantics, or changing assertions to accommodate a failure |
| Independent Reviewer | Correctness, architecture, security and regression review | No files | Implementing fixes or approving its own changes |

The directory table is a starting boundary, not a claim that every file in a
directory has only one concern. For shared files, the Architect names one
primary writer before work starts and assigns other specialists read-only
reviews or separate non-overlapping edits. In particular, split
`simulation/environment/` by the behavior owned by each file. A test follows
the source contract it verifies; QA may edit it only if the task explicitly
assigns the test file to QA. There is exactly one writer per file at a time.

The ML Engineer owns configuration infrastructure and identity, model/training
implementation, run lifecycle/recovery, compute planning, and Slurm mechanics;
domain owners retain the meaning of their settings and experiments. The Data
Scientist Engineer implements data and feature pipelines. The Quantitative
Trading Engineer owns trading semantics and acceptance criteria for features,
strategies, baselines, execution, and risk. Evidence & Reporting is the sole
owner of generic `artifacts/` identity, manifests, atomic persistence,
validation, retention, promotion, ledger-based evaluation/inference, and the
documentation process; producer domains own metric/schema meaning and technical
claims in their docs. The Architect names one writer per shared file and alone
freezes or changes the protocol and accepts scientific claims.

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

## Agent logs and handoff files

When a delegated assignment needs a persistent log, note, or evidence file,
create `logs/agents/<canonical_role_id>/<YYYYMMDD>_<task_slug>/` before work
starts and save every assignment log and handoff there. Use the exact role ID
from the roster, not a task-specific agent name or a shared `sub_agents`
folder. The root `/logs/` path is ignored by Git; keep execution logs and
temporary handoffs there unless the task explicitly requires a versioned
research artifact elsewhere. Include the relative log path in the agent's
handoff. Do not put subagent logs in an external `agent_plans` directory.

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
the allocation limit. Assign at most one Resource Monitoring Engineer check
at a time: plan the next check about 30 minutes out when the milestone is
farther away, or 15 minutes out when completion is expected within 30 minutes
or an allocation transition/output-verification boundary is near. Each
scheduled check is read-only. If the same handle remains live, recalculate the next
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

Agents inherit permissions and tools according to their platform. Role
profiles provide behavioral boundaries, not reliable filesystem ownership
enforcement. The coordinator must assign worktrees and review diffs to enforce
ownership. Treat the Independent Reviewer as read-only by instruction and
workflow; do not claim a profile technically prevents it from writing.

The CI Operation Engineer owns the change-to-commit workflow under
`.agents/rules/git-commit-rules.md` and `.agents/rules/ci-verification.md`:
inspect the changed paths, select and run applicable checks, inspect GitHub
checks/workflows/jobs/logs, and prepare and create a commit when assigned.
At commit time, run the required full-tree format/lint/type gates and scoped
pytest. Do not run `./tools/check full` for every edit; use it only when
explicitly requested, during Orchestra verification, or when reproducing a complete
hosted failure. If a CI failure is rooted in application code, delegate the
specific fix to its owning specialist with the commit, workflow/run/job,
failing step, evidence, acceptance check, and smallest reproduction; coordinate
the fix and revalidate it. The CI Operation Engineer may edit CI plumbing, not
domain behavior. Do not comment, create or update PRs, rerun/cancel workflows,
merge, push, or move refs without explicit user authorization.

Resource allocation, experiment run, polling, and cancellation behavior is
governed by `.agents/rules/triton-slurm.md`. The ML Engineer owns technical
compute operations only within that rule and the active research plan;
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
.agents/rules/agent-coordination.md   canonical role, ownership, and coordination contract
.agents/rules/*.md                   shared rules with Antigravity activation triggers
.agents/agents/*.md                  Antigravity native profiles
.codex/config.toml                   Codex agent enablement and concurrency cap
.codex/agents/*.toml                 Codex native profiles
.claude/agents/*.md                  Claude Code native profiles
.agents/rules/README.md              shared rule index and platform activation map
```

After the files are available in a trusted project and a fresh platform
session has loaded them, validate the shared rules and native adapter:

1. Parse every native profile format; verify each profile has its required
   fields and maps one-to-one to the canonical role IDs. For Antigravity, verify
   every `.agents/rules/*.md` file has a supported trigger and each custom
   agent profile points back to this shared rule.
2. Ask the Architect to report ownership and the default concurrency from this
   rule without editing files. Confirm the cap is three concurrent agents total;
   apply a platform-specific override only when scaling criteria and host limits
   allow it.
3. Assign each domain specialist and the CI Operation Engineer one short read-only
   mapping task; verify each returns a bounded handoff with concrete repository
   paths and no edits.
4. Ask QA for a focused test plan on a small, known contract; verify it does
   not propose production changes. Ask the Independent Reviewer to review a
   stable diff and verify the review is read-only and finding-led. Use a
   Resource Monitoring Engineer only for a concrete resource operation,
   environment task, cleanup, or scheduled check on a live handle.
5. For the first multi-writer task, start with no more than three total agents,
   isolated worktrees, and disjoint path ownership. Raise to five total only after
   recording the independent workstreams and resource check in the task brief.

If a platform does not load its profiles or rules, check project trust, native
discovery paths, and the installed client version against that platform's
official documentation before changing the shared role contract. Do not work
around a loading failure by duplicating shared role definitions.
