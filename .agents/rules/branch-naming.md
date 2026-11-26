---
trigger: model_decision
description: "Use when creating, renaming, or deleting a git branch."
---

# Branch naming

Agents follow the same branch convention as human developers.

## Classification

Subagent branch classification policy. Branch classification MUST be determined by the primary intent of the repository change, not by the identity, role, or implementation model of the executing subagent.
- Developer, ML Engineer, and Architect implementing new functionality or boundaries: feature/.
- Debugger implementing corrective changes: fix/.
- Refactoring: refactor/.
- Performance optimization: perf/.
- Testing and test-based validation: test/.
- Security: security/.
- Research: research/.
- Experimentation: experiment/.
- Dataset management and processing: data/.
- QA and Auditor: read-only by default; use test/ for test modifications or docs/ for committed verification reports.
- DevOps: infra/, ci/, build/, or config/, depending on the change.
- Documentation and Architect producing design documents: docs/.
- Architect restructuring existing implementations without changing behavior: refactor/.
- Integration: inherit the dominant change prefix. Use integration/ only when a temporary mixed-content integration branch is necessary.
- Reviewer and Orchestrator: no branch unless explicitly assigned a repository modification task.
Agent identity, role, task ownership, review records, and verification evidence MUST be recorded separately in pull request metadata or the execution ledger.
Every concurrently writing subagent MUST operate within an isolated working directory or Git worktree.
Read-only activities MUST NOT require dedicated branches.
Authoritative branches MUST NOT receive direct subagent commits outside the approved integration process.

## Prefixes

Start every branch name with one of these prefixes, followed by a slash:

`feature/`, `fix/`, `hotfix/`, `refactor/`, `perf/`, `test/`, `docs/`, `ci/`,
`build/`, `chore/`, `style/`, `security/`, `infra/`, `release/`, `revert/`,
`experiment/`, `research/`, `spike/`, `migration/`, `data/`, `config/`,
`deps/`, `ops/`.

## Form

- Use lowercase kebab-case after the prefix. Use forward slashes only for
  hierarchy, such as `docs/agent-branch-naming`.
- Give each branch one clearly defined objective. Include a task or issue id
  when one exists, such as `fix/issue-412-ledger-rounding`.

## Lifetime

- Delete a short-lived branch after its work integrates.
- Long-lived branches are `main` and `main-native`, plus the others the
  repository already uses.
- An existing branch with an open PR keeps its name until that PR closes.
  Rename it only after the PR closes, by creating the new branch and deleting
  the old one.
