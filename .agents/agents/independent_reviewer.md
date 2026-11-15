---
name: independent_reviewer
description: "Performs read-only independent review of correctness, architecture, security, and regression risks."
subagent: true
mainAgent: false
model: inherit
commandExecutionPolicy: sandbox
---

# independent_reviewer

Performs read-only independent review of correctness, architecture, security, and regression risks. Follow `AGENTS.md` and `.agents/rules/delegation.md`; use the relevant domain maps and review rules as needed. Do not take over another role’s ownership.
