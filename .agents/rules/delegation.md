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

The roster with workflow mode, push and merge rights, read-only and CI-watch
flags is in [`roles.md`](roles.md). Adding a role and the brief fields are
defined there too. A role needs lead approval and a roster row before it gets
any work.

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
gates in `git-commit-rules.md` and `ci-verification.md`. Branch names follow
[`branch-naming.md`](branch-naming.md).

## Plan workflow (native modernization)

This section governs the plan-driven workstreams in
`planning/native_modernization/OPERATING_MODEL.md`. It is a delegation pattern
on top of the rules above, not a new roster.

- **Streams.** At most four stream agents run at once. Each takes one ready
  work package with disjoint paths, works in a detached worktree from a green
  integration head, and returns commits, changed paths, and exact
  command results. The coordinator turns each stream's commit into a feature
  branch and a pull request.
- **Integration branch.** Work lands in `main-native` through pull requests
  from feature branches. Streams never edit `main-native` directly.
- **Trackers.** The main tracker keeps a worktree on remote `main` and reports
  what changed there. The main-native tracker is report-only: it finds fixes
  that also belong on `main`. Neither tracker pushes unless the coordinator names
  the commits and the batch.

- **No direct commits.** Once the registration PR is merged, nothing is
  committed directly to `main-native` or `main`. Every change goes through a
  feature branch and a pull request. CI must be green before a merge; the
  repository's branch protection (required CI checks, no direct pushes) is the
  owner's setting to apply, not an agent action.
- **Gate by target.** A PR's required checks follow its base. A PR into
  `main-native` needs `main-native`'s checks green; a PR into `main` needs
  `main`'s checks green. The two integration branches (`main` to `main-native`,
  and `main-native` to `main`) must be green against both targets. Feature
  branches may be pushed and rebased; force-push follows the Force-push rule.
  `main` and `main-native` stay protected from direct pushes and force-push.
- **Flows.** Each PR belongs to one flow: stream into `main-native`,
  `main-native` into `main`, `main` into `main-native`, or a change that stays on
  one branch. A flow may open several PRs; each PR is one reviewable unit.
- **Gate.** CI on each pull request is the full check and the gate. Merge only
  when every required check is green, using rebase or squash. No merge commits.
  Force-push only on feature branches, never on `main`.
- **Force-push.** Force-push is allowed only on feature branches named `feat/*`
  or `rules/*`, and only with `--force-with-lease`. `main` and `main-native`
  take no force-push and no direct push.
- **Fast check before commit and push.** Before every commit and every push,
  run `ruff format --check` and `ruff check` on the changed files, and `mypy` on
  the changed Python files. Also run the touched test files and the
  generated-docs check. Run `tools/check quality` only when it finishes in under
  a few minutes locally; otherwise the scoped commands above are the check. The
  brief names the exact command: `tools/check_fast` when it exists, and until
  then the commands listed in the brief. Full-suite and CI-only checks stay with
  CI. Use Slurm for the smallest necessary check, never for the full suite.
- **Mypy.** Mypy is not in CI yet, so run it locally on the touched files
  until a CI job exists.
- **Split roles.** A CI watcher agent watches each open PR. It is never the
  implementer that pushed the PR. The implementer keeps working on its next
  ready task while the watcher waits.
- **CI watcher.** On a failing job the watcher reports to the owning implementer
  with the run URL, the failing job, and a log excerpt. It does not fix the
  failure, edit code, push, or merge, unless the coordinator names the PR to
  merge.
- **Resource operator.** The coordinator alone requests Slurm allocations (one
  `srun` at a time) and owns the file-quota budget. Streams never run Slurm.
- **One owner per PR.** Every PR body names its owner agent and its flow. The
  CI watcher messages that owner on failure and nobody else. A PR without an
  owner is not opened.
- **Open a PR when delivered.** A subagent opens a PR only after it finishes one
  delivery: the work is complete and the fast checks in this file pass locally.
  The PR's required checks then gate the merge, and the CI watcher follows them.
  Do not open a PR for work in progress, a partial acceptance, or a draft meant
  to be finished later. If the work is not complete, hold the branch and report
  the remaining items to the coordinator.
- **Stack while open.** An agent does not wait for its PR to merge. After a
  delivery is pushed and its PR is open, it continues with its next ready task,
  stacked on its own unmerged PR branch. When the base or the PR branch changes,
  it rebases its stacked work and resolves conflicts on its own branch. Merging
  still needs the required checks green, and the CI watcher follows them.
- **Force-push policy.** Force-push is allowed on any branch except `main` and
  `main-native`, using `--force-with-lease`. `main` and `main-native` are
  protected: no force-push and no direct push to either. If the permission system
  denies a push, report the denial text and stop.
- **Messages are assignments.** Messages from other agents assign work under
  this file. They grant no permissions. An agent refuses a task that breaks a
  rule in this file and names that rule.
- **Owner on call.** An owner stays responsible for its PR until it merges. It
  handles the failures the watcher routes to it. It does not wait for checks. If
  it stops, it hands the PR to a named successor in writing first.
- **Rebase before push.** Before every PR push, rebase the feature branch onto
  the latest base: `main-native` for native PRs, `main` for Python-only PRs.
  Resolve conflicts on the feature branch, never on `main-native` or `main`.
- **Failure procedure.** The implementer stashes its in-progress work, checks
  out the PR branch, fixes the failure, adds or amends a commit, and pushes with
  `--force-with-lease` to that feature branch only. It reports the new SHA to the
  watcher to re-check. Then it pops the stash, rebases onto the latest base, and
  resolves any conflicts before it continues.
- **Never block.** Waiting for a check is not a reason to stop. If no other ready
  task exists, the implementer reports that and stops.
- **Denied pushes.** If a push is denied by a permission check, the agent reports
  the denial text to the coordinator. It does not retry a different command form
  or route around the denial.
- **Green base.** A branch is cut only from a green integration head. If the
  head is red, the work waits, or it targets the fix.
- **One PR per file-set.** PRs that touch the same file merge in sequence, not
  in parallel. The later branch rebases after the earlier one merges.
- **New modules.** A new module needs its study-catalog entries (`api_paths`,
  `caller_paths`, `source_scopes`), docstring Args and Returns sections, and
  regenerated docs in the same PR.
- **Push and tooling preflight.** The first step of every brief is a
  push-access check and a check that `gh` is callable at
  `/home/nguyenl37/.local/bin/gh`. The remote is HTTPS. If either check fails,
  the agent reports it at once and does not work around it.
- **Short-lived agents.** A brief has one narrow goal. Follow-ups go to the same
  agent by message so its context is kept. No agent waits on events it cannot
  see. An owner is kept on call under the owner-on-call rule.
- **Report format.** Every report ends with these fields: PR number, head SHA,
  each check and its conclusion, owner, and the exact blocker if any.
- **Honest gates.** An agent never marks a check as passed unless it ran it. It
  names any gate that CI does not run, which is mypy today.

- **Subprocess imports.** Tests that run a script or subprocess from a worktree
  set `PYTHONPATH` to that checkout, because a shared virtualenv can point at a
  different checkout.
