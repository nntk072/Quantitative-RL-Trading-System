---
trigger: model_decision
description: "Index for canonical agent rules and their task triggers."
---

# Agent rules

`AGENTS.md` is the short repository constitution. Use only the rule needed for
the current activity; platform profiles point to these shared rules.

| Rule | Use |
|---|---|
| [core-execution.md](core-execution.md) | Default engineering work loop |
| [delegation.md](delegation.md) | Choosing/spawning/reusing specialists and separating ownership |
| [reasoning-effort.md](reasoning-effort.md) | Selecting medium, high, or xhigh effort |
| [extension-routing.md](extension-routing.md) | Choosing an optional source/tool extension |
| [context-management.md](context-management.md) | Source loading, shared facts, and handoffs |
| [validation-routing.md](validation-routing.md) | Scoped and commit validation |
| [research-integrity.md](research-integrity.md) | Research, runs, evidence, and claims |
| [testing-rules.md](testing-rules.md) | Test design and assertions |
| [python-coding-standards.md](python-coding-standards.md) | Python edits |
| [security-rules.md](security-rules.md) | Security-sensitive changes and commit review |
| [ci-verification.md](ci-verification.md) | Local gates and hosted CI |
| [git-commit-rules.md](git-commit-rules.md) | Authorized commit/push work |
| [triton-slurm.md](triton-slurm.md) | Triton resources, allocations, and polling |
| [agent-tools.md](agent-tools.md) | Project-local optional tool setup; manual reference |
| [code-review-graph.md](code-review-graph.md) | Code Review Graph command reference; invocation criteria are centralized |
| [graphify-obsidian.md](graphify-obsidian.md) | Graphify/Obsidian installation and vault boundary |

Legacy paths remain short compatibility pointers where existing profiles or
external tooling may still link to them. Canonical behavior belongs only in
the rules listed above.
