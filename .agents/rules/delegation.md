---
trigger: model_decision
description: "Use before native subagent delegation, parallel work, or session reuse."
---

# Delegation and ownership

The Architect can investigate, implement, test, review, and integrate. Use a
specialist only when its bounded output can start now, remains useful by
itself, has a single owner, and improves the critical path or correctness.
Root-only work is valid; there is no minimum agent count.

## Scheduling

- Parallelize only ready independent work with disjoint files and mutable
  resources. Draw dependencies first; never delegate a blocked task.
- Root-only work is the default when delegation does not shorten the critical
  path. Add one specialist for one useful independent result; add more only for
  additional ready workstreams with disjoint ownership. Codex may run up to
  four spawned workers plus the root; this is a ceiling, not a target.
- Never exceed the active host's actual agent-slot limit; project config cannot
  create runtime capacity.
- The root is the only coordinator. Workers do not spawn workers by default.
- Reuse the canonical role agent for a related follow-up while its context is
  still relevant. Start fresh after a material source or task change.
- Never run competing writers on the same checkout or share mutable cache,
  checkpoint, database, or output roots. Use isolated worktrees only from a
  clean committed base; otherwise keep edits serial.
- QA and independent review start after the relevant implementation exists.
  Reviewers are read-only by workflow, not by claimed technical enforcement.

## Canonical roles

| Role | Owns and may edit | Must not take over |
|---|---|---|
| `architect` | Cross-domain contracts, decomposition, integration, acceptance; assigned coordination docs | Specialist implementation or independent review sign-off |
| `ml_engineer` | `configuration/`, `config/`, `decisioning/`, `models/`, `learning/`, `training/`, `experiments/`, `compute/`, assigned tests | Trading/data meaning, risk semantics, protocol decisions, host/resource operations |
| `data_scientist_engineer` | `market_data/`, `features/`, and directly owned tests | Trading interpretation, account/execution, policy/optimizer code |
| `quantitative_trading_engineer` | `trading/`, `simulation/backtest/`, assigned execution/risk files in `simulation/environment/`, trading tests | Data-pipeline implementation, policy/optimizer, protocol changes |
| `evidence_reporting_engineer` | `artifacts/`, `evaluation/`, assigned reporting, documentation structure/build/inventory tooling | Experiment lifecycle, producer metric meaning, data/policy/execution semantics, claim acceptance |
| `ci_operation_engineer` | `.github/workflows/`, `tools/check*`, CI tests/config; coordinates source fixes with owning specialists | Domain behavior, push/merge/workflow reruns without authorization |
| `resource_monitoring_engineer` | Read-only resource inspection; approved environment setup and inspected disposable-file cleanup; assigned resource helpers | Model design, source/checkpoint/log/evidence deletion, job cancellation |
| `qa_engineer` | Assigned test-only edits and independent test design | Production behavior or weakened assertions |
| `independent_reviewer` | Read-only review; no file edits | Editing the implementation or duplicate generic reviews |

The Architect names one writer for any shared file. Domain owners retain
technical meaning; the Architect alone freezes protocols and accepts
scientific claims. Paths are ownership defaults, not access-control: for a
shared file the coordinator names one writer before edits, then assigns all
other work on that file read-only.

## Assignment and handoff

Every assignment states goal, acceptance, owned/forbidden paths, source anchors,
verified facts, dependencies, resource limits, effort, tool allowance, and
handoff location. Do not forward the conversation or paste large source/logs.
Create persistent artifacts under
`logs/agents/<canonical_role_id>/<YYYYMMDD>_<task_slug>/` before work starts.
Use the schemas in `.agents/schemas/` for shared facts, delegation briefs, and
handoffs. Report exact checks and unresolved dependencies.

For a stable job expected to run at least 30 minutes, assign at most one timed
check at a time to the reusable Resource Monitoring Engineer when monitoring
delegation is authorized. Set the check for 30 minutes when the measured finish
estimate is at least 30 minutes away; use 15 minutes when completion, an
allocation transition, or output verification is closer. If completion is
expected sooner, wait once for that estimate. The monitor waits silently and
reports only a state change, failure, or completion; it does not send unchanged
poll results. Re-estimate before assigning the next check. Do not create a new
polling agent for each job. The 60-second wait limit for a new Slurm allocation
remains in `triton-slurm.md`.

## Git and permissions

Inspect branch, source revision, dirty paths, and active runs before dispatch.
Do not reset, clean, stash, move, or overwrite unrelated changes. Workers do
not rebase, merge, push, or alter refs on shared branches. A worker may commit
only on its own feature branch in its own isolated worktree, and only when the
coordinator has authorized commits for that task. Preserve user authorization
gates in `git-commit-rules.md` and `ci-verification.md`.

## Plan workflow (native modernization)

This section governs the plan-driven workstreams in
`planning/native_modernization/OPERATING_MODEL.md`. It is a delegation pattern
on top of the rules above, not a new roster.

- **Streams.** At most four stream agents run at once. Each takes one ready
  work package with disjoint paths, works in a detached worktree from the
  current integration branch, and returns commits, changed paths, and exact
  command results. The coordinator turns each stream's commit into a feature
  branch and a pull request.
- **Integration branch.** Work lands in `main-native` through pull requests
  from feature branches. Streams never edit `main-native` directly.
- **Trackers.** The main tracker keeps a worktree on remote `main` and reports
  what changed there. The main-native tracker is report-only: it finds fixes
  that also belong on `main`. Neither tracker pushes unless the coordinator names
  the commits and the batch.
- **Gate.** CI on each pull request is the gate. Merge only when every required
  check is green, using rebase or squash. No merge commits, no force-push on
  `main`, and force-push only on feature branches.
- **Resource operator.** The coordinator alone requests Slurm allocations (one
  `srun` at a time) and owns the file-quota budget. Streams never run Slurm.
- **Gates that CI does not enforce.** A check not in CI is run locally before
  the PR is opened. Today this includes full-tree mypy; add a CI job when one is
  created.
- **Subprocess imports.** Tests that run a script or subprocess from a worktree
  set `PYTHONPATH` to that checkout, because a shared virtualenv can point at a
  different checkout.
