---
trigger: model_decision
description: "Use when designing study coverage or implementing from a study plan."
---

# Study planning and implementation

- Examples illustrate a category, not its full scope. Expand to other
  source-backed cases in that category. Narrow scope to the named example only
  when the user explicitly asks to change that behavior.
- Every module profile records its owned source, config, focused tests,
  imported public API files, and external caller files. The catalog rejects
  stale API/caller inventories when the import graph changes.
- Before implementation is delegated, the planning owner maps each active
  module, relevant configuration, public boundary, caller, and existing test
  to a specific study, contract check, or evidence-backed disposition.
- Study entries provide `question`, `source_paths`, effective config inputs,
  registered factors or arms, outputs, focused checks, and an acceptance rule.
  Register only explicit combinations; never infer Cartesian products.
- Implementers follow the completed plan and do not reopen scope or
  repeat repository discovery. They may verify assigned paths and checks. If
  source contradicts the plan, stop and report the exact discrepancy to the
  coordinator before changing scope.
- Do not turn a code check or readiness audit into an empirical claim. Runs
  still require the applicable research and launch authorization.
