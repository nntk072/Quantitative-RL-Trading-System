---
trigger: model_decision
description: "Use when creating, renaming, or deleting a git branch."
---

# Branch naming

Agents follow the same branch convention as human developers.

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
