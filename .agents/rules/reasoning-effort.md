---
trigger: model_decision
description: "Use when choosing model reasoning effort for root or specialist work."
---

# Reasoning effort

Use the session model unless task needs justify a change. Model identity and
reasoning effort are separate choices. Do not set a global subagent model or
reasoning default in project configuration; Codex supports per-assignment
overrides and each custom profile should inherit the parent by default.

| Effort | Use |
|---|---|
| **Medium** | Normal minimum for meaningful engineering, routine implementation, bounded debugging, tests, and scoped config/docs work. |
| **High** | Unknown cause, cross-package contracts, data causality, execution/risk, public API, security, or substantial review. |
| **XHigh** | Protocol/security decisions, irreversible migrations, conflicting evidence, or final adjudication where extra reasoning can change the decision. |
| **Low** | Trivial retrieval/status only; never downgrade meaningful engineering just to save tokens. |

Use XHigh selectively. If the selected model does not support it, use its
nearest supported level (usually High) and report the limit. Do not create
duplicate role profiles just to change reasoning effort.
