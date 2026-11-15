---
trigger: always_on
description: "Use for repository reading, shared facts, durable context, and concise handoffs."
---

# Context management

Classify context as:

- **Authoritative:** current source, config, tests, and immutable run artifacts.
- **Verified shared fact:** source-backed conclusion with revision and location.
- **Historical:** prior plans, notes, and superseded evidence.
- **Speculative:** an unverified explanation or proposal.

## Loading and reuse

- Read only the relevant source slices and task-specific domain map/rule.
- Do not forward conversations, full architecture docs, large logs, or repeated
  source already inspected. Share paths and line ranges.
- Reuse a verified fact for navigation while its source revision is current.
  Reverify when affected source changed, findings conflict, or safety/science
  depends directly on it.
- Prefer the same specialist for related work while context remains relevant;
  start fresh when the source/task changes materially.

## Shared task packets

Substantial delegated work may use the ignored packet
`logs/agents/tasks/<task_id>/context/` with `task.md`, `facts.jsonl`,
`ownership.json`, and `status.md`. Keep it small and task-scoped.

Each `facts.jsonl` record uses this shape:

```json
{"fact":"<verified conclusion>","revision":"<source SHA>","source":"<path::symbol>","verified_by":"<canonical_role>","verified_at":"<UTC timestamp>","stale_if":["<path or condition>"]}
```

The packet is a handoff aid, not a second source of truth. Use
`tools/agent/context-status` to inspect revision and dirty-source staleness.

## Handoff

Use `.agents/schemas/agent-handoff.md`. State the result first, then evidence,
changes, validation, open dependency, and recommended next action. Keep routine
handoffs to a few hundred words; place detailed output in role-owned logs.
