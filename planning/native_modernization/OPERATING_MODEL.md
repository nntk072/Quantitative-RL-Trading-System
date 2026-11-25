# Operating model: five roles

Goal: finish the native modernization plan on `main-native` while keeping `main` a Python-only framework that gets the findings that help it.

## 1. Orchestra (project manager)

- Owns the plan, the work-package ledger (`work_package_ledger.json`), the decisions log, and the order of work.
- Splits work into streams with disjoint files, assigns each stream to one agent, and accepts a commit only with its evidence.
- Decides promotions: which commits go to `main` (see 3) and when a batch is ready.
- Writes the status reports and the final report.
- Implemented by the lead session. The repository's `orchestra/` package is not used: it was removed from `main` in `26ad3e8d`.

## 2. main-native (multi-language framework)

- Branch `main-native`, worktree `/scratch/work/nguyenl37/worktrees/main-native`.
- Rust crates under `native/`, Python bindings, planning and the Cargo workspace.
- Parallel streams run in detached worktrees off `main-native`, one agent per stream, each with its own files:
  - data and features;
  - native kernels (domain, execution, decisioning, environment);
  - verification (mutation checks, oracles);
  - compute and resource runtime.
- Streams commit to their detached worktree. The lead cherry-picks their commits into `main-native`, runs the batch checks, and removes the stream worktree.
- Shared resources: one Python venv (`.venv-x86`) for Python work, one `CARGO_TARGET_DIR` for Rust builds, and no per-stream venv.

## 3. main (Python-only framework)

- Only Python code, config and generated docs that `main` already uses. No Rust, no `native/`, no `planning/`.
- Receives `main-native` findings that fix problems in the current Python framework, even when they are unrelated to the multi-language work. Examples: oracle tests that catch defects, study-catalog registrations, converter quarantine logic.
- Publishing rule: a batch of named commits, one push, then watch CI (CI, Documentation website, CodeQL) to completion. No per-commit pushes. No force-push, no PRs, no merge commits.

## 4. main -> main-native (incoming)

- The tracker keeps a worktree on remote `main` and reports every change to it.
- Changes that matter to the plan are brought in either by cherry-pick (small, Python-only) or by updating the planning framework to match (for example, a new upstream commit changes a generated doc, so it is regenerated on `main-native` instead of being picked).
- Generated docs are regenerated, never cherry-picked.

## 5. Resource operator

- Owns Slurm allocations: one `srun` at a time, only from named tmux sessions, `--immediate=60`, never `scancel` except the owner-named jobs.
- Owns the file quota. Current budget: about 250k files free. Each worktree costs about 3k entries, the venv about 600, the Rust target about 1k. Stream worktrees are removed after their commits are merged.
- Requests the GH200 aarch64 build and any benchmark allocations, and reports them to the lead before running.
- Records every allocation (job id, partition, CPUs, memory, time, owner) in `logs/agents/architect/2026-11-25_native_goal/RESOURCES.md`.

## Parallel trackers (added by owner instruction)

Two trackers run in parallel with the stream agents. Each has its own worktree and may edit files there when needed.

- **Tracker main** (`/scratch/work/nguyenl37/worktrees/main-tracker`, detached on remote `main`): keeps `main` current, reports changes on remote `main`, and publishes only the commit list the lead names. Each publish is one push, followed by a CI watch to completion. No force-push, no PRs, no merge commits.
- **Tracker main-native** (its own detached worktree, created when it first needs to edit): finds `main-native` fixes that also belong on `main` and prepares candidate batches. It may edit and test in its own worktree. It never pushes, and its candidates reach `main` only through tracker main on a named batch.

Rules that apply to both trackers:
- They never change `main-native` itself. Commits reach `main-native` only through the lead's cherry-pick.
- Each worktree counts against the file quota, and it is removed when the tracker finishes its task.

## Handoffs

| From | To | Handoff |
|---|---|---|
| Orchestra | streams | exact work package, allowed paths, acceptance, output |
| streams | Orchestra | detached commits, changed paths, exact command results |
| Orchestra | main-tracker | publish request: named commits, one batch |
| main-tracker | Orchestra | remote SHA, CI results, conflicts |
| Orchestra | Resource operator | allocation request with the reason and the time budget |

## Rules for every role

- Never claim a check passed unless it ran, and record its exit code.
- Never fabricate a measurement or a gate result.
- Work that needs the owner's decision is recorded in `DECISIONS.md` with the least irreversible choice.

## Publishing (replaces the named-batch rule, owner-approved 2026-11-26)

- Each batch goes to `main` as a pull request from a feature branch. The branch is cut from the current remote `main`, carries only the Python-only commits the lead names, and includes the study-catalog registrations and regenerated docs those commits need.
- CI on the pull request is the gate. The tracker watches it, and merges only when every required check is green.
- Merge with rebase (or squash). No merge commits. Force-push only on feature branches, never on `main`.
- Feature branches may be pushed to origin. `main-native` stays local.
