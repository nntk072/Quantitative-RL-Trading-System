---
trigger: model_decision
description: "Rule index for choosing the applicable repository-wide agent, coding, review, CI, security, and compute instructions."
---

# Agent rules index & activation map (Quantitative-RL-Trading-System)

Shared rule index for every coding agent, regardless of model or tool. Canonical
engineering rules live in `AGENTS.md` and `.agents/rules/`; platform folders
contain only native profile adapters.

## Rule files

| File | Topic | Always on? |
|---|---|---|
| [antigravity-rtk-rules.md](antigravity-rtk-rules.md) | RTK CLI proxy (`rtk` prefix) | Yes |
| [token-efficient-context-replies.md](token-efficient-context-replies.md) | Read/context/reply discipline | Yes |
| [token-efficient-shell.md](token-efficient-shell.md) | Compact terminal commands | On shell use |
| [git-commit-rules.md](git-commit-rules.md) | Commit format + pre-commit checks | On commit/PR |
| [python-coding-standards.md](python-coding-standards.md) | Python style & structure | On `.py` edits |
| [code-review-graph.md](code-review-graph.md) | Graph-based change review | On multi-file review |
| [testing-rules.md](testing-rules.md) | TDD, AAA, measured line and branch coverage baseline | On feature/bugfix work |
| [security-rules.md](security-rules.md) | Secret & input safety checklist | Always at commit; deep on sensitive code |
| [development-workflow.md](development-workflow.md) | Research-first → plan → TDD → review → commit | On non-trivial features |
| [agent-planning-implementation.md](agent-planning-implementation.md) | Consistent repository inspection, naming, implementation, verification, and handoff rules for every agent model; keep agent plans outside the repo | Always |
| [agent-coordination.md](agent-coordination.md) | Subagent roles, file ownership, concurrency, research handoffs, CI boundaries, worktrees, and timed monitoring | When delegating |
| [ci-verification.md](ci-verification.md) | **Blocking** full-tree `ruff` + `mypy .` (not path-scoped); scoped pytest before commit/push | On commit/push |
| [triton-slurm.md](triton-slurm.md) | Use suitable existing GPU-node allocations for research computation when GPU-capable; CPU-only heavy work runs inside a properly sized CPU-node `srun` launched from persistent login tmux; heavy work never runs on normal login; inspect GPU/CPU/RAM; never use `srun --test-only` or `scancel`; preserve pending/active jobs | On Triton / GPU training |

## Activation flow

```
request
  ├─ ALWAYS: token-efficient-context-replies + RTK prefix (antigravity-rtk-rules)
  ├─ ALL tasks?               → agent-planning-implementation
  ├─ delegating?              → agent-coordination + matching platform profile
  ├─ running commands?        → token-efficient-shell (+ RTK)
  ├─ non-trivial feature?     → development-workflow
  │                             ├─ research/reuse first
  │                             ├─ plan (blast radius via code-review-graph)
  │                             ├─ TDD → testing-rules
  │                             └─ self-review via code-review-graph
  ├─ editing .py files?       → python-coding-standards (via token-efficient reads)
  ├─ reviewing a diff >1 file → code-review-graph
  ├─ editing code?            → scoped ruff + pytest on touched paths only
  ├─ Triton / GPU train?      → triton-slurm (reuse first; live inventory, tmux allocation, no cancellation)
  └─ committing / push / PR   → git-commit-rules + ci-verification + security-rules
                                  └─ BLOCKING: ruff format --check . → ruff check .
                                     → mypy . (FULL TREE — never path-scoped mypy)
                                     → pytest <relevant paths> -q
                                     (NOT full tests/ -v; that is CI/Orchestra);
                                     fix format drift with `ruff format .` first;
                                     scoped ruff/mypy while editing ≠ commit gate
```

## Priority

Layered principle: **specific overrides general**.

1. **RTK** wraps every command — never run raw commands.
2. **Token-efficiency** (context + shell) governs all I/O volume.
3. **Domain rules** (Python standards, testing, security, commit rules, review graph, workflow) apply by activity, layered on top of 1–2.
4. **Triton:** reuse existing GPU tmux/`srun` first for GPU-capable research
   computation. CPU-only work runs inside a properly sized CPU-node `srun`
   launched from persistent login tmux; never run compute on normal login.
   Standing user authorization permits necessary research allocations. Inspect each candidate
   node's live GPU, CPU, and RAM inventory, then run a real bounded `srun`
   from a named, persistent login tmux session when a compatible GPU is idle.
   Never use `srun --test-only` or scheduler forecasts.
   Stop polling after 60 seconds but leave pending jobs untouched; do not make
   overlapping requests or short diagnostic steps. Never call `scancel`.
5. When two rules conflict, the more specific one for the current activity wins; when still ambiguous, ask before proceeding.

## Platform adapters

- Codex profiles: `.codex/agents/*.toml`
- Claude Code profiles: `.claude/agents/*.md`
- Antigravity profiles: `.agents/agents/*.md`

All three use the canonical IDs in `agent-coordination.md`. Ownership changes
belong in that shared rule first; keep platform profiles concise and aligned.
Persistent subagent logs and handoffs belong in the Git-ignored
`logs/agents/<canonical_role_id>/<YYYYMMDD>_<task_slug>/` directory.
